import streamlit as st
import requests
from urllib.parse import quote
from scraper import get_law_history_items, fetch_law_text, get_law_name, get_law_era_year
from parser import extract_amendment_blocks, is_full_amendment

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


def build_egov_search_link(law_name: str):
    if not law_name:
        return None
    return (
        "https://elaws.e-gov.go.jp/search/elawsSearch/"
        f"elaws_search/lsg0500/search?keyword={quote(law_name)}"
    )

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
        timeline = [f"{r['era']}　{r['title']}" for r in records if r["era"]]
        if timeline:
            st.subheader("改正年表")
            st.text("\n".join(timeline))
            st.divider()

        for rec in records:
            kind_label = f"{rec['kind']}：" if rec["kind"] else ""
            st.subheader(rec["era"] or "年不明")
            st.caption(f"{kind_label}{rec['title']}")
            st.markdown(f"[法令DBを開く]({rec['url']})")

            if rec["amendments"]:
                if target_law_name:
                    filtered = [a for a in rec["amendments"] if target_law_name in a]
                else:
                    filtered = rec["amendments"]

                if filtered:
                    for a in filtered:
                        lines = a.splitlines()
                        preview = "\n".join(lines[:10])
                        st.markdown(
                            f"<pre style='white-space: pre-wrap; word-break: break-word; margin: 0;'>{preview}</pre>",
                            unsafe_allow_html=True,
                        )
                        if len(lines) > 10:
                            with st.expander("全文を表示"):
                                st.markdown(
                                    f"<pre style='white-space: pre-wrap; word-break: break-word; margin: 0;'>{a}</pre>",
                                    unsafe_allow_html=True,
                                )
                else:
                    st.info("対象法令名が含まれる条文が見つかりませんでした。")
            else:
                if is_full_amendment(rec["text"]):
                    st.error("制度転換（LEGAL RESET / 全文改正）")
                else:
                    st.info("改正指示なし")
                preview = "\n".join(rec["text"].splitlines()[:10])
                with st.container(border=True):
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

            egov = build_egov_search_link(target_law_name)
            if egov:
                st.subheader("現行法確認")
                st.markdown(f"[e-Gov法令検索]({egov})")
        else:
            st.info("対象法令名が取得できないため、外部リンクを表示できません。")
