# google-repos-scraper

GitHub の `google` 組織のリポジトリ情報(リポジトリ名・主要な言語・スター数)を
GitHub API を使わずにスクレイピングし、SQLite に保存するスクリプトです。

## 使い方

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scrape_google_repos.py
```

- ページ取得のたびに `time.sleep(1)` で待機します
- データは `google_repos.db` の `repositories` テーブルに保存されます
- 実行の最後に SELECT 文で保存内容を表示します
