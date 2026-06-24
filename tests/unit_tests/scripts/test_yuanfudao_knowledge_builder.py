import json
import zipfile
from pathlib import Path

from scripts.build_yuanfudao_knowledge import build_knowledge_pack


def _write_minimal_xlsx(path: Path) -> None:
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
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
            'Target="sharedStrings.xml"/>'
            '</Relationships>'
        ),
        'xl/sharedStrings.xml': (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><t>课程名称</t></si><si><t>价格</t></si>'
            '<si><t>自然拼读体验课</t></si><si><t>9元</t></si>'
            '</sst>'
        ),
        'xl/worksheets/sheet1.xml': (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<dimension ref="A1:B2"/>'
            '<sheetData>'
            '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
            '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row>'
            '</sheetData>'
            '</worksheet>'
        ),
    }
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_build_knowledge_pack_creates_manifest_and_rag_corpus(tmp_path):
    source = tmp_path / 'source'
    output = tmp_path / 'out'
    source.mkdir()
    (source / '自然拼读卖点话术更新.md').write_text(
        '# 自然拼读卖点话术更新\n\n9元体验课，支持回放。\n',
        encoding='utf-8',
    )
    _write_minimal_xlsx(source / '猿辅导课程货盘.xlsx')

    result = build_knowledge_pack(source, output)

    assert result['total_files'] == 2
    assert result['document_files'] == 2
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['document_files']) == 2
    assert manifest['knowledge_base']['name'] == '猿辅导销售知识库'
    assert manifest['knowledge_base']['freshness_policy']['range'] == '2024-2026'
    assert any(item['indexed'] for item in manifest['files'] if item['extension'] == '.md')
    assert any(item['kind'] == 'spreadsheet' for item in manifest['files'])

    corpus = (output / 'rag' / 'yuanfudao_markdown_corpus.md').read_text(encoding='utf-8')
    assert '自然拼读卖点话术更新' in corpus
    assert '9元体验课' in corpus

    spreadsheet_catalog = (output / 'rag' / 'yuanfudao_spreadsheet_catalog.md').read_text(encoding='utf-8')
    assert '猿辅导课程货盘.xlsx' in spreadsheet_catalog
    assert '课程名称' in spreadsheet_catalog
    assert '自然拼读体验课' in spreadsheet_catalog

    assert (output / 'documents' / '自然拼读卖点话术更新.md').exists()
    assert (output / 'documents' / '猿辅导课程货盘.xlsx').exists()
