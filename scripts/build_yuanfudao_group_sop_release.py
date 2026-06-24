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

import pandas as pd


DEFAULT_SOURCE = Path(
    r"C:\Users\C2023\AppData\Roaming\LarkShell\sdk_storage\368cae5d95e02fb4259fa5b6c48bd254\resources\files\猿辅导1天2次群发SOP.xlsx"
)
DEFAULT_OUTPUT = Path("outputs/yuanfudao-selected-faq-talk-cleaning/sop_ready")


def compact(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_dispimg(text: str) -> tuple[str, bool]:
    found = bool(re.search(r"=DISPIMG\([^)]+\)", text))
    cleaned = re.sub(r"\s*=DISPIMG\([^)]+\)\s*", "\n", text)
    return compact(cleaned), found


def make_id(*parts: Any) -> str:
    raw = "\n".join(compact(part) for part in parts)
    return "sop_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def product_for_sheet(sheet_name: str) -> str:
    if "自然拼读" in sheet_name:
        return "自然拼读"
    if "阅读" in sheet_name and "思维" in sheet_name:
        return "阅读+思维"
    return sheet_name


def stage_for_day(day: int) -> str:
    if day == 1:
        return "首次触达/活动介绍"
    if 2 <= day <= 5:
        return "价值补充/限时提醒"
    if 6 <= day <= 10:
        return "权益强化/报名推动"
    if 11 <= day <= 20:
        return "未回复跟进/异议唤醒"
    if 21 <= day <= 30:
        return "后续追访/持续唤醒"
    return "长周期未回复唤醒"


def risk_level(text: str) -> str:
    high_tokens = ["退款", "包邮", "赠", "名额", "链接", "9元", "9块", "截止", "最后"]
    return "高" if any(token in text for token in high_tokens) else "低"


def link_action(*values: Any) -> str:
    text = "\n".join(compact(value) for value in values)
    if "雷达" in text:
        return "发送雷达报名卡片/报名链接"
    if "报名链接" in text or "链接" in text or "报名" in text:
        return "发送报名链接或引导家长回复 1"
    return "根据回复继续跟进"


def source_image_required(image_value: Any, message: str) -> str:
    image_text = compact(image_value)
    if image_text or "=DISPIMG" in message:
        return "需要配图或素材卡片"
    return "无需单独配图"


def tags_for(entry: dict[str, Any]) -> list[str]:
    tags = [
        "SOP",
        "1天2次群发",
        entry["product"],
        entry["stage"],
        f"第{entry['day']}天",
        entry["send_order"],
    ]
    if entry["risk_level"] == "高":
        tags.append("高风险口径")
    return tags


def entry_content(entry: dict[str, Any]) -> str:
    lines = [
        f"SOP节点：第{entry['day']}天 {entry['send_order']}",
        f"适用产品：{entry['product']}",
        f"发送时间：{entry['send_time']}",
        f"跟进阶段：{entry['stage']}",
        f"触发条件：家长未完成报名或未明确回复时，按第{entry['day']}天节奏进行群发跟进。",
        f"推荐话术：{entry['message']}",
        f"报名动作：{entry['signup_action']}",
        f"素材要求：{entry['image_requirement']}",
        "注意事项：涉及价格、赠品、包邮、名额、报名链接、活动截止等内容，需以后续实际活动政策为准。",
    ]
    return "\n".join(lines)


def extract_entries(source: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    workbook = pd.ExcelFile(source)
    for sheet_name in workbook.sheet_names:
        df = pd.read_excel(source, sheet_name=sheet_name, dtype=str)
        product = product_for_sheet(sheet_name)
        second_col = "第二句 15:40/21:20"
        for index, row in df.iterrows():
            day_text = compact(row.get("天数"))
            if not day_text:
                continue
            try:
                day = int(float(day_text))
            except ValueError:
                continue
            excel_row = index + 2
            stage = stage_for_day(day)
            primary_raw = compact(row.get("话术"))
            primary_message, primary_has_inline_image = remove_dispimg(primary_raw)
            if primary_message:
                entry = {
                    "id": make_id(sheet_name, day, "第1条", primary_message),
                    "type": "group_send_sop",
                    "title": f"{product} 第{day}天第1条群发",
                    "product": product,
                    "category": "1天2次群发SOP",
                    "day": day,
                    "send_order": "第1条",
                    "send_time": compact(row.get("时间")) or "按SOP执行",
                    "stage": stage,
                    "trigger_condition": f"第{day}天第一次群发，家长未报名或未明确回复",
                    "message": primary_message,
                    "signup_action": link_action(row.get("报名链接"), row.get("Unnamed: 5"), primary_raw),
                    "image_requirement": source_image_required(row.get("图片"), primary_raw)
                    if not primary_has_inline_image
                    else "需要配图或素材卡片",
                    "risk_level": risk_level(primary_raw),
                    "status": "已审阅可入库",
                    "source_file": source.name,
                    "source_sheet": sheet_name,
                    "source_row": excel_row,
                }
                entry["content"] = entry_content(entry)
                entry["tags"] = tags_for(entry)
                entries.append(entry)
            second_raw = compact(row.get(second_col))
            second_message, second_has_inline_image = remove_dispimg(second_raw)
            if second_message:
                entry = {
                    "id": make_id(sheet_name, day, "第2条", second_message),
                    "type": "group_send_sop",
                    "title": f"{product} 第{day}天第2条群发",
                    "product": product,
                    "category": "1天2次群发SOP",
                    "day": day,
                    "send_order": "第2条",
                    "send_time": "15:40/21:20",
                    "stage": stage,
                    "trigger_condition": f"第{day}天第二次群发，家长仍未报名或未明确回复",
                    "message": second_message,
                    "signup_action": link_action(row.get("Unnamed: 7"), second_raw),
                    "image_requirement": "需要配图或素材卡片" if second_has_inline_image else "无需单独配图",
                    "risk_level": risk_level(second_raw),
                    "status": "已审阅可入库",
                    "source_file": source.name,
                    "source_sheet": sheet_name,
                    "source_row": excel_row,
                }
                entry["content"] = entry_content(entry)
                entry["tags"] = tags_for(entry)
                entries.append(entry)
    return entries


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
        "day",
        "send_order",
        "send_time",
        "stage",
        "trigger_condition",
        "message",
        "signup_action",
        "image_requirement",
        "risk_level",
        "status",
        "content",
        "tags",
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


def markdown_block(entry: dict[str, Any], index: int) -> list[str]:
    return [
        f"### {index}. {entry['title']}",
        "",
        f"- ID: {entry['id']}",
        f"- 产品: {entry['product']}",
        f"- 类别: {entry['category']}",
        f"- 第几天: 第{entry['day']}天",
        f"- 群发顺序: {entry['send_order']}",
        f"- 发送时间: {entry['send_time']}",
        f"- 阶段: {entry['stage']}",
        f"- 风险等级: {entry['risk_level']}",
        f"- 标签: {'、'.join(entry['tags'])}",
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
    for index, entry in enumerate(entries, start=1):
        lines.extend(markdown_block(entry, index))
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_text(path: Path, entries: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    for entry in entries:
        lines.extend(
            [
                f"[{entry['id']}] {entry['title']}",
                f"产品: {entry['product']}",
                f"第几天: 第{entry['day']}天",
                f"顺序/时间: {entry['send_order']} / {entry['send_time']}",
                entry["content"],
                "---",
                "",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_readme(path: Path, entries: list[dict[str, Any]], products: dict[str, int]) -> None:
    lines = [
        "# 猿辅导 1天2次群发 SOP 知识库入库包",
        "",
        "本目录是 `猿辅导1天2次群发SOP.xlsx` 转换后的正式入库版本，适合上传到文档型知识库、向量知识库、客服知识库或结构化导入系统。",
        "",
        "## 文件说明",
        "",
        "- `yuanfudao_group_sop_combined.md`: 通用合并版，适合直接上传到支持 Markdown 的知识库。",
        "- `yuanfudao_group_sop_entries.jsonl`: 结构化逐条记录，适合程序导入或二次切片。",
        "- `yuanfudao_group_sop_entries.csv`: 表格导入版。",
        "- `yuanfudao_group_sop_import.txt`: 纯文本兜底版。",
        "- `by_product/`: 按产品拆分的 Markdown 文件。",
        "",
        "## 条目统计",
        "",
        f"- SOP 条目: {len(entries)}",
    ]
    for product, count in sorted(products.items()):
        lines.append(f"- {product}: {count}")
    lines.extend(
        [
            "",
            "## 入库建议",
            "",
            "1. 文档型知识库优先上传 `yuanfudao_group_sop_combined.md`。",
            "2. 支持结构化导入时，优先使用 `yuanfudao_group_sop_entries.jsonl` 或 `yuanfudao_group_sop_entries.csv`。",
            "3. 如果知识库容易混淆产品线，建议使用 `by_product/` 下的拆分文件分开上传。",
            "4. 价格、赠品、包邮、名额、链接、活动截止类内容后续活动变更时仍需复核。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output = args.output
    by_product = output / "by_product"
    by_product.mkdir(parents=True, exist_ok=True)
    for stale in by_product.glob("*.md"):
        stale.unlink()

    entries = extract_entries(args.source)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[entry["product"]].append(entry)

    write_markdown(
        output / "yuanfudao_group_sop_combined.md",
        "猿辅导 1天2次群发 SOP 知识库",
        entries,
        "本文件为审阅通过后的 SOP 入库版。每个条目按产品、天数、群发顺序、发送时间、推荐话术和报名动作组织。",
    )
    write_jsonl(output / "yuanfudao_group_sop_entries.jsonl", entries)
    write_csv(output / "yuanfudao_group_sop_entries.csv", entries)
    write_text(output / "yuanfudao_group_sop_import.txt", entries)
    for product, product_entries in grouped.items():
        file_name = product.replace("/", "_").replace("+", "_") + ".md"
        write_markdown(
            by_product / file_name,
            f"猿辅导 {product} 1天2次群发 SOP",
            product_entries,
            f"本文件为 {product} 相关的 1天2次群发 SOP 入库版。",
        )

    summary = {
        "source": str(args.source),
        "output": str(output),
        "total_entries": len(entries),
        "products": {product: len(rows) for product, rows in sorted(grouped.items())},
        "files": [
            "README_入库说明.md",
            "yuanfudao_group_sop_combined.md",
            "yuanfudao_group_sop_entries.jsonl",
            "yuanfudao_group_sop_entries.csv",
            "yuanfudao_group_sop_import.txt",
            "by_product/",
        ],
    }
    write_readme(output / "README_入库说明.md", entries, summary["products"])
    (output / "release_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
