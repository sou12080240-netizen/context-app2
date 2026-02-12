import regex as re

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
