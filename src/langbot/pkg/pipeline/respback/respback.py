from __future__ import annotations

import random
import asyncio
import base64
import mimetypes
from typing import Any


import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from .. import stage, entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@stage.stage_class('SendResponseBackStage')
class SendResponseBackStage(stage.PipelineStage):
    """发送响应消息"""

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

    async def _matched_image_components(self, query: pipeline_query.Query) -> list[platform_message.MessageComponent]:
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

    async def _append_workflow_images(self, query: pipeline_query.Query) -> None:
        if not query.resp_message_chain:
            return
        for component in await self._matched_image_components(query):
            query.resp_message_chain[-1].append(component)

    def _plain_text_from_chain(self, message_chain: platform_message.MessageChain) -> str:
        return ''.join(component.text for component in message_chain if isinstance(component, platform_message.Plain))

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

    def _split_plain_text(self, text: str, threshold: int) -> list[str]:
        stripped = text.strip()
        if not stripped or len(stripped) <= threshold:
            return [text]

        chunks: list[str] = []
        current = ''
        for raw_part in stripped.replace('\r\n', '\n').split('\n'):
            part = raw_part.strip()
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
        message_chain = query.resp_message_chain[-1]
        if not enabled:
            return [message_chain]

        components = list(message_chain)
        if not components or any(not isinstance(component, platform_message.Plain) for component in components):
            return [message_chain]

        text = self._plain_text_from_chain(message_chain)
        if 'http://' in text or 'https://' in text or len(text.strip()) <= threshold:
            return [message_chain]

        chunks = self._split_plain_text(text, threshold)
        if len(chunks) <= 1:
            return [message_chain]
        return [platform_message.MessageChain([platform_message.Plain(text=chunk)]) for chunk in chunks]

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
        for component in message_chain:
            if not isinstance(component, platform_message.Plain):
                continue
            text = component.text
            for placeholder in placeholders:
                if placeholder in text:
                    text = text.replace(placeholder, link)
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

        link = self._course_sales_signup_link(query, intent_data)
        if not link:
            return

        if self._replace_course_sales_link_placeholders(query.resp_message_chain[-1], link):
            return

        current_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        if intent not in {'purchase', 'radar_clicked'} and not self._promises_course_sales_signup_link(current_text):
            return

        if self._contains_course_sales_link(current_text):
            return

        query.resp_message_chain[-1].append(
            platform_message.Plain(
                text=(
                    f'\n\n报名入口：{link}\n\n'
                    '点进去选孩子年级，手机号验证后支付9元就行。'
                    '支付成功后把截图发我，我帮您登记，后续老师会联系您安排上课和资料。'
                )
            )
        )

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
        reply_text = self._plain_text_from_chain(query.resp_message_chain[-1])
        await self._append_workflow_images(query)
        await self._append_task_assistant_voice(query, reply_text)
        self._append_course_sales_signup_link(query)

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
            if is_final:
                await self._append_response_enrichments(query)
            await query.adapter.reply_message_chunk(
                message_source=query.message_event,
                bot_message=query.resp_messages[-1],
                message=query.resp_message_chain[-1],
                quote_origin=quote_origin,
                is_final=is_final,
            )
        else:
            await self._append_response_enrichments(query)
            for index, message_chain in enumerate(self._multi_reply_chains(query)):
                await query.adapter.reply_message(
                    message_source=query.message_event,
                    message=message_chain,
                    quote_origin=quote_origin if index == 0 else False,
                )

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
