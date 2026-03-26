import feedparser
import re
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

FEEDS = {
    "IT/테크": [
        ("TechCrunch",       "https://techcrunch.com/feed/"),
        ("The Verge",        "https://www.theverge.com/rss/index.xml"),
        ("Wired",            "https://www.wired.com/feed/rss"),
        ("Ars Technica",     "https://feeds.arstechnica.com/arstechnica/index"),
        ("Engadget",         "https://www.engadget.com/rss.xml"),
        ("ZDNet",            "https://www.zdnet.com/news/rss.xml"),
    ],
    "경제/주식": [
        ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
        ("CNBC Economy",     "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
        ("CNBC Finance",     "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
        ("MarketWatch",      "https://feeds.marketwatch.com/marketwatch/topstories/"),
        ("Investing.com",    "https://www.investing.com/rss/news.rss"),
        ("Yahoo Finance",    "https://finance.yahoo.com/news/rssindex"),
    ],
    "국제 뉴스": [
        ("BBC World",        "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Reuters World",    "https://feeds.reuters.com/Reuters/worldNews"),
        ("AP News",          "https://rsshub.app/apnews/world-news"),
        ("Al Jazeera",       "https://www.aljazeera.com/xml/rss/all.xml"),
        ("Guardian World",   "https://www.theguardian.com/world/rss"),
        ("DW News",          "https://rss.dw.com/xml/rss-en-all"),
    ],
    "AI": [
        ("MIT Tech Review",  "https://www.technologyreview.com/feed/"),
        ("VentureBeat AI",   "https://venturebeat.com/category/ai/feed/"),
        ("Hacker News AI",   "https://hnrss.org/newest?q=AI&points=50"),
        ("The Verge AI",     "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
        ("Wired AI",         "https://www.wired.com/feed/tag/ai/latest/rss"),
        ("TechCrunch AI",    "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ],
    "스포츠": [
        ("ESPN",             "https://www.espn.com/espn/rss/news"),
        ("BBC Sport",        "http://feeds.bbci.co.uk/sport/rss.xml"),
        ("Sky Sports",       "https://www.skysports.com/rss/12040"),
        ("ESPN NFL",         "https://www.espn.com/espn/rss/nfl/news"),
        ("ESPN NBA",         "https://www.espn.com/espn/rss/nba/news"),
        ("CBS Sports",       "https://www.cbssports.com/rss/headlines/"),
    ],
}

def clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:220]

def fetch_news(category, sources, count=20):
    articles = []
    for source_name, url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = clean(entry.get("title", "제목 없음"))
                summary = clean(entry.get("summary", entry.get("description", "")))
                link = entry.get("link", "#")
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    dt = datetime(*published[:6], tzinfo=timezone.utc).astimezone(KST)
                    date_str = dt.strftime("%Y.%m.%d %H:%M")
                else:
                    date_str = "날짜 미상"
                # 기사 고유 ID = 링크 기반 해시
                article_id = str(abs(hash(link)) % (10**10))
                articles.append({
                    "id":      article_id,
                    "title":   title,
                    "summary": summary,
                    "link":    link,
                    "date":    date_str,
                    "source":  source_name
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
        # 카테고리 버튼에 뱃지 span 포함
        tabs_html += (
            f'<button class="tab-btn {active}" onclick="switchTab(\'{cat}\')" id="btn-{cat}">'
            f'{cat}<span class="new-badge" id="badge-{cat}"></span>'
            f'</button>\n'
        )

    for i, (cat, articles) in enumerate(all_news.items()):
        display = "block" if i == 0 else "none"
        cards_html = ""

        if not articles:
            cards_html = '<div class="no-news">📭 현재 뉴스를 불러올 수 없습니다.</div>'
        else:
            for a in articles:
                cards_html += f'''
        <div class="card" id="card-{a["id"]}" data-id="{a["id"]}" data-cat="{cat}" onclick="markRead(this)">
          <div class="card-top">
            <div class="card-source">{a["source"]}</div>
            <span class="unread-dot" id="dot-{a["id"]}">NEW</span>
          </div>
          <div class="card-title"><a href="{a["link"]}" target="_blank" onclick="event.stopPropagation()">{a["title"]}</a></div>
          <div class="card-summary">{a["summary"]}</div>
          <div class="card-date">🕐 {a["date"]}</div>
        </div>'''

        contents_html += f'''
    <div class="tab-content" id="tab-{cat}" style="display:{display}">
      <div class="tab-toolbar">
        <span class="unread-count" id="count-{cat}"></span>
        <button class="mark-all-btn" onclick="markAllRead('{cat}')">✅ 전체 읽음 처리</button>
      </div>
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
    --card-read: #13151e;
    --border: #2e3150;
    --border-read: #1e2035;
    --text: #e0e0e0;
    --text-read: #4a4f6a;
    --sub: #8b8fa8;
    --accent: #4f8ef7;
    --tag-bg: #252840;
    --new-color: #ff5c5c;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; padding: 24px 24px 60px; min-height: 100vh; }}

  /* ── 헤더 ── */
  header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 8px; }}
  header h1 {{ font-size: 1.6rem; color: #fff; }}
  .header-right {{ display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }}
  .updated {{ font-size: 0.8rem; color: var(--sub); }}
  .refresh-badge {{ font-size: 0.72rem; color: #4caf50; background: #1b2e1b; padding: 3px 10px; border-radius: 20px; border: 1px solid #2e5c2e; }}

  /* ── 탭 버튼 ── */
  .tabs {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }}
  .tab-btn {{
    position: relative;
    padding: 8px 22px; border: 1px solid var(--border);
    border-radius: 999px; background: var(--card-bg);
    color: var(--sub); cursor: pointer; font-size: 0.9rem;
    transition: all 0.2s;
  }}
  .tab-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .tab-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  /* 탭 위 NEW 개수 뱃지 */
  .new-badge {{
    position: absolute; top: -7px; right: -7px;
    background: var(--new-color); color: #fff;
    font-size: 0.62rem; font-weight: 700;
    padding: 2px 6px; border-radius: 999px;
    display: none;
  }}

  /* ── 툴바 ── */
  .tab-toolbar {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 14px;
  }}
  .unread-count {{ font-size: 0.82rem; color: var(--sub); }}
  .unread-count span {{ color: var(--new-color); font-weight: 700; }}
  .mark-all-btn {{
    font-size: 0.78rem; padding: 5px 14px;
    border: 1px solid var(--border); border-radius: 8px;
    background: var(--card-bg); color: var(--sub);
    cursor: pointer; transition: all 0.2s;
  }}
  .mark-all-btn:hover {{ border-color: #4caf50; color: #4caf50; }}

  /* ── 카드 그리드 ── */
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }}
  .card {{
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 12px; padding: 18px;
    display: flex; flex-direction: column; gap: 10px;
    transition: border-color 0.2s, transform 0.15s, opacity 0.3s;
    cursor: pointer;
  }}
  .card:hover {{ border-color: var(--accent); transform: translateY(-2px); }}
  /* 읽은 카드 스타일 */
  .card.read {{
    background: var(--card-read);
    border-color: var(--border-read);
    opacity: 0.55;
  }}
  .card.read .card-title a {{ color: var(--text-read); }}
  .card.read:hover {{ border-color: var(--border); transform: none; opacity: 0.65; }}

  .card-top {{ display: flex; justify-content: space-between; align-items: center; }}
  .card-source {{
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em;
    color: var(--accent); background: var(--tag-bg);
    padding: 3px 8px; border-radius: 4px;
  }}
  /* NEW 뱃지 */
  .unread-dot {{
    font-size: 0.65rem; font-weight: 800;
    background: var(--new-color); color: #fff;
    padding: 2px 7px; border-radius: 999px;
    letter-spacing: 0.04em;
  }}
  .card.read .unread-dot {{ display: none; }}

  .card-title {{ font-size: 0.95rem; font-weight: 600; line-height: 1.4; }}
  .card-title a {{ color: var(--text); text-decoration: none; }}
  .card-title a:hover {{ color: var(--accent); }}
  .card-summary {{ font-size: 0.82rem; color: var(--sub); line-height: 1.55; flex: 1; }}
  .card-date {{ font-size: 0.75rem; color: var(--sub); margin-top: auto; padding-top: 6px; border-top: 1px solid var(--border); }}
  .no-news {{ color: var(--sub); padding: 60px; text-align: center; font-size: 1rem; }}

  /* ── 하단 카운트다운 바 ── */
  #countdown-bar {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: #12151f; border-top: 1px solid var(--border);
    padding: 8px 24px; display: flex; align-items: center; gap: 12px;
    font-size: 0.78rem; color: var(--sub); z-index: 100;
  }}
  #progress-track {{ flex: 1; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }}
  #progress-fill {{ height: 100%; background: var(--accent); width: 0%; transition: width 1s linear; border-radius: 2px; }}
</style>
</head>
<body>

<header>
  <h1>📰 My News Dashboard</h1>
  <div class="header-right">
    <span class="updated">마지막 업데이트: {updated_time}</span>
    <span class="refresh-badge">🔄 매시간 자동 갱신</span>
  </div>
</header>

<div class="tabs">
{tabs_html}</div>

{contents_html}

<div id="countdown-bar">
  <span>⏱ 다음 갱신까지</span>
  <div id="progress-track"><div id="progress-fill"></div></div>
  <span id="countdown-text">60:00</span>
</div>

<script>
// ── 탭 전환 ──
function switchTab(cat) {{
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + cat).style.display = 'block';
  document.getElementById('btn-' + cat).classList.add('active');
}}

// ── localStorage 키 ──
const STORAGE_KEY = 'news_read_ids';

function getReadIds() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')); }}
  catch {{ return new Set(); }}
}}

function saveReadIds(set) {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
}}

// ── 단일 카드 읽음 처리 ──
function markRead(cardEl) {{
  const id = cardEl.dataset.id;
  const readIds = getReadIds();
  readIds.add(id);
  saveReadIds(readIds);
  cardEl.classList.add('read');
  updateCounts();
}}

// ── 전체 읽음 처리 ──
function markAllRead(cat) {{
  const readIds = getReadIds();
  document.querySelectorAll(`[data-cat="${{cat}}"]`).forEach(card => {{
    readIds.add(card.dataset.id);
    card.classList.add('read');
  }});
  saveReadIds(readIds);
  updateCounts();
}}

// ── 읽음 수 / 탭 뱃지 업데이트 ──
function updateCounts() {{
  const readIds = getReadIds();
  document.querySelectorAll('.tab-content').forEach(tabEl => {{
    const cat = tabEl.id.replace('tab-', '');
    const cards = tabEl.querySelectorAll('.card');
    const unread = [...cards].filter(c => !readIds.has(c.dataset.id)).length;
    const total  = cards.length;

    // 툴바 텍스트
    const countEl = document.getElementById('count-' + cat);
    if (countEl) {{
      countEl.innerHTML = `안 읽은 기사 <span>${{unread}}</span> / 전체 ${{total}}`;
    }}

    // 탭 버튼 뱃지
    const badge = document.getElementById('badge-' + cat);
    if (badge) {{
      if (unread > 0) {{
        badge.textContent = unread;
        badge.style.display = 'inline-block';
      }} else {{
        badge.style.display = 'none';
      }}
    }}
  }});
}}

// ── 페이지 로드 시 읽음 상태 복원 ──
function restoreReadState() {{
  const readIds = getReadIds();
  readIds.forEach(id => {{
    const card = document.getElementById('card-' + id);
    if (card) card.classList.add('read');
  }});
  updateCounts();
}}

// ── 카운트다운 바 (1시간) ──
(function() {{
  const TOTAL = 3600;
  let remaining = TOTAL;
  function fmt(sec) {{
    return String(Math.floor(sec/60)).padStart(2,'0') + ':' + String(sec%60).padStart(2,'0');
  }}
  function tick() {{
    remaining--;
    document.getElementById('countdown-text').textContent = fmt(remaining);
    document.getElementById('progress-fill').style.width = ((TOTAL - remaining) / TOTAL * 100).toFixed(2) + '%';
    if (remaining <= 0) location.reload();
  }}
  document.getElementById('countdown-text').textContent = fmt(remaining);
  setInterval(tick, 1000);
}})();

// ── 초기 실행 ──
restoreReadState();
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
