#!/usr/bin/env python3
import argparse, json, pathlib, re, sys
from urllib.parse import urlsplit, urlunsplit

WARDS = [
    '千代田区','中央区','港区','新宿区','文京区','台東区','墨田区','江東区','品川区','目黒区','大田区',
    '世田谷区','渋谷区','中野区','杉並区','豊島区','北区','荒川区','板橋区','練馬区','足立区','葛飾区','江戸川区'
]
HTTP_RE = re.compile(r'^https?://', re.I)


def canonical_url(value):
    if not value:
        return ''
    try:
        p = urlsplit(value.strip())
        host = p.netloc.lower().removeprefix('www.')
        path = p.path.rstrip('/') or '/'
        return urlunsplit((p.scheme.lower(), host, path, p.query, ''))
    except Exception:
        return value.strip()


def norm(value):
    return re.sub(r'\s+', '', str(value or '')).lower()


def validate_week(path, strict=False):
    errors, warnings = [], []
    data = json.loads(path.read_text(encoding='utf-8'))
    events = data.get('events')
    coverage = data.get('coverage') or {}
    if not isinstance(events, list):
        return [f'{path}: events must be an array'], warnings

    if strict and data.get('sample'):
        errors.append(f'{path}: sample=true cannot be deployed in strict mode')

    wards = coverage.get('wards') or []
    ward_rows = {row.get('ward'): row for row in wards if isinstance(row, dict)}
    missing_cov = [w for w in WARDS if w not in ward_rows]
    extra_cov = [w for w in ward_rows if w not in WARDS]
    if missing_cov:
        errors.append(f'{path}: coverage missing wards: {missing_cov}')
    if extra_cov:
        errors.append(f'{path}: coverage has invalid wards: {extra_cov}')
    if strict:
        unchecked = [w for w in WARDS if ward_rows.get(w, {}).get('status') != 'checked']
        if unchecked:
            errors.append(f'{path}: strict mode requires checked coverage for all wards: {unchecked}')

    if coverage.get('published_count') != len(events):
        errors.append(f"{path}: coverage.published_count={coverage.get('published_count')} != events={len(events)}")

    seen_ids, seen_urls, seen_signature = set(), {}, {}
    for i, ev in enumerate(events, 1):
        prefix = f'{path}: event #{i}'
        if not isinstance(ev, dict):
            errors.append(f'{prefix}: must be object')
            continue
        for key in ('id','ward','name','url','period','source'):
            if not ev.get(key):
                errors.append(f'{prefix}: missing required field {key}')
        ward = ev.get('ward')
        if ward and ward not in WARDS:
            errors.append(f'{prefix}: invalid ward {ward}')
        for key in ('url','official_url','source','image'):
            value = ev.get(key)
            if value and not HTTP_RE.match(value):
                errors.append(f'{prefix}: {key} must be http(s): {value}')

        eid = ev.get('id')
        if eid:
            if eid in seen_ids:
                errors.append(f'{prefix}: duplicate id {eid}')
            seen_ids.add(eid)

        url_key = canonical_url(ev.get('official_url') or ev.get('url'))
        if url_key:
            if url_key in seen_urls:
                warnings.append(f'{prefix}: same canonical URL as event #{seen_urls[url_key]}: {url_key}')
            else:
                seen_urls[url_key] = i

        sig = (norm(ev.get('name')), ev.get('date_start') or ev.get('period'), norm(ev.get('venue') or ward))
        if sig[0] and sig[1]:
            if sig in seen_signature:
                errors.append(f'{prefix}: probable duplicate of event #{seen_signature[sig]} (name/date/venue)')
            else:
                seen_signature[sig] = i

        fit = ev.get('family_fit') or {}
        if fit.get('grade') not in ('A','B','C'):
            warnings.append(f'{prefix}: family_fit.grade should be A/B/C')
        if not fit.get('reason'):
            warnings.append(f'{prefix}: family_fit.reason is empty')
        if not ev.get('venue'):
            warnings.append(f'{prefix}: venue is empty; copy output falls back to ward')
        if not ev.get('price'):
            warnings.append(f'{prefix}: price is empty; copy output uses the fixed fallback text')

    return errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data_dir', type=pathlib.Path)
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()
    manifest_path = args.data_dir / 'manifest.json'
    if not manifest_path.exists():
        print(f'ERROR: missing {manifest_path}')
        return 2
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    errors, warnings = [], []
    weekends = manifest.get('weekends') or []
    if not weekends:
        errors.append('manifest: weekends is empty')
    if manifest.get('default') and manifest.get('default') not in {w.get('sat') for w in weekends}:
        errors.append('manifest: default does not point to a listed weekend')
    for entry in weekends:
        p = args.data_dir / str(entry.get('file',''))
        if not p.exists():
            errors.append(f'manifest: missing data file {p}')
            continue
        e, w = validate_week(p, args.strict)
        errors.extend(e); warnings.extend(w)
        data = json.loads(p.read_text(encoding='utf-8'))
        if entry.get('count') != len(data.get('events') or []):
            errors.append(f"manifest: {entry.get('file')} count={entry.get('count')} != events={len(data.get('events') or [])}")

    for msg in warnings:
        print('WARN:', msg)
    for msg in errors:
        print('ERROR:', msg)
    if errors:
        print(f'FAILED: {len(errors)} error(s), {len(warnings)} warning(s)')
        return 1
    print(f'OK: {len(weekends)} weekend file(s), {len(warnings)} warning(s)')
    return 0

if __name__ == '__main__':
    sys.exit(main())
