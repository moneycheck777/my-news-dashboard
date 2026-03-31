import feedparser
import json
import os
import hashlib
from datetime import datetime, timezone

RSS_FEEDS = [
    {"url": "https://feeds.wired.com/wired/index",                          "category": "IT/테크",   "source": "Wired"},
    {"url": "https://techcrunch.com/feed/",                                 "category": "IT/테크",   "source": "TechCrunch"},
    {"url": "http://feeds.bbci.co.uk/news/technology/rss.xml",              "category": "IT/테크",   "source": "BBC Tech"},
    {"url": "https://www.theverge.com/rss/index.xml",                       "category": "IT/테크",   "source": "The Verge"},
    {"url": "https://feeds.bloomberg.com/markets/news.rss",                 "category": "경제/주식", "source": "Bloomberg"},
    {"url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",         "category": "경제/주식", "source": "CNBC"},
    {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",                "category": "경제/주식", "source": "WSJ Markets"},
    {"url": "http://feeds.bbci.co.uk/news/world/rss.xml",                   "category": "국제뉴스",  "source": "BBC World"},
    {"url": "https://feeds.reuters.com/reuters/worldNews",                  "category": "국제뉴스",  "source": "Reuters"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",       "category": "국제뉴스",  "source": "NYT World"},
    {"url": "https://feeds.feedburner.com/venturebeat/SZYF",                "category": "AI",        "source": "VentureBeat"},
    {"url": "https://www.artificialintelligence-news.com/feed/",            "category": "AI",        "source": "AI News"},
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/","category": "AI",        "source": "TC AI"},
    {"url": "https://www.espn.com/espn/rss/news",                           "category": "스포츠",    "source": "ESPN"},
    {"url": "http://feeds.bbci.co.uk/sport/rss.xml",                        "category": "스포츠",    "source": "BBC Sport"},
    {"url": "https://www.skysports.com/rss/12040",                          "category": "스포츠",    "source": "Sky Sports"},
]

CATEGORIES = ["IT/테크", "경제/주식", "국제뉴스", "AI", "스포츠"]
MAX_PER_CATEGORY = 60
ARCHIVE_FILE = "news_archive.json"

SOURCE_DOMAINS = {
    "Wired": "wired.com", "TechCrunch": "techcrunch.com",
    "BBC Tech": "bbc.com", "The Verge": "theverge.com",
    "Bloomberg": "bloomberg.com", "CNBC": "cnbc.com", "WSJ Markets": "wsj.com",
    "BBC World": "bbc.com", "Reuters": "reuters.com", "NYT World": "nytimes.com",
    "VentureBeat": "venturebeat.com", "AI News": "artificialintelligence-news.com",
    "TC AI": "techcrunch.com", "ESPN": "espn.com",
    "BBC Sport": "bbc.com", "Sky Sports": "skysports.com",
}


# ────────────────────── 아카이브 ──────────────────────────────────────────

def get_hash(entry):
    key = entry.get("link") or entry.get("title") or ""
    return hashlib.md5(key.encode()).hexdigest()

def load_archive():
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_archive(data):
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_all():
    archive = load_archive()
    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            cat, src = feed_info["category"], feed_info["source"]
            if cat not in archive:
                archive[cat] = {}
            for entry in feed.entries[:30]:
                h = get_hash(entry)
                if h not in archive[cat]:
                    published = getattr(entry, "published", "") or getattr(entry, "updated", "")
                    archive[cat][h] = {
                        "title":      entry.get("title", ""),
                        "link":       entry.get("link", ""),
                        "summary":    entry.get("summary", "")[:200],
                        "published":  published,
                        "source":     src,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }
        except Exception as e:
            print(f"[ERROR] {feed_info['source']}: {e}")

    for cat in archive:
        items = sorted(archive[cat].items(),
                       key=lambda x: x[1].get("fetched_at", ""), reverse=True)
        archive[cat] = dict(items[:MAX_PER_CATEGORY])

    save_archive(archive)
    return archive


# ────────────────────── 파비콘 ────────────────────────────────────────────

def get_favicon_html(source_name, domain):
    return (
        '![image](https://www.google.com/s2/favicons?domain=)'
        + source_name
    )


# ────────────────────── 카드 ──────────────────────────────────────────────

def build_card(h, item):
    source     = item.get("source", "")
    domain     = SOURCE_DOMAINS.get(source, "google.com")
    favicon    = get_favicon_html(source, domain)
    link       = item.get("link", "")
    summary    = item.get("summary", "").replace("<", "&lt;").replace(">", "&gt;")
    date       = item.get("published", item.get("fetched_at", ""))[:16]
    title_disp = item.get("title", "").replace("<", "&lt;").replace(">", "&gt;")
    safe_title  = item.get("title", "").replace("'", "\\'").replace('"', ' ')
    safe_source = source.replace("'", "\\'")
    safe_sum    = item.get("summary", "")[:100].replace("'", "\\'").replace('"', ' ')
    return (
        f'<a class="card" data-id="{h}" href="{link}" target="_blank" '
        f'onclick="markRead(\'{h}\');applyReadState()">'
        f'<div class="card-top">'
        f'<span class="card-source">{favicon}</span>'
        f'<div style="display:flex;gap:6px;align-items:center">'
        f'<span class="badge-new">NEW</span>'
        f'<button class="bookmark-btn" onclick="event.preventDefault();'
        f'toggleBM(\'{h}\',\'{safe_title}\',\'{link}\',\'{safe_source}\',\'{safe_sum}\',\'{date}\')">'
        f'&#9734; 저장</button>'
        f'</div></div>'
        f'<div class="card-title">{title_disp}</div>'
        f'<div class="card-summary">{summary}</div>'
        f'<div class="card-date">{date}</div>'
        f'</a>'
    )


# ────────────────────── HTML 생성 ─────────────────────────────────────────

def build_html(archive):
    now_str    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cat_counts = {cat: len(archive.get(cat, {})) for cat in CATEGORIES}

    CSS = """
:root{--bg:#0f172a;--surface:#1e293b;--surface2:#273449;--accent:#3b82f6;
      --accent2:#ef4444;--text:#e2e8f0;--muted:#94a3b8;--border:#334155;--radius:12px;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;min-height:100vh;}
header{background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);
       border-bottom:1px solid var(--border);padding:14px 24px;
       display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;}
header h1{font-size:1.3rem;font-weight:700;color:#fff;}
.header-right{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.upd{font-size:.78rem;color:var(--muted);}
.next-reset{font-size:.75rem;color:#64748b;}
.btn-refresh{background:var(--accent);border:none;color:#fff;padding:5px 13px;
             border-radius:8px;cursor:pointer;font-size:.8rem;transition:background .2s;}
.btn-refresh:hover{background:#2563eb;}
.btn-clear{background:var(--accent2);border:none;color:#fff;padding:5px 13px;
           border-radius:8px;cursor:pointer;font-size:.8rem;transition:background .2s;}
.btn-clear:hover{background:#dc2626;}
.search-bar{background:var(--surface);padding:12px 24px;border-bottom:1px solid var(--border);}
.search-bar input{width:100%;background:var(--surface2);border:1px solid var(--border);
  border-radius:10px;padding:10px 16px 10px 40px;color:var(--text);font-size:.95rem;outline:none;}
.search-bar input:focus{border-color:var(--accent);}
.search-wrap{position:relative;}
.search-wrap::before{content:'🔍';position:absolute;left:12px;top:50%;
                     transform:translateY(-50%);font-size:.9rem;}
.tabs{display:flex;gap:6px;padding:14px 24px;background:var(--surface);
      flex-wrap:wrap;border-bottom:1px solid var(--border);}
.tab{padding:7px 16px;border-radius:20px;cursor:pointer;font-size:.85rem;font-weight:600;
     border:none;background:var(--surface2);color:var(--muted);transition:all .2s;
     display:flex;align-items:center;gap:6px;}
.tab.active{background:var(--accent);color:#fff;}
.tab:hover:not(.active){background:var(--border);color:var(--text);}
.tab .badge{background:rgba(255,255,255,.2);color:#fff;font-size:.7rem;
            padding:1px 7px;border-radius:10px;font-weight:700;}
.tab:not(.active) .badge{background:var(--border);color:var(--muted);}
#mainContent{padding:20px 24px;}
.cat-panel{display:none;}
.cat-panel.active{display:block;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
      padding:16px;display:flex;flex-direction:column;gap:8px;
      transition:transform .15s,border-color .15s;cursor:pointer;text-decoration:none;color:inherit;}
.card:hover{transform:translateY(-2px);border-color:var(--accent);}
.card.read{opacity:.45;}
.card-top{display:flex;align-items:center;justify-content:space-between;}
.card-source{font-size:.75rem;color:var(--muted);display:flex;align-items:center;}
.badge-new{background:var(--accent2);color:#fff;font-size:.65rem;
           padding:2px 7px;border-radius:6px;font-weight:700;}
.card-title{font-size:.92rem;font-weight:600;line-height:1.4;color:var(--text);}
.card-summary{font-size:.8rem;color:var(--muted);line-height:1.5;}
.card-date{font-size:.72rem;color:#475569;margin-top:auto;}
#searchPanel{display:none;padding:20px 24px;}
#searchPanel h3{margin-bottom:14px;color:var(--muted);font-size:.9rem;}
.bookmark-btn{background:none;border:1px solid var(--border);color:var(--muted);
              border-radius:6px;padding:2px 8px;cursor:pointer;font-size:.75rem;transition:all .2s;}
.bookmark-btn:hover,.bookmark-btn.saved{background:#f59e0b;border-color:#f59e0b;color:#fff;}
#bookmarkPanel{display:none;padding:20px 24px;}
#bookmarkPanel h3{margin-bottom:14px;color:var(--muted);font-size:.9rem;}
"""

    JS = r"""
const READ_KEY='news_read_ids', BM_KEY='news_bookmarks';
function getRead(){try{return JSON.parse(localStorage.getItem(READ_KEY)||'[]');}catch{return[];}}
function getBM()  {try{return JSON.parse(localStorage.getItem(BM_KEY)  ||'[]');}catch{return[];}}

function markRead(id){
  const r=getRead();
  if(!r.includes(id)){r.push(id);localStorage.setItem(READ_KEY,JSON.stringify(r));}
}
function toggleBM(id,title,link,source,summary,date){
  let bm=getBM();
  const idx=bm.findIndex(x=>x.id===id);
  if(idx===-1) bm.push({id,title,link,source,summary,date});
  else         bm.splice(idx,1);
  localStorage.setItem(BM_KEY,JSON.stringify(bm));
  applyReadState();renderBookmarks();
}
function applyReadState(){
  const read=getRead(),bm=getBM().map(x=>x.id);
  document.querySelectorAll('.card[data-id]').forEach(card=>{
    const id=card.dataset.id;
    card.classList.toggle('read',read.includes(id));
    const btn=card.querySelector('.bookmark-btn');
    if(btn) btn.classList.toggle('saved',bm.includes(id));
  });
  updateTabBadges();
}
function updateTabBadges(){
  const read=getRead();
  document.querySelectorAll('.tab[data-cat]').forEach(tab=>{
    const cat=tab.dataset.cat, badge=tab.querySelector('.badge');
    if(!badge) return;
    if(cat==='__bookmark__'){badge.textContent=getBM().length;return;}
    const cards=document.querySelectorAll(
      '#panel-'+cat.replace(/\//g,'_')+' .card[data-id]');
    badge.textContent=[...cards].filter(c=>!read.includes(c.dataset.id)).length;
  });
}
function showTab(cat){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.cat-panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('searchPanel').style.display='none';
  document.getElementById('bookmarkPanel').style.display='none';
  document.getElementById('mainContent').style.display='block';
  if(cat==='__bookmark__'){
    document.getElementById('mainContent').style.display='none';
    document.getElementById('bookmarkPanel').style.display='block';
    document.querySelector('.tab[data-cat="__bookmark__"]').classList.add('active');
    renderBookmarks();return;
  }
  const panel=document.getElementById('panel-'+cat.replace(/\//g,'_'));
  if(panel) panel.classList.add('active');
  const tab=document.querySelector('.tab[data-cat="'+cat+'"]');
  if(tab) tab.classList.add('active');
}
function renderBookmarks(){
  const bm=getBM(),read=getRead(),wrap=document.getElementById('bm-grid');
  if(!wrap) return;
  if(!bm.length){
    wrap.innerHTML='<p style="color:var(--muted)">저장된 기사가 없습니다.</p>';return;
  }
  wrap.innerHTML=bm.map(item=>{
    const isRead=read.includes(item.id);
    return `<a class="card${isRead?' read':''}" data-id="${item.id}"
               href="${item.link}" target="_blank"
               onclick="markRead('${item.id}');applyReadState()">
      <div class="card-top">
        <span class="card-source">${item.source}</span>
        <button class="bookmark-btn saved"
          onclick="event.preventDefault();
            toggleBM('${item.id}','${item.title.replace(/'/g,"\\'")}',
            '${item.link}','${item.source}','','${item.date}')">&#9733; 저장됨</button>
      </div>
      <div class="card-title">${item.title}</div>
      <div class="card-summary">${item.summary||''}</div>
      <div class="card-date">${item.date}</div>
    </a>`;
  }).join('');
}

/* ── 검색 ── */
const searchInput=document.getElementById('searchInput');
const searchPanel=document.getElementById('searchPanel');
const searchGrid =document.getElementById('searchGrid');
const searchTitle=document.getElementById('searchTitle');
let allCards=[];
function initAllCards(){
  allCards=[...document.querySelectorAll('#mainContent .card[data-id]')].map(c=>({
    id:c.dataset.id, el:c.cloneNode(true),
    text:(c.querySelector('.card-title')?.textContent||'')+' '
        +(c.querySelector('.card-summary')?.textContent||'')+' '
        +(c.querySelector('.card-source')?.textContent||'')
  }));
}
searchInput.addEventListener('input',()=>{
  const q=searchInput.value.trim().toLowerCase();
  if(!q){
    searchPanel.style.display='none';
    document.getElementById('mainContent').style.display='block';
    document.getElementById('bookmarkPanel').style.display='none';return;
  }
  document.getElementById('mainContent').style.display='none';
  document.getElementById('bookmarkPanel').style.display='none';
  searchPanel.style.display='block';
  const results=allCards.filter(c=>c.text.toLowerCase().includes(q));
  searchTitle.textContent=`검색 결과: "${q}" — ${results.length}건`;
  searchGrid.innerHTML=results.length
    ?results.map(c=>c.el.outerHTML).join('')
    :'<p style="color:var(--muted)">검색 결과가 없습니다.</p>';
  applyReadState();
});

/* ── 읽음 초기화 ── */
function clearReadState(){
  if(!confirm('읽음 상태를 모두 초기화할까요?')) return;
  localStorage.removeItem(READ_KEY);
  location.reload();
}

/* ── 다음 수집 카운트다운 ── */
function updateNextReset(){
  const now=new Date(), next=new Date(now);
  next.setUTCMinutes(0,0,0);
  next.setUTCHours(next.getUTCHours()+1);
  const diffMin=Math.round((next-now)/60000);
  const h=Math.floor(diffMin/60), m=diffMin%60;
  const timeStr=next.toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'});
  const el=document.getElementById('nextReset');
  if(el) el.textContent='⏭️ 다음 수집: '+timeStr+' ('+(h>0?h+'시간 ':'')+m+'분 후)';
}
updateNextReset();
setInterval(updateNextReset, 30000);

/* ── 초기화 ── */
window.addEventListener('DOMContentLoaded',()=>{
  initAllCards();
  applyReadState();
  renderBookmarks();
  showTab('IT/테크');
});
"""

    # ── 패널
    panels_html = ""
    for cat in CATEGORIES:
        panel_id   = "panel-" + cat.replace("/", "_")
        items      = archive.get(cat, {})
        cards_html = "".join(build_card(h, item) for h, item in items.items())
        panels_html += (
            f'<div class="cat-panel" id="{panel_id}">'
            f'<div class="grid">{cards_html}</div>'
            f'</div>'
        )

    # ── 탭
    TAB_COLORS = {
        "IT/테크": "#3b82f6", "경제/주식": "#ef4444",
        "국제뉴스": "#b91c1c", "AI": "#7c3aed", "스포츠": "#059669",
    }
    tabs_html = ""
    for cat in CATEGORIES:
        cnt = cat_counts.get(cat, 0)
        col = TAB_COLORS.get(cat, "#3b82f6")
        tabs_html += (
            f'<button class="tab" data-cat="{cat}" style="--tab-color:{col}" '
            f'onclick="showTab(\'{cat}\')">'
            f'{cat} <span class="badge">{cnt}</span></button>'
        )
    tabs_html += (
        '<button class="tab" data-cat="__bookmark__" '
        'onclick="showTab(\'__bookmark__\')">'
        '🔖 보관함 <span class="badge" id="bm-count">0</span></button>'
    )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>My News Dashboard</title>
<style>{CSS}</style>
</head>
<body>

<header>
  <h1>📰 My News Dashboard</h1>
  <div class="header-right">
    <span class="upd">🕒 업데이트: {now_str}</span>
    <button class="btn-refresh" onclick="location.reload()">🔄 새로고침</button>
    <button class="btn-clear"   onclick="clearReadState()">🗑️ 읽음 초기화</button>
    <span id="nextReset" class="next-reset"></span>
  </div>
</header>

<div class="search-bar">
  <div class="search-wrap">
    <input type="text" id="searchInput" placeholder="뉴스 검색...">
  </div>
</div>

<div class="tabs">{tabs_html}</div>

<div id="mainContent">{panels_html}</div>

<div id="searchPanel">
  <h3 id="searchTitle"></h3>
  <div class="grid" id="searchGrid"></div>
</div>

<div id="bookmarkPanel">
  <h3>🔖 보관함</h3>
  <div class="grid" id="bm-grid"></div>
</div>

<script>{JS}</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html generated.")


if __name__ == "__main__":
    print("Fetching RSS feeds...")
    archive = fetch_all()
    print("Building HTML...")
    build_html(archive)
    print("Done.")
