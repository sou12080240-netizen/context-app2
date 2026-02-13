import streamlit as st
import requests
import os
import textwrap
import json
import streamlit.components.v1 as components
from urllib.parse import quote
from scraper import (
    get_law_history_items,
    fetch_law_text,
    get_law_name,
    get_law_era_year,
    get_law_header_info,
    search_law_by_name,
)
from parser import (
    extract_amendment_blocks,
    is_full_amendment,
    era_to_year,
    classify_amendment,
    extract_article_numbers,
)

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

st.set_page_config(layout="wide")

st.title("法令データベース拡張機能")

query = st.text_input("法令URLまたは法令名", "")

with st.expander("表示オプション", expanded=False):
    use_year_filter = st.checkbox("改正年フィルタを使う", value=True)
    use_kind_filter = st.checkbox("改正種別フィルタを使う", value=True)
    expand_all = st.checkbox("全文を最初から展開", value=False)
    show_copy_btn = st.checkbox("条文コピーを表示", value=True)
    show_type_tag = st.checkbox("改正タイプを表示", value=True)
    show_first_flag = st.checkbox("初出改正フラグを表示", value=True)
    show_gap_info = st.checkbox("空白期間の表示", value=True)
    show_density = st.checkbox("改正密度インジケータ", value=True)

selected_candidate = None
if st.session_state.get("search_results"):
    options = st.session_state["search_results"]
    labels = [f"{r['title']} ({r['url']})" for r in options]
    st.info("候補が複数あります。候補から選択して再度『解析開始』を押してください。")
    for i, label in enumerate(labels, start=1):
        if st.button(f"{i}. {label}", key=f"cand_{i}"):
            st.session_state.selected_url = options[i - 1]["url"]
            st.session_state.run = True
            st.session_state.search_results = []
            st.rerun()
    chosen = st.selectbox("法令候補（手動選択）", labels)
    selected_candidate = options[labels.index(chosen)]["url"]


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
    law_url = ""
    law_name = ""
    if query:
        if query.strip().lower().startswith(("http://", "https://")):
            law_url = query.strip()
        else:
            law_name = query.strip()

    if not law_url and law_name:
        if selected_candidate:
            law_url = selected_candidate
        else:
            results = search_law_by_name(law_name)
            if not results:
                st.error("法令名からURLを見つけられませんでした。法令URLを直接入力してください。")
                st.stop()
            st.session_state.search_results = results
            if len(results) == 1:
                law_url = results[0]["url"]
            else:
                st.stop()

    if not law_url:
        st.error("法令URLまたは法令名を入力してください。")
        st.stop()

    st.session_state.run = True
    st.session_state.selected_url = law_url


if "run" in st.session_state and st.session_state.get("run"):
    active_url = st.session_state.get("selected_url")

    if (
        st.session_state.get("last_url") != active_url
        or "records" not in st.session_state
    ):
        st.session_state.last_url = active_url

        history_items = get_law_history_items(active_url)
        target_law_name = get_law_name(active_url)
        if not history_items:
            st.session_state.records = []
            st.session_state.target_law_name = target_law_name
            st.error("法令データベースに接続できませんでした。ネットワーク/DNSを確認して再試行してください。")
            st.stop()
        target_header = get_law_header_info(active_url)

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

    records = st.session_state.get("records", [])
    target_law_name = st.session_state.get("target_law_name")
    target_header = st.session_state.get("target_header", {})

    years = [era_to_year(r.get("era")) for r in records if era_to_year(r.get("era"))]
    year_range = None
    if use_year_filter and years:
        min_year, max_year = min(years), max(years)
        year_range = st.slider("表示年範囲", min_year, max_year, (min_year, max_year))

    kind_selected = None
    if use_kind_filter:
        kind_selected = st.multiselect("種別", ["改正", "廃止", "全改"], default=["改正", "廃止", "全改"])

    def record_visible(rec):
        y = era_to_year(rec.get("era"))
        if year_range and y is not None:
            if y < year_range[0] or y > year_range[1]:
                return False
        if kind_selected is not None:
            k = rec.get("kind") or "改正"
            if k not in kind_selected:
                return False
        return True

    filtered_records = [r for r in records if record_visible(r)]

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
        target_text = fetch_law_text(st.session_state.get("last_url"))
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

    col1, col2 = st.columns([2.5, 1.5])

    with col1:
        timeline = [f"{r['era']}　{r['title']}" for r in filtered_records if r["era"]]
        if timeline:
            st.subheader("改正年表")
            st.text("\n".join(timeline))
            if show_gap_info:
                years_sorted = sorted({era_to_year(r.get("era")) for r in filtered_records if era_to_year(r.get("era"))})
                for i in range(len(years_sorted) - 1):
                    gap = years_sorted[i + 1] - years_sorted[i]
                    if gap >= 5:
                        st.info(f"この期間 {gap}年間改正なし")
            st.divider()

        if show_density:
            decade_counts = {}
            for r in filtered_records:
                y = era_to_year(r.get("era"))
                if y is None:
                    continue
                decade = (y // 10) * 10
                decade_counts[decade] = decade_counts.get(decade, 0) + 1
            if decade_counts:
                st.subheader("この年代は改正集中期")
                max_count = max(decade_counts.values())
                for decade in sorted(decade_counts):
                    st.caption(f"{decade}年代")
                    st.progress(decade_counts[decade] / max_count)
                st.divider()

        seen_articles = set()

        for rec in filtered_records:
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

                        # 部分改正型の条文コピーは非表示

                        if show_type_tag:
                            st.caption(f"改正タイプ: {classify_amendment(a)}")

                        if show_first_flag:
                            nums = extract_article_numbers(a)
                            new_nums = [n for n in nums if n not in seen_articles]
                            if new_nums:
                                st.caption("🆕初出改正")
                            seen_articles.update(nums)


                        if expand_all:
                            st.markdown(
                                f"<pre style='white-space: pre-wrap; word-break: break-word; margin: 0;'>{a}</pre>",
                                unsafe_allow_html=True,
                            )
                        else:
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
                    if expand_all:
                        st.text(rec["text"])
                    else:
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

            st.markdown(
                f"[関連論文（CiNii）](https://cir.nii.ac.jp/all?q={quote(target_law_name)})"
            )
            st.markdown(
                f"[関連論文（J-STAGE）](https://www.jstage.jst.go.jp/result/global/-char/ja?globalSearchKey={quote(target_law_name)})"
            )
            st.markdown(
                f"[国立国会図書館デジタルコレクション 簡易検索](https://dl.ndl.go.jp/search/searchResult?searchWord={quote(target_law_name)})"
            )

            egov = build_egov_search_link(target_law_name)
            if egov:
                st.subheader("現行法確認")
                st.markdown(f"[e-Gov法令検索]({egov})")
                st.caption(f"検索キーワード: {target_law_name}")
        else:
            st.info("対象法令名が取得できないため、外部リンクを表示できません。")
