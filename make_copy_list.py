# -*- coding: utf-8 -*-
"""
Canva貼り付け用「コピペリスト」ページ生成（個人利用・リポジトリ非公開の想定）
- site/data/{weekend}.json を読み込み、各イベントの個別ページから
  時間/会場/入場料/公式リンク/説明 を追加取得
- フィールドごとに「コピー」ボタン付きの一覧HTMLを生成し、ローカルに出力する

使い方: python make_copy_list.py [YYYY-MM-DD]  (省略時は直近の週末=site/data/manifest.jsonのdefault)
"""
import os, sys, json, html
from scraper import enrich_details, fmt_period

BASE = os.path.dirname(os.path.abspath(__file__))
DATADIR = os.path.join(BASE, "site", "data")

def load_weekend(date_arg):
    with open(os.path.join(DATADIR, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    sat = date_arg or manifest["default"]
    entry = next((w for w in manifest["weekends"] if w["sat"] == sat), None)
    if not entry:
        print(f"指定日 {sat} のデータがありません。利用可能: {[w['sat'] for w in manifest['weekends']]}")
        sys.exit(1)
    with open(os.path.join(DATADIR, entry["file"]), encoding="utf-8") as f:
        data = json.load(f)
    return data

def esc(s):
    return html.escape(s or "")

def build_html(data):
    label = data["label"]
    cards = []
    for i, ev in enumerate(data["events"], 1):
        title = ev["name"] or ev["url"]
        venue = ev.get("venue") or ev["area"]
        datetime_line = ev["period"] + (f"　{ev['time']}" if ev.get("time") else "")
        desc = ev.get("description") or ""
        price = ev.get("price") or "（料金情報は公式サイトでご確認ください）"
        official = ev.get("official_url") or ev["url"]
        img = ev.get("image") or ""

        def field(fid, label_txt, value, mono=False):
            cls = "val mono" if mono else "val"
            return f"""<div class="field">
  <div class="flabel">{esc(label_txt)}</div>
  <div class="{cls}" id="{fid}">{esc(value)}</div>
  <button class="copybtn" onclick="copyField('{fid}', this)">コピー</button>
</div>"""

        card = f"""<div class="card">
  <div class="cardhead">
    <span class="num">{i}</span>
    <img class="thumb" src="{esc(img)}" alt="" loading="lazy" onerror="this.style.display='none'">
    <div class="titlebox">
      <div class="flabel">タイトル</div>
      <div class="val big" id="t{i}">{esc(title)}</div>
      <button class="copybtn" onclick="copyField('t{i}', this)">コピー</button>
    </div>
  </div>
  {field(f'v{i}', '📍 場所', venue)}
  {field(f'd{i}', '🗓 日時', datetime_line)}
  {field(f'p{i}', '💰 料金', price)}
  {field(f's{i}', '📝 説明', desc)}
  {field(f'u{i}', '🔗 公式サイト', official, mono=True)}
  <button class="copyallbtn" onclick="copyAll({i})">この項目をまとめてコピー</button>
</div>"""
        cards.append(card)

    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Canva貼り付け用コピペリスト {label}</title>
<style>
body{{font-family:"Meiryo UI",Meiryo,-apple-system,sans-serif;background:#f4f6f8;margin:0;padding:16px;color:#1a1a1a}}
h1{{background:#16324f;color:#fff;padding:14px 16px;border-radius:10px;font-size:18px;margin:0 0 16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}}
.card{{background:#fff;border:1px solid #e3e6ea;border-radius:12px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.cardhead{{display:flex;gap:10px;align-items:flex-start;margin-bottom:10px}}
.num{{background:#2e86ab;color:#fff;font-weight:700;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;flex:0 0 auto;font-size:13px}}
.thumb{{width:64px;height:64px;object-fit:cover;border-radius:8px;flex:0 0 auto;background:#eee}}
.titlebox{{flex:1;position:relative}}
.field{{position:relative;margin-bottom:10px;padding-right:64px}}
.flabel{{font-size:11px;color:#888;font-weight:700;margin-bottom:2px}}
.val{{font-size:13.5px;line-height:1.5;background:#f7f8fa;border-radius:6px;padding:6px 8px;min-height:1.3em;white-space:pre-wrap}}
.val.big{{font-weight:700;font-size:14.5px}}
.val.mono{{font-family:Consolas,monospace;font-size:12px;word-break:break-all}}
.copybtn{{position:absolute;right:0;top:16px;border:1px solid #2e86ab;color:#2e86ab;background:#fff;border-radius:6px;
         font-size:11px;padding:4px 8px;cursor:pointer}}
.copybtn:hover{{background:#2e86ab;color:#fff}}
.copybtn.done{{background:#3baa6f;border-color:#3baa6f;color:#fff}}
.copyallbtn{{width:100%;border:none;background:#16324f;color:#fff;border-radius:8px;padding:9px;font-weight:700;
            font-size:13px;cursor:pointer;margin-top:4px}}
.copyallbtn.done{{background:#3baa6f}}
.tip{{color:#666;font-size:12px;margin:-8px 0 16px}}
</style></head>
<body>
<h1>📋 Canva貼り付け用コピペリスト ｜ {esc(label)}（{len(data['events'])}件）</h1>
<p class="tip">各項目の「コピー」でその1行だけ、カード下の「まとめてコピー」で全項目を改行区切りでコピーできます。</p>
<div class="grid">
{''.join(cards)}
</div>
<script>
function copyField(id, btn){{
  const text = document.getElementById(id).textContent;
  navigator.clipboard.writeText(text).then(()=>{{
    const old = btn.textContent; btn.textContent = '✓コピー済'; btn.classList.add('done');
    setTimeout(()=>{{ btn.textContent = old; btn.classList.remove('done'); }}, 1500);
  }});
}}
function copyAll(i){{
  const ids = ['t'+i, 'v'+i, 'd'+i, 'p'+i, 's'+i, 'u'+i];
  const text = ids.map(id => document.getElementById(id).textContent).join('\\n');
  navigator.clipboard.writeText(text).then(()=>{{
    const btn = event.target; const old = btn.textContent;
    btn.textContent = '✓コピーしました'; btn.classList.add('done');
    setTimeout(()=>{{ btn.textContent = old; btn.classList.remove('done'); }}, 1500);
  }});
}}
</script>
</body></html>"""

def main():
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    data = load_weekend(date_arg)
    enrich_details(data["events"])
    out_path = os.path.join(BASE, f"copy_list_{data['sat']}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_html(data))
    print(f"\n出力: {out_path}")
    return out_path

if __name__ == "__main__":
    main()
