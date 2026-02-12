import streamlit as st
import json
import re
import streamlit.components.v1 as components
from scraper import (
    get_law_history_items,
    fetch_law_text,
    get_law_name,
    get_law_era_year,
    get_amendment_anchors,
)
from parser import extract_amendment_blocks

st.set_page_config(layout="wide")

st.title("法令改正履歴ビューア")

law_url = st.text_input(
    "法令URLを入力",
    "https://jahis.law.nagoya-u.ac.jp/lawdb/l/320i0719"
)

if st.button("改正を取得"):
    with st.spinner("取得中..."):

        history_items = get_law_history_items(law_url)
        target_law_name = get_law_name(law_url)

        if target_law_name:
            st.caption(f"対象法令: {target_law_name}")
        else:
            st.warning("対象法令名を取得できませんでした。部分改正型の絞り込みが不完全になる可能性があります。")

        st.write(f"履歴リンク数: {len(history_items)}")

        for item in history_items:
            link = item["url"]
            kind = item.get("kind") or ""
            title = item.get("title") or ""
            kind_label = f"{kind}：" if kind else ""
            label = f"{kind_label}{title}" if title else f"{kind_label}{link}"

            text = fetch_law_text(link)

            amendments = extract_amendment_blocks(text)
            st.markdown(f"**{label}**")
            st.divider()

            if amendments:
                law_name = get_law_name(link)
                law_era = get_law_era_year(link)
                if law_name or law_era:
                    label = law_name or ""
                    if law_era:
                        label = f"{label}（{law_era}）" if label else law_era
                    st.caption(label)

                if target_law_name:
                    filtered = [a for a in amendments if target_law_name in a]
                else:
                    filtered = amendments

                if filtered:
                    anchors = get_amendment_anchors(link, filtered)
                    for idx, a in enumerate(filtered, start=1):
                        anchor = anchors[idx - 1] if idx - 1 < len(anchors) else None
                        display_link = f"{link}#{anchor}" if anchor else link
                        query = a.strip()
                        st.markdown(
                            f"[改正箇所{idx}へ]({display_link}){{:target=\"_blank\"}}",
                            unsafe_allow_html=True,
                        )
                        q = json.dumps(query)
                        components.html(
                            f"""
                            <div style="display:flex;gap:8px;align-items:center;margin:6px 0 10px;">
                              <button style="padding:6px 10px;border:1px solid #ccc;border-radius:6px;background:#fff;cursor:pointer;"
                                onclick="navigator.clipboard.writeText({q}); this.innerText='コピー済み'; setTimeout(()=>this.innerText='コピー', 1200);">
                                条文をコピー
                              </button>
                              <span style="font-size:12px;color:#333;">条文をクリップボードに保存します</span>
                            </div>
                            """,
                            height=40,
                        )
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
                preview = "\n".join(text.splitlines()[:10])
                st.text(preview)
                with st.expander("全文を表示"):
                    st.text(text)
