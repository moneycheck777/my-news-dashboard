import feedparser
import re
import json
import os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
ARCHIVE_FILE = "news_archive.json"
KEEP_HOURS = 168  # 7일치 보관

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
                title   = clean(entry.get("title", "제목 없음"))
                summary = clean(entry.get("summary", entry.get("description", "")))
                link    = entry.get("link", "#")
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    dt = datetime(*published[:6], tzinfo=timezone.utc).astimezone(KST)
                    date_str = dt.strftime("%Y.%m.%d %H:%M")
                else:
                    date_str = "날짜 미상"
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

# ── 아카이브 로드 ──
def load_archive():
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

# ── 아카이브 저장 (7일 초과분 자동 삭제) ──
def save_archive(archive):
    cutoff = datetime.now(KST) - timedelta(hours=KEEP_HOURS)
    cleaned = {}
    for cat, batches in archive.items():
        kept = []
        for batch in batches:
            try:
                batch_time = datetime.strptime(batch["collected_at"], "%Y-%m-%d %H:%M").replace(tzinfo=KST)
                if batch_time >= cutoff:
                    kept.append(batch)
            except:
                kept.append(batch)
        if kept:
            cleaned[cat] = kept
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    return cleaned

# ── 이번 수집분을 아카이브에 추가 ──
def update_archive(archive, all_news, collected_at):
    for cat, articles in all_news.items():
        if cat not in archive:
            archive[cat] = []
        # 중복 배치 방지
        existing_ids = {a["id"] for batch in archive[cat] for a in batch["articles"]}
        new_articles = [a for a in articles if a["id"] not in existing_ids]
        if new_articles:
            archive[cat].append({
                "collected_at": collected_at,
                "articles": new_articles
            })
    return archive

# ── 아카이브에서 최근 24시간 기사 추출 ──
def get_recent_archive(archive, hours=24):
    cutoff = datetime.now(KST) - timedelta(hours=hours)
    result = {}
    for cat, batches in archive.items():
        articles = []
        seen_ids = set()
        # 최신 배치부터 역순으로
        for batch in reversed(batches):
            try:
                batch_time = datetime.strptime(batch["collected_at"], "%Y-%m-%d %H:%M").replace(tzinfo=KST)
                if batch_time >= cutoff:
                    for a in batch["articles"]:
                        if a["id"] not in seen_ids:
                            a["batch_time"] = batch["collected_at"]
                            articles.append(a)
                            seen_ids.add(a["id"])
            except:
                continue
        result[cat] = articles
    return result

def generate_html(all_news, archive_news, updated_time):
    # ── 탭 버튼 ──
    tabs_html = ""
    categories = list(all_news.keys())
    for i, cat in enumerate(categories):
        active = "active" if i == 0 else ""
        tabs_html += (
            f'<button class="tab-btn {active}" onclick="switchTab(\'{cat}\')" id="btn-{cat}">'
            f'{cat}<span class="new-badge" id="badge-{cat}"></span>'
            f'</button>\n'
        )
    # 지난 기사 탭
    tabs_html += '<button class="tab-btn archive-btn" onclick="switchTab(\'__archive__\')" id="btn-__archive__">🗂️ 지난 기사</button>\n'

    # ── 현재 뉴스 탭 콘텐츠 ──
    contents_html = ""
    for i, (cat, articles) in enumerate(all_news.items()):
        display = "block" if i == 0 else "none"
        cards_html = _build_cards(articles, cat)
        contents_html += f'''
    <div class="tab-content" id="tab-{cat}" style="display:{display}">
      <div class="tab-toolbar">
        <span class="unread-count" id="count-{cat}"></span>
        <button class="mark-all-btn" onclick="markAllRead('{cat}')">✅ 전체 읽음</button>
      </div>
      <div class="grid">{cards_html}</div>
    </div>'''

    # ── 지난 기사 탭 콘텐츠 ──
    archive_inner = ""
    for cat, articles in archive_news.items():
        if not articles:
            continue
        cards_html = _build_cards(articles, f"archive_{cat}", show_batch=True)
        archive_inner += f'''
      <div class="archive-section">
        <div class="archive-cat-title">{cat}</div>
        <div class="grid">{cards_html}</div>
      </div>'''

    if not archive_inner:
        archive_inner = '<div class="no-news">📭 아직 누적된 지난 기사가 없습니다.<br>1시간 후부터 쌓이기 시작해요!</div>'

    contents_html += f'''
    <div class="tab-content" id="tab-__archive__" style="display:none">
      <div class="tab-toolbar">
        <span class="unread-count" id="count-__archive__" style="color:var(--sub);font-size:0.82rem;">📦 최근 24시간 누적 기사</span>
        <button class="mark-all-btn" onclick="markAllReadArchive()">✅ 전체 읽음</button>
      </div>
      {archive_inner}
    </div>'''

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>My News Dashboard</title>
<style>
  :root {{
    --bg: #0f1117; --card-bg: #1a1d27; --card-read: #13151e;
    --border: #2e3150; --border-read: #1e2035;
    --text: #e0e0e0; --text-read: #4a4f6a;
    --sub: #8b8fa8; --accent: #4f8ef7; --tag-bg: #252840;
    --new-color: #ff5c5c; --archive-accent: #f7a84f;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; padding: 24px 24px 60px; min-height: 100vh; }}
  header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 8px; }}
  header h1 {{ font-size: 1.6rem; color: #fff; }}
  .header-right {{ display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }}
  .updated {{ font-size: 0.8rem; color: var(--sub); }}
  .refresh-badge {{ font-size: 0.72rem; color: #4caf50; background: #1b2e1b; padding: 3px 10px; border-radius: 20px; border: 1px solid #2e5c2e; }}
  .tabs {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }}
  .tab-btn {{
    position: relative; padding: 8px 22px; border: 1px solid var(--border);
    border-radius: 999px; background: var(--card-bg); color: var(--sub);
    cursor: pointer; font-size: 0.9rem; transition: all 0.2s;
  }}
  .tab-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .tab-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  .archive-btn:hover {{ border-color: var(--archive-accent); color: var(--archive-accent); }}
  .archive-btn.active {{ background: var(--archive-accent); border-color: var(--archive-accent); }}
  .new-badge {{
    position: absolute; top: -7px; right: -7px;
    background: var(--new-color); color: #fff; font-size: 0.62rem; font-weight: 700;
    padding: 2px 6px; border-radius: 999px; display: none;
  }}
  .tab-toolbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }}
  .unread-count {{ font-size: 0.82rem; color: var(--sub); }}
  .unread-count span {{ color: var(--new-color); font-weight: 700; }}
  .mark-all-btn {{
    font-size: 0.78rem; padding: 5px 14px; border: 1px solid var(--border);
    border-radius: 8px; background: var(--card-bg); color: var(--sub);
    cursor: pointer; transition: all 0.2s;
  }}
  .mark-all-btn:hover {{ border-color: #4caf50; color: #4caf50; }}
  .archive-section {{ margin-bottom: 36px; }}
  .archive-cat-title {{
    font-size: 1rem; font-weight: 700; color: var(--archive-accent);
    margin-bottom: 12px; padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }}
  .card {{
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 12px; padding: 18px;
    display: flex; flex-direction: column; gap: 10px;
    transition: border-color 0.2s, transform 0.15s, opacity 0.3s;
    cursor: pointer;
  }}
  .card:hover {{ border-color: var(--accent); transform: translateY(-2px); }}
  .card.read {{ background: var(--card-read); border-color: var(--border-read); opacity: 0.55; }}
  .card.read:hover {{ border-color: var(--border); transform: none; opacity: 0.65; }}
  .card-top {{ display: flex; justify-content: space-between; align-items: center; }}
  .card-source {{
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em;
    color: var(--accent); background: var(--tag-bg); padding: 3px 8px; border-radius: 4px;
  }}
  .unread-dot {{
    font-size: 0.65rem; font-weight: 800; background: var(--new-color);
    color: #fff; padding: 2px 7px; border-radius: 999px;
  }}
  .card.read .unread-dot {{ display: none; }}
  .card-title {{ font-size: 0.95rem; font-weight: 600; line-height: 1.4; }}
  .card-title a {{ color: var(--text); text-decoration: none; }}
  .card-title a:hover {{ color: var(--accent); }}
  .card.read .card-title a {{ color: var(--text-read); }}
  .card-summary {{ font-size: 0.82rem; color: var(--sub); line-height: 1.55; flex: 1; }}
  .card-date {{ font-size: 0.75rem; color: var(--sub); margin-top: auto; padding-top: 6px; border-top: 1px solid var(--border); }}
  .card-batch {{ font-size: 0.7rem; color: var(--archive-accent); margin-top: 2px; }}
  .no-news {{ color: var(--sub); padding: 60px; text-align: center; font-size: 1rem; line-height: 2; }}
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
function switchTab(cat) {{
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + cat).style.display = 'block';
  document.getElementById('btn-' + cat).classList.add('active');
}}
const STORAGE_KEY = 'news_read_ids';
function getReadIds() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')); }}
  catch {{ return new Set(); }}
}}
function saveReadIds(set) {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
}}
function markRead(cardEl) {{
  const id = cardEl.dataset.id;
  const readIds = getReadIds();
  readIds.add(id);
  saveReadIds(readIds);
  cardEl.classList.add('read');
  updateCounts();
}}
function markAllRead(cat) {{
  const readIds = getReadIds();
  document.querySelectorAll(`[data-cat="${{cat}}"]`).forEach(card => {{
    readIds.add(card.dataset.id);
    card.classList.add('read');
  }});
  saveReadIds(readIds);
  updateCounts();
}}
function markAllReadArchive() {{
  const readIds = getReadIds();
  document.querySelectorAll('#tab-__archive__ .card').forEach(card => {{
    readIds.add(card.dataset.id);
    card.classList.add('read');
  }});
  saveReadIds(readIds);
  updateCounts();
}}
function updateCounts() {{
  const readIds = getReadIds();
  document.querySelectorAll('.tab-content').forEach(tabEl => {{
    const cat = tabEl.id.replace('tab-', '');
    if (cat === '__archive__') return;
    const cards = tabEl.querySelectorAll('.card');
    const unread = [...cards].filter(c => !readIds.has(c.dataset.id)).length;
    const total  = cards.length;
    const countEl = document.getElementById('count-' + cat);
    if (countEl) countEl.innerHTML = `안 읽은 기사 <span>${{unread}}</span> / 전체 ${{total}}`;
    const badge = document.getElementById('badge-' + cat);
    if (badge) {{
      badge.textContent = unread;
      badge.style.display = unread > 0 ? 'inline-block' : 'none';
    }}
  }});
}}
function restoreReadState() {{
  const readIds = getReadIds();
  readIds.forEach(id => {{
    const card = document.getElementById('card-' + id);
    if (card) card.classList.add('read');
  }});
  updateCounts();
}}
(function() {{
  const TOTAL = 3600;
  let remaining = TOTAL;
  function fmt(sec) {{
    return String(Math.floor(sec/60)).padStart(2,'0') + ':' + String(sec%60).padStart(2,'0');
  }}
  function tick() {{
    remaining--;
    document.getElementById('countdown-text').textContent = fmt(remaining);
    document.getElementById('progress-fill').style.width = ((TOTAL-remaining)/TOTAL*100).toFixed(2)+'%';
    if (remaining <= 0) location.reload();
  }}
  document.getElementById('countdown-text').textContent = fmt(remaining);
  setInterval(tick, 1000);
}})();
restoreReadState();
</script>
</body>
</html>'''

def _build_cards(articles, cat, show_batch=False):
    if not articles:
        return '<div class="no-news">📭 현재 뉴스를 불러올 수 없습니다.</div>'
    html = ""
    for a in articles:
        batch_line = f'<div class="card-batch">📥 수집: {a.get("batch_time","")}</div>' if show_batch else ""
        html += f'''
    <div class="card" id="card-{a["id"]}" data-id="{a["id"]}" data-cat="{cat}" onclick="markRead(this)">
      <div class="card-top">
        <div class="card-source">{a["source"]}</div>
        <span class="unread-dot">NEW</span>
      </div>
      <div class="card-title"><a href="{a["link"]}" target="_blank" onclick="event.stopPropagation()">{a["title"]}</a></div>
      <div class="card-summary">{a["summary"]}</div>
      <div class="card-date">🕐 {a["date"]}</div>
      {batch_line}
    </div>'''
    return html

if __name__ == "__main__":
    now_kst    = datetime.now(KST)
    now_str    = now_kst.strftime("%Y-%m-%d %H:%M")
    now_display = now_kst.strftime("%Y년 %m월 %d일 %H:%M KST")

    # 1. 현재 뉴스 수집
    all_news = {}
    for cat, sources in FEEDS.items():
        print(f"[수집 중] {cat}...")
        all_news[cat] = fetch_news(cat, sources)
        print(f"  → {len(all_news[cat])}개 수집 완료")

    # 2. 아카이브 업데이트
    archive = load_archive()
    archive = update_archive(archive, all_news, now_str)
    archive = save_archive(archive)
    print(f"✅ 아카이브 저장 완료")

    # 3. 최근 24시간 아카이브 추출
    archive_news = get_recent_archive(archive, hours=24)

    # 4. HTML 생성
    html = generate_html(all_news, archive_news, now_display)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ index.html 생성 완료!")
