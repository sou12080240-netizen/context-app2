import re
import requests
from bs4 import BeautifulSoup, FeatureNotFound
from urllib.parse import urljoin

BASE = "https://jahis.law.nagoya-u.ac.jp"


def fetch_html(url: str) -> BeautifulSoup:
    res = requests.get(url)
    res.raise_for_status()
    try:
        return BeautifulSoup(res.content, "lxml")
    except FeatureNotFound:
        # Fallback to built-in parser when lxml isn't installed
        return BeautifulSoup(res.content, "html.parser")


def get_law_history_links(law_url: str):
    """
    Extract history links from the law page.
    """
    soup = fetch_html(law_url)

    links = []

    history_section = soup.find(id="law-history") or soup.find(class_="law-history")

    if history_section is not None:
        for a in history_section.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/lawdb"):
                links.append(urljoin(BASE, href))
        return links

    # Fallback: scan all links for likely history URLs
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").strip()

        if not href.startswith("/lawdb"):
            continue

        if "history" in href or "/lawdb/h" in href or "??" in text or "??" in text:
            links.append(urljoin(BASE, href))

    # If nothing found, return empty list instead of raising
    return links


def fetch_law_text(url: str) -> str:
    """
    改正法令ページの本文を取得
    """
    soup = fetch_html(url)

    # 名古屋大学DB本文領域（構造差異に備えて複数候補）
    candidates = [
        soup.find(id="law-body"),
        soup.find(class_="law-body"),
        soup.find("div", {"class": "Main"}),
        soup
    ]

    for c in candidates:
        if c:
            return c.get_text("\n", strip=True)

    return soup.get_text("\n", strip=True)


def get_law_name(url: str):
    """
    法令名をページから抽出する。見つからなければ None を返す。
    """
    soup = fetch_html(url)

    candidates = [
        soup.find("h1"),
        soup.find("h2", class_="law-title"),
        soup.find(class_="law-title"),
        soup.find(class_="law-name"),
        soup.find(id="law-title"),
        soup.find(id="law-name"),
    ]

    for c in candidates:
        if c:
            text = c.get_text(strip=True)
            if text:
                return text

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    if title:
        # Remove common site suffixes
        for sep in [" | ", " - ", " ｜ ", " － "]:
            if sep in title:
                return title.split(sep)[0].strip()
        return title

    return None


_ERA_YEAR_RE = re.compile(r"(明治|大正|昭和|平成|令和)\s*(元年|[0-9０-９]+年)")


def get_law_era_year(url: str):
    """
    法令の年号（例: 平成9年, 令和元年）を抽出する。見つからなければ None。
    """
    soup = fetch_html(url)

    candidates = []
    for c in [
        soup.find("h1"),
        soup.find("h2", class_="law-title"),
        soup.find(class_="law-title"),
        soup.find(class_="law-name"),
        soup.find(id="law-title"),
        soup.find(id="law-name"),
    ]:
        if c:
            text = c.get_text(" ", strip=True)
            if text:
                candidates.append(text)

    if soup.title and soup.title.string:
        candidates.append(soup.title.string.strip())

    # 最後に全体テキストを候補として使う（重いので最後）
    candidates.append(soup.get_text(" ", strip=True))

    for text in candidates:
        m = _ERA_YEAR_RE.search(text)
        if m:
            return f"{m.group(1)}{m.group(2)}"

    return None
