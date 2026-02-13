import re
import requests
import streamlit as st
from requests import RequestException
from bs4 import BeautifulSoup, FeatureNotFound
from urllib.parse import urljoin

BASE = "https://jahis.law.nagoya-u.ac.jp"

_META_LINE_RE = re.compile(
    r"^(豕穂ｻ､繝・・繧ｿ繝吶・繧ｹ|譌･譛ｬ遐皮ｩｶ縺ｮ縺溘ａ縺ｮ豁ｴ蜿ｲ諠・ｱ|譛ｬ繝・・繧ｿ繝吶・繧ｹ縺ｫ縺､縺・※|豐ｿ髱ｩ|髢｢騾｣豕戊ｦ楯繝ｪ繝ｳ繧ｯ|蟇ｩ隴ｰ邨碁℃|"
    r"蝗ｽ遶句嵜莨壼峙譖ｸ鬢ｨ.*|蝗ｽ遶句・譁・嶌鬢ｨ.*|譌･譛ｬ豕穂ｻ､邏｢蠑怖豕穂ｻ､逡ｪ蜿ｷ:?.*|蜈ｬ蟶・ｹｴ譛域律:?.*|豕穂ｻ､縺ｮ蠖｢蠑・?.*|蜈ｬ蟶・?.*|謾ｹ豁｣蟇ｾ雎｡豕穂ｻ､)$"
)


def _clean_law_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        t = line.strip()
        if not t:
            continue
        if t in {"-", "窶・", "窶・"}:
            continue
        if _META_LINE_RE.match(t):
            continue
        lines.append(t)
    return "\n".join(lines).strip()


@st.cache_data(show_spinner=False)
def fetch_html(url: str):
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        try:
            return BeautifulSoup(res.content, "lxml")
        except FeatureNotFound:
            # Fallback to built-in parser when lxml isn't installed
            return BeautifulSoup(res.content, "html.parser")
    except RequestException:
        return None


@st.cache_data(show_spinner=False)
def get_law_history_items(law_url: str):
    """
    Extract history items from the law page.
    Each item: {"kind": "改正"/"廃止"/"全改", "url": full_url, "title": link_text}
    """
    soup = fetch_html(law_url)

    items = []
    if soup is None:
        return items

    history_section = soup.find(id="law-history") or soup.find(class_="law-history")

    if history_section is not None:
        for li in history_section.find_all("li"):
            kind = None
            label = li.find("span")
            if label:
                kind = label.get_text(strip=True).replace(":", "").replace("：", "")
                if kind:
                    kind = kind.replace("全改", "全改")
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


def search_law_by_name(name: str):
    """
    Search law pages by name on the law database.
    Returns list of {"title": str, "url": str}.
    """
    if not name:
        return []

    results = []

    # 1) Try to discover a search form on the site
    seed_urls = [f"{BASE}/lawdb", f"{BASE}/lawdb/", f"{BASE}/"]
    for seed in seed_urls:
        soup = fetch_html(seed)
        if soup is None:
            continue

        for form in soup.find_all("form"):
            action = form.get("action") or seed
            method = (form.get("method") or "get").lower()
            inputs = form.find_all("input")

            text_input = None
            params = {}
            for inp in inputs:
                itype = (inp.get("type") or "").lower()
                name_attr = inp.get("name") or ""
                value = inp.get("value") or ""
                if itype in {"hidden"} and name_attr:
                    params[name_attr] = value
                if itype in {"text", "search"} and name_attr and text_input is None:
                    text_input = name_attr

            if text_input is None:
                # fallback: pick a likely name
                for inp in inputs:
                    name_attr = (inp.get("name") or "").lower()
                    if any(k in name_attr for k in ["keyword", "search", "query", "word", "free", "name"]):
                        text_input = inp.get("name")
                        break

            if text_input is None:
                continue

            params[text_input] = name
            target = urljoin(BASE, action)

            try:
                if method == "post":
                    res = requests.post(target, data=params, timeout=10)
                else:
                    res = requests.get(target, params=params, timeout=10)
                res.raise_for_status()
                soup2 = BeautifulSoup(res.content, "lxml")
            except Exception:
                continue

            for a in soup2.find_all("a", href=True):
                href = a["href"]
                text = (a.get_text() or "").strip()
                if not href.startswith("/lawdb/l/"):
                    continue
                results.append({"title": text, "url": urljoin(BASE, href)})

            if results:
                break
        if results:
            break

    # 2) Fallback: try common search endpoints
    if not results:
        candidates = [
            f"{BASE}/lawdb/search?keyword={name}",
            f"{BASE}/lawdb/search?key={name}",
            f"{BASE}/lawdb/search?query={name}",
            f"{BASE}/lawdb/search?word={name}",
            f"{BASE}/lawdb/search?term={name}",
            f"{BASE}/lawdb/search?search={name}",
            f"{BASE}/lawdb/search?kw={name}",
        ]
        for url in candidates:
            soup = fetch_html(url)
            if soup is None:
                continue
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = (a.get_text() or "").strip()
                if not href.startswith("/lawdb/l/"):
                    continue
                results.append({"title": text, "url": urljoin(BASE, href)})
            if results:
                break

    # de-dup by url
    seen = set()
    uniq = []
    for r in results:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        uniq.append(r)
    return uniq


@st.cache_data(show_spinner=False)
def fetch_law_text(url: str) -> str:
    """
    法令データベースページの本文を取得
    """
    soup = fetch_html(url)
    if soup is None:
        return ""

    candidates = [
        soup.find(id="law-body-original"),
        soup.find(id="law-body-wrap"),
        soup.find(class_="PromulgateBody"),
        soup.find(id="law-body"),
        soup.find(class_="law-body"),
        soup.find("div", {"class": "Main"}),
        soup,
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
    if soup is None:
        return None

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
    if soup is None:
        return None

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

    candidates.append(soup.get_text(" ", strip=True))

    for text in candidates:
        m = _ERA_YEAR_RE.search(text)
        if m:
            return f"{m.group(1)}{m.group(2)}"

    return None


@st.cache_data(show_spinner=False)
def get_law_header_info(url: str):
    """
    Extract title, law number, and promulgate date from the law page header.
    """
    soup = fetch_html(url)
    if soup is None:
        return {"title": "", "num": "", "promulgate": ""}

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
    if soup is None:
        return []

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
