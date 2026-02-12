import streamlit as st
from scraper import get_law_history_links, fetch_law_text, get_law_name, get_law_era_year
from parser import extract_amendment_blocks

st.set_page_config(layout="wide")

st.title("法令改正抽出ビューア")

law_url = st.text_input(
    "法令URLを入力",
    "https://jahis.law.nagoya-u.ac.jp/lawdb/l/320i0719"
)

if st.button("改正を解析"):
    with st.spinner("解析中…"):

        history_links = get_law_history_links(law_url)

        st.write(f"沿革リンク数: {len(history_links)}")

        for link in history_links:
            st.divider()
            st.markdown(f"### 🔗 {link}")

            text = fetch_law_text(link)

            amendments = extract_amendment_blocks(text)

            if amendments:
                law_name = get_law_name(link)
                law_era = get_law_era_year(link)
                if law_name or law_era:
                    label = law_name or ""
                    if law_era:
                        label = f"{label}（{law_era}）" if label else law_era
                    st.caption(label)
                for a in amendments:
                    st.code(a, language="text")
            else:
                # 全文改正型（例：昭和21勅令70号）
                st.info("全文改正型 → 全文表示")
                st.text(text[:2000])
