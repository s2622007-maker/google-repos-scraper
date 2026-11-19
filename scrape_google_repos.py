"""GitHub の google 組織のリポジトリ情報をスクレイピングして SQLite に保存する。

取得項目: リポジトリ名 / 主要な言語 / スター数
※ GitHub API は使わず、HTML をスクレイピングする。
"""
import json
import re
import sqlite3
import time

import requests
from bs4 import BeautifulSoup

ORG = "google"
BASE_URL = f"https://github.com/orgs/{ORG}/repositories"
DB_PATH = "google_repos.db"
HEADERS = {"User-Agent": "Mozilla/5.0 (scraping practice for class)"}


def init_db(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            language TEXT,
            stars INTEGER
        )
        """
    )
    conn.commit()


def parse_star_count(text):
    """'1.2k' や '12,345' のような表記を整数にする。"""
    text = text.strip().lower().replace(",", "")
    m = re.match(r"^([\d.]+)\s*([km]?)$", text)
    if not m:
        return None
    num = float(m.group(1))
    return int(num * {"": 1, "k": 1000, "m": 1000000}[m.group(2)])


def parse_embedded_json(soup):
    """ページ埋め込みの JSON(React 版 UI)からリポジトリ情報を探す。"""
    repos = []
    for script in soup.find_all("script", {"type": "application/json"}):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                star_key = next(
                    (k for k in ("starsCount", "stargazerCount", "stargazersCount") if k in cur),
                    None,
                )
                if "name" in cur and star_key:
                    lang = cur.get("primaryLanguage") or cur.get("language")
                    if isinstance(lang, dict):
                        lang = lang.get("name")
                    repos.append(
                        {
                            "name": cur["name"],
                            "language": lang,
                            "stars": cur[star_key],
                        }
                    )
                else:
                    stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    return repos


def parse_html(soup):
    """従来の HTML 版(リポジトリ一覧の各行)からリポジトリ情報を探す。"""
    repos = []
    for a in soup.select(f'a[href^="/{ORG}/"][itemprop="name codeRepository"]'):
        name = a.get_text(strip=True)
        row = a.find_parent("li") or a.find_parent("div")
        lang_tag = row.select_one('[itemprop="programmingLanguage"]') if row else None
        star_tag = row.select_one('a[href$="/stargazers"]') if row else None
        repos.append(
            {
                "name": name,
                "language": lang_tag.get_text(strip=True) if lang_tag else None,
                "stars": parse_star_count(star_tag.get_text()) if star_tag else None,
            }
        )
    return repos


def scrape_page(page):
    res = requests.get(BASE_URL, params={"page": page}, headers=HEADERS, timeout=30)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    return parse_embedded_json(soup) or parse_html(soup)


def save(conn, repos):
    conn.executemany(
        """
        INSERT INTO repositories (name, language, stars)
        VALUES (:name, :language, :stars)
        ON CONFLICT(name) DO UPDATE SET
            language = excluded.language,
            stars = excluded.stars
        """,
        repos,
    )
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    page = 1
    seen = set()
    while True:
        repos = scrape_page(page)
        new = [r for r in repos if r["name"] not in seen]
        if not new:  # 新しいリポジトリが無ければ最終ページ
            if page == 1:
                print("1件も取得できませんでした(ページ構造が想定と違う可能性があります)")
            break
        seen.update(r["name"] for r in new)
        save(conn, new)
        print(f"page {page}: {len(new)} repos saved (total {len(seen)})")
        page += 1
        time.sleep(1)  # サーバーに負荷をかけないよう必ず待つ

    print("\n--- SELECT 結果 ---")
    for row in conn.execute(
        "SELECT name, language, stars FROM repositories ORDER BY stars DESC"
    ):
        print(row)
    conn.close()


if __name__ == "__main__":
    main()
