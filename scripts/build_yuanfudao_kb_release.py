from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("outputs/yuanfudao-selected-faq-talk-cleaning")
DEFAULT_OUTPUT = DEFAULT_INPUT / "knowledge_base_ready"


def load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def compact(text: Any) -> str:
    if text is None:
        return ""
    value = str(text).replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def heading(text: str) -> str:
    value = compact(text)
    value = re.sub(r"^[#>\-\s]+", "", value)
    return value.replace("\n", " ")[:120] or "未命名条目"


def slug(text: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", compact(text))
    value = re.sub(r"\s+", "_", value).strip("._ ")
    return value[:80] or "未分类"


def make_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(compact(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def tags_from(*parts: Any) -> list[str]:
    tags: list[str] = []
    for part in parts:
        for item in re.split(r"[;,，、/\s]+", compact(part)):
            item = item.strip()
            if item and item not in tags:
                tags.append(item)
    return tags


def infer_release_product(*parts: Any) -> str:
    text = "\n".join(compact(part) for part in parts)
    if "自然拼读" in text or "自拼" in text:
        return "自然拼读"
    if "剑桥" in text:
        return "剑桥英语"
    if "奥数" in text or "数学思维" in text or "数学/思维" in text:
        return "数学/思维"
    if "学科" in text or "语数英" in text:
        return "学科"
    if "英语" in text:
        return "英语"
    if "数学" in text:
        return "数学/思维"
    return "通用"


def faq_entry(row: dict[str, Any], index: int) -> dict[str, Any]:
    question = compact(row.get("question"))
    answer = compact(row.get("answer"))
    category = compact(row.get("category")) or "FAQ"
    source_file = compact(row.get("source_file"))
    source_sheet = compact(row.get("source_sheet"))
    source_row = row.get("source_row", "")
    product = compact(row.get("product")) or infer_release_product(
        source_file,
        category,
        question,
        answer,
    )
    similar = compact(row.get("similar_questions"))
    risk_level = compact(row.get("risk_level")) or "低"
    content_parts = [
        f"问题：{question}",
        f"回答：{answer}",
    ]
    if similar:
        content_parts.insert(1, f"相似问法：{similar}")
    content_parts.extend(
        [
            f"适用产品：{product}",
            f"分类：{category}",
            f"风险等级：{risk_level}",
        ]
    )
    return {
        "id": make_id("faq", question, answer, source_file, source_sheet, source_row, index),
        "type": "faq",
        "title": heading(question),
        "product": product,
        "category": category.replace("Markdown候选", "FAQ候选"),
        "question": question,
        "similar_questions": similar,
        "answer": answer,
        "content": "\n".join(content_parts),
        "tags": tags_from(product, category, risk_level, "FAQ"),
        "risk_level": risk_level,
        "priority": "P0" if risk_level == "高" else "P1",
        "status": "已审阅可入库",
        "source_file": source_file,
        "source_sheet": source_sheet,
        "source_row": source_row,
    }


def script_entry(row: dict[str, Any], index: int) -> dict[str, Any]:
    script_type = compact(row.get("script_type")) or "话术"
    stage = compact(row.get("stage")) or script_type
    intent = compact(row.get("customer_intent"))
    trigger = compact(row.get("trigger_text"))
    reply = compact(row.get("recommended_reply"))
    next_action = compact(row.get("next_action"))
    forbidden = compact(row.get("forbidden"))
    keywords = compact(row.get("keywords"))
    source_file = compact(row.get("source_file"))
    source_sheet = compact(row.get("source_sheet"))
    source_row = row.get("source_row", "")
    priority = compact(row.get("priority")) or "P1"
    product = infer_release_product(
        source_file,
        keywords,
        script_type,
        stage,
        intent,
        trigger,
        reply,
    )
    content_parts = [
        f"话术类型：{script_type}",
        f"使用场景：{stage}",
    ]
    if intent:
        content_parts.append(f"客户意图：{intent}")
    if trigger and trigger != stage:
        content_parts.append(f"触发条件：{trigger}")
    content_parts.append(f"推荐回复：{reply}")
    if next_action:
        content_parts.append(f"下一步动作：{next_action}")
    if forbidden:
        content_parts.append(f"禁忌/注意事项：{forbidden}")
    if keywords:
        content_parts.append(f"关键词：{keywords}")
    return {
        "id": make_id("script", script_type, stage, reply, source_file, source_sheet, source_row, index),
        "type": "talk_script",
        "title": heading(stage),
        "product": product,
        "category": script_type,
        "question": trigger or stage,
        "similar_questions": "",
        "answer": reply,
        "content": "\n".join(content_parts),
        "tags": tags_from(product, script_type, intent, keywords, priority, "话术"),
        "risk_level": "高" if any(token in reply for token in ["退款", "价格", "赠", "名额", "包邮", "链接"]) else "低",
        "priority": priority,
        "status": "已审阅可入库",
        "source_file": source_file,
        "source_sheet": source_sheet,
        "source_row": source_row,
    }


def markdown_entry(entry: dict[str, Any], idx: int) -> list[str]:
    tags = "、".join(entry["tags"])
    return [
        f"### {idx}. {entry['title']}",
        "",
        f"- ID: {entry['id']}",
        f"- 类型: {'FAQ' if entry['type'] == 'faq' else '话术'}",
        f"- 产品: {entry['product']}",
        f"- 分类: {entry['category']}",
        f"- 优先级: {entry['priority']}",
        f"- 风险等级: {entry['risk_level']}",
        f"- 标签: {tags}",
        f"- 来源: {entry['source_file']} / {entry['source_sheet']} / row {entry['source_row']}",
        "",
        entry["content"],
        "",
    ]


def write_markdown(path: Path, title: str, entries: list[dict[str, Any]], description: str) -> None:
    lines = [
        f"# {title}",
        "",
        description,
        "",
        f"- 生成日期: {date.today().isoformat()}",
        f"- 条目数: {len(entries)}",
        "- 状态: 已审阅可入库",
        "",
    ]
    for idx, entry in enumerate(entries, start=1):
        lines.extend(markdown_entry(entry, idx))
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_jsonl(path: Path, entries: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def write_csv(path: Path, entries: list[dict[str, Any]]) -> None:
    fields = [
        "id",
        "type",
        "title",
        "product",
        "category",
        "question",
        "similar_questions",
        "answer",
        "content",
        "tags",
        "risk_level",
        "priority",
        "status",
        "source_file",
        "source_sheet",
        "source_row",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for entry in entries:
            row = dict(entry)
            row["tags"] = ";".join(row["tags"])
            writer.writerow({field: row.get(field, "") for field in fields})


def write_plain_text(path: Path, entries: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    for entry in entries:
        lines.extend(
            [
                f"[{entry['id']}] {entry['title']}",
                f"类型: {'FAQ' if entry['type'] == 'faq' else '话术'}",
                f"产品: {entry['product']}",
                f"分类: {entry['category']}",
                entry["content"],
                "---",
                "",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_readme(path: Path, faq_count: int, script_count: int, products: list[str]) -> None:
    lines = [
        "# 猿辅导话术 FAQ 知识库入库包",
        "",
        "本目录是审阅通过后的正式入库版本，适合上传到文档型知识库、向量知识库、客服知识库或需要结构化导入的系统。",
        "",
        "## 文件说明",
        "",
        "- `yuanfudao_kb_combined.md`: 通用合并版，适合直接上传到支持 Markdown 的知识库。",
        "- `yuanfudao_faq_ready.md`: FAQ 专用版，一问一答结构。",
        "- `yuanfudao_talk_scripts_ready.md`: 话术专用版，按场景/意图组织。",
        "- `yuanfudao_kb_entries.jsonl`: 结构化逐条记录，适合程序导入或二次切片。",
        "- `yuanfudao_kb_entries.csv`: Excel/表格系统可打开的结构化版本。",
        "- `yuanfudao_kb_import.txt`: 纯文本兜底版，适合只支持 txt 的知识库。",
        "- `by_product/`: 按产品拆分的 Markdown 文件，适合分库、分标签上传。",
        "",
        "## 条目统计",
        "",
        f"- FAQ: {faq_count}",
        f"- 话术: {script_count}",
        f"- 总条目: {faq_count + script_count}",
        f"- 产品标签: {'、'.join(products)}",
        "",
        "## 入库建议",
        "",
        "1. 如果知识库支持 Markdown，优先上传 `yuanfudao_kb_combined.md`。",
        "2. 如果知识库支持结构化导入，优先使用 `yuanfudao_kb_entries.jsonl` 或 `yuanfudao_kb_entries.csv`。",
        "3. 如果希望减少检索噪声，可以分别上传 FAQ 和话术两个文件，或使用 `by_product/` 目录按产品分库。",
        "4. 价格、退款、赠品、名额、链接、排期类内容虽然已审阅通过，后续每次活动变更仍建议单独复核。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output = args.output
    by_product = output / "by_product"
    by_product.mkdir(parents=True, exist_ok=True)
    for stale in by_product.glob("*.md"):
        stale.unlink()

    faq_rows = load_json(args.input / "standard_faq.json")
    script_rows = load_json(args.input / "talk_scripts.json")
    faq_entries = [faq_entry(row, idx) for idx, row in enumerate(faq_rows, start=1)]
    script_entries = [script_entry(row, idx) for idx, row in enumerate(script_rows, start=1)]
    entries = faq_entries + script_entries

    write_markdown(
        output / "yuanfudao_faq_ready.md",
        "猿辅导 FAQ 知识库",
        faq_entries,
        "本文件为审阅通过后的 FAQ 入库版。每个条目按问题、回答、产品、分类和来源组织。",
    )
    write_markdown(
        output / "yuanfudao_talk_scripts_ready.md",
        "猿辅导销售话术知识库",
        script_entries,
        "本文件为审阅通过后的话术入库版。每个条目按场景、客户意图、推荐回复和注意事项组织。",
    )
    write_markdown(
        output / "yuanfudao_kb_combined.md",
        "猿辅导 FAQ 与销售话术综合知识库",
        entries,
        "本文件为审阅通过后的综合入库版，包含 FAQ 与销售话术。产品事实表未纳入本版。",
    )
    write_jsonl(output / "yuanfudao_kb_entries.jsonl", entries)
    write_csv(output / "yuanfudao_kb_entries.csv", entries)
    write_plain_text(output / "yuanfudao_kb_import.txt", entries)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[entry["product"]].append(entry)
    for product, product_entries in grouped.items():
        write_markdown(
            by_product / f"{slug(product)}.md",
            f"猿辅导 {product} 知识库",
            product_entries,
            f"本文件为 {product} 相关 FAQ 与销售话术入库版。",
        )

    products = sorted(grouped)
    write_readme(output / "README_入库说明.md", len(faq_entries), len(script_entries), products)
    summary = {
        "output": str(output),
        "faq_entries": len(faq_entries),
        "talk_script_entries": len(script_entries),
        "total_entries": len(entries),
        "products": products,
        "files": [
            "README_入库说明.md",
            "yuanfudao_kb_combined.md",
            "yuanfudao_faq_ready.md",
            "yuanfudao_talk_scripts_ready.md",
            "yuanfudao_kb_entries.jsonl",
            "yuanfudao_kb_entries.csv",
            "yuanfudao_kb_import.txt",
            "by_product/",
        ],
    }
    (output / "release_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
