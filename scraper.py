# -*- coding: utf-8 -*-
"""
東京イベント週末抽出 - コアスクレイパ（依存: 標準ライブラリのみ）
tokyofes.info 配下の各エリアサイトを巡回し、今週末(土・日)開催のイベントを抽出する。
build_site.py から import して使う。
"""
import urllib.request, re, os, html, time, datetime

WARDS = {
    "墨田":       "https://www.sumidaevent.com/",
    "浅草":       "https://www.asakusaevent.com/",
    "上野公園":   "https://www.uenopark.info/",
    "秋葉原":     "https://www.akihabaraevent.com/",
    "日比谷公園": "https://www.hibiyapark.info/",
    "池袋":       "https://www.ikebukuropark.info/",
    "新宿":       "https://www.shinjukuevent.com/",
    "中野":       "https://www.nakanoevent.com/",
    "代々木公園": "https://www.yoyogikoen.info/",
    "渋谷":       "https://www.miyashitapark.info/",
    "六本木":     "https://www.roppongievents.com/",
    "豊洲":       "https://www.toyosuevent.com/",
    "お台場":     "https://www.odaibapark.com/",
    "品川":       "https://www.shinagawaevent.com/",
    "立川":       "https://www.tachikawaevent.com/",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TokyoEventBot/1.0"

def this_weekend(today=None):
    today = today or datetime.date.today()
    wd = today.weekday()  # Mon=0..Sun=6
    if wd == 5:      sat = today
    elif wd == 6:    sat = today - datetime.timedelta(days=1)
    else:            sat = today + datetime.timedelta(days=(5 - wd))
    return sat, sat + datetime.timedelta(days=1)

def make_date(m, d, today):
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try: cand = datetime.date(y, m, d)
        except ValueError: continue
        if best is None or abs((cand - today).days) < abs((best - today).days):
            best = cand
    return best

DATE_RE = re.compile(r'(\d{1,2})月(\d{1,2})日')

def parse_period(text, today):
    ms = DATE_RE.findall(text)
    ongoing = "開催中" in text
    dates = [make_date(int(a), int(b), today) for a, b in ms]
    dates = [d for d in dates if d]
    if not dates:
        return None
    if ongoing and len(dates) >= 1:
        return (None, max(dates))
    if len(dates) >= 2:
        return (min(dates), max(dates))
    return (dates[0], dates[0])

def intersects(period, sat, sun):
    start, end = period
    s = start if start else sat
    e = end if end else s
    return s <= sun and e >= sat

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read()
    for enc in ("utf-8", "cp932", "euc-jp"):
        try: return raw.decode(enc)
        except UnicodeDecodeError: continue
    return raw.decode("utf-8", "replace")

def strip_tags(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s)).replace("　", " ").strip()

def parse_site(area, base_url, today):
    try:
        page = fetch(base_url)
    except Exception as e:
        print(f"  [警告] {area} 取得失敗: {e}")
        return []
    host = re.sub(r'^https?://', '', base_url).strip("/").split("/")[0]
    events = []
    for block in re.findall(r'<li[^>]*>(.*?)</li>', page, re.S):
        if "href=" not in block or not DATE_RE.search(block):
            continue
        url = None
        for href in re.findall(r'href="([^"]+)"', block):
            if host not in href:
                continue
            path = re.sub(r'^https?://[^/]+', '', href).strip("/")
            if not path:
                continue
            seg = path.split("/")
            if seg[0] in ("category", "tag", "author", "page", "wp-login.php"):
                continue
            url = href if href.startswith("http") else base_url.rstrip("/") + "/" + path
            break
        if not url:
            continue
        text = strip_tags(block)
        period = parse_period(text, today)
        if not period:
            continue
        name = DATE_RE.sub("", text)
        name = name.replace("開催中", "")
        name = re.sub(r'^[\s〜~\-－・･（）()日月火水木金土]+', '', name).strip()
        events.append({"area": area, "name": name[:80], "url": url, "period": period, "raw": text[:60]})
    return events

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']',
    re.I)

def fetch_og_image(url):
    """イベント個別ページから og:image (無ければ twitter:image) のURLを取得。失敗時は None。"""
    try:
        page = fetch(url)
    except Exception:
        return None
    m = OG_IMAGE_RE.search(page)
    return m.group(1) if m else None

def enrich_images(events, sleep=0.15, log=print):
    """各イベントに 'image' キー(サムネイルURL or None) を追加する。"""
    cache = {}
    for ev in events:
        url = ev["url"]
        if url not in cache:
            cache[url] = fetch_og_image(url)
            if sleep:
                time.sleep(sleep)
        ev["image"] = cache[url]
    n_ok = sum(1 for e in events if e.get("image"))
    log(f"サムネイル取得: {n_ok}/{len(events)} 件")
    return events

def fmt_period(p):
    s, e = p
    f = lambda d: f"{d.month}/{d.day}" if d else "開催中"
    return f(s) if (s == e) else f"{f(s)}〜{f(e)}"

def collect_all_events(today=None, sleep=0.4, log=print):
    """全エリアを1回ずつ巡回し、期間フィルタをかけずに全イベント(重複排除済み)を返す。"""
    today = today or datetime.date.today()
    all_events, seen = [], set()
    for area, url in WARDS.items():
        evs = parse_site(area, url, today)
        uniq = []
        for e in evs:
            if e["url"] in seen:
                continue
            seen.add(e["url"]); uniq.append(e)
        log(f"  {area:6s}: 抽出{len(evs):3d}件 / 新規{len(uniq):3d}件")
        all_events += uniq
        if sleep:
            time.sleep(sleep)
    log(f"合計 ユニークイベント: {len(all_events)}件")
    return all_events, today

def filter_weekend(all_events, sat, sun):
    return [e for e in all_events if intersects(e["period"], sat, sun)]

def upcoming_saturdays(today=None, n=12):
    """今週末を含め、n週分の土曜日(sat, sun)のリストを返す。"""
    today = today or datetime.date.today()
    sat0, sun0 = this_weekend(today)
    out = []
    for i in range(n):
        sat = sat0 + datetime.timedelta(days=7 * i)
        out.append((sat, sat + datetime.timedelta(days=1)))
    return out

def collect_weekend_events(today=None, sleep=0.4, log=print):
    """今週末に該当する全イベントを収集して (events, sat, sun) を返す。（単発利用向け・互換用）"""
    today = today or datetime.date.today()
    sat, sun = this_weekend(today)
    log(f"■ 東京 今週末イベント抽出  対象: {sat:%Y/%m/%d}(土)〜{sun:%m/%d}(日)")
    all_events, _ = collect_all_events(today, sleep, log)
    hit = filter_weekend(all_events, sat, sun)
    log(f"合計 週末該当: {len(hit)}件")
    return hit, sat, sun
