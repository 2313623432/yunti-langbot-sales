from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


FAQ_TALK_CSV = Path("outputs/yuanfudao-selected-faq-talk-cleaning/knowledge_base_ready/yuanfudao_kb_entries.csv")
SOP_CSV = Path("outputs/yuanfudao-selected-faq-talk-cleaning/sop_ready/yuanfudao_group_sop_entries.csv")
COURSE_CSV = Path("release/yuanfudao-course-catalog-cleaned/yuanfudao_course_catalog_entries.csv")
RELEASE_ROOT = Path("release/yuanfudao-qa-pairs-cleaned")
VOLCENGINE_ROOT = Path("release/yuanfudao-volcengine-kb-upload")

QA_FIELDS = [
    "qa_id",
    "question",
    "answer",
    "product",
    "category",
    "source_type",
    "source_id",
    "source_file",
    "tags",
    "risk_note",
]


def clean(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


def inline(value: str | None, limit: int = 120) -> str:
    text = clean(value).replace("\n", "；")
    while "  " in text:
        text = text.replace("  ", " ")
    text = text.strip("； ")
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def add_qa(
    items: list[dict[str, str]],
    *,
    question: str,
    answer: str,
    product: str,
    category: str,
    source_type: str,
    source_id: str,
    source_file: str,
    tags: str = "",
    risk_note: str = "",
) -> None:
    if not clean(question) or not clean(answer):
        return
    items.append(
        {
            "qa_id": f"YQA-{len(items) + 1:04d}",
            "question": clean(question),
            "answer": clean(answer),
            "product": clean(product),
            "category": clean(category),
            "source_type": clean(source_type),
            "source_id": clean(source_id),
            "source_file": clean(source_file),
            "tags": clean(tags),
            "risk_note": clean(risk_note),
        }
    )


def build_faq_talk_qa(items: list[dict[str, str]]) -> None:
    for row in read_csv(FAQ_TALK_CSV):
        row_type = row.get("type", "")
        product = row.get("product", "")
        category = row.get("category", "")
        source_id = row.get("id", "")
        source_file = row.get("source_file", "")
        if row_type == "faq":
            add_qa(
                items,
                question=row.get("question", ""),
                answer=row.get("answer", "") or row.get("content", ""),
                product=product,
                category=category or "FAQ",
                source_type="FAQ",
                source_id=source_id,
                source_file=source_file,
                tags=row.get("tags", ""),
                risk_note="价格、排期、权益等强时效信息需以最新活动页、班主任通知或后台为准。",
            )
        else:
            title = row.get("title", "") or "销售话术"
            question = f"{product}的“{inline(title, 60)}”场景应该怎么说？" if product else f"“{inline(title, 60)}”场景应该怎么说？"
            answer_parts = []
            if row.get("question"):
                answer_parts.append(f"适用问题/场景：{clean(row.get('question'))}")
            answer_parts.append(clean(row.get("answer") or row.get("content")))
            add_qa(
                items,
                question=question,
                answer="\n\n".join(part for part in answer_parts if part),
                product=product,
                category=category or "销售话术",
                source_type="销售话术",
                source_id=source_id,
                source_file=source_file,
                tags=row.get("tags", ""),
                risk_note="话术可用于表达参考，涉及实时政策需二次核对。",
            )


def build_sop_qa(items: list[dict[str, str]]) -> None:
    for row in read_csv(SOP_CSV):
        product = row.get("product", "")
        title = row.get("title", "") or "群发SOP"
        day = row.get("day", "")
        send_order = row.get("send_order", "")
        send_time = row.get("send_time", "")
        stage = row.get("stage", "")
        question = f"{product}{title}应该在什么时候发，发什么内容？"
        answer_parts = [
            f"发送时间：{send_time}" if send_time else "",
            f"触发条件：{row.get('trigger_condition', '')}" if row.get("trigger_condition") else "",
            f"阶段：{stage}" if stage else "",
            f"群发内容：\n{clean(row.get('message'))}" if row.get("message") else "",
            f"报名动作：{row.get('signup_action', '')}" if row.get("signup_action") else "",
            f"素材要求：{row.get('image_requirement', '')}" if row.get("image_requirement") else "",
        ]
        add_qa(
            items,
            question=question,
            answer="\n\n".join(part for part in answer_parts if clean(part)),
            product=product,
            category=f"1天2次群发SOP / 第{day}天 / {send_order}",
            source_type="群发SOP",
            source_id=row.get("id", ""),
            source_file=row.get("source_file", ""),
            tags=row.get("tags", ""),
            risk_note="群发节奏需结合实际运营日历和用户状态使用。",
        )


def build_course_catalog_qa(items: list[dict[str, str]]) -> None:
    for row in read_csv(COURSE_CSV):
        sku = row.get("商品/SKU名称", "")
        product = row.get("业务线", "")
        price = row.get("定价", "")
        unit = row.get("价格单位", "")
        add_qa(
            items,
            question=f"{sku}的课程货盘信息是什么？",
            answer=course_answer(row),
            product=product,
            category="课程货盘/产品事实",
            source_type="课程货盘",
            source_id=row.get("record_id", ""),
            source_file=row.get("来源文件", ""),
            tags="课程货盘;产品事实;价格;适用人群;课时",
            risk_note="课程货盘来自历史资料清洗，实时价格、权益、排期需以最新活动页、班主任通知或后台为准。",
        )
        if price:
            add_qa(
                items,
                question=f"{sku}多少钱？",
                answer=f"{sku}在清洗资料中的定价为：{price}{unit}。\n\n来源：{row.get('来源文件', '')}（{row.get('来源位置', '')}）。\n\n提醒：价格具有时效性，实际售卖请以最新活动页、班主任通知或后台为准。",
                product=product,
                category="课程货盘/价格",
                source_type="课程货盘",
                source_id=row.get("record_id", ""),
                source_file=row.get("来源文件", ""),
                tags="价格;课程货盘",
                risk_note="价格强时效，需核对最新口径。",
            )
        if row.get("适用人群/年级"):
            add_qa(
                items,
                question=f"{sku}适合什么年级或人群？",
                answer=f"{sku}在清洗资料中的适用人群/年级为：{clean(row.get('适用人群/年级'))}\n\n来源：{row.get('来源文件', '')}（{row.get('来源位置', '')}）。",
                product=product,
                category="课程货盘/适用人群",
                source_type="课程货盘",
                source_id=row.get("record_id", ""),
                source_file=row.get("来源文件", ""),
                tags="适用人群;年级;课程货盘",
                risk_note="如招生年级更新，需核对最新口径。",
            )


def course_answer(row: dict[str, str]) -> str:
    labels = [
        ("业务线", "业务线"),
        ("商品/SKU名称", "商品/SKU名称"),
        ("定价", "定价"),
        ("适用人群/年级", "适用人群/年级"),
        ("课程形式", "课程形式"),
        ("课时/周期", "课时/周期"),
        ("上课时间/排期", "上课时间/排期"),
        ("教材/资料/实物", "教材/资料/实物"),
        ("服务/伴学", "服务/伴学"),
        ("赠品/权益", "赠品/权益"),
        ("后转价格/正价课价格", "后转价格/正价课价格"),
        ("商品卖点", "商品卖点"),
        ("商品介绍", "商品介绍"),
        ("链接", "链接"),
        ("销转流程", "销转流程"),
        ("备注", "备注"),
    ]
    parts: list[str] = []
    for key, label in labels:
        value = clean(row.get(key))
        if value:
            if key == "定价" and row.get("价格单位"):
                value = f"{value}{row.get('价格单位')}"
            parts.append(f"{label}：{value}")
    parts.append(f"来源：{row.get('来源文件', '')}（{row.get('来源位置', '')}）")
    parts.append("提醒：价格、排期、权益、赠品、活动有效期等强时效信息需以最新活动页、班主任通知或后台为准。")
    return "\n".join(parts)


def write_outputs(items: list[dict[str, str]]) -> None:
    if RELEASE_ROOT.exists():
        shutil.rmtree(RELEASE_ROOT)
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)

    with (RELEASE_ROOT / "yuanfudao_qa_pairs.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=QA_FIELDS)
        writer.writeheader()
        writer.writerows(items)

    with (RELEASE_ROOT / "yuanfudao_qa_pairs.jsonl").open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    md_lines = [
        "# 猿辅导 QA 对知识库",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- QA 对数量：{len(items)}",
        "- 来源：FAQ、销售话术、1天2次群发 SOP、课程货盘。",
        "- 规则：答案只来自已清洗字段；涉及价格、排期、权益、赠品、活动有效期时需核对最新口径。",
        "",
    ]
    for item in items:
        md_lines.extend(
            [
                f"## {item['qa_id']} {item['question']}",
                "",
                f"- 产品/业务：{item['product']}",
                f"- 分类：{item['category']}",
                f"- 来源：{item['source_file']} / {item['source_id']}",
                "",
                "### 答案",
                "",
                item["answer"],
                "",
                f"> 风险提示：{item['risk_note']}",
                "",
            ]
        )
    (RELEASE_ROOT / "yuanfudao_qa_pairs_ready.md").write_text("\n".join(md_lines), encoding="utf-8")

    txt = []
    for item in items:
        txt.extend(
            [
                f"[{item['qa_id']}]",
                f"问题：{item['question']}",
                f"答案：{item['answer']}",
                f"产品/业务：{item['product']}",
                f"分类：{item['category']}",
                f"来源：{item['source_file']} / {item['source_id']}",
                f"风险提示：{item['risk_note']}",
                "",
            ]
        )
    (RELEASE_ROOT / "yuanfudao_qa_pairs_for_kb.txt").write_text("\n".join(txt), encoding="utf-8")

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_qa_pairs": len(items),
        "by_source_type": {},
        "files": [
            "yuanfudao_qa_pairs_ready.md",
            "yuanfudao_qa_pairs_for_kb.txt",
            "yuanfudao_qa_pairs.csv",
            "yuanfudao_qa_pairs.jsonl",
        ],
    }
    for item in items:
        summary["by_source_type"][item["source_type"]] = summary["by_source_type"].get(item["source_type"], 0) + 1
    (RELEASE_ROOT / "release_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RELEASE_ROOT / "README_QA对说明.md").write_text(
        f"""# 猿辅导 QA 对清洗版

共生成 {len(items)} 条 QA 对，来源包括 FAQ、销售话术、1天2次群发 SOP、课程货盘。

## 文件说明

- `yuanfudao_qa_pairs_ready.md`：推荐上传知识库的 Markdown 版本。
- `yuanfudao_qa_pairs_for_kb.txt`：纯文本导入版。
- `yuanfudao_qa_pairs.csv`：CSV 结构化版本。
- `yuanfudao_qa_pairs.jsonl`：JSONL 结构化版本。

## 生成原则

- FAQ 直接使用原 question/answer。
- 销售话术按产品和场景生成问题，答案保留话术正文。
- SOP 按产品、天数、群发序号生成问题，答案包含发送时间、触发条件、群发内容和报名动作。
- 课程货盘按 SKU 生成产品事实问答，并额外生成价格、适用人群问答。
- 不编造源文件没有明确写出的事实。
""",
        encoding="utf-8",
    )

    zip_path = RELEASE_ROOT.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in RELEASE_ROOT.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(RELEASE_ROOT.parent).as_posix())


def sync_to_volcengine() -> None:
    if not VOLCENGINE_ROOT.exists():
        return
    qa_dir = VOLCENGINE_ROOT / "06_qa_pairs"
    if qa_dir.exists():
        shutil.rmtree(qa_dir)
    qa_dir.mkdir(parents=True, exist_ok=True)
    for src in RELEASE_ROOT.iterdir():
        if src.is_file():
            shutil.copy2(src, qa_dir / src.name)

    md_target = VOLCENGINE_ROOT / "01_markdown_upload" / "05_猿辅导QA对知识库.md"
    txt_target = VOLCENGINE_ROOT / "02_txt_upload" / "04_猿辅导QA对导入版.txt"
    md_target.parent.mkdir(parents=True, exist_ok=True)
    txt_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RELEASE_ROOT / "yuanfudao_qa_pairs_ready.md", md_target)
    shutil.copy2(RELEASE_ROOT / "yuanfudao_qa_pairs_for_kb.txt", txt_target)

    readme = VOLCENGINE_ROOT / "README_火山知识库上传说明.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        text = text.replace(
            "2. `01_markdown_upload/04_猿辅导课程货盘知识库.md`\n   - 课程货盘/产品事实清洗版.",
            "2. `01_markdown_upload/04_猿辅导课程货盘知识库.md`\n   - 课程货盘/产品事实清洗版.\n3. `01_markdown_upload/05_猿辅导QA对知识库.md`\n   - FAQ、话术、SOP、课程货盘抽取出的 QA 对.",
        )
        text = text.replace("3. 或者分别上传：", "4. 或者分别上传：")
        text = text.replace("   - `01_markdown_upload/04_猿辅导课程货盘知识库.md`", "   - `01_markdown_upload/04_猿辅导课程货盘知识库.md`\n   - `01_markdown_upload/05_猿辅导QA对知识库.md`")
        text = text.replace("4. 如果平台对 Markdown 解析不好", "5. 如果平台对 Markdown 解析不好")
        text = text.replace("5. `03_by_product_markdown/`", "6. `03_by_product_markdown/`")
        text = text.replace("6. `04_structured_data/`", "7. `04_structured_data/`")
        text = text.replace("7. `05_course_catalog/`", "8. `05_course_catalog/`")
        if "9. `06_qa_pairs/`" not in text:
            text = text.replace(
                "8. `05_course_catalog/` 是课程货盘的 Markdown、TXT、CSV、JSONL 版本。",
                "8. `05_course_catalog/` 是课程货盘的 Markdown、TXT、CSV、JSONL 版本。\n9. `06_qa_pairs/` 是 QA 对的 Markdown、TXT、CSV、JSONL 版本。",
            )
        text = text.replace(
            "- 课程货盘/产品事实：21 条课程或商品记录",
            "- 课程货盘/产品事实：21 条课程或商品记录\n- QA 对：由 FAQ、话术、SOP、课程货盘抽取生成",
        )
        readme.write_text(text, encoding="utf-8")

    zip_path = Path("release/yuanfudao-volcengine-kb-upload.zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in VOLCENGINE_ROOT.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(VOLCENGINE_ROOT.parent).as_posix())


def main() -> None:
    items: list[dict[str, str]] = []
    build_faq_talk_qa(items)
    build_sop_qa(items)
    build_course_catalog_qa(items)
    write_outputs(items)
    sync_to_volcengine()
    print(
        json.dumps(
            {
                "qa_pairs": len(items),
                "output_dir": str(RELEASE_ROOT),
                "zip": str(RELEASE_ROOT.with_suffix(".zip")),
                "volcengine_zip": "release/yuanfudao-volcengine-kb-upload.zip" if VOLCENGINE_ROOT.exists() else "",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
