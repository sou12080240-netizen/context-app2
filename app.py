import streamlit as st
import requests
from urllib.parse import quote
from scraper import get_law_history_items, fetch_law_text, get_law_name, get_law_era_year
from parser import extract_amendment_blocks

st.set_page_config(layout="wide")

st.title("法令データベース拡張機能")

law_url = st.text_input(
    "法令URL",
    "https://jahis.law.nagoya-u.ac.jp/lawdb/l/320i0719"
)

def fetch_wikipedia(term):
    try:
        url = f"https://ja.wikipedia.org/api/rest_v1/page/summary/{term}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None

if st.button("解析開始"):
    history_items = get_law_history_items(law_url)
    target_law_name = get_law_name(law_url)

    if target_law_name:
        st.caption(f"対象法令: {target_law_name}")
    else:
        st.warning("対象法令名を取得できませんでした。部分改正型の絞り込みが不完全になる可能性があります。")

    records = []

    for item in history_items:
        text = fetch_law_text(item["url"])
        amendments = extract_amendment_blocks(text)

        records.append({
            "era": get_law_era_year(item["url"]),
            "title": item.get("title") or "",
            "url": item["url"],
            "text": text,
            "amendments": amendments,
            "kind": item.get("kind") or "",
        })

    records.sort(key=lambda x: x["era"] or "")

    col1, col2 = st.columns([3, 1])

    with col1:
        st.write(f"履歴リンク数: {len(records)}")
        for rec in records:
            kind_label = f"{rec['kind']}：" if rec["kind"] else ""
            st.subheader(rec["era"] or "年不明")
            st.caption(f"{kind_label}{rec['title']}")
            st.markdown(
                f"[法令DBを開く]({rec['url']}){{:target=\"_blank\"}}",
                unsafe_allow_html=True,
            )

            if rec["amendments"]:
                if target_law_name:
                    filtered = [a for a in rec["amendments"] if target_law_name in a]
                else:
                    filtered = rec["amendments"]

                if filtered:
                    for a in filtered:
                        lines = a.splitlines()
                        preview = "\n".join(lines[:10])
                        st.code(preview, language="text")
                        if len(lines) > 10:
                            with st.expander("全文を表示"):
                                st.code(a, language="text")
                else:
                    st.info("対象法令名が含まれる条文が見つかりませんでした。")
            else:
                st.info("全文改正型（改正条文なし）")
                preview = "\n".join(rec["text"].splitlines()[:10])
                st.text(preview)
                with st.expander("全文を表示"):
                    st.text(rec["text"])
            st.divider()

    with col2:
        st.subheader("制度解説")
        if target_law_name:
            wiki = fetch_wikipedia(target_law_name)
            if wiki and wiki.get("content_urls"):
                st.markdown(f"[Wikipedia]({wiki['content_urls']['desktop']['page']})")
            else:
                st.markdown(
                    f"[Wikipediaで検索](https://ja.wikipedia.org/wiki/{quote(target_law_name)})"
                )

            st.markdown(
                f"[コトバンクで検索](https://kotobank.jp/word/{quote(target_law_name)})",
            )
        else:
            st.info("対象法令名が取得できないため、外部リンクを表示できません。")
