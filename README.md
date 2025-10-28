# 内装見積自動化プラットフォーム

Numbersの雛形（CSV）と単価マスタCSV、現場メモJSONを取り込み、インボイス制度に準拠した見積PDFとメール草稿を自動生成するツール群です。CLIとWebアプリの両方を提供しており、社内用スクリプトから一般公開アプリまで一貫して利用できます。

## 主な機能

- 税別金額は四捨五入、税込金額は切り上げで計算する rounding ルールを実装。
- 内蔵PDFエンジンで見出し・仕切り線付きの帳票を生成（日本語テキストに対応）。
- メール草稿は To/Cc/件名/本文をテンプレート化し、ダウンロード可能なテキストとして生成。
- 軽量WSGIサーバーで動く Web UI を同梱。ファイルアップロード → ZIP ダウンロードまでブラウザで完結。
- API キーによるアクセス制御、CORSヘッダー、ヘルスチェックエンドポイントを実装。
- 環境変数ベースの設定と構造化ログ出力で運用・監視に対応。

## インストール

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### 依存ライブラリ

標準ライブラリのみで動作するため、追加インストールは不要です。

## Webアプリとして利用する

```bash
estimate-automation-web
```

- ブラウザで `http://localhost:8000/` にアクセスするとアップロードフォームが表示されます。
- API キーを設定したい場合は `export ESTIMATE_AUTOMATION_API_KEY="your-key"` を実行してください。UI と API の双方でキー入力が必須になります。
- CORS を制限したい場合は `ESTIMATE_AUTOMATION_CORS_ORIGINS` にカンマ区切りで許可ドメインを設定します。
- ヘルスチェック: `GET /healthz`
- 見積生成API: `POST /api/estimates`（multipart/form-data）

## CLI とバッチ処理

1. サンプル案件での検証

   ```bash
   python -m estimate_automation.cli samples/sample_projects.json
   ```

   `outputs/sample_runs/` に3案件分のPDFとメール草稿が生成されます。

2. 本番案件の処理

   - `config/production_template.json` をコピーし、テンプレートCSV・単価マスタCSV・現場メモJSONのパスを入力します。
   - CLI で本番設定を実行します。

   ```bash
   python -m estimate_automation.cli path/to/your_config.json
   python -m estimate_automation.cli path/to/your_config.json --project project_identifier
   ```

## セキュリティと運用

- **APIキー**: `ESTIMATE_AUTOMATION_API_KEY` を設定すると、ヘッダー `X-API-Key` もしくはフォーム入力で一致した場合のみ処理します。
- **ログ**: `ESTIMATE_AUTOMATION_LOG_LEVEL` で `DEBUG/INFO/WARNING` などを指定可能。JSON 収集基盤と連携する場合は外部ハンドラを追加してください。
- **一時ファイル**: Web アプリではアップロードしたファイルをメモリ上で処理し、ZIP 生成後に破棄するためディスクには保存されません。
- **監視**: ヘルスチェック `GET /healthz` を監視に利用できます。CI では `estimate-automation-web` を起動し応答を確認してください。
- **CI/CD 推奨**: 単体テスト (`pytest`) と `/healthz` の疎通確認をパイプラインに組み込み、APIキー・税率などは環境変数で注入します。

## サンプルデータ

`samples/` ディレクトリに Numbers からエクスポートしたCSVとメモJSONを同梱しています。Web UI でアップロードする際は以下の対応関係を利用してください。

- `samples/unit_prices.csv`
- `samples/projects/sample_a/template.csv`
- `samples/projects/sample_a/memo.json`

## 免責

生成結果の内容については十分に検証していますが、正式な帳票として利用する際は社内規定に沿ってレイアウト・文言・フォントの確認を行ってください。
