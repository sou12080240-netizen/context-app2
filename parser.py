import regex as re

# 年号 -> 西暦変換
_ERA_BASE = {
    "明治": 1868,
    "大正": 1912,
    "昭和": 1926,
    "平成": 1989,
    "令和": 2019,
}

_ERA_YEAR_RE = re.compile(r"(明治|大正|昭和|平成|令和)\s*(元年|[0-9０-９]+)年")
_ARTICLE_NO_RE = re.compile(r"第([0-9０-９]+)条")
# 改正開始パターン（超重要）
AMEND_START = re.compile(
    r"(?:^|\n)"
    r".+?の一部を次のように改正する。"
)

# 条文単位の改正命令
ARTICLE_OP = re.compile(
    r"(第[一二三四五六七八九十百千\d]+條(?:第[一二三\d]+項)?)"
    r".*?(削る|改める|加える|削除|追加|改正)"
)

def extract_amendment_blocks(text: str):
    """
    改正法令本文から「改正指示部分」だけを抽出
    """

    results = []

    # ① 「〇〇の一部を次のように改正する。」で分割
    starts = list(AMEND_START.finditer(text))

    if not starts:
        return []

    for i, m in enumerate(starts):
        start = m.start()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)

        block = text[start:end]

        # ② 条文操作があるか確認（ノイズ除去）
        if ARTICLE_OP.search(block):
            results.append(block.strip())

    return results


def is_full_amendment(text: str) -> bool:
    """
    Best-effort detection for full amendments (全文改正).
    """
    if not text:
        return False
    if "全部を改正する" in text or "全文改正" in text:
        return True
    if "一部を次のように改正する" in text or "の一部を次のように改正する" in text:
        return False
    return False


def summarize_amendment(text: str) -> str:
    """
    Simple rule-based summary for amendment blocks.
    """
    if not text:
        return "内容変更を伴う改正。"

    t = re.sub(r"\s+", " ", text)

    if "削除" in t or "削る" in t:
        return "条文を削除した改正。"
    if "追加" in t or "加える" in t or "新設" in t:
        return "新たな規定を追加した改正。"
    if "改める" in t or "改正" in t:
        return "文言の変更を行った改正。"
    if "全部改正" in t or "全文改正" in t:
        return "法律全体を全面的に改正。"

    return "内容変更を伴う改正。"


def era_to_year(era_text: str):
    """
    和暦文字列（例: 昭和3年）を西暦に変換。失敗時は None。
    """
    if not era_text:
        return None
    m = _ERA_YEAR_RE.search(era_text)
    if not m:
        return None
    era = m.group(1)
    year_text = m.group(2)
    if year_text == "元":
        year_num = 1
    else:
        year_num = int(year_text.translate(str.maketrans("０１２３４５６７８９", "0123456789")))
    base = _ERA_BASE.get(era)
    if not base:
        return None
    return base + year_num - 1


def classify_amendment(text: str) -> str:
    """
    改正タイプの簡易分類。
    """
    if not text:
        return "不明"
    if is_full_amendment(text):
        return "全面改正"
    if "削除" in text or "削る" in text:
        return "削除型"
    if "加える" in text or "追加" in text or "新設" in text:
        return "追加型"
    if "改める" in text:
        return "文言改正型"
    # 条番号のみ変更らしい記述の簡易推定
    if _ARTICLE_NO_RE.search(text) and not any(k in text for k in ["改める", "加える", "追加", "削除", "削る"]):
        return "技術改正型"
    return "内容変更型"


def extract_article_numbers(text: str):
    """
    amendment 内の「第◯条」を抽出して数値リストを返す。
    """
    nums = []
    if not text:
        return nums
    for m in _ARTICLE_NO_RE.finditer(text):
        n = int(m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789")))
        nums.append(n)
    return nums
