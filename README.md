# Web Search Agent

Unified web search tool for AI coding assistants. One script, 16+ platforms, works with any AI assistant.

## What it does

- **16 platform adapters**: Bilibili, Weibo, Zhihu, Xiaohongshu, Taobao, Reddit, Twitter/X, Stack Overflow, CSDN, Product Hunt, Coolapk, Heimao, SMZDM, Exa, Jina, and a universal `--site` search for any website
- **Direct scraping**: Fetch full page content with anti-detection (`--scrape`)
- **Comment extraction**: Pull comments from any page (`--comments`)
- **Login management**: Persistent browser profiles for auth-required platforms (`--login`)
- **AI-ready rules**: Drop-in prompt files for Claude Code, Cursor, Windsurf, or any AI assistant

## Quick Start

```bash
git clone https://github.com/siyucheng/web-search-agent.git
cd web-search-agent
./setup.sh
```

Test it:

```bash
.venv/bin/python3 search.py --list-platforms
.venv/bin/python3 search.py --platform bilibili --query "AI编程" --limit 3
.venv/bin/python3 search.py --site v2ex.com --query "Claude Code" --limit 5
.venv/bin/python3 search.py --scrape "https://example.com" --format markdown
```

## Integrate with your AI assistant

### Claude Code

Copy rules into your Claude Code config:

```bash
cp rules/web-collector.md ~/.claude/agents/web-collector.md
cp rules/web-research.md ~/.claude/skills/web-research/SKILL.md
```

### Cursor

Append the content of `rules/web-collector.md` and `rules/web-research.md` to your `.cursorrules` file.

### Windsurf

Append the content of `rules/web-collector.md` and `rules/web-research.md` to your `.windsurfrules` file.

### Any AI assistant

Copy the content of files in `rules/` into your AI assistant's system prompt or rules file.

## Supported Platforms

| Platform | ID | Login Required |
|----------|-----|:-:|
| Bilibili | `bilibili` | |
| Coolapk | `coolapk` | |
| CSDN | `csdn` | |
| Exa | `exa` | |
| Heimao (Black Cat) | `heimao` | |
| Jina | `jina` | |
| Product Hunt | `producthunt` | |
| Reddit | `reddit` | |
| SMZDM | `smzdm` | |
| Stack Overflow | `stackoverflow` | |
| Taobao | `taobao` | Yes |
| Twitter/X | `twitter` | |
| Any website | `web` + `--site` | |
| Weibo | `weibo` | Yes |
| Xiaohongshu | `xiaohongshu` | Yes |
| Zhihu | `zhihu` | Yes |

## Login for auth-required platforms

```bash
# Open browser for interactive login (QR code, password, etc.)
.venv/bin/python3 search.py --login "https://www.zhihu.com/signin"

# Check if login session is still valid
.venv/bin/python3 search.py --check-login zhihu.com
```

Login profiles are saved to `~/.web-search-agent/profiles/` by default. Override with:

```bash
export SEARCH_PROFILES_DIR=/path/to/your/profiles
```

## All commands

```bash
# Search a platform
search.py --platform <id> --query "keywords" [--limit N]

# Search any website via Exa
search.py --site <domain> --query "keywords" [--limit N]

# Scrape a URL
search.py --scrape <url> [--format markdown|text|html] [--css <selector>]

# Extract comments from a page
search.py --comments <url> [--limit N]

# Login management
search.py --login <url>
search.py --check-login <domain>

# List platforms
search.py --list-platforms
```

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SEARCH_PROFILES_DIR` | Browser profile storage path | `~/.web-search-agent/profiles` |
| `JINA_API_KEY` | API key for Jina search (optional) | - |

## Dependencies

- Python 3.10+
- [Scrapling](https://github.com/AliBarber/scrapling) — stealth web fetching
- [Playwright](https://playwright.dev/) — browser automation
- Exa search uses [mcporter](https://github.com/nichochar/mcporter) CLI (optional, for `exa` and `web` platforms)

## License

MIT
