import feedparser
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ────────────────────────────────────────────
# ① RSS 피드 정의 (영문 + 한국어 소스 추가)
# ────────────────────────────────────────────
FEEDS = {
    "IT/테크": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://feeds.wired.com/wired/index",
        "https://arstechnica.com/feed/",
    ],
    "경제/주식": [
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.ft.com/?format=rss",
    ],
    "국제 뉴스": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    ],
    "AI": [
        "https://venturebeat.com/category/ai/feed/",
        "https://www.artificialintelligence-news.com/feed/",
    ],
    "스포츠": [
        "https://www.espn.com/espn/rss/news",
        "https://feeds.bbci.co.uk/sport/rss.xml",
    ],
    # ④ 한국어 뉴스 소스 추가
    "국내 뉴스": [
        "https://www.yonhapnewstv.co.kr/feed/",          # 연합뉴스TV
        "https://rss.hani.co.kr/rss/",                    # 한겨레
        "https://www.chosun.com/arc/outboundfeeds/rss/",  # 조선일보
        "https://www.khan.co.kr/rss/rssdata/kh_total.xml",# 경향신문
    ],
    "IT 한국": [
        "https://feeds.feedburner.com/zdnetkorea",         # ZDNet Korea
        "https://www.itworld.co.kr/rss/news",              # ITWorld Korea
        "https://www.bloter.net/feed",                     # 블로터
    ],
}

ARCHIVE_FILE = "news_archive.json"
MAX_DAYS = 7
MAX_ARTICLES_PER_CAT = 20

KST = timezone(timedelta(hours=9))

# ────────────────────────────────────────────
# ③ 썸네일 추출 함수
# ────────────────────────────────────────────
def extract_thumbnail(entry):
    """RSS 엔트리에서 썸네일 이미지 URL 추출"""
    # 1) media:content 태그
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            url = m.get('url', '')
            if url and any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                return url
        # 확장자 없어도 첫 번째 media url 반환
        if entry.media_content[0].get('url'):
            return entry.media_content[0]['url']

    # 2) media:thumbnail 태그
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')

    # 3) enclosure 태그
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href', '')

    # 4) content 내 첫 번째 <img> 태그 파싱
    content = ''
    if hasattr(entry, 'content') and entry.content:
        content = entry.content[0].get('value', '')
    elif hasattr(entry, 'summary'):
        content = entry.summary or ''

    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if img_match:
        url = img_match.group(1)
        if url.startswith('http'):
            return url

    return ''  # 썸네일 없음


def clean_text(html):
    """HTML 태그 제거 및 텍스트 정리"""
    text = re.sub(r'<[^>]+>', '', html or '')
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:150] + '...' if len(text) > 150 else text


def get_source_domain(url):
    """URL에서 도메인 추출 (파비콘용)"""
    match = re.search(r'https?://([^/]+)', url or '')
    return match.group(1) if match else ''


def fetch_articles(cat, urls):
    articles = []
    seen_titles = set()
    for url in urls:
        try:
            feed = feedparser.parse(url, agent='Mozilla/5.0')
            source_name = feed.feed.get('title', get_source_domain(url))
            source_domain = get_source_domain(url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '').strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                link = entry.get('link', '')
                summary = clean_text(entry.get('summary', entry.get('description', '')))
                thumbnail = extract_thumbnail(entry)  # ③ 썸네일
                pub = entry.get('published', entry.get('updated', ''))
                articles.append({
                    'id': abs(hash(title + link)) % (10**10),
                    'title': title,
                    'link': link,
                    'summary': summary,
                    'thumbnail': thumbnail,           # ③ 추가
                    'source': source_name,
                    'source_domain': source_domain,
                    'pub_date': pub,
                    'cat': cat,
                    'fetched_at': datetime.now(KST).isoformat(),
                })
        except Exception as e:
            print(f"  [ERROR] {url}: {e}")
    return articles[:MAX_ARTICLES_PER_CAT]


def load_archive():
    if Path(ARCHIVE_FILE).exists():
        with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_archive(data):
    with open(ARCHIVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def prune_old(archive):
    cutoff = datetime.now(KST) - timedelta(days=MAX_DAYS)
    for cat in archive:
        archive[cat] = [
            snap for snap in archive[cat]
            if datetime.fromisoformat(snap['timestamp']) > cutoff
        ]
    return archive


# ────────────────────────────────────────────
# HTML 템플릿 (② 검색 + ③ 썸네일 + ④ 국내)
# ────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📰 내 뉴스 대시보드</title>
<style>
  :root {
    --bg: #0f1117;
    --card-bg: #1a1d27;
    --card-hover: #22263a;
    --accent: #4f8ef7;
    --accent2: #a78bfa;
    --text: #e2e8f0;
    --muted: #64748b;
    --border: #2d3148;
    --new-badge: #ef4444;
    --read-op: 0.45;
    --tab-active: #4f8ef7;
    --search-bg: #1e2235;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', 'Apple SD Gothic Neo', sans-serif;
    min-height: 100vh;
  }

  /* ── 헤더 ── */
  header {
    background: linear-gradient(135deg, #1a1d27 0%, #12151f 100%);
    border-bottom: 1px solid var(--border);
    padding: 18px 24px 0;
    position: sticky; top: 0; z-index: 100;
  }
  .header-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  .logo { font-size: 1.3rem; font-weight: 700; }
  .logo span { color: var(--accent); }
  .header-right { display: flex; align-items: center; gap: 12px; }
  .update-time { font-size: 0.75rem; color: var(--muted); }

  /* ── ② 검색창 ── */
  .search-wrap {
    position: relative;
    width: 260px;
  }
  .search-wrap input {
    width: 100%;
    background: var(--search-bg);
    border: 1px solid var(--border);
    border-radius: 20px;
    color: var(--text);
    font-size: 0.85rem;
    padding: 7px 36px 7px 14px;
    outline: none;
    transition: border 0.2s;
  }
  .search-wrap input:focus { border-color: var(--accent); }
  .search-wrap input::placeholder { color: var(--muted); }
  .search-icon {
    position: absolute; right: 12px; top: 50%;
    transform: translateY(-50%);
    color: var(--muted); font-size: 0.9rem; pointer-events: none;
  }
  .search-count {
    font-size: 0.75rem; color: var(--accent);
    display: none; white-space: nowrap;
  }

  /* ── 탭 ── */
  .tabs {
    display: flex; gap: 4px; overflow-x: auto;
    scrollbar-width: none;
  }
  .tabs::-webkit-scrollbar { display: none; }
  .tab-btn {
    background: none; border: none;
    color: var(--muted);
    padding: 10px 16px 8px;
    font-size: 0.88rem; font-weight: 500;
    cursor: pointer; white-space: nowrap;
    border-bottom: 2px solid transparent;
    transition: all 0.2s; position: relative;
  }
  .tab-btn:hover { color: var(--text); }
  .tab-btn.active {
    color: var(--tab-active);
    border-bottom-color: var(--tab-active);
  }
  .badge {
    background: var(--new-badge);
    color: #fff; border-radius: 10px;
    font-size: 0.7rem; font-weight: 700;
    padding: 1px 6px; margin-left: 5px;
    vertical-align: middle;
  }

  /* ── 메인 컨텐츠 ── */
  main { max-width: 1400px; margin: 0 auto; padding: 20px 16px; }

  /* ── 탭 패널 ── */
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  /* ── 패널 상단 바 ── */
  .panel-bar {
    display: flex; align-items: center;
    justify-content: space-between;
    margin-bottom: 16px; flex-wrap: wrap; gap: 8px;
  }
  .panel-info { font-size: 0.82rem; color: var(--muted); }
  .panel-info span { color: var(--accent); font-weight: 700; }
  .btn-mark-all {
    background: none; border: 1px solid var(--border);
    color: var(--muted); border-radius: 6px;
    padding: 5px 12px; font-size: 0.78rem;
    cursor: pointer; transition: all 0.2s;
  }
  .btn-mark-all:hover { border-color: var(--accent); color: var(--accent); }

  /* ── 카드 그리드 ── */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 14px;
  }

  /* ── ③ 썸네일 포함 카드 ── */
  .card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    cursor: pointer;
    transition: transform 0.18s, box-shadow 0.18s, opacity 0.3s;
    display: flex; flex-direction: column;
  }
  .card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    border-color: var(--accent);
  }
  .card.read { opacity: var(--read-op); }
  .card.hidden { display: none !important; }  /* 검색 필터용 */

  /* 썸네일 영역 */
  .card-thumb {
    width: 100%; height: 160px;
    overflow: hidden; position: relative;
    background: var(--search-bg);
  }
  .card-thumb img {
    width: 100%; height: 100%;
    object-fit: cover;
    transition: transform 0.3s;
  }
  .card:hover .card-thumb img { transform: scale(1.04); }
  .card-thumb.no-img {
    display: flex; align-items: center;
    justify-content: center;
    color: var(--muted); font-size: 2rem;
  }

  .card-body { padding: 14px; flex: 1; display: flex; flex-direction: column; gap: 8px; }
  .card-top { display: flex; align-items: center; justify-content: space-between; }
  .source-wrap { display: flex; align-items: center; gap: 6px; }
  .favicon {
    width: 16px; height: 16px; border-radius: 3px;
    object-fit: contain; flex-shrink: 0;
  }
  .source-name { font-size: 0.72rem; color: var(--muted); }
  .new-badge {
    background: var(--new-badge); color: #fff;
    font-size: 0.65rem; font-weight: 700;
    padding: 2px 6px; border-radius: 4px; letter-spacing: 0.5px;
  }
  .card.read .new-badge { display: none; }
  .card-title {
    font-size: 0.92rem; font-weight: 600;
    line-height: 1.45; color: var(--text);
    display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .card-summary {
    font-size: 0.78rem; color: var(--muted);
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 3; -webkit-box-orient: vertical;
    overflow: hidden;
    flex: 1;
  }
  .card-footer {
    font-size: 0.72rem; color: var(--muted);
    display: flex; justify-content: space-between;
    align-items: center;
    border-top: 1px solid var(--border);
    padding-top: 8px; margin-top: auto;
  }
  .read-label {
    font-size: 0.7rem; color: var(--accent2);
    display: none;
  }
  .card.read .read-label { display: inline; }

  /* ── 검색 없음 메시지 ── */
  .no-results {
    text-align: center; padding: 60px 20px;
    color: var(--muted); display: none;
  }
  .no-results.show { display: block; }
  .no-results-icon { font-size: 2.5rem; margin-bottom: 12px; }

  /* ── 아카이브 ── */
  .batch-group { margin-bottom: 24px; }
  .batch-header {
    font-size: 0.8rem; color: var(--muted);
    border-left: 3px solid var(--accent);
    padding-left: 10px; margin-bottom: 12px;
  }

  /* ── 하단 새로고침 바 ── */
  .refresh-bar {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: #12151f; border-top: 1px solid var(--border);
    padding: 8px 20px;
    display: flex; align-items: center; justify-content: center;
    gap: 12px; font-size: 0.8rem; color: var(--muted);
  }
  #countdown { color: var(--accent); font-weight: 600; }
  .refresh-btn {
    background: var(--accent); color: #fff;
    border: none; border-radius: 6px;
    padding: 4px 12px; font-size: 0.78rem;
    cursor: pointer; font-weight: 600;
  }
  pb { padding-bottom: 48px; display: block; }
</style>
</head>
<body>

<header>
  <div class="header-top">
    <div class="logo">📰 <span>My</span>News</div>
    <div class="header-right">
      <!-- ② 검색창 -->
      <div class="search-wrap">
        <input type="text" id="searchInput" placeholder="🔍 기사 제목/내용 검색...">
        <span class="search-icon">⌕</span>
      </div>
      <span class="search-count" id="searchCount"></span>
      <span class="update-time">업데이트: __UPDATED__</span>
    </div>
  </div>
  <div class="tabs" id="tabBar">__TABS__</div>
</header>

<main>
  __PANELS__
  <pb></pb>
</main>

<div class="refresh-bar">
  ⏱ 자동 새로고침까지 <span id="countdown">60:00</span>
  <button class="refresh-btn" onclick="location.reload()">지금 새로고침</button>
</div>

<script>
// ── 탭 전환 ──
function switchTab(cat) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.cat === cat));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + cat));
  // 검색어 유지 시 해당 탭에서도 필터링
  const q = document.getElementById('searchInput').value.trim();
  if (q) filterCards(q);
  updateCounts();
}

// ── localStorage read 관리 ──
const READ_KEY = 'news_read_ids';
function getReadIds() { return new Set(JSON.parse(localStorage.getItem(READ_KEY) || '[]')); }
function saveReadIds(s) { localStorage.setItem(READ_KEY, JSON.stringify([...s])); }

function markRead(card) {
  const id = card.dataset.id;
  const ids = getReadIds();
  ids.add(id);
  saveReadIds(ids);
  card.classList.add('read');
  updateCounts();
}

function markAllRead(cat) {
  const panel = document.getElementById('tab-' + cat);
  const ids = getReadIds();
  panel.querySelectorAll('.card').forEach(c => { ids.add(c.dataset.id); c.classList.add('read'); });
  saveReadIds(ids);
  updateCounts();
}

// 페이지 로드 시 read 상태 복원
function restoreRead() {
  const ids = getReadIds();
  document.querySelectorAll('.card').forEach(c => {
    if (ids.has(c.dataset.id)) c.classList.add('read');
  });
}

// ── 카운트 업데이트 (탭별 정확히) ──
function updateCounts() {
  const readIds = getReadIds();
  document.querySelectorAll('.tab-btn').forEach(btn => {
    const cat = btn.dataset.cat;
    if (cat === '__archive__') return;
    const panel = document.getElementById('tab-' + cat);
    if (!panel) return;
    // hidden(검색 필터) 카드 제외
    const cards = [...panel.querySelectorAll('.card')].filter(c => !c.classList.contains('hidden'));
    const unread = cards.filter(c => !readIds.has(c.dataset.id)).length;
    const badge = document.getElementById('badge-' + cat);
    if (badge) { badge.textContent = unread; badge.style.display = unread > 0 ? '' : 'none'; }
    const info = document.getElementById('info-' + cat);
    if (info) info.innerHTML = `안 읽은 기사 <span>${unread}</span> / 전체 ${cards.length}`;
  });
}

// ── ② 검색 기능 ──
function filterCards(query) {
  const q = query.toLowerCase().trim();
  // 현재 활성 탭만 검색
  const activePanel = document.querySelector('.tab-panel.active');
  if (!activePanel) return;

  let visible = 0;
  activePanel.querySelectorAll('.card').forEach(card => {
    const title = (card.dataset.title || '').toLowerCase();
    const summary = (card.dataset.summary || '').toLowerCase();
    const source = (card.dataset.source || '').toLowerCase();
    const match = !q || title.includes(q) || summary.includes(q) || source.includes(q);
    card.classList.toggle('hidden', !match);
    if (match) visible++;
  });

  // 검색 결과 없음 메시지
  const noRes = activePanel.querySelector('.no-results');
  if (noRes) noRes.classList.toggle('show', visible === 0 && q !== '');

  // 검색 카운트 표시
  const countEl = document.getElementById('searchCount');
  if (q) {
    countEl.textContent = `${visible}건 검색됨`;
    countEl.style.display = 'inline';
  } else {
    countEl.style.display = 'none';
  }
  updateCounts();
}

document.getElementById('searchInput').addEventListener('input', e => {
  filterCards(e.target.value);
});

// ── 카드 클릭 ──
document.querySelectorAll('.card').forEach(card => {
  card.addEventListener('click', () => {
    markRead(card);
    window.open(card.dataset.href, '_blank');
  });
});

// ── 카운트다운 타이머 ──
let secs = 3600;
const cdEl = document.getElementById('countdown');
setInterval(() => {
  secs--;
  if (secs <= 0) location.reload();
  const m = String(Math.floor(secs/60)).padStart(2,'0');
  const s = String(secs%60).padStart(2,'0');
  cdEl.textContent = m + ':' + s;
}, 1000);

// ── 초기화 ──
restoreRead();
updateCounts();
switchTab('__FIRST_CAT__');
</script>
</body>
</html>"""


# ────────────────────────────────────────────
# HTML 생성 함수
# ────────────────────────────────────────────
def build_card_html(article):
    """③ 썸네일 포함 카드 HTML 생성"""
    thumb_html = ''
    if article.get('thumbnail'):
        thumb_html = f'''<div class="card-thumb">
      ![image]({article[)
    </div>'''
    else:
        thumb_html = '<div class="card-thumb no-img">📰</div>'

    domain = article.get('source_domain', '')
    favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32" if domain else ''
    favicon_html = f'![image]({favicon_url})' if favicon_url else ''

    # data 속성에 검색용 텍스트 삽입
    title_esc = article['title'].replace('"', '&quot;')
    summary_esc = article.get('summary', '').replace('"', '&quot;')
    source_esc = article.get('source', '').replace('"', '&quot;')

    return f'''<div class="card"
     data-id="{article['id']}"
     data-href="{article['link']}"
     data-cat="{article['cat']}"
     data-title="{title_esc}"
     data-summary="{summary_esc}"
     data-source="{source_esc}">
  {thumb_html}
  <div class="card-body">
    <div class="card-top">
      <div class="source-wrap">
        {favicon_html}
        <span class="source-name">{article.get('source','')}</span>
      </div>
      <span class="new-badge">NEW</span>
    </div>
    <div class="card-title">{article['title']}</div>
    <div class="card-summary">{article.get('summary','')}</div>
    <div class="card-footer">
      <span>{article.get('pub_date','')[:16]}</span>
      <span class="read-label">✓ 읽음</span>
    </div>
  </div>
</div>'''


def build_html(archive):
    cats = list(FEEDS.keys())
    first_cat = cats[0]

    # 탭 버튼 생성
    tabs_html = ''
    for cat in cats:
        tabs_html += f'<button class="tab-btn" data-cat="{cat}" onclick="switchTab(\'{cat}\')">{cat} <span class="badge" id="badge-{cat}">0</span></button>\n'
    tabs_html += '<button class="tab-btn" data-cat="__archive__" onclick="switchTab(\'__archive__\')">📁 지난 기사</button>\n'

    # 패널 생성
    panels_html = ''
    archive_batches = {}

    for cat in cats:
        snaps = archive.get(cat, [])
        if not snaps:
            continue
        latest = snaps[-1]  # 최신 스냅샷
        articles = latest.get('articles', [])

        cards_html = ''.join(build_card_html(a) for a in articles)

        panels_html += f'''<div class="tab-panel" id="tab-{cat}">
  <div class="panel-bar">
    <div class="panel-info" id="info-{cat}">로딩 중...</div>
    <button class="btn-mark-all" onclick="markAllRead('{cat}')">모두 읽음 처리</button>
  </div>
  <div class="card-grid">{cards_html}</div>
  <div class="no-results">
    <div class="no-results-icon">🔍</div>
    <div>검색 결과가 없습니다</div>
  </div>
</div>\n'''

        # 아카이브용 배치 수집
        for snap in snaps:
            ts = snap['timestamp']
            if ts not in archive_batches:
                archive_batches[ts] = []
            for a in snap.get('articles', []):
                a['_ts'] = ts
                archive_batches[ts].append(a)

    # 아카이브 패널
    archive_html = ''
    for ts in sorted(archive_batches.keys(), reverse=True):
        arts = archive_batches[ts]
        dt_str = ts[:16].replace('T', ' ')
        cards = ''.join(build_card_html(a) for a in arts[:30])
        archive_html += f'''<div class="batch-group">
  <div class="batch-header">🗂 {dt_str} 수집 ({len(arts)}건)</div>
  <div class="card-grid">{cards}</div>
</div>\n'''

    panels_html += f'''<div class="tab-panel" id="tab-__archive__">
  <div class="panel-bar">
    <div class="panel-info">📁 최근 7일 아카이브</div>
  </div>
  {archive_html}
  <div class="no-results">
    <div class="no-results-icon">🔍</div>
    <div>검색 결과가 없습니다</div>
  </div>
</div>'''

    now_kst = datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')
    html = HTML_TEMPLATE \
        .replace('__TABS__', tabs_html) \
        .replace('__PANELS__', panels_html) \
        .replace('__UPDATED__', now_kst) \
        .replace('__FIRST_CAT__', first_cat)

    return html


# ────────────────────────────────────────────
# 메인 실행
# ────────────────────────────────────────────
def main():
    print(f"[{datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}] 뉴스 수집 시작")
    archive = load_archive()
    archive = prune_old(archive)

    timestamp = datetime.now(KST).isoformat()

    for cat, urls in FEEDS.items():
        print(f"  [{cat}] 수집 중...")
        articles = fetch_articles(cat, urls)
        print(f"  [{cat}] {len(articles)}건 수집 완료")
        if cat not in archive:
            archive[cat] = []
        archive[cat].append({'timestamp': timestamp, 'articles': articles})

    save_archive(archive)
    print("✅ 아카이브 저장 완료")

    html = build_html(archive)
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ index.html 생성 완료")
    print(f"   총 카테고리: {len(FEEDS)}개")


if __name__ == '__main__':
    main()
