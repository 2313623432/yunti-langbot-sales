from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_SOURCE = Path(r"C:\Users\C2023\Downloads\yuanfudao-knowledge\documents")
DEFAULT_OUTPUT = Path("outputs/yuanfudao-kb-cleaning")


@dataclass
class ProductFact:
    product_name: str
    business: str
    price: str
    subject: str
    suitable_grades: str
    course_format: str
    schedule: str
    benefits: str
    upsell_price: str
    selling_points: str
    product_intro: str
    link: str
    freshness_status: str
    risk_note: str
    source_file: str
    source_sheet: str
    source_row: int


@dataclass
class FAQEntry:
    category: str
    standard_question: str
    similar_questions: str
    standard_answer: str
    product_name: str
    suitable_grades: str
    risk_level: str
    freshness_status: str
    source_file: str
    source_sheet: str
    source_row: int


@dataclass
class TalkScript:
    scenario: str
    user_intent: str
    trigger_text: str
    recommended_reply: str
    follow_up: str
    forbidden: str
    product_name: str
    source_file: str
    source_sheet: str
    source_row: int


@dataclass
class DocumentIndex:
    file_name: str
    extension: str
    size_bytes: int
    category: str
    recommended_use: str
    cleaning_priority: str
    notes: str


def compact(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_header(value: Any) -> str:
    return compact(value).replace(" ", "").replace("\n", "")


def classify_file(path: Path) -> tuple[str, str, str, str]:
    name = path.name
    lower = name.lower()
    if "货盘" in name or "产品" in name or "介绍" in name or "在售" in name:
        return "产品事实", "产品事实表/产品说明", "P0", "优先进入主知识库，需人工确认价格、链接和有效期。"
    if "问答" in name or "常见问题" in name or "faq" in lower:
        return "FAQ", "一问一答知识", "P0", "建议整理为一问一答一条知识。"
    if "sop" in lower or "话术" in name or "私域" in name or "社群" in name or "聊天记录" in name:
        return "销售话术/SOP", "话术和流程知识", "P1", "适合按用户意图、跟进节点或场景切分。"
    if "素材" in name or "品牌" in name or "朋友圈" in name:
        return "素材/品牌", "参考素材", "P2", "先做索引，后续如需自动发图再单独做素材库。"
    if path.suffix.lower() == ".pdf":
        return "PDF资料", "长文参考", "P2", "先做索引，后续按章节抽取。"
    return "综合资料", "待人工分拣", "P2", "暂不进入主事实库。"


def read_excel_sheets(path: Path) -> dict[str, pd.DataFrame]:
    return pd.read_excel(path, sheet_name=None, header=None, dtype=object)


def row_text(row: pd.Series) -> str:
    return "\n".join(compact(v) for v in row.tolist() if compact(v))


def find_header_row(df: pd.DataFrame, required: list[str], max_scan: int = 20) -> int | None:
    for idx in range(min(max_scan, len(df))):
        headers = [normalize_header(v) for v in df.iloc[idx].tolist()]
        if all(any(req in header for header in headers) for req in required):
            return idx
    return None


def table_from_header(df: pd.DataFrame, header_row: int) -> pd.DataFrame:
    headers = [compact(v) or f"列{idx + 1}" for idx, v in enumerate(df.iloc[header_row].tolist())]
    table = df.iloc[header_row + 1 :].copy()
    table.columns = headers
    table = table.dropna(how="all")
    return table


def get_by_keywords(row: pd.Series, keywords: list[str]) -> str:
    for col, value in row.items():
        normalized = normalize_header(col)
        if any(keyword in normalized for keyword in keywords):
            return compact(value)
    return ""


def infer_subject(*texts: str) -> str:
    joined = " ".join(t for t in texts if t)
    if any(token in joined for token in ["自然拼读", "英语", "剑桥"]):
        return "英语/自然拼读"
    if any(token in joined for token in ["数学", "奥数", "思维", "原型题"]):
        return "数学/思维"
    if any(token in joined for token in ["语文", "人文", "素养", "阅读"]):
        return "语文/人文素养"
    return ""


def extract_schedule(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    hits = [
        line
        for line in lines
        if any(token in line for token in ["直播", "上课", "周", "每天", "课时", "班主任", "答疑"])
    ]
    return "\n".join(hits[:4])


def extract_benefits(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    hits = [
        line
        for line in lines
        if any(token in line for token in ["赠", "礼包", "资料", "教材", "实物", "权益", "伴学", "答疑"])
    ]
    return "\n".join(hits[:5])


def extract_upsell_price(text: str) -> str:
    match = re.search(r"后转价格[：:\s]*([^\n]+)", text)
    return compact(match.group(1)) if match else ""


def is_high_risk_text(text: str) -> bool:
    return any(token in text for token in ["价格", "元", "赠", "退款", "包邮", "链接", "名额", "活动", "后转"])


def clean_product_cargo(path: Path) -> list[ProductFact]:
    facts: list[ProductFact] = []
    for sheet_name, df in read_excel_sheets(path).items():
        header_row = find_header_row(df, ["业务", "定价"], max_scan=12)
        if header_row is None:
            continue
        table = table_from_header(df, header_row)
        last_business = ""
        last_price = ""
        for offset, row in table.iterrows():
            business = get_by_keywords(row, ["业务"]) or last_business
            price = get_by_keywords(row, ["定价"]) or last_price
            selling_points = get_by_keywords(row, ["卖点", "提炼"])
            intro = get_by_keywords(row, ["商品介绍", "介绍"])
            grades = get_by_keywords(row, ["适用人群", "适用"])
            link = get_by_keywords(row, ["链接", "url", "URL"])
            text = "\n".join([business, price, selling_points, intro, grades, link])
            if business:
                last_business = business
            if price:
                last_price = price
            if not compact(text) or (not business and not selling_points and not intro):
                continue
            facts.append(
                ProductFact(
                    product_name=business or infer_subject(text),
                    business=business,
                    price=price,
                    subject=infer_subject(business, selling_points, intro),
                    suitable_grades=grades,
                    course_format="",
                    schedule=extract_schedule(intro),
                    benefits=extract_benefits(intro + "\n" + selling_points),
                    upsell_price=extract_upsell_price(intro),
                    selling_points=selling_points,
                    product_intro=intro,
                    link=link,
                    freshness_status="待人工确认",
                    risk_note="价格、赠品、排期、链接以当前活动页/班主任/后台为准" if is_high_risk_text(text) else "",
                    source_file=path.name,
                    source_sheet=sheet_name,
                    source_row=int(offset) + 1,
                )
            )
    return facts


def clean_faq_workbook(path: Path) -> list[FAQEntry]:
    faqs: list[FAQEntry] = []
    for sheet_name, df in read_excel_sheets(path).items():
        header_row = find_header_row(df, ["问题", "回答"], max_scan=15)
        if header_row is not None:
            table = table_from_header(df, header_row)
            last_category = ""
            for offset, row in table.iterrows():
                category = get_by_keywords(row, ["类别", "分类"]) or last_category
                question = get_by_keywords(row, ["问题", "问法"])
                answer = get_by_keywords(row, ["回答", "答案", "回复"])
                if category:
                    last_category = category
                if not question or not answer:
                    continue
                risk_level = "高" if is_high_risk_text(question + answer) else "中"
                faqs.append(
                    FAQEntry(
                        category=category,
                        standard_question=question,
                        similar_questions="",
                        standard_answer=answer,
                        product_name="",
                        suitable_grades="",
                        risk_level=risk_level,
                        freshness_status="待人工确认" if risk_level == "高" else "可用",
                        source_file=path.name,
                        source_sheet=sheet_name,
                        source_row=int(offset) + 1,
                    )
                )
            continue

        # Fallback for wide SOP-style sheets: treat non-empty row blocks as talk scripts.
        for offset, row in df.dropna(how="all").iterrows():
            text = row_text(row)
            if not text or len(text) < 20:
                continue
            if any(token in text for token in ["问题", "回答", "要买", "不买", "考虑", "报名", "跟进"]):
                faqs.append(
                    FAQEntry(
                        category="表格摘录",
                        standard_question=compact(row.iloc[0])[:120],
                        similar_questions="",
                        standard_answer=text[:1200],
                        product_name="",
                        suitable_grades="",
                        risk_level="中",
                        freshness_status="待整理",
                        source_file=path.name,
                        source_sheet=sheet_name,
                        source_row=int(offset) + 1,
                    )
                )
    return faqs


def clean_talk_script_workbook(path: Path) -> list[TalkScript]:
    scripts: list[TalkScript] = []
    for sheet_name, df in read_excel_sheets(path).items():
        for offset, row in df.dropna(how="all").iterrows():
            cells = [compact(v) for v in row.tolist() if compact(v)]
            text = "\n".join(cells)
            if len(text) < 30:
                continue
            if not any(token in text for token in ["用户", "销售", "跟进", "报名", "不买", "考虑", "要买", "话术"]):
                continue
            scripts.append(
                TalkScript(
                    scenario=sheet_name,
                    user_intent=cells[0][:80] if cells else "",
                    trigger_text="\n".join(cells[:3]),
                    recommended_reply=text[:1500],
                    follow_up="",
                    forbidden="",
                    product_name="",
                    source_file=path.name,
                    source_sheet=sheet_name,
                    source_row=int(offset) + 1,
                )
            )
    return scripts


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_rag_markdown(path: Path, products: list[ProductFact], faqs: list[FAQEntry], scripts: list[TalkScript]) -> None:
    lines: list[str] = [
        "# 猿辅导知识库清洗版 RAG 导入草稿",
        "",
        "> 第一版自动清洗结果。带有“待人工确认”的价格、赠品、排期、链接不得直接作为最终承诺。",
        "",
        "## 产品事实",
    ]
    for idx, item in enumerate(products, start=1):
        lines.extend(
            [
                "",
                f"### 产品事实 {idx}: {item.product_name or item.business or '未命名产品'}",
                f"- 业务/学科: {item.business}",
                f"- 价格: {item.price}",
                f"- 适用人群: {item.suitable_grades}",
                f"- 课程安排: {item.schedule}",
                f"- 权益/赠品: {item.benefits}",
                f"- 后转价格: {item.upsell_price}",
                f"- 核心卖点: {item.selling_points}",
                f"- 商品介绍: {item.product_intro}",
                f"- 链接: {item.link}",
                f"- 风险提示: {item.risk_note}",
                f"- 来源: {item.source_file} / {item.source_sheet} / row {item.source_row}",
            ]
        )

    lines.extend(["", "## FAQ"])
    for idx, item in enumerate(faqs, start=1):
        lines.extend(
            [
                "",
                f"### FAQ {idx}: {item.standard_question}",
                f"- 类别: {item.category}",
                f"- 标准问题: {item.standard_question}",
                f"- 标准回答: {item.standard_answer}",
                f"- 风险等级: {item.risk_level}",
                f"- 时效状态: {item.freshness_status}",
                f"- 来源: {item.source_file} / {item.source_sheet} / row {item.source_row}",
            ]
        )

    lines.extend(["", "## 销售话术/SOP 摘录"])
    for idx, item in enumerate(scripts, start=1):
        lines.extend(
            [
                "",
                f"### 话术 {idx}: {item.user_intent or item.scenario}",
                f"- 场景: {item.scenario}",
                f"- 触发内容: {item.trigger_text}",
                f"- 推荐话术/流程: {item.recommended_reply}",
                f"- 来源: {item.source_file} / {item.source_sheet} / row {item.source_row}",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source
    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    documents: list[DocumentIndex] = []
    products: list[ProductFact] = []
    faqs: list[FAQEntry] = []
    scripts: list[TalkScript] = []

    for path in sorted(source.glob("*"), key=lambda item: item.name):
        if not path.is_file():
            continue
        category, recommended_use, priority, notes = classify_file(path)
        documents.append(
            DocumentIndex(
                file_name=path.name,
                extension=path.suffix.lower(),
                size_bytes=path.stat().st_size,
                category=category,
                recommended_use=recommended_use,
                cleaning_priority=priority,
                notes=notes,
            )
        )

        if path.suffix.lower() != ".xlsx":
            continue
        if "货盘" in path.name:
            products.extend(clean_product_cargo(path))
        elif "问答" in path.name or "常见问题" in path.name:
            faqs.extend(clean_faq_workbook(path))
        else:
            scripts.extend(clean_talk_script_workbook(path))

    document_rows = [asdict(item) for item in documents]
    product_rows = [asdict(item) for item in products]
    faq_rows = [asdict(item) for item in faqs]
    script_rows = [asdict(item) for item in scripts]

    pd.DataFrame(document_rows).to_csv(output / "document_inventory.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(product_rows).to_csv(output / "product_facts.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(faq_rows).to_csv(output / "faq_entries.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(script_rows).to_csv(output / "talk_scripts.csv", index=False, encoding="utf-8-sig")
    (output / "document_inventory.json").write_text(
        json.dumps(document_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "product_facts.json").write_text(
        json.dumps(product_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "faq_entries.json").write_text(
        json.dumps(faq_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "talk_scripts.json").write_text(
        json.dumps(script_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    write_jsonl(output / "rag_product_facts.jsonl", product_rows)
    write_jsonl(output / "rag_faq_entries.jsonl", faq_rows)
    write_jsonl(output / "rag_talk_scripts.jsonl", script_rows)
    write_rag_markdown(output / "rag_import_draft.md", products, faqs, scripts)

    summary = {
        "source": str(source),
        "output": str(output),
        "documents": len(document_rows),
        "product_facts": len(product_rows),
        "faq_entries": len(faq_rows),
        "talk_scripts": len(script_rows),
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
