from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
from openai import OpenAI


KB_UUID = "yuanfudao-sales-knowledge-base"
DEFAULT_FAQ_TALK_DIR = Path("outputs/yuanfudao-selected-faq-talk-cleaning/knowledge_base_ready")
DEFAULT_SOP_DIR = Path("outputs/yuanfudao-selected-faq-talk-cleaning/sop_ready")
DEFAULT_COURSE_DIR = Path("release/yuanfudao-course-catalog-cleaned")
DEFAULT_QA_DIR = Path("release/yuanfudao-qa-pairs-cleaned")
DEFAULT_TEMPLATE_DIR = Path("src/langbot/resources/templates/course-sales/yuanfudao-knowledge")
DEFAULT_DB_PATH = Path("data/langbot.db")
DEFAULT_CHROMA_PATH = Path("data/chroma")
DEFAULT_RELEASE_DIR = Path("release/yuanfudao-clean-knowledge-base")
CHUNK_SIZE = 250
CHUNK_OVERLAP = 50
EMBED_BATCH_SIZE = 10


@dataclass
class ReleaseDocument:
    filename: str
    title: str
    category: str
    source_path: Path


def compact(text: str) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = compact(text)
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end].strip()
        if len(chunk) >= 8:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def load_embedding_client(db_path: Path) -> tuple[OpenAI, dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    model = conn.execute(
        "SELECT * FROM embedding_models WHERE uuid = 'lne-baidu-bge-large-zh'"
    ).fetchone()
    if model is None:
        raise RuntimeError("Embedding model lne-baidu-bge-large-zh not found")
    provider = conn.execute(
        "SELECT * FROM model_providers WHERE uuid = ?",
        (model["provider_uuid"],),
    ).fetchone()
    if provider is None:
        raise RuntimeError(f"Provider {model['provider_uuid']} not found")
    keys = json.loads(provider["api_keys"] or "[]")
    if not keys:
        raise RuntimeError("Embedding provider has no API key configured")
    extra_args = json.loads(model["extra_args"] or "{}")
    client = OpenAI(api_key=keys[0], base_url=provider["base_url"])
    conn.close()
    return client, {"model": model["name"], **extra_args}


def embed_texts(client: OpenAI, model_args: dict[str, Any], texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                resp = client.embeddings.create(input=batch, **model_args)
                vectors.extend([item.embedding for item in resp.data])
                break
            except Exception as exc:  # pragma: no cover - network/provider failures vary.
                last_error = exc
                if attempt >= 3:
                    raise
                time.sleep(2**attempt)
        if last_error is not None and len(vectors) < start + len(batch):
            raise last_error
    return vectors


def build_release_documents(
    faq_talk_dir: Path,
    sop_dir: Path,
    course_dir: Path,
    qa_dir: Path,
) -> list[ReleaseDocument]:
    return [
        ReleaseDocument(
            filename="01_yuanfudao_faq_ready.md",
            title="猿辅导 FAQ 知识库",
            category="FAQ",
            source_path=faq_talk_dir / "yuanfudao_faq_ready.md",
        ),
        ReleaseDocument(
            filename="02_yuanfudao_talk_scripts_ready.md",
            title="猿辅导销售话术知识库",
            category="销售话术",
            source_path=faq_talk_dir / "yuanfudao_talk_scripts_ready.md",
        ),
        ReleaseDocument(
            filename="03_yuanfudao_group_sop_ready.md",
            title="猿辅导 1天2次群发 SOP 知识库",
            category="群发SOP",
            source_path=sop_dir / "yuanfudao_group_sop_combined.md",
        ),
        ReleaseDocument(
            filename="04_yuanfudao_course_catalog_ready.md",
            title="猿辅导课程货盘知识库",
            category="课程货盘/产品事实",
            source_path=course_dir / "yuanfudao_course_catalog_ready.md",
        ),
        ReleaseDocument(
            filename="05_yuanfudao_qa_pairs_ready.md",
            title="猿辅导 QA 对知识库",
            category="QA对",
            source_path=qa_dir / "yuanfudao_qa_pairs_ready.md",
        ),
    ]


def write_template_pack(template_dir: Path, documents: list[ReleaseDocument]) -> None:
    if template_dir.exists():
        for child_name in ("documents", "raw-markdown", "rag"):
            child = template_dir / child_name
            if child.exists():
                shutil.rmtree(child)
    docs_dir = template_dir / "documents"
    raw_dir = template_dir / "raw-markdown"
    rag_dir = template_dir / "rag"
    docs_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    rag_dir.mkdir(parents=True, exist_ok=True)

    manifest_docs: list[dict[str, Any]] = []
    combined_sections = [
        "# 猿辅导清洗版销售知识库语料",
        "",
        "> 本语料包含已审阅的话术、FAQ、群发 SOP、课程货盘和 QA 对。实时价格、排期、赠品和退款政策仍需以最新活动页、班主任通知和系统后台为准。",
        "",
    ]
    index_lines = [
        "# 猿辅导清洗版销售知识库索引",
        "",
        "- 当前版本：FAQ + 销售话术 + 1天2次群发 SOP + 课程货盘 + QA 对",
        "- 不含：实时活动政策、价格排期权威口径、图片/视频素材本体",
        "- 使用规则：涉及价格、赠品、包邮、名额、链接、退款、排期时，必须以最新活动页/班主任通知/系统后台为准。",
        "",
        "## 入库文件",
        "",
    ]
    for doc in documents:
        if not doc.source_path.exists():
            raise FileNotFoundError(doc.source_path)
        content = compact(doc.source_path.read_text(encoding="utf-8"))
        (docs_dir / doc.filename).write_text(content + "\n", encoding="utf-8")
        (raw_dir / doc.filename).write_text(content + "\n", encoding="utf-8")
        combined_sections.extend([f"## {doc.title}", "", content, ""])
        index_lines.append(f"- `{doc.filename}`：{doc.category}")
        manifest_docs.append(
            {
                "path": f"documents/{doc.filename}",
                "source_name": doc.source_path.name,
                "storage_name": doc.filename,
                "kind": "markdown",
                "category": doc.category,
                "size_bytes": (docs_dir / doc.filename).stat().st_size,
            }
        )

    (rag_dir / "yuanfudao_knowledge_index.md").write_text(
        "\n".join(index_lines).strip() + "\n",
        encoding="utf-8",
    )
    (rag_dir / "yuanfudao_markdown_corpus.md").write_text(
        "\n".join(combined_sections).strip() + "\n",
        encoding="utf-8",
    )
    (rag_dir / "yuanfudao_spreadsheet_catalog.md").write_text(
        "# 猿辅导清洗版表格结构化数据说明\n\n"
        "本版本已将原始 Excel 中的 FAQ、话术和 SOP 清洗为 Markdown/JSONL/CSV。"
        "运行时知识库默认导入 Markdown 正文，结构化 JSONL/CSV 随 release 包提供。\n",
        encoding="utf-8",
    )
    manifest = {
        "knowledge_base": {
            "name": "猿辅导销售知识库",
            "description": "猿辅导已审阅 FAQ、销售话术、1天2次群发 SOP、课程货盘与 QA 对清洗版。",
            "freshness_policy": {
                "range": "cleaned-2026-06-18",
                "answering_rule": "价格、排期、权益、赠品、活动有效期、退款政策以最新活动页、班主任通知、系统后台为准；本知识库用于 FAQ、话术、SOP、课程货盘和 QA 对检索。",
            },
            "rag_files": [
                "rag/yuanfudao_knowledge_index.md",
                "rag/yuanfudao_markdown_corpus.md",
                "rag/yuanfudao_spreadsheet_catalog.md",
            ],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_label": "yuanfudao-clean-faq-talk-sop-course-qa",
        "total_files": len(documents),
        "document_files": manifest_docs,
        "files": [
            {
                "name": doc.filename,
                "extension": ".md",
                "kind": "markdown",
                "category": doc.category,
                "size_bytes": (docs_dir / doc.filename).stat().st_size,
                "indexed": True,
                "upload_ready": True,
                "note": "已审阅清洗，可入库。",
            }
            for doc in documents
        ],
        "known_gaps": [
            "实时价格、赠品、包邮、名额、退款、排期仍需以最新活动页、班主任通知和系统后台为准。",
            "图片/视频素材未进入文本知识库。",
        ],
    }
    (template_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (template_dir / "README.md").write_text(
        "# 猿辅导销售知识库\n\n"
        "这个目录是清洗后的 FAQ、销售话术、1天2次群发 SOP、课程货盘和 QA 对入库包。\n\n"
        "## 自动导入到知识库文档\n\n"
        f"- `documents/` 目录包含 {len(documents)} 个 Markdown 入库文件。\n"
        "- 后端启动时会自动把这些文件导入「猿辅导销售知识库」。\n\n"
        "## 聚合检索语料\n\n"
        "- `rag/yuanfudao_knowledge_index.md`\n"
        "- `rag/yuanfudao_markdown_corpus.md`\n"
        "- `rag/yuanfudao_spreadsheet_catalog.md`\n\n"
        "## 缺口说明\n\n"
        "- 价格、赠品、包邮、名额、退款、排期等强时效内容需以后续最新口径为准。\n",
        encoding="utf-8",
    )


def backup_local_state(db_path: Path, chroma_path: Path, release_dir: Path) -> dict[str, str]:
    backup_dir = release_dir / "_local_backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    db_backup = backup_dir / db_path.name
    shutil.copy2(db_path, db_backup)
    chroma_backup = backup_dir / "chroma"
    if chroma_path.exists():
        shutil.copytree(chroma_path, chroma_backup)
    return {"db_backup": str(db_backup), "chroma_backup": str(chroma_backup)}


def reset_db_file_records(db_path: Path, documents: list[ReleaseDocument]) -> list[dict[str, str]]:
    conn = sqlite3.connect(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("DELETE FROM knowledge_base_chunks WHERE file_id IN (SELECT uuid FROM knowledge_base_files WHERE kb_id = ?)", (KB_UUID,))
    conn.execute("DELETE FROM knowledge_base_files WHERE kb_id = ?", (KB_UUID,))
    conn.execute(
        "UPDATE knowledge_bases SET description = ?, updated_at = ? WHERE uuid = ?",
        (
            "猿辅导已审阅 FAQ、销售话术、1天2次群发 SOP、课程货盘与 QA 对清洗版。",
            now,
            KB_UUID,
        ),
    )
    rows: list[dict[str, str]] = []
    for doc in documents:
        file_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{KB_UUID}:{doc.filename}"))
        conn.execute(
            "INSERT INTO knowledge_base_files (uuid, kb_id, file_name, extension, created_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            (file_id, KB_UUID, doc.filename, "md", now, "completed"),
        )
        rows.append({"uuid": file_id, "file_name": doc.filename})
    conn.commit()
    conn.close()
    return rows


def rebuild_chroma(
    chroma_path: Path,
    db_path: Path,
    template_dir: Path,
    db_files: list[dict[str, str]],
) -> dict[str, Any]:
    client = chromadb.PersistentClient(path=str(chroma_path))
    try:
        client.delete_collection(KB_UUID)
    except Exception:
        pass
    collection = client.get_or_create_collection(KB_UUID)
    embed_client, model_args = load_embedding_client(db_path)

    ids: list[str] = []
    metadatas: list[dict[str, Any]] = []
    chunks: list[str] = []
    for file in db_files:
        path = template_dir / "documents" / file["file_name"]
        text = path.read_text(encoding="utf-8")
        for index, chunk in enumerate(split_text(text)):
            chunk_id = f"{file['uuid']}:{index}"
            ids.append(chunk_id)
            chunks.append(chunk)
            metadatas.append(
                {
                    "file_id": file["uuid"],
                    "knowledge_base_id": KB_UUID,
                    "filename": file["file_name"],
                    "document_name": file["file_name"],
                    "chunk_index": index,
                    "text": chunk,
                }
            )
    vectors = embed_texts(embed_client, model_args, chunks)
    for start in range(0, len(ids), 100):
        end = start + 100
        collection.upsert(
            ids=ids[start:end],
            embeddings=vectors[start:end],
            metadatas=metadatas[start:end],
            documents=chunks[start:end],
        )
    return {
        "collection": KB_UUID,
        "files": len(db_files),
        "chunks": len(chunks),
        "vectors": collection.count(),
        "embedding_dim": len(vectors[0]) if vectors else 0,
    }


def copy_tree_files(source: Path, target: Path) -> None:
    if not source.exists():
        return
    for path in source.rglob("*"):
        if path.is_file():
            rel = path.relative_to(source)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)


def write_release_package(
    release_dir: Path,
    faq_talk_dir: Path,
    sop_dir: Path,
    course_dir: Path,
    qa_dir: Path,
    template_dir: Path,
    summary: dict[str, Any],
) -> Path:
    if release_dir.exists():
        for child in release_dir.iterdir():
            if child.name == "_local_backups":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    release_dir.mkdir(parents=True, exist_ok=True)
    copy_tree_files(faq_talk_dir, release_dir / "faq_talk_ready")
    copy_tree_files(sop_dir, release_dir / "sop_ready")
    copy_tree_files(course_dir, release_dir / "course_catalog_ready")
    copy_tree_files(qa_dir, release_dir / "qa_pairs_ready")
    copy_tree_files(template_dir, release_dir / "langbot_template_pack")
    (release_dir / "release_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (release_dir / "README.md").write_text(
        "# 猿辅导清洗版知识库交付包\n\n"
        "包含 FAQ、销售话术、1天2次群发 SOP、课程货盘、QA 对的正式入库文件，以及 LangBot 模板目录。\n\n"
        "## 推荐用法\n\n"
        "1. 文档型知识库：上传 `langbot_template_pack/documents/*.md` 或 `faq_talk_ready` / `sop_ready` 中的 Markdown。\n"
        "2. 结构化知识库：使用 `faq_talk_ready/*.jsonl`、`faq_talk_ready/*.csv`、`sop_ready/*.jsonl`、`sop_ready/*.csv`。\n"
        "3. LangBot 项目：本仓库已把 `src/langbot/resources/templates/course-sales/yuanfudao-knowledge` 替换为清洗版模板。\n\n"
        "## 缺口\n\n"
        "- 价格、赠品、包邮、名额、退款、排期需要以后续最新活动页/班主任通知/系统后台为准。\n",
        encoding="utf-8",
    )
    zip_path = release_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in release_dir.rglob("*"):
            if path.is_file() and "_local_backups" not in path.parts:
                archive.write(path, path.relative_to(release_dir.parent))
    return zip_path


def count_csv(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--faq-talk-dir", type=Path, default=DEFAULT_FAQ_TALK_DIR)
    parser.add_argument("--sop-dir", type=Path, default=DEFAULT_SOP_DIR)
    parser.add_argument("--course-dir", type=Path, default=DEFAULT_COURSE_DIR)
    parser.add_argument("--qa-dir", type=Path, default=DEFAULT_QA_DIR)
    parser.add_argument("--template-dir", type=Path, default=DEFAULT_TEMPLATE_DIR)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE_DIR)
    parser.add_argument("--skip-db", action="store_true")
    args = parser.parse_args()

    documents = build_release_documents(args.faq_talk_dir, args.sop_dir, args.course_dir, args.qa_dir)
    write_template_pack(args.template_dir, documents)
    backup = {}
    db_files: list[dict[str, str]] = []
    chroma_summary: dict[str, Any] = {}
    if not args.skip_db:
        backup = backup_local_state(args.db_path, args.chroma_path, args.release_dir)
        db_files = reset_db_file_records(args.db_path, documents)
        chroma_summary = rebuild_chroma(args.chroma_path, args.db_path, args.template_dir, db_files)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "knowledge_base_uuid": KB_UUID,
        "documents": [doc.filename for doc in documents],
        "faq_records": count_csv(args.faq_talk_dir / "yuanfudao_kb_entries.csv"),
        "sop_records": count_csv(args.sop_dir / "yuanfudao_group_sop_entries.csv"),
        "course_catalog_records": count_csv(args.course_dir / "yuanfudao_course_catalog_entries.csv"),
        "qa_pairs": count_csv(args.qa_dir / "yuanfudao_qa_pairs.csv"),
        "known_gaps": [
            "实时价格、赠品、包邮、名额、退款、排期需要以最新活动页、班主任通知、系统后台为准。",
            "图片/视频素材未进入文本知识库。",
        ],
        "local_backup": backup,
        "database_files": len(db_files),
        "chroma": chroma_summary,
    }
    zip_path = write_release_package(
        args.release_dir,
        args.faq_talk_dir,
        args.sop_dir,
        args.course_dir,
        args.qa_dir,
        args.template_dir,
        summary,
    )
    summary["zip_path"] = str(zip_path)
    (args.release_dir / "release_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
