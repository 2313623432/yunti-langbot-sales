from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_SOURCE = Path(r"C:\Users\C2023\Downloads\yuanfudao-knowledge\documents")
DEFAULT_OUTPUT = Path("outputs/yuanfudao-faq-talk-cleaning")


@dataclass
class StandardFAQ:
    category: str
    product: str
    question: str
    similar_questions: str
    answer: str
    answer_style: str
    risk_level: str
    status: str
    source_file: str
    source_sheet: str
    source_row: int


@dataclass
class TalkScript:
    script_type: str
    stage: str
    customer_intent: str
    trigger_text: str
    recommended_reply: str
    next_action: str
    forbidden: str
    keywords: str
    priority: str
    status: str
    source_file: str
    source_sheet: str
    source_row: int


@dataclass
class SOPNode:
    node: str
    trigger_condition: str
    customer_expression: str
    recommended_action: str
    recommended_script: str
    forbidden_script: str
    decision_standard: str
    keywords: str
    review_status: str
    source_file: str
    source_sheet: str
    source_row: int


@dataclass
class IntentKeyword:
    keyword: str
    tag_type: str
    meaning: str
    sales_stage: str
    handling_advice: str
    example: str
    priority: str
    source_file: str
    source_sheet: str
    source_row: int


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


def read_excel(path: Path) -> dict[str, pd.DataFrame]:
    return pd.read_excel(path, sheet_name=None, header=None, dtype=object)


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
    return table.dropna(how="all")


def get_by_keywords(row: pd.Series, keywords: list[str]) -> str:
    for col, value in row.items():
        normalized = normalize_header(col)
        if any(keyword in normalized for keyword in keywords):
            return compact(value)
    return ""


def row_cells(row: pd.Series) -> list[str]:
    return [compact(v) for v in row.tolist() if compact(v)]


def row_text(row: pd.Series) -> str:
    return "\n".join(row_cells(row))


def risk_level(text: str) -> str:
    if any(token in text for token in ["退款", "退费", "承诺", "保证", "包邮", "赠送", "价格", "元", "链接", "名额"]):
        return "高"
    if any(token in text for token in ["效果", "提升", "成绩", "老师", "报名", "支付"]):
        return "中"
    return "低"


def is_question_like(text: str) -> bool:
    text = compact(text)
    if not text:
        return False
    if "?" in text or "？" in text:
        return True
    markers = [
        "什么",
        "怎么",
        "吗",
        "能不能",
        "有没有",
        "在哪",
        "哪里",
        "几天",
        "几节",
        "多久",
        "什么时候",
        "为啥",
        "为什么",
        "靠谱吗",
        "真的假的",
        "退",
        "回放",
        "上课",
        "适合",
        "同步",
    ]
    return any(marker in text for marker in markers) and len(text) <= 80


def infer_product(*texts: str) -> str:
    joined = " ".join(texts)
    if any(token in joined for token in ["自然拼读", "自拼"]):
        return "自然拼读"
    if any(token in joined for token in ["思维", "奥数", "数学"]):
        return "数学/思维"
    if any(token in joined for token in ["英语", "剑桥"]):
        return "英语"
    if any(token in joined for token in ["语文", "作文", "阅读"]):
        return "语文"
    return ""


def extract_course_faq(path: Path) -> list[StandardFAQ]:
    faqs: list[StandardFAQ] = []
    for sheet, df in read_excel(path).items():
        header_row = find_header_row(df, ["问题", "回答"], max_scan=10)
        if header_row is None:
            continue
        table = table_from_header(df, header_row)
        last_category = ""
        for offset, row in table.iterrows():
            category = get_by_keywords(row, ["类别", "分类"]) or last_category
            question = get_by_keywords(row, ["问题"])
            answer = get_by_keywords(row, ["回答", "答案", "回复"])
            if category:
                last_category = category
            if not question or not answer:
                continue
            text = question + "\n" + answer
            faqs.append(
                StandardFAQ(
                    category=category,
                    product=infer_product(text),
                    question=question,
                    similar_questions="",
                    answer=answer,
                    answer_style="客服口吻",
                    risk_level=risk_level(text),
                    status="待人工确认" if risk_level(text) == "高" else "可用草稿",
                    source_file=path.name,
                    source_sheet=sheet,
                    source_row=int(offset) + 1,
                )
            )
    return faqs


def extract_natural_phonics_mixed(path: Path) -> tuple[list[StandardFAQ], list[TalkScript]]:
    faqs: list[StandardFAQ] = []
    scripts: list[TalkScript] = []
    for sheet, df in read_excel(path).items():
        last_stage = ""
        for offset, row in df.dropna(how="all").iterrows():
            cells = row_cells(row)
            if not cells:
                continue
            first = cells[0]
            rest = "\n".join(cells[1:])
            full = "\n".join(cells)
            if first in {"马上", "情况说明"}:
                continue
            if len(first) <= 12 and not rest and first in {"不买", "考虑", "买了", "报名链接卡片"}:
                last_stage = first
                continue
            if is_question_like(first) and rest:
                faqs.append(
                    StandardFAQ(
                        category="自然拼读常见问题",
                        product="自然拼读",
                        question=first,
                        similar_questions="",
                        answer=rest,
                        answer_style="客服口吻",
                        risk_level=risk_level(full),
                        status="待人工确认" if risk_level(full) == "高" else "可用草稿",
                        source_file=path.name,
                        source_sheet=sheet,
                        source_row=int(offset) + 1,
                    )
                )
            elif len(full) >= 20:
                scripts.append(
                    TalkScript(
                        script_type="自然拼读跟进话术",
                        stage=last_stage or first[:40],
                        customer_intent=first[:120],
                        trigger_text=first,
                        recommended_reply=rest or full,
                        next_action="根据用户回复进入报名、解释课程、异议处理或成交后交付",
                        forbidden="涉及赠品、名额、价格、包邮时需按当前活动页确认",
                        keywords="自然拼读;报名;跟进",
                        priority="P0" if first in {"不买", "考虑", "买了"} else "P1",
                        status="待人工整理",
                        source_file=path.name,
                        source_sheet=sheet,
                        source_row=int(offset) + 1,
                    )
                )
    return faqs, scripts


def extract_ai_sales_workbook(path: Path) -> tuple[list[TalkScript], list[SOPNode], list[IntentKeyword]]:
    scripts: list[TalkScript] = []
    sop_nodes: list[SOPNode] = []
    keywords: list[IntentKeyword] = []
    sheets = read_excel(path)

    if "03_SOP沉淀" in sheets:
        table = table_from_header(sheets["03_SOP沉淀"], 0)
        for offset, row in table.iterrows():
            node = get_by_keywords(row, ["SOP节点"])
            action = get_by_keywords(row, ["销售推荐动作"])
            script = get_by_keywords(row, ["推荐话术"])
            if not node or not (action or script):
                continue
            sop_nodes.append(
                SOPNode(
                    node=node,
                    trigger_condition=get_by_keywords(row, ["触发条件"]),
                    customer_expression=get_by_keywords(row, ["客户典型表达"]),
                    recommended_action=action,
                    recommended_script=script,
                    forbidden_script=get_by_keywords(row, ["禁忌话术"]),
                    decision_standard=get_by_keywords(row, ["判断标准"]),
                    keywords=get_by_keywords(row, ["关联关键词"]),
                    review_status=get_by_keywords(row, ["复核状态"]) or "待复核",
                    source_file=path.name,
                    source_sheet="03_SOP沉淀",
                    source_row=int(offset) + 1,
                )
            )

    if "02_结构化拆解" in sheets:
        table = table_from_header(sheets["02_结构化拆解"], 0)
        for offset, row in table.iterrows():
            stage = get_by_keywords(row, ["销售阶段"])
            intent = get_by_keywords(row, ["客户意图"])
            reusable = get_by_keywords(row, ["可复用话术"])
            next_action = get_by_keywords(row, ["下一步动作"])
            if not reusable and not next_action:
                continue
            scripts.append(
                TalkScript(
                    script_type="结构化拆解话术",
                    stage=stage,
                    customer_intent=intent,
                    trigger_text=get_by_keywords(row, ["关键信息"]),
                    recommended_reply=reusable,
                    next_action=next_action,
                    forbidden=get_by_keywords(row, ["风险", "问题"]),
                    keywords=intent,
                    priority=get_by_keywords(row, ["可信度"]) or "中",
                    status="待人工整理",
                    source_file=path.name,
                    source_sheet="02_结构化拆解",
                    source_row=int(offset) + 1,
                )
            )

    if "04_关键词标签" in sheets:
        table = table_from_header(sheets["04_关键词标签"], 0)
        for offset, row in table.iterrows():
            keyword = get_by_keywords(row, ["关键词"])
            if not keyword:
                continue
            keywords.append(
                IntentKeyword(
                    keyword=keyword,
                    tag_type=get_by_keywords(row, ["标签类型"]),
                    meaning=get_by_keywords(row, ["解释"]),
                    sales_stage=get_by_keywords(row, ["对应销售阶段"]),
                    handling_advice=get_by_keywords(row, ["处理建议"]),
                    example=get_by_keywords(row, ["示例原话"]),
                    priority=get_by_keywords(row, ["优先级"]),
                    source_file=path.name,
                    source_sheet="04_关键词标签",
                    source_row=int(offset) + 1,
                )
            )
    return scripts, sop_nodes, keywords


def extract_private_domain_sop(path: Path) -> tuple[list[TalkScript], list[TalkScript]]:
    scripts: list[TalkScript] = []
    grade_points: list[TalkScript] = []
    for sheet, df in read_excel(path).items():
        for offset, row in df.dropna(how="all").iterrows():
            cells = [compact(v) for v in row.tolist()]
            if len(cells) >= 2 and cells[0] and cells[1]:
                scripts.append(
                    TalkScript(
                        script_type="私域推课话术",
                        stage=cells[0],
                        customer_intent=cells[0],
                        trigger_text=cells[0],
                        recommended_reply=cells[1],
                        next_action="根据用户反馈继续追问年级、薄弱点或推进报名",
                        forbidden="避免夸大效果；遇到已拒绝用户不要持续强推",
                        keywords=cells[0],
                        priority="P0" if any(token in cells[0] for token in ["不回复", "不需要", "买过", "担心"]) else "P1",
                        status="待人工整理",
                        source_file=path.name,
                        source_sheet=sheet,
                        source_row=int(offset) + 1,
                    )
                )
            if len(cells) >= 5 and cells[3] and cells[4]:
                grade_points.append(
                    TalkScript(
                        script_type="分年级痛点话术",
                        stage="分年级打点",
                        customer_intent=cells[3],
                        trigger_text=cells[3],
                        recommended_reply=cells[4],
                        next_action="结合孩子年级和薄弱项使用",
                        forbidden="不要制造过度焦虑；不要承诺固定提分",
                        keywords=f"{sheet};{cells[3]}",
                        priority="P1",
                        status="待人工整理",
                        source_file=path.name,
                        source_sheet=sheet,
                        source_row=int(offset) + 1,
                    )
                )
    return scripts, grade_points


def extract_generic_talk_workbook(path: Path, script_type: str) -> list[TalkScript]:
    scripts: list[TalkScript] = []
    for sheet, df in read_excel(path).items():
        for offset, row in df.dropna(how="all").iterrows():
            text = row_text(row)
            if len(text) < 35:
                continue
            first = row_cells(row)[0]
            scripts.append(
                TalkScript(
                    script_type=script_type,
                    stage=sheet,
                    customer_intent=first[:120],
                    trigger_text=first[:300],
                    recommended_reply=text[:2500],
                    next_action="待人工按场景拆分",
                    forbidden="长段直播/群发话术上线前需压缩为短句客服口吻",
                    keywords=infer_product(text),
                    priority="P2",
                    status="原文摘录",
                    source_file=path.name,
                    source_sheet=sheet,
                    source_row=int(offset) + 1,
                )
            )
    return scripts


def write_outputs(output: Path, rows_by_name: dict[str, list[dict[str, Any]]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in rows_by_name.items():
        (output / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pd.DataFrame(rows).to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
        with (output / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_rag_markdown(output: Path, faqs: list[StandardFAQ], scripts: list[TalkScript], sop_nodes: list[SOPNode]) -> None:
    lines = [
        "# 猿辅导 FAQ 与话术清洗版 RAG 草稿",
        "",
        "> 本文件不包含产品事实表。价格、赠品、链接、排期、名额等高风险内容仍需人工确认。",
        "",
        "## 标准 FAQ",
    ]
    for idx, faq in enumerate(faqs, start=1):
        lines.extend(
            [
                "",
                f"### FAQ {idx}: {faq.question}",
                f"- 类别: {faq.category}",
                f"- 产品: {faq.product}",
                f"- 问题: {faq.question}",
                f"- 回答: {faq.answer}",
                f"- 风险等级: {faq.risk_level}",
                f"- 状态: {faq.status}",
                f"- 来源: {faq.source_file} / {faq.source_sheet} / row {faq.source_row}",
            ]
        )
    lines.extend(["", "## SOP 节点"])
    for idx, node in enumerate(sop_nodes, start=1):
        lines.extend(
            [
                "",
                f"### SOP {idx}: {node.node}",
                f"- 触发条件: {node.trigger_condition}",
                f"- 客户表达: {node.customer_expression}",
                f"- 推荐动作: {node.recommended_action}",
                f"- 推荐话术: {node.recommended_script}",
                f"- 禁忌话术: {node.forbidden_script}",
                f"- 判断标准: {node.decision_standard}",
                f"- 关键词: {node.keywords}",
                f"- 来源: {node.source_file} / {node.source_sheet} / row {node.source_row}",
            ]
        )
    lines.extend(["", "## 话术摘录"])
    for idx, script in enumerate(scripts, start=1):
        if script.status == "原文摘录" and script.priority == "P2":
            continue
        lines.extend(
            [
                "",
                f"### 话术 {idx}: {script.stage or script.customer_intent}",
                f"- 类型: {script.script_type}",
                f"- 阶段: {script.stage}",
                f"- 用户意图: {script.customer_intent}",
                f"- 触发内容: {script.trigger_text}",
                f"- 推荐回复: {script.recommended_reply}",
                f"- 下一步动作: {script.next_action}",
                f"- 禁忌: {script.forbidden}",
                f"- 来源: {script.source_file} / {script.source_sheet} / row {script.source_row}",
            ]
        )
    (output / "faq_talk_rag_draft.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source
    output = args.output
    faqs: list[StandardFAQ] = []
    scripts: list[TalkScript] = []
    sop_nodes: list[SOPNode] = []
    intent_keywords: list[IntentKeyword] = []

    course_faq = source / "猿辅导课程问答整理.xlsx"
    if course_faq.exists():
        faqs.extend(extract_course_faq(course_faq))

    phonics = source / "猿辅导自然拼读常见问题(1).xlsx"
    if phonics.exists():
        phonics_faqs, phonics_scripts = extract_natural_phonics_mixed(phonics)
        faqs.extend(phonics_faqs)
        scripts.extend(phonics_scripts)

    ai_sales = source / "AI销售聊天记录_SOP整理模板_B015资料版.xlsx"
    if ai_sales.exists():
        ai_scripts, ai_sop, ai_keywords = extract_ai_sales_workbook(ai_sales)
        scripts.extend(ai_scripts)
        sop_nodes.extend(ai_sop)
        intent_keywords.extend(ai_keywords)

    private_sop = source / "学科私转推课话术 sop.xlsx"
    if private_sop.exists():
        private_scripts, grade_points = extract_private_domain_sop(private_sop)
        scripts.extend(private_scripts)
        scripts.extend(grade_points)

    for filename, script_type in [
        ("猿辅导1天2次群发SOP.xlsx", "群发跟进SOP"),
        ("【直播】英语初级话术.xlsx", "直播话术原文"),
    ]:
        path = source / filename
        if path.exists():
            scripts.extend(extract_generic_talk_workbook(path, script_type))

    rows_by_name = {
        "standard_faq": [asdict(item) for item in faqs],
        "talk_scripts": [asdict(item) for item in scripts],
        "sop_nodes": [asdict(item) for item in sop_nodes],
        "intent_keywords": [asdict(item) for item in intent_keywords],
    }
    write_outputs(output, rows_by_name)
    write_rag_markdown(output, faqs, scripts, sop_nodes)

    summary = {
        "source": str(source),
        "output": str(output),
        "standard_faq": len(faqs),
        "talk_scripts": len(scripts),
        "sop_nodes": len(sop_nodes),
        "intent_keywords": len(intent_keywords),
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
