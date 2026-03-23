# Web Search Tool

This project includes a unified web search tool at `skills/web-search/scripts/search.py` that supports 16+ platforms.

## Setup

```bash
bash skills/web-search/scripts/setup.sh
```

## Usage

```bash
# Search a platform
python3 skills/web-search/scripts/search.py --platform <id> --query "keywords" --limit 10

# Search any website
python3 skills/web-search/scripts/search.py --site <domain> --query "keywords" --limit 10

# Scrape a URL
python3 skills/web-search/scripts/search.py --scrape <url> --format text

# Extract comments
python3 skills/web-search/scripts/search.py --comments <url> --limit 20

# Login for auth-required platforms
python3 skills/web-search/scripts/search.py --login <url>
```

## Platforms

bilibili, coolapk, csdn, exa, heimao, jina, tavily, producthunt, reddit, smzdm, stackoverflow, taobao[login], twitter, web(any site), weibo[login], xiaohongshu[login], zhihu[login]

## Research Flow

1. Parse user's research need → extract topic, goal, depth (quick/standard/deep)
2. Choose platforms by topic type (see SKILL.md for platform selection matrix)
3. Execute searches with search.py, use `--comments` and `--scrape` for deeper content
4. Summarize findings with source attribution
