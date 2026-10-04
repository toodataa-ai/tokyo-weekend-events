# -*- coding: utf-8 -*-
"""
杉並区公式ホームページのイベントカレンダーから、
ジャンル「おまつり」(event_category=5) のイベントだけを取得する。

既存スクレイパーとは独立しており、一覧・詳細取得に失敗した場合は
取得できた分だけを返す。外部依存ライブラリは使用しない。
"""
import datetime
import html
import re
import time
import urllib.parse
import urllib.request

BASE_URL = "https://www.city.suginami.tokyo.jp"
CALENDAR_URL = (
    BASE_URL
    + "/cgi-bin/event_cal_multi/calendar.cgi?type=2&year={year}&month={month}"
    + "&event_category=5&siteid=1"
)
SOURCE_URL = BASE_URL + "/event/index.html"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TokyoWeekendEvents/1.0"

EVENT_HREF_RE = re.compile(r'href=["\']([^"\']*/event/\d+\.html(?:[?#][^"\']*)?)["\']', re.I)
DATE_TOKEN_RE = re.compile(
    r"(?:(?P<y>\d{4})年)?\s*(?:(?P<m>\d{1,2})月)?\s*(?P<d>\d{1,2})日"
)
_RANGE_MARKER_RE = re.compile(r"(?:から|〜|～|~|－|−|―|—|-)" )
_FULLWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")


def _fetch(url, retries=2):
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
            for enc in ("utf-8", "cp932", "euc-jp"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    pass
            return raw.decode("utf-8", "replace")
        except Exception as e:
            last = e
            code = getattr(e, "code", None)
            if attempt >= retries or code not in (403, 429, 500, 502, 503, 504):
                raise
            time.sleep(1.2 * (attempt + 1))
    raise last


def _flatten(page):
    text = re.sub(r"<script[\s\S]*?</script>", " ", page, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def _meta(page, key):
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
        m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.I | re.S)
        if m:
            title = _flatten(m.group(1))
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        if m:
            title = _flatten(m.group(1))
    if not title:
        return None
    return re.sub(r"\s*[|｜]\s*杉並区公式ホームページ\s*$", "", title).strip() or None


def _extract_detail_fields(flat_text):
    """本文の「イベント情報詳細」ブロックから主要項目を抜き出す。"""
    marker = "イベント情報詳細"
    p = flat_text.find(marker)
    section = flat_text[p + len(marker):] if p >= 0 else flat_text
    end = section.find("ここまでが本文です")
    if end >= 0:
        section = section[:end]

    labels = [
        "開催日",
        "開催時間",
        "対象者",
        "開催場所",
        "内容",
        "申し込み",
        "申し込み期間",
        "費用",
        "お問い合わせ先",
    ]
    positions = []
    for label in labels:
        pos = section.find(label)
        if pos >= 0:
            positions.append((pos, label))
    positions.sort()

    out = {}
    for i, (pos, label) in enumerate(positions):
        start = pos + len(label)
        end = positions[i + 1][0] if i + 1 < len(positions) else min(len(section), start + 2500)
        value = section[start:end].strip(" :：|｜")
        if value and label not in out:
            out[label] = value
    return out


def _make_date(year, month, day):
    try:
        return datetime.date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None


def parse_event_schedule(date_text, today=None):
    """
    開催日欄を ranges=[(開始,終了), ...] と dates=[単発日,...] に分解する。
    「2026年10月3日 から 2026年10月4日」のほか、年月省略表記にも対応。
    """
    today = today or datetime.date.today()
    text = (date_text or "").translate(_FULLWIDTH)
    tokens = []
    current_year = today.year
    current_month = None

    for m in DATE_TOKEN_RE.finditer(text):
        year_raw, month_raw, day_raw = m.group("y"), m.group("m"), m.group("d")
        if year_raw:
            current_year = int(year_raw)
        if month_raw:
            month = int(month_raw)
            if (
                not year_raw
                and current_month is not None
                and current_month >= 10
                and month <= 3
                and month < current_month
            ):
                current_year += 1
            current_month = month
        if current_month is None:
            continue
        value = _make_date(current_year, current_month, int(day_raw))
        if value:
            tokens.append((m.start(), m.end(), value))

    ranges = []
    dates = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            between = text[tokens[i][1]:tokens[i + 1][0]]
            if _RANGE_MARKER_RE.search(between):
                start, end = tokens[i][2], tokens[i + 1][2]
                if start <= end:
                    ranges.append((start, end))
                    i += 2
                    continue
        dates.append(tokens[i][2])
        i += 1

    return {
        "ranges": sorted(set(ranges)),
        "dates": sorted(set(dates)),
    }


def _extract_image(page, detail_url):
    image = _meta(page, "og:image")
    if image and "/shared/images/sns/logo" not in image:
        return urllib.parse.urljoin(detail_url, image)
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', page, re.I):
        src = html.unescape(src)
        if "/documents/" in src or "/event/" in src:
            return urllib.parse.urljoin(detail_url, src)
    return None


def _discover_event_urls(page, list_url):
    urls = []
    seen = set()
    for href in EVENT_HREF_RE.findall(page):
        url = urllib.parse.urldefrag(urllib.parse.urljoin(list_url, html.unescape(href)))[0]
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _month_keys(start_date, end_date):
    cur = start_date.replace(day=1)
    last = end_date.replace(day=1)
    out = []
    while cur <= last:
        out.append((cur.year, cur.month))
        if cur.month == 12:
            cur = datetime.date(cur.year + 1, 1, 1)
        else:
            cur = datetime.date(cur.year, cur.month + 1, 1)
    return out


def _event_intersects_window(event, start_date, end_date):
    for start, end in event.get("ranges") or []:
        if start <= end_date and end >= start_date:
            return True
    return any(start_date <= d <= end_date for d in (event.get("dates") or []))


def _detail_to_event(detail_url, today):
    page = _fetch(detail_url)
    title = _title_from_page(page)
    if not title:
        return None

    flat = _flatten(page)
    fields = _extract_detail_fields(flat)
    schedule = parse_event_schedule(fields.get("開催日"), today=today)
    if not schedule["ranges"] and not schedule["dates"]:
        return None

    boundaries = list(schedule["dates"])
    for start, end in schedule["ranges"]:
        boundaries.extend((start, end))

    description = _meta(page, "description") or fields.get("内容")
    if description:
        description = re.sub(r"\s+", " ", description).strip()
        if len(description) > 360:
            description = description[:357] + "..."

    time_text = fields.get("開催時間")
    if time_text and len(time_text) > 180:
        time_text = time_text[:177] + "..."
    venue = fields.get("開催場所")
    if venue and len(venue) > 220:
        venue = venue[:217] + "..."
    price = fields.get("費用")
    if price and len(price) > 160:
        price = price[:157] + "..."

    return {
        "area": "杉並区",
        "name": title[:140],
        "url": detail_url,
        "period": (min(boundaries), max(boundaries)),
        "ranges": schedule["ranges"],
        "dates": schedule["dates"],
        "raw": (fields.get("開催日") or "")[:180],
        "source": SOURCE_URL,
        "image": _extract_image(page, detail_url),
        "description": description,
        "time": time_text,
        "venue": venue,
        "price": price,
        "official_url": None,
    }


def scrape_suginami(today=None, n_weeks=12, sleep=0.12, log=print):
    """今週末から n_weeks 分に関係する「おまつり」イベントを取得する。"""
    today = today or datetime.date.today()
    wd = today.weekday()
    if wd == 5:
        sat0 = today
    elif wd == 6:
        sat0 = today - datetime.timedelta(days=1)
    else:
        sat0 = today + datetime.timedelta(days=(5 - wd))
    last_sun = sat0 + datetime.timedelta(days=7 * (n_weeks - 1) + 1)

    event_urls = set()
    list_errors = 0
    for year, month in _month_keys(sat0, last_sun):
        url = CALENDAR_URL.format(year=year, month=month)
        try:
            page = _fetch(url)
            event_urls.update(_discover_event_urls(page, url))
        except Exception as e:
            list_errors += 1
            log(f"  [警告] 杉並区おまつり 月別一覧取得失敗 {year}-{month:02d}: {e}")
        if sleep:
            time.sleep(sleep)

    events = []
    detail_errors = 0
    for detail_url in sorted(event_urls):
        try:
            event = _detail_to_event(detail_url, today)
            if event and _event_intersects_window(event, sat0, last_sun):
                events.append(event)
        except Exception as e:
            detail_errors += 1
            log(f"  [警告] 杉並区おまつり 詳細取得失敗 {detail_url}: {e}")
        if sleep:
            time.sleep(sleep)

    log(
        f"  {'杉並区(おまつり)':12s}: 候補{len(event_urls):3d}件 / "
        f"取得{len(events):3d}件 / 一覧失敗{list_errors}件 / 詳細失敗{detail_errors}件"
    )
    return events
