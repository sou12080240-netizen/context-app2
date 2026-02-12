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
