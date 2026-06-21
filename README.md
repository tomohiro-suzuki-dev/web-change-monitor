# web-change-monitor

Webサイトの変更を定期的に検知し、Discordに通知するツールです。

## 機能

- 指定したURLのスクリーンショットを取得
- 前回との差分をハッシュ値で比較
- 変更を検知したらDiscordにスクリーンショット付きで通知
- GitHub Actionsで毎時自動実行

## 技術スタック

- Python 3.11
- Playwright（ブラウザ自動化・スクリーンショット取得）
- GitHub Actions（定期実行・状態キャッシュ）
- Discord Webhook（通知）

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 監視URLの設定

`config.yml` を編集して監視したいURLを追加してください。

```yaml
urls:
  - https://example.com
  - https://www.python.org/news/
```

### 3. Discord Webhookの設定

GitHubリポジトリの `Settings > Secrets and variables > Actions` に以下を追加：

| Secret名 | 値 |
|---|---|
| `DISCORD_WEBHOOK_URL` | DiscordチャンネルのWebhook URL |

### 4. ローカルでの実行

```bash
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
python monitor.py
```

## GitHub Actions

`.github/workflows/monitor.yml` により毎時0分に自動実行されます。
`workflow_dispatch` から手動実行も可能です。

前回実行時のスクリーンショットとハッシュ値は `actions/cache` で管理されます。

## ディレクトリ構成

```
web-change-monitor/
├── monitor.py              # メインスクリプト
├── config.yml              # 監視URL設定
├── requirements.txt
├── .github/
│   └── workflows/
│       └── monitor.yml     # GitHub Actions定義
└── screenshots/            # スクリーンショット保存先（自動生成）
```
