from __future__ import annotations

import random
import asyncio
import base64
import json
import mimetypes
import re
from typing import Any


import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

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
    _COURSE_SALES_CHILD_GRADE_RE = re.compile(r'(幼儿园|小班|中班|大班|[一二三四五六七八九1-9]年级|初[一二三]|高[一二三])')

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

    def _is_task_assistant_workflow(self, workflow: dict[str, Any]) -> bool:
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

    async def _image_component(self, file_key: str, image_url: str) -> platform_message.Image:
        if image_url:
            return platform_message.Image(url=image_url)

        storage_mgr = getattr(self.ap, 'storage_mgr', None)
        storage_provider = getattr(storage_mgr, 'storage_provider', None) if storage_mgr is not None else None
        if storage_provider is not None:
            try:
                file_content = await storage_provider.load(file_key)
                mime_type = mimetypes.guess_type(file_key)[0] or 'image/png'
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
            components.append(await self._image_component(file_key, image_url))

            if max_images is not None and sum(isinstance(component, platform_message.Image) for component in components) >= max_images:
                break

        return components

    async def _append_workflow_images(self, query: pipeline_query.Query, *, link_bound_only: bool | None = None) -> None:
        if not query.resp_message_chain:
            return
        for component in await self._matched_image_components(query, link_bound_only=link_bound_only):
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
        if not components or any(not isinstance(component, platform_message.Plain) for component in components):
            return [message_chain]

        text = self._plain_text_from_chain(message_chain)
        if is_course_sales:
            if any(not isinstance(component, (platform_message.Plain, platform_message.Image)) for component in components):
                return [message_chain]
            chains = self._course_sales_reply_chains(message_chain)
            if len(chains) <= 1 and text:
                return [platform_message.MessageChain([platform_message.Plain(text=self._strip_course_sales_final_periods(text))])]
            return chains

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
                component.text = self._strip_course_sales_final_periods(component.text)

    def _course_sales_link_question_needed(self, text: str) -> bool:
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

    def _course_sales_open_question(self, text: str) -> str:
        if self._course_sales_link_question_needed(text):
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

    def _queue_extra_reply_chain(self, query: pipeline_query.Query, text: str) -> None:
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

    def _append_course_sales_open_question(self, query: pipeline_query.Query) -> None:
        workflow = self._active_workflow(query)
        if not self._is_course_sales_workflow(workflow) or not query.resp_message_chain:
            return
        intent_data = self._current_intent_data(query)
        if str(intent_data.get('intent') or '') in {'explicit_rejection', 'objection', 'stop', 'handoff'}:
            return
        if str(intent_data.get('intent') or '') == 'resource_help' and self._course_sales_user_reported_open_failure(query):
            return
        current_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        if self._course_sales_user_confirmed_open(query):
            return
        question = self._course_sales_open_question(current_text)
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

    def _append_course_sales_resource_link(self, query: pipeline_query.Query) -> None:
        if query.variables.get(self._COURSE_SALES_RESOURCE_LINK_QUEUED_KEY):
            return
        intent_data = self._current_intent_data(query)
        if str(intent_data.get('intent') or '') != 'resource_help':
            return
        if not self._course_sales_user_reported_open_failure(query):
            return
        current_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        if not self._promises_course_sales_resource_link(current_text):
            return
        title, url = self._course_sales_resource_link(query)
        if not url or url in current_text:
            return
        self._queue_extra_reply_chain(query, f'{title}：{url}')
        query.variables[self._COURSE_SALES_RESOURCE_LINK_QUEUED_KEY] = True

    def _prepend_course_sales_first_reply_emoji(self, query: pipeline_query.Query) -> None:
        workflow = self._active_workflow(query)
        if not self._is_course_sales_workflow(workflow) or not query.resp_message_chain:
            return
        if query.variables.get('course_sales_first_contact') is not True:
            return
        for component in query.resp_message_chain[-1]:
            if not isinstance(component, platform_message.Plain):
                continue
            text = component.text.lstrip()
            if text.startswith(('😊', '😄', '😂', '👍', '👌', '🙏', '❤️')):
                return
            component.text = f'😊 {text}'
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
        if await self._apply_handoff_response(query):
            self._normalize_course_sales_text(query)
            return
        if await self._apply_special_case_response(query):
            self._normalize_course_sales_text(query)
            self._prepend_course_sales_first_reply_emoji(query)
            self._append_course_sales_open_question(query)
            return
        reply_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        await self._append_workflow_images(query, link_bound_only=False)
        await self._append_task_assistant_voice(query, reply_text)
        self._remove_course_sales_open_question_after_resource_failure(query)
        self._append_course_sales_resource_link(query)
        self._append_course_sales_signup_link(query)
        await self._append_workflow_images(query, link_bound_only=True)
        self._normalize_course_sales_text(query)
        self._prepend_course_sales_first_reply_emoji(query)
        self._append_course_sales_open_question(query)

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
                    *self._pop_extra_reply_chains(query),
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
            reply_chains = [
                *self._multi_reply_chains(query),
                *self._pop_extra_reply_chains(query),
            ]
            for index, message_chain in enumerate(reply_chains):
                await query.adapter.reply_message(
                    message_source=query.message_event,
                    message=message_chain,
                    quote_origin=quote_origin if index == 0 else False,
                )

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
