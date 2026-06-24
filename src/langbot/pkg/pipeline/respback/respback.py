from __future__ import annotations

import random
import asyncio
import base64
from collections import deque
import io
import json
import mimetypes
import re
from typing import Any

import aiohttp
from PIL import Image as PILImage

import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from langbot.pkg.utils import httpclient

from .. import stage, entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@stage.stage_class('SendResponseBackStage')
class SendResponseBackStage(stage.PipelineStage):
    """发送响应消息"""

    _EXTRA_REPLY_CHAINS_KEY = '_respback_extra_reply_chains'
    _COURSE_SALES_LINK_OPEN_QUESTION = '家长，您这边能打开吗？'
    _COURSE_SALES_CHILD_GRADE_QUESTION = '孩子现在几年级呀？'
    _COURSE_SALES_SIGNUP_LINK_QUEUED_KEY = '_course_sales_signup_link_queued'
    _COURSE_SALES_RESOURCE_LINK_QUEUED_KEY = '_course_sales_resource_link_queued'
    _OIAPI_EMOTION_URL = 'https://oiapi.net/api/Emotion'
    _MEME_PROVIDERS = [
        {
            'id': 'oiapi',
            'url': 'https://oiapi.net/api/Emotion',
            'params': {'msg': '{keyword}', '0': '{keyword}', 'limit': '{limit}'},
        },
        {
            'id': 'doutula',
            'url': 'https://www.doutula.com/api/search',
            'params': {'keyword': '{keyword}', 'page': '1', 'mime': '0'},
            'keywords': {'赞同': '点赞'},
        },
        {
            'id': 'apihz_sogou',
            'url': 'https://cn.apihz.cn/api/img/apihzbqbsougou.php',
            'params': {'id': '88888888', 'key': '88888888', 'words': '{keyword}', 'page': '1'},
            'keywords': {'赞同': '点赞'},
        },
        {
            'id': 'yuanfen',
            'url': 'https://api.yuanfen.top/doutu',
            'params': {'msg': '{keyword}'},
            'keywords': {'赞同': '点赞'},
        },
        {
            'id': 'xiaokang',
            'url': 'https://api.xiaokangsb.com/api/doutu',
            'params': {'key': '{keyword}'},
        },
        {
            'id': 'yunxiaomeng',
            'url': 'https://api.yunxiaomeng.top/api/doutu',
            'params': {'keyword': '{keyword}', 'page': '1'},
        },
        {
            'id': 'miaotian',
            'url': 'https://api.miaotian.top/api/doutu',
            'params': {'msg': '{keyword}'},
        },
        {
            'id': 'abaiyun',
            'url': 'https://api.abaiyun.cn/api/doutu',
            'params': {'word': '{keyword}'},
        },
        {
            'id': 'ysapi',
            'url': 'https://api.ysapi.top/doutu',
            'params': {'keyword': '{keyword}'},
        },
        {
            'id': 'qqsuu',
            'url': 'https://api.qqsuu.cn/api/dm/doutu',
            'params': {'msg': '{keyword}'},
        },
    ]
    _FEISHU_NATIVE_EMOJIS_BY_KEY = {
        'happy': ('[微笑]', '[愉快]', '[笑容满面]', '[大笑]', '[欢呼]', '[耶]'),
        'thanks': ('[双手合十]', '[感谢]', '[抱拳]'),
        'like': ('[赞]', '[+1]', '[我看行]', '[强]', '[完成]'),
        'success': ('[完成]', '[勾号]', '[100分]', '[鼓掌]'),
        'morning': ('[微笑]', '[咖啡]'),
        'noon': ('[咖啡]', '[愉快]'),
        'evening': ('[咖啡]', '[微笑]'),
        'night': ('[再见]', '[鼾睡]'),
        'ok': ('[OK]', '[了解]', '[完成]'),
        'received': ('[了解]', '[OK]', '[完成]'),
        'cheer': ('[加油]', '[奋斗]', '[冲！]', '[鼓掌]'),
        'welcome': ('[挥手]', '[微笑]', '[愉快]'),
        'question': ('[思考]', '[什么？]', '[啊？]'),
        'thinking': ('[思考]', '[思考中]', '[稍等]'),
        'sorry': ('[抱拳]', '[双手合十]'),
        'wait': ('[稍等]', '[在做了]', '[思考中]'),
        'checking': ('[在做了]', '[稍等]', '[思考]'),
        'reminder': ('[图钉]', '[闹钟]', '[点击]'),
        'deal': ('[鼓掌]', '[欢呼]', '[撒花]'),
        'signup': ('[完成]', '[鼓掌]', '[撒花]'),
        'payment': ('[完成]', '[勾号]', '[100分]'),
        'link': ('[点击]', '[OK]', '[了解]'),
        'resource': ('[图钉]', '[点击]', '[了解]'),
        'class_time': ('[日程]', '[闹钟]', '[了解]'),
        'replay': ('[电视]', '[了解]', '[OK]'),
        'gift': ('[礼物]', '[送你小红花]', '[撒花]'),
        'trial': ('[挥手]', '[微笑]', '[愉快]'),
        'discount': ('[礼物]', '[火]', '[点击]'),
        'grade': ('[了解]', '[思考]', '[OK]'),
        'parent': ('[微笑]', '[了解]', '[双手合十]'),
        'child': ('[送你小红花]', '[加油]', '[比心]'),
        'homework': ('[奋斗]', '[加油]', '[100分]'),
        'reading': ('[100分]', '[送你小红花]', '[加油]'),
        'phonics': ('[音乐]', '[100分]', '[加油]'),
        'followup': ('[图钉]', '[了解]', '[微笑]'),
        'congrats': ('[鼓掌]', '[欢呼]', '[撒花]'),
        'polite': ('[双手合十]', '[感谢]', '[微笑]'),
        'calm': ('[摸头]', '[抱拳]', '[稍等]'),
        'service': ('[在做了]', '[了解]', '[OK]'),
        'handoff_ready': ('[举手]', '[稍等]', '[了解]'),
    }
    _FEISHU_NATIVE_KEY_ALIASES = {
        '开心': 'happy',
        '高兴': 'happy',
        '愉快': 'happy',
        '赞同': 'like',
        '点赞': 'like',
        '认可': 'like',
        '完成': 'success',
        '成功': 'success',
        '感谢': 'thanks',
        '谢谢': 'thanks',
        '疑惑': 'question',
        '疑问': 'question',
        '思考': 'thinking',
        '稍等': 'wait',
        '核实': 'checking',
        '收到': 'received',
        '好的': 'ok',
        '加油': 'cheer',
        '欢迎': 'welcome',
        '报名': 'signup',
        '支付': 'payment',
        '链接': 'link',
        '资料': 'resource',
        '上课时间': 'class_time',
        '回放': 'replay',
        '礼品': 'gift',
        '体验课': 'trial',
        '优惠': 'discount',
        '年级': 'grade',
        '家长': 'parent',
        '孩子': 'child',
        '练习': 'homework',
        '阅读': 'reading',
        '自然拼读': 'phonics',
        '跟进': 'followup',
        '恭喜': 'congrats',
        '礼貌': 'polite',
        '安抚': 'calm',
        '服务': 'service',
        '协助': 'handoff_ready',
    }
    _FEISHU_NATIVE_EMOJI_VALUES = frozenset(
        emoji for options in _FEISHU_NATIVE_EMOJIS_BY_KEY.values() for emoji in options
    )

    _MEME_TRIGGER_RE = re.compile(r'\{([a-z][a-z0-9_-]{1,32})\}', re.IGNORECASE)
    _TRAILING_UNICODE_EMOJI_RE = re.compile(r'[\s\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]+$')
    _DEFAULT_MEME_CODES = set(_FEISHU_NATIVE_EMOJIS_BY_KEY)
    _BUILTIN_MEME_FILE_PREFIX = 'builtin:sales-meme:'

    def __init__(self, ap):
        super().__init__(ap)
        self._meme_session_states: dict[str, dict[str, int]] = {}
    _COURSE_SALES_CHILD_GRADE_RE = re.compile(r'(幼儿园|小班|中班|大班|[一二三四五六七八九1-9]年级|初[一二三]|高[一二三])')
    _COURSE_SALES_CHINESE_TERM_REPLACEMENTS = (
        (re.compile(r'(?<![A-Za-z])English\s+Phonics(?![A-Za-z])', re.IGNORECASE), '英语自然拼读'),
        (re.compile(r'(?<![A-Za-z])Phonics(?![A-Za-z])', re.IGNORECASE), '自然拼读'),
        (re.compile(r'(?<![A-Za-z])VIP(?=\s*(权益|服务))', re.IGNORECASE), '会员'),
        (re.compile(r'(?<![A-Za-z])APP(?![A-Za-z])', re.IGNORECASE), '应用'),
        (re.compile(r'(?<![A-Za-z])AI(?=\s*(强化营|课|课程|工具|伴学|学|服务))', re.IGNORECASE), '智能'),
    )
    _COURSE_SALES_UNRENDERED_PLACEHOLDER_RE = re.compile(r'\{\{\s*([^{}\r\n]{1,40}?)\s*\}\}')

    def _current_intent_data(self, query: pipeline_query.Query) -> dict[str, Any]:
        intent_data = query.variables.get('sales_intent') or query.variables.get('workflow_intent') or {}
        if isinstance(intent_data, dict):
            return intent_data
        if isinstance(intent_data, str):
            return {'intent': intent_data, 'confidence': 1.0}
        return {}

    def _current_intent(self, query: pipeline_query.Query) -> tuple[str, float]:
        intent_data = self._current_intent_data(query)
        if isinstance(intent_data, str):
            return intent_data, 1.0
        if isinstance(intent_data, dict):
            return str(intent_data.get('intent') or ''), float(intent_data.get('confidence') or 0)
        return '', 0

    def _intent_threshold(self, workflow: dict[str, Any]) -> float:
        for node in workflow.get('nodes', []):
            if not isinstance(node, dict) or node.get('type') != 'intent':
                continue
            node_config = node.get('config') if isinstance(node.get('config'), dict) else {}
            try:
                return float(node_config.get('confidence_threshold') or 0)
            except (TypeError, ValueError):
                return 0
        return 0

    def _is_task_assistant_workflow(self, workflow: dict[str, Any] | None) -> bool:
        if not isinstance(workflow, dict):
            return False
        metadata = workflow.get('metadata') if isinstance(workflow.get('metadata'), dict) else {}
        return metadata.get('scenario') == 'task_assistant_ant_af'

    def _is_course_sales_workflow(self, workflow: dict[str, Any] | None) -> bool:
        if not isinstance(workflow, dict):
            return False
        metadata = workflow.get('metadata') if isinstance(workflow.get('metadata'), dict) else {}
        return metadata.get('scenario') == 'course_sales_yuanfudao_phonics' or workflow.get('scenario') == 'course_sales_yuanfudao_phonics'

    def _node_step_id(self, node: dict[str, Any], node_config: dict[str, Any]) -> str:
        if node_config.get('step_id'):
            return str(node_config['step_id'])
        node_id = str(node.get('id') or '')
        if node_id.startswith('image_'):
            return node_id.removeprefix('image_')
        return ''

    def _as_string_set(self, value: Any) -> set[str]:
        if isinstance(value, str):
            return {value} if value else set()
        if isinstance(value, (list, tuple, set)):
            return {str(item) for item in value if str(item)}
        return set()

    def _active_workflow(self, query: pipeline_query.Query) -> dict[str, Any] | None:
        pipeline_config = query.pipeline_config if isinstance(query.pipeline_config, dict) else {}
        task_assistant_service = getattr(self.ap, 'task_assistant_service', None)
        active_workflow_from_config = getattr(task_assistant_service, 'active_workflow_from_config', None)
        if callable(active_workflow_from_config):
            try:
                workflow = active_workflow_from_config(pipeline_config)
            except Exception as exc:
                logger = getattr(self.ap, 'logger', None)
                if logger is not None:
                    logger.warning('Failed to resolve active workflow from pipeline config: %s', exc)
            else:
                if isinstance(workflow, dict) and workflow:
                    return workflow

        workflow = pipeline_config.get('workflow')
        return workflow if isinstance(workflow, dict) else None

    def _workflow_special_cases(self, query: pipeline_query.Query) -> list[dict[str, Any]]:
        workflow = self._active_workflow(query)
        if not isinstance(workflow, dict):
            return []
        cases = workflow.get('special_cases')
        if not isinstance(cases, list):
            cases = workflow.get('variables', {}).get('special_cases') if isinstance(workflow.get('variables'), dict) else []
        if not isinstance(cases, list):
            return []

        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(cases):
            if not isinstance(item, dict) or item.get('enabled') is False:
                continue
            condition = str(item.get('condition') or '').strip()
            reply = str(item.get('reply') or '').strip()
            if not condition or not reply:
                continue
            case = dict(item)
            case['id'] = str(case.get('id') or f'special-case-{index + 1}')
            case['condition'] = condition
            case['reply'] = reply
            normalized.append(case)
        return normalized

    def _message_chain_text(self, message_chain: platform_message.MessageChain | None) -> str:
        if not message_chain:
            return ''
        return ''.join(component.text for component in message_chain if isinstance(component, platform_message.Plain)).strip()

    def _query_user_text(self, query: pipeline_query.Query) -> str:
        text = self._message_chain_text(getattr(query, 'message_chain', None))
        if text:
            return text
        user_message = getattr(query, 'user_message', None)
        content = getattr(user_message, 'content', None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return ''.join(str(getattr(item, 'text', '') or '') for item in content).strip()
        return ''

    def _provider_content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                text = getattr(item, 'text', None)
                if text is None and isinstance(item, dict):
                    text = item.get('text')
                if text:
                    parts.append(str(text))
            return '\n'.join(parts).strip()
        return str(content or '').strip()

    def _provider_message_text(self, message: Any) -> str:
        if isinstance(message, tuple) and message:
            message = message[0]
        return self._provider_content_to_text(getattr(message, 'content', message))

    def _special_case_model_uuid(self, query: pipeline_query.Query) -> str:
        uuid = str(getattr(query, 'use_llm_model_uuid', '') or '').strip()
        if uuid:
            return uuid
        workflow = self._active_workflow(query) or {}
        model_uuid = str(workflow.get('model_uuid') or '').strip() if isinstance(workflow, dict) else ''
        if model_uuid:
            return model_uuid
        metadata = workflow.get('metadata') if isinstance(workflow.get('metadata'), dict) else {}
        return str(metadata.get('model_uuid') or '').strip()

    async def _invoke_special_case_llm(self, query: pipeline_query.Query, prompt: str) -> str:
        model_uuid = self._special_case_model_uuid(query)
        model_mgr = getattr(self.ap, 'model_mgr', None)
        if not model_uuid or model_mgr is None:
            return ''
        try:
            model = await model_mgr.get_model_by_uuid(model_uuid)
            result = await model.provider.invoke_llm(
                query,
                model,
                [provider_message.Message(role='user', content=prompt)],
                funcs=[],
                extra_args={},
                remove_think=True,
            )
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Failed to evaluate workflow special case: %s', exc)
            return ''
        return self._provider_message_text(result)

    def _semantic_match_prompt(self, user_text: str, cases: list[dict[str, Any]]) -> str:
        payload = [{'id': case['id'], 'condition': case['condition']} for case in cases]
        return (
            '你是语义路由器，只判断用户这句话是否符合某一条特殊情况的语义条件。\n'
            '不要按关键词机械匹配，要按意思判断；同义、口语化、换一种说法也可以命中。\n'
            '如果没有命中，返回 {"matched_id":""}。\n'
            '只输出 JSON，不要解释。\n\n'
            f'用户消息：{user_text}\n\n'
            f'特殊情况：{json.dumps(payload, ensure_ascii=False)}'
        )

    def _parse_special_case_match(self, text: str, cases: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not text:
            return None
        matched_id = ''
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                matched_id = str(parsed.get('matched_id') or parsed.get('id') or '').strip()
        except (TypeError, json.JSONDecodeError):
            for case in cases:
                if case['id'] in text:
                    matched_id = case['id']
                    break
        if not matched_id:
            return None
        return next((case for case in cases if case['id'] == matched_id), None)

    def _special_case_keywords(self, case: dict[str, Any]) -> set[str]:
        configured = case.get('keywords')
        if isinstance(configured, str):
            return {item.strip() for item in re.split(r'[,，、/\\s]+', configured) if item.strip()}
        if isinstance(configured, (list, tuple, set)):
            return {str(item).strip() for item in configured if str(item).strip()}

        source = ' '.join(str(case.get(key) or '') for key in ('id', 'condition', 'reply'))
        candidates = {
            '二维码',
            '听力',
            '答案',
            '音频',
            '扫码',
            '扫书',
            '资源',
        }
        return {keyword for keyword in candidates if keyword in source}

    def _should_check_special_cases(self, user_text: str, cases: list[dict[str, Any]]) -> bool:
        for case in cases:
            keywords = self._special_case_keywords(case)
            if not keywords:
                return True
            if any(keyword in user_text for keyword in keywords):
                return True
        return False

    async def _match_special_case(self, query: pipeline_query.Query) -> dict[str, Any] | None:
        cases = self._workflow_special_cases(query)
        user_text = self._query_user_text(query)
        if not cases or not user_text:
            return None
        if not self._should_check_special_cases(user_text, cases):
            return None
        result_text = await self._invoke_special_case_llm(query, self._semantic_match_prompt(user_text, cases))
        return self._parse_special_case_match(result_text, cases)

    def _special_case_rewrite_prompt(self, user_text: str, case: dict[str, Any]) -> str:
        return (
            '你是正在和客户聊天的数字员工。请按“回复意思”自然表达一条可直接发送的短回复。\n'
            '要求：意思必须一致；不要编造新政策；不要输出标题；每次表达可以略有不同；语气像真人客服。\n\n'
            f'用户消息：{user_text}\n'
            f'回复意思：{case["reply"]}'
        )

    async def _special_case_reply_text(self, query: pipeline_query.Query, case: dict[str, Any]) -> str:
        if not bool(case.get('ai_rewrite')):
            return case['reply']
        rewritten = await self._invoke_special_case_llm(
            query,
            self._special_case_rewrite_prompt(self._query_user_text(query), case),
        )
        return rewritten or case['reply']

    async def _apply_special_case_response(self, query: pipeline_query.Query) -> bool:
        case = await self._match_special_case(query)
        if not case:
            return False
        components: list[platform_message.MessageComponent] = [
            platform_message.Plain(text=await self._special_case_reply_text(query, case))
        ]
        image_url = str(case.get('image_url') or '').strip()
        file_key = str(case.get('file_key') or '').strip()
        if image_url or file_key:
            components.append(await self._image_component(file_key, image_url))
        query.resp_message_chain = [platform_message.MessageChain(components)]
        query.variables['workflow_special_case'] = {
            'id': case.get('id'),
            'condition': case.get('condition'),
            'ai_rewrite': bool(case.get('ai_rewrite')),
        }
        return True

    def _handoff_intent_data(self, query: pipeline_query.Query) -> dict[str, Any]:
        intent_data = self._current_intent_data(query)
        intent = str(intent_data.get('intent') or '').strip()
        if intent == 'handoff' or intent_data.get('requires_handoff') is True:
            return intent_data
        return {}

    def _handoff_reason(self, intent_data: dict[str, Any]) -> str:
        return str(intent_data.get('handoff_reason') or intent_data.get('reason') or 'handoff')

    def _handoff_notice(self, intent_data: dict[str, Any]) -> str:
        handoff_config = intent_data.get('handoff_config')
        if isinstance(handoff_config, dict):
            notice = str(handoff_config.get('notify_message') or '').strip()
            if notice:
                return notice
        return str(intent_data.get('notify_message') or intent_data.get('notice') or '').strip()

    async def _apply_handoff_response(self, query: pipeline_query.Query) -> bool:
        intent_data = self._handoff_intent_data(query)
        if not intent_data:
            return False
        sales_service = getattr(self.ap, 'sales_service', None)
        open_handoff = getattr(sales_service, 'open_handoff_from_query', None)
        opened = False
        if callable(open_handoff):
            try:
                await open_handoff(query, self._handoff_reason(intent_data), self._query_user_text(query))
                opened = True
                query.variables['sales_handoff_opened'] = True
            except Exception as exc:
                logger = getattr(self.ap, 'logger', None)
                if logger is not None:
                    logger.warning('Failed to open sales handoff from response stage: %s', exc)
        notice = self._handoff_notice(intent_data)
        if notice:
            query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text=notice)])]
        return opened or bool(notice)

    @staticmethod
    def _tight_sticker_png(image_bytes: bytes) -> bytes:
        try:
            image = PILImage.open(io.BytesIO(image_bytes)).convert('RGBA')
        except Exception:
            return image_bytes

        width, height = image.size
        if width <= 0 or height <= 0:
            return image_bytes

        pixels = image.load()
        visited = bytearray(width * height)
        queue: deque[tuple[int, int]] = deque()

        def index(x: int, y: int) -> int:
            return y * width + x

        def is_outer_background(x: int, y: int) -> bool:
            r, g, b, alpha = pixels[x, y]
            return alpha <= 10 or (r >= 245 and g >= 245 and b >= 245)

        def push_if_background(x: int, y: int) -> None:
            pos = index(x, y)
            if visited[pos] or not is_outer_background(x, y):
                return
            visited[pos] = 1
            queue.append((x, y))

        for x in range(width):
            push_if_background(x, 0)
            push_if_background(x, height - 1)
        for y in range(height):
            push_if_background(0, y)
            push_if_background(width - 1, y)

        while queue:
            x, y = queue.popleft()
            r, g, b, _ = pixels[x, y]
            pixels[x, y] = (r, g, b, 0)
            if x > 0:
                push_if_background(x - 1, y)
            if x + 1 < width:
                push_if_background(x + 1, y)
            if y > 0:
                push_if_background(x, y - 1)
            if y + 1 < height:
                push_if_background(x, y + 1)

        bbox = image.getbbox()
        if not bbox:
            return image_bytes

        cropped = image.crop(bbox)
        padding = max(4, min(16, round(max(cropped.size) * 0.035)))
        sticker = PILImage.new(
            'RGBA',
            (cropped.width + padding * 2, cropped.height + padding * 2),
            (255, 255, 255, 0),
        )
        sticker.alpha_composite(cropped, (padding, padding))

        max_side = 420
        longest_side = max(sticker.size)
        if longest_side > max_side:
            scale = max_side / longest_side
            sticker = sticker.resize(
                (max(1, round(sticker.width * scale)), max(1, round(sticker.height * scale))),
                PILImage.Resampling.LANCZOS,
            )

        output = io.BytesIO()
        sticker.save(output, format='PNG', optimize=True)
        return output.getvalue()

    async def _download_image_bytes(self, image_url: str) -> bytes:
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        return b''
                    content = await response.read()
                    return content if len(content) <= 5 * 1024 * 1024 else b''
        except Exception:
            return b''

    @staticmethod
    def _is_image_bytes(image_bytes: bytes) -> bool:
        try:
            PILImage.open(io.BytesIO(image_bytes)).verify()
            return True
        except Exception:
            return False

    async def _image_component(self, file_key: str, image_url: str, *, sticker: bool = False) -> platform_message.Image:
        if image_url:
            if sticker:
                image_content = await self._download_image_bytes(image_url)
                if image_content and self._is_image_bytes(image_content):
                    image_content = self._tight_sticker_png(image_content)
                    image_base64 = base64.b64encode(image_content).decode('utf-8')
                    return platform_message.Image(base64=f'data:image/png;base64,{image_base64}')
            return platform_message.Image(url=image_url)

        storage_mgr = getattr(self.ap, 'storage_mgr', None)
        storage_provider = getattr(storage_mgr, 'storage_provider', None) if storage_mgr is not None else None
        if storage_provider is not None:
            try:
                file_content = await storage_provider.load(file_key)
                if sticker:
                    file_content = self._tight_sticker_png(file_content)
                mime_type = 'image/png' if sticker else mimetypes.guess_type(file_key)[0] or 'image/png'
                image_base64 = base64.b64encode(file_content).decode('utf-8')
                return platform_message.Image(base64=f'data:{mime_type};base64,{image_base64}')
            except Exception as exc:
                logger = getattr(self.ap, 'logger', None)
                if logger is not None:
                    logger.warning('Failed to load workflow image %s from storage: %s', file_key, exc)

        return platform_message.Image(path=file_key)

    def _course_sales_signup_link_sent(self, query: pipeline_query.Query) -> bool:
        if query.variables.get(self._COURSE_SALES_SIGNUP_LINK_QUEUED_KEY) is True:
            return True
        if not query.resp_message_chain:
            return False
        return any(self._contains_course_sales_link(self._plain_text_from_chain(chain)) for chain in query.resp_message_chain)

    async def _matched_image_components(
        self,
        query: pipeline_query.Query,
        *,
        link_bound_only: bool | None = None,
    ) -> list[platform_message.MessageComponent]:
        workflow = self._active_workflow(query)
        if not isinstance(workflow, dict):
            return []

        intent_data = self._current_intent_data(query)
        intent, confidence = self._current_intent(query)
        if not intent or confidence < self._intent_threshold(workflow):
            return []

        components: list[platform_message.MessageComponent] = []
        seen_assets: set[tuple[str, str]] = set()
        is_task_assistant_workflow = self._is_task_assistant_workflow(workflow)
        selected_step_ids = self._as_string_set(intent_data.get('step_ids') or intent_data.get('image_step_ids'))
        max_images = 1 if is_task_assistant_workflow else None
        try:
            if intent_data.get('max_images') is not None:
                max_images = max(0, int(intent_data['max_images']))
        except (TypeError, ValueError):
            max_images = 1 if is_task_assistant_workflow else None
        if max_images == 0:
            return []

        for node in workflow.get('nodes', []):
            if not isinstance(node, dict) or node.get('type') != 'image':
                continue
            node_config = node.get('config') if isinstance(node.get('config'), dict) else {}
            if node_config.get('enabled') is False:
                continue

            trigger_intents = node_config.get('trigger_intents') or node_config.get('intents') or []
            if isinstance(trigger_intents, str):
                trigger_intents = [item.strip() for item in trigger_intents.split(',') if item.strip()]
            if intent not in trigger_intents and '*' not in trigger_intents and 'all' not in trigger_intents:
                continue
            if is_task_assistant_workflow and selected_step_ids:
                node_step_id = self._node_step_id(node, node_config)
                if node_step_id not in selected_step_ids:
                    continue
            requires_signup_link = node_config.get('requires_course_sales_signup_link') is True
            if link_bound_only is not None and requires_signup_link is not link_bound_only:
                continue
            if requires_signup_link and not self._course_sales_signup_link_sent(query):
                continue

            file_key = str(node_config.get('file_key') or '').strip()
            image_url = str(node_config.get('image_url') or '').strip()
            if not file_key and not image_url:
                continue

            asset_key = (file_key, image_url)
            if asset_key in seen_assets:
                continue
            seen_assets.add(asset_key)

            caption = str(node_config.get('caption') or '').strip()
            if caption and not is_task_assistant_workflow and node_config.get('append_caption') is not False:
                components.append(platform_message.Plain(text=f'\n{caption}'))
            elif requires_signup_link and self._is_course_sales_workflow(workflow) and not is_task_assistant_workflow:
                current_text = self._plain_text_from_chain(query.resp_message_chain[-1])
                if not any(marker in current_text for marker in ('完课好礼', '礼品说明', '赠品', '礼品')):
                    components.append(platform_message.Plain(text='报课后按活动规则有完课礼，礼品说明我发您看一下。'))
            components.append(await self._image_component(file_key, image_url))

            if max_images is not None and sum(isinstance(component, platform_message.Image) for component in components) >= max_images:
                break

        return components

    async def _append_workflow_images(self, query: pipeline_query.Query, *, link_bound_only: bool | None = None) -> None:
        if not query.resp_message_chain:
            return
        for component in await self._matched_image_components(query, link_bound_only=link_bound_only):
            if link_bound_only is True and query.variables.get(self._COURSE_SALES_SIGNUP_LINK_QUEUED_KEY) is True:
                self._queue_extra_reply_chain(query, platform_message.MessageChain([component]))
            else:
                query.resp_message_chain[-1].append(component)

    def _plain_text_from_chain(self, message_chain: platform_message.MessageChain) -> str:
        return ''.join(component.text for component in message_chain if isinstance(component, platform_message.Plain))

    def _strip_thinking_text(self, text: str) -> str:
        return re.sub(r'<think>.*?(?:</think>|$)', '', text or '', flags=re.DOTALL).strip()

    def _strip_thinking_from_response(self, query: pipeline_query.Query) -> None:
        for message_chain in query.resp_message_chain or []:
            for component in message_chain:
                if isinstance(component, platform_message.Plain):
                    component.text = self._strip_thinking_text(component.text)
        for message in query.resp_messages or []:
            content = getattr(message, 'content', None)
            if isinstance(content, str):
                message.content = self._strip_thinking_text(content)

    def _multi_reply_config(self, query: pipeline_query.Query) -> tuple[bool, int]:
        pipeline_config = query.pipeline_config if isinstance(query.pipeline_config, dict) else {}
        output_config = pipeline_config.get('output') if isinstance(pipeline_config.get('output'), dict) else {}
        misc_config = output_config.get('misc') if isinstance(output_config.get('misc'), dict) else {}
        config = misc_config.get('multi-reply') if isinstance(misc_config.get('multi-reply'), dict) else {}
        try:
            threshold = int(config.get('threshold') or 200)
        except (TypeError, ValueError):
            threshold = 200
        return bool(config.get('enabled')), max(1, threshold)

    def _strip_course_sales_final_periods(self, text: str) -> str:
        return re.sub(r'[。．.]+$', '', text.rstrip())

    def _split_natural_sentences(self, text: str) -> list[str]:
        chunks: list[str] = []
        for raw_line in text.strip().replace('\r\n', '\n').split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            for marker in (
                self._COURSE_SALES_LINK_OPEN_QUESTION,
                self._COURSE_SALES_CHILD_GRADE_QUESTION,
                '方便发我一张截图吗？',
            ):
                if marker in line and not line.startswith(marker):
                    line = line.replace(marker, f'\n{marker}')
            if '\n' in line:
                chunks.extend(self._split_natural_sentences(line))
                continue
            parts = re.findall(r'.+?(?:[。！？!?；;]+|$)', line)
            chunks.extend(part.strip() for part in parts if part.strip())
        return chunks

    def _split_course_sales_reply_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        url_pattern = re.compile(r'https?://[^\s<>"\]\)】》>，。！？、；：]*')
        for raw_line in text.strip().replace('\r\n', '\n').split('\n'):
            line = raw_line.strip()
            if not line:
                continue

            cursor = 0
            for match in url_pattern.finditer(line):
                before = line[cursor:match.start()].strip().rstrip('：:，,、；; ')
                chunks.extend(self._split_natural_sentences(before))
                chunks.append(match.group(0).strip())
                cursor = match.end()

            after = re.sub(r'^[，,、；;：:\s]+', '', line[cursor:].strip())
            chunks.extend(self._split_natural_sentences(after))

        normalized: list[str] = []
        for chunk in chunks:
            if chunk.startswith(('http://', 'https://')):
                normalized.append(chunk)
            else:
                stripped = self._strip_course_sales_final_periods(chunk)
                if stripped:
                    normalized.append(stripped)
        return normalized

    def _course_sales_reply_chains(
        self,
        message_chain: platform_message.MessageChain,
    ) -> list[platform_message.MessageChain]:
        chains: list[platform_message.MessageChain] = []
        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                for chunk in self._split_course_sales_reply_text(component.text):
                    chains.append(platform_message.MessageChain([platform_message.Plain(text=chunk)]))
                continue
            if isinstance(component, platform_message.Image):
                chains.append(platform_message.MessageChain([component]))
                continue
            return [message_chain]
        return chains or [message_chain]

    def _split_plain_text(self, text: str, threshold: int, *, natural_sentences: bool = False) -> list[str]:
        stripped = text.strip()
        if not stripped or len(stripped) <= threshold:
            if natural_sentences:
                if '\n' in stripped.replace('\r\n', '\n'):
                    lines = [line.strip() for line in stripped.replace('\r\n', '\n').split('\n') if line.strip()]
                    if len(lines) > 1:
                        return [self._strip_course_sales_final_periods(line) for line in lines]
                chunks = self._split_natural_sentences(stripped)
                if len(chunks) > 1:
                    return [self._strip_course_sales_final_periods(chunk) for chunk in chunks]
            return [text]

        chunks: list[str] = []
        current = ''
        raw_parts = self._split_natural_sentences(stripped) if natural_sentences else stripped.replace('\r\n', '\n').split('\n')
        for raw_part in raw_parts:
            part = self._strip_course_sales_final_periods(raw_part.strip()) if natural_sentences else raw_part.strip()
            if not part:
                continue
            if current and len(current) + len(part) + 1 > threshold:
                chunks.append(current)
                current = part
            else:
                current = f'{current}\n{part}' if current else part
        if current:
            chunks.append(current)
        return chunks or [text]

    def _multi_reply_chains(self, query: pipeline_query.Query) -> list[platform_message.MessageChain]:
        if not query.resp_message_chain:
            return []

        enabled, threshold = self._multi_reply_config(query)
        workflow = self._active_workflow(query)
        is_course_sales = self._is_course_sales_workflow(workflow)
        message_chain = query.resp_message_chain[-1]

        components = list(message_chain)
        if not components:
            return [message_chain]

        text = self._plain_text_from_chain(message_chain)
        if is_course_sales:
            if any(not isinstance(component, (platform_message.Plain, platform_message.Image)) for component in components):
                return [message_chain]
            chains = self._course_sales_reply_chains(message_chain)
            if len(chains) <= 1 and text:
                return [platform_message.MessageChain([platform_message.Plain(text=self._strip_course_sales_final_periods(text))])]
            return chains

        if any(not isinstance(component, platform_message.Plain) for component in components):
            return [message_chain]

        if not enabled:
            return [message_chain]

        if 'http://' in text or 'https://' in text or len(text.strip()) <= threshold:
            return [message_chain]

        chunks = self._split_plain_text(text, threshold)
        if len(chunks) <= 1:
            return [message_chain]
        return [platform_message.MessageChain([platform_message.Plain(text=chunk)]) for chunk in chunks]

    def _normalize_course_sales_text(self, query: pipeline_query.Query) -> None:
        workflow = self._active_workflow(query)
        if not self._is_course_sales_workflow(workflow) or not query.resp_message_chain:
            return
        for component in query.resp_message_chain[-1]:
            if isinstance(component, platform_message.Plain):
                component.text = self._normalize_course_sales_plain_text(component.text)
        for message in query.resp_messages or []:
            content = getattr(message, 'content', None)
            if isinstance(content, str):
                message.content = self._normalize_course_sales_plain_text(content)

    def _normalize_course_sales_plain_text(self, text: str) -> str:
        normalized = text or ''
        for pattern, replacement in self._COURSE_SALES_CHINESE_TERM_REPLACEMENTS:
            normalized = pattern.sub(replacement, normalized)
        normalized = self._COURSE_SALES_UNRENDERED_PLACEHOLDER_RE.sub(
            lambda match: match.group(1).strip(),
            normalized,
        )
        return self._strip_course_sales_final_periods(normalized)

    def _course_sales_link_question_needed(self, query: pipeline_query.Query, text: str) -> bool:
        if not text:
            return False
        if '能打开吗' in text or '能否打开' in text or '可以打开吗' in text:
            return False
        if '猿辅导英语自然拼读9元体验课点这里' in text or 'yuanfudao.com/primary/templates/package' in text:
            return False
        if 'http://' in text or 'https://' in text or '#小程序://' in text:
            return True
        negated_link_markers = (
            '不发链接',
            '不用发链接',
            '不要链接',
            '不需要链接',
            '不给您发链接',
            '先不发链接',
            '没有链接',
        )
        if any(marker in text for marker in negated_link_markers):
            return False

        intent_data = self._current_intent_data(query)
        intent = str(intent_data.get('intent') or '').strip()
        if intent == 'resource_help':
            return False
        if intent in {'purchase', 'radar_clicked', 'link_error'} or intent_data.get('include_link') is True or intent_data.get('link_url'):
            return any(marker in text for marker in ('链接', '入口', '卡片', '扫码记录', '小程序'))
        if intent:
            return False
        return any(marker in text for marker in ('链接', '入口', '卡片', '资源', '扫码记录', '小程序'))

    def _course_sales_user_confirmed_open(self, query: pipeline_query.Query) -> bool:
        intent_data = self._current_intent_data(query)
        if intent_data.get('intent') == 'resource_confirmed':
            return True
        text = str(query.variables.get('user_message_text') or '').strip().lower()
        if not text:
            return False
        if any(marker in text for marker in ('打不开', '不能打开', '无法打开', '没打开', '没有打开', '点不开')):
            return False
        return any(
            marker in text
            for marker in (
                '能打开',
                '可以打开',
                '能点开',
                '可以点开',
                '打开了',
                '点开了',
                '看到了',
                '可以的',
                '可以',
                '好的',
                '好哒',
                '没问题',
            )
        )

    def _course_sales_user_reported_open_failure(self, query: pipeline_query.Query) -> bool:
        text = str(query.variables.get('user_message_text') or '').strip().lower()
        if not text:
            text = self._plain_text_from_chain(query.message_chain) if isinstance(query.message_chain, platform_message.MessageChain) else ''
        return any(marker in text for marker in ('打不开', '不能打开', '无法打开', '没打开', '没有打开', '点不开', '进不去'))

    def _course_sales_screenshot_question_needed(self, text: str) -> bool:
        if not text:
            return False
        if '截图' in text and any(marker in text for marker in ('吗', '发我', '发一下', '发张', '发一张')):
            return False
        return any(marker in text for marker in ('报错', '打不开', '进不去', '无法打开', '不能打开', '页面异常', '白屏'))

    def _course_sales_grade_question_needed(self, text: str) -> bool:
        if not text:
            return False
        if any(marker in text for marker in ('几年级', '年级呀', '年级呢', '孩子多大')):
            return False
        return any(
            marker in text
            for marker in (
                '自然拼读',
                '课程',
                '课表',
                '上课',
                '课后',
                '老师跟进',
                '价格',
                '费用',
                '学费',
                '9元',
            )
        )

    def _course_sales_open_question(self, query: pipeline_query.Query, text: str) -> str:
        if self._course_sales_link_question_needed(query, text):
            return self._COURSE_SALES_LINK_OPEN_QUESTION
        if self._course_sales_screenshot_question_needed(text):
            return '方便发我一张截图吗？'
        if self._course_sales_grade_question_needed(text):
            return self._COURSE_SALES_CHILD_GRADE_QUESTION
        return ''

    def _course_sales_provider_content_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ''
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    parts.append(str(item.get('text') or ''))
                continue
            if getattr(item, 'type', None) == 'text':
                parts.append(str(getattr(item, 'text', '') or ''))
        return ''.join(parts)

    def _course_sales_provider_user_text(self, message: Any) -> str:
        role = getattr(message, 'role', '')
        role_value = str(getattr(role, 'value', role)).lower()
        if role_value != 'user':
            return ''
        return self._course_sales_provider_content_text(getattr(message, 'content', ''))

    def _course_sales_child_grade_known(self, query: pipeline_query.Query) -> bool:
        user_texts = [
            str(query.variables.get('user_message_text') or ''),
            self._plain_text_from_chain(query.message_chain) if isinstance(query.message_chain, platform_message.MessageChain) else '',
            self._course_sales_provider_user_text(query.user_message),
        ]
        user_texts.extend(self._course_sales_provider_user_text(message) for message in query.messages)
        return any(self._COURSE_SALES_CHILD_GRADE_RE.search(text or '') for text in user_texts)

    def _queue_extra_reply_chain(self, query: pipeline_query.Query, text: str | platform_message.MessageChain) -> None:
        if isinstance(text, platform_message.MessageChain):
            chain = text
        else:
            chain = platform_message.MessageChain([platform_message.Plain(text=text)])
        extra_chains = query.variables.get(self._EXTRA_REPLY_CHAINS_KEY)
        if not isinstance(extra_chains, list):
            extra_chains = []
            query.variables[self._EXTRA_REPLY_CHAINS_KEY] = extra_chains
        extra_chains.append(chain)

    def _pop_extra_reply_chains(self, query: pipeline_query.Query) -> list[platform_message.MessageChain]:
        extra_chains = query.variables.pop(self._EXTRA_REPLY_CHAINS_KEY, [])
        if not isinstance(extra_chains, list):
            return []
        return [chain for chain in extra_chains if isinstance(chain, platform_message.MessageChain)]

    def _pop_outgoing_extra_reply_chains(self, query: pipeline_query.Query) -> list[platform_message.MessageChain]:
        extra_chains = self._pop_extra_reply_chains(query)
        workflow = self._active_workflow(query)
        if not self._is_course_sales_workflow(workflow):
            return extra_chains
        outgoing_chains: list[platform_message.MessageChain] = []
        for chain in extra_chains:
            outgoing_chains.extend(self._course_sales_reply_chains(chain))
        return outgoing_chains

    def _append_course_sales_open_question(self, query: pipeline_query.Query) -> None:
        workflow = self._active_workflow(query)
        if not self._is_course_sales_workflow(workflow) or not query.resp_message_chain:
            return
        intent_data = self._current_intent_data(query)
        if str(intent_data.get('intent') or '') in {
            'explicit_rejection',
            'objection',
            'stop',
            'handoff',
            'smalltalk',
            'clarification',
        }:
            return
        if str(intent_data.get('intent') or '') == 'resource_help' and self._course_sales_user_reported_open_failure(query):
            return
        current_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        if self._course_sales_user_confirmed_open(query):
            return
        question = self._course_sales_open_question(query, current_text)
        if not question:
            return
        if question == self._COURSE_SALES_CHILD_GRADE_QUESTION and self._course_sales_child_grade_known(query):
            return
        self._queue_extra_reply_chain(query, question)

    def _remove_course_sales_open_question_after_resource_failure(self, query: pipeline_query.Query) -> None:
        intent_data = self._current_intent_data(query)
        if str(intent_data.get('intent') or '') != 'resource_help':
            return
        if not self._course_sales_user_reported_open_failure(query):
            return
        for component in query.resp_message_chain[-1]:
            if not isinstance(component, platform_message.Plain):
                continue
            lines = [
                line
                for line in component.text.replace('\r\n', '\n').split('\n')
                if line.strip() != self._COURSE_SALES_LINK_OPEN_QUESTION
            ]
            component.text = '\n'.join(lines)

    def _course_sales_resource_link(self, query: pipeline_query.Query) -> tuple[str, str]:
        workflow = self._active_workflow(query)
        if not isinstance(workflow, dict):
            return '', ''
        links = workflow.get('sales_links')
        if not isinstance(links, list):
            variables = workflow.get('variables') if isinstance(workflow.get('variables'), dict) else {}
            links = variables.get('sales_links')
        if not isinstance(links, list):
            return '', ''
        for item in links:
            if not isinstance(item, dict) or item.get('id') != 'phonics_resource_card':
                continue
            title = str(item.get('title') or '图书配套学习资源卡片').strip()
            url = str(item.get('url') or '').strip()
            if url:
                return title, url
        return '', ''

    def _promises_course_sales_resource_link(self, text: str) -> bool:
        if not text:
            return False
        if not any(marker in text for marker in ('资源链接', '资源卡片', '学习资源', '图书资源')):
            return False
        return any(marker in text for marker in ('再发', '重发', '重新发', '发一下', '补发', '发给您', '发给你'))

    def _course_sales_resource_step_selected(self, query: pipeline_query.Query) -> bool:
        intent_data = self._current_intent_data(query)
        selected_step_ids = self._as_string_set(intent_data.get('step_ids') or intent_data.get('image_step_ids'))
        return 'gift_qr' in selected_step_ids or intent_data.get('resource_link_id') == 'phonics_resource_card'

    def _append_course_sales_resource_link(self, query: pipeline_query.Query) -> None:
        if query.variables.get(self._COURSE_SALES_RESOURCE_LINK_QUEUED_KEY):
            return
        intent_data = self._current_intent_data(query)
        if str(intent_data.get('intent') or '') != 'resource_help':
            return
        reported_open_failure = self._course_sales_user_reported_open_failure(query)
        current_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        if not reported_open_failure and not self._course_sales_resource_step_selected(query):
            return
        if reported_open_failure and not self._promises_course_sales_resource_link(current_text):
            return
        title, url = self._course_sales_resource_link(query)
        if not url or url in current_text:
            return
        self._queue_extra_reply_chain(query, f'{title}：{url}')
        if not reported_open_failure:
            self._queue_extra_reply_chain(query, self._COURSE_SALES_LINK_OPEN_QUESTION)
        query.variables[self._COURSE_SALES_RESOURCE_LINK_QUEUED_KEY] = True

    def _strip_course_sales_trailing_unicode_emoji(self, query: pipeline_query.Query) -> None:
        workflow = self._active_workflow(query)
        if not self._is_course_sales_workflow(workflow) or not query.resp_message_chain:
            return
        stripped = False
        for chain in query.resp_message_chain:
            for component in chain:
                if not isinstance(component, platform_message.Plain):
                    continue
                text = component.text
                cleaned = self._TRAILING_UNICODE_EMOJI_RE.sub('', text).rstrip()
                if cleaned != text:
                    component.text = cleaned
                    stripped = True
        if stripped and not str(query.variables.get('auto_meme_emotion') or '').strip():
            query.variables['auto_meme_emotion'] = 'welcome'

    def _prepend_course_sales_first_reply_emoji(self, query: pipeline_query.Query) -> None:
        workflow = self._active_workflow(query)
        if not self._is_course_sales_workflow(workflow) or not query.resp_message_chain:
            return
        if query.variables.get('course_sales_first_contact') is not True:
            return
        if not str(query.variables.get('auto_meme_emotion') or '').strip():
            query.variables['auto_meme_emotion'] = 'welcome'

    def _source_message_id(self, query: pipeline_query.Query) -> str:
        message_chain = getattr(getattr(query, 'message_event', None), 'message_chain', None)
        message_id = str(getattr(message_chain, 'message_id', '') or '').strip()
        if message_id:
            return message_id
        for component in message_chain or []:
            if isinstance(component, platform_message.Source):
                return str(component.id or '').strip()
        return ''

    async def _add_platform_reaction(self, query: pipeline_query.Query) -> None:
        emoji_type = str(query.variables.pop('lark_reaction_emoji_type', '') or '').strip()
        if not emoji_type:
            return
        add_reaction = getattr(query.adapter, 'add_message_reaction', None)
        if not callable(add_reaction):
            return
        message_id = self._source_message_id(query)
        if not message_id:
            return
        try:
            await add_reaction(message_id, emoji_type)
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Failed to add platform reaction: %s', exc)

    def _meme_config(self, query: pipeline_query.Query) -> dict[str, Any]:
        pipeline_config = query.pipeline_config if isinstance(query.pipeline_config, dict) else {}
        template_config = pipeline_config.get('template_config')
        if isinstance(template_config, dict) and isinstance(template_config.get('memes'), dict):
            return template_config['memes']

        workflow = self._active_workflow(query)
        if not isinstance(workflow, dict):
            return {}
        memes = workflow.get('memes')
        if not isinstance(memes, dict):
            variables = workflow.get('variables') if isinstance(workflow.get('variables'), dict) else {}
            memes = variables.get('memes')
        return memes if isinstance(memes, dict) else {}

    def _has_explicit_meme_config(self, query: pipeline_query.Query) -> bool:
        pipeline_config = query.pipeline_config if isinstance(query.pipeline_config, dict) else {}
        template_config = pipeline_config.get('template_config')
        if isinstance(template_config, dict) and isinstance(template_config.get('memes'), dict):
            return True
        workflow = self._active_workflow(query)
        if not isinstance(workflow, dict):
            return False
        if isinstance(workflow.get('memes'), dict):
            return True
        variables = workflow.get('variables') if isinstance(workflow.get('variables'), dict) else {}
        return isinstance(variables.get('memes'), dict)

    def _meme_config_bool(self, query: pipeline_query.Query, key: str, default: bool) -> bool:
        value = self._meme_config(query).get(key)
        return value if isinstance(value, bool) else default

    def _meme_config_int(self, query: pipeline_query.Query, key: str, default: int, minimum: int = 1, maximum: int = 99) -> int:
        try:
            value = int(self._meme_config(query).get(key) or default)
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    def _meme_master_enabled(self, query: pipeline_query.Query) -> bool:
        return self._meme_config_bool(query, 'enabled', True)

    def _large_meme_enabled(self, query: pipeline_query.Query) -> bool:
        workflow = self._active_workflow(query)
        if self._is_task_assistant_workflow(workflow) and not self._has_explicit_meme_config(query):
            return False
        if (
            self._is_course_sales_workflow(workflow)
            and not self._has_explicit_meme_config(query)
            and not self._is_lark_query(query)
            and not str(query.variables.get('lark_reaction_emoji_type') or '').strip()
        ):
            return False
        return self._meme_config_bool(query, 'large_enabled', True)

    def _feishu_native_emoji_enabled(self, query: pipeline_query.Query) -> bool:
        return self._meme_config_bool(query, 'feishu_native_enabled', True)

    def _is_lark_query(self, query: pipeline_query.Query) -> bool:
        adapter = getattr(query, 'adapter', None)
        adapter_class = getattr(adapter, '__class__', None)
        adapter_name = str(getattr(adapter_class, '__name__', type(adapter).__name__)).lower()
        return 'lark' in adapter_name or 'feishu' in adapter_name

    def _meme_library_enabled(self, query: pipeline_query.Query) -> bool:
        return self._meme_config_bool(query, 'library_enabled', True)

    def _meme_api_fallback_enabled(self, query: pipeline_query.Query) -> bool:
        config = self._meme_config(query)
        return config.get('api_fallback_enabled') is not False and config.get('oiapi_enabled') is not False

    def _meme_smart_judge_enabled(self, query: pipeline_query.Query) -> bool:
        config = self._meme_config(query)
        value = config.get('smart_judge_enabled')
        if isinstance(value, bool):
            return value
        value = config.get('smart_enabled')
        return value if isinstance(value, bool) else True

    def _meme_interval_rounds(self, query: pipeline_query.Query, kind: str) -> int:
        if kind == 'small':
            return self._meme_config_int(query, 'small_interval_rounds', 3)
        return self._meme_config_int(query, 'large_interval_rounds', 5)

    def _meme_session_key(self, query: pipeline_query.Query) -> str:
        session_id = str(query.variables.get('session_id') or '').strip()
        launcher_type = getattr(getattr(query, 'launcher_type', ''), 'value', getattr(query, 'launcher_type', ''))
        launcher_id = str(getattr(query, 'launcher_id', '') or '').strip()
        session_key = session_id or f'{launcher_type}_{launcher_id}'
        bot_uuid = str(getattr(query, 'bot_uuid', '') or '').strip()
        pipeline_uuid = str(getattr(query, 'pipeline_uuid', '') or '').strip()
        return f'{bot_uuid}:{pipeline_uuid}:{session_key}'

    def _meme_session_state(self, query: pipeline_query.Query) -> dict[str, int]:
        key = self._meme_session_key(query)
        if len(self._meme_session_states) > 1000 and key not in self._meme_session_states:
            self._meme_session_states.pop(next(iter(self._meme_session_states)), None)
        return self._meme_session_states.setdefault(key, {'turn': 0})

    def _prepare_meme_turn(self, query: pipeline_query.Query) -> None:
        if query.variables.get('_meme_turn_prepared') is True:
            return
        state = self._meme_session_state(query)
        state['turn'] = int(state.get('turn') or 0) + 1
        query.variables['_meme_turn_prepared'] = True

    def _meme_frequency_allows(self, query: pipeline_query.Query, kind: str) -> bool:
        self._prepare_meme_turn(query)
        state = self._meme_session_state(query)
        turn = int(state.get('turn') or 0)
        last_turn = state.get(f'last_{kind}_turn')
        if last_turn is None:
            return True
        return turn - int(last_turn) >= self._meme_interval_rounds(query, kind)

    def _meme_required_due(self, query: pipeline_query.Query, kind: str) -> bool:
        self._prepare_meme_turn(query)
        state = self._meme_session_state(query)
        turn = int(state.get('turn') or 0)
        last_turn = state.get(f'last_{kind}_turn')
        required_within = self._meme_interval_rounds(query, kind)
        if last_turn is None:
            return turn >= required_within
        return turn - int(last_turn) >= required_within

    def _mark_meme_sent(self, query: pipeline_query.Query, kind: str) -> None:
        self._prepare_meme_turn(query)
        state = self._meme_session_state(query)
        state[f'last_{kind}_turn'] = int(state.get('turn') or 0)

    def _meme_suppressed_context(self, query: pipeline_query.Query) -> bool:
        intent = str(self._current_intent_data(query).get('intent') or '').strip()
        if intent in {'handoff', 'objection', 'explicit_rejection', 'stop'}:
            return True
        if not self._has_explicit_meme_config(query) and (
            query.variables.get(self._COURSE_SALES_SIGNUP_LINK_QUEUED_KEY) is True
            or query.variables.get(self._COURSE_SALES_RESOURCE_LINK_QUEUED_KEY) is True
        ):
            return True
        reply_text = self._plain_text_from_chain(query.resp_message_chain[-1]) if query.resp_message_chain else ''
        if not self._has_explicit_meme_config(query) and re.search(r'https?://', reply_text):
            return True
        text = str(query.variables.get('user_message_text') or self._query_user_text(query) or '').strip()
        return any(marker in text for marker in ('转人工', '投诉', '生气', '不需要', '别发', '退钱', '拉黑'))

    def _meme_emotion_for_dispatch(self, query: pipeline_query.Query, kind: str, emotion: str) -> str:
        if not self._meme_master_enabled(query):
            return ''
        emotion = str(emotion or '').strip()
        if emotion and self._meme_suppressed_context(query):
            return ''
        if emotion:
            return emotion if self._meme_frequency_allows(query, kind) else ''
        if self._meme_smart_judge_enabled(query):
            return '礼貌' if self._meme_required_due(query, kind) else ''
        if self._meme_suppressed_context(query):
            return ''
        if not self._meme_frequency_allows(query, kind):
            return ''
        return '礼貌'

    def _meme_library_items(self, query: pipeline_query.Query) -> list[dict[str, Any]]:
        if not self._meme_library_enabled(query):
            return []
        library = self._meme_config(query).get('library')
        if not isinstance(library, list):
            return []
        return [item for item in library if isinstance(item, dict) and item.get('enabled') is not False]

    def _meme_entry_codes(self, item: dict[str, Any]) -> set[str]:
        codes: set[str] = set()
        for key in ('code', 'trigger_keyword'):
            value = str(item.get(key) or '').strip().lower()
            if not value:
                continue
            match = self._MEME_TRIGGER_RE.fullmatch(value)
            codes.add(match.group(1).lower() if match else value.strip('{}'))
        for key in ('keywords', 'tags'):
            values = item.get(key)
            if isinstance(values, str):
                values = re.split(r'[\s,，/]+', values)
            if not isinstance(values, list):
                continue
            for value in values:
                text = str(value or '').strip().lower()
                if not text:
                    continue
                match = self._MEME_TRIGGER_RE.fullmatch(text)
                if match:
                    codes.add(match.group(1).lower())
        return {code for code in codes if code}

    def _known_meme_trigger_codes(self, query: pipeline_query.Query) -> set[str]:
        codes = set(self._DEFAULT_MEME_CODES)
        for item in self._meme_library_items(query):
            codes.update(self._meme_entry_codes(item))
        return codes

    def _strip_meme_trigger_codes(self, query: pipeline_query.Query) -> str:
        existing = str(query.variables.get('_auto_meme_trigger_code') or '').strip().lower()
        if existing:
            return existing

        known_codes = self._known_meme_trigger_codes(query)
        selected_code = ''

        def replace(match: re.Match[str]) -> str:
            nonlocal selected_code
            code = match.group(1).lower()
            if code not in known_codes:
                return match.group(0)
            if not selected_code:
                selected_code = code
            return ''

        for chain in query.resp_message_chain or []:
            for component in chain:
                if not isinstance(component, platform_message.Plain):
                    continue
                text = self._MEME_TRIGGER_RE.sub(replace, component.text)
                text = re.sub(r'[ \t]{2,}', ' ', text).strip()
                component.text = text

        if selected_code:
            query.variables['_auto_meme_trigger_code'] = selected_code
        return selected_code

    def _peek_meme_trigger_code(self, query: pipeline_query.Query) -> str:
        existing = str(query.variables.get('_auto_meme_trigger_code') or '').strip().lower()
        if existing:
            return existing
        known_codes = self._known_meme_trigger_codes(query)
        for chain in query.resp_message_chain or []:
            for component in chain:
                if not isinstance(component, platform_message.Plain):
                    continue
                for match in self._MEME_TRIGGER_RE.finditer(component.text):
                    code = match.group(1).lower()
                    if code in known_codes:
                        return code
        return ''

    def _meme_entry_matches_code(self, item: dict[str, Any], code: str) -> bool:
        return bool(code and code.lower() in self._meme_entry_codes(item))

    def _meme_emotion_lookup_keys(self, emotion: str) -> set[str]:
        needle = emotion.strip().lower()
        normalized = emotion.strip()
        aliases = {
            '赞同': {'like', 'success', '点赞'},
            '璧炲悓': {'like', 'success', '点赞'},
            '开心': {'happy'},
            '寮€蹇?': {'happy'},
            '感谢': {'thanks'},
            '鎰熻阿': {'thanks'},
            '疑惑': {'question', 'thinking'},
            '鐤戞儜': {'question', 'thinking'},
        }
        if normalized in self._FEISHU_NATIVE_KEY_ALIASES:
            aliases.setdefault(normalized, set()).add(self._FEISHU_NATIVE_KEY_ALIASES[normalized])
        if needle in self._FEISHU_NATIVE_EMOJIS_BY_KEY:
            aliases.setdefault(normalized, set()).add(needle)
        keys = {needle} if needle else set()
        keys.update(alias.lower() for alias in aliases.get(normalized, set()))
        return keys

    def _meme_entry_matches_emotion(self, item: dict[str, Any], emotion: str) -> bool:
        if not emotion:
            return False
        needles = self._meme_emotion_lookup_keys(emotion)
        values: list[str] = [
            str(item.get('emotion') or ''),
            str(item.get('meaning') or ''),
            str(item.get('search_keyword') or ''),
            str(item.get('usage_scene') or ''),
        ]
        usage_instruction = str(item.get('usage_instruction') or item.get('usage_timing') or item.get('timing') or '')
        if usage_instruction:
            positive_instruction = re.split(r'(?:不要|避免|不适合|不用于|禁用|禁止)', usage_instruction, maxsplit=1)[0]
            values.append(positive_instruction)
        for key in ('keywords', 'tags'):
            raw_values = item.get(key)
            if isinstance(raw_values, str):
                raw_values = re.split(r'[\s,，/]+', raw_values)
            if isinstance(raw_values, list):
                values.extend(str(value or '') for value in raw_values)
        return any(needle and needle in value.lower() for needle in needles for value in values)

    def _local_meme_entry(self, query: pipeline_query.Query, *, code: str = '', emotion: str = '') -> dict[str, Any] | None:
        items = self._meme_library_items(query)
        if not items:
            return None
        exact = [item for item in items if self._meme_entry_matches_code(item, code)]
        if exact:
            return random.choice(exact)
        emotional = [item for item in items if self._meme_entry_matches_emotion(item, emotion)]
        if emotional:
            return random.choice(emotional)
        return None

    def _default_local_meme_entry(self, query: pipeline_query.Query, emotion: str) -> dict[str, Any] | None:
        if not self._meme_library_enabled(query):
            return None
        for key in self._feishu_emoji_lookup_keys(emotion):
            code = self._FEISHU_NATIVE_KEY_ALIASES.get(key, key)
            if code in self._FEISHU_NATIVE_EMOJIS_BY_KEY:
                return {
                    'id': f'default-{code}',
                    'enabled': True,
                    'code': code,
                    'emotion': code,
                    'search_keyword': emotion,
                    'file_key': f'sales-memes/{code}/soft.png',
                }
        return None

    def _meme_emotion_from_entry(self, item: dict[str, Any], fallback: str) -> str:
        return str(item.get('search_keyword') or item.get('emotion') or item.get('code') or fallback).strip()

    async def _local_meme_component(self, item: dict[str, Any]) -> platform_message.Image | None:
        image_url = str(item.get('image_url') or item.get('url') or '').strip()
        file_key = str(item.get('file_key') or '').strip()
        if image_url or (file_key and not file_key.startswith(self._BUILTIN_MEME_FILE_PREFIX)):
            return await self._image_component(file_key, image_url, sticker=True)
        return None

    def _infer_generic_meme_emotion(self, query: pipeline_query.Query) -> str:
        workflow = self._active_workflow(query)
        if self._is_task_assistant_workflow(workflow):
            return ''
        text = str(query.variables.get('user_message_text') or self._query_user_text(query) or '').strip()
        if not text and query.resp_message_chain:
            text = self._plain_text_from_chain(query.resp_message_chain[-1])
        if not text:
            return ''
        if any(marker in text for marker in ('转人工', '投诉', '生气', '不需要', '别发', '退钱', '拉黑')):
            return ''
        if any(marker in text for marker in ('报名了', '已报名', '支付成功', '付款了', '买了', '下单了')):
            return '赞同'
        if any(marker in text for marker in ('谢谢', '感谢')):
            return '感谢'
        if any(marker in text for marker in ('你好', '您好', '哈喽', '在吗', '早上好', '晚上好')):
            return '欢迎'
        if any(marker in text for marker in ('可以打开', '能打开', '打开了', '好的', '好哒', '开心')):
            return '开心'
        return ''

    def _meme_emotion_for_query(self, query: pipeline_query.Query) -> str:
        if not self._meme_master_enabled(query):
            return ''
        trigger_code = self._strip_meme_trigger_codes(query)
        if trigger_code:
            entry = self._local_meme_entry(query, code=trigger_code)
            if entry:
                return self._meme_emotion_from_entry(entry, trigger_code)
            return trigger_code
        explicit = str(query.variables.get('auto_meme_emotion') or '').strip()
        if explicit:
            return explicit
        config = self._meme_config(query)
        if config.get('enabled') is False:
            return self._infer_generic_meme_emotion(query)
        intent = str(self._current_intent_data(query).get('intent') or '').strip()
        if intent in {'handoff', 'objection', 'explicit_rejection', 'stop'}:
            return ''
        if intent in {'purchased', 'purchase', 'radar_clicked'}:
            return '赞同'
        if intent in {'course_intro', 'course_question', 'product_intro', 'product_inquiry'}:
            return '服务'
        if intent == 'resource_confirmed':
            return 'received'
        if intent == 'smalltalk':
            return 'welcome'
        if intent in {'resource_help', 'screenshot_help', 'clarification', 'link_error'}:
            return '疑惑'
        return self._infer_generic_meme_emotion(query)

    def _configured_meme_url(self, query: pipeline_query.Query, emotion: str) -> str:
        config = self._meme_config(query)
        emotions = config.get('emotions') or config.get('images') or {}
        if not isinstance(emotions, dict):
            return ''
        candidates = emotions.get(emotion) or emotions.get('*') or []
        if isinstance(candidates, (str, dict)):
            candidates = [candidates]
        if not isinstance(candidates, list) or not candidates:
            return ''
        selected = random.choice(candidates)
        if isinstance(selected, str):
            return selected.strip()
        if isinstance(selected, dict):
            return str(selected.get('url') or selected.get('image_url') or '').strip()
        return ''

    def _meme_provider_keyword(self, provider: dict[str, Any], emotion: str) -> str:
        keywords = provider.get('keywords') if isinstance(provider.get('keywords'), dict) else {}
        return str(keywords.get(emotion) or emotion).strip()

    def _provider_params(self, provider: dict[str, Any], keyword: str, limit: int) -> dict[str, str]:
        params = provider.get('params') if isinstance(provider.get('params'), dict) else {}
        return {
            str(key): str(value).replace('{keyword}', keyword).replace('{limit}', str(limit))
            for key, value in params.items()
        }

    def _candidate_url(self, candidate: dict[str, Any]) -> str:
        for key in ('url', 'pic', 'image', 'img', 'src', 'path', 'gif', 'cover', 'face', 'murl'):
            value = candidate.get(key)
            if isinstance(value, str) and value.startswith(('http://', 'https://')):
                return value.strip()
        return ''

    def _extract_meme_candidates(self, payload: Any) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        def visit(value: Any, title_hint: str = '') -> None:
            if isinstance(value, str):
                if value.startswith(('http://', 'https://')):
                    candidates.append({'url': value, 'title': title_hint})
                return
            if isinstance(value, list):
                for item in value:
                    visit(item, title_hint)
                return
            if not isinstance(value, dict):
                return

            local_title = str(
                value.get('title')
                or value.get('name')
                or value.get('desc')
                or value.get('description')
                or title_hint
                or ''
            )
            url = self._candidate_url(value)
            if url:
                item = dict(value)
                item['url'] = url
                item['title'] = local_title
                candidates.append(item)
            for key in ('data', 'result', 'results', 'list', 'items', 'images', 'imgs', 'rows'):
                if key in value:
                    visit(value[key], local_title)

        visit(payload)
        return candidates

    def _is_safe_meme_candidate(self, candidate: dict[str, Any], emotion: str) -> bool:
        if not self._candidate_url(candidate):
            return False
        text = ' '.join(
            str(candidate.get(key) or '')
            for key in ('title', 'name', 'desc', 'description', 'source', 'url')
        ).lower()
        unsafe_terms = (
            '投降', '嘲讽', '鄙视', '垃圾', '骂', '咒', '滚', '傻', '笨', '爹', '妈',
            '草', '死你', '约炮', '色图', '看垃圾', '拳头硬', '破防', '裂开',
        )
        if any(term.lower() in text for term in unsafe_terms):
            return False

        positive_terms = {
            '赞同': ('赞', '点赞', '收到', '完成', '好的', 'ok', '+1', '可以', '支持'),
            '开心': ('开心', '高兴', '微笑', '笑', '愉快', '好耶', '欢呼'),
            '疑惑': ('疑惑', '疑问', '思考', '问号', '怎么', '无语', '懵'),
            '感谢': ('谢谢', '感谢', '合十', '致谢'),
        }
        opposite_terms = {
            '开心': ('不开心', '不高兴', '生气', '大哭'),
            '赞同': ('投降', '不同意', '拒绝', '嘲讽'),
            '感谢': ('不谢', '别谢'),
        }
        if any(term.lower() in text for term in opposite_terms.get(emotion, ())):
            return False
        title = str(candidate.get('title') or candidate.get('name') or candidate.get('desc') or '').strip()
        terms = positive_terms.get(emotion, ())
        if title and terms and not any(term.lower() in text for term in terms):
            return False
        return True

    async def _fetch_oiapi_meme_url(self, emotion: str, limit: int) -> str:
        session = httpclient.get_session()
        params = {'msg': emotion, '0': emotion, 'limit': str(max(1, limit))}
        async with session.get(
            self._OIAPI_EMOTION_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=8),
        ) as response:
            if response.status != 200:
                return ''
            payload = await response.json(content_type=None)
        data = payload.get('data') if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return ''
        for item in data:
            if not isinstance(item, dict):
                continue
            url = str(item.get('pic') or item.get('url') or '').strip()
            if url.startswith(('http://', 'https://')):
                return url
        return ''

    async def _fetch_meme_provider_candidates(
        self,
        provider: dict[str, Any],
        keyword: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        if provider.get('id') == 'oiapi':
            url = await self._fetch_oiapi_meme_url(keyword, limit)
            return [{'url': url, 'title': keyword}] if url else []

        session = httpclient.get_session()
        async with session.get(
            str(provider.get('url') or ''),
            params=self._provider_params(provider, keyword, limit),
            timeout=aiohttp.ClientTimeout(total=8),
        ) as response:
            if response.status != 200:
                return []
            text = await response.text()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = text
        return self._extract_meme_candidates(payload)

    async def _fetch_provider_chain_meme_url(self, emotion: str, limit: int) -> str:
        for provider in self._MEME_PROVIDERS:
            keyword = self._meme_provider_keyword(provider, emotion)
            try:
                candidates = await self._fetch_meme_provider_candidates(provider, keyword, limit)
            except Exception:
                continue
            for candidate in candidates:
                if self._is_safe_meme_candidate(candidate, emotion):
                    return self._candidate_url(candidate)
        return ''

    async def _meme_image_url(self, query: pipeline_query.Query, emotion: str) -> str:
        configured = self._configured_meme_url(query, emotion)
        if configured:
            return configured
        if not self._meme_api_fallback_enabled(query):
            return ''
        config = self._meme_config(query)
        try:
            limit = int(config.get('oiapi_limit') or 5)
        except (TypeError, ValueError):
            limit = 5
        try:
            return await self._fetch_provider_chain_meme_url(emotion, limit)
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Failed to fetch OIAPI meme for %s: %s', emotion, exc)
            return ''

    async def _meme_image_component(self, query: pipeline_query.Query, emotion: str) -> platform_message.Image | None:
        trigger_code = str(query.variables.get('_auto_meme_trigger_code') or '').strip().lower()
        entry = self._local_meme_entry(query, code=trigger_code, emotion=emotion)
        has_explicit_local_entry = entry is not None
        if entry:
            component = await self._local_meme_component(entry)
            if component is not None:
                return component
            emotion = self._meme_emotion_from_entry(entry, emotion)

        configured = self._configured_meme_url(query, emotion)
        if configured:
            return await self._image_component('', configured, sticker=True)

        if not (trigger_code and has_explicit_local_entry):
            default_entry = self._default_local_meme_entry(query, emotion)
            if default_entry:
                component = await self._local_meme_component(default_entry)
                if component is not None:
                    return component

        if not self._meme_api_fallback_enabled(query):
            return None
        config = self._meme_config(query)
        try:
            limit = int(config.get('oiapi_limit') or 5)
        except (TypeError, ValueError):
            limit = 5
        try:
            url = await self._fetch_provider_chain_meme_url(emotion, limit)
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Failed to fetch OIAPI meme for %s: %s', emotion, exc)
            return None
        if not url:
            return None
        return await self._image_component('', url, sticker=True)

    async def _append_auto_meme(self, query: pipeline_query.Query) -> None:
        if query.variables.get('_auto_meme_sent') is True:
            return
        if not self._large_meme_enabled(query):
            return
        emotion = self._meme_emotion_for_dispatch(query, 'large', self._meme_emotion_for_query(query))
        if not emotion:
            return
        image = await self._meme_image_component(query, emotion)
        if image is None:
            return
        extra_chains = query.variables.get(self._EXTRA_REPLY_CHAINS_KEY)
        if not isinstance(extra_chains, list):
            extra_chains = []
            query.variables[self._EXTRA_REPLY_CHAINS_KEY] = extra_chains
        insert_at = 0
        for index, chain in enumerate(extra_chains):
            if isinstance(chain, platform_message.MessageChain) and re.search(
                r'https?://',
                self._plain_text_from_chain(chain),
            ):
                insert_at = index + 1
        extra_chains.insert(insert_at, platform_message.MessageChain([image]))
        query.variables['_auto_meme_sent'] = True
        self._mark_meme_sent(query, 'large')

    def _feishu_emoji_lookup_keys(self, value: str) -> list[str]:
        text = str(value or '').strip()
        if not text:
            return []
        keys: list[str] = []
        lowered = text.lower().strip('{} ')
        if lowered:
            keys.append(lowered)
        if text in self._FEISHU_NATIVE_KEY_ALIASES:
            keys.append(self._FEISHU_NATIVE_KEY_ALIASES[text])
        for key in self._meme_emotion_lookup_keys(text):
            keys.append(self._FEISHU_NATIVE_KEY_ALIASES.get(key, key))
        seen: set[str] = set()
        return [key for key in keys if key and not (key in seen or seen.add(key))]

    def _feishu_native_emoji_for_entry(self, item: dict[str, Any] | None, fallback: str = '') -> str:
        if item:
            explicit = str(item.get('feishu_emoji') or item.get('native_emoji') or '').strip()
            if explicit in self._FEISHU_NATIVE_EMOJI_VALUES:
                return explicit
            values: list[str] = [
                str(item.get('code') or ''),
                str(item.get('trigger_keyword') or ''),
                str(item.get('emotion') or ''),
                str(item.get('search_keyword') or ''),
                str(item.get('meaning') or ''),
            ]
            for key in ('keywords', 'tags'):
                raw_values = item.get(key)
                if isinstance(raw_values, str):
                    raw_values = re.split(r'[\s,，/]+', raw_values)
                if isinstance(raw_values, list):
                    values.extend(str(value or '') for value in raw_values)
            for value in values:
                for lookup_key in self._feishu_emoji_lookup_keys(value):
                    options = self._FEISHU_NATIVE_EMOJIS_BY_KEY.get(lookup_key)
                    if options:
                        return random.choice(options)

        for lookup_key in self._feishu_emoji_lookup_keys(fallback):
            options = self._FEISHU_NATIVE_EMOJIS_BY_KEY.get(lookup_key)
            if options:
                return random.choice(options)
        return ''

    def _replace_meme_triggers_with_feishu_native_emoji(self, query: pipeline_query.Query) -> bool:
        known_codes = self._known_meme_trigger_codes(query)
        selected_code = str(query.variables.get('_auto_meme_trigger_code') or '').strip().lower()
        replaced_any = False

        def replacement(match: re.Match[str]) -> str:
            nonlocal selected_code, replaced_any
            code = match.group(1).lower()
            if code not in known_codes:
                return match.group(0)
            entry = self._local_meme_entry(query, code=code)
            emoji = self._feishu_native_emoji_for_entry(entry, code)
            if not emoji:
                return ''
            if not selected_code:
                selected_code = code
            replaced_any = True
            return emoji

        for chain in query.resp_message_chain or []:
            for component in chain:
                if not isinstance(component, platform_message.Plain):
                    continue
                text = self._MEME_TRIGGER_RE.sub(replacement, component.text)
                text = re.sub(r'[ \t]{2,}', ' ', text).strip()
                component.text = text

        if selected_code:
            query.variables['_auto_meme_trigger_code'] = selected_code
        return replaced_any

    def _prepend_feishu_native_emoji(self, query: pipeline_query.Query) -> None:
        if not self._meme_master_enabled(query) or not self._feishu_native_emoji_enabled(query):
            return
        if not self._is_lark_query(query) or not query.resp_message_chain:
            return
        trigger_code = self._peek_meme_trigger_code(query)
        if trigger_code:
            entry = self._local_meme_entry(query, code=trigger_code)
            emotion = self._meme_emotion_from_entry(entry, trigger_code) if entry else trigger_code
        else:
            emotion = self._meme_emotion_for_query(query)
        emotion = self._meme_emotion_for_dispatch(query, 'small', emotion)
        if not emotion:
            if trigger_code and not self._large_meme_enabled(query):
                self._strip_meme_trigger_codes(query)
            return
        if self._replace_meme_triggers_with_feishu_native_emoji(query):
            self._mark_meme_sent(query, 'small')
            return
        entry = self._local_meme_entry(query, code=str(query.variables.get('_auto_meme_trigger_code') or ''), emotion=emotion)
        emoji = self._feishu_native_emoji_for_entry(entry, emotion)
        if not emoji:
            return
        for component in query.resp_message_chain[-1]:
            if not isinstance(component, platform_message.Plain):
                continue
            text = component.text.strip()
            if not text or text.startswith('[') or text.endswith(']'):
                return
            component.text = f'{text} {emoji}'
            self._mark_meme_sent(query, 'small')
            return

    def _course_sales_signup_link(self, query: pipeline_query.Query, intent_data: dict[str, Any]) -> str:
        link = str(intent_data.get('link_url') or query.variables.get('course_sales_radar_link') or '').strip()
        if not link or '/api/v1/sales/radar/click/' in link:
            return link

        sales_service = getattr(self.ap, 'sales_service', None)
        if sales_service is None or not hasattr(sales_service, 'build_radar_tracking_url'):
            return link

        launcher_type = getattr(query, 'launcher_type', None)
        target_type = str(getattr(launcher_type, 'value', '') or '').strip().lower()
        if not target_type:
            launcher_type_text = str(launcher_type or '').lower()
            target_type = 'group' if 'group' in launcher_type_text else 'person'
        target_id = str(getattr(query, 'launcher_id', '') or '').strip()
        workflow = query.pipeline_config.get('workflow') if isinstance(query.pipeline_config, dict) else {}
        radar = workflow.get('radar') if isinstance(workflow, dict) and isinstance(workflow.get('radar'), dict) else {}
        try:
            return str(
                sales_service.build_radar_tracking_url(
                    destination_url=link,
                    bot_uuid=str(getattr(query, 'bot_uuid', '') or ''),
                    target_type=target_type or 'person',
                    target_id=target_id,
                    link_id='phonics_radar_apply',
                    session_id=str(query.variables.get('session_id') or (f'{target_type}_{target_id}' if target_id else '')),
                    pipeline_uuid=str(getattr(query, 'pipeline_uuid', '') or ''),
                    tracking_base_path=str(radar.get('tracking_base_path') or '/api/v1/sales/radar/click'),
                )
            ).strip()
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Failed to build course sales radar tracking link: %s', exc)
            return link

    def _contains_course_sales_link(self, text: str) -> bool:
        return 'yuanfudao.com/primary/templates/package' in text or '/api/v1/sales/radar/click/' in text

    def _replace_course_sales_link_placeholders(
        self,
        message_chain: platform_message.MessageChain,
        link: str,
    ) -> bool:
        replaced = False
        placeholders = ('[报名链接]', '【报名链接】', '[报名入口]', '【报名入口】')
        link_placeholder_pattern = re.compile(
            r'((?:报名|预约|购买|课程)?(?:链接|入口|通道|页面)\s*[：:]?\s*)(?:[xXｘＸ]{2,}|…+|\.{3,})'
        )
        for component in message_chain:
            if not isinstance(component, platform_message.Plain):
                continue
            text = component.text
            new_text = re.sub(r'[\[【]报名(?:链接|入口)[^\]】]*[\]】]', link, text)
            if new_text != text:
                text = new_text
                replaced = True
            for placeholder in placeholders:
                if placeholder in text:
                    text = text.replace(placeholder, link)
                    replaced = True
            text, count = link_placeholder_pattern.subn(lambda match: f'{match.group(1)}{link}', text)
            if count:
                replaced = True
            component.text = text
        return replaced

    def _replace_raw_course_sales_links(
        self,
        message_chain: platform_message.MessageChain,
        link: str,
    ) -> bool:
        replaced = False
        raw_link_pattern = re.compile(r'https?://m\.yuanfudao\.com/primary/templates/package[^\s<>"\]\)】》>，。！？、；：]*')
        for component in message_chain:
            if not isinstance(component, platform_message.Plain):
                continue
            text, count = raw_link_pattern.subn(link, component.text)
            if count:
                replaced = True
                component.text = text
        return replaced

    def _promises_course_sales_signup_link(self, text: str) -> bool:
        return any(
            marker in text
            for marker in (
                '链接发给您',
                '链接发给你',
                '把链接发给您',
                '把链接发给你',
                '课表发给您',
                '课表发给你',
                '详细课表发给您',
                '详细课表发给你',
                '报名页面',
                '报名页',
                '报名入口',
            )
        )

    def _append_course_sales_signup_link(self, query: pipeline_query.Query) -> None:
        if not query.resp_message_chain:
            return

        intent_data = self._current_intent_data(query)
        intent = str(intent_data.get('intent') or '')
        if intent in {'explicit_rejection', 'objection', 'stop', 'handoff'}:
            return

        link = self._course_sales_signup_link(query, intent_data)
        if not link:
            return

        if self._replace_course_sales_link_placeholders(query.resp_message_chain[-1], link):
            return

        if self._replace_raw_course_sales_links(query.resp_message_chain[-1], link):
            return

        current_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        if intent not in {'purchase', 'radar_clicked'} and not self._promises_course_sales_signup_link(current_text):
            return

        if self._contains_course_sales_link(current_text):
            return

        self._queue_extra_reply_chain(
            query,
            f'猿辅导英语自然拼读9元体验课点这里👉：{link}',
        )
        query.variables[self._COURSE_SALES_SIGNUP_LINK_QUEUED_KEY] = True

    def _estimate_voice_length_seconds(self, text: str) -> int:
        visible_chars = sum(1 for char in (text or '') if not char.isspace())
        if visible_chars <= 0:
            return 1
        return max(1, min(60, (visible_chars + 4) // 5))

    async def _append_task_assistant_voice(self, query: pipeline_query.Query, text: str) -> None:
        if not query.resp_message_chain:
            return
        task_assistant_service = getattr(self.ap, 'task_assistant_service', None)
        if task_assistant_service is None:
            return
        voice_base64 = await task_assistant_service.synthesize_reply_voice(query, text)
        if voice_base64:
            query.resp_message_chain[-1] = platform_message.MessageChain(
                [platform_message.Voice(base64=voice_base64, length=self._estimate_voice_length_seconds(text))]
            )

    async def _append_response_enrichments(self, query: pipeline_query.Query) -> None:
        if not query.resp_message_chain:
            return
        self._prepare_meme_turn(query)
        if await self._apply_handoff_response(query):
            self._normalize_course_sales_text(query)
            return
        if await self._apply_special_case_response(query):
            self._normalize_course_sales_text(query)
            self._strip_course_sales_trailing_unicode_emoji(query)
            self._prepend_course_sales_first_reply_emoji(query)
            self._append_course_sales_open_question(query)
            self._prepend_feishu_native_emoji(query)
            await self._append_auto_meme(query)
            return
        reply_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        await self._append_workflow_images(query, link_bound_only=False)
        self._normalize_course_sales_text(query)
        reply_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        await self._append_task_assistant_voice(query, reply_text)
        self._remove_course_sales_open_question_after_resource_failure(query)
        self._append_course_sales_resource_link(query)
        self._append_course_sales_signup_link(query)
        await self._append_workflow_images(query, link_bound_only=True)
        self._normalize_course_sales_text(query)
        self._strip_course_sales_trailing_unicode_emoji(query)
        self._prepend_course_sales_first_reply_emoji(query)
        self._append_course_sales_open_question(query)
        self._prepend_feishu_native_emoji(query)
        await self._append_auto_meme(query)

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        """处理"""

        random_range = (
            query.pipeline_config['output']['force-delay']['min'],
            query.pipeline_config['output']['force-delay']['max'],
        )

        random_delay = random.uniform(*random_range)

        self.ap.logger.debug('根据规则强制延迟回复: %s s', random_delay)

        await asyncio.sleep(random_delay)

        if query.pipeline_config['output']['misc']['at-sender'] and isinstance(
            query.message_event, platform_events.GroupMessage
        ):
            query.resp_message_chain[-1].insert(0, platform_message.At(target=query.message_event.sender.id))

        quote_origin = query.pipeline_config['output']['misc']['quote-origin']

        has_chunks = any(isinstance(msg, provider_message.MessageChunk) for msg in query.resp_messages)
        # TODO 命令与流式的兼容性问题
        if await query.adapter.is_stream_output_supported() and has_chunks:
            is_final = [msg.is_final for msg in query.resp_messages][0]
            self._strip_thinking_from_response(query)
            if is_final:
                await self._append_response_enrichments(query)
                self._strip_thinking_from_response(query)
                await self._add_platform_reaction(query)
            reply_chains = self._multi_reply_chains(query) if is_final else [query.resp_message_chain[-1]]
            await query.adapter.reply_message_chunk(
                message_source=query.message_event,
                bot_message=query.resp_messages[-1],
                message=reply_chains[0],
                quote_origin=quote_origin,
                is_final=is_final,
            )
            if is_final:
                for message_chain in [
                    *reply_chains[1:],
                    *self._pop_outgoing_extra_reply_chains(query),
                ]:
                    await query.adapter.reply_message(
                        message_source=query.message_event,
                        message=message_chain,
                        quote_origin=False,
                    )
        else:
            self._strip_thinking_from_response(query)
            await self._append_response_enrichments(query)
            self._strip_thinking_from_response(query)
            await self._add_platform_reaction(query)
            reply_chains = [
                *self._multi_reply_chains(query),
                *self._pop_outgoing_extra_reply_chains(query),
            ]
            for index, message_chain in enumerate(reply_chains):
                await query.adapter.reply_message(
                    message_source=query.message_event,
                    message=message_chain,
                    quote_origin=quote_origin if index == 0 else False,
                )

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
