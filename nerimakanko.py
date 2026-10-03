# -*- coding: utf-8 -*-
"""
ねりま観光センター「とっておきの練馬」イベントカレンダー取得。

既存スクレイパーとは独立して動作する追加ソース。
月別検索ページから候補イベントを集め、各詳細ページの「日時」を解析して
連続開催と飛び石開催を区別する。
"""
import datetime
import html
import re
import time
import urllib.parse
import urllib.request

BASE_URL = "https://www.nerimakanko.jp"
EVENT_TOP_URL = BASE_URL + "/event/"
MONTH_URL = BASE_URL + "/event/search.php?month={month}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TokyoWeekendEvents/1.0"

DETAIL_HREF_RE = re.compile(
    r'href=["\']([^"\']*detail\.php\?event_id=[^"\']+)["\']',
    re.I,
)
PAGE_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)

DATE_RANGE_RE = re.compile(
    r'(?:(?P<y1>\d{4})年)?(?P<m1>\d{1,2})月(?P<d1>\d{1,2})日'
    r'.{0,20}?[〜～~\-ー−―]+.{0,20}?'
    r'(?:(?P<y2>\d{4})年)?(?:(?P<m2>\d{1,2})月)?(?P<d2>\d{1,2})日',
    re.S,
)
DATE_RE = re.compile(
    r'(?:(?P<y>\d{4})年)?(?P<m>\d{1,2})月(?P<d>\d{1,2})日'
)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read()
    for enc in ("utf-8", "cp932", "euc-jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def _flatten(page):
    text = re.sub(r"<script[\s\S]*?</script>", " ", page, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def _meta(page, key):
    """meta property/name の属性順に依存せず content を取る。"""
    for tag in re.findall(r"<meta\b[^>]*>", page, re.I):
        if not re.search(
            r'(?:property|name)\s*=\s*["\']' + re.escape(key) + r'["\']',
            tag,
            re.I,
        ):
            continue
        m = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return None


def _title_from_page(page):
    title = _meta(page, "og:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        title = _flatten(m.group(1)) if m else None
    if not title:
        for tag in ("h1", "h2"):
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", page, re.I | re.S)
            if m:
                title = _flatten(m.group(1))
                break
    if not title:
        return None
    title = re.split(r"\s*[|｜]\s*練馬区のイベント情報", title, maxsplit=1)[0].strip()
    return title or None


def _extract_fields(text):
    """日時/場所/住所/料金/主催者/関連URL などをラベル間で切り出す。"""
    labels = ["日時", "場所", "住所", "アクセス", "料金", "主催者", "お問合せ", "申込み", "関連URL", "備考"]
    positions = []
    for label in labels:
        p = text.find(label)
        if p >= 0:
            positions.append((p, label))
    positions.sort()
    out = {}
    for i, (pos, label) in enumerate(positions):
        start = pos + len(label)
        end = positions[i + 1][0] if i + 1 < len(positions) else min(len(text), start + 1800)
        value = text[start:end].strip(" :：|｜")
        if value:
            out[label] = value
    return out


def _make_date(year, month, day):
    try:
        return datetime.date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None


def parse_event_schedule(date_text, today=None):
    """
    「日時」欄を ranges=[(開始,終了), ...] と dates=[単発日,...] に分解する。

    飛び石開催を min〜max の連続期間にしないことが重要。
    例: 10/1, 10/8, 10/22 ... は dates として保持する。
    """
    today = today or datetime.date.today()
    text = date_text or ""
    ranges = []
    range_spans = []

    for m in DATE_RANGE_RE.finditer(text):
        y1 = int(m.group("y1") or today.year)
        mo1, d1 = int(m.group("m1")), int(m.group("d1"))
        y2 = int(m.group("y2") or y1)
        mo2 = int(m.group("m2") or mo1)
        d2 = int(m.group("d2"))

        if not m.group("y2") and m.group("m2") and mo1 >= 10 and mo2 <= 3 and mo2 < mo1:
            y2 += 1

        start = _make_date(y1, mo1, d1)
        end = _make_date(y2, mo2, d2)
        if start and end and start <= end:
            ranges.append((start, end))
            range_spans.append(m.span())

    masked = list(text)
    for a, b in range_spans:
        masked[a:b] = " " * (b - a)
    rest = "".join(masked)

    dates = []
    current_year = today.year
    last_month = None
    for m in DATE_RE.finditer(rest):
        if m.group("y"):
            current_year = int(m.group("y"))
        month, day = int(m.group("m")), int(m.group("d"))
        if (
            not m.group("y")
            and last_month is not None
            and last_month >= 10
            and month <= 3
            and month < last_month
        ):
            current_year += 1
        value = _make_date(current_year, month, day)
        if value:
            dates.append(value)
        last_month = month

    return {
        "ranges": sorted(set(ranges)),
        "dates": sorted(set(dates)),
    }


def _extract_related_url(page, fields):
    m = re.search(
        r"関連URL[\s\S]{0,1200}?href=[\"'](https?://[^\"']+)[\"']",
        page,
        re.I,
    )
    if m:
        return html.unescape(m.group(1)).strip()
    raw = fields.get("関連URL")
    if raw:
        m = re.search(r"https?://\S+", raw)
        if m:
            return m.group(0).rstrip("。、)")
    return None


def _extract_image(page, detail_url):
    image = _meta(page, "og:image") or _meta(page, "twitter:image")
    if image:
        return urllib.parse.urljoin(detail_url, image)
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', page, re.I):
        low = src.lower()
        if "event" in low or "upload" in low:
            return urllib.parse.urljoin(detail_url, html.unescape(src))
    return None


def _canonical_detail_url(href, base_url):
    url = urllib.parse.urljoin(base_url, html.unescape(href))
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    event_id = (params.get("event_id") or [None])[0]
    if not event_id:
        return None
    return BASE_URL + "/event/detail.php?event_id=" + urllib.parse.quote(event_id, safe="")


def _discover_detail_urls(search_page, search_url):
    urls = []
    seen = set()
    for href in DETAIL_HREF_RE.findall(search_page):
        url = _canonical_detail_url(href, search_url)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _discover_pagination_urls(page, current_url, month):
    """同じ month のページングURLだけを拾う。"""
    out = []
    seen = set()
    for href in PAGE_HREF_RE.findall(page):
        u = urllib.parse.urljoin(current_url, html.unescape(href))
        p = urllib.parse.urlparse(u)
        if not p.path.endswith("/event/search.php"):
            continue
        qs = urllib.parse.parse_qs(p.query)
        if (qs.get("month") or [None])[0] != month:
            continue
        if not any(k.lower() in ("page", "p", "offset", "start") for k in qs):
            continue
        if u != current_url and u not in seen:
            seen.add(u)
            out.append(u)
    return out[:10]


def _month_keys(start_date, end_date):
    cur = start_date.replace(day=1)
    last = end_date.replace(day=1)
    out = []
    while cur <= last:
        out.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = datetime.date(cur.year + 1, 1, 1)
        else:
            cur = datetime.date(cur.year, cur.month + 1, 1)
    return out


def _detail_to_event(detail_url, today):
    page = _fetch(detail_url)
    title = _title_from_page(page)
    if not title:
        return None

    text = _flatten(page)
    fields = _extract_fields(text)
    date_text = fields.get("日時")
    schedule = parse_event_schedule(date_text, today)
    if not schedule["ranges"] and not schedule["dates"]:
        return None

    description = _meta(page, "og:description") or _meta(page, "description")
    if description:
        description = description.strip()
    time_text = date_text
    if time_text and len(time_text) > 240:
        time_text = time_text[:237] + "..."
    venue = fields.get("場所")
    if venue and len(venue) > 180:
        venue = venue[:177] + "..."
    price = fields.get("料金")
    if price and len(price) > 180:
        price = price[:177] + "..."

    all_boundaries = list(schedule["dates"])
    for start, end in schedule["ranges"]:
        all_boundaries.extend((start, end))
    period = (min(all_boundaries), max(all_boundaries))

    return {
        "area": "練馬区",
        "name": title[:120],
        "url": detail_url,
        "period": period,
        "ranges": schedule["ranges"],
        "dates": schedule["dates"],
        "raw": (date_text or "")[:180],
        "source": EVENT_TOP_URL,
        "image": _extract_image(page, detail_url),
        "description": description,
        "time": time_text,
        "venue": venue,
        "price": price,
        "official_url": _extract_related_url(page, fields),
    }


def scrape_nerimakanko(today=None, n_weeks=12, sleep=0.15, log=print):
    """
    今週末から n_weeks の期間を含む月別検索を巡回し、候補イベントを取得する。
    取得元側の障害はこの関数内で吸収し、取得できた分だけ返す。
    """
    today = today or datetime.date.today()
    wd = today.weekday()
    if wd == 5:
        sat0 = today
    elif wd == 6:
        sat0 = today - datetime.timedelta(days=1)
    else:
        sat0 = today + datetime.timedelta(days=(5 - wd))
    last_sun = sat0 + datetime.timedelta(days=7 * (n_weeks - 1) + 1)

    detail_urls = set()
    page_errors = 0

    for month in _month_keys(sat0, last_sun):
        first_url = MONTH_URL.format(month=month)
        pending = [first_url]
        visited = set()
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                page = _fetch(url)
            except Exception as e:
                page_errors += 1
                log(f"  [警告] 練馬観光 月別検索取得失敗 {month}: {e}")
                continue

            detail_urls.update(_discover_detail_urls(page, url))
            for purl in _discover_pagination_urls(page, url, month):
                if purl not in visited and purl not in pending:
                    pending.append(purl)
            if sleep:
                time.sleep(sleep)

    events = []
    detail_errors = 0
    for detail_url in sorted(detail_urls):
        try:
            event = _detail_to_event(detail_url, today)
            if event:
                events.append(event)
        except Exception as e:
            detail_errors += 1
            log(f"  [警告] 練馬観光 詳細取得失敗 {detail_url}: {e}")
        if sleep:
            time.sleep(sleep)

    log(
        f"  {'練馬区(観光)':10s}: 候補{len(detail_urls):3d}件 / "
        f"取得{len(events):3d}件 / 一覧失敗{page_errors}件 / 詳細失敗{detail_errors}件"
    )
    return events
