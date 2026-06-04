from __future__ import annotations

import base64
import gzip
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import aiohttp
import sqlalchemy
import websockets

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from ....core import app
from ....entity.persistence import model as persistence_model
from ....entity.persistence import pipeline as persistence_pipeline
from ....utils import paths as path_utils
from .pipeline import default_stage_order


TASK_ASSISTANT_SCENARIO = 'task_assistant_ant_af'
TASK_ASSISTANT_PIPELINE_UUID = 'task-assistant-ant-af-pipeline'
TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID = 'task-assistant-ant-af-template-pipeline'
TASK_ASSISTANT_PROVIDER_UUID = 'task-assistant-bailian-provider'
TASK_ASSISTANT_MODEL_UUID = 'task-assistant-qwen-vl-plus'
TASK_ASSISTANT_MODEL_NAME = 'qwen-vl-plus'
TASK_ASSISTANT_TTS_VOICE_TYPE = 'zh_female_yuanqinvyou_moon_bigtts'


ANT_AF_STEPS = [
    {
        'id': 'download_qr',
        'title': '支付宝扫码下载蚂蚁阿福 App',
        'detail': '让用户先用支付宝扫描绑定的渠道码，进入下载页面，点击“下载蚂蚁阿福App”。',
        'image_key': 'task-assistant/ant-af/af_step_01.png',
        'intents': ['task_overview', 'download_app', 'screenshot_help'],
    },
    {
        'id': 'app_store_download',
        'title': '在应用商店点击下载',
        'detail': '如果跳转到应用商店，确认页面是“蚂蚁阿福”，点击下载并等待安装完成。',
        'image_key': 'task-assistant/ant-af/af_step_02.png',
        'intents': ['task_overview', 'download_app', 'screenshot_help'],
    },
    {
        'id': 'alipay_login',
        'title': '打开 App 后使用支付宝一键登录',
        'detail': '进入蚂蚁阿福首页后，点击页面底部的“支付宝一键登录”。',
        'image_key': 'task-assistant/ant-af/af_step_03.png',
        'intents': ['task_overview', 'alipay_login', 'screenshot_help'],
    },
    {
        'id': 'alipay_login_confirm',
        'title': '同意支付宝授权登录',
        'detail': '在支付宝授权页确认申请方是蚂蚁阿福 App，点击“同意”。',
        'image_key': 'task-assistant/ant-af/af_step_04.png',
        'intents': ['task_overview', 'alipay_login', 'screenshot_help'],
    },
    {
        'id': 'open_profile',
        'title': '登录后点击左上角头像/菜单',
        'detail': '登录成功后，在首页点击左上角头像或菜单入口，进入个人中心。',
        'image_key': 'task-assistant/ant-af/af_step_05.png',
        'intents': ['task_overview', 'real_person_verify', 'screenshot_help'],
    },
    {
        'id': 'open_settings',
        'title': '进入设置',
        'detail': '在个人中心页面点击用户信息区域或设置入口，进入“我的/设置”相关页面。',
        'image_key': 'task-assistant/ant-af/af_step_06.png',
        'intents': ['task_overview', 'real_person_verify', 'screenshot_help'],
    },
    {
        'id': 'open_real_person_verify',
        'title': '点击实名认证',
        'detail': '在“我的”页面找到“实名认证”，点击进入。若显示“已认证”，说明这一步已完成。',
        'image_key': 'task-assistant/ant-af/af_step_07.png',
        'intents': ['task_overview', 'real_person_verify', 'finish', 'screenshot_help'],
    },
    {
        'id': 'import_identity',
        'title': '支付宝一键导入身份信息',
        'detail': '在真人认证页面点击“支付宝一键导入”，按支付宝提示完成身份信息授权。',
        'image_key': 'task-assistant/ant-af/af_step_08.png',
        'intents': ['task_overview', 'real_person_verify', 'finish', 'screenshot_help'],
    },
]

ANT_AF_STEP_IDS = [step['id'] for step in ANT_AF_STEPS]
ANT_AF_STEP_INDEX_BY_ID = {step_id: idx for idx, step_id in enumerate(ANT_AF_STEP_IDS)}
CHINESE_STEP_NUMBERS = {
    '一': 0,
    '二': 1,
    '三': 2,
    '四': 3,
    '五': 4,
    '六': 5,
    '七': 6,
    '八': 7,
    '1': 0,
    '2': 1,
    '3': 2,
    '4': 3,
    '5': 4,
    '6': 5,
    '7': 6,
    '8': 7,
}


class TaskAssistantService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self._session_progress: dict[str, dict[str, Any]] = {}

    def is_task_assistant_pipeline(self, pipeline_config: dict[str, Any] | None) -> bool:
        if not isinstance(pipeline_config, dict):
            return False
        workflow = pipeline_config.get('workflow')
        if not isinstance(workflow, dict):
            return False
        metadata = workflow.get('metadata') if isinstance(workflow.get('metadata'), dict) else {}
        return metadata.get('scenario') == TASK_ASSISTANT_SCENARIO

    async def prepare_query(self, query: pipeline_query.Query) -> dict[str, Any]:
        if not self.is_task_assistant_pipeline(getattr(query, 'pipeline_config', None)):
            return {'handled': False}

        if not getattr(query, 'variables', None):
            query.variables = {}

        text = query.variables.get('user_message_text', '')
        session_key = self._query_session_key(query)
        progress = self._session_progress.get(session_key, {}) if session_key else {}
        previous_messages = getattr(query, 'messages', []) or []
        intent = self.classify_intent(text, query.message_chain, previous_messages, progress)
        self._record_progress(session_key, intent)
        query.variables['workflow_intent'] = intent
        query.variables['task_assistant_voice_reply'] = self._has_voice(query.message_chain)
        self._rewrite_user_message_for_multimodal_task(query)
        self._append_step_control_context(query, intent)

        if getattr(query, 'prompt', None) is not None and hasattr(query.prompt, 'messages'):
            if not query.variables.get('_task_assistant_prompt_injected'):
                query.prompt.messages.insert(
                    0,
                    provider_message.Message(role='system', content=self.compose_system_prompt()),
                )
                query.variables['_task_assistant_prompt_injected'] = True

        return {'handled': True, 'intent': intent}

    def classify_intent(
        self,
        text: str,
        message_chain: platform_message.MessageChain | list[platform_message.MessageComponent],
        previous_messages: list[provider_message.Message] | None = None,
        progress: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = (text or '').strip().lower()
        progress = progress or {}
        current_step_id = str(progress.get('current_step_id') or '')
        current_step_index = ANT_AF_STEP_INDEX_BY_ID.get(current_step_id)
        if current_step_index is None:
            current_step_index = self._step_index_from_messages(previous_messages or [])

        explicit_step_index = self._step_index_from_user_text(normalized)
        overview_sent = bool(progress.get('overview_sent'))

        if self._has_image(message_chain):
            step_ids = [ANT_AF_STEPS[current_step_index]['id']] if current_step_index is not None else []
            return {
                'intent': 'screenshot_help',
                'confidence': 0.92,
                'reason': '用户发送了截图，需要识别当前卡住的步骤',
                'step_ids': step_ids,
                'max_images': 1 if step_ids else 0,
                'reply_mode': 'single_step',
                'max_steps_to_describe': 1,
                'include_full_overview': False,
            }
        if self._is_progress_command(normalized):
            next_step_index = self._next_step_index(current_step_index)
            return self._step_intent(
                intent='task_progress',
                confidence=0.84,
                reason='用户表示已完成当前步骤，需要继续下一步',
                step_index=next_step_index,
            )
        if explicit_step_index is not None:
            return self._step_intent(
                intent=self._intent_for_step_index(explicit_step_index),
                confidence=0.86,
                reason='用户明确说明当前卡在某个步骤',
                step_index=explicit_step_index,
            )
        if any(keyword in normalized for keyword in ['完整流程', '完整步骤', '全部流程', '全部步骤', '所有步骤', '一次说完']):
            return self._overview_intent('full_overview', '用户明确要求查看完整流程')
        if any(keyword in normalized for keyword in ['下载', '扫码', '二维码', '安装', 'app']):
            step_id = 'app_store_download' if any(keyword in normalized for keyword in ['应用商店', '安装']) else 'download_qr'
            return self._step_intent(
                intent='download_app',
                confidence=0.82,
                reason='命中下载安装关键词',
                step_index=ANT_AF_STEP_INDEX_BY_ID[step_id],
            )
        if any(keyword in normalized for keyword in ['实名', '真人', '认证', '身份', '导入']):
            step_id = 'import_identity' if '导入' in normalized else 'open_real_person_verify'
            if any(keyword in normalized for keyword in ['设置', '我的']):
                step_id = 'open_settings'
            return self._step_intent(
                intent='real_person_verify',
                confidence=0.86,
                reason='命中实名认证相关关键词',
                step_index=ANT_AF_STEP_INDEX_BY_ID[step_id],
            )
        if any(keyword in normalized for keyword in ['登录', '授权', '一键登录', '同意']):
            step_id = 'alipay_login_confirm' if any(keyword in normalized for keyword in ['授权', '同意']) else 'alipay_login'
            return self._step_intent(
                intent='alipay_login',
                confidence=0.82,
                reason='命中支付宝授权登录关键词',
                step_index=ANT_AF_STEP_INDEX_BY_ID[step_id],
            )
        if any(keyword in normalized for keyword in ['已认证', '认证成功', '任务完成', '完成了', '成功了']):
            return self._step_intent(
                intent='finish',
                confidence=0.78,
                reason='用户确认已完成或接近完成',
                step_index=ANT_AF_STEP_INDEX_BY_ID['import_identity'],
            )
        if self._has_voice(message_chain):
            return self._step_intent(
                intent='voice_reply',
                confidence=0.78,
                reason='用户发送了语音消息',
                step_index=current_step_index or 0,
            )
        if self._is_general_task_question(normalized):
            if overview_sent:
                return self._step_intent(
                    intent='task_overview',
                    confidence=0.7,
                    reason='用户重复询问任务流程，沿用当前步骤继续引导',
                    step_index=current_step_index or 0,
                )
            return self._overview_intent('first_overview', '会话首次咨询任务流程')

        return self._step_intent(
            intent='task_overview',
            confidence=0.64,
            reason='默认从当前步骤继续引导',
            step_index=current_step_index or 0,
        )

    def _step_intent(
        self,
        *,
        intent: str,
        confidence: float,
        reason: str,
        step_index: int,
    ) -> dict[str, Any]:
        step_index = max(0, min(step_index, len(ANT_AF_STEPS) - 1))
        return {
            'intent': intent,
            'confidence': confidence,
            'reason': reason,
            'step_ids': [ANT_AF_STEPS[step_index]['id']],
            'current_step_no': step_index + 1,
            'max_images': 1,
            'reply_mode': 'single_step',
            'max_steps_to_describe': 1,
            'include_full_overview': False,
        }

    def _overview_intent(self, reply_mode: str, reason: str) -> dict[str, Any]:
        return {
            'intent': 'task_overview',
            'confidence': 0.72,
            'reason': reason,
            'step_ids': ['download_qr'],
            'current_step_no': 1,
            'max_images': 1,
            'reply_mode': reply_mode,
            'max_steps_to_describe': 8,
            'include_full_overview': True,
        }

    def _query_session_key(self, query: pipeline_query.Query) -> str:
        session = getattr(query, 'session', None)
        launcher_type = getattr(getattr(session, 'launcher_type', None), 'value', None)
        launcher_id = getattr(session, 'launcher_id', None)
        if launcher_type and launcher_id is not None:
            return f'{launcher_type}_{launcher_id}'

        launcher_type = getattr(getattr(query, 'launcher_type', None), 'value', None) or getattr(query, 'launcher_type', '')
        launcher_id = getattr(query, 'launcher_id', '')
        return f'{launcher_type}_{launcher_id}' if launcher_type and launcher_id != '' else ''

    def _record_progress(self, session_key: str, intent: dict[str, Any]) -> None:
        if not session_key:
            return
        progress = self._session_progress.setdefault(session_key, {})
        step_ids = intent.get('step_ids') if isinstance(intent.get('step_ids'), list) else []
        if step_ids:
            progress['current_step_id'] = str(step_ids[0])
        if intent.get('include_full_overview'):
            progress['overview_sent'] = True

    def _append_step_control_context(self, query: pipeline_query.Query, intent: dict[str, Any]) -> None:
        user_message = getattr(query, 'user_message', None)
        if not isinstance(user_message, provider_message.Message):
            return
        if not isinstance(user_message.content, list):
            user_message.content = [provider_message.ContentElement.from_text(str(user_message.content or ''))]

        step = self._step_from_intent(intent)
        reply_mode = intent.get('reply_mode')
        if reply_mode in {'first_overview', 'full_overview'}:
            control_text = (
                '\n\n[任务办理上下文]\n'
                '可以给一版精简完整流程，每步只写一行；完整流程说完后，立刻聚焦第 1 步。'
                '后续用户再问时不要重复完整流程，只根据当前步骤继续引导。'
            )
        elif step is not None:
            step_no = int(intent.get('current_step_no') or (ANT_AF_STEP_INDEX_BY_ID[step['id']] + 1))
            control_text = (
                '\n\n[任务办理上下文]\n'
                f'本轮只讲第 {step_no} 步：{step["title"]}。本轮只讲这一步，不要列出完整 8 步；'
                '不要重复完整流程。用真人客服口吻告诉用户具体点哪里，最后只补一句做完后可以继续问下一步。'
            )
        else:
            control_text = (
                '\n\n[任务办理上下文]\n'
                '用户发了截图但当前步骤不明确。先根据图片识别页面，再只讲识别出的当前步骤；'
                '如果识别不出来，只问一个最短的问题，不要乱发第一步。'
            )

        user_message.content.append(provider_message.ContentElement.from_text(control_text))

    def _step_from_intent(self, intent: dict[str, Any]) -> dict[str, Any] | None:
        step_ids = intent.get('step_ids') if isinstance(intent.get('step_ids'), list) else []
        if not step_ids:
            return None
        step_index = ANT_AF_STEP_INDEX_BY_ID.get(str(step_ids[0]))
        if step_index is None:
            return None
        return ANT_AF_STEPS[step_index]

    def _is_progress_command(self, normalized: str) -> bool:
        return any(
            keyword in normalized
            for keyword in [
                '下一步',
                '下步',
                '继续',
                '好了',
                '弄好了',
                '做完了',
                '完成这步',
                '完成这一步',
                '然后呢',
                '接下来',
            ]
        )

    def _is_general_task_question(self, normalized: str) -> bool:
        return any(keyword in normalized for keyword in ['怎么做', '怎么完成', '如何完成', '这个任务', '流程', '步骤'])

    def _next_step_index(self, current_step_index: int | None) -> int:
        if current_step_index is None:
            return 0
        return min(current_step_index + 1, len(ANT_AF_STEPS) - 1)

    def _step_index_from_user_text(self, normalized: str) -> int | None:
        for token, step_index in CHINESE_STEP_NUMBERS.items():
            if re.search(rf'第\s*{re.escape(token)}\s*步', normalized):
                return step_index
        step_keywords = [
            ('download_qr', ['二维码', '扫码', '渠道码']),
            ('app_store_download', ['应用商店', '安装']),
            ('alipay_login', ['一键登录', '支付宝登录']),
            ('alipay_login_confirm', ['授权', '同意']),
            ('open_profile', ['头像', '菜单', '个人中心']),
            ('open_settings', ['设置', '我的']),
            ('open_real_person_verify', ['实名认证', '实名']),
            ('import_identity', ['导入身份', '一键导入', '身份信息']),
        ]
        for step_id, keywords in step_keywords:
            if any(keyword in normalized for keyword in keywords):
                return ANT_AF_STEP_INDEX_BY_ID[step_id]
        return None

    def _step_index_from_messages(self, previous_messages: list[provider_message.Message]) -> int | None:
        for message in reversed(previous_messages):
            if getattr(message, 'role', '') not in {'assistant', 'system'}:
                continue
            text = self._message_text(message)
            step_index = self._step_index_from_user_text(text.lower())
            if step_index is not None:
                return step_index
        return None

    def _message_text(self, message: provider_message.Message) -> str:
        content = getattr(message, 'content', '')
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return ''.join(str(getattr(item, 'text', '') or '') for item in content)
        return ''

    def _intent_for_step_index(self, step_index: int) -> str:
        step_id = ANT_AF_STEPS[step_index]['id']
        if step_id in {'download_qr', 'app_store_download'}:
            return 'download_app'
        if step_id in {'alipay_login', 'alipay_login_confirm'}:
            return 'alipay_login'
        if step_id in {'open_profile', 'open_settings', 'open_real_person_verify', 'import_identity'}:
            return 'real_person_verify'
        return 'task_overview'

    def compose_system_prompt(self) -> str:
        step_text = '\n'.join(
            f'{idx}. {step["title"]}：{step["detail"]}' for idx, step in enumerate(ANT_AF_STEPS, 1)
        )
        return f"""你是蚂蚁阿福实名认证办理客服，像真人客服一样自然说话。

说话要求：
- 不要自称 AI、机器人、任务助手、智能助手。
- 不要用官方公告腔，像真人客服一样短句、明确、好懂。
- 用户第一次问完整任务怎么做时，可以先给精简完整流程，每步只写一行，然后马上带他做第 1 步。
- 除了第一次完整概览或用户明确要“完整流程”，每次只讲当前一步和下一步动作，不要一次把 8 个步骤全部列出来。
- 用户说卡住了或发送截图时，先判断他大概在哪一步，再告诉他下一步点哪里。
- 用户发语音时，用短句回复，适合转语音播放。
- 不要编造蚂蚁阿福以外的活动规则、收益承诺或非文档中的入口。

已知标准流程：
{step_text}

回复格式：
1. 先判断用户当前所在步骤。
2. 给出下一步动作，动作要具体到按钮或页面名称。
3. 如果用户缺少上下文，只问一个最短的问题，例如“你现在页面上能看到实名认证吗？”。
4. 如果用户已经完成，提醒他检查是否显示已认证或任务完成。
""".strip()

    def _rewrite_user_message_for_multimodal_task(self, query: pipeline_query.Query) -> None:
        """Keep task-assistant model input compatible with Bailian chat/vision calls."""
        if not isinstance(getattr(query, 'user_message', None), provider_message.Message):
            return

        content: list[provider_message.ContentElement] = []
        plain_text = str(query.variables.get('user_message_text') or '').strip()
        has_voice = self._has_voice(query.message_chain)

        if plain_text:
            content.append(provider_message.ContentElement.from_text(plain_text))

        if has_voice:
            voice_context = (
                '用户发来一条语音咨询。请按蚂蚁阿福实名认证办理场景回复，'
                '口吻像真人客服，短句、自然、适合语音播报；'
                '如果没有明确步骤信息，就先引导他从支付宝扫码下载或让他发当前页面截图。'
            )
            content.append(provider_message.ContentElement.from_text(voice_context))

        for component in query.message_chain:
            if not isinstance(component, platform_message.Image):
                continue
            if component.base64:
                content.append(provider_message.ContentElement.from_image_base64(component.base64))
            elif component.url:
                content.append(provider_message.ContentElement.from_image_url(component.url))

        if not content:
            content.append(
                provider_message.ContentElement.from_text(
                    '用户正在咨询蚂蚁阿福实名认证办理流程，请用真人客服口吻确认他当前卡在哪一步。'
                )
            )

        query.user_message = provider_message.Message(role='user', content=content)

    async def synthesize_reply_voice(self, query: pipeline_query.Query, text: str) -> str | None:
        workflow = query.pipeline_config.get('workflow') if isinstance(query.pipeline_config, dict) else {}
        if not self.is_task_assistant_pipeline(query.pipeline_config):
            return None
        if not query.variables.get('task_assistant_voice_reply'):
            return None

        voice_config = workflow.get('voice') if isinstance(workflow.get('voice'), dict) else {}
        if voice_config.get('enabled') is False:
            return None

        app_id = (
            voice_config.get('app_id')
            or os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_APP_ID')
            or os.getenv('VOLCENGINE_TTS_APP_ID')
        )
        token = (
            voice_config.get('token')
            or os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_TOKEN')
            or os.getenv('VOLCENGINE_TTS_TOKEN')
        )
        if not app_id or not token:
            self.ap.logger.warning('Task assistant TTS skipped: Volcengine app_id/token is not configured')
            return None

        plain_text = self._compact_tts_text(text)
        if not plain_text:
            return None

        encoding = voice_config.get('encoding') or 'ogg_opus'
        audio_base64 = await self._request_volcengine_tts(
            text=plain_text,
            app_id=app_id,
            token=token,
            cluster=voice_config.get('cluster') or 'volcano_tts',
            voice_type=voice_config.get('voice_type') or TASK_ASSISTANT_TTS_VOICE_TYPE,
            encoding=encoding,
        )
        if not audio_base64:
            return None
        return f'data:{self._tts_mime_type(encoding)};base64,{audio_base64}'

    async def ensure_default_resources(self) -> None:
        await self._ensure_task_images()
        await self._ensure_bailian_model()
        await self._ensure_pipeline()
        await self._ensure_template_pipeline()

    def build_pipeline_config(
        self,
        *,
        bailian_model_uuid: str = TASK_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        config['ai']['runner']['runner'] = 'local-agent'
        config['ai']['runner']['expire-time'] = 0
        config['ai']['local-agent']['model'] = {'primary': bailian_model_uuid, 'fallbacks': []}
        config['ai']['local-agent']['max-round'] = 8
        config['ai']['local-agent']['prompt'] = [
            {'role': 'system', 'content': self.compose_system_prompt()},
        ]
        config['output']['misc']['at-sender'] = False
        config['output']['misc']['quote-origin'] = True
        existing_workflow = existing_config.get('workflow') if isinstance(existing_config, dict) else {}
        existing_voice = existing_workflow.get('voice') if isinstance(existing_workflow, dict) else {}
        config['workflow'] = self.build_workflow_config(
            voice_overrides=existing_voice if isinstance(existing_voice, dict) else None,
        )
        return config

    def build_template_pipeline_config(
        self,
        *,
        bailian_model_uuid: str = TASK_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = self.build_pipeline_config(
            bailian_model_uuid=bailian_model_uuid,
            existing_config=existing_config,
        )
        existing_template = existing_config.get('template_config') if isinstance(existing_config, dict) else {}
        template_config = self.build_template_config(
            overrides=existing_template if isinstance(existing_template, dict) else None,
        )
        config['config_mode'] = 'template'
        config['template_config'] = template_config
        config['workflow'] = self.build_workflow_from_template_config(template_config)
        return config

    def build_template_config(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        voice = {
            'provider': 'volcengine',
            'enabled': True,
            'voice_type': TASK_ASSISTANT_TTS_VOICE_TYPE,
            'encoding': 'ogg_opus',
        }
        scheduled_push = {
            'enabled': True,
            'mode': 'daily',
            'time': '10:00',
            'single_date': '',
            'message': '你好，今天继续完成蚂蚁阿福实名认证任务，有卡住的页面直接发截图给我。',
            'push_message': '你好，今天继续完成蚂蚁阿福实名认证任务，有卡住的页面直接发截图给我。',
        }
        template_config = {
            'name': '任务助手模板配置版',
            'role_prompt': self.compose_system_prompt(),
            'opening_message': '我带你一步步完成实名认证。先用支付宝扫码下载蚂蚁阿福 App，完成后跟我说“下一步”。',
            'recommended_questions': [
                '我应该怎么完成这个任务？',
                '我卡在这一步了怎么办？',
                '下一步怎么做？',
            ],
            'model_uuid': TASK_ASSISTANT_MODEL_UUID,
            'max_reasoning_steps': 2,
            'reference_rounds': 2,
            'knowledge_base_uuids': [],
            'product_uuids': [],
            'tools': {
                'intent_recognition': True,
                'knowledge_base': True,
                'product_database': True,
                'image_recognition': True,
                'voice_reply': True,
            },
            'memory': {
                'variables_enabled': True,
                'table_enabled': True,
                'segments_enabled': False,
            },
            'voice': voice,
            'scheduled_push': scheduled_push,
            'image_text_bindings': [
                {
                    'step_id': step['id'],
                    'title': step['title'],
                    'text': step['detail'],
                    'file_key': step['image_key'],
                    'trigger_intents': step['intents'],
                    'enabled': True,
                }
                for step in ANT_AF_STEPS
            ],
        }
        if overrides:
            for key, value in overrides.items():
                if key == 'voice' and isinstance(value, dict):
                    template_config['voice'] = {**voice, **value}
                elif key == 'scheduled_push' and isinstance(value, dict):
                    template_config['scheduled_push'] = {**scheduled_push, **value}
                elif key == 'image_text_bindings' and isinstance(value, list) and value:
                    template_config['image_text_bindings'] = value
                else:
                    template_config[key] = value
        return template_config

    def build_workflow_from_template_config(self, template_config: dict[str, Any]) -> dict[str, Any]:
        voice_overrides = template_config.get('voice') if isinstance(template_config.get('voice'), dict) else None
        workflow = self.build_workflow_config(voice_overrides=voice_overrides)
        workflow['name'] = str(template_config.get('name') or '任务助手模板配置版')
        metadata = workflow.setdefault('metadata', {})
        metadata['source_mode'] = 'template'
        metadata['template_name'] = template_config.get('name') or '任务助手模板配置版'

        model_uuid = str(template_config.get('model_uuid') or TASK_ASSISTANT_MODEL_UUID)
        for node in workflow.get('nodes', []):
            if not isinstance(node, dict):
                continue
            config = node.setdefault('config', {})
            if node.get('type') in {'llm', 'vision'}:
                config['model_uuid'] = model_uuid
            if node.get('type') == 'voice' and isinstance(template_config.get('voice'), dict):
                config.update(template_config['voice'])

        bindings = template_config.get('image_text_bindings')
        if isinstance(bindings, list):
            binding_by_step = {
                str(binding.get('step_id')): binding for binding in bindings if isinstance(binding, dict)
            }
            for node in workflow.get('nodes', []):
                if not isinstance(node, dict):
                    continue
                config = node.setdefault('config', {})
                step_id = str(config.get('step_id') or '')
                binding = binding_by_step.get(step_id)
                if not binding:
                    continue
                if node.get('type') == 'task':
                    node['title'] = str(binding.get('title') or node.get('title') or '')
                    node['description'] = str(binding.get('text') or node.get('description') or '')
                    config['instruction'] = str(binding.get('text') or config.get('instruction') or '')
                    config['enabled'] = binding.get('enabled', True)
                elif node.get('type') == 'image':
                    node['title'] = str(binding.get('title') or node.get('title') or '')
                    config['file_key'] = str(binding.get('file_key') or config.get('file_key') or '')
                    config['caption'] = str(binding.get('title') or config.get('caption') or '')
                    config['enabled'] = binding.get('enabled', True)

        scheduled_push = template_config.get('scheduled_push')
        if isinstance(scheduled_push, dict):
            workflow['scheduled_push'] = scheduled_push
        return workflow

    def build_workflow_config(self, voice_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        voice_config = {
            'provider': 'volcengine',
            'enabled': True,
            'app_id': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_APP_ID', ''),
            'token': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_TOKEN', ''),
            'cluster': 'volcano_tts',
            'voice_type': TASK_ASSISTANT_TTS_VOICE_TYPE,
            'encoding': 'ogg_opus',
        }
        if voice_overrides:
            for key in ('app_id', 'token'):
                if voice_overrides.get(key):
                    voice_config[key] = voice_overrides[key]

        nodes = [
            {
                'id': 'start',
                'type': 'start',
                'title': '会话触发',
                'description': '用户在网页、微信或企微发来咨询',
                'position': {'x': 80, 'y': 260},
                'config': {'trigger': 'message'},
            },
            {
                'id': 'channel',
                'type': 'channel',
                'title': '渠道接入',
                'description': '统一接收网页、微信、企微等渠道消息',
                'position': {'x': 330, 'y': 260},
                'config': {'channels': ['web', 'wechat', 'wecom'], 'keep_session': True},
            },
            {
                'id': 'media_router',
                'type': 'media',
                'title': '消息类型判断',
                'description': '区分文字、截图和语音',
                'position': {'x': 580, 'y': 260},
                'config': {
                    'routes': [
                        {'when': 'has_text', 'target': 'text_input'},
                        {'when': 'has_voice', 'target': 'voice_asr'},
                        {'when': 'has_image', 'target': 'screenshot_input'},
                    ],
                },
            },
            {
                'id': 'text_input',
                'type': 'custom',
                'title': '文字问题',
                'description': '整理用户文字问题和上下文',
                'position': {'x': 850, 'y': 90},
                'config': {
                    'output_key': 'user_text',
                    'params': '{"from": "message_chain.plain_text"}',
                },
            },
            {
                'id': 'voice_asr',
                'type': 'asr',
                'title': '语音输入处理',
                'description': '语音消息转成适合模型理解的任务上下文，避免聊天请求失败',
                'position': {'x': 850, 'y': 260},
                'config': {
                    'provider': 'bailian',
                    'fallback_text': '用户发来一条语音咨询，请用适合语音播报的短句回复。',
                },
            },
            {
                'id': 'screenshot_input',
                'type': 'vision',
                'title': '截图识别',
                'description': '识别用户卡在哪个页面或步骤',
                'position': {'x': 850, 'y': 430},
                'config': {
                    'model_uuid': TASK_ASSISTANT_MODEL_UUID,
                    'target_steps': [step['id'] for step in ANT_AF_STEPS],
                },
            },
            {
                'id': 'intent',
                'type': 'intent',
                'title': '意图识别',
                'description': '识别下载、登录、实名认证、截图卡点、完成确认等意图',
                'position': {'x': 1130, 'y': 260},
                'config': {
                    'intents': [
                        'task_overview',
                        'download_app',
                        'alipay_login',
                        'real_person_verify',
                        'finish',
                        'screenshot_help',
                        'voice_reply',
                    ],
                    'confidence_threshold': 0.55,
                    'image_intents': ['screenshot_help'],
                },
            },
            {
                'id': 'route_intent',
                'type': 'router',
                'title': '意图路由',
                'description': '把用户问题分发到对应步骤节点',
                'position': {'x': 1400, 'y': 260},
                'config': {
                    'rules': [
                        'download_app -> download_qr, app_store_download',
                        'alipay_login -> alipay_login, alipay_login_confirm',
                        'real_person_verify -> open_profile, open_settings, open_real_person_verify, import_identity',
                        'screenshot_help -> matched_step',
                        'finish -> open_real_person_verify, import_identity',
                    ],
                },
            },
            {
                'id': 'knowledge_fallback',
                'type': 'knowledge',
                'title': '知识库兜底',
                'description': '不属于固定步骤的问题，查知识库后再回答',
                'position': {'x': 1660, 'y': 620},
                'config': {'knowledge_base_uuids': [], 'top_k': 4},
            },
            {
                'id': 'reply',
                'type': 'llm',
                'title': '真人客服式回复',
                'description': '用百炼生成自然、短句、可执行的下一步指引',
                'position': {'x': 3030, 'y': 260},
                'config': {
                    'model_uuid': TASK_ASSISTANT_MODEL_UUID,
                    'tone': '真人客服、短句、具体',
                    'prompt': self.compose_system_prompt(),
                },
            },
            {
                'id': 'voice',
                'type': 'voice',
                'title': '火山语音回复',
                'description': '用户发语音时，把文字回复转成语音一起发回去',
                'position': {'x': 3300, 'y': 160},
                'config': {
                    'provider': 'volcengine',
                    'enabled': True,
                    'voice_type': TASK_ASSISTANT_TTS_VOICE_TYPE,
                    'encoding': 'ogg_opus',
                },
            },
            {
                'id': 'end',
                'type': 'end',
                'title': '发送给用户',
                'description': '发送文字、相关步骤图和必要时的语音',
                'position': {'x': 3300, 'y': 360},
                'config': {},
            },
        ]
        step_positions = [
            {'x': 1660, 'y': 40},
            {'x': 1660, 'y': 200},
            {'x': 1940, 'y': 40},
            {'x': 1940, 'y': 200},
            {'x': 2220, 'y': 40},
            {'x': 2220, 'y': 200},
            {'x': 2500, 'y': 40},
            {'x': 2500, 'y': 200},
        ]
        image_positions = [
            {'x': 1660, 'y': 380},
            {'x': 1660, 'y': 500},
            {'x': 1940, 'y': 380},
            {'x': 1940, 'y': 500},
            {'x': 2220, 'y': 380},
            {'x': 2220, 'y': 500},
            {'x': 2500, 'y': 380},
            {'x': 2500, 'y': 500},
        ]
        for idx, step in enumerate(ANT_AF_STEPS):
            nodes.append(
                {
                    'id': f'step_{step["id"]}',
                    'type': 'task',
                    'title': step['title'],
                    'description': step['detail'],
                    'position': step_positions[idx],
                    'config': {
                        'step_id': step['id'],
                        'step_no': idx + 1,
                        'instruction': step['detail'],
                        'trigger_intents': step['intents'],
                        'completion_check': '用户完成后继续下一步，最后检查是否显示已认证或任务完成。',
                    },
                }
            )
            nodes.append(
                {
                    'id': f'image_{step["id"]}',
                    'type': 'image',
                    'title': f'步骤图 {idx + 1}',
                    'description': step['title'],
                    'position': image_positions[idx],
                    'config': {
                        'file_key': step['image_key'],
                        'caption': step['title'],
                        'trigger_intents': step['intents'],
                        'append_caption': False,
                    },
                }
            )

        edges = [
            {'id': 'e-start-channel', 'source': 'start', 'target': 'channel'},
            {'id': 'e-channel-media', 'source': 'channel', 'target': 'media_router'},
            {'id': 'e-media-text', 'source': 'media_router', 'target': 'text_input', 'label': '文字'},
            {'id': 'e-media-voice', 'source': 'media_router', 'target': 'voice_asr', 'label': '语音'},
            {'id': 'e-media-image', 'source': 'media_router', 'target': 'screenshot_input', 'label': '截图/图片'},
            {'id': 'e-text-intent', 'source': 'text_input', 'target': 'intent'},
            {'id': 'e-voice-intent', 'source': 'voice_asr', 'target': 'intent'},
            {'id': 'e-screenshot-intent', 'source': 'screenshot_input', 'target': 'intent'},
            {'id': 'e-intent-route', 'source': 'intent', 'target': 'route_intent'},
            {'id': 'e-route-knowledge', 'source': 'route_intent', 'target': 'knowledge_fallback', 'label': '兜底问题'},
            {'id': 'e-knowledge-reply', 'source': 'knowledge_fallback', 'target': 'reply'},
            {'id': 'e-reply-voice', 'source': 'reply', 'target': 'voice', 'label': '用户发语音'},
            {'id': 'e-reply-end', 'source': 'reply', 'target': 'end', 'label': '文字/图片'},
            {'id': 'e-voice-end', 'source': 'voice', 'target': 'end'},
        ]
        for step in ANT_AF_STEPS:
            step_node_id = f'step_{step["id"]}'
            image_node_id = f'image_{step["id"]}'
            edges.extend(
                [
                    {
                        'id': f'e-route-{step["id"]}',
                        'source': 'route_intent',
                        'target': step_node_id,
                        'label': '/'.join(step['intents'][:2]),
                    },
                    {'id': f'e-step-image-{step["id"]}', 'source': step_node_id, 'target': image_node_id},
                    {'id': f'e-image-reply-{step["id"]}', 'source': image_node_id, 'target': 'reply'},
                ]
            )

        return {
            'version': 1,
            'name': '任务助手',
            'description': '用真人客服口吻引导用户完成蚂蚁阿福实名认证，支持步骤图片、截图识别和语音回复。',
            'metadata': {
                'scenario': TASK_ASSISTANT_SCENARIO,
                'source': '蚂蚁阿福.docx',
                'model_provider': 'bailian',
                'tts_provider': 'volcengine',
            },
            'nodes': nodes,
            'edges': edges,
            'voice': voice_config,
        }

    async def _ensure_task_images(self) -> None:
        image_dir = Path(path_utils.get_resource_path('templates/task-assistant/ant-af/images'))
        for idx, step in enumerate(ANT_AF_STEPS, 1):
            source_path = image_dir / f'af_step_{idx:02d}.png'
            if not source_path.exists():
                continue
            if await self.ap.storage_mgr.storage_provider.exists(step['image_key']):
                continue
            await self.ap.storage_mgr.storage_provider.save(step['image_key'], source_path.read_bytes())

    async def _ensure_bailian_model(self) -> None:
        api_key = os.getenv('LANGBOT_TASK_ASSISTANT_BAILIAN_API_KEY') or os.getenv('DASHSCOPE_API_KEY') or ''
        provider_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == TASK_ASSISTANT_PROVIDER_UUID
            )
        )
        provider = provider_result.first()
        provider_values = {
            'uuid': TASK_ASSISTANT_PROVIDER_UUID,
            'name': '任务助手-阿里云百炼',
            'requester': 'bailian-chat-completions',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'api_keys': [api_key] if api_key else [],
        }
        if provider is None:
            await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_model.ModelProvider).values(provider_values))
        elif api_key:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_model.ModelProvider)
                .where(persistence_model.ModelProvider.uuid == TASK_ASSISTANT_PROVIDER_UUID)
                .values(api_keys=[api_key])
            )

        model_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == TASK_ASSISTANT_MODEL_UUID)
        )
        if model_result.first() is None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_model.LLMModel).values(
                    uuid=TASK_ASSISTANT_MODEL_UUID,
                    name=TASK_ASSISTANT_MODEL_NAME,
                    provider_uuid=TASK_ASSISTANT_PROVIDER_UUID,
                    abilities=['vision'],
                    extra_args={},
                    prefered_ranking=0,
                )
            )

    async def _ensure_pipeline(self) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == TASK_ASSISTANT_PIPELINE_UUID
            )
        )
        existing_pipeline = result.first()
        if existing_pipeline is not None:
            existing_config = existing_pipeline.config if isinstance(existing_pipeline.config, dict) else {}
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == TASK_ASSISTANT_PIPELINE_UUID)
                .values(
                    name='任务助手',
                    description='用真人客服口吻引导用户完成蚂蚁阿福实名认证，支持一步一图、截图识别和语音回复。',
                    emoji='✅',
                    config=self.build_pipeline_config(existing_config=existing_config),
                    extensions_preferences={
                        'enable_all_plugins': True,
                        'enable_all_mcp_servers': True,
                        'plugins': [],
                        'mcp_servers': [],
                    },
                )
            )
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(
                uuid=TASK_ASSISTANT_PIPELINE_UUID,
                name='任务助手',
                description='用真人客服口吻引导用户完成蚂蚁阿福实名认证，支持一步一图、截图识别和语音回复。',
                emoji='✅',
                for_version=self.ap.ver_mgr.get_current_version(),
                is_default=False,
                stages=default_stage_order.copy(),
                config=self.build_pipeline_config(),
                extensions_preferences={
                    'enable_all_plugins': True,
                    'enable_all_mcp_servers': True,
                    'plugins': [],
                    'mcp_servers': [],
                },
            )
        )

    async def _ensure_template_pipeline(self) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID
            )
        )
        existing_pipeline = result.first()
        if existing_pipeline is not None:
            existing_config = existing_pipeline.config if isinstance(existing_pipeline.config, dict) else {}
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID)
                .values(
                    name='任务助手模板配置版',
                    description='用表单模板配置蚂蚁阿福实名认证引导，自动同步为可运行工作流。',
                    emoji='✅',
                    config=self.build_template_pipeline_config(existing_config=existing_config),
                    extensions_preferences={
                        'enable_all_plugins': True,
                        'enable_all_mcp_servers': True,
                        'plugins': [],
                        'mcp_servers': [],
                    },
                )
            )
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(
                uuid=TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID,
                name='任务助手模板配置版',
                description='用表单模板配置蚂蚁阿福实名认证引导，自动同步为可运行工作流。',
                emoji='✅',
                for_version=self.ap.ver_mgr.get_current_version(),
                is_default=False,
                stages=default_stage_order.copy(),
                config=self.build_template_pipeline_config(),
                extensions_preferences={
                    'enable_all_plugins': True,
                    'enable_all_mcp_servers': True,
                    'plugins': [],
                    'mcp_servers': [],
                },
            )
        )

    async def _request_volcengine_tts(
        self,
        *,
        text: str,
        app_id: str,
        token: str,
        cluster: str,
        voice_type: str,
        encoding: str,
    ) -> str | None:
        if voice_type.endswith('_bigtts') or encoding == 'ogg_opus':
            audio_base64 = await self._request_volcengine_tts_ws(
                text=text,
                app_id=app_id,
                token=token,
                cluster=cluster,
                voice_type=voice_type,
                encoding=encoding,
            )
            if audio_base64:
                return audio_base64

        payload = {
            'app': {
                'appid': app_id,
                'token': token,
                'cluster': cluster,
            },
            'user': {'uid': 'langbot-task-assistant'},
            'audio': {
                'voice_type': voice_type,
                'encoding': encoding,
                'speed_ratio': 1.0,
                'volume_ratio': 1.0,
                'pitch_ratio': 1.0,
            },
            'request': {
                'reqid': str(uuid.uuid4()),
                'text': text,
                'text_type': 'plain',
                'operation': 'query',
            },
        }
        for authorization in (f'Bearer;{token}', f'Bearer {token}'):
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://openspeech.bytedance.com/api/v1/tts',
                    json=payload,
                    headers={'Authorization': authorization},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    data = await response.json(content_type=None)
            if response.status == 200 and data.get('code') == 3000 and data.get('data'):
                return data['data']
            self.ap.logger.warning(
                'Volcengine TTS request failed: status=%s code=%s message=%s',
                response.status,
                data.get('code'),
                data.get('message'),
            )
        return None

    async def _request_volcengine_tts_ws(
        self,
        *,
        text: str,
        app_id: str,
        token: str,
        cluster: str,
        voice_type: str,
        encoding: str,
    ) -> str | None:
        payload = {
            'app': {
                'appid': app_id,
                'token': token,
                'cluster': cluster,
            },
            'user': {'uid': 'langbot-task-assistant'},
            'audio': {
                'voice_type': voice_type,
                'encoding': encoding,
                'speed_ratio': 1.0,
                'volume_ratio': 1.0,
                'pitch_ratio': 1.0,
            },
            'request': {
                'reqid': str(uuid.uuid4()),
                'text': text,
                'text_type': 'plain',
                'operation': 'submit',
            },
        }
        body = gzip.compress(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        request_bytes = bytes([0x11, 0x10, 0x11, 0x00]) + len(body).to_bytes(4, 'big') + body

        for authorization in (f'Bearer;{token}', f'Bearer; {token}'):
            audio_chunks: list[bytes] = []
            try:
                async with websockets.connect(
                    'wss://openspeech.bytedance.com/api/v1/tts/ws_binary',
                    additional_headers={'Authorization': authorization},
                    open_timeout=10,
                    close_timeout=5,
                    max_size=None,
                ) as websocket:
                    await websocket.send(request_bytes)
                    async for message in websocket:
                        if isinstance(message, str):
                            continue
                        audio_chunk, is_final = self._parse_volcengine_tts_ws_audio_message(message)
                        if audio_chunk:
                            audio_chunks.append(audio_chunk)
                        if is_final:
                            break
                if audio_chunks:
                    return base64.b64encode(b''.join(audio_chunks)).decode('utf-8')
            except Exception as exc:
                self.ap.logger.warning('Volcengine TTS websocket request failed: %s', exc)
        return None

    @staticmethod
    def _parse_volcengine_tts_ws_audio_message(message: bytes) -> tuple[bytes, bool]:
        if len(message) < 4:
            raise ValueError('Volcengine TTS websocket response is too short')

        header_size = (message[0] & 0x0F) * 4
        message_type = (message[1] & 0xF0) >> 4
        message_flags = message[1] & 0x0F
        compression = message[2] & 0x0F
        payload = message[header_size:]

        if message_type == 0xB:
            if message_flags == 0:
                return b'', False
            if len(payload) < 8:
                raise ValueError('Volcengine TTS websocket audio payload is too short')
            sequence_number = int.from_bytes(payload[:4], 'big', signed=True)
            payload_size = int.from_bytes(payload[4:8], 'big', signed=False)
            return payload[8 : 8 + payload_size], sequence_number < 0

        if message_type == 0xF:
            if len(payload) < 8:
                raise ValueError('Volcengine TTS websocket error payload is too short')
            error_code = int.from_bytes(payload[:4], 'big', signed=False)
            error_size = int.from_bytes(payload[4:8], 'big', signed=False)
            error_payload = payload[8 : 8 + error_size]
            if compression == 1:
                error_payload = gzip.decompress(error_payload)
            error_message = error_payload.decode('utf-8', errors='replace')
            raise ValueError(f'Volcengine TTS websocket error {error_code}: {error_message}')

        return b'', False

    @staticmethod
    def _tts_mime_type(encoding: str) -> str:
        if encoding == 'ogg_opus':
            return 'audio/ogg'
        if encoding == 'wav':
            return 'audio/wav'
        return 'audio/mpeg'

    def _compact_tts_text(self, text: str) -> str:
        normalized = ' '.join((text or '').split())
        if len(normalized) > 350:
            return normalized[:350] + '。'
        return normalized

    def _has_image(self, message_chain: platform_message.MessageChain | list[platform_message.MessageComponent]) -> bool:
        return any(isinstance(component, platform_message.Image) for component in message_chain)

    def _has_voice(self, message_chain: platform_message.MessageChain | list[platform_message.MessageComponent]) -> bool:
        return any(isinstance(component, platform_message.Voice) for component in message_chain)


def audio_bytes_to_data_uri(audio_bytes: bytes, mime_type: str = 'audio/mpeg') -> str:
    return f'data:{mime_type};base64,{base64.b64encode(audio_bytes).decode("utf-8")}'
