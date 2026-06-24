from __future__ import annotations

import re
import unicodedata

_MARKDOWN_IMAGE_RE = re.compile(r'!\[[^\]]*\]\([^)]+\)')
_URL_RE = re.compile(r'https?://[^\s)\]"\'<>]+', re.IGNORECASE)
_AUTHCODE_FRAGMENT_RE = re.compile(
    r'(?:download/)?authcode/\?code=[A-Za-z0-9+/=_-]+',
    re.IGNORECASE,
)
_LONG_ENCODED_TOKEN_RE = re.compile(r'[A-Za-z0-9+/=_-]{80,}')
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_ESCAPED_NEWLINE_RE = re.compile(r'\\[nrt]')
_MULTI_BLANK_LINE_RE = re.compile(r'\n{3,}')
_MULTI_SPACE_RE = re.compile(r'[ \t]{2,}')

_MIN_MEANINGFUL_CHUNK_CHARS = 24
_MIN_MEANINGFUL_RATIO = 0.45
_MIN_DOC_MEANINGFUL_CHARS = 120
_DEFAULT_CHUNK_SIZE = 250
_DEFAULT_CHUNK_OVERLAP = 50
_MIN_DOCUMENT_BODY_CHARS = 100
_MIN_CJK_DOCUMENT_CHARS = 80
_WATERMARK_RE = re.compile(r'yuans?fudao|猿辅导', re.IGNORECASE)


def _strip_html(text: str) -> str:
    normalized = text.replace('</tr>', '\n').replace('</td>', ' ')
    normalized = _HTML_TAG_RE.sub(' ', normalized)
    return normalized


def _normalize_whitespace(text: str) -> str:
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    normalized = _MULTI_BLANK_LINE_RE.sub('\n\n', normalized)
    lines = [_MULTI_SPACE_RE.sub(' ', line).strip() for line in normalized.split('\n')]
    return '\n'.join(line for line in lines if line).strip()


def _is_meaningful_char(char: str) -> bool:
    if char.isspace():
        return False
    category = unicodedata.category(char)
    if category.startswith('C'):
        return False
    if char.isalnum():
        return True
    if '\u4e00' <= char <= '\u9fff':
        return True
    return char in '，。！？、；：""''（）【】《》…—·,.!?;:\'"-+/\\'


def clean_ingestion_text(text: str) -> str:
    """Normalize extracted document text before chunking and embedding."""
    normalized = text.strip()
    if not normalized:
        return ''

    normalized = _MARKDOWN_IMAGE_RE.sub(' ', normalized)
    normalized = _URL_RE.sub(' ', normalized)
    normalized = _AUTHCODE_FRAGMENT_RE.sub(' ', normalized)
    normalized = _LONG_ENCODED_TOKEN_RE.sub(' ', normalized)
    normalized = _ESCAPED_NEWLINE_RE.sub(' ', normalized)

    if '<' in normalized and '>' in normalized:
        normalized = _strip_html(normalized)

    return _normalize_whitespace(normalized)


def _count_cjk_chars(text: str) -> int:
    return sum(1 for char in text if '\u4e00' <= char <= '\u9fff')


def is_meaningful_document(text: str) -> bool:
    """Return True when extracted document text is usable for retrieval indexing."""
    cleaned = clean_ingestion_text(text)
    if not cleaned:
        return False

    body = _normalize_whitespace(_WATERMARK_RE.sub(' ', cleaned))
    if len(body) < _MIN_DOCUMENT_BODY_CHARS:
        return False

    cjk_count = _count_cjk_chars(body)
    if 0 < cjk_count < _MIN_CJK_DOCUMENT_CHARS:
        return False

    return True


def count_meaningful_chars(text: str) -> int:
    return sum(1 for char in text if _is_meaningful_char(char))


def _split_for_validation(
    text: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    if chunk_size <= 0:
        chunk_size = _DEFAULT_CHUNK_SIZE
    if overlap < 0:
        overlap = 0
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end])
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def has_extractable_document_text(
    text: str,
    *,
    min_meaningful_chars: int = _MIN_DOC_MEANINGFUL_CHARS,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> bool:
    """Return True when cleaned document text is suitable for RAG ingestion."""
    cleaned = clean_ingestion_text(text)
    if not cleaned.strip():
        return False

    meaningful = count_meaningful_chars(cleaned)
    if meaningful < min_meaningful_chars:
        return False
    if meaningful / max(len(cleaned), 1) < _MIN_MEANINGFUL_RATIO:
        return False

    meaningful_chunks = [
        chunk for chunk in _split_for_validation(cleaned, chunk_size=chunk_size, overlap=chunk_overlap)
        if is_meaningful_chunk(chunk)
    ]
    return bool(meaningful_chunks)


def is_meaningful_chunk(text: str, *, min_chars: int = _MIN_MEANINGFUL_CHUNK_CHARS) -> bool:
    """Return True when a chunk contains enough readable text for retrieval."""
    stripped = text.strip()
    if len(stripped) < min_chars:
        return False

    lowered = stripped.lower()
    if 'authcode/?code=' in lowered or 'feishu.cn' in lowered:
        return False

    meaningful = sum(1 for char in stripped if _is_meaningful_char(char))
    if meaningful < min_chars:
        return False

    return meaningful / max(len(stripped), 1) >= _MIN_MEANINGFUL_RATIO
