from __future__ import annotations

from langbot.pkg.rag.knowledge.text_normalize import (
    clean_ingestion_text,
    has_extractable_document_text,
    is_meaningful_chunk,
    is_meaningful_document,
)

FEISHU_IMAGE = (
    '![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/'
    '?code=YzNlNTc0NmI2ZDgwNWM0ZTVlOWFmNGNlYjNkMTEzNWNfZGIzNjA1OWI4N2MyZTZlMjQyMGRlOWE3YzRjZTdmZmZf'
    'SUQ6NzYxMzQ0Mzk4Mzg2NzQzMTg3NF8xNzgxMDU3OTc2OjE3ODExNDQzNzZfVjM)'
)
HTML_TABLE = (
    "<tr><td style='text-align: center;'>第一人称</td>"
    "<td style='text-align: center;'>I</td>"
    "<td style='text-align: center;'>me</td></tr>"
    "<tr><td style='text-align: center;'>地点副词</td>"
    "<td style='text-align: center;'>here, there, everywhere</td></tr>"
)


def test_clean_ingestion_text_removes_feishu_image_links():
    text = f'自然拼读很重要。{FEISHU_IMAGE}\n\n适合小学英语启蒙。'
    cleaned = clean_ingestion_text(text)
    assert 'feishu.cn' not in cleaned
    assert 'authcode/?code=' not in cleaned
    assert '自然拼读很重要' in cleaned
    assert '适合小学英语启蒙' in cleaned


def test_clean_ingestion_text_strips_html_tables():
    cleaned = clean_ingestion_text(HTML_TABLE)
    assert '<td' not in cleaned
    assert '第一人称' in cleaned
    assert 'I' in cleaned
    assert '地点副词' in cleaned
    assert 'everywhere' in cleaned


def test_is_meaningful_chunk_rejects_url_fragments():
    assert is_meaningful_chunk('authcode/?code=YzNlNTc0NmI2ZDgwNWM0ZTVl') is False


def test_is_meaningful_chunk_accepts_sales_copy():
    text = '自然拼读是我们英语的底层逻辑，学会自然拼读可以让孩子快速增加单词储备量。'
    assert is_meaningful_chunk(text) is True


def test_has_extractable_document_text_rejects_empty_pdf_output():
    assert has_extractable_document_text('   ') is False


def test_has_extractable_document_text_rejects_watermark_only_poster():
    text = (
        'YUANFUDAO YUANFUDAO YUANFUDAO '
        '猿辅导 小学生必背古诗词 1-6 YUANFUDAO YUANFUDAO'
    )
    assert is_meaningful_document(text) is False
    assert has_extractable_document_text(text) is False


def test_has_extractable_document_text_accepts_real_sales_copy():
    text = clean_ingestion_text(
        '自然拼读是我们英语的底层逻辑，学会自然拼读可以让孩子快速增加单词储备量。'
        * 20
    )
    assert has_extractable_document_text(text) is True
    assert is_meaningful_document(text) is True


def test_is_meaningful_document_rejects_empty_text():
    assert is_meaningful_document('') is False
    assert is_meaningful_document('   ') is False


def test_is_meaningful_document_rejects_watermark_garbage():
    garbage = (
        'e YUANFUDAO e YUANFUDAO e YUANFUDAO\n'
        '1-6\nD猿辅导\n小学生必背古诗词\n'
        ',; YUANFUDAO ,; YUANFUDAO ,; YUANFUDAO'
    )
    assert is_meaningful_document(garbage) is False


def test_is_meaningful_document_accepts_real_chinese_copy():
    text = (
        '自然拼读是我们英语的底层逻辑，学会自然拼读可以让孩子快速增加单词储备量。'
        '课程覆盖小学核心词汇与常见语法点，适合作为销售话术中的专业背书。'
        '家长常问的问题包括课程时长、师资背景、续费政策与退费规则，需要结合最新活动页说明。'
    )
    assert is_meaningful_document(text) is True
