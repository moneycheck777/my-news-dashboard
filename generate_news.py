import feedparser
import json
import re
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

FEEDS = {
    "IT/테크": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Wired", "https://www.wired.com/feed/rss"),
    ],
    "경제/주식": [
        ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
        ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss"),
        ("CNBC Economy", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ],
    "국제 뉴스": [
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
        ("AP News", "https://rsshub.app/apnews/world-news"),
    ],
    "AI": [
        ("MIT Tech Review AI", "https://www.technologyreview.com/feed/"),
        ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
        ("Hacker News AI", "https://hnrss.org/newest?q=AI&points=50"),
    ],
    "스포츠": [
        ("ESPN", "https://www.espn.com/espn/rss/news"),
        ("BBC Sport", "http://feeds.bbci.co.uk/sport/rss.xml"),
        ("Sky Sports", "https://www.skysports.com/rss/12040"),
    ],
}

def clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]

def fetch_news(category, sources, count=9):
    articles = []
    for source_name, url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
                title = clean(entry.get("title", "제목 없음"))
                summary = clean(entry.get("summary", entry.get("description", "")))
                link = entry.get("link", "#")
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    dt = datetime(*published[:6], tzinfo=timezone.utc).astimezone(KST)
                    date_str = dt.strftime("%Y.%m.%d %H:%M")
                else:
                    date_str = "날짜 미상"
                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "date": date_str,
                    "source": source_name
                })
        except Exception as e:
            print(f"[오류] {source_name}: {e}")
            continue
    return articles[:count]

def generate_html(all_news, updated_time):
    tabs_html = ""
    contents_html = ""
    categories = list(all_news.keys())

    for i, cat in enumerate(categories):
        active = "active" if i == 0 else ""
        tabs_html += f'<button class="tab-btn {active}" onclick="switchTab(\'{cat}\')" id="btn-{cat}">{cat}</button>\n'

    for i, (cat, articles) in enumerate(all_news.items()):
        display = "block" if i == 0 else "none"
        cards_html = ""

        if not articles:
            cards_html = '<div class="no-news">📭 현재 뉴스를 불러올 수 없습니다.</div>'
        else:
            for a in articles:
                cards_html += f'''
        <div class="card">
          <div class="card-source">{a["source"]}</div>
          <div class="card-title"><a href="{a["link"]}" target="_blank">{a["title"]}</a></div>
          <div class="card-summary">{a["summary"]}</div>
          <div class="card-date">🕐 {a["date"]}</div>
        </div>'''

        contents_html += f'''
    <div class="tab-content" id="tab-{cat}" style="display:{display}">
      <div class="grid">{cards_html}
      </div>
    </div>'''

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>My News Dashboard</title>
<style>
  :root {{
    --bg: #0f1117;
    --card-bg: #1a1d27;
    --border: #2e3150;
    --text: #e0e0e0;
    --sub: #8b8fa8;
    --accent: #4f8ef7;
    --tag-bg: #252840;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; padding: 24px; }}
  header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 8px; }}
  header h1 {{ font-size: 1.6rem; color: #fff; }}
  .updated {{ font-size: 0.8rem; color: var(--sub); }}
  .tabs {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 24px; }}
  .tab-btn {{
    padding: 8px 20px; border: 1px solid var(--border);
    border-radius: 999px; background: var(--card-bg);
    color: var(--sub); cursor: pointer; font-size: 0.9rem;
    transition: all 0.2s;
  }}
  .tab-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .tab-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px;
    display: flex; flex-direction: column; gap: 10px;
    transition: border-color 0.2s;
  }}
  .card:hover {{ border-color: var(--accent); }}
  .card-source {{
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em;
    color: var(--accent); background: var(--tag-bg);
    display: inline-block; padding: 3px 8px; border-radius: 4px;
    width: fit-content;
  }}
  .card-title {{ font-size: 0.95rem; font-weight: 600; line-height: 1.4; }}
  .card-title a {{ color: var(--text); text-decoration: none; }}
  .card-title a:hover {{ color: var(--accent); }}
  .card-summary {{ font-size: 0.82rem; color: var(--sub); line-height: 1.5; flex: 1; }}
  .card-date {{ font-size: 0.75rem; color: var(--sub); margin-top: auto; }}
  .no-news {{ color: var(--sub); padding: 40px; text-align: center; font-size: 1rem; }}
</style>
</head>
<body>
<header>
  <h1>📰 My News Dashboard</h1>
  <span class="updated">마지막 업데이트: {updated_time}</span>
</header>
<div class="tabs">
{tabs_html}</div>
{contents_html}
<script>
function switchTab(cat) {{
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + cat).style.display = 'block';
  document.getElementById('btn-' + cat).classList.add('active');
}}
</script>
</body>
</html>'''

if __name__ == "__main__":
    now_kst = datetime.now(KST).strftime("%Y년 %m월 %d일 %H:%M KST")
    all_news = {}
    for cat, sources in FEEDS.items():
        print(f"[수집 중] {cat}...")
        all_news[cat] = fetch_news(cat, sources)
        print(f"  → {len(all_news[cat])}개 수집 완료")

    html = generate_html(all_news, now_kst)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ index.html 생성 완료!")
