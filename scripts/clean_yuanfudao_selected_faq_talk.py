from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from clean_yuanfudao_faq_talk import (
    IntentKeyword,
    SOPNode,
    StandardFAQ,
    TalkScript,
    compact,
    extract_ai_sales_workbook,
    extract_course_faq,
    extract_natural_phonics_mixed,
    extract_private_domain_sop,
    infer_product,
    is_question_like,
    risk_level,
)


DEFAULT_OUTPUT = Path("outputs/yuanfudao-selected-faq-talk-cleaning")
DEFAULT_PATHS = [
    Path(r"C:\Users\C2023\Downloads\奥数思维社群话术.md"),
    Path(r"C:\Users\C2023\Downloads\自然拼读卖点话术更新.md"),
    Path(r"C:\Users\C2023\Downloads\剑桥英语卖点&话术.md"),
    Path(r"C:\Users\C2023\Downloads\自拼TMK 话术.md"),
    Path(r"C:\Users\C2023\Downloads\自然拼读-产品培训文档-26.3.11.md"),
    Path(r"C:\Users\C2023\Downloads\学科语数英课程话术_卖点.md"),
    Path(r"C:\Users\C2023\Downloads\学科TMK参考话术.md"),
    Path(r"C:\Users\C2023\Downloads\学科私转推课话术 sop.xlsx"),
    Path(
        r"C:\Users\C2023\AppData\Roaming\LarkShell\sdk_storage\368cae5d95e02fb4259fa5b6c48bd254\resources\files\猿辅导自然拼读常见问题(1).xlsx"
    ),
    Path(
        r"C:\Users\C2023\AppData\Roaming\LarkShell\sdk_storage\368cae5d95e02fb4259fa5b6c48bd254\resources\files\猿辅导课程问答整理.xlsx"
    ),
]


@dataclass
class SourceInventory:
    file_name: str
    full_path: str
    extension: str
    size_bytes: int
    source_type: str
    extraction_note: str


@dataclass
class MarkdownSection:
    source_file: str
    section_title: str
    product: str
    section_type: str
    content: str
    suggested_use: str
    priority: str
    status: str
    source_line: int


def detect_script_type(path: Path) -> str:
    name = path.name
    if "社群" in name:
        return "社群话术"
    if "TMK" in name or "tmk" in name.lower():
        return "TMK话术"
    if "培训" in name:
        return "培训文档摘录"
    if "卖点" in name:
        return "卖点话术"
    return "Markdown话术"


def detect_section_type(title: str, content: str) -> str:
    text = title + "\n" + content
    if any(token in text for token in ["FAQ", "问答", "常见问题", "问题"]):
        return "FAQ候选"
    if any(token in text for token in ["异议", "不买", "考虑", "拒绝", "没时间", "太贵"]):
        return "异议处理"
    if any(token in text for token in ["卖点", "优势", "亮点", "痛点"]):
        return "卖点话术"
    if any(token in text for token in ["SOP", "流程", "步骤", "跟进"]):
        return "SOP/流程"
    return "话术段落"


def priority_for_section(section_type: str, content: str) -> str:
    if section_type in {"FAQ候选", "异议处理", "SOP/流程"}:
        return "P0"
    if any(token in content for token in ["退款", "价格", "赠", "名额", "包邮", "链接"]):
        return "P0"
    if section_type == "卖点话术":
        return "P1"
    return "P2"


def markdown_blocks(text: str) -> list[tuple[str, str, int]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[tuple[str, str, int]] = []
    current_title = "全文开头"
    current: list[str] = []
    current_line = 1

    def flush() -> None:
        nonlocal current
        content = compact("\n".join(current))
        if content:
            blocks.append((current_title, content, current_line))
        current = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        bold_heading = re.match(r"^\*\*(.+?)\*\*\s*$", stripped)
        plain_heading = (
            len(stripped) <= 40
            and not stripped.endswith(("。", "，", "；", ",", "."))
            and any(token in stripped for token in ["卖点", "话术", "问题", "流程", "异议", "介绍", "痛点"])
        )
        if heading_match or bold_heading or (plain_heading and len(current) >= 2):
            flush()
            current_title = compact(heading_match.group(2) if heading_match else bold_heading.group(1) if bold_heading else stripped)
            current_line = idx
            continue
        current.append(line)
    flush()

    if len(blocks) <= 1:
        # Fallback: split long markdown by blank paragraphs.
        paragraphs = [compact(p) for p in re.split(r"\n\s*\n", text) if compact(p)]
        blocks = []
        for idx, paragraph in enumerate(paragraphs, start=1):
            if len(paragraph) >= 40:
                blocks.append((f"段落 {idx}", paragraph, idx))
    return blocks


def extract_markdown(path: Path) -> tuple[list[MarkdownSection], list[TalkScript], list[StandardFAQ]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    sections: list[MarkdownSection] = []
    scripts: list[TalkScript] = []
    faqs: list[StandardFAQ] = []
    script_type = detect_script_type(path)

    for title, content, line_no in markdown_blocks(text):
        if len(content) < 30:
            continue
        section_type = detect_section_type(title, content)
        product = infer_product(path.name, title, content)
        priority = priority_for_section(section_type, content)
        status = "待人工确认" if risk_level(content) == "高" else "待整理"
        sections.append(
            MarkdownSection(
                source_file=path.name,
                section_title=title,
                product=product,
                section_type=section_type,
                content=content[:5000],
                suggested_use="可转为话术/SOP知识" if priority in {"P0", "P1"} else "参考素材",
                priority=priority,
                status=status,
                source_line=line_no,
            )
        )
        scripts.append(
            TalkScript(
                script_type=script_type,
                stage=title,
                customer_intent=section_type,
                trigger_text=title,
                recommended_reply=content[:2500],
                next_action="人工确认后按场景压缩为短句客服话术",
                forbidden="避免过度承诺；价格、赠品、退款、名额、链接需人工确认",
                keywords=";".join(filter(None, [product, section_type])),
                priority=priority,
                status=status,
                source_file=path.name,
                source_sheet="Markdown",
                source_row=line_no,
            )
        )

        lines = [compact(line) for line in content.split("\n") if compact(line)]
        for idx, line in enumerate(lines):
            if not is_question_like(line):
                continue
            answer_parts: list[str] = []
            for follow in lines[idx + 1 : idx + 5]:
                if is_question_like(follow) or len("\n".join(answer_parts)) > 800:
                    break
                answer_parts.append(follow)
            answer = compact("\n".join(answer_parts))
            if len(answer) < 10:
                continue
            qa_text = line + "\n" + answer
            faqs.append(
                StandardFAQ(
                    category=f"Markdown候选 / {section_type}",
                    product=product,
                    question=line[:240],
                    similar_questions="",
                    answer=answer[:1500],
                    answer_style="原文摘录",
                    risk_level=risk_level(qa_text),
                    status="待人工确认",
                    source_file=path.name,
                    source_sheet="Markdown",
                    source_row=line_no,
                )
            )
    return sections, scripts, faqs


def write_rows(output: Path, name: str, rows: list[dict[str, Any]]) -> None:
    (output / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(rows).to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
    with (output / f"{name}.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_rag_markdown(
    output: Path,
    faqs: list[StandardFAQ],
    scripts: list[TalkScript],
    sop_nodes: list[SOPNode],
    sections: list[MarkdownSection],
) -> None:
    lines = [
        "# 猿辅导单独话术 FAQ 文件整合草稿",
        "",
        "> 来源为用户本次单独拉出的 Markdown / Excel 文件。产品事实未纳入本草稿。",
        "",
        "## 标准 FAQ 与 FAQ 候选",
    ]
    for idx, item in enumerate(faqs, start=1):
        lines.extend(
            [
                "",
                f"### FAQ {idx}: {item.question}",
                f"- 类别: {item.category}",
                f"- 产品: {item.product}",
                f"- 回答: {item.answer}",
                f"- 风险等级: {item.risk_level}",
                f"- 状态: {item.status}",
                f"- 来源: {item.source_file} / {item.source_sheet} / row {item.source_row}",
            ]
        )
    lines.extend(["", "## SOP 节点"])
    for idx, item in enumerate(sop_nodes, start=1):
        lines.extend(
            [
                "",
                f"### SOP {idx}: {item.node}",
                f"- 触发条件: {item.trigger_condition}",
                f"- 客户表达: {item.customer_expression}",
                f"- 推荐动作: {item.recommended_action}",
                f"- 推荐话术: {item.recommended_script}",
                f"- 禁忌: {item.forbidden_script}",
                f"- 来源: {item.source_file} / {item.source_sheet} / row {item.source_row}",
            ]
        )
    lines.extend(["", "## P0/P1 话术段落"])
    for idx, item in enumerate(scripts, start=1):
        if item.priority == "P2":
            continue
        lines.extend(
            [
                "",
                f"### 话术 {idx}: {item.stage}",
                f"- 类型: {item.script_type}",
                f"- 场景/意图: {item.customer_intent}",
                f"- 推荐回复: {item.recommended_reply}",
                f"- 禁忌: {item.forbidden}",
                f"- 来源: {item.source_file} / {item.source_sheet} / row {item.source_row}",
            ]
        )
    lines.extend(["", "## Markdown 章节索引"])
    for idx, item in enumerate(sections, start=1):
        lines.extend(
            [
                "",
                f"### 章节 {idx}: {item.section_title}",
                f"- 来源: {item.source_file}",
                f"- 类型: {item.section_type}",
                f"- 优先级: {item.priority}",
                f"- 内容: {item.content[:1200]}",
            ]
        )
    (output / "selected_faq_talk_rag_draft.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--paths", nargs="*", type=Path, default=DEFAULT_PATHS)
    args = parser.parse_args()

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    inventory: list[SourceInventory] = []
    sections: list[MarkdownSection] = []
    faqs: list[StandardFAQ] = []
    scripts: list[TalkScript] = []
    sop_nodes: list[SOPNode] = []
    intent_keywords: list[IntentKeyword] = []

    for path in args.paths:
        note = ""
        source_type = "missing"
        if path.exists():
            if path.suffix.lower() == ".md":
                source_type = "markdown"
                md_sections, md_scripts, md_faqs = extract_markdown(path)
                sections.extend(md_sections)
                scripts.extend(md_scripts)
                faqs.extend(md_faqs)
                note = f"sections={len(md_sections)}, faq_candidates={len(md_faqs)}"
            elif path.suffix.lower() == ".xlsx":
                source_type = "excel"
                if "课程问答" in path.name:
                    extracted = extract_course_faq(path)
                    faqs.extend(extracted)
                    note = f"standard_faq={len(extracted)}"
                elif "自然拼读常见问题" in path.name:
                    extracted_faqs, extracted_scripts = extract_natural_phonics_mixed(path)
                    faqs.extend(extracted_faqs)
                    scripts.extend(extracted_scripts)
                    note = f"faq={len(extracted_faqs)}, scripts={len(extracted_scripts)}"
                elif "私转推课话术" in path.name:
                    extracted_scripts, grade_points = extract_private_domain_sop(path)
                    scripts.extend(extracted_scripts)
                    scripts.extend(grade_points)
                    note = f"scripts={len(extracted_scripts)}, grade_points={len(grade_points)}"
                elif "AI销售聊天记录" in path.name:
                    extracted_scripts, extracted_sop, extracted_keywords = extract_ai_sales_workbook(path)
                    scripts.extend(extracted_scripts)
                    sop_nodes.extend(extracted_sop)
                    intent_keywords.extend(extracted_keywords)
                    note = (
                        f"scripts={len(extracted_scripts)}, sop={len(extracted_sop)}, "
                        f"keywords={len(extracted_keywords)}"
                    )
                else:
                    note = "excel skipped: no matching extractor"
            else:
                source_type = "other"
                note = "unsupported"
        inventory.append(
            SourceInventory(
                file_name=path.name,
                full_path=str(path),
                extension=path.suffix.lower(),
                size_bytes=path.stat().st_size if path.exists() else 0,
                source_type=source_type,
                extraction_note=note,
            )
        )

    rows = {
        "source_inventory": [asdict(item) for item in inventory],
        "markdown_sections": [asdict(item) for item in sections],
        "standard_faq": [asdict(item) for item in faqs],
        "talk_scripts": [asdict(item) for item in scripts],
        "sop_nodes": [asdict(item) for item in sop_nodes],
        "intent_keywords": [asdict(item) for item in intent_keywords],
    }
    for name, data in rows.items():
        write_rows(output, name, data)
    write_rag_markdown(output, faqs, scripts, sop_nodes, sections)

    summary = {
        "output": str(output),
        "source_files": len(inventory),
        "markdown_sections": len(sections),
        "standard_faq": len(faqs),
        "talk_scripts": len(scripts),
        "sop_nodes": len(sop_nodes),
        "intent_keywords": len(intent_keywords),
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
