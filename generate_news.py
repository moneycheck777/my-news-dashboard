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
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml",  "source": "BBC Tech",    "cat": "IT/테크"},
    {"url": "https://feeds.wired.com/wired/index",               "source": "Wired",       "cat": "IT/테크"},
    {"url": "https://techcrunch.com/feed/",                      "source": "TechCrunch",  "cat": "IT/테크"},
    {"url": "https://feeds.feedburner.com/zdkorea",              "source": "ZDNet Korea", "cat": "IT/테크"},
    {"url": "https://bloter.net/feed",                           "source": "Bloter",      "cat": "IT/테크"},
    # 경제/주식
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",        "source": "BBC Business",     "cat": "경제/주식"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",        "source": "Reuters Business", "cat": "경제/주식"},
    {"url": "https://feeds.marketwatch.com/marketwatch/topstories/", "source": "MarketWatch",      "cat": "경제/주식"},
    # 국제뉴스
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",           "source": "BBC World",   "cat": "국제뉴스"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml","source": "NYT World",  "cat": "국제뉴스"},
    {"url": "https://feeds.reuters.com/reuters/topNews",             "source": "Reuters",     "cat": "국제뉴스"},
    {"url": "https://www.yonhapnewstv.co.kr/category/news/headline/feed/", "source": "연합뉴스TV", "cat": "국제뉴스"},
    {"url": "https://www.chosun.com/arc/outboundfeeds/rss/",         "source": "조선일보",    "cat": "국제뉴스"},
    # AI
    {"url": "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en",
                                                                     "source": "Google News AI", "cat": "AI"},
    {"url": "https://www.theverge.com/rss/index.xml",                "source": "The Verge",      "cat": "AI"},
    # 스포츠
    {"url": "https://feeds.bbci.co.uk/sport/rss.xml",                "source": "BBC Sport",   "cat": "스포츠"},
    {"url": "https://www.espn.com/espn/rss/news",                    "source": "ESPN",        "cat": "스포츠"},
]

CATS = ["IT/테크", "경제/주식", "국제뉴스", "AI", "스포츠"]

# ──────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────
def make_id(link):
    return hashlib.md5(link.encode()).hexdigest()[:12]

def parse_pub_date(entry):
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()

def esc(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

# ──────────────────────────────────────────
# 썸네일 추출
# ──────────────────────────────────────────
class ImgParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.src = None
    def handle_starttag(self, tag, attrs):
        if tag == "img" and not self.src:
            for k, v in attrs:
                if k == "src" and v and v.startswith("http"):
                    self.src = v

def extract_thumbnail(entry):
    media = getattr(entry, "media_content", None)
    if media and isinstance(media, list):
        for m in media:
            url = m.get("url", "")
            if url.startswith("http"):
                return url
    thumb = getattr(entry, "media_thumbnail", None)
    if thumb and isinstance(thumb, list):
        url = thumb[0].get("url", "")
        if url.startswith("http"):
            return url
    for enc in getattr(entry, "enclosures", []):
        if getattr(enc, "type", "").startswith("image"):
            url = getattr(enc, "href", "") or getattr(enc, "url", "")
            if url.startswith("http"):
                return url
    summary = getattr(entry, "summary", "") or ""
    p = ImgParser()
    p.feed(summary)
    if p.src:
        return p.src
    return ""

# ──────────────────────────────────────────
# RSS 수집
# ──────────────────────────────────────────
def fetch_all():
    articles = {}
    for feed_info in RSS_FEEDS:
        try:
            d = feedparser.parse(
                feed_info["url"],
                agent=UA,
                request_headers={"Accept-Language": "ko,en;q=0.9"},
            )
            for entry in d.entries[:15]:
                link = getattr(entry, "link", "")
                if not link:
                    continue
                aid = make_id(link)
                if aid in articles:
                    continue
                title   = getattr(entry, "title", "").strip()
                summary = re.sub(r"<[^>]+>", "", getattr(entry, "summary", "") or "").strip()[:200]
                domain  = urlparse(link).netloc.replace("www.", "")
                articles[aid] = {
                    "id":            aid,
                    "title":         title,
                    "link":          link,
                    "summary":       summary,
                    "source":        feed_info["source"],
                    "source_domain": domain,
                    "cat":           feed_info["cat"],
                    "pub_date":      parse_pub_date(entry),
                    "thumbnail":     extract_thumbnail(entry),
                }
        except Exception as e:
            print(f"[WARN] {feed_info['source']} 수집 실패: {e}")
    return articles

# ──────────────────────────────────────────
# 아카이브 관리
# ──────────────────────────────────────────
def load_archive():
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_archive(data):
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def merge_archive(old, new):
    merged = {**old, **new}
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_DAYS)
    result = {}
    for aid, art in merged.items():
        if not isinstance(art, dict):
            print(f"[SKIP] 잘못된 데이터 형식 제거: {aid}")
            continue
        try:
            dt = datetime.fromisoformat(art["pub_date"])
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
    aid     = str(article.get("id", ""))
    href    = article.get("link", "").replace("'", "\\'")
    title   = esc(article.get("title", ""))
    summary = esc(article.get("summary", ""))
    source  = esc(article.get("source", ""))
    domain  = article.get("source_domain", "")
    thumb   = article.get("thumbnail", "")
    pub     = article.get("pub_date", "")[:16].replace("T", " ")

    thumb_html = (
        '<div class="card-thumb"><img src="' + thumb + '" onerror="this.parentElement.innerHTML=\'<span>📰</span>\'"></div>'
        if thumb else
        '<div class="card-thumb no-thumb"><span>📰</span></div>'
    )
    favicon_html = (
        '![image](https://www.google.com/s2/favicons?domain=)'
        if domain else ""
    )
    return (
        '<article class="card" data-id="' + aid + '" onclick="openArticle(\'' + aid + "','" + href + '\')">'
        + thumb_html
        + '<div class="card-body">'
        + '<div class="card-meta">' + favicon_html
        + '<span class="source-name">' + source + '</span>'
        + '<span class="new-badge">NEW</span>'
        + '</div>'
        + '<h3 class="card-title">' + title + '</h3>'
        + '<p class="card-summary">' + summary + '</p>'
        + '<div class="card-footer">'
        + '<span class="pub-date">' + pub + '</span>'
        + '<span class="read-check">✓ 읽음</span>'
        + '</div></div></article>'
    )

# ──────────────────────────────────────────
# HTML 생성
# ──────────────────────────────────────────
def build_html(articles):
    now_str    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cutoff_48h = datetime.now(timezone.utc) - timedelta(hours=48)

    tab_cards = {c: [] for c in CATS}
    tab_cards["__archive__"] = []

    sorted_arts = sorted(
        [a for a in articles.values() if isinstance(a, dict)],
        key=lambda x: x.get("pub_date", ""),
        reverse=True,
    )
    for art in sorted_arts:
        c    = art.get("cat", "")
        card = build_card_html(art)
        if c in tab_cards:
            tab_cards[c].append(card)
        try:
            dt = datetime.fromisoformat(art["pub_date"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff_48h:
                tab_cards["__archive__"].append(card)
        except Exception:
            pass

    # ── 탭 버튼
    tab_btns = ""
    for i, c in enumerate(CATS):
        active = " active" if i == 0 else ""
        tab_btns += (
            '<button class="tab-btn' + active + '" onclick="switchTab(\'' + c + '\',this)">'
            + c
            + '<span class="tab-badge" id="badge-' + c + '">0</span>'
            + '</button>'
        )
    tab_btns += (
        '<button class="tab-btn" onclick="switchTab(\'__archive__\',this)">'
        '📁 보관함'
        '<span class="tab-badge" id="badge-__archive__">' + str(len(tab_cards["__archive__"])) + '</span>'
        '</button>'
    )

    # ── 탭 컨텐츠
    tab_contents = ""
    for i, c in enumerate(CATS):
        display = "block" if i == 0 else "none"
        inner   = "".join(tab_cards[c]) if tab_cards[c] else '<p class="empty">뉴스가 없습니다.</p>'
        tab_contents += (
            '<div class="tab-content" id="tab-' + c + '" style="display:' + display + '">'
            + '<div class="cards-grid">' + inner + '</div>'
            + '</div>'
        )
    arch_inner = "".join(tab_cards["__archive__"]) if tab_cards["__archive__"] else '<p class="empty">보관된 뉴스가 없습니다.</p>'
    tab_contents += (
        '<div class="tab-content" id="tab-__archive__" style="display:none">'
        + '<div class="cards-grid">' + arch_inner + '</div>'
        + '</div>'
    )

    # ── JS용 전체 기사 목록 (검색)
    all_json = json.dumps(
        [{"id": a.get("id",""), "title": a.get("title",""), "summary": a.get("summary",""),
          "source": a.get("source",""), "cat": a.get("cat",""), "link": a.get("link","")}
         for a in sorted_arts],
        ensure_ascii=False,
    )

    return (
"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>📡 My News Dashboard</title>
<style>
:root{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#22263a;
  --accent:#4f8ef7;--accent2:#7c5ef7;
  --text:#e8eaf0;--text2:#9da3b4;
  --red:#f74f4f;--green:#4fbd7c;
  --radius:12px;--shadow:0 4px 24px rgba(0,0,0,.4);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;min-height:100vh}
header{
  background:linear-gradient(135deg,var(--surface),var(--surface2));
  border-bottom:1px solid rgba(79,142,247,.2);
  padding:18px 24px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;
}
header h1{font-size:1.4rem;font-weight:700;
  background:linear-gradient(90deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header-meta{margin-left:auto;color:var(--text2);font-size:.8rem}
.countdown{color:var(--accent);font-weight:700}
.search-wrap{width:100%;margin-top:10px}
#searchInput{
  width:100%;padding:10px 18px;
  background:var(--surface2);border:1px solid rgba(255,255,255,.1);
  border-radius:24px;color:var(--text);font-size:.95rem;outline:none;transition:border .2s;
}
#searchInput:focus{border-color:var(--accent)}
#searchInput::placeholder{color:var(--text2)}
.tabs{
  display:flex;gap:6px;padding:16px 24px 0;
  overflow-x:auto;border-bottom:1px solid rgba(255,255,255,.06);
}
.tab-btn{
  padding:8px 18px;border-radius:24px 24px 0 0;border:none;
  background:var(--surface);color:var(--text2);cursor:pointer;
  font-size:.85rem;font-weight:600;white-space:nowrap;
  display:flex;align-items:center;gap:6px;transition:background .2s,color .2s;
}
.tab-btn:hover{background:var(--surface2);color:var(--text)}
.tab-btn.active{background:var(--accent);color:#fff}
.tab-badge{
  background:rgba(255,255,255,.25);color:#fff;
  border-radius:10px;padding:1px 7px;font-size:.72rem;font-weight:700;min-width:22px;text-align:center;
}
.tab-btn.active .tab-badge{background:rgba(0,0,0,.25)}
.tab-content{padding:20px 24px}
.cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.empty{color:var(--text2);text-align:center;padding:40px}
.card{
  background:var(--surface);border-radius:var(--radius);overflow:hidden;cursor:pointer;
  box-shadow:var(--shadow);transition:transform .18s,box-shadow .18s,opacity .2s;
  border:1px solid rgba(255,255,255,.06);
}
.card:hover{transform:translateY(-3px);box-shadow:0 8px 32px rgba(0,0,0,.5)}
.card.read{opacity:.42}
.card-thumb{height:160px;overflow:hidden;background:var(--surface2);
  display:flex;align-items:center;justify-content:center}
.card-thumb img{width:100%;height:100%;object-fit:cover}
.card-thumb.no-thumb span{font-size:2.5rem}
.card-body{padding:14px}
.card-meta{display:flex;align-items:center;gap:6px;margin-bottom:8px;flex-wrap:wrap}
.favicon{width:14px;height:14px;border-radius:3px}
.source-name{font-size:.75rem;color:var(--text2);font-weight:600}
.new-badge{
  background:var(--red);color:#fff;font-size:.65rem;font-weight:700;
  padding:2px 7px;border-radius:10px;margin-left:auto;
}
.card.read .new-badge{display:none}
.card-title{font-size:.95rem;font-weight:700;line-height:1.4;margin-bottom:6px}
.card-summary{font-size:.8rem;color:var(--text2);line-height:1.5;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card-footer{display:flex;justify-content:space-between;align-items:center;margin-top:10px}
.pub-date{font-size:.72rem;color:var(--text2)}
.read-check{font-size:.72rem;color:var(--green);opacity:0;transition:opacity .2s}
.card.read .read-check{opacity:1}
#noResult{display:none;text-align:center;padding:40px;color:var(--text2)}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--surface2);border-radius:3px}
</style>
</head>
<body>

<header>
  <h1>📡 My News Dashboard</h1>
  <div class="header-meta">
    마지막 갱신: """ + now_str + """ &nbsp;|&nbsp;
    다음 갱신까지: <span class="countdown" id="countdown">--:--</span>
  </div>
  <div class="search-wrap">
    <input id="searchInput" type="text"
      placeholder="🔍 제목, 요약, 출처 검색..."
      oninput="doSearch(this.value)">
  </div>
</header>

<div class="tabs" id="tabBar">"""
+ tab_btns +
"""</div>

<div id="mainContent">"""
+ tab_contents +
"""</div>
<div id="noResult">검색 결과가 없습니다.</div>

<script>
const ALL = """ + all_json + """;
const READ_KEY = 'news_read_ids';

function getRS(){
  try{ return new Set(JSON.parse(localStorage.getItem(READ_KEY)||'[]')); }
  catch(e){ return new Set(); }
}
function saveRS(s){ localStorage.setItem(READ_KEY, JSON.stringify([...s])); }

function applyRead(){
  const rs = getRS();
  document.querySelectorAll('.card').forEach(c => {
    c.classList.toggle('read', rs.has(c.dataset.id));
  });
  updateBadges();
}

function openArticle(aid, href){
  const rs = getRS();
  rs.add(aid);
  saveRS(rs);
  applyRead();
  window.open(href, '_blank');
}

function updateBadges(){
  const rs = getRS();
  document.querySelectorAll('.tab-content').forEach(tc => {
    const id    = tc.id.replace('tab-', '');
    const badge = document.getElementById('badge-' + id);
    if(!badge) return;
    const unread = [...tc.querySelectorAll('.card')].filter(c => !rs.has(c.dataset.id)).length;
    badge.textContent    = unread;
    badge.style.display  = unread > 0 ? 'inline-block' : 'none';
  });
}

function switchTab(id, btn){
  if(document.getElementById('searchInput').value.trim()) return;
  document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const sp = document.getElementById('searchPanel');
  if(sp) sp.style.display = 'none';
  document.getElementById('tab-' + id).style.display = 'block';
  btn.classList.add('active');
}

function doSearch(q){
  const query = q.trim().toLowerCase();
  const nr    = document.getElementById('noResult');
  const tb    = document.getElementById('tabBar');
  const mc    = document.getElementById('mainContent');

  if(!query){
    tb.style.display = 'flex';
    const sp = document.getElementById('searchPanel');
    if(sp) sp.style.display = 'none';
    document.querySelectorAll('.tab-content').forEach((t,i) =>
      t.style.display = i===0 ? 'block' : 'none');
    document.querySelectorAll('.tab-btn').forEach((b,i) =>
      b.classList.toggle('active', i===0));
    nr.style.display = 'none';
    applyRead();
    return;
  }

  tb.style.display = 'none';
  document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');

  let sp = document.getElementById('searchPanel');
  if(!sp){ sp = document.createElement('div'); sp.id = 'searchPanel'; mc.appendChild(sp); }
  sp.style.display = 'block';
  sp.className = 'tab-content';

  const rs      = getRS();
  const matched = ALL.filter(a =>
    (a.title + ' ' + a.summary + ' ' + a.source).toLowerCase().includes(query)
  );

  if(!matched.length){ sp.innerHTML = ''; nr.style.display = 'block'; return; }
  nr.style.display = 'none';

  let grid = '<div class="cards-grid">';
  matched.forEach(a => {
    const rc = rs.has(a.id) ? ' read' : '';
    const nb = rc ? '' : '<span class="new-badge">NEW</span>';
    const safeHref = a.link.replace(/'/g, "&apos;");
    grid += `<article class="card${rc}" data-id="${a.id}" onclick="openArticle('${a.id}','${safeHref}')">`
      + '<div class="card-body">'
      + `<div class="card-meta"><span class="source-name">${a.source}</span>${nb}</div>`
      + `<h3 class="card-title">${a.title}</h3>`
      + `<p class="card-summary">${a.summary}</p>`
      + `<div class="card-footer"><span class="pub-date">${a.cat}</span>`
      + '<span class="read-check">✓ 읽음</span></div>'
      + '</div></article>';
  });
  grid += '</div>';
  sp.innerHTML = grid;
}

function tick(){
  const now  = new Date();
  const next = new Date(now);
  next.setUTCMinutes(0,0,0);
  next.setUTCHours(next.getUTCHours() + 1);
  const d = Math.max(0, Math.floor((next - now) / 1000));
  document.getElementById('countdown').textContent =
    String(Math.floor(d/60)).padStart(2,'0') + ':' + String(d%60).padStart(2,'0');
}

applyRead();
tick();
setInterval(tick, 1000);
</script>
</body>
</html>"""
    )

# ──────────────────────────────────────────
# 메인
# ──────────────────────────────────────────
if __name__ == "__main__":
    print("뉴스 수집 중...")
    new_articles = fetch_all()
    print(f"  수집: {len(new_articles)}건")

    archive = load_archive()
    merged  = merge_archive(archive, new_articles)
    save_archive(merged)
    print(f"  아카이브: {len(merged)}건")

    html = build_html(merged)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  '{OUTPUT_FILE}' 생성 완료!")
