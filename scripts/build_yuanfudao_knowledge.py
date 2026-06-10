from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


DEFAULT_SOURCE = Path(r'C:\Users\C2023\Downloads\猿辅导知识库')
DEFAULT_OUTPUT = Path('src/langbot/resources/templates/course-sales/yuanfudao-knowledge')
FRESHNESS_RANGE = '2024-2026'
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
IMPORTABLE_KINDS = {'markdown', 'spreadsheet', 'pdf'}


@dataclass
class SourceFile:
    path: Path
    extension: str
    kind: str
    category: str
    indexed: bool
    upload_ready: bool
    note: str


def _document_storage_name(source_dir: Path, path: Path) -> str:
    rel = path.relative_to(source_dir)
    flattened = '__'.join(rel.parts) if len(rel.parts) > 1 else rel.name
    return _safe_name(flattened)


def _safe_name(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    normalized = re.sub(r'[\\/:*?"<>|]+', '_', stem).strip(' .')
    normalized = re.sub(r'\s+', ' ', normalized)
    return f'{normalized or "untitled"}{suffix}'


def _category_for_name(name: str) -> str:
    lowered = name.lower()
    if any(token in name for token in ['自然拼读', '自拼', '英语', '剑桥']):
        return '英语与自然拼读'
    if any(token in name for token in ['奥数', '思维', '数学', '原型题', '满分冲刺']):
        return '数学与思维'
    if any(token in name for token in ['语文', '人文', '博雅', '阅读', '作文']):
        return '语文与人文素养'
    if any(token in name for token in ['SOP', 'sop', '话术', '私域', '社群', 'TMK', '群发']):
        return '销售话术与私域SOP'
    if any(token in name for token in ['货盘', '课程问答', '产品', '价格', '课表']):
        return '产品货盘与课程资料'
    if any(token in lowered for token in ['mp4', 'mov', '视频']):
        return '视频素材'
    if any(token in name for token in ['品牌', '宣传', '介绍']):
        return '品牌介绍与宣传素材'
    return '综合资料'


def _kind_for_extension(extension: str) -> str:
    return {
        '.md': 'markdown',
        '.xlsx': 'spreadsheet',
        '.pdf': 'pdf',
        '.pptx': 'presentation',
        '.mp4': 'video',
        '.mov': 'video',
    }.get(extension, 'asset')


def _scan_source(source_dir: Path) -> list[SourceFile]:
    files: list[SourceFile] = []
    for path in sorted(source_dir.rglob('*'), key=lambda item: item.name):
        if not path.is_file():
            continue
        extension = path.suffix.lower()
        kind = _kind_for_extension(extension)
        indexed = kind in IMPORTABLE_KINDS
        upload_ready = path.stat().st_size <= MAX_UPLOAD_BYTES and kind in IMPORTABLE_KINDS
        if kind == 'video':
            note = '视频素材保留在来源清单中，不进入默认RAG文本语料。'
        elif not upload_ready and kind in {'pdf', 'spreadsheet'}:
            note = '超过前端500MB上传限制；默认用清单或表格摘录进入知识库。'
        elif indexed:
            note = '已纳入可检索文本语料。'
        else:
            note = '作为原始附件来源记录。'
        files.append(
            SourceFile(
                path=path,
                extension=extension,
                kind=kind,
                category=_category_for_name(path.name),
                indexed=indexed,
                upload_ready=upload_ready,
                note=note,
            )
        )
    return files


def _read_markdown(path: Path) -> str:
    text = path.read_text(encoding='utf-8-sig', errors='replace')
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()


def _xml_text(element: ElementTree.Element) -> str:
    return ''.join(element.itertext()).strip()


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
    except KeyError:
        return []
    except ElementTree.ParseError:
        return []
    return [_xml_text(item) for item in root.iter() if item.tag.endswith('}si') or item.tag == 'si']


def _xlsx_relationships(archive: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    except KeyError:
        return {}
    relationships: dict[str, str] = {}
    for rel in root:
        rel_id = rel.attrib.get('Id')
        target = rel.attrib.get('Target', '')
        if rel_id and target:
            relationships[rel_id] = target if target.startswith('xl/') else f'xl/{target}'
    return relationships


def _xlsx_sheet_entries(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    try:
        root = ElementTree.fromstring(archive.read('xl/workbook.xml'))
    except (KeyError, ElementTree.ParseError):
        return []
    rels = _xlsx_relationships(archive)
    entries: list[tuple[str, str]] = []
    rel_attr = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    for sheet in root.iter():
        if not sheet.tag.endswith('}sheet') and sheet.tag != 'sheet':
            continue
        name = sheet.attrib.get('name', 'Sheet')
        rel_id = sheet.attrib.get(rel_attr) or sheet.attrib.get('r:id')
        target = rels.get(rel_id or '')
        if target:
            entries.append((name, target))
    return entries


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    value_node = next((child for child in cell if child.tag.endswith('}v') or child.tag == 'v'), None)
    inline_node = next((child for child in cell if child.tag.endswith('}is') or child.tag == 'is'), None)
    if inline_node is not None:
        return _xml_text(inline_node)
    if value_node is None or value_node.text is None:
        return ''
    value = value_node.text.strip()
    if cell.attrib.get('t') == 's':
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value
    return value


def _preview_xlsx(path: Path, max_rows: int = 8) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            shared_strings = _xlsx_shared_strings(archive)
            sheets = []
            for name, target in _xlsx_sheet_entries(archive):
                try:
                    root = ElementTree.fromstring(archive.read(target))
                except (KeyError, ElementTree.ParseError):
                    continue
                dimension = ''
                for element in root.iter():
                    if element.tag.endswith('}dimension') or element.tag == 'dimension':
                        dimension = element.attrib.get('ref', '')
                        break
                rows: list[list[str]] = []
                for row in root.iter():
                    if not (row.tag.endswith('}row') or row.tag == 'row'):
                        continue
                    values = [
                        _xlsx_cell_value(cell, shared_strings)
                        for cell in row
                        if cell.tag.endswith('}c') or cell.tag == 'c'
                    ]
                    if any(values):
                        rows.append(values)
                    if len(rows) >= max_rows:
                        break
                sheets.append({'name': name, 'dimension': dimension, 'preview_rows': rows})
            return {'sheets': sheets, 'error': ''}
    except zipfile.BadZipFile as exc:
        return {'sheets': [], 'error': str(exc)}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _markdown_table(rows: list[list[str]]) -> str:
    if not rows:
        return ''
    width = max(len(row) for row in rows)
    normalized = [row + [''] * (width - len(row)) for row in rows]
    header = normalized[0]
    body = normalized[1:]
    lines = [
        '| ' + ' | '.join(cell.replace('|', '\\|') for cell in header) + ' |',
        '| ' + ' | '.join('---' for _ in header) + ' |',
    ]
    for row in body:
        lines.append('| ' + ' | '.join(cell.replace('|', '\\|') for cell in row) + ' |')
    return '\n'.join(lines)


def build_knowledge_pack(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    if not source_dir.exists():
        raise FileNotFoundError(f'Source directory not found: {source_dir}')

    if output_dir.exists():
        shutil.rmtree(output_dir)
    rag_dir = output_dir / 'rag'
    raw_md_dir = output_dir / 'raw-markdown'
    documents_dir = output_dir / 'documents'
    rag_dir.mkdir(parents=True, exist_ok=True)
    raw_md_dir.mkdir(parents=True, exist_ok=True)
    documents_dir.mkdir(parents=True, exist_ok=True)

    source_files = _scan_source(source_dir)
    markdown_sections: list[str] = [
        '# 猿辅导销售知识库 Markdown 语料',
        '',
        f'> 资料范围：{FRESHNESS_RANGE}。回答价格、排期、权益、赠品、活动有效期时，必须以最新活动页、班主任通知、系统后台为准；历史资料优先用于学习话术、异议处理和产品表达。',
        '',
    ]
    spreadsheet_sections: list[str] = [
        '# 猿辅导销售知识库 表格摘录',
        '',
        f'> 表格来源于飞书导出的 `.xlsx`，仅抽取 sheet 名称、范围和前几行预览。完整价格、货盘、排期以原始表格和最新后台为准。',
        '',
    ]

    copied_markdown: list[str] = []
    document_files: list[dict[str, Any]] = []
    spreadsheet_previews: dict[str, Any] = {}
    for item in source_files:
        if item.upload_ready and item.kind in IMPORTABLE_KINDS:
            storage_name = _document_storage_name(source_dir, item.path)
            target = documents_dir / storage_name
            shutil.copy2(item.path, target)
            document_files.append(
                {
                    'path': f'documents/{storage_name}',
                    'source_name': item.path.name,
                    'storage_name': storage_name,
                    'kind': item.kind,
                    'category': item.category,
                    'size_bytes': item.path.stat().st_size,
                }
            )
        if item.kind == 'markdown':
            safe_name = _safe_name(item.path.name)
            target = raw_md_dir / safe_name
            shutil.copy2(item.path, target)
            copied_markdown.append(safe_name)
            markdown_sections.extend([
                f'## 来源：{item.path.name}',
                '',
                f'- 分类：{item.category}',
                f'- 时效：{FRESHNESS_RANGE} 资料，具体政策按最新口径核对',
                '',
                _read_markdown(item.path),
                '',
            ])
        elif item.kind == 'spreadsheet':
            preview = _preview_xlsx(item.path)
            spreadsheet_previews[item.path.name] = preview
            spreadsheet_sections.extend([
                f'## 来源：{item.path.name}',
                '',
                f'- 分类：{item.category}',
                f'- 文件大小：{item.path.stat().st_size} bytes',
                f'- 备注：{item.note}',
                '',
            ])
            if preview.get('error'):
                spreadsheet_sections.extend([f'- 解析失败：{preview["error"]}', ''])
            for sheet in preview.get('sheets', []):
                spreadsheet_sections.extend([
                    f'### Sheet：{sheet["name"]}',
                    '',
                    f'- 范围：{sheet.get("dimension") or "未知"}',
                    '',
                ])
                table = _markdown_table(sheet.get('preview_rows') or [])
                if table:
                    spreadsheet_sections.extend([table, ''])

    (rag_dir / 'yuanfudao_markdown_corpus.md').write_text('\n'.join(markdown_sections).strip() + '\n', encoding='utf-8')
    (rag_dir / 'yuanfudao_spreadsheet_catalog.md').write_text(
        '\n'.join(spreadsheet_sections).strip() + '\n',
        encoding='utf-8',
    )

    files_payload = [
        {
            'name': item.path.name,
            'extension': item.extension,
            'kind': item.kind,
            'category': item.category,
            'size_bytes': item.path.stat().st_size,
            'indexed': item.indexed,
            'upload_ready': item.upload_ready,
            'note': item.note,
        }
        for item in source_files
    ]
    by_category: dict[str, list[str]] = {}
    for item in files_payload:
        by_category.setdefault(item['category'], []).append(item['name'])

    manifest = {
        'knowledge_base': {
            'name': '猿辅导销售知识库',
            'description': '猿辅导对外产品介绍、课程货盘、销售话术、私域SOP、品牌宣传和学科资料整理包。',
            'freshness_policy': {
                'range': FRESHNESS_RANGE,
                'answering_rule': '价格、排期、权益、赠品、活动有效期以最新活动页、班主任通知、系统后台为准；历史资料用于话术学习和异议处理。',
            },
            'rag_files': [
                'rag/yuanfudao_knowledge_index.md',
                'rag/yuanfudao_markdown_corpus.md',
                'rag/yuanfudao_spreadsheet_catalog.md',
            ],
        },
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'source_label': source_dir.name,
        'total_files': len(source_files),
        'files': files_payload,
        'copied_markdown': copied_markdown,
        'document_files': document_files,
        'spreadsheet_previews': spreadsheet_previews,
    }

    index_lines = [
        '# 猿辅导销售知识库索引',
        '',
        f'- 资料范围：{FRESHNESS_RANGE}',
        '- 使用原则：销售助手可学习产品表达、话术SOP、异议处理和资料说明；涉及价格、排期、优惠、赠品、名额、活动截止等强时效信息时，必须提示以最新活动页、班主任通知、系统后台为准。',
        f'- 文件总数：{len(source_files)}',
        f'- Markdown：{sum(1 for item in source_files if item.kind == "markdown")}',
        f'- Excel：{sum(1 for item in source_files if item.kind == "spreadsheet")}',
        f'- PDF：{sum(1 for item in source_files if item.kind == "pdf")}',
        f'- 视频：{sum(1 for item in source_files if item.kind == "video")}（默认不入RAG文本语料）',
        '',
        '## 推荐上传到前端知识库的文件',
        '',
        '- `rag/yuanfudao_knowledge_index.md`',
        '- `rag/yuanfudao_markdown_corpus.md`',
        '- `rag/yuanfudao_spreadsheet_catalog.md`',
        '',
        '## 分类清单',
        '',
    ]
    for category in sorted(by_category):
        index_lines.extend([f'### {category}', ''])
        for name in sorted(by_category[category]):
            index_lines.append(f'- {name}')
        index_lines.append('')
    (rag_dir / 'yuanfudao_knowledge_index.md').write_text('\n'.join(index_lines).strip() + '\n', encoding='utf-8')

    readme_lines = [
        '# 猿辅导销售知识库',
        '',
        '这个目录由 `scripts/build_yuanfudao_knowledge.py` 从飞书导出的资料包生成。',
        '',
        '## 自动导入到知识库文档',
        '',
        f'- `documents/` 目录包含 {len(document_files)} 个可导入文件（Markdown / Excel / PDF，不含视频与 PPT）。',
        '- 后端启动时会自动把这些文件导入「猿辅导销售知识库」。',
        '',
        '## 聚合检索语料',
        '',
        '- `rag/yuanfudao_knowledge_index.md`',
        '- `rag/yuanfudao_markdown_corpus.md`',
        '- `rag/yuanfudao_spreadsheet_catalog.md`',
        '',
        '原始视频和超过 500MB 的文件不会进入知识库文档；如需要逐个查看，回到下载目录的原始资料。',
        '',
        '## 时效规则',
        '',
        manifest['knowledge_base']['freshness_policy']['answering_rule'],
        '',
    ]
    (output_dir / 'README.md').write_text('\n'.join(readme_lines), encoding='utf-8')
    _write_json(output_dir / 'manifest.json', manifest)

    return {
        'total_files': len(source_files),
        'document_files': len(document_files),
        'output_dir': str(output_dir),
        'rag_files': manifest['knowledge_base']['rag_files'],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Build Yuanfudao sales knowledge pack.')
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_knowledge_pack(args.source, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
