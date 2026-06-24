from __future__ import annotations

import asyncio
import io
import uuid
import zipfile
from pathlib import Path

import aiohttp

DEFAULT_BASE_URL = 'https://mineru.net/api/v4'
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_MAX_WAIT_SECONDS = 600.0
TERMINAL_STATES = frozenset({'done', 'failed'})


def _normalize_base_url(base_url: str) -> str:
    normalized = (base_url or DEFAULT_BASE_URL).strip().rstrip('/')
    if not normalized:
        return DEFAULT_BASE_URL
    return normalized


def extract_markdown_from_zip(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        for preferred in ('full.md',):
            for name in names:
                if name == preferred or name.endswith(f'/{preferred}'):
                    return archive.read(name).decode('utf-8', errors='ignore').strip()
        md_files = sorted(name for name in names if name.lower().endswith('.md'))
        if md_files:
            return archive.read(md_files[0]).decode('utf-8', errors='ignore').strip()
    return ''


async def extract_text_with_mineru_cloud(
    filename: str,
    content: bytes,
    *,
    token: str,
    base_url: str = DEFAULT_BASE_URL,
    model_version: str = 'vlm',
    is_ocr: bool = False,
    page_range: str = '',
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
) -> str:
    resolved_token = token.strip()
    if not resolved_token:
        return ''

    api_base = _normalize_base_url(base_url)
    data_id = uuid.uuid4().hex
    file_entry: dict[str, object] = {
        'name': Path(filename).name,
        'data_id': data_id,
    }
    if is_ocr:
        file_entry['is_ocr'] = True
    if page_range.strip():
        file_entry['page_ranges'] = page_range.strip()

    payload: dict[str, object] = {
        'files': [file_entry],
        'model_version': (model_version or 'vlm').strip() or 'vlm',
    }

    headers = {
        'Authorization': f'Bearer {resolved_token}',
        'Content-Type': 'application/json',
    }
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f'{api_base}/file-urls/batch', headers=headers, json=payload) as response:
            body = await response.json()
            if response.status != 200 or body.get('code') != 0:
                raise RuntimeError(f'MinerU batch upload request failed ({response.status}): {body}')
            data = body.get('data') or {}
            batch_id = str(data.get('batch_id') or '').strip()
            upload_urls = data.get('file_urls') or []
            if not batch_id or not upload_urls:
                raise RuntimeError(f'MinerU batch upload returned no batch_id or upload URLs: {body}')

        upload_url = str(upload_urls[0]).strip()
        async with session.put(upload_url, data=content) as upload_response:
            if upload_response.status != 200:
                upload_body = await upload_response.text()
                raise RuntimeError(
                    f'MinerU file upload failed ({upload_response.status}): {upload_body}'
                )

        zip_url = await _poll_batch_result(
            session,
            api_base=api_base,
            batch_id=batch_id,
            headers=headers,
            poll_interval=poll_interval,
            max_wait=max_wait,
        )
        if not zip_url:
            return ''

        async with session.get(zip_url) as zip_response:
            zip_response.raise_for_status()
            zip_content = await zip_response.read()

    return extract_markdown_from_zip(zip_content)


async def _poll_batch_result(
    session: aiohttp.ClientSession,
    *,
    api_base: str,
    batch_id: str,
    headers: dict[str, str],
    poll_interval: float,
    max_wait: float,
) -> str:
    deadline = asyncio.get_running_loop().time() + max_wait
    while asyncio.get_running_loop().time() < deadline:
        async with session.get(
            f'{api_base}/extract-results/batch/{batch_id}',
            headers=headers,
        ) as response:
            body = await response.json()
            if response.status != 200 or body.get('code') != 0:
                raise RuntimeError(f'MinerU batch poll failed ({response.status}): {body}')

            data = body.get('data') or {}
            extract_results = data.get('extract_result')
            if isinstance(extract_results, dict):
                extract_results = [extract_results]
            if not isinstance(extract_results, list) or not extract_results:
                await asyncio.sleep(poll_interval)
                continue

            result = extract_results[0]
            state = str(result.get('state') or '').strip()
            if state == 'done':
                return str(result.get('full_zip_url') or '').strip()
            if state == 'failed':
                error_msg = str(result.get('err_msg') or 'unknown error')
                raise RuntimeError(f'MinerU batch extraction failed: {error_msg}')
            if state in TERMINAL_STATES:
                return ''

        await asyncio.sleep(poll_interval)
    raise TimeoutError(f'MinerU batch {batch_id} timed out after {max_wait}s')
