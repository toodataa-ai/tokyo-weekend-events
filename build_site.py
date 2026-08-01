# -*- coding: utf-8 -*-
"""
東京 週末イベント 静的サイト生成
scraper.py で収集したデータを、モバイル対応のカード一覧サイト(site/index.html)にビルドする。
GitHub Actions から実行され、GitHub Pages にデプロイされる想定。
ローカル確認: python build_site.py  → site/index.html を開く
"""
import os, html, datetime, webbrowser, sys
from scraper import collect_weekend_events, fmt_period, WARDS

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")

# エリアごとの色（15エリア分・巡回して割当）
PALETTE = ["2E86AB","3BAA6F","8E5EA8","1BA6C4","D98324","5B6670",
           "C0392B","2E7D57","6C5CE7","E17055","0984E3","B8891F","16324F","D64550","2C3E50"]
AREA_COLOR = {area: PALETTE[i % len(PALETTE)] for i, area in enumerate(WARDS.keys())}

def area_chip(area, count):
    color = AREA_COLOR.get(area, "2E86AB")
    return (f'<button class="chip" data-area="{html.escape(area)}" '
            f'style="--c:#{color}">{html.escape(area)} <span>{count}</span></button>')

def event_card(ev):
    color = AREA_COLOR.get(ev["area"], "2E86AB")
    name = html.escape(ev["name"] or ev["url"])
    return f"""<a class="card" data-area="{html.escape(ev['area'])}" href="{html.escape(ev['url'])}" target="_blank" rel="noopener">
  <div class="card-top">
    <span class="badge" style="background:#{color}">{html.escape(ev['area'])}</span>
    <span class="date">{html.escape(fmt_period(ev['period']))}</span>
  </div>
  <div class="card-name">{name}</div>
</a>"""

def build_html(events, sat, sun):
    by_area = {}
    for ev in events:
        by_area.setdefault(ev["area"], []).append(ev)
    chips = "".join(area_chip(a, len(evs)) for a, evs in by_area.items())
    cards = "\n".join(event_card(ev) for ev in events)
    if not events:
        cards = '<p class="empty">今週末に開催されるイベントは見つかりませんでした。</p>'
    updated = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>東京 今週末イベント {sat:%m/%d}-{sun:%m/%d}</title>
<style>
:root{{--navy:#16324f;--ink:#1a1a1a;--sub:#666}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic UI",Meiryo,sans-serif;
     background:#f4f6f8;color:var(--ink)}}
header{{background:linear-gradient(135deg,var(--navy),#2e5e8c);color:#fff;padding:18px 16px 14px;
        position:sticky;top:0;z-index:10;box-shadow:0 2px 8px rgba(0,0,0,.15)}}
header h1{{margin:0;font-size:19px;line-height:1.4}}
header .range{{font-size:12.5px;opacity:.9;margin-top:2px}}
header .count{{font-size:12px;opacity:.85;margin-top:6px}}
.chips{{display:flex;gap:6px;overflow-x:auto;padding:10px 12px;background:#fff;
       border-bottom:1px solid #e3e6ea;-webkit-overflow-scrolling:touch}}
.chips::-webkit-scrollbar{{display:none}}
.chip{{flex:0 0 auto;border:1.5px solid var(--c);color:var(--c);background:#fff;border-radius:99px;
      padding:5px 11px;font-size:12.5px;font-weight:600;white-space:nowrap;cursor:pointer}}
.chip.active{{background:var(--c);color:#fff}}
.chip span{{opacity:.75;margin-left:2px}}
main{{padding:12px;max-width:900px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}}
.card{{display:block;background:#fff;border-radius:12px;padding:12px 14px;text-decoration:none;color:var(--ink);
      box-shadow:0 1px 3px rgba(0,0,0,.08);border:1px solid #eceff2;transition:transform .1s}}
.card:active{{transform:scale(.98)}}
.card-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.badge{{color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px}}
.date{{color:#c0392b;font-size:12px;font-weight:600}}
.card-name{{font-size:14.5px;line-height:1.45;font-weight:600}}
.empty{{text-align:center;color:var(--sub);padding:40px 0}}
footer{{text-align:center;color:var(--sub);font-size:11.5px;padding:20px 16px 30px}}
</style>
</head>
<body>
<header>
  <h1>&#127961; 東京 今週末イベント</h1>
  <div class="range">{sat:%Y/%m/%d}(土) 〜 {sun:%m/%d}(日) 開催中・開催</div>
  <div class="count">該当 {len(events)} 件 ／ {len(by_area)} エリア</div>
</header>
<nav class="chips" id="chips">
  <button class="chip active" data-area="__all__" style="--c:#16324f">すべて <span>{len(events)}</span></button>
  {chips}
</nav>
<main>
  <div class="grid" id="grid">
{cards}
  </div>
</main>
<footer>
  自動収集（tokyofes.info 配下の各エリアサイト）。日程・開催有無は必ず各公式ページでご確認ください。<br>
  最終更新: {updated}
</footer>
<script>
document.getElementById('chips').addEventListener('click', function(e){{
  var btn = e.target.closest('.chip');
  if(!btn) return;
  document.querySelectorAll('.chip').forEach(c=>c.classList.remove('active'));
  btn.classList.add('active');
  var area = btn.dataset.area;
  document.querySelectorAll('#grid .card').forEach(function(card){{
    card.style.display = (area === '__all__' || card.dataset.area === area) ? '' : 'none';
  }});
}});
</script>
</body>
</html>"""

def main():
    events, sat, sun = collect_weekend_events()
    os.makedirs(OUTDIR, exist_ok=True)
    out_path = os.path.join(OUTDIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_html(events, sat, sun))
    # GitHub Pages で Jekyll処理をスキップさせるため
    open(os.path.join(OUTDIR, ".nojekyll"), "w").close()
    print(f"\nサイト出力: {out_path}")
    if "--open" in sys.argv:
        webbrowser.open("file:///" + out_path.replace("\\", "/"))
    return out_path

if __name__ == "__main__":
    main()
