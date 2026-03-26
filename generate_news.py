import feedparser
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

FEEDS = {
    "💻 IT/테크": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.theverge.com/rss/index.xml",
    ],
    "📈 경제/주식": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.reuters.com/reuters/businessNews",
    ],
    "🌍 국제 뉴스": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.reuters.com/Reuters/worldNews",
    ],
    "🤖 AI": [
        "https://hnrss.org/frontpage?q=AI+LLM+GPT",
        "https://www.technologyreview.com/feed/",
    ],
    "⚽ 스포츠": [
        "https://feeds.bbci.co.uk/sport/rss.xml",
        "https://www.espn.com/espn/rss/news",
    ],
}

def fetch_news(urls, limit=20):
    items = []
    seen = set()
    for url in urls:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get("title", url)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link  = entry.get("link", "#")
                pub   = entry.get("published", "")
                summary = entry.get("summary", "")[:120]
                # HTML 태그 간단 제거
                import re
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if title and title not in seen:
                    seen.add(title)
                    items.append({
                        "title": title,
                        "link": link,
                        "pub": pub,
                        "summary": summary,
                        "source": source
                    })
        except Exception as e:
            print(f"Feed error ({url}): {e}")
    return items[:limit]

def card(item):
    return f"""
        <a class="card" href="{item['link']}" target="_blank" rel="noopener">
          <div class="card-source">{item['source']}</div>
          <div class="card-title">{item['title']}</div>
          <div class="card-summary">{item['summary']}</div>
          <div class="card-date">{item['pub'][:16] if item['pub'] else ''}</div>
        </a>"""

tabs_html = ""
panels_html = ""

for i, (cat, urls) in enumerate(FEEDS.items()):
    active = "active" if i == 0 else ""
    tab_id = f"tab{i}"
    tabs_html += f'<button class="tab {active}" onclick="switchTab(this,\'{tab_id}\')">{cat}</button>\n'
    news_items = fetch_news(urls)
    if news_items:
        cards = "".join(card(n) for n in news_items)
    else:
        cards = '<p class="empty">뉴스를 불러오지 못했어요. 잠시 후 다시 시도합니다.</p>'
    panels_html += f'<div class="panel {active}" id="{tab_id}">\n<div class="grid">{cards}</div>\n</div>\n'

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>My News Dashboard</title>
<style>
  :root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2e3147;
    --accent: #4f8ef7;
    --text: #e8eaf6;
    --muted: #8b90a7;
    --source: #4f8ef7;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; min-height: 100vh; }}
  header {{ padding: 24px 20px 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; border-bottom: 1px solid var(--border); }}
  header h1 {{ font-size: 1.5rem; font-weight: 700; }}
  .updated {{ font-size: 0.8rem; color: var(--muted); }}
  .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 16px 20px; }}
  .tab {{
    background: var(--surface); color: var(--muted);
    border: 1px solid var(--border); border-radius: 20px;
    padding: 8px 18px; cursor: pointer; font-size: 0.9rem;
    transition: all 0.2s;
  }}
  .tab.active, .tab:hover {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  .panel {{ display: none; padding: 0 20px 40px; }}
  .panel.active {{ display: block; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    margin-top: 16px;
  }}
  .card {{
    display: flex; flex-direction: column; gap: 8px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px;
    text-decoration: none; color: var(--text);
    transition: border-color 0.2s, transform 0.2s;
  }}
  .card:hover {{ border-color: var(--accent); transform: translateY(-2px); }}
  .card-source {{ font-size: 0.75rem; color: var(--source); font-weight: 600; text-transform: uppercase; }}
  .card-title {{ font-size: 0.95rem; font-weight: 600; line-height: 1.4; }}
  .card-summary {{ font-size: 0.82rem; color: var(--muted); line-height: 1.5; flex: 1; }}
  .card-date {{ font-size: 0.75rem; color: var(--muted); margin-top: auto; }}
  .empty {{ color: var(--muted); padding: 40px 0; text-align: center; }}
  @media (max-width: 600px) {{
    .grid {{ grid-template-columns: 1fr; }}
    header h1 {{ font-size: 1.2rem; }}
  }}
</style>
</head>
<body>
<header>
  <h1>📰 My News Dashboard</h1>
  <span class="updated">마지막 업데이트: {now}</span>
</header>
<div class="tabs">
{tabs_html}
</div>
{panels_html}
<script>
  function switchTab(btn, id) {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(id).classList.add('active');
  }}
</script>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ index.html 생성 완료 ({now})")
