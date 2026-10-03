# -*- coding: utf-8 -*-
"""
既存 build_site.py をそのまま先に完走させ、その成功結果へ
「とっておきの練馬」イベントだけを追加マージするラッパー。

練馬観光サイトの取得・解析に失敗しても既存データは維持する。
"""
import datetime
import json
import os
import tempfile

import build_site


def _intersects(start, end, sat, sun):
    return start <= sun and end >= sat


def _matching_period(event, sat, sun):
    """
    この週末に該当する場合、表示用 period を返す。
    連続開催は元の期間、飛び石開催はその週末の該当日だけを返す。
    """
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


def merge_nerimakanko():
    # 遅延 import。新規スクレイパーに問題があっても既存 build は完了済み。
    from nerimakanko import scrape_nerimakanko

    manifest_path = os.path.join(build_site.DATADIR, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    weekends = manifest.get("weekends") or []
    if not weekends:
        print("[練馬観光] マニフェストに週末データがないため追加をスキップ")
        return

    events = scrape_nerimakanko(
        today=datetime.date.today(),
        n_weeks=len(weekends),
        sleep=0.12,
        log=print,
    )

    # 追加ソースが0件なら既存ファイルを一切触らない。
    # サイト側障害・HTML変更時に既存機能へ波及させないため。
    if not events:
        print("[練馬観光] 取得0件のため既存データを変更せず終了")
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

    # 全JSONをメモリ上で組み立てた後に書き込む。
    for path, data in staged:
        _write_json_atomic(path, data)
    _write_json_atomic(manifest_path, manifest)
    print(f"[練馬観光] 追加完了: 延べ {total_added}件（週末別の掲載数合計）")


def main():
    # 既存ロジックは変更せず、そのまま先に完走。
    build_site.main()

    # 新ソースはオプション。失敗しても既存生成物を残す。
    try:
        merge_nerimakanko()
    except Exception as e:
        print(f"[警告] 練馬観光イベントの追加に失敗しました。既存データは維持します: {e}")


if __name__ == "__main__":
    main()
