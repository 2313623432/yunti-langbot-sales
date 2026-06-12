from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

OCR_JOB_URL = 'https://paddleocr.aistudio-app.com/api/v2/ocr/jobs'
DEFAULT_OCR_MODEL = 'PaddleOCR-VL-1.6'
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_MAX_WAIT_SECONDS = 600.0

_DEFAULT_OPTIONAL_PAYLOAD = {
    'useDocOrientationClassify': False,
    'useDocUnwarping': False,
    'useChartRecognition': False,
}


@dataclass(frozen=True)
class PaddleOcrConfig:
    token: str
    job_url: str
    model: str


def get_paddleocr_token() -> str:
    return (
        (os.getenv('LNE_BAIDU_PADDLEOCR_TOKEN') or '').strip()
        or (os.getenv('LNE_BAIDU_EMBEDDING_API_KEY') or '').strip()
    )


def resolve_paddleocr_config(
    provider_entity: Any | None = None,
    extra_args: dict[str, Any] | None = None,
) -> PaddleOcrConfig:
    extra_args = extra_args or {}
    token = get_paddleocr_token()
    job_url = (os.getenv('LNE_BAIDU_PADDLEOCR_JOB_URL') or OCR_JOB_URL).strip()
    model = (os.getenv('LNE_BAIDU_PADDLEOCR_MODEL') or DEFAULT_OCR_MODEL).strip()

    if provider_entity is not None:
        provider_base_url = str(getattr(provider_entity, 'base_url', '') or '').strip()
        if provider_base_url:
            job_url = provider_base_url
        api_keys = getattr(provider_entity, 'api_keys', None) or []
        if api_keys:
            token = str(api_keys[0]).strip()

    model_name = str(extra_args.get('model') or extra_args.get('display_name') or '').strip()
    if model_name and model_name != 'PaddleOCR-VL 1.6':
        model = model_name
    elif extra_args.get('model_id'):
        model = str(extra_args['model_id']).strip() or model

    return PaddleOcrConfig(token=token, job_url=job_url, model=model)


def is_paddleocr_vl_configured(provider_entity: Any | None = None) -> bool:
    return bool(resolve_paddleocr_config(provider_entity).token)


def parse_jsonl_markdown(jsonl_text: str) -> str:
    sections: list[str] = []
    for line in jsonl_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        result = payload.get('result') or {}
        for item in result.get('layoutParsingResults') or []:
            markdown = item.get('markdown') or {}
            text = str(markdown.get('text') or '').strip()
            if text:
                sections.append(text)
    return '\n\n'.join(sections).strip()


async def extract_text_with_paddleocr_vl(
    filename: str,
    content: bytes,
    *,
    token: str | None = None,
    model: str | None = None,
    job_url: str | None = None,
    provider_entity: Any | None = None,
    extra_args: dict[str, Any] | None = None,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
) -> str:
    config = resolve_paddleocr_config(provider_entity, extra_args)
    resolved_token = (token or config.token).strip()
    if not resolved_token:
        return ''
    resolved_model = (model or config.model).strip()
    resolved_job_url = (job_url or config.job_url).strip()

    headers = {'Authorization': f'bearer {resolved_token}'}
    form = aiohttp.FormData()
    form.add_field('model', resolved_model)
    form.add_field('optionalPayload', json.dumps(_DEFAULT_OPTIONAL_PAYLOAD))
    form.add_field(
        'file',
        content,
        filename=Path(filename).name,
        content_type='application/octet-stream',
    )

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(resolved_job_url, headers=headers, data=form) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(f'PaddleOCR job submit failed ({response.status}): {body}')
            payload = await response.json()
            job_id = str((payload.get('data') or {}).get('jobId') or '').strip()
            if not job_id:
                raise RuntimeError(f'PaddleOCR job submit returned no jobId: {payload}')

        jsonl_url = await _poll_job_result(
            session,
            job_url=resolved_job_url,
            job_id=job_id,
            headers=headers,
            poll_interval=poll_interval,
            max_wait=max_wait,
        )
        if not jsonl_url:
            return ''

        async with session.get(jsonl_url) as jsonl_response:
            jsonl_response.raise_for_status()
            jsonl_text = await jsonl_response.text()
    return parse_jsonl_markdown(jsonl_text)


async def _poll_job_result(
    session: aiohttp.ClientSession,
    *,
    job_url: str,
    job_id: str,
    headers: dict[str, str],
    poll_interval: float,
    max_wait: float,
) -> str:
    deadline = asyncio.get_running_loop().time() + max_wait
    while asyncio.get_running_loop().time() < deadline:
        async with session.get(f'{job_url}/{job_id}', headers=headers) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(f'PaddleOCR job poll failed ({response.status}): {body}')
            payload = await response.json()
            data = payload.get('data') or {}
            state = str(data.get('state') or '').strip()
            if state == 'done':
                result_url = (data.get('resultUrl') or {}).get('jsonUrl') or ''
                return str(result_url).strip()
            if state == 'failed':
                error_msg = str(data.get('errorMsg') or 'unknown error')
                raise RuntimeError(f'PaddleOCR job failed: {error_msg}')
        await asyncio.sleep(poll_interval)
    raise TimeoutError(f'PaddleOCR job {job_id} timed out after {max_wait}s')
