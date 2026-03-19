---
name: web-search
description: "Unified web search across 16+ platforms (Weibo, Zhihu, Xiaohongshu, Bilibili, Reddit, Twitter, etc.) with scraping, comment extraction, and login management. Use for web research, competitive analysis, user feedback collection, trend monitoring. Triggers on: research, investigate, search, 调研, 搜索, 帮我查, 了解一下, 看看大家怎么说, 用户口碑, 舆情, competitive analysis."
---

# Web Search

Unified web search tool — 16+ platform adapters, direct scraping, comment extraction, login management.

## Setup

Before first use, run the setup script to install Python dependencies:

```bash
bash scripts/setup.sh
```

This creates a `.venv` in the scripts directory and installs Scrapling + Playwright.

## Quick Reference

```bash
# Search a platform
python3 scripts/search.py --platform <id> --query "keywords" --limit 10

# Search any website via Exa
python3 scripts/search.py --site <domain> --query "keywords" --limit 10

# Scrape a URL (full page content)
python3 scripts/search.py --scrape <url> --format markdown|text|html

# Extract comments from a page
python3 scripts/search.py --comments <url> --limit 20

# Login for auth-required platforms
python3 scripts/search.py --login <url>

# Check login status
python3 scripts/search.py --check-login <domain>

# List all platforms
python3 scripts/search.py --list-platforms
```

Output format: JSON Lines — one JSON object per line: `{title, url, snippet, author, date, platform, metrics}`

## Platforms

| ID | Platform | Login |
|----|----------|:-----:|
| `bilibili` | B站 | |
| `coolapk` | 酷安 | |
| `csdn` | CSDN | |
| `exa` | Exa 语义搜索 | |
| `heimao` | 黑猫投诉 | |
| `jina` | Jina | |
| `producthunt` | Product Hunt | |
| `reddit` | Reddit | |
| `smzdm` | 什么值得买 | |
| `stackoverflow` | Stack Overflow | |
| `taobao` | 淘宝 | Yes |
| `twitter` | Twitter/X | |
| `web` | 任意网站 (`--site`) | |
| `weibo` | 微博 | Yes |
| `xiaohongshu` | 小红书 | Yes |
| `zhihu` | 知乎 | Yes |

## Research Workflow

When a user needs web research, follow this flow:

### 1. Parse the request

Extract: topic, research goal, keywords, depth (quick/standard/deep), language.

- **quick** (3-5 searches): simple fact queries
- **standard** (8-12 searches): multi-dimension comparison
- **deep** (15-20 searches): full report

### 2. Plan search strategy

Choose platforms by topic type:

| Topic | P0 (must) | P1 (recommended) | P2 (deep only) |
|-------|-----------|-------------------|----------------|
| Product/Tech | twitter + reddit | zhihu + --site v2ex.com | --site sspai.com |
| Chinese UX | zhihu + xiaohongshu | weibo + --site v2ex.com | --site sspai.com |
| Consumer electronics | coolapk + --site zol.com.cn | smzdm + heimao | taobao + reddit |
| Tech Q&A | stackoverflow + csdn | --site segmentfault.com | --site juejin.cn |
| Startup/Indie | --site indiehackers.com | --site hackernoon.com | exa |
| Video content | bilibili | --site douyin.com | --site kuaishou.com |
| Trending | exa + weibo | --site toutiao.com | --site thepaper.cn |

### 3. Execute searches

Run search.py for each query. For high-value results:
- Use `--comments` to get comment sections
- Use `--scrape` to fetch full article text

### 4. Summarize results

- Statistics: X platforms, Y results, sources covered
- Key findings: grouped by theme, highlight high-engagement content
- Gaps: what couldn't be found and why

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SEARCH_PROFILES_DIR` | Browser profile storage | `~/.web-search-agent/profiles` |
| `JINA_API_KEY` | Jina search API key (optional) | - |
