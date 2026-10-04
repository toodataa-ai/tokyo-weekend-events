# -*- coding: utf-8 -*-
"""
既存の build_with_nerima.py をそのまま完走させた後、
杉並区公式イベントカレンダーの「おまつり」だけを追加マージする。

杉並区側の取得・解析に失敗しても、既存データと練馬観光データは維持する。
"""
import datetime
import json
import os
import tempfile

import build_site
import build_with_nerima


def _intersects(start, end, sat, sun):
    return start <= sun and end >= sat


def _matching_period(event, sat, sun):
    for start, end in event.get("ranges") or []:
        if _intersects(start, end, sat, sun):
            return start, end

    hit_dates = sorted(d for d in (event.get("dates") or []) if sat <= d <= sun)
    if hit_dates:
        return hit_dates[0], hit_dates[-1]
    return None


def _fmt_period(period):
    start, end = period
    if start == end:
        return f"{start.month}/{start.day}"
    return f"{start.month}/{start.day}〜{end.month}/{end.day}"


def _to_json_event(event, sat, sun):
    period = _matching_period(event, sat, sun)
    if not period:
        return None
    return {
        "area": event["area"],
        "name": event["name"],
        "url": event["url"],
        "image": event.get("image"),
        "period": _fmt_period(period),
        "description": event.get("description"),
        "time": event.get("time"),
        "venue": event.get("venue"),
        "price": event.get("price"),
        "official_url": event.get("official_url"),
        "source": event.get("source"),
    }


def _write_json_atomic(path, data):
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def merge_suginami():
    from suginami import scrape_suginami

    manifest_path = os.path.join(build_site.DATADIR, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    weekends = manifest.get("weekends") or []
    if not weekends:
        print("[杉並区おまつり] マニフェストに週末データがないため追加をスキップ")
        return

    events = scrape_suginami(
        today=datetime.date.today(),
        n_weeks=len(weekends),
        sleep=0.12,
        log=print,
    )

    # 新ソースが0件なら既存JSONを一切触らない。
    if not events:
        print("[杉並区おまつり] 取得0件のため既存データを変更せず終了")
        return

    staged = []
    total_added = 0
    for entry in weekends:
        sat = datetime.date.fromisoformat(entry["sat"])
        sun = datetime.date.fromisoformat(entry["sun"])
        path = os.path.join(build_site.DATADIR, entry["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        existing_urls = {ev.get("url") for ev in data.get("events", [])}
        additions = []
        for event in events:
            item = _to_json_event(event, sat, sun)
            if item and item["url"] not in existing_urls:
                additions.append(item)
                existing_urls.add(item["url"])

        if additions:
            data["events"].extend(additions)
        entry["count"] = len(data.get("events", []))
        total_added += len(additions)
        staged.append((path, data))

    # 全週分をメモリ上で組み立ててから置換する。
    for path, data in staged:
        _write_json_atomic(path, data)
    _write_json_atomic(manifest_path, manifest)
    print(f"[杉並区おまつり] 追加完了: 延べ {total_added}件（週末別の掲載数合計）")


def main():
    # 既存機能 + 練馬観光は、従来のラッパーをそのまま実行。
    build_with_nerima.main()

    # 杉並区は完全に追加扱い。失敗しても既存生成物を残す。
    try:
        merge_suginami()
    except Exception as e:
        print(f"[警告] 杉並区おまつりイベントの追加に失敗しました。既存データは維持します: {e}")


if __name__ == "__main__":
    main()
