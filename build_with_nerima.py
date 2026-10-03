# -*- coding: utf-8 -*-
"""
既存 build_site.py の出力を一切変えずに先に生成し、
成功後に「とっておきの練馬」イベントだけを追加マージするラッパー。

練馬観光サイトの取得・解析に失敗しても、既存サイトの生成結果はそのまま残す。
"""
import datetime
import json
import os
import tempfile

import build_site


def _period_for_weekend(dates, sat, sun):
    hit = sorted(d for d in dates if sat <= d <= sun)
    if not hit:
        return None
    if len(hit) == 1:
        return f"{hit[0].month}/{hit[0].day}"
    return f"{hit[0].month}/{hit[0].day}〜{hit[-1].month}/{hit[-1].day}"


def _to_json_event(event, sat, sun):
    period = _period_for_weekend(event.get("dates") or [], sat, sun)
    if not period:
        return None
    return {
        "area": event["area"],
        "name": event["name"],
        "url": event["url"],
        "image": event.get("image"),
        "period": period,
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

    # すべてメモリ上で作成してから書き込む。
    # 解析途中で失敗した場合に一部ファイルだけ変わるのを防ぐ。
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

    for path, data in staged:
        _write_json_atomic(path, data)
    _write_json_atomic(manifest_path, manifest)
    print(f"[練馬観光] 追加完了: 延べ {total_added}件（週末別の掲載数合計）")


def main():
    # まず既存処理をそのまま完走させる。
    build_site.main()

    # 追加ソースは完全にオプション扱い。
    try:
        merge_nerimakanko()
    except Exception as e:
        print(f"[警告] 練馬観光イベントの追加に失敗しました。既存データは維持します: {e}")


if __name__ == "__main__":
    main()
