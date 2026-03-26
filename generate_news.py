import feedparser
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))

FEEDS = {
    "💻 IT/테크": [
        "https://feeds.feedburner.com/TechCrunch/",
        "https://www.theverge.com/rss/index.xml",
    ],
    "📈 경제/주식": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://rss.reuters.com/reuters/businessNews",
    ],
    "🌍 국제 뉴스": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.reuters.com/reuters/worldNews",
    ],
    "🤖 AI": [
        "https://venturebeat.com/category/ai/feed/",
        "https://www.artificialintelligence-news.com/feed/",
    ],
    "⚽ 스포츠": [
        "https://feeds.bbci.co.uk/sport/rss.xml",
        "https://rss.reuters.com/reuters/sportsNews",
    ],
}

MAX_PER_FEED = 8

def fetch_all():
    result = {}
    for category, urls in FEEDS.items():
        articles = []
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:MAX_PER_FEED]:
                    title   = entry.get("title", "").strip()
                    link    = entry.get("link", "#")
                    pub     = entry.get("published", "")
                    summary = entry.get("summary", "")[:200]
                    if title:
                        articles.append({
                            "title":   title,
                            "link":    link,
                            "pub":     pub,
                            "summary": summary,
                            "source":  feed.feed.get("title", url),
                        })
            except Exception as e:
                print(f"[WARN] {url}: {e}")
        seen, unique = set(), []
        for a in articles:
            if a["title"] not in seen:
                seen.add(a["title"])
                unique.append(a)
        result[category] = unique[:20]
    return result

def build_html(data: dict) -> str:
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    tabs_html = ""
    for i, cat in enumerate(data.keys()):
        active = "active" if i == 0 else ""
        tabs_html += f'<button class="tab-btn {active}" onclick="showTab(this,\'tab{i}\')">{cat}</button>\n'

    sections_html = ""
    for i, (cat, articles) in enumerate(data.items()):
        display = "block" if i == 0 else "none"
        cards = ""
        if not articles:
            cards = "<p class='empty'>뉴스를 불러오지 못했습니다.</p>"
        for art in articles:
            summary_block = f"<p class='summary'>{art['summary']}…</p>" if art["summary"] else ""
            cards += f"""
            <a class="card" href="{art['link']}" target="_blank" rel="noopener">
              <div class="card-source">{art['source']}</div>
              <div class="card-title">{art['title']}</div>
              {summary_block}
              <div class="card-pub">{art['pub']}</div>
            </a>"""
        sections_html += f"""
        <div id="tab{i}" class="tab-section" style="display:{display}">
          <div class="grid">{cards}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>📰 My News Dashboard</title>
  <style>
    :root {{
      --bg:#0f1117; --surface:#1a1d27; --card:#22263a;
      --accent:#4f8ef7; --text:#e8eaf0; --sub:#8b90a4; --border:#2e3348;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ background:var(--bg); color:var(--text);
           font-family:"Pretendard","Noto Sans KR",sans-serif; min-height:100vh; }}
    header {{ background:var(--surface); border-bottom:1px solid var(--border);
              padding:20px 32px; display:flex; justify-content:space-between; align-items:center; }}
    header h1 {{ font-size:1.4rem; font-weight:700; }}
    .update-time {{ font-size:.8rem; color:var(--sub); }}
    .tabs {{ display:flex; gap:8px; padding:20px 32px 0; flex-wrap:wrap; }}
    .tab-btn {{ background:var(--surface); border:1px solid var(--border); color:var(--sub);
                border-radius:999px; padding:8px 18px; font-size:.9rem; cursor:pointer; transition:all .2s; }}
    .tab-btn:hover {{ border-color:var(--accent); color:var(--accent); }}
    .tab-btn.active {{ background:var(--accent); border-color:var(--accent); color:#fff; font-weight:600; }}
    .tab-section {{ padding:24px 32px 48px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; }}
    .card {{ background:var(--card); border:1px solid var(--border); border-radius:12px;
             padding:18px; text-decoration:none; color:var(--text);
             display:flex; flex-direction:column; gap:8px; transition:transform .15s,border-color .15s; }}
    .card:hover {{ transform:translateY(-3px); border-color:var(--accent); }}
    .card-source {{ font-size:.72rem; color:var(--accent); font-weight:600; text-transform:uppercase; }}
    .card-title {{ font-size:.97rem; font-weight:600; line-height:1.45; }}
    .summary {{ font-size:.82rem; color:var(--sub); line-height:1.5; }}
    .card-pub {{ font-size:.72rem; color:var(--sub); margin-top:auto; }}
    .empty {{ color:var(--sub); padding:40px 0; text-align:center; }}
    @media(max-width:600px) {{
      header {{ flex-direction:column; gap:6px; padding:16px; }}
      .tabs {{ padding:14px 16px 0; }}
      .tab-section {{ padding:16px 16px 40px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>📰 My News Dashboard</h1>
    <span class="update-time">🕐 마지막 업데이트: {now_kst}</span>
  </header>
  <nav class="tabs">{tabs_html}</nav>
  {sections_html}
  <script>
    function showTab(btn, id) {{
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-section").forEach(s => s.style.display = "none");
      btn.classList.add("active");
      document.getElementById(id).style.display = "block";
    }}
  </script>
</body>
</html>"""

if __name__ == "__main__":
    print("📡 뉴스 수집 중...")
    data = fetch_all()
    html = build_html(data)
    Path("index.html").write_text(html, encoding="utf-8")
    total = sum(len(v) for v in data.values())
    print(f"✅ 완료! 총 {total}개 기사 → index.html 생성")
