import streamlit as st
import requests
import os
import textwrap
from urllib.parse import quote
from scraper import (
    get_law_history_items,
    fetch_law_text,
    get_law_name,
    get_law_era_year,
    get_law_header_info,
)
from parser import extract_amendment_blocks, is_full_amendment

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

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
    # e-Gov法令検索は2024年7月にURL変更
    return "https://laws.e-gov.go.jp/"


def _wrap_jp_line(line: str, width: int):
    if len(line) <= width:
        return [line]
    return [line[i:i + width] for i in range(0, len(line), width)]


def build_pdf_bytes(title: str, text: str):
    if fitz is None:
        return None
    font_candidates = [
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\yugothm.ttc",
        r"C:\Windows\Fonts\YuMincho.ttc",
        r"C:\Windows\Fonts\yumin.ttf",
    ]
    fontfile = next((p for p in font_candidates if os.path.exists(p)), None)

    doc = fitz.open()
    page = doc.new_page()

    font_size = 10
    lineheight = 12
    margin = 36

    max_lines = int((page.rect.height - margin * 2) / lineheight)

    lines = []
    if title:
        lines.append(title)
        lines.append("")

    for raw in text.splitlines():
        if not raw.strip():
            lines.append("")
        else:
            lines.extend(_wrap_jp_line(raw, width=40))

    for i in range(0, len(lines), max_lines):
        if i > 0:
            page = doc.new_page()
        y = margin
        if fontfile:
            page.insert_font(fontname="JP", fontfile=fontfile)
        for line in lines[i:i + max_lines]:
            page.insert_text(
                (margin, y),
                line,
                fontsize=font_size,
                fontname="JP" if fontfile else "helv",
            )
            y += lineheight

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


if st.button("解析開始"):
    st.session_state.run = True
    st.session_state.last_url = law_url

    history_items = get_law_history_items(law_url)
    target_law_name = get_law_name(law_url)
    target_header = get_law_header_info(law_url)

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
            "header": get_law_header_info(item["url"]),
        })

    records.sort(key=lambda x: x["era"] or "")

    st.session_state.records = records
    st.session_state.target_law_name = target_law_name
    st.session_state.target_header = target_header

if "run" in st.session_state and st.session_state.get("run"):
    records = st.session_state.get("records", [])
    target_law_name = st.session_state.get("target_law_name")
    target_header = st.session_state.get("target_header", {})

    if target_law_name:
        st.caption(f"対象法令: {target_law_name}")
    else:
        st.warning("対象法令名を取得できませんでした。部分改正型の絞り込みが不完全になる可能性があります。")

    if target_header:
        title = target_header.get("title") or ""
        num = target_header.get("num") or ""
        promulgate = target_header.get("promulgate") or ""
        st.markdown(
            f"""
<div style="font-size:22px;font-weight:700;">{title}</div>
<div style="font-size:18px;">法令番号: {num}</div>
<div style="font-size:18px;">公布年月日: {promulgate}</div>
""",
            unsafe_allow_html=True,
        )
        # 目的の法令本文の取得とダウンロード
        target_text = fetch_law_text(st.session_state.get("last_url", law_url))
        if target_text:
            st.download_button(
                "テキストでダウンロード",
                data=target_text,
                file_name=f"{title or 'law'}.txt",
                mime="text/plain",
            )
            target_pdf = build_pdf_bytes(title, target_text)
            if target_pdf:
                st.download_button(
                    "PDFでダウンロード",
                    data=target_pdf,
                    file_name=f"{title or 'law'}.pdf",
                    mime="application/pdf",
                )

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
            header = rec.get("header") or {}
            if header:
                title = header.get("title") or ""
                num = header.get("num") or ""
                promulgate = header.get("promulgate") or ""
                st.markdown(
                    f"""
<div style="font-size:20px;font-weight:700;">{title}</div>
<div style="font-size:16px;">法令番号: {num}</div>
<div style="font-size:16px;">公布年月日: {promulgate}</div>
""",
                    unsafe_allow_html=True,
                )
            st.markdown(f"[法令DBを開く]({rec['url']})")

            if rec["text"]:
                txt_name = f"{rec['title'] or 'law'}.txt"
                st.download_button(
                    "テキストでダウンロード",
                    data=rec["text"],
                    file_name=txt_name,
                    mime="text/plain",
                )

                pdf_bytes = build_pdf_bytes(rec["title"], rec["text"])
                if pdf_bytes:
                    st.download_button(
                        "PDFでダウンロード",
                        data=pdf_bytes,
                        file_name=f"{rec['title'] or 'law'}.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.info("PDF出力には PyMuPDF が必要です。requirements.txt に PyMuPDF を追加してください。")

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
                st.caption(f"検索キーワード: {target_law_name}")
        else:
            st.info("対象法令名が取得できないため、外部リンクを表示できません。")
