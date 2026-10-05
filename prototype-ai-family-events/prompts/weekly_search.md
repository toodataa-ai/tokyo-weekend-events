# 東京23区 子連れイベント AI探索・週次更新プロンプト v1.0

対象週末の東京23区について、子連れで参加できそうなイベントを網羅的に探索し、新サイト用JSONを作成する。

## 最重要ルール

1. 23区を必ず1区ずつ処理する。まとめ検索だけで完了扱いにしない。
2. 各区の探索が終わるまで `coverage.wards[].status` を `checked` にしない。
3. 「子ども向け」と明記されたイベントだけに限定しない。祭り、鉄道、動物、科学、防災、消防、スポーツ、フード、商店街、スタンプラリー等も子連れ可能性を評価する。
4. 開催日・開催場所・年齢制限・予約要否を確認する。
5. 公式URLが見つかる場合は必ず `official_url` に入れる。媒体記事だけで確定しない。
6. 同一イベントの複数掲載は1件に統合する。
7. 推測で料金・時間・会場を埋めない。不明はnull/空欄とする。
8. コピペ互換フィールド `name, ward, period, time, venue, price, description, official_url, url, source, image` を壊さない。
9. 掲載判断に迷うイベントは落とすのではなく、子連れ適性Cとして注意点を `family_fit.reason` に書けるか検討する。
10. 全23区の探索が完了していなければ本番データとして提出しない。

## 区ごとの探索手順

各区について以下を順に確認する。

### A. 公式系
- 区公式イベントカレンダー
- 区観光協会
- 区の子育て/文化/公園ページ
- 区立文化施設、図書館、児童館等

### B. 東京都・都立施設
- 東京都公式イベント
- こども向け都施策
- 都立公園
- 博物館、美術館、科学館、動物園等

### C. 子育て・イベント媒体
- 子ども/親子向けイベント媒体
- 地域イベント媒体

### D. 施設・企業公式
- 商業施設
- 鉄道・交通
- スポーツ施設/クラブ
- 劇場・ホール
- 大学/専門施設

### E. Web横断検索
最低限、区名と対象日を入れ、以下の語を組み合わせて検索する。
- 子供 / 子ども / 親子
- イベント
- 祭り / お祭り / フェス
- ワークショップ / 体験
- 無料
- スタンプラリー
- 鉄道 / 電車
- 動物
- 科学
- 防災 / 消防

## 子連れ適性

- A: 幼児・小学生向け要素が明確。親子参加を強く勧めやすい
- B: 子連れ参加しやすいが主目的は家族向けとは限らない
- C: 条件付き。年齢、混雑、時間帯、内容等に注意が必要

必ず短い `family_fit.reason` を付ける。

## 重複判定

次を併用する。
- official_urlの正規化
- nameの正規化
- date_start/date_end
- venue

媒体違いの同一イベントは統合し、公式情報を優先する。

## coverage

各区について最低限:

```json
{
  "ward": "中野区",
  "status": "checked",
  "queries": 12,
  "sources_checked": 8,
  "candidate_count": 14,
  "published_count": 9,
  "note": "区公式、観光、主要施設、媒体、横断検索まで確認"
}
```

週全体で:

```json
{
  "sources_checked": 123,
  "candidate_count": 240,
  "duplicate_removed": 55,
  "excluded_count": 62,
  "published_count": 123,
  "wards": []
}
```

`published_count` は実際の `events.length` と一致させる。

## event JSON

```json
{
  "id": "2026-10-10-nakano-example",
  "ward": "中野区",
  "name": "イベント名",
  "url": "https://...",
  "official_url": "https://...",
  "source": "https://...",
  "image": null,
  "period": "10/10〜10/11",
  "date_start": "2026-10-10",
  "date_end": "2026-10-11",
  "time": "10:00〜16:00",
  "venue": "会場名",
  "price": "無料",
  "description": "子連れ利用者が内容を判断できる簡潔な説明",
  "categories": ["祭り","体験"],
  "family_fit": {"grade":"A","reason":"子ども向け体験と縁日あり","age":"幼児〜小学生"},
  "reservation": {"required": false, "note": ""},
  "indoor_outdoor": "outdoor",
  "ai": {"checked_at":"2026-10-06T07:00:00+09:00","confidence":"high","discovery_query":"中野区 10月10日 子ども イベント"}
}
```

## 最終監査

出力前に必ず確認する。

- [ ] 23/23区がchecked
- [ ] 対象週末外のイベントが混じっていない
- [ ] 23区外が混じっていない
- [ ] 同一イベント重複なし
- [ ] 必須URL確認済み
- [ ] published_count = events.length
- [ ] コピペ互換フィールドが存在
- [ ] 不明情報を推測で補完していない

その後 `python tools/validate_data.py --strict site/data` と `npm test` を通してから公開する。
