"""
Pipeline full-flow integration tests.

Tests real pipeline stages with fake runner/provider.
Validates message processing through PreProcessor, Processor, and SendResponseBackStage.

Uses RuntimePipeline directly (not PipelineManager) to avoid DB dependency.

Run: uv run pytest tests/integration/pipeline -q --tb=short
"""

from __future__ import annotations

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
import sys

from tests.factories import FakeApp, text_query, mock_platform_adapter
from tests.factories.provider import FakeProvider
from tests.factories.platform import FakePlatform


pytestmark = pytest.mark.integration


# ============== FIXTURE FOR SYS.MODULES ISOLATION ==============

@pytest.fixture(scope='module')
def mock_circular_import_chain():
    """
    Break circular import chain for pipeline modules using isolated_sys_modules.

    Chain: pipeline → core.app → provider.runner → http_controller → groups/plugins

    We mock minimal modules to allow importing RuntimePipeline, StageInstContainer,
    and stage classes without triggering full application initialization.

    After mocking, we import the stage modules so decorators register them.
    """
    from tests.utils.import_isolation import isolated_sys_modules, MockLifecycleControlScope

    # Mock core.entities with LifecycleControlScope enum
    mock_core_entities = Mock()
    mock_core_entities.LifecycleControlScope = MockLifecycleControlScope

    # Mock core.app - Application class is referenced but not instantiated
    mock_core_app = Mock()

    # Mock provider.runner with preregistered_runners list
    mock_runner = Mock()
    mock_runner.preregistered_runners = []  # Will be populated in tests

    # Mock utils.importutil - prevents auto-import of runners
    mock_importutil = Mock()
    mock_importutil.import_modules_in_pkg = lambda pkg: None
    mock_importutil.import_modules_in_pkgs = lambda pkgs: None

    # Modules to clear (force re-import after mocking)
    clear = [
        'langbot.pkg.pipeline.stage',
        'langbot.pkg.pipeline.entities',
        'langbot.pkg.pipeline.pipelinemgr',
        'langbot.pkg.pipeline.preproc.preproc',
        'langbot.pkg.pipeline.process.process',
        'langbot.pkg.pipeline.process.handler',
        'langbot.pkg.pipeline.process.handlers.chat',
        'langbot.pkg.pipeline.process.handlers.command',
        'langbot.pkg.pipeline.respback.respback',
        'langbot.pkg.provider.runner',
    ]

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.entities': mock_core_entities,
            'langbot.pkg.core.app': mock_core_app,
            'langbot.pkg.provider.runner': mock_runner,
            'langbot.pkg.utils.importutil': mock_importutil,
            'langbot.pkg.pipeline.controller': Mock(),
            'langbot.pkg.pipeline.pipelinemgr': Mock(),
        },
        clear=clear,
    ):
        # Import stage modules AFTER clearing so decorators register them
        from importlib import import_module

        # Import stage base first
        import_module('langbot.pkg.pipeline.stage')

        # Import entities
        import_module('langbot.pkg.pipeline.entities')

        # Import specific stages to register them
        import_module('langbot.pkg.pipeline.preproc.preproc')
        import_module('langbot.pkg.pipeline.process.process')
        import_module('langbot.pkg.pipeline.respback.respback')

        # Import pipelinemgr for RuntimePipeline
        import_module('langbot.pkg.pipeline.pipelinemgr')

        yield


# ============== FAKE RUNNER ==============

class FakeRunner:
    """Minimal fake runner class for pipeline integration tests.

    Note: preregistered_runners expects a CLASS, not an instance.
    The handler calls runner_cls(self.ap, query.pipeline_config) to instantiate.
    """

    name = 'local-agent'

    def __init__(self, app=None, config=None):
        self.app = app
        self.config = config or {}
        self._provider = FakeProvider()
        # Instance-level configuration set via class attribute
        self._response_text = "fake response"
        self._raise_error = None

    @classmethod
    def returns(cls, text: str):
        """Create a runner class configured to return specific text."""
        # We create a subclass with configured response
        class ConfiguredRunner(cls):
            name = cls.name
            _response_text = text
            _raise_error = None

            def __init__(self, app=None, config=None):
                super().__init__(app, config)
                self._response_text = text
        return ConfiguredRunner

    @classmethod
    def raises(cls, error: Exception):
        """Create a runner class configured to raise an error."""
        class ConfiguredRunner(cls):
            name = cls.name
            _response_text = None
            _raise_error = error

            def __init__(self, app=None, config=None):
                super().__init__(app, config)
                self._raise_error = error
        return ConfiguredRunner

    async def run(self, query):
        """Run the fake provider and yield messages."""
        from langbot_plugin.api.entities.builtin.provider.message import Message

        # Use the configured response/error
        if self._raise_error:
            raise self._raise_error

        # Yield a simple message
        yield Message(role='assistant', content=self._response_text)


# ============== PIPELINE APP FIXTURE ==============

@pytest.fixture
def pipeline_app():
    """
    Create FakeApp with all dependencies required by pipeline stages.

    PreProcessor needs: sess_mgr, model_mgr, tool_mgr, plugin_connector
    Processor needs: instance_config, plugin_connector
    SendResponseBackStage needs: logger
    ChatMessageHandler needs: telemetry, survey
    """
    app = FakeApp()

    # Session/conversation mocks for PreProcessor
    mock_session = Mock()
    mock_session.launcher_type = Mock()
    mock_session.launcher_type.value = 'person'
    mock_session.launcher_id = 12345
    mock_session.sender_id = 12345
    mock_session.use_prompt_name = 'default'
    mock_session.using_conversation = None

    # Create a simple class to mimic Prompt behavior
    class MockPrompt:
        def __init__(self, name, messages):
            self.name = name
            self.messages = messages
        def copy(self):
            return MockPrompt(self.name, list(self.messages))

    # Create real lists for messages
    prompt_messages_list = []
    messages_list = []

    mock_prompt = MockPrompt('default', prompt_messages_list)
    mock_conversation = Mock()
    mock_conversation.prompt = mock_prompt
    mock_conversation.messages = messages_list
    mock_conversation.uuid = 'test-conversation-uuid'
    mock_conversation.update_time = None
    mock_conversation.create_time = None

    app.sess_mgr.get_session = AsyncMock(return_value=mock_session)
    app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

    # Model mock for PreProcessor
    mock_model = Mock()
    mock_model.model_entity = Mock()
    mock_model.model_entity.uuid = 'test-model-uuid'
    mock_model.model_entity.name = 'test-model'
    mock_model.model_entity.abilities = ['func_call', 'vision']
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=mock_model)

    # Tool manager mock
    app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

    # Telemetry mock (required by ChatMessageHandler)
    app.telemetry = Mock()
    app.telemetry.start_send_task = AsyncMock()

    # Survey mock
    app.survey = None

    return app


@pytest.fixture
def fake_platform_adapter():
    """Create a fake platform adapter for outbound capture."""
    platform = FakePlatform(stream_output_supported=False)
    adapter = mock_platform_adapter(platform)
    return adapter, platform


@pytest.fixture
def set_fake_runner():
    """Factory fixture to set a fake runner CLASS in preregistered_runners."""
    def _set_runner(runner_cls):
        # preregistered_runners expects a list of runner classes
        sys.modules['langbot.pkg.provider.runner'].preregistered_runners = [runner_cls]
    return _set_runner


# ============== PIPELINE CONFIGURATION ==============

def create_minimal_pipeline_config():
    """Create minimal pipeline configuration for tests."""
    return {
        'ai': {
            'runner': {'runner': 'local-agent', 'expire-time': None},
            'local-agent': {
                'model': {'primary': 'test-model-uuid', 'fallbacks': []},
                'prompt': 'default',
                'knowledge-bases': [],
            },
        },
        'output': {
            'force-delay': {'min': 0.0, 'max': 0.0},
            'misc': {
                'at-sender': False,
                'quote-origin': False,
                'exception-handling': 'show-hint',
                'failure-hint': 'Request failed.',
            },
        },
        'trigger': {
            'misc': {'combine-quote-message': False},
        },
    }


# ============== HELPER TO PROCESS COROUTINE/GENERATOR ==============

async def collect_processor_results(processor, query, stage_name):
    """
    Helper to handle the coroutine -> async_generator pattern.

    Processor.process() returns a coroutine that yields an async_generator.
    This helper handles both cases like RuntimePipeline does.
    """
    result = processor.process(query, stage_name)

    # Handle coroutine (await it to get async_generator)
    if asyncio.iscoroutine(result):
        result = await result

    # Now iterate over async_generator
    results = []
    async for item in result:
        results.append(item)

    return results


# ============== TESTS ==============

@pytest.mark.usefixtures('mock_circular_import_chain')
class TestPipelineStageChainReal:
    """Tests for real pipeline stage chain."""

    @pytest.mark.asyncio
    async def test_import_pipeline_modules(self):
        """Verify we can import real pipeline modules."""
        from langbot.pkg.pipeline import stage, entities
        from langbot.pkg.pipeline import pipelinemgr

        assert hasattr(stage, 'PipelineStage')
        assert hasattr(stage, 'preregistered_stages')
        assert hasattr(entities, 'ResultType')
        assert hasattr(entities, 'StageProcessResult')
        assert hasattr(pipelinemgr, 'RuntimePipeline')
        assert hasattr(pipelinemgr, 'StageInstContainer')

    @pytest.mark.asyncio
    async def test_stage_preregistration(self):
        """Verify stages are preregistered after fixture imports them."""
        from langbot.pkg.pipeline import stage

        # Check that our target stages are registered
        assert 'PreProcessor' in stage.preregistered_stages
        assert 'MessageProcessor' in stage.preregistered_stages
        assert 'SendResponseBackStage' in stage.preregistered_stages


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestPreProcessorStage:
    """Tests for PreProcessor stage alone."""

    @pytest.mark.asyncio
    async def test_preproc_continues_on_valid_query(self, pipeline_app, fake_platform_adapter):
        """PreProcessor should return CONTINUE for valid text query."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.preproc import preproc

        adapter, platform = fake_platform_adapter

        # Create query with adapter
        query = text_query("hello")
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()

        # Mock plugin_connector for PromptPreProcessing event
        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.default_prompt = []  # Real list
        mock_event_ctx.event.prompt = []  # Real list
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create PreProcessor stage
        preproc_stage = preproc.PreProcessor(pipeline_app)

        result = await preproc_stage.process(query, 'PreProcessor')

        assert result.result_type == entities.ResultType.CONTINUE
        assert result.new_query.session is not None
        assert result.new_query.user_message is not None

    @pytest.mark.asyncio
    async def test_preproc_sets_user_message(self, pipeline_app, fake_platform_adapter):
        """PreProcessor should set user_message from message_chain."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.preproc import preproc

        adapter, platform = fake_platform_adapter

        query = text_query("test message content")
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()

        # Mock plugin_connector for PromptPreProcessing event
        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.default_prompt = []
        mock_event_ctx.event.prompt = []
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        preproc_stage = preproc.PreProcessor(pipeline_app)

        result = await preproc_stage.process(query, 'PreProcessor')

        assert result.result_type == entities.ResultType.CONTINUE
        # Check user_message content
        assert result.new_query.user_message is not None
        assert result.new_query.user_message.role == 'user'


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestProcessorStage:
    """Tests for MessageProcessor stage."""

    @pytest.mark.asyncio
    async def test_processor_calls_chat_handler(self, pipeline_app, fake_platform_adapter, set_fake_runner):
        """Processor should route to ChatMessageHandler for non-command messages."""
        adapter, platform = fake_platform_adapter

        # Set fake runner that returns pong
        fake_runner = FakeRunner().returns("LANGBOT_FAKE_PONG")
        set_fake_runner(fake_runner)

        # Create query
        query = text_query("hello")
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()
        query.resp_messages = []

        # Mock plugin_connector to not prevent default
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.user_message_alter = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process
        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        # Collect results using helper
        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) >= 1
        # Check that resp_messages was populated
        assert len(query.resp_messages) >= 1

    @pytest.mark.asyncio
    async def test_processor_prevent_default_without_reply_interrupts(self, pipeline_app, fake_platform_adapter):
        """Processor should INTERRUPT when plugin prevents default without reply."""
        from langbot.pkg.pipeline import entities

        adapter, platform = fake_platform_adapter

        # Create query
        query = text_query("hello")
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()

        # Mock plugin_connector to prevent default without reply
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=True)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.reply_message_chain = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process
        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT

    @pytest.mark.asyncio
    async def test_processor_prevent_default_with_reply_continues(self, pipeline_app, fake_platform_adapter):
        """Processor should CONTINUE when plugin prevents default with reply."""
        from langbot.pkg.pipeline import entities
        from tests.factories.message import text_chain

        adapter, platform = fake_platform_adapter

        # Create query
        query = text_query("hello")
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()
        query.resp_messages = []

        # Create reply chain
        reply_chain = text_chain("plugin response")

        # Mock plugin_connector to prevent default with reply
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=True)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.reply_message_chain = reply_chain
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process
        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        assert len(query.resp_messages) == 1
        assert query.resp_messages[0] == reply_chain


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestRunnerExceptionFlow:
    """Tests for runner exception handling."""

    @pytest.mark.asyncio
    async def test_runner_exception_yields_interrupt(self, pipeline_app, fake_platform_adapter, set_fake_runner):
        """Runner exception should yield INTERRUPT with error notices."""
        from langbot.pkg.pipeline import entities

        adapter, platform = fake_platform_adapter

        # Set fake runner that raises exception
        fake_runner = FakeRunner().raises(ValueError("API Error: rate limit exceeded"))
        set_fake_runner(fake_runner)

        # Create query with exception handling config
        config = create_minimal_pipeline_config()
        config['output']['misc']['exception-handling'] = 'show-hint'
        config['output']['misc']['failure-hint'] = 'Request failed.'

        query = text_query("hello")
        query.adapter = adapter
        query.pipeline_config = config

        # Mock plugin_connector to not prevent default
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.user_message_alter = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process
        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT
        assert results[0].user_notice == 'Request failed.'
        assert results[0].error_notice is not None

    @pytest.mark.asyncio
    async def test_runner_exception_show_error_mode(self, pipeline_app, fake_platform_adapter, set_fake_runner):
        """show-error mode should show actual exception message."""
        from langbot.pkg.pipeline import entities

        adapter, platform = fake_platform_adapter

        # Set fake runner that raises specific exception
        fake_runner = FakeRunner().raises(RuntimeError("Custom runtime error"))
        set_fake_runner(fake_runner)

        # Create query with show-error mode
        config = create_minimal_pipeline_config()
        config['output']['misc']['exception-handling'] = 'show-error'

        query = text_query("hello")
        query.adapter = adapter
        query.pipeline_config = config

        # Mock plugin_connector to not prevent default
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.user_message_alter = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process
        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT
        assert 'Custom runtime error' in results[0].user_notice

    @pytest.mark.asyncio
    async def test_runner_exception_hide_mode(self, pipeline_app, fake_platform_adapter, set_fake_runner):
        """hide mode should not show user notice."""
        from langbot.pkg.pipeline import entities

        adapter, platform = fake_platform_adapter

        # Set fake runner that raises exception
        fake_runner = FakeRunner().raises(Exception("Hidden error"))
        set_fake_runner(fake_runner)

        # Create query with hide mode
        config = create_minimal_pipeline_config()
        config['output']['misc']['exception-handling'] = 'hide'

        query = text_query("hello")
        query.adapter = adapter
        query.pipeline_config = config

        # Mock plugin_connector to not prevent default
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.user_message_alter = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process
        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT
        assert results[0].user_notice is None


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestSendResponseBackStage:
    """Tests for SendResponseBackStage."""

    @pytest.mark.asyncio
    async def test_send_response_calls_adapter(self, pipeline_app, fake_platform_adapter):
        """SendResponseBackStage should call adapter.reply_message."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter

        # Create query with response message
        query = text_query("hello")
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()

        # Add response message
        query.resp_messages = [Message(role='assistant', content='test response')]
        query.resp_message_chain = [text_chain('test response')]

        # Create SendResponseBackStage
        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE

        # Check that adapter was called
        outbound = platform.get_outbound_messages()
        assert len(outbound) == 1
        assert outbound[0]['type'] == 'reply'

    @pytest.mark.asyncio
    async def test_send_response_appends_workflow_image_for_matched_intent(self, pipeline_app, fake_platform_adapter):
        """Configured workflow image nodes should be appended before replying."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter

        config = create_minimal_pipeline_config()
        config['workflow'] = {
            'nodes': [
                {
                    'id': 'image-price',
                    'type': 'image',
                    'config': {
                        'file_key': 'price-sheet.png',
                        'caption': 'Price sheet',
                        'trigger_intents': ['price'],
                    },
                },
            ],
        }
        query = text_query("price?")
        query.adapter = adapter
        query.pipeline_config = config
        query.variables['sales_intent'] = {'intent': 'price', 'confidence': 0.91}
        query.resp_messages = [Message(role='assistant', content='Here is the price.')]
        query.resp_message_chain = [text_chain('Here is the price.')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        assert len(outbound) == 1
        components = outbound[0]['message']
        assert [component.type for component in components] == ['Plain', 'Plain', 'Image']
        assert components[1].text == 'Price sheet'
        assert str(components[2].path) == 'price-sheet.png'

    @pytest.mark.asyncio
    async def test_send_response_skips_link_bound_course_sales_image_without_signup_link(
        self, pipeline_app, fake_platform_adapter
    ):
        """Course sales images bound to signup links should not appear in ordinary replies."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter
        config = create_minimal_pipeline_config()
        config['workflow'] = {
            'metadata': {'scenario': 'course_sales_yuanfudao_phonics'},
            'nodes': [
                {
                    'id': 'image_gift_poster',
                    'type': 'image',
                    'config': {
                        'file_key': 'course-sales/phonics/gift_poster.jpeg',
                        'trigger_intents': ['course_intro'],
                        'requires_course_sales_signup_link': True,
                    },
                },
            ],
        }
        query = text_query('还有什么资料')
        query.adapter = adapter
        query.pipeline_config = config
        query.variables['workflow_intent'] = {'intent': 'course_intro', 'confidence': 0.91}
        query.resp_messages = [Message(role='assistant', content='咱们有发音练习纸和拼读卡这些资料。')]
        query.resp_message_chain = [text_chain('咱们有发音练习纸和拼读卡这些资料。')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[0]['message']
        assert [component.type for component in components] == ['Plain']

    @pytest.mark.asyncio
    async def test_send_response_appends_link_bound_course_sales_image_after_signup_link(
        self, pipeline_app, fake_platform_adapter
    ):
        """Course sales signup-link images should appear after the signup link is sent."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter
        signup_link = 'https://m.yuanfudao.com/primary/templates/package?test=gift'
        config = create_minimal_pipeline_config()
        config['workflow'] = {
            'metadata': {'scenario': 'course_sales_yuanfudao_phonics'},
            'nodes': [
                {
                    'id': 'image_gift_poster',
                    'type': 'image',
                    'config': {
                        'file_key': 'course-sales/phonics/gift_poster.jpeg',
                        'trigger_intents': ['purchase'],
                        'requires_course_sales_signup_link': True,
                    },
                },
            ],
        }
        query = text_query('我要报名')
        query.adapter = adapter
        query.pipeline_config = config
        query.variables['workflow_intent'] = {'intent': 'purchase', 'confidence': 0.91, 'link_url': signup_link}
        query.variables['course_sales_radar_link'] = signup_link
        query.resp_messages = [Message(role='assistant', content='可以，我现在把链接发给您。')]
        query.resp_message_chain = [text_chain('可以，我现在把链接发给您。')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[0]['message']
        assert [component.type for component in components] == ['Plain', 'Image']
        assert str(components[1].path) == 'course-sales/phonics/gift_poster.jpeg'
        link_components = outbound[1]['message']
        assert [component.type for component in link_components] == ['Plain']
        assert signup_link in link_components[0].text

    @pytest.mark.asyncio
    async def test_send_response_appends_task_assistant_tts_for_voice_query(self, pipeline_app, fake_platform_adapter):
        """Task assistant should append synthesized voice when the user sent voice."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, voice_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter
        pipeline_app.task_assistant_service = Mock()
        pipeline_app.task_assistant_service.synthesize_reply_voice = AsyncMock(
            return_value='data:audio/mpeg;base64,ZmFrZQ=='
        )

        query = voice_query('https://example.com/audio.mp3')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()
        query.pipeline_config['workflow'] = {
            'metadata': {'scenario': 'task_assistant_ant_af'},
            'voice': {'enabled': True},
        }
        query.variables['task_assistant_voice_reply'] = True
        query.resp_messages = [Message(role='assistant', content='下一步点击实名认证。')]
        query.resp_message_chain = [text_chain('下一步点击实名认证。')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        assert len(outbound) == 1
        components = outbound[0]['message']
        assert [component.type for component in components] == ['Voice']
        assert components[0].base64 == 'data:audio/mpeg;base64,ZmFrZQ=='
        assert components[0].length and components[0].length > 0
        pipeline_app.task_assistant_service.synthesize_reply_voice.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_response_appends_course_sales_signup_link_for_purchase_intent(
        self, pipeline_app, fake_platform_adapter
    ):
        """Course sales purchase replies should send the signup link as a separate outgoing message."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter
        signup_link = 'https://m.yuanfudao.com/primary/templates/package?test=1'
        query = text_query('我要报名')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()
        query.variables['workflow_intent'] = {
            'intent': 'purchase',
            'confidence': 0.98,
            'link_url': signup_link,
        }
        query.variables['course_sales_radar_link'] = signup_link
        query.resp_messages = [Message(role='assistant', content='可以，我现在把链接发给您。')]
        query.resp_message_chain = [text_chain('可以，我现在把链接发给您。')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[1]['message']
        text = ''.join(component.text for component in components if component.type == 'Plain')
        assert signup_link in text
        assert text.count(signup_link) == 1
        assert '猿辅导英语自然拼读9元体验课点这里' in text

    @pytest.mark.asyncio
    async def test_send_response_replaces_course_sales_signup_link_placeholder(
        self, pipeline_app, fake_platform_adapter
    ):
        """Course sales replies must not send the signup link placeholder to users."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter
        signup_link = 'https://m.yuanfudao.com/primary/templates/package?test=placeholder'
        query = text_query('好的')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()
        query.variables['workflow_intent'] = {
            'intent': 'course_content',
            'confidence': 0.72,
        }
        query.variables['course_sales_radar_link'] = signup_link
        query.resp_messages = [Message(role='assistant', content='太棒了，点击这里报名：[报名链接XXXXXXX]')]
        query.resp_message_chain = [text_chain('太棒了，点击这里报名：[报名链接XXXXXXX]')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[0]['message']
        text = ''.join(component.text for component in components if component.type == 'Plain')
        assert signup_link in text
        assert '[报名链接' not in text

    @pytest.mark.asyncio
    async def test_send_response_appends_signup_link_when_schedule_reply_promises_link(
        self, pipeline_app, fake_platform_adapter
    ):
        """If the assistant promises a signup page link, send it as a separate message."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter
        signup_link = 'https://m.yuanfudao.com/primary/templates/package?test=schedule'
        query = text_query('具体的课表发来看看')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()
        query.variables['workflow_intent'] = {
            'intent': 'course_schedule',
            'confidence': 0.88,
            'link_url': signup_link,
        }
        query.variables['course_sales_radar_link'] = signup_link
        query.resp_messages = [Message(role='assistant', content='我这就把详细课表发给您看看。')]
        query.resp_message_chain = [text_chain('我这就把详细课表发给您看看。')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[1]['message']
        text = ''.join(component.text for component in components if component.type == 'Plain')
        assert signup_link in text
        assert text.count(signup_link) == 1

    @pytest.mark.asyncio
    async def test_send_response_wraps_signup_link_with_radar_tracking_when_available(
        self, pipeline_app, fake_platform_adapter
    ):
        """Direct signup links should use the radar tracking URL when the sales service is available."""
        from types import SimpleNamespace

        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter
        signup_link = 'https://m.yuanfudao.com/primary/templates/package?test=tracking'
        tracking_link = 'http://127.0.0.1:5300/api/v1/sales/radar/click/test-token'
        pipeline_app.sales_service = SimpleNamespace(build_radar_tracking_url=Mock(return_value=tracking_link))
        query = text_query('我要报名')
        query.adapter = adapter
        query.bot_uuid = 'bot-uuid'
        query.pipeline_uuid = 'pipeline-uuid'
        query.launcher_id = 'ou_customer'
        query.pipeline_config = create_minimal_pipeline_config()
        query.variables['workflow_intent'] = {
            'intent': 'purchase',
            'confidence': 0.98,
            'link_url': signup_link,
        }
        query.variables['course_sales_radar_link'] = signup_link
        query.resp_messages = [Message(role='assistant', content='可以，我现在把链接发给您。')]
        query.resp_message_chain = [text_chain('可以，我现在把链接发给您。')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[1]['message']
        text = ''.join(component.text for component in components if component.type == 'Plain')
        assert tracking_link in text
        assert signup_link not in text
        pipeline_app.sales_service.build_radar_tracking_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_replaces_model_signup_link_with_radar_tracking(
        self, pipeline_app, fake_platform_adapter
    ):
        """Model-authored signup URLs should be replaced with radar tracking URLs."""
        from types import SimpleNamespace

        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter
        signup_link = 'https://m.yuanfudao.com/primary/templates/package?pageId=6641&solutionId=27246'
        tracking_link = 'http://127.0.0.1:5300/api/v1/sales/radar/click/model-token'
        pipeline_app.sales_service = SimpleNamespace(build_radar_tracking_url=Mock(return_value=tracking_link))
        query = text_query('给我个链接')
        query.adapter = adapter
        query.bot_uuid = 'bot-uuid'
        query.pipeline_uuid = 'pipeline-uuid'
        query.launcher_id = 'ou_customer'
        query.pipeline_config = create_minimal_pipeline_config()
        query.variables['workflow_intent'] = {
            'intent': 'purchase',
            'confidence': 0.98,
            'link_url': signup_link,
        }
        query.variables['course_sales_radar_link'] = signup_link
        reply = f'这就发给您：\n{signup_link}\n\n点开链接选好孩子的年级，支付9元报名成功后截图发我。'
        query.resp_messages = [Message(role='assistant', content=reply)]
        query.resp_message_chain = [text_chain(reply)]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[0]['message']
        text = ''.join(component.text for component in components if component.type == 'Plain')
        assert tracking_link in text
        assert signup_link not in text
        pipeline_app.sales_service.build_radar_tracking_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_keeps_signup_link_when_purchase_voice_reply_uses_tts(
        self, pipeline_app, fake_platform_adapter
    ):
        """Voice replies still need a clickable signup link for purchase actions."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, voice_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter
        pipeline_app.task_assistant_service = Mock()
        pipeline_app.task_assistant_service.synthesize_reply_voice = AsyncMock(
            return_value='data:audio/mpeg;base64,ZmFrZQ=='
        )
        signup_link = 'https://m.yuanfudao.com/primary/templates/package?test=voice'
        query = voice_query('https://example.com/audio.mp3')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()
        query.variables['task_assistant_voice_reply'] = True
        query.variables['workflow_intent'] = {
            'intent': 'purchase',
            'confidence': 0.98,
            'link_url': signup_link,
        }
        query.resp_messages = [Message(role='assistant', content='可以，我现在把链接发给您。')]
        query.resp_message_chain = [text_chain('可以，我现在把链接发给您。')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[0]['message']
        assert [component.type for component in components] == ['Voice']
        link_components = outbound[1]['message']
        assert [component.type for component in link_components] == ['Plain']
        assert link_components[0].text.count(signup_link) == 1

    @pytest.mark.asyncio
    async def test_send_response_sends_one_task_assistant_image_without_caption_tail(self, pipeline_app, fake_platform_adapter):
        """Task assistant sends only the current step image and no caption tail."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message
        from types import SimpleNamespace

        adapter, platform = fake_platform_adapter
        storage_provider = Mock()
        storage_provider.load = AsyncMock(return_value=b'fake-png')
        pipeline_app.storage_mgr = SimpleNamespace(storage_provider=storage_provider)
        config = create_minimal_pipeline_config()
        config['workflow'] = {
            'metadata': {'scenario': 'task_assistant_ant_af'},
            'nodes': [
                {
                    'id': 'image_download_qr',
                    'type': 'image',
                    'config': {
                        'file_key': 'task-assistant/ant-af/af_step_01.png',
                        'step_id': 'download_qr',
                        'caption': '支付宝扫码下载蚂蚁阿福 App',
                        'trigger_intents': ['task_overview'],
                    },
                },
                {
                    'id': 'image_alipay_login',
                    'type': 'image',
                    'config': {
                        'file_key': 'task-assistant/ant-af/af_step_03.png',
                        'step_id': 'alipay_login',
                        'caption': '打开 App 后使用支付宝一键登录',
                        'trigger_intents': ['task_overview'],
                    },
                },
            ],
        }
        query = text_query('怎么完成任务')
        query.adapter = adapter
        query.pipeline_config = config
        query.variables['workflow_intent'] = {'intent': 'task_overview', 'confidence': 0.91, 'step_ids': ['download_qr']}
        query.resp_messages = [Message(role='assistant', content='我带你一步一步做。')]
        query.resp_message_chain = [text_chain('我带你一步一步做。')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[0]['message']
        assert [component.type for component in components] == ['Plain', 'Image']
        assert components[0].text == '我带你一步一步做。'
        assert components[1].base64.startswith('data:image/png;base64,')
        storage_provider.load.assert_awaited_once_with('task-assistant/ant-af/af_step_01.png')

    @pytest.mark.asyncio
    async def test_send_response_template_mode_uses_template_images_without_mutating_saved_workflow(
        self, pipeline_app, fake_platform_adapter
    ):
        """Template mode should render images from template config, not the saved workflow graph."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message
        from types import SimpleNamespace

        adapter, platform = fake_platform_adapter
        storage_provider = Mock()
        storage_provider.load = AsyncMock(return_value=b'uploaded-template-png')
        pipeline_app.storage_mgr = SimpleNamespace(storage_provider=storage_provider)
        active_workflow = {
            'metadata': {'scenario': 'task_assistant_ant_af'},
            'nodes': [
                {
                    'id': 'image_download_qr',
                    'type': 'image',
                    'config': {
                        'file_key': 'uploads/template-step.png',
                        'step_id': 'download_qr',
                        'trigger_intents': ['task_overview'],
                    },
                },
            ],
        }
        pipeline_app.task_assistant_service = Mock()
        pipeline_app.task_assistant_service.active_workflow_from_config = Mock(return_value=active_workflow)
        pipeline_app.task_assistant_service.synthesize_reply_voice = AsyncMock(return_value=None)

        config = create_minimal_pipeline_config()
        config['config_mode'] = 'template'
        config['workflow'] = {
            'metadata': {'scenario': 'custom-workflow'},
            'nodes': [],
            'edges': [],
        }
        config['template_config'] = {
            'image_text_bindings': [
                {
                    'step_id': 'download_qr',
                    'file_key': 'uploads/template-step.png',
                    'trigger_intents': ['task_overview'],
                    'enabled': True,
                },
            ],
        }
        query = text_query('鎬庝箞瀹屾垚浠诲姟')
        query.adapter = adapter
        query.pipeline_config = config
        query.variables['workflow_intent'] = {'intent': 'task_overview', 'confidence': 0.91, 'step_ids': ['download_qr']}
        query.resp_messages = [Message(role='assistant', content='ok')]
        query.resp_message_chain = [text_chain('ok')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        pipeline_app.task_assistant_service.active_workflow_from_config.assert_called_with(config)
        assert config['workflow']['nodes'] == []
        outbound = platform.get_outbound_messages()
        components = outbound[0]['message']
        assert [component.type for component in components] == ['Plain', 'Image']
        assert components[1].base64.startswith('data:image/png;base64,')
        storage_provider.load.assert_awaited_once_with('uploads/template-step.png')

    @pytest.mark.asyncio
    async def test_send_response_sends_no_task_assistant_image_when_max_images_is_zero(
        self, pipeline_app, fake_platform_adapter
    ):
        """Unknown screenshot context should not fall back to the first task image."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain, text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message
        from types import SimpleNamespace

        adapter, platform = fake_platform_adapter
        storage_provider = Mock()
        storage_provider.load = AsyncMock(return_value=b'fake-png')
        pipeline_app.storage_mgr = SimpleNamespace(storage_provider=storage_provider)
        config = create_minimal_pipeline_config()
        config['workflow'] = {
            'metadata': {'scenario': 'task_assistant_ant_af'},
            'nodes': [
                {
                    'id': 'image_download_qr',
                    'type': 'image',
                    'config': {
                        'file_key': 'task-assistant/ant-af/af_step_01.png',
                        'step_id': 'download_qr',
                        'trigger_intents': ['screenshot_help'],
                    },
                },
            ],
        }
        query = text_query('我发了截图但不知道在哪一步')
        query.adapter = adapter
        query.pipeline_config = config
        query.variables['workflow_intent'] = {
            'intent': 'screenshot_help',
            'confidence': 0.91,
            'max_images': 0,
        }
        query.resp_messages = [Message(role='assistant', content='我先看下你截图里的页面。')]
        query.resp_message_chain = [text_chain('我先看下你截图里的页面。')]

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type == entities.ResultType.CONTINUE
        outbound = platform.get_outbound_messages()
        components = outbound[0]['message']
        assert [component.type for component in components] == ['Plain']
        storage_provider.load.assert_not_awaited()


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestStageChainIntegration:
    """Tests for full stage chain (PreProcessor -> Processor -> SendResponseBackStage)."""

    @pytest.mark.asyncio
    async def test_full_chain_text_message_flow(self, pipeline_app, fake_platform_adapter, set_fake_runner):
        """
        Full chain: text message -> PreProcessor -> Processor -> SendResponseBackStage.

        Validates:
        - PreProcessor sets up session, user_message
        - Processor calls runner and populates resp_messages
        - SendResponseBackStage calls adapter.reply_message
        """
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.preproc import preproc
        from langbot.pkg.pipeline.process import process
        from langbot.pkg.pipeline.respback import respback

        adapter, platform = fake_platform_adapter

        # Set fake runner
        fake_runner = FakeRunner().returns("LANGBOT_FAKE_PONG")
        set_fake_runner(fake_runner)

        # Create query
        config = create_minimal_pipeline_config()
        query = text_query("ping")
        query.adapter = adapter
        query.pipeline_config = config
        query.resp_messages = []
        query.resp_message_chain = []

        # Mock plugin_connector for PreProcessor and Processor events
        mock_event_ctx_preproc = Mock()
        mock_event_ctx_preproc.event = Mock()
        mock_event_ctx_preproc.event.default_prompt = []
        mock_event_ctx_preproc.event.prompt = []

        mock_event_ctx_processor = Mock()
        mock_event_ctx_processor.is_prevented_default = Mock(return_value=False)
        mock_event_ctx_processor.event = Mock()
        mock_event_ctx_processor.event.user_message_alter = None

        pipeline_app.plugin_connector.emit_event = AsyncMock()
        pipeline_app.plugin_connector.emit_event.side_effect = [
            mock_event_ctx_preproc,   # PreProcessor PromptPreProcessing
            mock_event_ctx_processor,  # Processor NormalMessageReceived
        ]

        # Create stages
        preproc_stage = preproc.PreProcessor(pipeline_app)
        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(config)
        respback_stage = respback.SendResponseBackStage(pipeline_app)

        # Run PreProcessor
        result1 = await preproc_stage.process(query, 'PreProcessor')
        assert result1.result_type == entities.ResultType.CONTINUE
        query = result1.new_query

        # Run Processor
        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')
        assert len(results) >= 1

        # Build resp_message_chain from resp_messages
        from tests.factories.message import text_chain
        for resp_msg in query.resp_messages:
            if resp_msg.content:
                query.resp_message_chain.append(text_chain(resp_msg.content))

        # Run SendResponseBackStage
        result3 = await respback_stage.process(query, 'SendResponseBackStage')
        assert result3.result_type == entities.ResultType.CONTINUE

        # Verify adapter was called
        outbound = platform.get_outbound_messages()
        assert len(outbound) >= 1

    @pytest.mark.asyncio
    async def test_chain_stops_on_interrupt(self, pipeline_app, fake_platform_adapter):
        """
        Chain should stop when a stage returns INTERRUPT.

        PreProcessor returns CONTINUE, Processor returns INTERRUPT (prevent_default).
        """
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.preproc import preproc
        from langbot.pkg.pipeline.process import process

        adapter, platform = fake_platform_adapter

        # Create query
        query = text_query("hello")
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()

        # Mock plugin_connector - PreProcessor continues, Processor interrupts
        mock_event_ctx_preproc = Mock()
        mock_event_ctx_preproc.event = Mock()
        mock_event_ctx_preproc.event.default_prompt = []
        mock_event_ctx_preproc.event.prompt = []

        mock_event_ctx_processor = Mock()
        mock_event_ctx_processor.is_prevented_default = Mock(return_value=True)
        mock_event_ctx_processor.event = Mock()
        mock_event_ctx_processor.event.reply_message_chain = None

        pipeline_app.plugin_connector.emit_event = AsyncMock()
        pipeline_app.plugin_connector.emit_event.side_effect = [
            mock_event_ctx_preproc,   # PreProcessor PromptPreProcessing
            mock_event_ctx_processor,  # Processor NormalMessageReceived
        ]

        # Create stages
        preproc_stage = preproc.PreProcessor(pipeline_app)
        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        # Run PreProcessor
        result1 = await preproc_stage.process(query, 'PreProcessor')
        assert result1.result_type == entities.ResultType.CONTINUE
        query = result1.new_query

        # Run Processor - should INTERRUPT
        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT

        # Chain stops here - no resp_messages
        assert len(query.resp_messages) == 0
