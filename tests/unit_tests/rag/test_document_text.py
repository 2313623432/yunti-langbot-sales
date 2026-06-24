from __future__ import annotations

import zipfile
from pathlib import Path

from langbot.pkg.rag.knowledge.document_text import extract_text_from_bytes


def test_extract_text_from_markdown_bytes():
    content = '# 标题\n\n9元体验课'.encode('utf-8')
    assert '9元体验课' in extract_text_from_bytes('note.md', content)


def test_extract_text_from_xlsx_bytes(tmp_path):
    xlsx_path = tmp_path / 'sample.xlsx'
    files = {
        '[Content_Types].xml': (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            '</Types>'
        ),
        '_rels/.rels': (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '</Relationships>'
        ),
        'xl/workbook.xml': (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="课程货盘" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>'
        ),
        'xl/_rels/workbook.xml.rels': (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        ),
        'xl/sharedStrings.xml': (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><t>自然拼读体验课</t></si><si><t>9元</t></si>'
            '</sst>'
        ),
        'xl/worksheets/sheet1.xml': (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
            '</sheetData>'
            '</worksheet>'
        ),
    }
    with zipfile.ZipFile(xlsx_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)

    text = extract_text_from_bytes('sample.xlsx', xlsx_path.read_bytes())
    assert '自然拼读体验课' in text
    assert '9元' in text
