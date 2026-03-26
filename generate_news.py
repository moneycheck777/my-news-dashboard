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
UA           = "Mozilla/5.0 (compatible; NewsDashboard/1.0)"

RSS_FEEDS = [
    # IT/테크
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml",  "source": "BBC Tech",      "cat": "IT/테크"},
    {"url": "https://feeds.wired.com/wired/index",               "source": "Wired",          "cat": "IT/테크"},
    {"url": "https://techcrunch.com/feed/",                      "source": "TechCrunch",     "cat": "IT/테크"},
    {"url": "https://feeds.feedburner.com/zdkorea",              "source": "ZDNet Korea",    "cat": "IT/테크"},
    # 경제/주식
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",   "source": "BBC Business",   "cat": "경제/주식"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",   "source": "Reuters Biz",    "cat": "경제/주식"},
    # 국제뉴스
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",      "source": "BBC World",      "cat": "국제뉴스"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "source": "NYT World", "cat": "국제뉴스"},
    {"url": "https://feeds.reuters.com/reuters/topNews",        "source": "Reuters",        "cat": "국제뉴스"},
    # AI
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "source": "TC AI", "cat": "AI"},
    {"url": "https://feeds.feedburner.com/venturebeat/SZYF",    "source": "VentureBeat",    "cat": "AI"},
    # 스포츠
    {"url": "https://feeds.bbci.co.uk/sport/rss.xml",           "source": "BBC Sport",      "cat": "스포츠"},
    {"url": "https://www.espn.com/espn/rss/news",               "source": "ESPN",           "cat": "스포츠"},
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
    media = getattr(entry, 'media_content', None)
    if media and isinstance(media, list):
        for m in media:
            url = m.get('url', '')
            if url.startswith('http'):
                return url
    thumb = getattr(entry, 'media_thumbnail', None)
    if thumb and isinstance(thumb, list):
        url = thumb[0].get('url', '')
        if url.startswith('http'):
            return url
    for enc in getattr(entry, 'enclosures', []):
        if getattr(enc, 'type', '').startswith('image'):
            url = getattr(enc, 'href', '') or getattr(enc, 'url', '')
            if url.startswith('http'):
                return url
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
        if not isinstance(art, dict):
            continue
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
# 카드 HTML 생성
# ──────────────────────────────────────────
def build_card_html(article):
    aid     = str(article.get('id', ''))
    href    = article.get('link', '')
    title   = article.get('title', '').replace('"', '&quot;')
    summary = article.get('summary', '').replace('"', '&quot;')
    source  = article.get('source', '').replace('"', '&quot;')
    domain  = article.get('source_domain', '')
    thumb   = article.get('thumbnail', '')
    pub     = article.get('pub_date', '')[:16]

    # 썸네일
    if thumb:
        thumb_html = (
            '<div class="thumb">'
            '<img src="' + thumb + '" alt="" onerror="this.parentElement.innerHTML=\'<span class=no-img>📰</span>\'">'
            '</div>'
        )
    else:
        thumb_html = '<div class="thumb no-img">📰</div>'

    # 파비콘 ← 핵심 수정: <img> 태그로 올바르게 생성
    if domain:
        favicon_html = (
            '![image](https://www.google.com/s2/favicons?domain=)'
        )
    else:
        favicon_html = ''

    html = (
        '<a class="card" href="' + href + '" target="_blank" '
        'data-id="' + aid + '" onclick="markRead(this)">'
        + thumb_html +
        '<div class="card-body">'
        '<div class="meta">'
        + favicon_html +
        '<span class="src">' + source + '</span>'
        '<span class="new-badge">NEW</span>'
        '</div>'
        '<h3>' + article.get('title', '') + '</h3>'
        '<p>' + article.get('summary', '') + '</p>'
        '<div class="footer">'
        '<span class="date">' + pub + '</span>'
        '<span class="read-label">✓ 읽음</span>'
        '</div>'
        '</div>'
        '</a>'
    )
    return html

# ──────────────────────────────────────────
# HTML 생성
# ──────────────────────────────────────────
def build_html(articles):
    cats     = ['IT/테크', '경제/주식', '국제뉴스', 'AI', '스포츠']
    now_str  = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    tab_cards = {c: [] for c in cats}
    tab_cards['__archive__'] = []
    cutoff_recent = datetime.now(timezone.utc) - timedelta(days=2)

    for art in sorted(
        [a for a in articles.values() if isinstance(a, dict)],
        key=lambda x: x.get('pub_date', ''),
        reverse=True
    ):
        c    = art.get('cat', '')
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
    for i, c in enumerate(cats):
        active = ' active' if i == 0 else ''
        cnt    = len(tab_cards[c])
        tab_buttons += (
            '<button class="tab-btn' + active + '" onclick="switchTab(\'' + c + '\', this)">'
            + c +
            ' <span class="badge">' + str(cnt) + '</span>'
            '</button>'
        )
    tab_buttons += (
        '<button class="tab-btn" onclick="switchTab(\'__archive__\', this)">'
        '📁 보관함'
        ' <span class="badge">' + str(len(tab_cards['__archive__'])) + '</span>'
        '</button>'
    )

    # 탭 컨텐츠
    tab_contents = ''
    for i, c in enumerate(cats):
        display    = 'block' if i == 0 else 'none'
        cards_html = ''.join(tab_cards[c]) if tab_cards[c] else '<p class="empty">뉴스가 없습니다.</p>'
        tab_contents += (
            '<div class="tab-panel" id="tab-' + c + '" style="display:' + display + '">'
            '<div class="grid">' + cards_html + '</div>'
            '</div>'
        )
    archive_html = ''.join(tab_cards['__archive__']) if tab_cards['__archive__'] else '<p class="empty">보관된 뉴스가 없습니다.</p>'
    tab_contents += (
        '<div class="tab-panel" id="tab-__archive__" style="display:none">'
        '<div class="grid">' + archive_html + '</div>'
        '</div>'
    )

    html = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>My News Dashboard</title>
<style>
:root{--bg:#0f1117;--card:#1a1d27;--accent:#4f8ef7;--text:#e8eaf0;--sub:#8b8fa8;--border:#2a2d3a}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;min-height:100vh}
header{padding:18px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
header h1{font-size:1.2rem;color:var(--accent)}
header .upd{font-size:.75rem;color:var(--sub)}
.search-wrap{padding:12px 24px}
.search-wrap input{width:100%;padding:9px 14px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:.9rem;outline:none}
.search-wrap input:focus{border-color:var(--accent)}
.tabs{display:flex;gap:6px;padding:0 24px 12px;flex-wrap:wrap}
.tab-btn{background:var(--card);border:1px solid var(--border);color:var(--sub);padding:7px 14px;border-radius:20px;cursor:pointer;font-size:.85rem;transition:.2s}
.tab-btn.active,.tab-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.badge{background:#ff4757;color:#fff;border-radius:10px;padding:1px 6px;font-size:.72rem;margin-left:4px}
.tab-btn.active .badge{background:rgba(255,255,255,.3)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;padding:0 24px 32px}
.card{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;text-decoration:none;color:inherit;transition:.2s;cursor:pointer}
.card:hover{border-color:var(--accent);transform:translateY(-2px)}
.card.read{opacity:.42}
.thumb{width:100%;height:160px;overflow:hidden;background:#222}
.thumb img{width:100%;height:100%;object-fit:cover}
.no-img{display:flex;align-items:center;justify-content:center;font-size:2rem;color:var(--sub)}
.card-body{padding:14px;display:flex;flex-direction:column;gap:8px;flex:1}
.meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.favicon{width:14px;height:14px;vertical-align:middle}
.src{font-size:.78rem;color:var(--accent);font-weight:600}
.new-badge{background:#ff4757;color:#fff;font-size:.68rem;padding:2px 6px;border-radius:4px;display:none}
.card:not(.read) .new-badge{display:inline}
.card h3{font-size:.92rem;line-height:1.4;color:var(--text)}
.card p{font-size:.8rem;color:var(--sub);line-height:1.5;flex:1}
.footer{display:flex;align-items:center;justify-content:space-between;margin-top:4px}
.date{font-size:.73rem;color:var(--sub)}
.read-label{font-size:.73rem;color:#4caf50;display:none}
.card.read .read-label{display:inline}
.empty{padding:40px 24px;color:var(--sub);text-align:center}
#searchPanel{display:none;padding:0 24px 32px}
#searchPanel .grid{padding:0}
</style>
</head>
<body>
<header>
  <h1>📰 My News Dashboard</h1>
  <span class="upd">업데이트: """ + now_str + """</span>
</header>
<div class="search-wrap">
  <input type="text" id="searchBox" placeholder="🔍 뉴스 검색..." oninput="doSearch(this.value)">
</div>
<div class="tabs" id="tabBar">
""" + tab_buttons + """
</div>
<div id="tabContents">
""" + tab_contents + """
</div>
<div id="searchPanel"><div class="grid" id="searchGrid"></div></div>
<script>
const READ_KEY = 'news_read_ids';
function getReadSet(){
  try{ return new Set(JSON.parse(localStorage.getItem(READ_KEY)||'[]')); }
  catch(e){ return new Set(); }
}
function saveReadSet(s){
  localStorage.setItem(READ_KEY, JSON.stringify([...s]));
}
function applyReadState(){
  const s = getReadSet();
  document.querySelectorAll('.card[data-id]').forEach(card=>{
    if(s.has(card.dataset.id)) card.classList.add('read');
  });
  updateBadges();
}
function markRead(el){
  const s = getReadSet();
  s.add(el.dataset.id);
  saveReadSet(s);
  el.classList.add('read');
  updateBadges();
}
function updateBadges(){
  const s = getReadSet();
  document.querySelectorAll('.tab-btn').forEach(btn=>{
    const tabId = btn.getAttribute('onclick').match(/'([^']+)'/)[1];
    const panel = document.getElementById('tab-'+tabId);
    if(!panel) return;
    const total   = panel.querySelectorAll('.card').length;
    const readCnt = [...panel.querySelectorAll('.card')].filter(c=>s.has(c.dataset.id)).length;
    const unread  = total - readCnt;
    const badge   = btn.querySelector('.badge');
    if(badge) badge.textContent = unread;
  });
}
function switchTab(id, btn){
  document.getElementById('searchBox').value = '';
  document.getElementById('searchPanel').style.display = 'none';
  document.getElementById('tabContents').style.display = 'block';
  document.getElementById('tabBar').style.display = 'flex';
  document.querySelectorAll('.tab-panel').forEach(p=>p.style.display='none');
  const panel = document.getElementById('tab-'+id);
  if(panel) panel.style.display = 'block';
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
}
function doSearch(q){
  const tabBar      = document.getElementById('tabBar');
  const tabContents = document.getElementById('tabContents');
  const searchPanel = document.getElementById('searchPanel');
  const grid        = document.getElementById('searchGrid');
  q = q.trim().toLowerCase();
  if(!q){
    searchPanel.style.display = 'none';
    tabContents.style.display = 'block';
    tabBar.style.display      = 'flex';
    return;
  }
  tabContents.style.display = 'none';
  tabBar.style.display      = 'none';
  searchPanel.style.display = 'block';
  const allCards = [...document.querySelectorAll('#tabContents .card')];
  const matched  = allCards.filter(c=>{
    const h3 = c.querySelector('h3');
    const p  = c.querySelector('p');
    return (h3&&h3.textContent.toLowerCase().includes(q))||(p&&p.textContent.toLowerCase().includes(q));
  });
  grid.innerHTML = matched.length
    ? matched.map(c=>c.outerHTML).join('')
    : '<p class="empty">검색 결과가 없습니다.</p>';
  applyReadState();
}
applyReadState();
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
