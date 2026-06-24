"""Message Aggregator Module

This module provides message aggregation/debounce functionality.
When users send multiple messages consecutively, the aggregator will wait
for a configurable delay period and merge them into a single message
before processing.
"""

from __future__ import annotations

import asyncio
import json
import time
import typing
from dataclasses import dataclass, field

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter

if typing.TYPE_CHECKING:
    from ..core import app

# Maximum number of messages to buffer before forcing a flush
MAX_BUFFER_MESSAGES = 10
DEFAULT_SPAM_HANDOFF_MESSAGES = 8


@dataclass
class PendingMessage:
    """A pending message waiting to be aggregated"""

    bot_uuid: str
    launcher_type: provider_session.LauncherTypes
    launcher_id: typing.Union[int, str]
    sender_id: typing.Union[int, str]
    message_event: platform_events.MessageEvent
    message_chain: platform_message.MessageChain
    adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter
    pipeline_uuid: typing.Optional[str]
    routed_by_rule: bool = False
    raw_monitoring_message_id: str = ''
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionBuffer:
    """Buffer for a single session's pending messages"""

    session_id: str
    messages: list[PendingMessage] = field(default_factory=list)
    timer_task: typing.Optional[asyncio.Task] = None
    last_message_time: float = field(default_factory=time.time)


class MessageAggregator:
    """Message aggregator that buffers and merges consecutive messages

    This class implements a debounce mechanism for incoming messages.
    When a message arrives, it starts a timer. If more messages arrive
    before the timer expires, they are buffered. When the timer expires,
    all buffered messages are merged and sent to the query pool.
    """

    ap: app.Application

    buffers: dict[str, SessionBuffer]
    """Session ID -> SessionBuffer mapping"""

    recent_message_ids: dict[str, dict[str, tuple[float, str]]]
    """Session ID -> recently seen platform message IDs with expiry and content fingerprint"""

    lock: asyncio.Lock
    """Lock for thread-safe buffer operations"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.buffers = {}
        self.recent_message_ids = {}
        self.lock = asyncio.Lock()

    def _get_session_id(
        self,
        bot_uuid: str,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: typing.Union[int, str],
    ) -> str:
        """Generate a unique session ID"""
        return f'{bot_uuid}:{launcher_type.value}:{launcher_id}'

    def _message_source_id(self, message_chain: platform_message.MessageChain) -> str:
        """Return the platform Source id when present."""
        for component in message_chain:
            if isinstance(component, platform_message.Source):
                return str(component.id or '').strip()
        return ''

    def _is_recent_duplicate(self, session_id: str, source_id: str, fingerprint: str, now: float) -> bool:
        if not source_id:
            return False

        recent_ids = self.recent_message_ids.setdefault(session_id, {})
        expired_ids = [msg_id for msg_id, (expires_at, _fingerprint) in recent_ids.items() if expires_at <= now]
        for msg_id in expired_ids:
            recent_ids.pop(msg_id, None)

        existing = recent_ids.get(source_id)
        if existing is not None and existing[1] == fingerprint:
            return True

        recent_ids[source_id] = (now + 60, fingerprint)
        return False

    def _sender_name(self, message_event: platform_events.MessageEvent) -> str | None:
        sender = getattr(message_event, 'sender', None)
        if sender is None:
            return None
        return getattr(sender, 'nickname', None) or getattr(sender, 'member_name', None)

    def _message_content(self, message_chain: platform_message.MessageChain) -> str:
        if hasattr(message_chain, 'model_dump'):
            return json.dumps(message_chain.model_dump(), ensure_ascii=False)
        return str(message_chain)

    async def _pipeline_name(self, pipeline_uuid: typing.Optional[str]) -> str:
        if not pipeline_uuid:
            return ''
        try:
            pipeline = await self.ap.pipeline_mgr.get_pipeline_by_uuid(pipeline_uuid)
            return getattr(getattr(pipeline, 'pipeline_entity', None), 'name', '') or pipeline_uuid
        except Exception:
            return pipeline_uuid

    async def _bot_name(self, bot_uuid: str) -> str:
        bot_mgr = getattr(self.ap, 'bot_mgr', None)
        get_bot = getattr(bot_mgr, 'get_bot', None)
        if get_bot is None:
            return bot_uuid
        try:
            bot = await get_bot(bot_uuid)
            name = getattr(getattr(bot, 'bot_entity', None), 'name', '')
            if name:
                return name
        except Exception:
            pass
        return bot_uuid

    async def _record_raw_monitoring_message(
        self,
        bot_uuid: str,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: typing.Union[int, str],
        sender_id: typing.Union[int, str],
        message_event: platform_events.MessageEvent,
        message_chain: platform_message.MessageChain,
        pipeline_uuid: typing.Optional[str],
    ) -> str:
        monitoring_service = getattr(self.ap, 'monitoring_service', None)
        if monitoring_service is None:
            return ''

        session_id = f'{launcher_type}_{launcher_id}'
        platform = launcher_type.value if hasattr(launcher_type, 'value') else str(launcher_type)
        pipeline_name = await self._pipeline_name(pipeline_uuid)
        bot_name = await self._bot_name(bot_uuid)

        message_id = await monitoring_service.record_message(
            bot_id=bot_uuid,
            bot_name=bot_name,
            pipeline_id=pipeline_uuid or '',
            pipeline_name=pipeline_name,
            message_content=self._message_content(message_chain),
            session_id=session_id,
            status='success',
            level='info',
            platform=platform,
            user_id=str(sender_id),
            user_name=self._sender_name(message_event),
            variables=json.dumps({'monitoring_source': 'raw_platform_message'}, ensure_ascii=False),
            role='user',
        )
        session_updated = await monitoring_service.update_session_activity(
            session_id,
            pipeline_id=pipeline_uuid or '',
            pipeline_name=pipeline_name,
        )
        if not session_updated:
            await monitoring_service.record_session_start(
                session_id=session_id,
                bot_id=bot_uuid,
                bot_name=bot_name,
                pipeline_id=pipeline_uuid or '',
                pipeline_name=pipeline_name,
                platform=platform,
                user_id=str(sender_id),
                user_name=self._sender_name(message_event),
            )
        return message_id

    async def _get_aggregation_config(self, pipeline_uuid: typing.Optional[str]) -> tuple[bool, float]:
        """Get aggregation configuration for a pipeline

        Returns:
            tuple: (enabled, delay_seconds)
        """
        default_enabled = False
        default_delay = 1.5

        if pipeline_uuid is None:
            return default_enabled, default_delay

        # Get pipeline from pipeline manager
        pipeline = await self.ap.pipeline_mgr.get_pipeline_by_uuid(pipeline_uuid)
        if pipeline is None:
            return default_enabled, default_delay

        config = pipeline.pipeline_entity.config or {}
        trigger_config = config.get('trigger', {})
        aggregation_config = trigger_config.get('message-aggregation', {})

        enabled = aggregation_config.get('enabled', default_enabled)

        delay_raw = aggregation_config.get('delay', default_delay)
        try:
            delay = float(delay_raw)
        except (TypeError, ValueError):
            delay = default_delay

        # Clamp delay to valid range
        delay = max(1.0, min(10.0, delay))

        return enabled, delay

    async def _pipeline_config(self, pipeline_uuid: typing.Optional[str]) -> dict:
        if pipeline_uuid is None:
            return {}
        pipeline = await self.ap.pipeline_mgr.get_pipeline_by_uuid(pipeline_uuid)
        if pipeline is None:
            return {}
        config = getattr(getattr(pipeline, 'pipeline_entity', None), 'config', None)
        return config if isinstance(config, dict) else {}

    def _is_course_sales_config(self, config: dict) -> bool:
        workflow = config.get('workflow') if isinstance(config.get('workflow'), dict) else {}
        metadata = workflow.get('metadata') if isinstance(workflow.get('metadata'), dict) else {}
        return metadata.get('scenario') == 'course_sales_yuanfudao_phonics' or workflow.get('scenario') == 'course_sales_yuanfudao_phonics'

    def _spam_handoff_limit(self, config: dict) -> int | None:
        if not self._is_course_sales_config(config):
            return None
        trigger_config = config.get('trigger') if isinstance(config.get('trigger'), dict) else {}
        aggregation_config = (
            trigger_config.get('message-aggregation')
            if isinstance(trigger_config.get('message-aggregation'), dict)
            else {}
        )
        if aggregation_config.get('spam_handoff_enabled') is False:
            return None
        try:
            limit = int(aggregation_config.get('spam_message_limit') or DEFAULT_SPAM_HANDOFF_MESSAGES)
        except (TypeError, ValueError):
            limit = DEFAULT_SPAM_HANDOFF_MESSAGES
        return max(2, min(MAX_BUFFER_MESSAGES, limit))

    async def _open_spam_handoff(self, messages: list[PendingMessage]) -> None:
        if not messages:
            return
        sales_service = getattr(self.ap, 'sales_service', None)
        open_handoff = getattr(sales_service, 'open_handoff_from_aggregated_messages', None)
        if not callable(open_handoff):
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Spam handoff triggered but sales_service does not support aggregated handoff')
            return
        await open_handoff(messages=messages, reason='spam_flood')

    async def add_message(
        self,
        bot_uuid: str,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: typing.Union[int, str],
        sender_id: typing.Union[int, str],
        message_event: platform_events.MessageEvent,
        message_chain: platform_message.MessageChain,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        pipeline_uuid: typing.Optional[str] = None,
        routed_by_rule: bool = False,
    ) -> None:
        """Add a message to the aggregation buffer

        If aggregation is disabled for the pipeline, the message is sent
        directly to the query pool. Otherwise, it's buffered and will be
        merged with other messages from the same session.
        """
        enabled, delay = await self._get_aggregation_config(pipeline_uuid)
        pipeline_config = await self._pipeline_config(pipeline_uuid) if enabled else {}
        spam_handoff_limit = self._spam_handoff_limit(pipeline_config)
        session_id = self._get_session_id(bot_uuid, launcher_type, launcher_id)
        source_id = self._message_source_id(message_chain)
        message_fingerprint = self._message_content(message_chain)
        if self._is_recent_duplicate(session_id, source_id, message_fingerprint, time.time()):
            return
        raw_monitoring_message_id = await self._record_raw_monitoring_message(
            bot_uuid,
            launcher_type,
            launcher_id,
            sender_id,
            message_event,
            message_chain,
            pipeline_uuid,
        )

        if not enabled:
            # Aggregation disabled, send directly to query pool
            await self.ap.query_pool.add_query(
                bot_uuid=bot_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
                sender_id=sender_id,
                message_event=message_event,
                message_chain=message_chain,
                adapter=adapter,
                pipeline_uuid=pipeline_uuid,
                routed_by_rule=routed_by_rule,
                raw_monitoring_message_ids=[raw_monitoring_message_id] if raw_monitoring_message_id else None,
            )
            return

        pending_msg = PendingMessage(
            bot_uuid=bot_uuid,
            launcher_type=launcher_type,
            launcher_id=launcher_id,
            sender_id=sender_id,
            message_event=message_event,
            message_chain=message_chain,
            adapter=adapter,
            pipeline_uuid=pipeline_uuid,
            routed_by_rule=routed_by_rule,
            raw_monitoring_message_id=raw_monitoring_message_id,
        )

        force_flush = False
        spam_handoff_messages: list[PendingMessage] | None = None
        async with self.lock:
            if session_id in self.buffers:
                buffer = self.buffers[session_id]
                # Cancel existing timer (just cancel, don't await inside lock)
                if buffer.timer_task and not buffer.timer_task.done():
                    buffer.timer_task.cancel()
                buffer.messages.append(pending_msg)
            else:
                buffer = SessionBuffer(
                    session_id=session_id,
                    messages=[pending_msg],
                )
                self.buffers[session_id] = buffer

            buffer.last_message_time = time.time()

            if spam_handoff_limit is not None and len(buffer.messages) >= spam_handoff_limit:
                if buffer.timer_task and not buffer.timer_task.done():
                    buffer.timer_task.cancel()
                spam_handoff_messages = list(buffer.messages)
                self.buffers.pop(session_id, None)
            # Check if buffer reached max capacity
            elif len(buffer.messages) >= MAX_BUFFER_MESSAGES:
                force_flush = True
            else:
                # Start new timer
                buffer.timer_task = asyncio.create_task(self._delayed_flush(session_id, delay))

        if spam_handoff_messages is not None:
            await self._open_spam_handoff(spam_handoff_messages)
            return

        if force_flush:
            await self._flush_buffer(session_id)

    async def _delayed_flush(self, session_id: str, delay: float) -> None:
        """Wait for delay then flush the buffer"""
        try:
            await asyncio.sleep(delay)
            await self._flush_buffer(session_id)
        except asyncio.CancelledError:
            # Timer was cancelled, new message arrived
            pass

    async def _flush_buffer(self, session_id: str) -> None:
        """Flush the buffer for a session, merging all messages"""
        async with self.lock:
            buffer = self.buffers.pop(session_id, None)

        if buffer is None or not buffer.messages:
            return

        if len(buffer.messages) == 1:
            # Only one message, no need to merge
            msg = buffer.messages[0]
            await self.ap.query_pool.add_query(
                bot_uuid=msg.bot_uuid,
                launcher_type=msg.launcher_type,
                launcher_id=msg.launcher_id,
                sender_id=msg.sender_id,
                message_event=msg.message_event,
                message_chain=msg.message_chain,
                adapter=msg.adapter,
                pipeline_uuid=msg.pipeline_uuid,
                routed_by_rule=msg.routed_by_rule,
                raw_monitoring_message_ids=[msg.raw_monitoring_message_id] if msg.raw_monitoring_message_id else None,
            )
            return

        # Merge multiple messages
        merged_msg = self._merge_messages(buffer.messages)
        raw_monitoring_message_ids = [
            msg.raw_monitoring_message_id for msg in buffer.messages if msg.raw_monitoring_message_id
        ]
        await self.ap.query_pool.add_query(
            bot_uuid=merged_msg.bot_uuid,
            launcher_type=merged_msg.launcher_type,
            launcher_id=merged_msg.launcher_id,
            sender_id=merged_msg.sender_id,
            message_event=merged_msg.message_event,
            message_chain=merged_msg.message_chain,
            adapter=merged_msg.adapter,
            pipeline_uuid=merged_msg.pipeline_uuid,
            routed_by_rule=merged_msg.routed_by_rule,
            raw_monitoring_message_ids=raw_monitoring_message_ids or None,
        )

    def _merge_messages(self, messages: list[PendingMessage]) -> PendingMessage:
        """Merge multiple messages into one

        The merged message uses the first message as base and combines
        all message chains with newline separators.
        The original message_event is kept unmodified to preserve
        message metadata (message_id, etc.) for reply/quote.
        """
        if len(messages) == 1:
            return messages[0]

        base_msg = messages[0]

        # Build merged message chain
        merged_chain = platform_message.MessageChain([])

        for i, msg in enumerate(messages):
            if i > 0:
                # Add newline separator between messages
                merged_chain.append(platform_message.Plain(text='\n'))

            # Copy all components from this message
            for component in msg.message_chain:
                merged_chain.append(component)

        # Keep message_event unmodified (preserves original message_id and
        # metadata for reply/quote), only pass merged chain separately
        return PendingMessage(
            bot_uuid=base_msg.bot_uuid,
            launcher_type=base_msg.launcher_type,
            launcher_id=base_msg.launcher_id,
            sender_id=base_msg.sender_id,
            message_event=base_msg.message_event,
            message_chain=merged_chain,
            adapter=base_msg.adapter,
            pipeline_uuid=base_msg.pipeline_uuid,
            routed_by_rule=any(msg.routed_by_rule for msg in messages),
            raw_monitoring_message_id=base_msg.raw_monitoring_message_id,
        )

    async def flush_all(self) -> None:
        """Flush all pending buffers immediately

        This is useful during shutdown to ensure no messages are lost.
        """
        # Snapshot session IDs and cancel all timers under lock
        async with self.lock:
            session_ids = list(self.buffers.keys())
            for sid in session_ids:
                buffer = self.buffers.get(sid)
                if buffer and buffer.timer_task and not buffer.timer_task.done():
                    buffer.timer_task.cancel()

        # Flush each buffer outside the lock
        for session_id in session_ids:
            await self._flush_buffer(session_id)
