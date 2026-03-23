# Web Search Agent

Unified web search for AI coding assistants. One script, 16+ platforms, zero-config integration.

## What it does

- **16 platform adapters**: Bilibili, Weibo, Zhihu, Xiaohongshu, Taobao, Reddit, Twitter/X, Stack Overflow, CSDN, Product Hunt, Coolapk, Heimao, SMZDM, Exa, Jina, plus `--site` for any website
- **Direct scraping**: Full page content with anti-detection (`--scrape`)
- **Comment extraction**: Pull comments from any page (`--comments`)
- **Login management**: Persistent browser profiles for auth-required platforms (`--login`)

## Install

Each AI assistant has its own one-liner:

### Claude Code

```bash
npx skills add seangreenidge949-lang/web-search-agent -g
```

Then run setup:

```bash
bash ~/.claude/skills/web-search/scripts/setup.sh
```

### Codex / OpenAI

Clone into your project — `agents/AGENTS.md` is auto-discovered:

```bash
git clone https://github.com/seangreenidge949-lang/web-search-agent.git
bash web-search-agent/skills/web-search/scripts/setup.sh
```

### Cursor

Clone into your project — `.cursor/rules/web-search.md` is auto-discovered:

```bash
git clone https://github.com/seangreenidge949-lang/web-search-agent.git
bash web-search-agent/skills/web-search/scripts/setup.sh
```

### Gemini CLI

Uses `gemini-extension.json` — auto-discovered when the repo is in your project:

```bash
git clone https://github.com/seangreenidge949-lang/web-search-agent.git
bash web-search-agent/skills/web-search/scripts/setup.sh
```

### Any other AI assistant

Copy the content of `skills/web-search/SKILL.md` into your AI assistant's system prompt or rules file.

## Usage

```bash
# Search a platform
python3 search.py --platform bilibili --query "AI编程" --limit 5

# Search any website
python3 search.py --site v2ex.com --query "Claude Code" --limit 5

# Scrape a URL
python3 search.py --scrape "https://example.com" --format markdown

# Extract comments
python3 search.py --comments "https://www.zhihu.com/question/xxx" --limit 10

# Login for auth-required platforms
python3 search.py --login "https://www.zhihu.com/signin"

# Check login status
python3 search.py --check-login zhihu.com

# List all platforms
python3 search.py --list-platforms
```

## Supported Platforms

| Platform | ID | Login Required |
|----------|-----|:-:|
| Bilibili | `bilibili` | |
| Coolapk | `coolapk` | |
| CSDN | `csdn` | |
| Exa | `exa` | |
| Heimao (Black Cat) | `heimao` | |
| Jina | `jina` | |
| Tavily | `tavily` | |
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

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SEARCH_PROFILES_DIR` | Browser profile storage path | `~/.web-search-agent/profiles` |
| `JINA_API_KEY` | API key for Jina search (optional) | - |
| `TAVILY_API_KEY` | API key for Tavily search (optional) | - |

## Dependencies

- Python 3.10+
- [Scrapling](https://github.com/AliBarber/scrapling) — stealth web fetching
- [Playwright](https://playwright.dev/) — browser automation
- [mcporter](https://github.com/nichochar/mcporter) — for Exa search (optional)

## License

MIT
