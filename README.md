# 東京 週末イベント（モバイル対応Webサイト・自動更新）

`https://www.tokyofes.info/` 配下の各エリアサイト（墨田・浅草・上野公園・秋葉原・日比谷公園・池袋・
新宿・中野・代々木公園・渋谷・六本木・豊洲・お台場・品川・立川）を巡回し、
**今週末（土・日）に開催中/開催されるイベント**をカード一覧のモバイルサイトにまとめます。

PCを立ち上げていなくても、**GitHub Actionsが自動で毎週更新してGitHub Pagesに公開**します。

## 構成
| ファイル | 役割 |
|---|---|
| `scraper.py` | 各エリアサイト巡回・週末イベント抽出（標準ライブラリのみ） |
| `build_site.py` | `site/index.html` を生成（カード一覧・エリアフィルタ付き） |
| `.github/workflows/deploy.yml` | 毎週自動ビルド＆GitHub Pagesデプロイ |

## ローカルで確認する
```bash
python build_site.py --open
```
`site/index.html` が生成され、ブラウザで開きます。

## GitHub Pages 公開手順（初回のみ・要あなたの操作）
1. GitHub（`toodataa-ai` アカウント）で新しい**空のリポジトリ**を作成（例: `tokyo-weekend-events`）。
   Public / README追加なし。
2. このフォルダで:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: tokyo weekend events site"
   git branch -M main
   git remote add origin https://github.com/toodataa-ai/tokyo-weekend-events.git
   git push -u origin main
   ```
3. GitHubのリポジトリ → **Settings → Pages** → "Build and deployment" の **Source** を
   **「GitHub Actions」** に変更（これでワークフローがデプロイできるようになります）。
4. **Actions** タブでワークフローを1回手動実行（`Run workflow`）するか、mainにpushすると自動で走ります。
5. 数分後、`https://toodataa-ai.github.io/tokyo-weekend-events/` で公開されます。

## 自動更新のタイミング
`.github/workflows/deploy.yml` の `cron` で設定：
- 毎週 **金曜 09:00 JST** と **土曜 07:00 JST** に自動でスクレイピング→サイト再ビルド→再公開。
- 手動更新したい時は GitHub の Actions タブから `Run workflow`。
- タイミングを変えたい場合は cron 式（UTC基準）を編集してください。

## 注意
- 自動収集のため、日程・開催有無・中止情報は必ず各公式ページでご確認ください（サイト下部に明記）。
- GitHub Actions の無料枠内で動作します（1回数十秒・週2回程度なら十分収まります）。
- 巡回対象エリアを増減したい場合は `scraper.py` の `WARDS` 辞書を編集してください。
