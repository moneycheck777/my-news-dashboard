import feedparser
import json
import os
import hashlib
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from html.parser import HTMLParser

# ──────────────────────────────────────────
# 설정
# ──────────────────────────────────────────
ARCHIVE_FILE = "news_archive.json"
OUTPUT_FILE  = "index.html"
MAX_DAYS     = 7
UA = "Mozilla/5.0 (compatible; NewsDashboard/1.0)"

RSS_FEEDS = [
    # 영어 뉴스
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",            "source": "BBC News",          "cat": "세계"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "source": "NYT World",         "cat": "세계"},
    {"url": "https://feeds.reuters.com/reuters/topNews",              "source": "Reuters",           "cat": "세계"},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml",       "source": "BBC Tech",          "cat": "기술"},
    {"url": "https://feeds.wired.com/wired/index",                    "source": "Wired",             "cat": "기술"},
    {"url": "https://techcrunch.com/feed/",                           "source": "TechCrunch",        "cat": "기술"},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",         "source": "BBC Business",      "cat": "경제"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",         "source": "Reuters Business",  "cat": "경제"},
    # 한국 뉴스
    {"url": "https://www.yonhapnewstv.co.kr/category/news/headline/feed/", "source": "연합뉴스TV",  "cat": "세계"},
    {"url": "https://www.hani.co.kr/rss/",                           "source": "한겨레",            "cat": "세계"},
    {"url": "https://www.chosun.com/arc/outboundfeeds/rss/",         "source": "조선일보",          "cat": "세계"},
    {"url": "https://www.khan.co.kr/rss/rssdata/kh_total.xml",       "source": "경향신문",          "cat": "세계"},
    {"url": "https://feeds.feedburner.com/zdkorea",                  "source": "ZDNet Korea",       "cat": "기술"},
    {"url": "https://bloter.net/feed",                               "source": "Bloter",            "cat": "기술"},
]

# ──────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────
def make_id(link):
    return hashlib.md5(link.encode()).hexdigest()[:12]

def parse_pub_date(entry):
    for attr in ('published_parsed', 'updated_parsed'):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()

def is_within_days(iso_str, days=MAX_DAYS):
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt < timedelta(days=days)
    except Exception:
        return True

# ──────────────────────────────────────────
# 썸네일 추출
# ──────────────────────────────────────────
class ImgParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.src = None
    def handle_starttag(self, tag, attrs):
        if tag == 'img' and not self.src:
            for k, v in attrs:
                if k == 'src' and v and v.startswith('http'):
                    self.src = v

def extract_thumbnail(entry):
    # 1) media:content
    media = getattr(entry, 'media_content', None)
    if media and isinstance(media, list):
        for m in media:
            url = m.get('url', '')
            if url.startswith('http'):
                return url

    # 2) media:thumbnail
    thumb = getattr(entry, 'media_thumbnail', None)
    if thumb and isinstance(thumb, list):
        url = thumb[0].get('url', '')
        if url.startswith('http'):
            return url

    # 3) enclosure
    for enc in getattr(entry, 'enclosures', []):
        if getattr(enc, 'type', '').startswith('image'):
            url = getattr(enc, 'href', '') or getattr(enc, 'url', '')
            if url.startswith('http'):
                return url

    # 4) summary 안 <img>
    summary = getattr(entry, 'summary', '') or ''
    p = ImgParser()
    p.feed(summary)
    if p.src:
        return p.src

    return ''

# ──────────────────────────────────────────
# RSS 수집
# ──────────────────────────────────────────
def fetch_all():
    articles = {}
    for feed_info in RSS_FEEDS:
        try:
            d = feedparser.parse(feed_info['url'],
                                 agent=UA,
                                 request_headers={'Accept-Language': 'ko,en;q=0.9'})
            for entry in d.entries[:15]:
                link = getattr(entry, 'link', '')
                if not link:
                    continue
                aid = make_id(link)
                if aid in articles:
                    continue
                title   = getattr(entry, 'title', '').strip()
                summary = re.sub(r'<[^>]+>', '', getattr(entry, 'summary', '') or '').strip()[:200]
                domain  = urlparse(link).netloc.replace('www.', '')
                articles[aid] = {
                    'id':            aid,
                    'title':         title,
                    'link':          link,
                    'summary':       summary,
                    'source':        feed_info['source'],
                    'source_domain': domain,
                    'cat':           feed_info['cat'],
                    'pub_date':      parse_pub_date(entry),
                    'thumbnail':     extract_thumbnail(entry),
                }
        except Exception as e:
            print(f"[WARN] {feed_info['source']} 수집 실패: {e}")
    return articles

# ──────────────────────────────────────────
# 아카이브 관리
# ──────────────────────────────────────────
def load_archive():
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_archive(data):
    with open(ARCHIVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def merge_archive(old, new):
    merged = {**old, **new}
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_DAYS)
    result = {}
    for aid, art in merged.items():
        try:
            dt = datetime.fromisoformat(art['pub_date'])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                result[aid] = art
        except Exception:
            result[aid] = art
    return result

# ──────────────────────────────────────────
# 카드 HTML 생성 (f-string 없이 문자열 연결)
# ──────────────────────────────────────────
def build_card_html(article):
    aid     = str(article.get('id', ''))
    href    = article.get('link', '')
    cat     = article.get('cat', '')
    title   = article.get('title', '').replace('"', '&quot;')
    summary = article.get('summary', '').replace('"', '&quot;')
    source  = article.get('source', '').replace('"', '&quot;')
    domain  = article.get('source_domain', '')
    thumb   = article.get('thumbnail', '')
    pub     = article.get('pub_date', '')[:16]

    # 썸네일
    if thumb:
        thumb_html = (
            '<div class="card-thumb">'
            '<img src="' + thumb + '" alt="" loading="lazy"'
            ' onerror="this.parentNode.className=\'card-thumb no-img\';'
            'this.parentNode.innerHTML=\'📰\';">'
            '</div>'
        )
    else:
        thumb_html = '<div class="card-thumb no-img">📰</div>'

    # 파비콘
    if domain:
        favicon_html = (
            '![image](https://www.google.com/s2/favicons?domain=)'
        )
    else:
        favicon_html = ''

    # 카드 조립
    html = (
        '<div class="card"'
        ' data-id="' + aid + '"'
        ' data-href="' + href + '"'
        ' data-cat="' + cat + '"'
        ' data-title="' + title + '"'
        ' data-summary="' + summary + '"'
        ' data-source="' + source + '">'
        + thumb_html +
        '<div class="card-body">'
        '<div class="card-top">'
        '<div class="source-wrap">'
        + favicon_html +
        '<span class="source-name">' + source + '</span>'
        '</div>'
        '<span class="new-badge">NEW</span>'
        '</div>'
        '<div class="card-title">' + article.get('title', '') + '</div>'
        '<div class="card-summary">' + article.get('summary', '') + '</div>'
        '<div class="card-footer">'
        '<span>' + pub + '</span>'
        '<span class="read-label">✓ 읽음</span>'
        '</div>'
        '</div>'
        '</div>'
    )
    return html

# ──────────────────────────────────────────
# HTML 생성
# ──────────────────────────────────────────
def build_html(articles):
    cats = ['세계', '기술', '경제']
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    # 탭별 카드 수집
    tab_cards = {c: [] for c in cats}
    tab_cards['__archive__'] = []
    cutoff_recent = datetime.now(timezone.utc) - timedelta(days=2)

    for art in sorted(articles.values(), key=lambda x: x.get('pub_date', ''), reverse=True):
        c = art.get('cat', '기타')
        card = build_card_html(art)
        if c in tab_cards:
            tab_cards[c].append(card)
        try:
            dt = datetime.fromisoformat(art['pub_date'])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff_recent:
                tab_cards['__archive__'].append(card)
        except Exception:
            pass

    # 탭 버튼
    tab_buttons = ''
    for c in cats:
        cnt = len(tab_cards[c])
        tab_buttons += (
            '<button class="tab-btn" data-tab="tab-' + c + '">'
            + c +
            ' <span class="badge" id="badge-' + c + '">' + str(cnt) + '</span>'
            '</button>'
        )
    tab_buttons += (
        '<button class="tab-btn" data-tab="tab-__archive__">'
        '📁 보관함'
        ' <span class="badge" id="badge-__archive__">' + str(len(tab_cards['__archive__'])) + '</span>'
        '</button>'
    )

    # 탭 컨텐츠
    tab_contents = ''
    for c in cats:
        cards_html = ''.join(tab_cards[c]) if tab_cards[c] else '<p class="empty">뉴스가 없습니다.</p>'
        tab_contents += (
            '<div class="tab-content" id="tab-' + c + '">'
            '<div class="card-grid">' + cards_html + '</div>'
            '</div>'
        )
    archive_html = ''.join(tab_cards['__archive__']) if tab_cards['__archive__'] else '<p class="empty">보관된 뉴스가 없습니다.</p>'
    tab_contents += (
        '<div class="tab-content" id="tab-__archive__">'
        '<div class="card-grid">' + archive_html + '</div>'
        '</div>'
    )

    html = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>My News Dashboard</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --surface2: #22263a;
    --accent: #4f8ef7; --accent2: #7c5cbf;
    --text: #e8eaf6; --muted: #6b7280; --border: #2e3250;
    --green: #22c55e; --red: #ef4444; --yellow: #f59e0b;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; min-height: 100vh; }

  /* 헤더 */
  header {
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface2) 100%);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px; display: flex; align-items: center;
    justify-content: space-between; flex-wrap: wrap; gap: 12px;
    position: sticky; top: 0; z-index: 100;
  }
  .logo { font-size: 1.3rem; font-weight: 700; color: var(--accent); letter-spacing: -0.5px; }
  .updated { font-size: 0.75rem; color: var(--muted); }

  /* 검색 */
  #searchWrap { display: flex; align-items: center; gap: 8px; flex: 1; max-width: 360px; }
  #searchInput {
    width: 100%; padding: 8px 14px; border-radius: 20px;
    border: 1px solid var(--border); background: var(--surface2);
    color: var(--text); font-size: 0.9rem; outline: none; transition: border .2s;
  }
  #searchInput:focus { border-color: var(--accent); }
  #searchCount { font-size: 0.78rem; color: var(--accent); white-space: nowrap; }

  /* 탭 */
  .tab-bar {
    display: flex; gap: 6px; padding: 14px 24px 0;
    border-bottom: 1px solid var(--border); overflow-x: auto;
  }
  .tab-btn {
    padding: 8px 18px; border: none; border-radius: 10px 10px 0 0;
    background: var(--surface2); color: var(--muted);
    cursor: pointer; font-size: 0.9rem; transition: all .2s;
    display: flex; align-items: center; gap: 6px;
  }
  .tab-btn:hover { background: var(--surface); color: var(--text); }
  .tab-btn.active { background: var(--accent); color: #fff; font-weight: 600; }
  .badge {
    background: var(--surface); color: var(--accent);
    border-radius: 10px; padding: 1px 7px;
    font-size: 0.72rem; font-weight: 700;
  }
  .tab-btn.active .badge { background: rgba(255,255,255,.2); color: #fff; }

  /* 컨텐츠 */
  .tab-content { display: none; padding: 24px; }
  .tab-content.active { display: block; }

  /* 카드 그리드 */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  /* 카드 */
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; overflow: hidden; cursor: pointer;
    transition: transform .2s, box-shadow .2s, opacity .3s;
    display: flex; flex-direction: column;
  }
  .card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.4); }
  .card.read { opacity: 0.45; }

  /* 썸네일 */
  .card-thumb {
    width: 100%; height: 160px; overflow: hidden;
    background: var(--surface2); display: flex; align-items: center; justify-content: center;
  }
  .card-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .card-thumb.no-img { font-size: 2.5rem; color: var(--muted); }

  /* 카드 본문 */
  .card-body { padding: 14px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
  .card-top { display: flex; align-items: center; justify-content: space-between; }
  .source-wrap { display: flex; align-items: center; gap: 6px; }
  .favicon { width: 16px; height: 16px; border-radius: 3px; }
  .source-name { font-size: 0.72rem; color: var(--accent); font-weight: 600; text-transform: uppercase; }
  .new-badge {
    font-size: 0.65rem; background: var(--green); color: #fff;
    border-radius: 4px; padding: 1px 6px; font-weight: 700;
    opacity: 1; transition: opacity .3s;
  }
  .card.read .new-badge { opacity: 0; }
  .card-title { font-size: 0.95rem; font-weight: 600; line-height: 1.4; color: var(--text); }
  .card-summary { font-size: 0.8rem; color: var(--muted); line-height: 1.5; }
  .card-footer {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: auto; padding-top: 8px; border-top: 1px solid var(--border);
    font-size: 0.72rem; color: var(--muted);
  }
  .read-label { color: var(--green); opacity: 0; transition: opacity .3s; font-weight: 600; }
  .card.read .read-label { opacity: 1; }

  /* 검색 없음 */
  .no-result {
    grid-column: 1/-1; text-align: center;
    padding: 60px 0; color: var(--muted); font-size: 1rem;
  }
  .empty { color: var(--muted); padding: 40px; text-align: center; }
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">📰 My News Dashboard</div>
    <div class="updated">업데이트: """ + now_str + """</div>
  </div>
  <div id="searchWrap">
    <input type="text" id="searchInput" placeholder="🔍 제목·요약·언론사 검색...">
    <span id="searchCount"></span>
  </div>
</header>

<div class="tab-bar">""" + tab_buttons + """</div>

<main>""" + tab_contents + """</main>

<script>
// ── 읽음 상태 ──
const READ_KEY = 'news_read_ids';
function getRead() {
  try { return new Set(JSON.parse(localStorage.getItem(READ_KEY) || '[]')); }
  catch { return new Set(); }
}
function saveRead(s) {
  localStorage.setItem(READ_KEY, JSON.stringify([...s]));
}
function applyRead() {
  const read = getRead();
  document.querySelectorAll('.card').forEach(card => {
    if (read.has(card.dataset.id)) card.classList.add('read');
  });
  updateBadges();
}
function markRead(card) {
  const read = getRead();
  read.add(card.dataset.id);
  saveRead(read);
  card.classList.add('read');
  updateBadges();
}

// ── 배지(미읽음 수) ──
function updateBadges() {
  const read = getRead();
  document.querySelectorAll('.tab-btn').forEach(btn => {
    const tabId = btn.dataset.tab;
    const cat = tabId.replace('tab-', '');
    const badgeEl = document.getElementById('badge-' + cat);
    if (!badgeEl) return;
    const cards = document.querySelectorAll('#' + tabId + ' .card');
    const unread = [...cards].filter(c => !read.has(c.dataset.id) && c.style.display !== 'none').length;
    badgeEl.textContent = unread;
  });
}

// ── 탭 ──
const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');
function switchTab(targetId) {
  tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === targetId));
  tabContents.forEach(t => t.classList.toggle('active', t.id === targetId));
  filterCards();
}
tabBtns.forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.tab)));

// ── 카드 클릭 ──
document.querySelectorAll('.card').forEach(card => {
  card.addEventListener('click', () => {
    markRead(card);
    window.open(card.dataset.href, '_blank');
  });
});

// ── 검색 ──
const searchInput = document.getElementById('searchInput');
const searchCount = document.getElementById('searchCount');
function filterCards() {
  const q = searchInput.value.trim().toLowerCase();
  const activeTab = document.querySelector('.tab-content.active');
  if (!activeTab) return;
  const cards = activeTab.querySelectorAll('.card');
  let visible = 0;
  cards.forEach(card => {
    const hit = !q
      || card.dataset.title.toLowerCase().includes(q)
      || card.dataset.summary.toLowerCase().includes(q)
      || card.dataset.source.toLowerCase().includes(q);
    card.style.display = hit ? '' : 'none';
    if (hit) visible++;
  });
  // 검색 결과 없음 표시
  const grid = activeTab.querySelector('.card-grid');
  let noRes = activeTab.querySelector('.no-result');
  if (q && visible === 0) {
    if (!noRes) {
      noRes = document.createElement('div');
      noRes.className = 'no-result';
      noRes.textContent = '검색 결과가 없습니다.';
      grid.appendChild(noRes);
    }
    noRes.style.display = '';
  } else {
    if (noRes) noRes.style.display = 'none';
  }
  searchCount.textContent = q ? visible + '건 검색됨' : '';
  updateBadges();
}
searchInput.addEventListener('input', filterCards);

// ── 초기화 ──
switchTab('tab-세계');
applyRead();
</script>
</body>
</html>"""
    return html

# ──────────────────────────────────────────
# 메인
# ──────────────────────────────────────────
if __name__ == '__main__':
    print("뉴스 수집 중...")
    new_articles = fetch_all()
    print(f"  수집: {len(new_articles)}건")

    archive = load_archive()
    merged  = merge_archive(archive, new_articles)
    save_archive(merged)
    print(f"  아카이브: {len(merged)}건")

    html = build_html(merged)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  '{OUTPUT_FILE}' 생성 완료!")
