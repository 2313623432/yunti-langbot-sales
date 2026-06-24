from __future__ import annotations

import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree

TEXT_EXTENSIONS = {'.md', '.txt', '.html', '.htm', '.csv'}


def extract_text_from_bytes(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension in TEXT_EXTENSIONS:
        return content.decode('utf-8', errors='ignore').strip()
    if extension == '.pdf':
        return _extract_pdf_text(content)
    if extension == '.xlsx':
        return _extract_xlsx_text(content)
    if extension == '.pptx':
        return _extract_pptx_text(content)
    return content.decode('utf-8', errors='ignore').strip()


def _extract_pdf_text(content: bytes) -> str:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return ''
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception:
        return ''
    pages: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ''
        except Exception:
            text = ''
        if text.strip():
            pages.append(text.strip())
    return '\n\n'.join(pages).strip()


def _xml_text(element: ElementTree.Element) -> str:
    return ''.join(element.itertext()).strip()


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
    except (KeyError, ElementTree.ParseError):
        return []
    return [_xml_text(item) for item in root.iter() if item.tag.endswith('}si') or item.tag == 'si']


def _xlsx_relationships(archive: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    except (KeyError, ElementTree.ParseError):
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


def _extract_xlsx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            shared_strings = _xlsx_shared_strings(archive)
            sections: list[str] = []
            for sheet_name, target in _xlsx_sheet_entries(archive):
                try:
                    root = ElementTree.fromstring(archive.read(target))
                except (KeyError, ElementTree.ParseError):
                    continue
                rows: list[str] = []
                for row in root.iter():
                    if not (row.tag.endswith('}row') or row.tag == 'row'):
                        continue
                    values = [
                        _xlsx_cell_value(cell, shared_strings)
                        for cell in row
                        if cell.tag.endswith('}c') or cell.tag == 'c'
                    ]
                    line = '\t'.join(value for value in values if value)
                    if line.strip():
                        rows.append(line)
                if rows:
                    sections.append(f'## Sheet: {sheet_name}\n\n' + '\n'.join(rows))
            return '\n\n'.join(sections).strip()
    except zipfile.BadZipFile:
        return ''


def _extract_pptx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            slide_names = sorted(
                name
                for name in archive.namelist()
                if name.startswith('ppt/slides/slide') and name.endswith('.xml')
            )
            sections: list[str] = []
            for index, slide_name in enumerate(slide_names, start=1):
                try:
                    root = ElementTree.fromstring(archive.read(slide_name))
                except (KeyError, ElementTree.ParseError):
                    continue
                texts = [
                    _xml_text(node)
                    for node in root.iter()
                    if node.tag.endswith('}t') or node.tag == 't'
                ]
                lines = [text for text in texts if text.strip()]
                if lines:
                    sections.append(f'## Slide {index}\n\n' + '\n'.join(lines))
            return '\n\n'.join(sections).strip()
    except zipfile.BadZipFile:
        return ''
