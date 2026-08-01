# -*- coding: utf-8 -*-
"""
東京 週末イベント 静的サイト生成（日付指定・複数週対応版）
- 全エリアを1回巡回し(collect_all_events)、直近N週分の週末データをJSONとして事前生成
- index.html は静的シェル＋JS。日付を選んで「更新」を押すと該当週のJSONを読み込んで再描画
  （GitHub Pages上の同一オリジンJSONを読むだけなので、ブラウザから直接他サイトを叩くCORS問題を回避）
- サーバー不要。GitHub Actionsが週次で全JSONを再生成してPagesに再公開する。

ローカル確認: python build_site.py --open
"""
import os, json, html, datetime, webbrowser, sys
from scraper import collect_all_events, enrich_images, filter_weekend, upcoming_saturdays, fmt_period, WARDS

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
DATADIR = os.path.join(OUTDIR, "data")
N_WEEKS = 12  # 事前生成する週数（今週末を含め約3ヶ月分）

PALETTE = ["2E86AB","3BAA6F","8E5EA8","1BA6C4","D98324","5B6670",
           "C0392B","2E7D57","6C5CE7","E17055","0984E3","B8891F","16324F","D64550","2C3E50"]
AREA_COLOR = {area: PALETTE[i % len(PALETTE)] for i, area in enumerate(WARDS.keys())}

def build_weekend_json(events, sat, sun):
    return {
        "sat": sat.isoformat(),
        "sun": sun.isoformat(),
        "label": f"{sat.month}/{sat.day}(土)〜{sun.month}/{sun.day}(日)",
        "generated": datetime.datetime.now().isoformat(timespec="minutes"),
        "events": [
            {
                "area": e["area"],
                "name": e["name"],
                "url": e["url"],
                "image": e.get("image"),
                "period": fmt_period(e["period"]),
            }
            for e in events
        ],
    }

INDEX_TEMPLATE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>東京 週末イベント</title>
<style>
:root{{--navy:#16324f;--ink:#1a1a1a;--sub:#666}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic UI",Meiryo,sans-serif;
     background:#f4f6f8;color:var(--ink)}}
header{{background:linear-gradient(135deg,var(--navy),#2e5e8c);color:#fff;padding:16px 16px 14px;
        position:sticky;top:0;z-index:10;box-shadow:0 2px 8px rgba(0,0,0,.15)}}
header h1{{margin:0 0 8px;font-size:19px;line-height:1.4}}
.datebar{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.datebar input[type=date]{{border:none;border-radius:8px;padding:7px 9px;font-size:13.5px;font-family:inherit}}
.datebar button{{border:none;border-radius:8px;padding:7px 14px;font-size:13.5px;font-weight:700;
                 background:#f6d97a;color:#16324f;cursor:pointer}}
.datebar button:active{{transform:scale(.97)}}
.range{{font-size:12.5px;opacity:.9;margin-top:8px}}
.count{{font-size:12px;opacity:.85;margin-top:4px}}
.msg{{font-size:12.5px;background:#fff3cd;color:#7a5c1e;padding:6px 10px;border-radius:8px;margin-top:8px;display:none}}
.chips{{display:flex;gap:6px;overflow-x:auto;padding:10px 12px;background:#fff;
       border-bottom:1px solid #e3e6ea;-webkit-overflow-scrolling:touch}}
.chips::-webkit-scrollbar{{display:none}}
.chip{{flex:0 0 auto;border:1.5px solid var(--c);color:var(--c);background:#fff;border-radius:99px;
      padding:5px 11px;font-size:12.5px;font-weight:600;white-space:nowrap;cursor:pointer}}
.chip.active{{background:var(--c);color:#fff}}
.chip span{{opacity:.75;margin-left:2px}}
main{{padding:12px;max-width:900px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
.card{{display:block;background:#fff;border-radius:12px;overflow:hidden;text-decoration:none;color:var(--ink);
      box-shadow:0 1px 3px rgba(0,0,0,.08);border:1px solid #eceff2;transition:transform .1s}}
.card:active{{transform:scale(.98)}}
.thumb{{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:#e3e6ea}}
.thumb.ph{{display:flex;align-items:center;justify-content:center}}
.thumb.ph span{{color:#fff;font-size:34px;font-weight:800;opacity:.85}}
.card-body{{padding:10px 12px 12px}}
.card-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.badge{{color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px}}
.date{{color:#c0392b;font-size:12px;font-weight:600}}
.card-name{{font-size:14px;line-height:1.45;font-weight:600}}
.empty{{text-align:center;color:var(--sub);padding:40px 0}}
.loading{{text-align:center;color:var(--sub);padding:40px 0}}
footer{{text-align:center;color:var(--sub);font-size:11.5px;padding:20px 16px 30px}}
</style>
</head>
<body>
<header>
  <h1>&#127961; 東京 週末イベント</h1>
  <div class="datebar">
    <input type="date" id="dateInput" value="{default_date}">
    <button id="updateBtn">この週末を表示</button>
  </div>
  <div class="range" id="rangeText"></div>
  <div class="count" id="countText"></div>
  <div class="msg" id="msgBox"></div>
</header>
<nav class="chips" id="chips"></nav>
<main>
  <div class="grid" id="grid"><div class="loading">読み込み中...</div></div>
</main>
<footer>
  自動収集（tokyofes.info 配下の各エリアサイト）。日程・開催有無は必ず各公式ページでご確認ください。<br>
  事前生成データ: 直近{n_weeks}週分（毎週自動更新）／ マニフェスト生成: {generated}
</footer>
<script>
const AREA_COLOR = {area_color_json};
let MANIFEST = null;

function fmtRange(sat, sun){{
  const s = new Date(sat+'T00:00:00'), e = new Date(sun+'T00:00:00');
  const w = ['日','月','火','水','木','金','土'];
  return `${{s.getFullYear()}}/${{s.getMonth()+1}}/${{s.getDate()}}(${{w[s.getDay()]}}) 〜 ${{e.getMonth()+1}}/${{e.getDate()}}(${{w[e.getDay()]}})`;
}}

function isoLocal(d){{
  const y = d.getFullYear(), m = String(d.getMonth()+1).padStart(2,'0'), day = String(d.getDate()).padStart(2,'0');
  return `${{y}}-${{m}}-${{day}}`;
}}

function saturdayOf(dateStr){{
  // dateStr(YYYY-MM-DD)をローカル日付として解釈し、その週の土曜日をローカル日付基準で返す
  // (toISOString()はUTC変換されるため、JST等UTCより進んだTZで日付がズレるバグを避ける)
  const [y,m,d] = dateStr.split('-').map(Number);
  const base = new Date(y, m-1, d);
  const wd = base.getDay();
  const diff = (wd === 6) ? 0 : (wd === 0) ? -1 : (6 - wd);
  const sat = new Date(y, m-1, d + diff);
  return isoLocal(sat);
}}

function showMsg(text){{
  const box = document.getElementById('msgBox');
  if(!text){{ box.style.display='none'; box.textContent=''; return; }}
  box.style.display='block'; box.textContent = text;
}}

function render(data){{
  const grid = document.getElementById('grid');
  const chips = document.getElementById('chips');
  document.getElementById('rangeText').textContent =
    fmtRange(data.sat, data.sun) + ' 開催中・開催';
  const byArea = {{}};
  data.events.forEach(ev => {{ (byArea[ev.area] = byArea[ev.area]||[]).push(ev); }});
  document.getElementById('countText').textContent =
    `該当 ${{data.events.length}} 件 ／ ${{Object.keys(byArea).length}} エリア`;

  let chipHtml = `<button class="chip active" data-area="__all__" style="--c:#16324f">すべて <span>${{data.events.length}}</span></button>`;
  Object.keys(byArea).forEach(area => {{
    const c = AREA_COLOR[area] || '2E86AB';
    chipHtml += `<button class="chip" data-area="${{area}}" style="--c:#${{c}}">${{area}} <span>${{byArea[area].length}}</span></button>`;
  }});
  chips.innerHTML = chipHtml;

  if(data.events.length === 0){{
    grid.innerHTML = '<p class="empty">この週末に開催されるイベントは見つかりませんでした。</p>';
    return;
  }}
  grid.innerHTML = data.events.map(ev => {{
    const c = AREA_COLOR[ev.area] || '2E86AB';
    const thumb = ev.image
      ? `<img class="thumb" src="${{ev.image}}" alt="" loading="lazy" onerror="this.style.display='none'">`
      : `<div class="thumb ph" style="background:#${{c}}"><span>${{(ev.area||'?').slice(0,1)}}</span></div>`;
    return `<a class="card" data-area="${{ev.area}}" href="${{ev.url}}" target="_blank" rel="noopener">
      ${{thumb}}
      <div class="card-body">
        <div class="card-top">
          <span class="badge" style="background:#${{c}}">${{ev.area}}</span>
          <span class="date">${{ev.period}}</span>
        </div>
        <div class="card-name">${{ev.name || ev.url}}</div>
      </div>
    </a>`;
  }}).join('\\n');
}}

document.getElementById('chips').addEventListener('click', function(e){{
  const btn = e.target.closest('.chip');
  if(!btn) return;
  document.querySelectorAll('.chip').forEach(c=>c.classList.remove('active'));
  btn.classList.add('active');
  const area = btn.dataset.area;
  document.querySelectorAll('#grid .card').forEach(card=>{{
    card.style.display = (area === '__all__' || card.dataset.area === area) ? '' : 'none';
  }});
}});

async function loadManifest(){{
  const res = await fetch('data/manifest.json', {{cache:'no-store'}});
  MANIFEST = await res.json();
}}

async function loadWeekend(satIso){{
  showMsg('');
  const entry = MANIFEST.weekends.find(w => w.sat === satIso);
  if(!entry){{
    const first = MANIFEST.weekends[0].sat, last = MANIFEST.weekends[MANIFEST.weekends.length-1].sat;
    showMsg(`この日付(${{satIso}}の週)のデータはまだありません。対応範囲: ${{first}} 〜 ${{last}}（毎週自動生成・拡大されます）`);
    document.getElementById('grid').innerHTML = '';
    document.getElementById('chips').innerHTML = '';
    document.getElementById('rangeText').textContent = '';
    document.getElementById('countText').textContent = '';
    return;
  }}
  const res = await fetch('data/' + entry.file, {{cache:'no-store'}});
  const data = await res.json();
  render(data);
}}

document.getElementById('updateBtn').addEventListener('click', function(){{
  const v = document.getElementById('dateInput').value;
  if(!v) return;
  loadWeekend(saturdayOf(v));
}});

(async function init(){{
  await loadManifest();
  await loadWeekend(document.getElementById('dateInput').value ? saturdayOf(document.getElementById('dateInput').value) : MANIFEST.default);
}})();
</script>
</body>
</html>"""

def main():
    all_events, today = collect_all_events()
    enrich_images(all_events)

    weekends = upcoming_saturdays(today, n=N_WEEKS)
    os.makedirs(DATADIR, exist_ok=True)

    manifest_weekends = []
    for sat, sun in weekends:
        hit = filter_weekend(all_events, sat, sun)
        data = build_weekend_json(hit, sat, sun)
        fname = f"{sat.isoformat()}.json"
        with open(os.path.join(DATADIR, fname), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        manifest_weekends.append({"sat": sat.isoformat(), "sun": sun.isoformat(),
                                  "file": fname, "label": data["label"], "count": len(hit)})
        print(f"  {data['label']:20s}: {len(hit)}件 -> data/{fname}")

    default_sat = weekends[0][0].isoformat()
    manifest = {
        "generated": datetime.datetime.now().isoformat(timespec="minutes"),
        "default": default_sat,
        "weekends": manifest_weekends,
    }
    with open(os.path.join(DATADIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)

    index_html = INDEX_TEMPLATE.format(
        default_date=default_sat,
        n_weeks=N_WEEKS,
        generated=manifest["generated"],
        area_color_json=json.dumps(AREA_COLOR, ensure_ascii=False),
    )
    with open(os.path.join(OUTDIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    open(os.path.join(OUTDIR, ".nojekyll"), "w").close()

    print(f"\nサイト出力: {os.path.join(OUTDIR, 'index.html')}")
    print(f"事前生成: {len(weekends)}週分 ({weekends[0][0]} 〜 {weekends[-1][0]})")
    if "--open" in sys.argv:
        webbrowser.open("file:///" + os.path.join(OUTDIR, "index.html").replace("\\", "/"))

if __name__ == "__main__":
    main()
