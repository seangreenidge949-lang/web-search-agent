#!/usr/bin/env python3
"""
Unified web search, scrape, and login management tool.
LLM decides what to search; this script executes and returns structured results.

Usage:
    search.py --platform <id> --query "<keywords>" [--limit N]
    search.py --list-platforms
"""

import os
import sys
import json
import time
import argparse
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from urllib.parse import quote_plus

PROFILES_DIR = Path(os.environ.get("SEARCH_PROFILES_DIR", str(Path.home() / ".web-search-agent" / "profiles")))


# ── Data Model ──────────────────────────────────────────────────────

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    author: str = ""
    date: str = ""
    platform: str = ""
    fetch_method: str = "search_script"
    metrics: dict = field(default_factory=dict)


def truncate_snippet(text: str, max_len: int = 300) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    for sep in ["。", ".", "！", "!", "？", "?", "；", ";"]:
        idx = text.rfind(sep, 0, max_len)
        if idx > max_len // 2:
            return text[: idx + 1]
    return text[:max_len].rsplit(" ", 1)[0] + "…"


# ── Profile Management ──────────────────────────────────────────────

def domain_from_url(url: str) -> str:
    """Extract registered domain for profile lookup."""
    from urllib.parse import urlparse
    hostname = urlparse(url).hostname or ""
    parts = hostname.split(".")
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return hostname


def get_profile(domain: str) -> str | None:
    p = PROFILES_DIR / domain
    if p.exists() and any(p.iterdir()):
        return str(p)
    return None


def create_profile(domain: str) -> Path:
    """Create or get profile directory for a domain."""
    profile_dir = PROFILES_DIR / domain
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


# ── Login Flow ──────────────────────────────────────────────────────

def login_interactive(url: str, profile_name: str = None):
    """Open headful browser for user to complete login (QR code, password, etc.)."""
    from playwright.sync_api import sync_playwright

    domain = profile_name or domain_from_url(url)
    profile_dir = create_profile(domain)

    sys.stderr.write(f"[login] Opening browser for {domain}...\n")
    sys.stderr.write(f"[login] Profile: {profile_dir}\n")
    sys.stderr.write(f"[login] Please complete login in the browser window.\n")
    sys.stderr.write(f"[login] The browser will close automatically after 5 minutes, or when login is detected.\n")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded")

        original_url = page.url
        sys.stderr.write(f"[login] Page loaded: {original_url}\n")
        sys.stderr.write(f"[login] Waiting for login...\n")

        for i in range(100):
            page.wait_for_timeout(3000)
            current_url = page.url

            if current_url != original_url and "login" not in current_url.lower() and "signin" not in current_url.lower():
                sys.stderr.write(f"[login] Redirected to {current_url} — login successful!\n")
                page.wait_for_timeout(3000)
                break

            if i > 0 and i % 10 == 0:
                remaining = (100 - i) * 3
                sys.stderr.write(f"[login] Still waiting... ({remaining}s remaining)\n")
        else:
            sys.stderr.write(f"[login] Timeout reached. Saving profile as-is.\n")

        ctx.close()

    sys.stderr.write(f"[login] Profile saved to {profile_dir}\n")
    print(json.dumps({"status": "saved", "domain": domain, "profile": str(profile_dir)}, ensure_ascii=False))


def check_login(domain: str):
    """Check if a login profile exists and is usable."""
    profile_dir = PROFILES_DIR / domain
    if not profile_dir.exists() or not any(profile_dir.iterdir()):
        print(json.dumps({"domain": domain, "logged_in": False, "reason": "no_profile"}, ensure_ascii=False))
        return

    from playwright.sync_api import sync_playwright

    test_urls = {
        "weibo.com": "https://s.weibo.com/top/summary",
        "zhihu.com": "https://www.zhihu.com/hot",
        "xiaohongshu.com": "https://www.xiaohongshu.com/explore",
    }
    test_url = test_urls.get(domain, f"https://www.{domain}/")

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(profile_dir), headless=True, locale="zh-CN",
            )
            page = ctx.new_page()
            page.goto(test_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            content = page.content()
            login_keywords = ["登录", "signin", "login", "扫码", "qrcode"]
            has_login_wall = sum(1 for kw in login_keywords if kw.lower() in content.lower())

            texts = page.query_selector_all("body *")
            text_count = len([el for el in texts if (el.text_content() or "").strip()])

            ctx.close()

            if text_count > 20 and has_login_wall < 3:
                print(json.dumps({"domain": domain, "logged_in": True, "content_items": text_count}, ensure_ascii=False))
            else:
                print(json.dumps({"domain": domain, "logged_in": False, "reason": "session_expired"}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"domain": domain, "logged_in": False, "reason": f"error: {e}"}, ensure_ascii=False))


PLATFORM_PROFILE_DOMAINS = {
    "weibo": "weibo.com",
    "zhihu": "zhihu.com",
    "xiaohongshu": "xiaohongshu.com",
    "taobao": "taobao.com",
}

PLATFORMS_REQUIRING_LOGIN = {"weibo", "zhihu", "xiaohongshu", "taobao"}

LOGIN_URLS = {
    "weibo": "https://passport.weibo.com/sso/signin?entry=miniblog&source=miniblog",
    "zhihu": "https://www.zhihu.com/signin",
    "xiaohongshu": "https://www.xiaohongshu.com/explore",
    "taobao": "https://login.taobao.com/member/login.jhtml",
}


# ── Adapter Registry ────────────────────────────────────────────────

ADAPTERS: dict[str, callable] = {}
PLATFORM_DESCRIPTIONS: dict[str, str] = {}


def adapter(platform_id: str, description: str):
    """Decorator to register a search adapter."""
    def wrapper(fn):
        ADAPTERS[platform_id] = fn
        PLATFORM_DESCRIPTIONS[platform_id] = description
        return fn
    return wrapper


# ── Output ──────────────────────────────────────────────────────────

def output_results(results: list[SearchResult], platform: str, query: str, elapsed: float):
    for r in results:
        r.platform = platform
        print(json.dumps(asdict(r), ensure_ascii=False))
    sys.stderr.write(f'[search] {platform} | query="{query}" | results={len(results)} | {elapsed:.1f}s\n')


# ── Shared Helpers ──────────────────────────────────────────────────

def _stealth_fetch(url: str, profile_dir: str = None):
    """Fetch with Scrapling StealthySession."""
    from scrapling.engines._browsers._stealth import StealthySession
    kwargs = dict(headless=True, network_idle=True, solve_cloudflare=True)
    if profile_dir:
        kwargs["user_data_dir"] = profile_dir
    with StealthySession(**kwargs) as session:
        return session.fetch(url)


def _http_fetch(url: str):
    """Fast HTTP fetch with TLS fingerprint impersonation."""
    from scrapling.fetchers import Fetcher
    return Fetcher.get(url, stealthy_headers=True, impersonate="chrome", timeout=15)


# ═══════════════════════════════════════════════════════════════════
# ADAPTERS — Scrapling stealth + DOM
# ═══════════════════════════════════════════════════════════════════

@adapter("weibo", "微博搜索")
def search_weibo(query: str, limit: int) -> list[SearchResult]:
    url = f"https://s.weibo.com/weibo?q={quote_plus(query)}"
    profile = get_profile("weibo.com")
    page = _stealth_fetch(url, profile_dir=profile)

    results = []
    cards = page.css('.card-wrap')
    for card in cards[:limit]:
        author = card.css('.name::text').get("").strip()
        content_parts = card.css('.txt::text').getall()
        content = " ".join(t.strip() for t in content_parts if t.strip())
        mid_link = card.css('.from a::attr(href)').get("")
        if mid_link and not mid_link.startswith("http"):
            mid_link = "https:" + mid_link
        date = card.css('.from a::text').get("").strip()
        likes = card.css('[action-type="feed_list_like"] em::text').get("").strip()
        comments = card.css('[action-type="feed_list_comment"] em::text').get("").strip()
        reposts = card.css('[action-type="feed_list_forward"] em::text').get("").strip()

        if content and len(content) > 5:
            results.append(SearchResult(
                title=content[:80], url=mid_link,
                snippet=truncate_snippet(content), author=author, date=date,
                metrics={k: v for k, v in [("likes", likes), ("comments", comments), ("reposts", reposts)]
                         if v and v not in ("转发", "评论", "赞")},
            ))
    return results


@adapter("zhihu", "知乎搜索")
def search_zhihu(query: str, limit: int) -> list[SearchResult]:
    url = f"https://www.zhihu.com/search?type=content&q={quote_plus(query)}"
    profile = get_profile("zhihu.com")
    page = _stealth_fetch(url, profile_dir=profile)

    results = []
    items = page.css('.SearchResult-Card, .List-item')
    for item in items[:limit]:
        title_parts = item.css('h2 span::text, .ContentItem-title::text').getall()
        title = " ".join(t.strip() for t in title_parts if t.strip())
        link = item.css('h2 a::attr(href), .ContentItem-title a::attr(href)').get("")
        if link and not link.startswith("http"):
            link = "https://www.zhihu.com" + link
        excerpt_parts = item.css('.RichContent-inner span::text').getall()
        excerpt = " ".join(t.strip() for t in excerpt_parts if t.strip())
        author = item.css('.AuthorInfo-content .UserLink-link::text').get("").strip()
        votes = item.css('.VoteButton--up::text').get("").strip()

        if title:
            results.append(SearchResult(
                title=title[:80], url=link,
                snippet=truncate_snippet(excerpt) if excerpt else "",
                author=author,
                metrics={"votes": votes} if votes else {},
            ))
    return results


@adapter("bilibili", "B站搜索")
def search_bilibili(query: str, limit: int) -> list[SearchResult]:
    url = f"https://search.bilibili.com/all?keyword={quote_plus(query)}"
    page = _stealth_fetch(url)

    results = []
    seen_urls = set()
    # B站搜索结果的视频链接是 a[href*="/video/"]，标题在第二个同 href 的 a 标签
    all_links = page.css("a")
    video_links = [a for a in all_links if "/video/" in a.attrib.get("href", "")]

    for a in video_links:
        if len(results) >= limit:
            break
        href = a.attrib.get("href", "")
        if href in seen_urls:
            continue
        text = " ".join(a.css("::text").getall()).strip()
        # Skip "稍后再看" links and very short text
        if not text or "稍后再看" in text or len(text) < 4:
            continue
        seen_urls.add(href)
        link = "https:" + href if not href.startswith("http") else href

        results.append(SearchResult(
            title=text[:80], url=link, snippet="",
        ))
    return results


@adapter("stackoverflow", "Stack Overflow 搜索")
def search_stackoverflow(query: str, limit: int) -> list[SearchResult]:
    # SO has strict anti-automation (captcha). Use Google site: search via Exa/Jina as fallback.
    url = f"https://stackoverflow.com/search?q={quote_plus(query)}"
    try:
        page = _http_fetch(url)
        if "nocaptcha" in str(page) or len(page.css(".s-post-summary")) == 0:
            raise RuntimeError("captcha")
    except Exception:
        # Fallback: search via Exa with site: filter
        sys.stderr.write("[info] stackoverflow: captcha detected, using exa site:stackoverflow.com...\n")
        try:
            exa_results = search_exa(f"site:stackoverflow.com {query}", limit)
            for r in exa_results:
                r.platform = "stackoverflow"
            return exa_results
        except Exception:
            return []

    results = []
    items = page.css('.s-post-summary')
    for item in items[:limit]:
        title = item.css('.s-post-summary--content-title a::text').get("").strip()
        link = item.css('.s-post-summary--content-title a::attr(href)').get("")
        if link and not link.startswith("http"):
            link = "https://stackoverflow.com" + link
        excerpt = " ".join(item.css('.s-post-summary--content-excerpt::text').getall()).strip()
        votes = item.css('.s-post-summary--stats-item-number::text').get("").strip()

        if title:
            results.append(SearchResult(
                title=title[:80], url=link, snippet=truncate_snippet(excerpt),
                metrics={"votes": votes} if votes else {},
            ))
    return results


@adapter("csdn", "CSDN 搜索")
def search_csdn(query: str, limit: int) -> list[SearchResult]:
    url = f"https://so.csdn.net/so/search?q={quote_plus(query)}&t=blog"
    try:
        page = _http_fetch(url)
    except Exception:
        sys.stderr.write("[info] csdn: HTTP failed, switching to stealth...\n")
        page = _stealth_fetch(url)

    results = []
    seen = set()
    # CSDN search is SPA; find blog article links by href pattern
    all_links = page.css("a")
    for a in all_links:
        if len(results) >= limit:
            break
        href = a.attrib.get("href", "")
        if "/article/details/" not in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        text = " ".join(a.css("::text").getall()).strip()
        if not text or len(text) < 5:
            continue
        results.append(SearchResult(
            title=text[:80], url=href, snippet=truncate_snippet(text),
        ))
    return results


@adapter("producthunt", "Product Hunt 搜索")
def search_producthunt(query: str, limit: int) -> list[SearchResult]:
    # PH search is fully SPA-rendered, DOM has no content. Use Exa with site: filter.
    results = search_exa(f"site:producthunt.com {query}", limit)
    for r in results:
        r.platform = "producthunt"
    return results


@adapter("coolapk", "酷安搜索")
def search_coolapk(query: str, limit: int) -> list[SearchResult]:
    # Coolapk search URL returns 404; use Exa site: filter
    results = search_exa(f"site:coolapk.com {query}", limit)
    for r in results:
        r.platform = "coolapk"
    return results


@adapter("heimao", "黑猫投诉搜索")
def search_heimao(query: str, limit: int) -> list[SearchResult]:
    # 黑猫投诉搜索页是 SPA，DOM 解析不到结果。用 Exa site: 降级。
    results = search_exa(f"site:tousu.sina.com.cn {query}", limit)
    for r in results:
        r.platform = "heimao"
    return results


@adapter("smzdm", "什么值得买搜索")
def search_smzdm(query: str, limit: int) -> list[SearchResult]:
    # SMZDM 搜索是 SPA 渲染。用 Exa site: 降级。
    results = search_exa(f"site:smzdm.com {query}", limit)
    for r in results:
        r.platform = "smzdm"
    return results


@adapter("taobao", "淘宝搜索")
def search_taobao(query: str, limit: int) -> list[SearchResult]:
    url = f"https://s.taobao.com/search?q={quote_plus(query)}"
    profile = get_profile("taobao.com")
    page = _stealth_fetch(url, profile_dir=profile)

    results = []
    # Taobao uses dynamic class names; find product links by href pattern
    all_links = page.css("a")
    product_links = [a for a in all_links
                     if "item.taobao" in a.attrib.get("href", "")
                     or "detail.tmall" in a.attrib.get("href", "")]

    for a in product_links[:limit]:
        texts = a.css("::text").getall()
        full_text = " ".join(t.strip() for t in texts if t.strip())
        if len(full_text) < 10:
            continue
        link = a.attrib.get("href", "")
        if link and not link.startswith("http"):
            link = "https:" + link

        # Extract price from text (¥ followed by digits)
        import re
        price_match = re.search(r"¥\s*(\d+(?:\.\d+)?)", full_text)
        price = price_match.group(1) if price_match else ""
        sales_match = re.search(r"(\d+(?:\.\d+)?万?\+?人付款?)", full_text)
        sales = sales_match.group(1) if sales_match else ""

        # Title is usually the first meaningful chunk before ¥
        title_part = full_text.split("¥")[0].strip() if "¥" in full_text else full_text
        title_part = title_part[:80]

        results.append(SearchResult(
            title=title_part, url=link,
            snippet=f"¥{price} {sales}".strip() if price else "",
            metrics={k: v for k, v in [("price", price), ("sales", sales)] if v},
        ))
    return results


# ═══════════════════════════════════════════════════════════════════
# ADAPTERS — Playwright API Intercept
# ═══════════════════════════════════════════════════════════════════

@adapter("xiaohongshu", "小红书搜索")
def search_xiaohongshu(query: str, limit: int) -> list[SearchResult]:
    from playwright.sync_api import sync_playwright

    profile = get_profile("xiaohongshu.com")
    url = f"https://www.xiaohongshu.com/search_result?keyword={quote_plus(query)}&source=web_search_result_note"
    captured = []

    with sync_playwright() as p:
        if profile:
            ctx = p.chromium.launch_persistent_context(profile, headless=True, locale="zh-CN")
        else:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(locale="zh-CN")

        page = ctx.new_page()

        def on_response(response):
            if "/api/sns/web/v1/search/notes" in response.url:
                try:
                    captured.append(response.json())
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(5000)
        ctx.close()

    if not captured:
        return []

    results = []
    items = captured[0].get("data", {}).get("items", [])
    for item in items[:limit]:
        card = item.get("note_card", {})
        title = card.get("display_title", "").strip()
        if not title:
            continue
        user = card.get("user", {}).get("nickname", "")
        likes = card.get("interact_info", {}).get("liked_count", "")
        note_id = item.get("id", "")
        note_type = card.get("type", "")
        note_url = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""

        results.append(SearchResult(
            title=title[:80], url=note_url, snippet=title,
            author=user,
            metrics={k: v for k, v in [("likes", likes), ("type", note_type)] if v},
        ))
    return results


# ═══════════════════════════════════════════════════════════════════
# ADAPTERS — CLI Tools
# ═══════════════════════════════════════════════════════════════════

@adapter("twitter", "Twitter/X 搜索")
def search_twitter(query: str, limit: int) -> list[SearchResult]:
    try:
        out = subprocess.run(
            ["xreach", "search", query, "--json", "-n", str(limit)],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            sys.stderr.write(f"[warn] twitter: xreach failed: {out.stderr[:200]}\n")
            return []
        data = json.loads(out.stdout)
    except FileNotFoundError:
        sys.stderr.write("[warn] twitter: xreach not found in PATH\n")
        return []
    except Exception as e:
        sys.stderr.write(f"[warn] twitter: {e}\n")
        return []

    results = []
    items = data if isinstance(data, list) else data.get("items", data.get("results", data.get("tweets", [])))
    for item in items[:limit]:
        text = item.get("text", item.get("full_text", ""))
        user_obj = item.get("user", {})
        user = user_obj.get("screen_name", user_obj.get("username", user_obj.get("name", "")))
        tweet_id = item.get("id", "")
        rest_id = user_obj.get("restId", "")
        tweet_url = item.get("url", f"https://x.com/{rest_id}/status/{tweet_id}" if tweet_id else "")
        likes = item.get("likeCount", item.get("favorite_count", item.get("likes", "")))
        retweets = item.get("retweetCount", item.get("retweet_count", item.get("retweets", "")))
        views = item.get("viewCount", "")
        date = item.get("createdAt", item.get("created_at", ""))

        if text:
            results.append(SearchResult(
                title=text[:80], url=tweet_url, snippet=truncate_snippet(text),
                author=user, date=date,
                metrics={k: v for k, v in [("likes", str(likes)), ("retweets", str(retweets)), ("views", str(views))]
                         if v and str(v) != "0" and str(v) != ""},
            ))
    return results


@adapter("reddit", "Reddit 搜索")
def search_reddit(query: str, limit: int) -> list[SearchResult]:
    try:
        out = subprocess.run(
            ["curl", "-s",
             f"https://www.reddit.com/search.json?q={quote_plus(query)}&limit={limit}",
             "-H", "User-Agent: agent-reach/1.0"],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(out.stdout)
    except Exception as e:
        sys.stderr.write(f"[warn] reddit: {e}\n")
        return []

    results = []
    for child in data.get("data", {}).get("children", [])[:limit]:
        post = child.get("data", {})
        title = post.get("title", "")
        permalink = post.get("permalink", "")
        url = f"https://www.reddit.com{permalink}" if permalink else ""
        selftext = post.get("selftext", "")
        author = post.get("author", "")
        score = post.get("score", 0)
        comments = post.get("num_comments", 0)
        subreddit = post.get("subreddit", "")

        if title:
            results.append(SearchResult(
                title=title[:80], url=url,
                snippet=truncate_snippet(selftext) if selftext else f"r/{subreddit}",
                author=author,
                metrics={k: v for k, v in [("score", str(score)), ("comments", str(comments)),
                                            ("subreddit", subreddit)] if v and str(v) != "0"},
            ))
    return results


@adapter("exa", "Exa 语义搜索")
def search_exa(query: str, limit: int) -> list[SearchResult]:
    try:
        out = subprocess.run(
            ["mcporter", "call", f'exa.web_search_exa(query: "{query}", numResults: {limit})'],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            sys.stderr.write(f"[warn] exa: mcporter failed: {out.stderr[:200]}\n")
            return []
        raw = out.stdout
    except FileNotFoundError:
        sys.stderr.write("[warn] exa: mcporter not found in PATH\n")
        return []
    except Exception as e:
        sys.stderr.write(f"[warn] exa: {e}\n")
        return []

    # mcporter outputs formatted text, not JSON. Parse "Title: / URL: / Text:" blocks.
    results = []
    current = {}
    for line in raw.split("\n"):
        if line.startswith("Title: "):
            if current.get("title"):
                results.append(SearchResult(
                    title=current["title"][:80],
                    url=current.get("url", ""),
                    snippet=truncate_snippet(current.get("text", "")),
                    author=current.get("author", ""),
                    date=current.get("date", ""),
                ))
                if len(results) >= limit:
                    break
            current = {"title": line[7:].strip()}
        elif line.startswith("URL: "):
            current["url"] = line[5:].strip()
        elif line.startswith("Author: "):
            current["author"] = line[8:].strip()
        elif line.startswith("Published Date: "):
            current["date"] = line[16:].strip()[:10]  # ISO date only
        elif line.startswith("Text: "):
            current["text"] = line[6:].strip()
        elif "text" in current and line.strip():
            current["text"] += " " + line.strip()

    # Don't forget the last item
    if current.get("title") and len(results) < limit:
        results.append(SearchResult(
            title=current["title"][:80],
            url=current.get("url", ""),
            snippet=truncate_snippet(current.get("text", "")),
            author=current.get("author", ""),
            date=current.get("date", ""),
        ))
    return results


@adapter("jina", "Jina 搜索")
def search_jina(query: str, limit: int) -> list[SearchResult]:
    import os
    api_key = os.environ.get("JINA_API_KEY", "")
    headers = ["Accept: application/json", "X-Retain-Images: none"]
    if api_key:
        headers.append(f"Authorization: Bearer {api_key}")

    try:
        cmd = ["curl", "-s", f"https://s.jina.ai/{quote_plus(query)}"]
        for h in headers:
            cmd.extend(["-H", h])
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        data = json.loads(out.stdout)
    except Exception as e:
        sys.stderr.write(f"[warn] jina: {e}\n")
        return []

    if data.get("code") == 401:
        sys.stderr.write("[warn] jina: API key required. Set JINA_API_KEY env var.\n")
        return []

    results = []
    items = data.get("data", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        return []
    for item in items[:limit]:
        title = item.get("title", "")
        url = item.get("url", "")
        desc = item.get("description", item.get("content", ""))
        if title:
            results.append(SearchResult(
                title=title[:80], url=url, snippet=truncate_snippet(desc),
            ))
    return results


@adapter("web", "通用 Web 搜索（支持 --site 限定域名）")
def search_web(query: str, limit: int) -> list[SearchResult]:
    return search_exa(query, limit)


# ═══════════════════════════════════════════════════════════════════
# COMMENTS — Universal comment extraction
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Comment:
    text: str
    author: str = ""
    likes: int = 0
    replies: int = 0
    date: str = ""
    platform: str = ""


# Platform-specific API patterns for comment interception
COMMENT_API_PATTERNS = {
    "douyin.com": "comment/list",
    "bilibili.com": "api.bilibili.com/x/v2/reply",
}

# Platform-specific JSON parsers for intercepted comment APIs
def _parse_douyin_comments(data: dict) -> list[Comment]:
    results = []
    for c in data.get("comments", []):
        results.append(Comment(
            text=c.get("text", ""),
            author=c.get("user", {}).get("nickname", ""),
            likes=c.get("digg_count", 0),
            replies=c.get("reply_comment_total", 0),
        ))
    return results


def _parse_bilibili_comments(data: dict) -> list[Comment]:
    results = []
    for r in data.get("data", {}).get("replies", []):
        results.append(Comment(
            text=r.get("content", {}).get("message", ""),
            author=r.get("member", {}).get("uname", ""),
            likes=r.get("like", 0),
            replies=r.get("rcount", 0),
        ))
    return results


COMMENT_PARSERS = {
    "douyin.com": _parse_douyin_comments,
    "bilibili.com": _parse_bilibili_comments,
}


def fetch_comments(url: str, limit: int = 20) -> list[Comment]:
    """Universal comment fetcher. Tries API interception first, falls back to DOM."""
    from urllib.parse import urlparse
    hostname = urlparse(url).hostname or ""
    # Normalize domain
    parts = hostname.split(".")
    domain = ".".join(parts[-2:]) if len(parts) > 2 else hostname

    profile = get_profile(domain)

    # Check if this domain has a known comment API
    api_pattern = COMMENT_API_PATTERNS.get(domain)

    if api_pattern:
        comments = _fetch_comments_api(url, api_pattern, domain, profile, limit)
        if comments:
            return comments

    # Fallback: DOM-based comment extraction
    return _fetch_comments_dom(url, profile, limit)


def _fetch_comments_api(url: str, api_pattern: str, domain: str, profile: str | None, limit: int) -> list[Comment]:
    """Fetch comments by intercepting JSON API responses."""
    from playwright.sync_api import sync_playwright

    captured = []

    with sync_playwright() as p:
        if profile:
            ctx = p.chromium.launch_persistent_context(profile, headless=True, locale="zh-CN")
        else:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(locale="zh-CN", user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")

        page = ctx.new_page()

        def on_response(response):
            if api_pattern in response.url:
                try:
                    captured.append(response.json())
                except Exception:
                    pass

        page.on("response", on_response)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(10000)
        except Exception:
            pass
        ctx.close()

    parser = COMMENT_PARSERS.get(domain)
    if not parser or not captured:
        return []

    all_comments = []
    for data in captured:
        all_comments.extend(parser(data))
    return all_comments[:limit]


def _fetch_comments_dom(url: str, profile: str | None, limit: int) -> list[Comment]:
    """Fetch comments by parsing DOM with Scrapling stealth + scrolling."""
    from scrapling.engines._browsers._stealth import StealthySession

    def scroll_page(page):
        for _ in range(4):
            page.evaluate("window.scrollBy(0, 800)")
            page.wait_for_timeout(2000)

    kwargs = dict(headless=True, network_idle=True, solve_cloudflare=True)
    if profile:
        kwargs["user_data_dir"] = profile

    with StealthySession(**kwargs) as s:
        page = s.fetch(url, page_action=scroll_page)

    # Strategy 1: Look for comment-specific elements
    comment_selectors = [
        '[class*="comment-content"]', '[class*="comment-text"]',
        '[class*="CommentItem"]', '[class*="comment_item"]', '[class*="comment-item"]',
        '[class*="reply-content"]', '[class*="reply-item"]',
        '.comment-list li', '.reply-list li',
    ]

    comments = []
    seen_texts = set()

    for sel in comment_selectors:
        for item in page.css(sel):
            text = " ".join(item.css("::text").getall()).strip()
            if text and 5 < len(text) < 1000 and text not in seen_texts:
                seen_texts.add(text)
                # Try to extract author from nearby elements
                author = item.css('[class*="name"]::text, [class*="author"]::text, [class*="user"]::text').get("").strip()
                comments.append(Comment(text=text[:300], author=author))
                if len(comments) >= limit:
                    return comments

    # Strategy 2: Heuristic — find clusters of short user-generated text
    if not comments:
        all_texts = page.css("body *::text").getall()
        nav_words = {"首页", "登录", "注册", "关于", "联系", "版权", "备案", "隐私", "京ICP", "沪ICP", "粤ICP",
                     "下载", "广告", "举报", "用户协议", "营业执照", "京公网", "网络文化"}
        for t in all_texts:
            t = t.strip()
            if 10 < len(t) < 500 and not any(w in t for w in nav_words):
                if t not in seen_texts:
                    # Dedupe: skip if this text is a substring of an already-seen text
                    is_dup = any(t in existing for existing in seen_texts)
                    if not is_dup:
                        seen_texts.add(t)
                        comments.append(Comment(text=t[:300]))
                        if len(comments) >= limit:
                            break

    return comments[:limit]


# ═══════════════════════════════════════════════════════════════════
# SCRAPE — Direct URL fetching with content formatting
# ═══════════════════════════════════════════════════════════════════

STEALTH_DOMAINS = {
    "weibo.com", "s.weibo.com", "m.weibo.com",
    "taobao.com", "www.taobao.com", "item.taobao.com", "s.taobao.com",
    "tmall.com", "www.tmall.com", "detail.tmall.com",
    "jd.com", "www.jd.com", "item.jd.com", "search.jd.com",
    "xiaohongshu.com", "www.xiaohongshu.com",
    "douyin.com", "www.douyin.com",
    "bilibili.com", "www.bilibili.com",
    "zhihu.com", "www.zhihu.com",
    "producthunt.com", "www.producthunt.com",
}

API_INTERCEPT_DOMAINS = {"xiaohongshu.com"}


def _auto_detect_mode(url: str) -> str:
    """Detect whether to use http or stealth mode based on domain."""
    from urllib.parse import urlparse
    hostname = urlparse(url).hostname or ""
    if hostname in STEALTH_DOMAINS:
        return "stealth"
    return "http"


def _has_content(page) -> bool:
    """Check if page has meaningful content (not just login/error page)."""
    texts = page.css("body *::text").getall()
    meaningful = [t.strip() for t in texts if t.strip() and len(t.strip()) > 2]
    return len(meaningful) > 5


def _to_markdown(page, css_selector: str = None) -> str:
    """Convert page content to markdown."""
    lines = []

    title = page.css("title::text").get()
    if title:
        lines.append(f"# {title.strip()}")
        lines.append("")

    if css_selector:
        elements = page.css(css_selector)
        if not elements:
            lines.append(f"*No elements found for selector: `{css_selector}`*")
        else:
            for el in elements:
                text = el.css("::text").getall()
                text = " ".join(t.strip() for t in text if t.strip())
                if text:
                    lines.append(f"- {text}")
        return "\n".join(lines)

    for el in page.css("body *"):
        tag = el.tag if hasattr(el, "tag") else ""
        text_parts = el.css("::text").getall()
        text = " ".join(t.strip() for t in text_parts if t.strip())
        if not text:
            continue

        if tag in ("h1",):
            lines.append(f"\n# {text}")
        elif tag in ("h2",):
            lines.append(f"\n## {text}")
        elif tag in ("h3",):
            lines.append(f"\n### {text}")
        elif tag in ("h4", "h5", "h6"):
            lines.append(f"\n#### {text}")
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag == "a":
            href = el.attrib.get("href", "")
            if href and not href.startswith("#") and not href.startswith("javascript"):
                lines.append(f"[{text}]({href})")
        elif tag in ("p", "div", "span", "td", "th"):
            if len(text) > 3 and text not in [l.strip("- #[]()") for l in lines[-5:]]:
                lines.append(text)

    result = []
    for line in lines:
        if not result or line != result[-1]:
            result.append(line)

    return "\n".join(result)


def _to_text(page, css_selector: str = None) -> str:
    """Extract plain text."""
    if css_selector:
        elements = page.css(css_selector)
        texts = []
        for el in elements:
            t = " ".join(el.css("::text").getall()).strip()
            if t:
                texts.append(t)
        return "\n".join(texts)

    texts = page.css("body *::text").getall()
    return "\n".join(t.strip() for t in texts if t.strip())


def _to_html(page, css_selector: str = None) -> str:
    """Return raw HTML."""
    if css_selector:
        elements = page.css(css_selector)
        return "\n".join(str(el) for el in elements)
    return str(page)


def _fetch_api_intercept(url: str, profile_dir: str = None) -> str | None:
    """Fetch SPA content by intercepting API responses (e.g. Xiaohongshu)."""
    from playwright.sync_api import sync_playwright

    captured = []

    domain = domain_from_url(url)
    api_patterns = {
        "xiaohongshu.com": "/api/sns/web/v1/",
    }
    pattern = api_patterns.get(domain)
    if not pattern:
        return None

    with sync_playwright() as p:
        if profile_dir:
            ctx = p.chromium.launch_persistent_context(profile_dir, headless=True, locale="zh-CN")
        else:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(locale="zh-CN", user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

        page = ctx.new_page()

        def on_response(response):
            if pattern in response.url:
                try:
                    captured.append(response.json())
                except Exception:
                    pass

        page.on("response", on_response)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(10000)
        except Exception:
            pass
        ctx.close()

    if not captured:
        return None

    # Format captured API data as readable text
    parts = []
    for data in captured:
        parts.append(json.dumps(data, ensure_ascii=False, indent=2)[:5000])
    return "\n---\n".join(parts)


def scrape_url(url: str, output_format: str = "markdown", css_selector: str = None,
               timeout: int = 30, no_cloudflare: bool = False) -> str:
    """Scrape a URL and return formatted content."""
    mode = _auto_detect_mode(url)
    domain = domain_from_url(url)
    profile_dir = get_profile(domain)

    # Try API interception for SPA sites
    if domain in API_INTERCEPT_DOMAINS and mode == "stealth":
        sys.stderr.write(f"[api-intercept] {domain} uses SPA rendering, intercepting API...\n")
        api_output = _fetch_api_intercept(url, profile_dir=profile_dir)
        if api_output:
            sys.stderr.write(f"[scraped] {url} | mode=api-intercept\n")
            return api_output

    # Standard fetch with auto-escalation
    page = None
    used_mode = mode

    try:
        if mode == "http":
            page = _http_fetch(url)
            if not _has_content(page):
                sys.stderr.write("[auto-escalate] HTTP returned empty content, switching to stealth...\n")
                page = _stealth_fetch(url, profile_dir=profile_dir)
                used_mode = "stealth (auto-escalated)"
        else:
            page = _stealth_fetch(url, profile_dir=profile_dir)
    except Exception as e:
        if mode == "http":
            sys.stderr.write(f"[fallback] HTTP failed ({e}), trying stealth...\n")
            page = _stealth_fetch(url, profile_dir=profile_dir)
            used_mode = "stealth (fallback)"
        else:
            raise

    formatters = {"markdown": _to_markdown, "text": _to_text, "html": _to_html}
    output = formatters[output_format](page, css_selector)

    profile_info = f" | profile={profile_dir}" if profile_dir else ""
    sys.stderr.write(f"[scraped] {url} | mode={used_mode}{profile_info}\n")

    return output

def main():
    parser = argparse.ArgumentParser(description="Unified platform search, scrape, and login management")
    parser.add_argument("--platform", help="Platform ID to search")
    parser.add_argument("--query", help="Search keywords")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--site", help="Limit search to a specific domain (e.g. --site v2ex.com). Auto-sets platform to 'web'")
    parser.add_argument("--comments", metavar="URL", help="Extract comments from a page URL")
    parser.add_argument("--list-platforms", action="store_true", help="List all supported platforms")
    # Scrape mode
    parser.add_argument("--scrape", metavar="URL", help="Scrape a URL and output formatted content")
    parser.add_argument("--format", choices=["markdown", "text", "html"], default="markdown",
                        dest="output_format", help="Output format for --scrape (default: markdown)")
    parser.add_argument("--css", help="CSS selector to extract specific elements (for --scrape)")
    # Login management
    parser.add_argument("--login", metavar="URL", help="Open browser for interactive login")
    parser.add_argument("--check-login", metavar="DOMAIN", help="Check if login session exists")
    args = parser.parse_args()

    if args.list_platforms:
        for pid, desc in sorted(PLATFORM_DESCRIPTIONS.items()):
            req = " [需登录]" if pid in PLATFORMS_REQUIRING_LOGIN else ""
            print(f"  {pid:20s} {desc}{req}")
        return

    # --login mode
    if args.login:
        login_interactive(args.login)
        return

    # --check-login mode
    if args.check_login:
        check_login(args.check_login)
        return

    # --scrape mode
    if args.scrape:
        start = time.time()
        try:
            output = scrape_url(args.scrape, output_format=args.output_format, css_selector=args.css)
        except Exception as e:
            sys.stderr.write(f"[error] scrape: {type(e).__name__}: {e}\n")
            sys.exit(1)
        elapsed = time.time() - start
        sys.stderr.write(f"[scrape] {args.scrape} | {elapsed:.1f}s\n")
        print(output)
        return

    # --comments mode: extract comments from a page URL
    if args.comments:
        start = time.time()
        try:
            comments = fetch_comments(args.comments, args.limit)
        except Exception as e:
            sys.stderr.write(f"[error] comments: {type(e).__name__}: {e}\n")
            sys.exit(1)
        elapsed = time.time() - start
        for c in comments:
            print(json.dumps(asdict(c), ensure_ascii=False))
        sys.stderr.write(f'[comments] {args.comments} | {len(comments)} comments | {elapsed:.1f}s\n')
        return

    # --site shorthand: auto-set platform to web and prepend site: to query
    if args.site:
        args.platform = args.platform or "web"
        args.query = f"site:{args.site} {args.query}" if args.query else None

    if not args.platform or not args.query:
        parser.print_help()
        sys.exit(1)

    if args.platform not in ADAPTERS:
        sys.stderr.write(f"[error] Unknown platform: {args.platform}\n")
        sys.stderr.write("[error] Run --list-platforms to see available options\n")
        sys.exit(1)

    # Check login requirement
    if args.platform in PLATFORMS_REQUIRING_LOGIN:
        domain = PLATFORM_PROFILE_DOMAINS.get(args.platform)
        if domain and not get_profile(domain):
            login_url = LOGIN_URLS.get(args.platform, "")
            sys.stderr.write(f'[warn] {args.platform}: login required but no profile found. '
                             f'Run: search.py --login "{login_url}"\n')
            return

    start = time.time()
    try:
        results = ADAPTERS[args.platform](args.query, args.limit)
    except Exception as e:
        sys.stderr.write(f"[error] {args.platform}: {type(e).__name__}: {e}\n")
        sys.exit(1)

    elapsed = time.time() - start
    output_results(results, args.platform, args.query, elapsed)


if __name__ == "__main__":
    main()
