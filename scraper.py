import re
import requests
from bs4 import BeautifulSoup, FeatureNotFound
from urllib.parse import urljoin

BASE = "https://jahis.law.nagoya-u.ac.jp"

_META_LINE_RE = re.compile(
    r"^(法令データベース|日本研究のための歴史情報|本データベースについて|沿革|関連法規|リンク|審議経過|"
    r"国立国会図書館.*|国立公文書館.*|日本法令索引|法令番号:?.*|公布年月日:?.*|法令の形式:?.*|公布:?.*|改正対象法令)$"
)


def _clean_law_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        t = line.strip()
        if not t:
            continue
        if t in {"-", "—", "―"}:
            continue
        if _META_LINE_RE.match(t):
            continue
        lines.append(t)
    return "\n".join(lines).strip()


def fetch_html(url: str) -> BeautifulSoup:
    res = requests.get(url)
    res.raise_for_status()
    try:
        return BeautifulSoup(res.content, "lxml")
    except FeatureNotFound:
        # Fallback to built-in parser when lxml isn't installed
        return BeautifulSoup(res.content, "html.parser")


def get_law_history_items(law_url: str):
    """
    Extract history items from the law page.
    Each item: {"kind": "改正"/"廃止", "url": full_url, "title": link_text}
    """
    soup = fetch_html(law_url)

    items = []

    history_section = soup.find(id="law-history") or soup.find(class_="law-history")

    if history_section is not None:
        for li in history_section.find_all("li"):
            kind = None
            label = li.find("span")
            if label:
                kind = label.get_text(strip=True).replace(":", "").replace("：", "")
            a = li.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if not href.startswith("/lawdb"):
                continue
            items.append(
                {
                    "kind": kind or "",
                    "url": urljoin(BASE, href),
                    "title": a.get_text(strip=True),
                }
            )
        return items

    # Fallback: scan all links for likely history URLs
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").strip()

        if not href.startswith("/lawdb"):
            continue

        if "history" in href or "/lawdb/h" in href or "改正" in text or "廃止" in text:
            items.append(
                {
                    "kind": "",
                    "url": urljoin(BASE, href),
                    "title": text,
                }
            )

    return items


def fetch_law_text(url: str) -> str:
    """
    改正法令ページの本文を取得
    """
    soup = fetch_html(url)

    # 名古屋大学DB本文領域（構造差異に備えて複数候補）
    candidates = [
        soup.find(id="law-body-original"),
        soup.find(id="law-body-wrap"),
        soup.find(class_="PromulgateBody"),
        soup.find(id="law-body"),
        soup.find(class_="law-body"),
        soup.find("div", {"class": "Main"}),
        soup
    ]

    for c in candidates:
        if c:
            text = c.get_text("\n", strip=True)
            return _clean_law_text(text)

    return _clean_law_text(soup.get_text("\n", strip=True))


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


def get_law_header_info(url: str):
    """
    Extract title, law number, and promulgate date from the law page header.
    """
    soup = fetch_html(url)

    title = ""
    num = ""
    promulgate = ""

    title_tag = soup.find("div", class_="title fw-bold")
    if title_tag:
        title = title_tag.get_text(strip=True)
    else:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    num_tag = soup.find("div", class_="num")
    if num_tag:
        num = num_tag.get_text(" ", strip=True).replace("法令番号:", "").strip()

    prom_tag = soup.find("div", class_="promulgate")
    if prom_tag:
        promulgate = prom_tag.get_text(" ", strip=True).replace("公布年月日:", "").strip()

    return {"title": title, "num": num, "promulgate": promulgate}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _pick_anchor_text(block: str) -> str:
    for line in block.splitlines():
        t = line.strip()
        if t:
            return t
    return block.strip()


def get_amendment_anchors(url: str, amendment_blocks):
    """
    Return a list of fragment ids/names for each amendment block.
    Best-effort: find an element containing a key phrase from the block
    that has id/name, or a parent with id. Returns None for not found.
    """
    soup = fetch_html(url)

    tags = ["a", "span", "div", "p", "li", "h1", "h2", "h3", "h4", "h5", "h6"]
    candidates = []
    for tag in soup.find_all(tags):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        anchor = tag.get("id") or tag.get("name")
        parent = tag.find_parent(attrs={"id": True})
        parent_id = parent.get("id") if parent else None
        candidates.append((text, anchor, parent_id))

    results = []
    for block in amendment_blocks:
        key = _pick_anchor_text(block)
        key = _normalize_text(key)[:60]
        found = None
        if key:
            for text, anchor, parent_id in candidates:
                if key and key in _normalize_text(text):
                    found = anchor or parent_id
                    if found:
                        break
        results.append(found)

    return results
