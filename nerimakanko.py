# -*- coding: utf-8 -*-
"""
ねりま観光センター「とっておきの練馬」イベントカレンダー取得。

既存スクレイパーとは独立して動作し、取得に失敗した場合は空配列を返す。
対象期間の土日ごとに日付検索ページを取得し、その日に該当するイベント詳細URLを集約する。
同じイベントが複数日に該当する場合は dates に正確な開催日一覧を保持する。
"""
import datetime
import html
import re
import time
import urllib.parse
import urllib.request

BASE_URL = "https://www.nerimakanko.jp"
EVENT_TOP_URL = BASE_URL + "/event/"
SEARCH_URL = BASE_URL + "/event/search.php?day={date}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TokyoWeekendEvents/1.0"

DETAIL_HREF_RE = re.compile(
    r'href=["\']([^"\']*?/event/detail\.php\?event_id=[^"\'&<>\s]+(?:&amp;[^"\']*)?)["\']',
    re.I,
)
PAGE_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)


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


def _discover_detail_urls(search_page, search_url):
    urls = []
    seen = set()
    for href in DETAIL_HREF_RE.findall(search_page):
        href = html.unescape(href)
        url = urllib.parse.urljoin(search_url, href)
        url = urllib.parse.urldefrag(url)[0]
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _discover_pagination_urls(page, current_url):
    """日付検索結果が複数ページの場合に、同じ day のページングURLを拾う。"""
    parsed = urllib.parse.urlparse(current_url)
    current_qs = urllib.parse.parse_qs(parsed.query)
    day = (current_qs.get("day") or [None])[0]
    if not day:
        return []
    out = []
    seen = set()
    for href in PAGE_HREF_RE.findall(page):
        href = html.unescape(href)
        u = urllib.parse.urljoin(current_url, href)
        p = urllib.parse.urlparse(u)
        if not p.path.endswith("/event/search.php"):
            continue
        qs = urllib.parse.parse_qs(p.query)
        if (qs.get("day") or [None])[0] != day:
            continue
        if not any(k.lower() in ("page", "p", "offset", "start") for k in qs):
            continue
        if u != current_url and u not in seen:
            seen.add(u)
            out.append(u)
    return out[:10]


def _detail_to_event(detail_url, dates):
    page = _fetch(detail_url)
    title = _title_from_page(page)
    if not title:
        return None
    text = _flatten(page)
    fields = _extract_fields(text)
    description = _meta(page, "og:description") or _meta(page, "description")
    if description:
        description = description.strip()
    date_text = fields.get("日時")
    time_text = date_text
    if time_text and len(time_text) > 220:
        time_text = time_text[:217] + "..."
    venue = fields.get("場所")
    if venue and len(venue) > 180:
        venue = venue[:177] + "..."
    price = fields.get("料金")
    if price and len(price) > 180:
        price = price[:177] + "..."

    dates = sorted(set(dates))
    if not dates:
        return None
    return {
        "area": "練馬区",
        "name": title[:120],
        "url": detail_url,
        "period": (dates[0], dates[-1]),
        "dates": dates,
        "raw": (date_text or "")[:160],
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
    今週末から n_weeks 分の土日を日付検索し、イベントをURL単位で集約して返す。
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

    date_by_url = {}
    page_errors = 0

    for i in range(n_weeks):
        sat = sat0 + datetime.timedelta(days=7 * i)
        for target in (sat, sat + datetime.timedelta(days=1)):
            first_url = SEARCH_URL.format(date=target.isoformat())
            pending = [first_url]
            visited_pages = set()
            while pending:
                url = pending.pop(0)
                if url in visited_pages:
                    continue
                visited_pages.add(url)
                try:
                    page = _fetch(url)
                except Exception as e:
                    page_errors += 1
                    log(f"  [警告] 練馬観光 日付検索取得失敗 {target}: {e}")
                    continue
                for detail_url in _discover_detail_urls(page, url):
                    date_by_url.setdefault(detail_url, set()).add(target)
                for purl in _discover_pagination_urls(page, url):
                    if purl not in visited_pages and purl not in pending:
                        pending.append(purl)
                if sleep:
                    time.sleep(sleep)

    events = []
    for detail_url, dates in sorted(date_by_url.items()):
        try:
            event = _detail_to_event(detail_url, dates)
            if event:
                events.append(event)
        except Exception as e:
            log(f"  [警告] 練馬観光 詳細取得失敗 {detail_url}: {e}")
        if sleep:
            time.sleep(sleep)

    log(
        f"  {'練馬区(観光)':10s}: 対象URL{len(date_by_url):3d}件 / "
        f"取得{len(events):3d}件 / 日付ページ失敗{page_errors}件"
    )
    return events
