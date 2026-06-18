import sys
import types
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.modules.setdefault('dashscope', types.ModuleType('dashscope'))

from langbot.pkg.api.http.service.task_assistant import (  # noqa: E402
    COURSE_SALES_AFTER_LINK_OPEN_MESSAGE,
    COURSE_SALES_EVENING_FOLLOWUP_MESSAGE,
    COURSE_SALES_FIVE_MIN_FOLLOWUP_MESSAGE,
    COURSE_SALES_ONE_HOUR_FOLLOWUP_MESSAGE,
    COURSE_RESOURCE_CARD_LINK,
    COURSE_OPENING_MESSAGE,
    COURSE_SALES_SCENARIO,
    COURSE_SALES_RADAR_LINK,
    COURSE_SALES_TEMPLATE_PIPELINE_UUID,
    COURSE_SALES_TTS_VOICE_TYPE,
    COURSE_SALES_WORKFLOW_PIPELINE_UUID,
    TASK_ASSISTANT_PIPELINE_UUID,
    TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID,
    TASK_ASSISTANT_TTS_VOICE_TYPE,
    TaskAssistantService,
    YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID,
    YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID,
)
from langbot.pkg.entity.persistence import model as persistence_model  # noqa: E402
from langbot_plugin.api.entities.builtin.platform import message as platform_message  # noqa: E402
from langbot_plugin.api.entities.builtin.provider import message as provider_message  # noqa: E402
from tests.factories.message import image_chain, text_chain, voice_query  # noqa: E402


class _FirstResult:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value

    def all(self):
        return [self.value] if self.value is not None else []


class _EmptyListResult:
    def first(self):
        return None

    def all(self):
        return []


class _ListResult:
    def __init__(self, values):
        self.values = values

    def first(self):
        return self.values[0] if self.values else None

    def all(self):
        return self.values


def _query(message_chain, text='', session_id='user-1'):
    launcher_type = SimpleNamespace(value='person')
    return SimpleNamespace(
        variables={'user_message_text': text},
        pipeline_config={
            'workflow': {
                'metadata': {'scenario': 'task_assistant_ant_af'},
            },
        },
        message_chain=message_chain,
        user_message=provider_message.Message(role='user', content=[provider_message.ContentElement.from_text(text)]),
        prompt=SimpleNamespace(messages=[]),
        session=SimpleNamespace(launcher_type=launcher_type, launcher_id=session_id),
        launcher_type=launcher_type,
        launcher_id=session_id,
    )


@pytest.mark.asyncio
async def test_prepare_query_sets_verify_intent_and_injects_prompt():
    service = TaskAssistantService(SimpleNamespace())
    query = _query(text_chain('我卡在实名认证这一步了'), '我卡在实名认证这一步了')

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert query.variables['workflow_intent']['intent'] == 'real_person_verify'
    assert query.prompt.messages[0].role == 'system'
    assert '蚂蚁阿福' in query.prompt.messages[0].content
    assert '支付宝一键导入身份信息' in query.prompt.messages[0].content


@pytest.mark.asyncio
async def test_prepare_query_resets_task_assistant_progress_on_new_command():
    sales_service = SimpleNamespace(reset_sales_session_context=AsyncMock(return_value={'reset': True}))
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service))
    service._session_progress['person_user-1'] = {'current_step_id': 'verify_identity'}
    query = _query(text_chain('/new'), '/new')

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert result['interrupted'] is True
    assert '已重置' in result['notice']
    assert 'person_user-1' not in service._session_progress
    sales_service.reset_sales_session_context.assert_awaited_once_with(query)


@pytest.mark.asyncio
async def test_prepare_query_marks_generic_task_handoff_request():
    service = TaskAssistantService(SimpleNamespace())
    query = _query(text_chain('我要转人工'), '我要转人工')

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert query.variables['workflow_intent']['intent'] == 'handoff'
    assert query.variables['workflow_intent']['handoff_reason'] == 'manual_request'
    assert query.variables['workflow_intent']['handoff_config']['enabled'] is True
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '人工介入上下文' in context_text


@pytest.mark.asyncio
async def test_prepare_query_marks_screenshot_and_voice_context():
    service = TaskAssistantService(SimpleNamespace())
    query = voice_query('https://example.com/audio.mp3')
    query.pipeline_config = {'workflow': {'metadata': {'scenario': 'task_assistant_ant_af'}}}
    query.variables = {'user_message_text': '我卡住了'}
    query.prompt = SimpleNamespace(messages=[])
    query.message_chain.extend(image_chain(url='https://example.com/screen.png'))

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert query.variables['workflow_intent']['intent'] == 'screenshot_help'
    assert query.variables['task_assistant_voice_reply'] is True


@pytest.mark.asyncio
async def test_prepare_query_rewrites_voice_input_to_text_context():
    service = TaskAssistantService(SimpleNamespace())
    query = voice_query('https://example.com/audio.mp3')
    query.pipeline_config = {'workflow': {'metadata': {'scenario': 'task_assistant_ant_af'}}}
    query.variables = {'user_message_text': ''}
    query.prompt = SimpleNamespace(messages=[])
    query.user_message = provider_message.Message(
        role='user',
        content=[provider_message.ContentElement.from_file_url('https://example.com/audio.mp3', 'voice')],
    )

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert query.variables['task_assistant_voice_reply'] is True
    assert [item.type for item in query.user_message.content] == ['text', 'text']
    assert '用户发来一条语音' in query.user_message.content[0].text
    assert '本轮只讲' in query.user_message.content[1].text


@pytest.mark.asyncio
async def test_prepare_query_passes_voice_audio_for_native_audio_model():
    model = SimpleNamespace(
        uuid='gemini-model',
        name='gemini-3-flash-preview',
        abilities=['vision', 'func_call'],
        provider_uuid='provider-1',
    )
    provider = SimpleNamespace(requester='geminichatcmpl', name='Gemini', api_keys=['test-key'])
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(
            side_effect=[
                _FirstResult(model),
                _FirstResult(provider),
            ]
        )
    )
    service = TaskAssistantService(SimpleNamespace(persistence_mgr=persistence_mgr))
    query = voice_query('https://example.com/audio.mp3')
    query.pipeline_config = {
        'template_config': {'model_uuid': 'gemini-model'},
        'workflow': {'metadata': {'scenario': 'task_assistant_ant_af'}},
    }
    query.variables = {'user_message_text': ''}
    query.prompt = SimpleNamespace(messages=[])
    query.message_chain = [
        platform_message.Voice(
            base64='data:audio/mpeg;base64,YWJj',
            url='file:///tmp/voice.mp3',
        )
    ]
    query.user_message = provider_message.Message(
        role='user',
        content=[provider_message.ContentElement.from_text('')],
    )

    result = await service.prepare_query(query)

    assert result['handled'] is True
    content_types = [item.type for item in query.user_message.content]
    assert 'file_base64' in content_types
    assert any(item.type == 'text' and '用户发来一条语音' in (item.text or '') for item in query.user_message.content)


@pytest.mark.asyncio
async def test_course_sales_voice_uses_asr_fallback_when_native_audio_unavailable():
    primary_model = SimpleNamespace(
        uuid='text-model',
        name='plain-text-model',
        abilities=['func_call'],
        provider_uuid='text-provider',
    )
    primary_provider = SimpleNamespace(requester='openai-chat-completions', name='OpenAI Proxy', api_keys=['llm-key'])
    asr_model = SimpleNamespace(
        uuid='lna-doubao-bigasr-flash',
        name='bigmodel',
        abilities=['asr'],
        provider_uuid='lna-doubao',
        extra_args={'provider': 'volcengine-asr', 'resource_id': 'volc.bigasr.auc_turbo'},
    )
    asr_provider = SimpleNamespace(
        requester='volcengine-asr',
        name='豆包语音 ASR',
        base_url='https://openspeech.bytedance.com',
        api_keys=['speech-api-key'],
    )
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(
            side_effect=[
                _FirstResult(primary_model),
                _FirstResult(primary_provider),
                _FirstResult(asr_model),
                _FirstResult(asr_provider),
            ]
        )
    )
    service = TaskAssistantService(
        SimpleNamespace(persistence_mgr=persistence_mgr, sales_service=None, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = voice_query('https://example.com/audio.mp3')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(
        model_uuid='text-model',
        template_slug='yuanfudao-enhanced',
        existing_config={'template_config': {'asr': {'model_uuid': 'lna-doubao-bigasr-flash'}}},
    )
    query.variables = {'user_message_text': ''}
    query.prompt = SimpleNamespace(messages=[])
    query.message_chain = [
        platform_message.Voice(
            base64='data:audio/mpeg;base64,YWJj',
            url='https://example.com/audio.mp3',
        )
    ]
    query.user_message = provider_message.Message(
        role='user',
        content=[provider_message.ContentElement.from_text('')],
    )

    with patch(
        'langbot.pkg.api.http.service.task_assistant.asr_invoke.invoke_asr',
        new=AsyncMock(return_value='我想了解自然拼读什么时候上课'),
    ) as invoke_asr:
        await service.prepare_query(query)

    invoke_asr.assert_awaited_once()
    assert query.variables['course_sales_asr_text'] == '我想了解自然拼读什么时候上课'
    assert query.variables['user_message_text'] == '我想了解自然拼读什么时候上课'
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '我想了解自然拼读什么时候上课' in context_text
    assert query.variables['workflow_intent']['intent'] == 'course_schedule'


@pytest.mark.asyncio
async def test_course_sales_voice_prefers_asr_text_even_when_primary_model_supports_audio():
    primary_model = SimpleNamespace(
        uuid='gemini-model',
        name='gemini-3-flash-preview',
        abilities=['vision', 'func_call'],
        provider_uuid='gemini-provider',
    )
    primary_provider = SimpleNamespace(requester='geminichatcmpl', name='Gemini', api_keys=['llm-key'])
    asr_model = SimpleNamespace(
        uuid='lna-doubao-bigasr-flash',
        name='bigmodel',
        abilities=['asr'],
        provider_uuid='lna-doubao',
        extra_args={'provider': 'volcengine-asr', 'resource_id': 'volc.bigasr.auc_turbo'},
    )
    asr_provider = SimpleNamespace(
        requester='volcengine-asr',
        name='豆包语音 ASR',
        base_url='https://openspeech.bytedance.com',
        api_keys=['speech-api-key'],
    )
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(
            side_effect=[
                _FirstResult(primary_model),
                _FirstResult(primary_provider),
                _FirstResult(asr_model),
                _FirstResult(asr_provider),
            ]
        )
    )
    service = TaskAssistantService(
        SimpleNamespace(persistence_mgr=persistence_mgr, sales_service=None, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = voice_query('https://example.com/audio.mp3')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(
        model_uuid='gemini-model',
        template_slug='yuanfudao-enhanced',
        existing_config={'template_config': {'asr': {'model_uuid': 'lna-doubao-bigasr-flash'}}},
    )
    query.variables = {'user_message_text': ''}
    query.prompt = SimpleNamespace(messages=[])
    query.message_chain = [
        platform_message.Voice(
            base64='data:audio/mpeg;base64,YWJj',
            url='https://example.com/audio.mp3',
        )
    ]
    query.user_message = provider_message.Message(
        role='user',
        content=[provider_message.ContentElement.from_text('')],
    )

    with patch(
        'langbot.pkg.api.http.service.task_assistant.asr_invoke.invoke_asr',
        new=AsyncMock(return_value='9元体验课是什么东西'),
    ) as invoke_asr:
        await service.prepare_query(query)

    invoke_asr.assert_awaited_once()
    assert query.variables['course_sales_asr_text'] == '9元体验课是什么东西'
    assert query.variables['user_message_text'] == '9元体验课是什么东西'
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '9元体验课是什么东西' in context_text
    assert '必须按转写内容回答' in context_text


@pytest.mark.asyncio
async def test_prepare_query_limits_first_step_question_to_one_step():
    service = TaskAssistantService(SimpleNamespace())
    query = _query(text_chain('我现在只到第一步，二维码这一步怎么弄'), '我现在只到第一步，二维码这一步怎么弄')
    query.user_message = provider_message.Message(
        role='user',
        content=[provider_message.ContentElement.from_text('我现在只到第一步，二维码这一步怎么弄')],
    )

    result = await service.prepare_query(query)

    intent = query.variables['workflow_intent']
    assert result['handled'] is True
    assert intent['reply_mode'] == 'single_step'
    assert intent['step_ids'] == ['download_qr']
    assert intent['max_steps_to_describe'] == 1
    control_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '本轮只讲这一步' in control_text
    assert '不要列出完整 8 步' in control_text


@pytest.mark.asyncio
async def test_prepare_query_allows_concise_full_overview_only_for_full_flow_question():
    service = TaskAssistantService(SimpleNamespace())
    query = _query(text_chain('完整流程怎么做'), '完整流程怎么做')
    query.user_message = provider_message.Message(
        role='user',
        content=[provider_message.ContentElement.from_text('完整流程怎么做')],
    )

    await service.prepare_query(query)

    intent = query.variables['workflow_intent']
    assert intent['reply_mode'] == 'full_overview'
    assert intent['max_steps_to_describe'] == 8
    control_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '可以给一版精简完整流程' in control_text
    assert '每步只写一行' in control_text


def test_classify_next_step_uses_previous_assistant_step_as_progress_context():
    service = TaskAssistantService(SimpleNamespace())
    previous_messages = [
        provider_message.Message(role='assistant', content='第一步：支付宝扫码下载蚂蚁阿福 App。弄好后跟我说。'),
    ]

    intent = service.classify_intent('好了，下一步', text_chain('好了，下一步'), previous_messages)

    assert intent['intent'] == 'task_progress'
    assert intent['reply_mode'] == 'single_step'
    assert intent['step_ids'] == ['app_store_download']
    assert intent['max_steps_to_describe'] == 1


@pytest.mark.asyncio
async def test_ensure_default_resources_removes_seeded_digital_employee_templates():
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        pipeline_mgr=SimpleNamespace(remove_pipeline=AsyncMock()),
        sales_service=None,
    )
    service = TaskAssistantService(ap)
    service._ensure_task_images = AsyncMock()
    service._ensure_course_sales_images = AsyncMock()
    service._ensure_pipeline = AsyncMock()
    service._ensure_template_pipeline = AsyncMock()
    service._ensure_course_sales_product = AsyncMock()
    service._ensure_course_sales_workflow_pipeline = AsyncMock()
    service._ensure_course_sales_template_pipeline = AsyncMock()
    service._ensure_yuanfudao_enhanced_template_pipeline = AsyncMock()
    service._ensure_course_sales_outreach_for_chatted_users = AsyncMock()
    service._ensure_builtin_pipeline_default_models = AsyncMock()
    service._ensure_course_sales_doubao_model_defaults = AsyncMock()
    service._ensure_course_sales_runtime_defaults = AsyncMock()

    await service.ensure_default_resources()

    assert not hasattr(service, '_ensure_bailian_model')
    service._ensure_pipeline.assert_not_called()
    service._ensure_course_sales_workflow_pipeline.assert_not_called()
    service._ensure_template_pipeline.assert_awaited_once()
    service._ensure_course_sales_template_pipeline.assert_awaited_once()
    service._ensure_yuanfudao_enhanced_template_pipeline.assert_awaited_once()
    service._ensure_course_sales_doubao_model_defaults.assert_awaited_once()
    service._ensure_course_sales_runtime_defaults.assert_awaited_once()
    removed_pipeline_uuids = [call.args[0] for call in ap.pipeline_mgr.remove_pipeline.await_args_list]
    assert removed_pipeline_uuids == [
        TASK_ASSISTANT_PIPELINE_UUID,
        COURSE_SALES_WORKFLOW_PIPELINE_UUID,
    ]
    delete_statement = ap.persistence_mgr.execute_async.await_args_list[0].args[0]
    assert TASK_ASSISTANT_PIPELINE_UUID in str(delete_statement.compile(compile_kwargs={'literal_binds': True}))
    assert COURSE_SALES_WORKFLOW_PIPELINE_UUID in str(delete_statement.compile(compile_kwargs={'literal_binds': True}))
    assert TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID not in str(delete_statement.compile(compile_kwargs={'literal_binds': True}))
    assert COURSE_SALES_TEMPLATE_PIPELINE_UUID not in str(delete_statement.compile(compile_kwargs={'literal_binds': True}))


@pytest.mark.asyncio
async def test_course_sales_outreach_backfill_queries_template_pipeline_only():
    sales_service = SimpleNamespace(get_chatted_outreach_targets=AsyncMock(return_value=[]))
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=Mock())))

    await service._ensure_course_sales_outreach_for_chatted_users()

    sales_service.get_chatted_outreach_targets.assert_awaited_once_with(
        pipeline_uuids=[COURSE_SALES_TEMPLATE_PIPELINE_UUID]
    )


@pytest.mark.asyncio
async def test_task_assistant_template_seed_preserves_existing_identity_and_avatar():
    existing_pipeline = SimpleNamespace(
        name='自定义任务助手',
        description='用户改过的任务助手描述',
        emoji='🧪',
        config={'basic': {'avatar': '/agent-avatars/custom-task.png'}},
        extensions_preferences={
            'enable_all_plugins': False,
            'enable_all_mcp_servers': False,
            'plugins': ['plugin-a'],
            'mcp_servers': ['mcp-a'],
        },
    )
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(side_effect=[_FirstResult(existing_pipeline), None])),
        ver_mgr=SimpleNamespace(get_current_version=Mock(return_value='test-version')),
    )
    service = TaskAssistantService(ap)

    await service._ensure_template_pipeline()

    update_statement = ap.persistence_mgr.execute_async.await_args_list[1].args[0]
    params = update_statement.compile().params
    assert params['name'] == '自定义任务助手'
    assert params['description'] == '用户改过的任务助手描述'
    assert params['emoji'] == '🧪'
    assert params['config']['basic']['avatar'] == '/agent-avatars/custom-task.png'
    assert params['extensions_preferences']['enable_all_plugins'] is False
    assert params['extensions_preferences']['plugins'] == ['plugin-a']


@pytest.mark.asyncio
async def test_course_sales_template_seed_preserves_existing_identity_and_avatar():
    existing_pipeline = SimpleNamespace(
        name='自定义课程销售',
        description='用户改过的课程销售描述',
        emoji='🎯',
        config={'basic': {'avatar': '/agent-avatars/custom-course.png'}},
        extensions_preferences={
            'enable_all_plugins': False,
            'enable_all_mcp_servers': False,
            'plugins': ['plugin-course'],
            'mcp_servers': ['mcp-course'],
        },
    )
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(side_effect=[_FirstResult(existing_pipeline), None])),
        ver_mgr=SimpleNamespace(get_current_version=Mock(return_value='test-version')),
    )
    service = TaskAssistantService(ap)

    await service._ensure_course_sales_template_pipeline()

    update_statement = ap.persistence_mgr.execute_async.await_args_list[1].args[0]
    params = update_statement.compile().params
    assert params['name'] == '自定义课程销售'
    assert params['description'] == '用户改过的课程销售描述'
    assert params['emoji'] == '🎯'
    assert params['config']['basic']['avatar'] == '/agent-avatars/custom-course.png'
    assert params['extensions_preferences']['enable_all_plugins'] is False
    assert params['extensions_preferences']['plugins'] == ['plugin-course']


@pytest.mark.asyncio
async def test_yuanfudao_enhanced_template_seed_preserves_existing_identity_and_avatar():
    existing_pipeline = SimpleNamespace(
        name='用户改名的猿辅导助手',
        description='用户改过的增强版描述',
        emoji='🧪',
        config={'basic': {'avatar': '/agent-avatars/custom-yuanfudao.png'}},
        extensions_preferences={
            'enable_all_plugins': False,
            'enable_all_mcp_servers': False,
            'plugins': ['plugin-yuanfudao'],
            'mcp_servers': ['mcp-yuanfudao'],
        },
    )
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(side_effect=[_FirstResult(existing_pipeline), None])),
        ver_mgr=SimpleNamespace(get_current_version=Mock(return_value='test-version')),
    )
    service = TaskAssistantService(ap)

    await service._ensure_yuanfudao_enhanced_template_pipeline()

    update_statement = ap.persistence_mgr.execute_async.await_args_list[1].args[0]
    params = update_statement.compile().params
    assert params['name'] == '用户改名的猿辅导助手'
    assert params['description'] == '用户改过的增强版描述'
    assert params['emoji'] == '🧪'
    assert params['config']['basic']['avatar'] == '/agent-avatars/custom-yuanfudao.png'
    assert params['config']['template_config']['name'] == '猿辅导销售助手加强版'
    assert params['config']['template_config']['stop_policy']['explicit_rejection_threshold'] == 2
    assert params['extensions_preferences']['enable_all_plugins'] is False
    assert params['extensions_preferences']['plugins'] == ['plugin-yuanfudao']


@pytest.mark.asyncio
async def test_yuanfudao_enhanced_template_seed_inserts_configurable_demo():
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(side_effect=[_FirstResult(None), None])),
        ver_mgr=SimpleNamespace(get_current_version=Mock(return_value='test-version')),
    )
    service = TaskAssistantService(ap)

    await service._ensure_yuanfudao_enhanced_template_pipeline()

    insert_statement = ap.persistence_mgr.execute_async.await_args_list[1].args[0]
    params = insert_statement.compile().params
    assert params['uuid'] == YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
    assert params['name'] == '猿辅导销售助手加强版'
    assert params['config']['template_config']['source_materials']
    assert {profile['key'] for profile in params['config']['template_config']['course_profiles']} == {
        'phonics',
        'reading_thinking',
    }


@pytest.mark.asyncio
async def test_course_sales_product_seed_preserves_existing_product_edits():
    existing_product = SimpleNamespace(
        uuid='yuanfudao-phonics-course',
        name='用户改过的课程产品',
        price='用户改过的价格',
        enabled=False,
    )
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(return_value=_FirstResult(existing_product))),
    )
    service = TaskAssistantService(ap)

    await service._ensure_course_sales_product()

    assert ap.persistence_mgr.execute_async.await_count == 1


@pytest.mark.asyncio
async def test_course_sales_product_seed_respects_deleted_product_when_other_products_exist():
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(
                side_effect=[
                    _FirstResult(None),
                    _FirstResult(SimpleNamespace(uuid='user-product')),
                ]
            )
        ),
    )
    service = TaskAssistantService(ap)

    await service._ensure_course_sales_product()

    assert ap.persistence_mgr.execute_async.await_count == 2
    second_statement = ap.persistence_mgr.execute_async.await_args_list[1].args[0]
    assert str(second_statement).lstrip().upper().startswith('SELECT')


def test_task_assistant_pipeline_config_starts_without_hardcoded_model():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_pipeline_config()

    assert config['ai']['runner']['runner'] == 'local-agent'
    assert config['ai']['local-agent']['model']['primary'] == ''
    workflow = config['workflow']
    reply_node = next(node for node in workflow['nodes'] if node['id'] == 'reply')
    assert reply_node['config']['model_uuid'] == ''


def test_task_assistant_workflow_is_fully_visualized_with_step_nodes_and_assets():
    service = TaskAssistantService(SimpleNamespace())

    workflow = service.build_workflow_config()

    node_ids = {node['id'] for node in workflow['nodes']}
    required_base_nodes = {
        'start',
        'channel',
        'media_router',
        'text_input',
        'voice_asr',
        'screenshot_input',
        'intent',
        'route_intent',
        'knowledge_fallback',
        'reply',
        'voice',
        'end',
    }
    assert required_base_nodes <= node_ids

    for step_id in (
        'download_qr',
        'app_store_download',
        'alipay_login',
        'alipay_login_confirm',
        'open_profile',
        'open_settings',
        'open_real_person_verify',
        'import_identity',
    ):
        assert f'step_{step_id}' in node_ids
        assert f'image_{step_id}' in node_ids

    edges = {(edge['source'], edge['target']) for edge in workflow['edges']}
    assert ('media_router', 'text_input') in edges
    assert ('media_router', 'voice_asr') in edges
    assert ('media_router', 'screenshot_input') in edges
    assert ('route_intent', 'step_download_qr') in edges
    assert ('route_intent', 'step_import_identity') in edges
    for step_id in (
        'download_qr',
        'app_store_download',
        'alipay_login',
        'alipay_login_confirm',
        'open_profile',
        'open_settings',
        'open_real_person_verify',
        'import_identity',
    ):
        assert (f'step_{step_id}', f'image_{step_id}') in edges
        assert (f'image_{step_id}', 'reply') in edges


@pytest.mark.asyncio
async def test_prepare_query_advances_task_step_instead_of_repeating_first_answer():
    service = TaskAssistantService(SimpleNamespace())

    first_query = _query(text_chain('这个任务怎么做'), '这个任务怎么做', session_id='repeat-user')
    first_result = await service.prepare_query(first_query)

    assert first_result['intent']['reply_mode'] == 'first_overview'
    assert first_result['intent']['step_ids'] == ['download_qr']
    assert first_result['intent']['include_full_overview'] is True

    next_query = _query(text_chain('好了，下一步'), '好了，下一步', session_id='repeat-user')
    next_result = await service.prepare_query(next_query)

    assert next_result['intent']['reply_mode'] == 'single_step'
    assert next_result['intent']['step_ids'] == ['app_store_download']
    assert next_result['intent']['include_full_overview'] is False
    assert '本轮只讲第 2 步' in next_query.user_message.content[-1].text


@pytest.mark.asyncio
async def test_prepare_query_repeated_general_question_keeps_current_step_short():
    service = TaskAssistantService(SimpleNamespace())

    await service.prepare_query(_query(text_chain('这个任务怎么做'), '这个任务怎么做', session_id='short-user'))
    repeated_query = _query(text_chain('怎么完成这个任务'), '怎么完成这个任务', session_id='short-user')

    result = await service.prepare_query(repeated_query)

    assert result['intent']['reply_mode'] == 'single_step'
    assert result['intent']['step_ids'] == ['download_qr']
    assert result['intent']['include_full_overview'] is False
    assert '不要重复完整流程' in repeated_query.user_message.content[-1].text


def test_task_assistant_pipeline_uses_frontend_configured_model_only():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_pipeline_config()

    assert config['ai']['runner']['runner'] == 'local-agent'
    assert config['ai']['local-agent']['model']['primary'] == ''
    assert config['workflow']['voice']['voice_type'] == TASK_ASSISTANT_TTS_VOICE_TYPE
    reply_node = next(node for node in config['workflow']['nodes'] if node['id'] == 'reply')
    voice_node = next(node for node in config['workflow']['nodes'] if node['id'] == 'voice')
    assert reply_node['config']['model_uuid'] == ''
    assert voice_node['config']['voice_type'] == TASK_ASSISTANT_TTS_VOICE_TYPE
    assert config['workflow']['voice']['encoding'] == 'ogg_opus'
    assert voice_node['config']['encoding'] == 'ogg_opus'


def test_course_sales_template_defaults_to_doubao_reply_and_intent_models():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    template = config['template_config']

    assert template['model_uuid'] == 'doubao-seed-2-0-pro-260215'
    assert template['intent_model_uuid'] == 'doubao-seed-2-0-mini-260215'
    assert template['model_extra_args']['reasoning_effort'] == 'low'
    assert template['intent_model_extra_args']['thinking'] == {'type': 'disabled'}
    assert '不要输出思考过程' in template['role_prompt']
    assert '人设' in template['role_prompt']
    assert '口吻' in template['role_prompt']
    assert '绝对禁则' in template['role_prompt']
    assert '业务边界' in template['role_prompt']
    assert '最终回复风格' in template['role_prompt']
    assert '成交SOP' not in template['role_prompt']
    assert '怎么识别意图' not in template['role_prompt']
    assert '怎么改写问题' not in template['role_prompt']
    assert '怎么更新画像' not in template['role_prompt']
    assert '怎么检索知识库' not in template['role_prompt']


@pytest.mark.asyncio
async def test_course_sales_prepare_query_runs_configured_agent_orchestration(monkeypatch):
    responses = [
        '{"孩子年级":"三年级","关注点":"上课时间","购买阶段":"课程咨询"}',
        '{"intent":"course_schedule","confidence":0.91,"reason":"模型判断用户在问排课","step_ids":[],"include_link":true}',
        '自然拼读 什么时候上课 支持回放 赠品 报名',
        '证据：自然拼读课分两周上，晚上19点到20点，支持3年回放。',
        '家长，这个课是晚上7点到8点，没赶上也能看回放',
        '{"next_action":"send_signup_link","delay":"马上","reason":"用户询问排课，可承接报名"}',
    ]
    provider = SimpleNamespace(
        invoke_llm=AsyncMock(
            side_effect=[
                (provider_message.Message(role='assistant', content=response), {})
                for response in responses
            ]
        )
    )

    async def get_model_by_uuid(model_uuid):
        return SimpleNamespace(
            model_entity=SimpleNamespace(
                uuid=model_uuid,
                name=model_uuid,
                abilities=[],
                extra_args={'thinking': {'type': 'disabled'}},
            ),
            provider=provider,
        )

    service = TaskAssistantService(
        SimpleNamespace(
            model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(side_effect=get_model_by_uuid)),
            sales_service=None,
            logger=SimpleNamespace(warning=lambda *_: None),
        )
    )
    monkeypatch.setattr(service, '_resolve_primary_llm_model_info', AsyncMock(return_value={}))
    query = _query(text_chain('什么时候上课'), '什么时候上课')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(
        model_uuid='doubao-seed-2-0-pro-260215',
        template_slug='yuanfudao-enhanced',
        existing_config={
            'template_config': {
                'intent_model_uuid': 'doubao-seed-2-0-mini-260215',
                'intent_model_extra_args': {'thinking': {'type': 'disabled'}},
            }
        },
    )

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert query.variables['workflow_intent']['intent'] == 'course_schedule'
    assert query.variables['workflow_intent']['source'] == 'agent'
    assert query.variables['workflow_intent']['agent_id'] == 'intent_classifier'
    assert query.variables['user_profile']['孩子年级'] == '三年级'
    assert query.variables['rewritten_query'] == '自然拼读 什么时候上课 支持回放 赠品 报名'
    assert '晚上19点到20点' in query.variables['evidence_bundle']
    assert '晚上7点到8点' in query.variables['agent_reply_draft']
    assert 'send_signup_link' in query.variables['outreach_plan']
    assert len(query.variables['agent_orchestration_trace']) == 6
    assert provider.invoke_llm.await_count == 6
    requested_model_uuids = [call.args[0] for call in service.ap.model_mgr.get_model_by_uuid.await_args_list]
    assert requested_model_uuids == [
        'doubao-seed-2-0-mini-260215',
        'doubao-seed-2-0-mini-260215',
        'doubao-seed-2-0-mini-260215',
        'doubao-seed-2-0-mini-260215',
        'doubao-seed-2-0-pro-260215',
        'doubao-seed-2-0-mini-260215',
    ]
    invoke_kwargs = provider.invoke_llm.await_args_list[0].kwargs
    assert invoke_kwargs['extra_args'] == {'thinking': {'type': 'disabled'}, 'reasoning_effort': 'minimal'}
    assert invoke_kwargs['remove_think'] is True
    system_prompts = [call.kwargs['messages'][0].content for call in provider.invoke_llm.await_args_list]
    assert '画像增量' in system_prompts[0]
    assert '识别咨询意图' in system_prompts[1]
    assert '适合知识库' in system_prompts[2]
    assert '输出证据摘要' in system_prompts[3]
    assert '生成给家长看的回复草稿' in system_prompts[4]
    assert '生成下一步跟进计划' in system_prompts[5]
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '[智能体编排结果]' in context_text
    assert '用户画像' in context_text
    assert '重写问题' in context_text
    assert '检索证据' in context_text
    assert '回复草稿' in context_text
    assert '跟进计划' in context_text


@pytest.mark.asyncio
async def test_course_sales_agent_orchestration_skips_heavy_agents_for_smalltalk(monkeypatch):
    responses = [
        '{"关注点":"寒暄","购买阶段":"未开始"}',
        '{"intent":"smalltalk","confidence":0.89,"reason":"用户只是打招呼","step_ids":[],"include_link":false}',
        '家长您好，我在的，您可以直接把问题发我。',
    ]
    provider = SimpleNamespace(
        invoke_llm=AsyncMock(
            side_effect=[
                (provider_message.Message(role='assistant', content=response), {})
                for response in responses
            ]
        )
    )

    async def get_model_by_uuid(model_uuid):
        return SimpleNamespace(
            model_entity=SimpleNamespace(
                uuid=model_uuid,
                name=model_uuid,
                abilities=[],
                extra_args={'thinking': {'type': 'disabled'}},
            ),
            provider=provider,
        )

    service = TaskAssistantService(
        SimpleNamespace(
            model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(side_effect=get_model_by_uuid)),
            sales_service=None,
            logger=SimpleNamespace(warning=lambda *_: None),
        )
    )
    monkeypatch.setattr(service, '_resolve_primary_llm_model_info', AsyncMock(return_value={}))
    query = _query(text_chain('你好'), '你好')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(
        model_uuid='doubao-seed-2-0-pro-260215',
        template_slug='yuanfudao-enhanced',
    )

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert query.variables['workflow_intent']['intent'] == 'smalltalk'
    assert query.variables['agent_reply_draft'] == '家长您好，我在的，您可以直接把问题发我。'
    assert 'rewritten_query' not in query.variables
    assert 'evidence_bundle' not in query.variables
    assert 'outreach_plan' not in query.variables
    assert provider.invoke_llm.await_count == 3
    assert [item['id'] for item in query.variables['agent_orchestration_trace']] == [
        'profile_updater',
        'intent_classifier',
        'reply_composer',
    ]
    system_prompts = [call.kwargs['messages'][0].content for call in provider.invoke_llm.await_args_list]
    assert '画像增量' in system_prompts[0]
    assert '识别咨询意图' in system_prompts[1]
    assert '生成给家长看的回复草稿' in system_prompts[2]


@pytest.mark.asyncio
async def test_course_sales_agent_orchestration_respects_profile_memory_toggle(monkeypatch):
    responses = [
        '{"孩子年级":"三年级","关注点":"上课时间","购买阶段":"课程咨询"}',
        '{"intent":"course_schedule","confidence":0.91,"reason":"模型判断用户在问排课","step_ids":[],"include_link":true}',
        '自然拼读 什么时候上课 支持回放 赠品 报名',
        '证据：自然拼读课分两周上，晚上19点到20点，支持3年回放。',
        '家长，这个课是晚上7点到8点，没赶上也能看回放',
        '{"next_action":"send_signup_link","delay":"马上","reason":"用户询问排课，可承接报名"}',
    ]
    provider = SimpleNamespace(
        invoke_llm=AsyncMock(
            side_effect=[
                (provider_message.Message(role='assistant', content=response), {})
                for response in responses
            ]
        )
    )

    async def get_model_by_uuid(model_uuid):
        return SimpleNamespace(
            model_entity=SimpleNamespace(
                uuid=model_uuid,
                name=model_uuid,
                abilities=[],
                extra_args={'thinking': {'type': 'disabled'}},
            ),
            provider=provider,
        )

    service = TaskAssistantService(
        SimpleNamespace(
            model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(side_effect=get_model_by_uuid)),
            sales_service=None,
            logger=SimpleNamespace(warning=lambda *_: None),
        )
    )
    monkeypatch.setattr(service, '_resolve_primary_llm_model_info', AsyncMock(return_value={}))
    query = _query(text_chain('什么时候上课'), '什么时候上课')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(
        model_uuid='doubao-seed-2-0-pro-260215',
        template_slug='yuanfudao-enhanced',
        existing_config={
            'template_config': {
                'agent_orchestration': {'profile_memory_enabled': False},
            }
        },
    )

    await service.prepare_query(query)

    assert 'user_profile' not in query.variables
    assert query.variables['workflow_intent']['intent'] == 'course_schedule'
    assert query.variables['rewritten_query'] == '自然拼读 什么时候上课 支持回放 赠品 报名'
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '用户画像：' not in context_text
    assert '重写问题：' in context_text


@pytest.mark.asyncio
async def test_course_sales_intent_model_receives_recent_reference_rounds(monkeypatch):
    provider = SimpleNamespace(
        invoke_llm=AsyncMock(
            return_value=(
                provider_message.Message(
                    role='assistant',
                    content='{"intent":"resource_help","confidence":0.91,"reason":"模型结合上下文判断","step_ids":[],"include_link":false}',
                ),
                {},
            )
        )
    )
    runtime_model = SimpleNamespace(
        model_entity=SimpleNamespace(
            uuid='doubao-seed-2-0-mini-260215',
            name='doubao-seed-2-0-mini-260215',
            abilities=[],
            extra_args={'thinking': {'type': 'disabled'}},
        ),
        provider=provider,
    )
    service = TaskAssistantService(
        SimpleNamespace(
            model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=runtime_model)),
            sales_service=None,
            logger=SimpleNamespace(warning=lambda *_: None),
        )
    )
    monkeypatch.setattr(service, '_resolve_primary_llm_model_info', AsyncMock(return_value={}))
    query = _query(text_chain('现在呢'), '现在呢')
    query.messages = [
        provider_message.Message(role='user', content='太早的历史'),
        provider_message.Message(role='assistant', content='旧回复'),
        provider_message.Message(role='user', content='第一轮：答案在哪里'),
        provider_message.Message(role='assistant', content='可以点资源卡片'),
        provider_message.Message(role='user', content='第二轮：卡片打不开'),
        provider_message.Message(role='assistant', content='我帮您看一下'),
        provider_message.Message(role='user', content='第三轮：我点不开'),
        provider_message.Message(role='assistant', content='可以发截图'),
        provider_message.Message(role='user', content='第四轮：还是进不去'),
        provider_message.Message(role='assistant', content='我再发链接'),
    ]
    query.pipeline_config = service.build_course_sales_template_pipeline_config(
        model_uuid='doubao-seed-2-0-pro-260215',
        template_slug='yuanfudao-enhanced',
        existing_config={
            'template_config': {
                'reference_rounds': 4,
                'intent_model_uuid': 'doubao-seed-2-0-mini-260215',
                'intent_model_extra_args': {'thinking': {'type': 'disabled'}},
                'agent_orchestration': {'enabled': False},
            }
        },
    )

    await service.prepare_query(query)

    prompt = provider.invoke_llm.await_args.kwargs['messages'][1].content
    assert '历史对话（最近4轮）' in prompt
    assert '第一轮：答案在哪里' in prompt
    assert '第二轮：卡片打不开' in prompt
    assert '第三轮：我点不开' in prompt
    assert '第四轮：还是进不去' in prompt
    assert '太早的历史' not in prompt
    assert '用户消息：现在呢' in prompt


@pytest.mark.asyncio
async def test_builtin_pipeline_default_model_replaces_unconfigured_saved_model():
    saved_config = TaskAssistantService(SimpleNamespace()).build_course_sales_template_pipeline_config(
        model_uuid='lnp-openai-gpt-4o-mini',
        template_slug='yuanfudao-enhanced',
    )
    saved_config['template_config']['model_uuid'] = 'lnp-openai-gpt-4o-mini'
    pipeline = SimpleNamespace(config=saved_config)
    ap = SimpleNamespace(
        logger=SimpleNamespace(info=Mock(), warning=Mock(), debug=Mock()),
        llm_model_service=SimpleNamespace(
            get_llm_models=AsyncMock(
                return_value=[
                    {
                        'uuid': 'configured-model',
                        'name': 'gemini-3-flash-preview',
                        'abilities': ['vision', 'func_call'],
                    }
                ]
            )
        ),
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(
                side_effect=[
                    _FirstResult(pipeline),
                    None,
                    _FirstResult(None),
                    _FirstResult(None),
                ]
            )
        ),
    )
    service = TaskAssistantService(ap)

    await service._ensure_builtin_pipeline_default_models()

    update_statement = ap.persistence_mgr.execute_async.await_args_list[1].args[0]
    params = update_statement.compile().params
    updated_config = params['config']
    assert updated_config['template_config']['model_uuid'] == 'configured-model'
    assert updated_config['ai']['local-agent']['model']['primary'] == 'configured-model'
    ap.llm_model_service.get_llm_models.assert_awaited_once_with(
        include_secret=False,
        include_space_models=False,
        include_system_models=False,
        only_configured_providers=True,
        model_category='text',
    )


@pytest.mark.asyncio
async def test_course_sales_doubao_defaults_rebind_saved_course_pipeline_models():
    saved_config = TaskAssistantService(SimpleNamespace()).build_course_sales_template_pipeline_config(
        model_uuid='old-gemini-model',
        template_slug='yuanfudao-enhanced',
    )
    pipeline = SimpleNamespace(config=saved_config)
    ap = SimpleNamespace(
        logger=SimpleNamespace(info=Mock(), warning=Mock(), debug=Mock()),
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(
                side_effect=[
                    _FirstResult(pipeline),
                    None,
                    _FirstResult(None),
                    _EmptyListResult(),
                ]
            )
        ),
    )
    service = TaskAssistantService(ap)

    await service._ensure_course_sales_doubao_model_defaults()

    update_statement = ap.persistence_mgr.execute_async.await_args_list[1].args[0]
    params = update_statement.compile().params
    updated_config = params['config']
    assert updated_config['template_config']['model_uuid'] == 'doubao-seed-2-0-pro-260215'
    assert updated_config['template_config']['intent_model_uuid'] == 'doubao-seed-2-0-mini-260215'
    assert updated_config['ai']['local-agent']['model']['primary'] == 'doubao-seed-2-0-pro-260215'


@pytest.mark.asyncio
async def test_course_sales_doubao_defaults_repair_all_course_sales_pipelines():
    blank_config = TaskAssistantService(SimpleNamespace()).build_course_sales_pipeline_config(
        model_uuid='',
        template_config={'scenario': COURSE_SALES_SCENARIO, 'model_uuid': '', 'intent_model_uuid': ''},
    )
    pipeline = SimpleNamespace(uuid='custom-course-sales-pipeline', config=blank_config)
    updates = []

    async def execute_async(statement):
        params = statement.compile().params
        if getattr(statement, 'is_select', False):
            if params:
                return _FirstResult(None)
            return _ListResult([pipeline])
        if getattr(statement, 'is_update', False):
            updates.append(params)
        return None

    ap = SimpleNamespace(
        logger=SimpleNamespace(info=Mock(), warning=Mock(), debug=Mock()),
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(side_effect=execute_async)),
    )
    service = TaskAssistantService(ap)

    await service._ensure_course_sales_doubao_model_defaults()

    assert updates
    updated_config = updates[-1]['config']
    assert updated_config['template_config']['model_uuid'] == 'doubao-seed-2-0-pro-260215'
    assert updated_config['template_config']['intent_model_uuid'] == 'doubao-seed-2-0-mini-260215'
    assert updated_config['ai']['local-agent']['model']['primary'] == 'doubao-seed-2-0-pro-260215'


@pytest.mark.asyncio
async def test_course_sales_doubao_text_models_are_seeded_for_model_dropdowns():
    inserted_providers = []
    inserted_models = []

    async def execute_async(statement):
        params = statement.compile().params
        if getattr(statement, 'is_select', False):
            selected_table = statement.column_descriptions[0].get('entity')
            if selected_table is persistence_model.ModelProvider:
                return _EmptyListResult()
            if selected_table is persistence_model.LLMModel:
                return _EmptyListResult()
        if getattr(statement, 'is_insert', False):
            table_name = statement.table.name
            if table_name == 'model_providers':
                inserted_providers.append(params)
            if table_name == 'llm_models':
                inserted_models.append(params)
        return None

    ap = SimpleNamespace(
        logger=SimpleNamespace(info=Mock(), warning=Mock(), debug=Mock()),
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(side_effect=execute_async)),
    )
    service = TaskAssistantService(ap)

    await service._ensure_course_sales_doubao_text_models()

    assert inserted_providers == [
        {
            'uuid': 'lnp-doubao',
            'name': '豆包',
            'requester': 'volcark-chat-completions',
            'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
            'api_keys': [],
        }
    ]
    assert {model['uuid'] for model in inserted_models} == {
        'doubao-seed-2-0-pro-260215',
        'doubao-seed-2-0-mini-260215',
    }
    assert all(model['provider_uuid'] == 'lnp-doubao' for model in inserted_models)
    assert all('vision' in model['abilities'] for model in inserted_models)


def test_task_assistant_template_pipeline_config_matches_workflow_capabilities():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_template_pipeline_config()

    assert TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID == 'task-assistant-ant-af-template-pipeline'
    assert config['config_mode'] == 'template'
    assert config['ai']['local-agent']['model']['primary'] == ''
    assert config['ai']['local-agent']['max-round'] == 12
    assert config['workflow']['metadata']['scenario'] == 'task_assistant_ant_af'
    assert 'source_mode' not in config['workflow']['metadata']
    template_config = config['template_config']
    assert template_config['name'] == '任务助手模板配置版'
    assert template_config['scheduled_push']['mode'] == 'daily'
    assert template_config['scheduled_push']['message']
    assert template_config['interaction_radar']['enabled'] is False
    assert template_config['interaction_radar']['link_url'] == ''
    assert template_config['interaction_radar']['click_reply']
    assert template_config['voice']['voice_type'] == TASK_ASSISTANT_TTS_VOICE_TYPE
    assert template_config['voice']['encoding'] == 'ogg_opus'
    assert len(template_config['image_text_bindings']) == 8
    first_binding = template_config['image_text_bindings'][0]
    assert first_binding['step_id'] == 'download_qr'
    assert first_binding['text']
    assert first_binding['file_key'].endswith('af_step_01.png')


def test_course_sales_template_pipeline_contains_full_sop_capabilities():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_course_sales_template_pipeline_config()

    assert COURSE_SALES_TEMPLATE_PIPELINE_UUID == 'course-sales-template-pipeline'
    assert config['config_mode'] == 'template'
    assert config['workflow']['metadata']['scenario'] == COURSE_SALES_SCENARIO
    assert config['ai']['runner']['runner'] == 'local-agent'
    assert config['ai']['local-agent']['model']['primary'] == 'doubao-seed-2-0-pro-260215'
    assert config['ai']['local-agent']['max-round'] == 12
    assert config['workflow']['reference_rounds'] == 4
    template = config['template_config']
    assert template['intent_model_uuid'] == 'doubao-seed-2-0-mini-260215'
    assert template['reference_rounds'] == 4
    assert template['name'] == '课程销售模板'
    assert template['course_profile']['course_name'] == '猿辅导英语自然拼读体验课/自然拼读集训营'
    assert template['course_profile']['price'] == '9元体验'
    assert template['course_profile']['target_grade'] == '大班至小学4年级'
    assert len(template['resource_faqs']) >= 7
    resource_faq_text = '\n'.join(
        f"{faq.get('question', '')} {faq.get('answer', '')} {' '.join(faq.get('keywords', []))}"
        for faq in template['resource_faqs']
    )
    assert '资源为空' in resource_faq_text
    assert '正在上传' in resource_faq_text
    assert '资源缺失' in resource_faq_text
    assert '音频' in resource_faq_text and '不匹配' in resource_faq_text
    assert '资源问题工单' in resource_faq_text
    assert '图书二维码' in resource_faq_text
    assert '有问题的那一页' in resource_faq_text
    assert len(template['course_faqs']) >= 10
    assert len(template['followup_sequences']) >= 6
    assert len(template['long_term_broadcasts']) == 49
    assert template['radar']['enabled'] is True
    assert template['radar']['link_url'] == COURSE_SALES_RADAR_LINK
    assert len(template['radar']['rules']) >= 4
    assert any(rule['event'] == 'browse_30s' for rule in template['radar']['rules'])
    assert template['radar']['rules'][0]['message'] == COURSE_SALES_AFTER_LINK_OPEN_MESSAGE
    assert template['tools']['voice_reply'] is True
    assert template['voice']['enabled'] is True
    assert template['voice']['voice_type'] == COURSE_SALES_TTS_VOICE_TYPE
    assert template['voice']['encoding'] == 'ogg_opus'
    assert '您的图书配套学习资源点击' in template['opening_message']
    assert COURSE_RESOURCE_CARD_LINK not in template['opening_message']
    assert COURSE_RESOURCE_CARD_LINK not in template['role_prompt']
    assert '先解释用户当前问题，再自然问要不要给孩子试试' not in template['role_prompt']
    assert '发完结课礼物图后，再发雷达报名链接' not in template['role_prompt']
    assert COURSE_SALES_AFTER_LINK_OPEN_MESSAGE not in template['role_prompt']
    assert '跟进计划助手' in {
        assistant['name']
        for assistant in template['agent_orchestration']['assistants']
    }
    assert 'https://mp.bookln.cn/user/history/moment.htm' in template['opening_message']
    assert '#小程序://教辅好帮手/la0KWwjPCx8S26C' in template['opening_message']
    assert 'https://d.codeup.cn/d/UVruQn' in template['opening_message']
    assert len(template['image_text_bindings']) >= 2
    image_file_keys = {binding['file_key'] for binding in template['image_text_bindings']}
    assert 'course-sales/phonics/gift_poster.jpeg' in image_file_keys
    assert 'course-sales/phonics/gift_qr.jpeg' in image_file_keys
    gift_binding = next(
        binding for binding in template['image_text_bindings']
        if binding['file_key'] == 'course-sales/phonics/gift_poster.jpeg'
    )
    schedule_faq = next(faq for faq in template['course_faqs'] if faq['intent'] == 'course_schedule')
    assert '回放' not in schedule_faq['keywords']
    assert 'course_intro' not in gift_binding['trigger_intents']
    assert 'course_schedule' in gift_binding['trigger_intents']
    assert 'course_content' in gift_binding['trigger_intents']
    assert 'course_replay' in gift_binding['trigger_intents']
    assert 'course_conflict' in gift_binding['trigger_intents']
    assert all('day1_' not in file_key and 'day2_' not in file_key and 'day3_' not in file_key for file_key in image_file_keys)
    broadcast_messages = '\n'.join(broadcast['message'] for broadcast in template['long_term_broadcasts'])
    assert '自然拼读专项课' in broadcast_messages
    assert '9元' in broadcast_messages
    assert '可以回放' in broadcast_messages
    assert '180次开口练习' in broadcast_messages
    assert '给孩子报一个吧' not in broadcast_messages
    assert '优惠马上要截止了' not in broadcast_messages
    assert any(broadcast.get('time') == '15:40' for broadcast in template['long_term_broadcasts'])
    assert any(broadcast.get('time') == '21:20' for broadcast in template['long_term_broadcasts'])
    assert all(not broadcast.get('image_key') for broadcast in template['long_term_broadcasts'])
    assert all(
        'sop_doc_media' not in str(value).lower()
        and 'image1.png' not in str(value).lower()
        and 'image2.png' not in str(value).lower()
        and 'image3.png' not in str(value).lower()
        for broadcast in template['long_term_broadcasts']
        for value in broadcast.values()
    )
    assert template['stop_rules']['stop_keywords']
    links_by_id = {link['id']: link for link in template['sales_links']}
    assert links_by_id['phonics_resource_card']['url'] == COURSE_RESOURCE_CARD_LINK
    assert links_by_id['phonics_resource_card']['radar_enabled'] is False
    assert links_by_id['phonics_radar_apply']['url'] == COURSE_SALES_RADAR_LINK
    assert links_by_id['phonics_radar_apply']['radar_enabled'] is True
    followups_by_stage = {sequence['stage']: sequence for sequence in template['followup_sequences']}
    assert any(
        message.get('link_id') == 'phonics_radar_apply'
        for message in followups_by_stage['purchase']['messages']
    )
    assert any(
        message.get('image_key') == 'course-sales/phonics/gift_poster.jpeg'
        for message in followups_by_stage['not_buy']['messages']
    )
    assert any(
        message.get('image_key') == 'course-sales/phonics/gift_qr.jpeg'
        for message in followups_by_stage['purchased']['messages']
    )
    silence_messages = followups_by_stage['silence_revisit']['messages']
    assert silence_messages[0]['delay_minutes'] == 5
    assert silence_messages[0]['message'] == COURSE_SALES_FIVE_MIN_FOLLOWUP_MESSAGE
    assert silence_messages[1]['delay_minutes'] == 60
    assert silence_messages[1]['message'] == COURSE_SALES_ONE_HOUR_FOLLOWUP_MESSAGE
    assert silence_messages[1]['voice_optional'] is True
    assert silence_messages[2]['schedule_policy'] == 'daytime_2130_else_next_1000'
    assert silence_messages[2]['message'] == COURSE_SALES_EVENING_FOLLOWUP_MESSAGE
    assert silence_messages[2]['voice_optional'] is True
    assert (
        followups_by_stage['radar_clicked']['messages'][0]['message']
        == COURSE_SALES_AFTER_LINK_OPEN_MESSAGE
    )


def test_course_sales_dynamic_evening_followup_uses_2130_or_next_1000():
    service = TaskAssistantService(SimpleNamespace())
    message = {
        'schedule_policy': 'daytime_2130_else_next_1000',
        'daytime_schedule_time': '21:30',
        'night_schedule_time': '10:00',
        'night_cutoff_time': '21:00',
    }

    daytime = datetime.datetime(2026, 6, 18, 20, 15)
    night = datetime.datetime(2026, 6, 18, 21, 5)

    assert service._course_message_scheduled_at(message, daytime) == datetime.datetime(2026, 6, 18, 21, 30)
    assert service._course_message_scheduled_at(message, night) == datetime.datetime(2026, 6, 19, 10, 0)


def test_course_sales_runtime_defaults_update_copied_pipeline_config():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    config['ai']['local-agent']['max-round'] = 8
    config['workflow'].pop('reference_rounds', None)

    changed = service._apply_course_sales_runtime_defaults(config)

    assert changed is True
    assert config['ai']['local-agent']['max-round'] == 12
    assert config['workflow']['reference_rounds'] == 4


def test_course_sales_runtime_defaults_refresh_conflict_faq_answer():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config()
    old_answer = '不冲突的，这个课更侧重拼读技巧和方法，而且支持回放。时间不方便也可以先报名，后面按老师安排和回放节奏学。'
    config['workflow']['template_config'] = {
        'course_faqs': [
            {'intent': 'course_conflict', 'question': '和其他课有冲突', 'answer': old_answer}
        ]
    }

    changed = service._apply_course_sales_runtime_defaults(config)

    assert changed is True
    answer = config['workflow']['template_config']['course_faqs'][0]['answer']
    assert '报名还独家赠送小猿篮球/护脊书包/小猿手办/宇航员文具盒/铅笔/转笔刀' in answer
    assert '主要是赠送实物的名额，就这一周有' in answer


def test_course_sales_runtime_defaults_refresh_intro_faq_and_remove_intro_gift_image():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config()
    old_intro = '这是猿辅导英语自然拼读集训营，9元5天10节，适合大班到小学4年级。主要带孩子学拼读规律、绘本阅读和开口表达，目标是见词能拼、听音能写，少靠死记硬背。'
    config['workflow']['template_config'] = {
        'course_faqs': [
            {'intent': 'course_schedule', 'question': '什么时候上课', 'answer': '晚上上课', 'keywords': ['几点', '回放']},
            {'intent': 'course_intro', 'question': '这个是什么课', 'answer': old_intro},
            {'intent': 'course_content', 'question': '学习内容', 'answer': '核心内容包括26个字母巧记、拼读规则和绘本阅读。'},
            {'intent': 'course_replay', 'question': '支持回放吗', 'answer': '支持回放，3年内可以无限次看。'},
        ],
        'image_text_bindings': [
            {
                'file_key': 'course-sales/phonics/gift_poster.jpeg',
                'trigger_intents': ['gift', 'course_intro', 'purchase'],
            }
        ],
    }
    config['workflow']['nodes'] = [
        {
            'type': 'image',
            'config': {
                'file_key': 'course-sales/phonics/gift_poster.jpeg',
                'trigger_intents': ['course_intro', 'purchase'],
            },
        }
    ]

    changed = service._apply_course_sales_runtime_defaults(config)

    assert changed is True
    schedule_keywords = config['workflow']['template_config']['course_faqs'][0]['keywords']
    assert '回放' not in schedule_keywords
    schedule_answer = config['workflow']['template_config']['course_faqs'][0]['answer']
    assert '晚上19点到20点' in schedule_answer
    assert '需要给孩子试试不，现在报名还送结课礼物' in schedule_answer
    answer = config['workflow']['template_config']['course_faqs'][1]['answer']
    assert '5次绘本阅读实践' in answer
    assert '180次开口练习' in answer
    assert '360分钟配套视频' in answer
    assert '报名链接我发您' in answer
    content_answer = config['workflow']['template_config']['course_faqs'][2]['answer']
    assert '每个年级的学习内容不一样' in content_answer
    assert '根据孩子年级匹配' in content_answer
    assert '需要给孩子试试不，现在报名还送结课礼物' in content_answer
    replay_answer = config['workflow']['template_config']['course_faqs'][3]['answer']
    assert '每次也就一小时左右' in replay_answer
    assert '要不要试试看' in replay_answer
    assert '小猿篮球/护脊书包/小猿手办/宇航员文具盒/铅笔/转笔刀' in replay_answer
    binding_intents = config['workflow']['template_config']['image_text_bindings'][0]['trigger_intents']
    node_intents = config['workflow']['nodes'][0]['config']['trigger_intents']
    assert 'course_intro' not in binding_intents
    assert 'course_intro' not in node_intents
    assert 'course_schedule' in binding_intents
    assert 'course_schedule' in node_intents
    assert 'course_content' in binding_intents
    assert 'course_content' in node_intents
    assert 'course_replay' in binding_intents
    assert 'course_replay' in node_intents
    assert 'course_conflict' in binding_intents
    assert 'course_conflict' in node_intents


def test_course_sales_runtime_defaults_skip_non_course_pipeline_config():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_template_pipeline_config()

    changed = service._apply_course_sales_runtime_defaults(config)

    assert changed is False


@pytest.mark.parametrize(
    ('text', 'expected_issue_type'),
    [
        ('扫码以后提示资源缺失', 'missing_resource'),
        ('页面显示资源正在上传中', 'resource_uploading'),
        ('打开以后资源为空', 'empty_resource'),
        ('听力音频和题目不匹配，内容是错的', 'content_error'),
    ],
)
def test_course_sales_runtime_classifies_resource_issue_cases(text, expected_issue_type):
    service = TaskAssistantService(SimpleNamespace())
    workflow = service.build_course_sales_workflow_config(
        template_config=service.build_course_sales_template_config(template_slug='yuanfudao-enhanced')
    )

    intent = service.classify_course_sales_intent(text, text_chain(text), workflow)

    assert intent['intent'] == 'resource_help'
    assert intent['resource_issue_type'] == expected_issue_type
    assert intent['step_ids'] == ['gift_qr']


@pytest.mark.asyncio
async def test_prepare_course_sales_query_records_resource_issue_ticket(monkeypatch):
    sales_service = SimpleNamespace(create_resource_issue_from_query=AsyncMock(return_value={'id': 12}))
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=Mock())))
    monkeypatch.setattr(service, '_resolve_primary_llm_model_info', AsyncMock(return_value={}))
    monkeypatch.setattr(service, '_schedule_course_sales_outreach_for_query', AsyncMock())
    query = _query(
        text_chain('听力音频和题目不匹配，内容是错的'),
        '听力音频和题目不匹配，内容是错的',
        session_id='customer-issue',
    )
    query.bot_uuid = 'bot-uuid'
    query.sender_id = 'ou_customer'
    query.adapter = SimpleNamespace()
    query.pipeline_uuid = 'pipeline-1'
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    result = await service.prepare_query(query)

    assert result['handled'] is True
    sales_service.create_resource_issue_from_query.assert_awaited_once()
    _, payload = sales_service.create_resource_issue_from_query.await_args.args
    assert payload['issue_type'] == 'content_error'
    assert payload['user_description'] == '听力音频和题目不匹配，内容是错的'
    assert '内容错误' in payload['issue_summary']


@pytest.mark.asyncio
async def test_prepare_course_sales_query_records_resource_issue_image_evidence(monkeypatch):
    sales_service = SimpleNamespace(create_resource_issue_from_query=AsyncMock(return_value={'id': 12}))
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=Mock())))
    monkeypatch.setattr(service, '_resolve_primary_llm_model_info', AsyncMock(return_value={}))
    monkeypatch.setattr(service, '_schedule_course_sales_outreach_for_query', AsyncMock())
    query = _query(
        image_chain(text='听力音频和题目不匹配，内容是错的', url='https://example.com/resource-error.jpg'),
        '听力音频和题目不匹配，内容是错的',
        session_id='customer-issue',
    )
    query.bot_uuid = 'bot-uuid'
    query.sender_id = 'ou_customer'
    query.adapter = SimpleNamespace()
    query.pipeline_uuid = 'pipeline-1'
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    result = await service.prepare_query(query)

    assert result['handled'] is True
    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'resource_help'
    assert intent['resource_issue_type'] == 'content_error'
    assert intent['has_evidence_image'] is True
    sales_service.create_resource_issue_from_query.assert_awaited_once()
    _, payload = sales_service.create_resource_issue_from_query.await_args.args
    assert payload['evidence_images'] == ['https://example.com/resource-error.jpg']


def test_course_sales_template_config_migrates_legacy_default_assets_and_links():
    service = TaskAssistantService(SimpleNamespace())

    template = service.build_course_sales_template_config(
        overrides={
            'role_prompt': (
                '你是微信/企微私域里的真人课程客服兼销售。'
                '首次还要单独发送图书配套学习资源卡片：'
                f'{COURSE_RESOURCE_CARD_LINK}。'
                '按 SOP 图片转写后的文字群发，不发送 SOP 截图。'
            ),
            'opening_message': '家长您好，您扫描的图书配套学习资料已经发您了，您看这个资源能打开吗？',
            'radar': {'link_url': 'https://radar.yunti.local/course/phonics'},
            'sales_links': [
                {
                    'id': 'phonics_radar_apply',
                    'title': '旧报名链接',
                    'url': 'https://radar.yunti.local/course/phonics',
                    'radar_enabled': True,
                }
            ],
            'image_text_bindings': [
                {
                    'step_id': 'course_intro',
                    'title': '旧课程介绍海报',
                    'text': '旧素材',
                    'file_key': 'course-sales/phonics/day1_course_intro.png',
                    'trigger_intents': ['course_intro'],
                    'enabled': True,
                }
            ],
            'long_term_broadcasts': [
                {
                    'day': 1,
                    'title': '旧群发',
                    'time': '10:05',
                    'message': '旧群发文案',
                    'image_key': 'course-sales/phonics/day1_course_intro.png',
                }
            ],
            'followup_sequences': [
                {
                    'stage': 'purchase',
                    'label': '旧跟进',
                    'messages': [{'delay_minutes': 0, 'message': '旧跟进文案'}],
                }
            ],
        }
    )

    assert COURSE_RESOURCE_CARD_LINK not in template['opening_message']
    assert COURSE_RESOURCE_CARD_LINK not in template['role_prompt']
    assert 'radar.yunti.local' not in template['role_prompt']
    assert '不要整段塞话术' in template['role_prompt']
    assert '课程统一口径：' not in template['role_prompt']
    assert template['radar']['link_url'] == COURSE_SALES_RADAR_LINK
    links_by_id = {link['id']: link for link in template['sales_links']}
    assert links_by_id['phonics_resource_card']['url'] == COURSE_RESOURCE_CARD_LINK
    assert links_by_id['phonics_radar_apply']['url'] == COURSE_SALES_RADAR_LINK
    assert {binding['file_key'] for binding in template['image_text_bindings']} == {
        'course-sales/phonics/gift_poster.jpeg',
        'course-sales/phonics/gift_qr.jpeg',
    }
    assert '自然拼读专项课' in template['long_term_broadcasts'][0]['message']
    assert all(not broadcast.get('image_key') for broadcast in template['long_term_broadcasts'])
    assert all(
        'sop_doc_media' not in str(value).lower()
        and 'image1.png' not in str(value).lower()
        and 'image2.png' not in str(value).lower()
        and 'image3.png' not in str(value).lower()
        for broadcast in template['long_term_broadcasts']
        for value in broadcast.values()
    )
    assert template['voice']['enabled'] is True
    assert template['tools']['voice_reply'] is True
    migrated_followups = {sequence['stage']: sequence for sequence in template['followup_sequences']}
    assert any(
        message.get('link_id') == 'phonics_radar_apply'
        for message in migrated_followups['purchase']['messages']
    )
    assert any(
        message.get('image_key') == 'course-sales/phonics/gift_poster.jpeg'
        for message in migrated_followups['not_buy']['messages']
    )


def test_course_sales_template_config_replaces_legacy_long_role_prompt():
    service = TaskAssistantService(SimpleNamespace())

    template = service.build_course_sales_template_config(
        overrides={
            'role_prompt': (
                '你是微信/企微私域里的真人课程客服兼销售。\n\n'
                '成交SOP:\n'
                '- 通用成交SOP：先解释用户当前问题，再自然问要不要给孩子试试；'
                '若家长没发截图，5分钟后追问“家长领取到了吗？”；'
                '仍未回复，1小时后优先语音追问。'
            )
        }
    )

    assert '成交SOP' not in template['role_prompt']
    assert '通用成交SOP' not in template['role_prompt']
    assert '5分钟后追问' not in template['role_prompt']
    assert '人设' in template['role_prompt']
    assert '业务边界' in template['role_prompt']
    assert '最终回复风格' in template['role_prompt']


def test_course_sales_template_safety_flags_placeholder_and_legacy_links():
    service = TaskAssistantService(SimpleNamespace())

    issues = service._course_sales_template_safety_issues(
        {
            'sales_links': [
                {
                    'id': 'placeholder_apply',
                    'title': '占位报名链接',
                    'url': 'https://xxx.example.com/[报名链接]',
                    'radar_enabled': True,
                },
                {
                    'id': 'legacy_apply',
                    'title': '旧雷达报名链接',
                    'url': 'https://radar.yunti.local/course/phonics',
                    'radar_enabled': True,
                },
                {
                    'id': 'zhizhuma_apply',
                    'title': '资源链接误作报名雷达',
                    'url': COURSE_RESOURCE_CARD_LINK,
                    'radar_enabled': True,
                },
            ],
            'radar': {'link_url': 'https://mp.zhizhuma.com/webappv2/videoLecture/video-tbxvm9.htm'},
            'source_materials': [{'title': '报名素材', 'url': 'XXXX'}],
        }
    )

    assert {issue['code'] for issue in issues} == {
        'placeholder_link',
        'legacy_radar_link',
        'resource_link_used_as_radar',
    }
    assert any(issue['path'] == 'sales_links[0].url' for issue in issues)
    assert any(issue['path'] == 'sales_links[1].url' for issue in issues)
    assert any(issue['path'] == 'sales_links[2].url' for issue in issues)
    assert any(issue['path'] == 'radar.link_url' for issue in issues)
    assert any(issue['path'] == 'source_materials[0].url' for issue in issues)


@pytest.mark.parametrize('template_slug', [None, 'yuanfudao-enhanced'])
def test_course_sales_template_config_links_are_offline_safe(template_slug):
    service = TaskAssistantService(SimpleNamespace())

    template = service.build_course_sales_template_config(template_slug=template_slug)

    assert service._course_sales_template_safety_issues(template) == []
    links_by_id = {link['id']: link for link in template['sales_links']}
    assert links_by_id['phonics_resource_card']['url'] == COURSE_RESOURCE_CARD_LINK
    assert links_by_id['phonics_resource_card']['radar_enabled'] is False
    assert links_by_id['phonics_radar_apply']['url'] == COURSE_SALES_RADAR_LINK
    assert links_by_id['phonics_radar_apply']['radar_enabled'] is True


@pytest.mark.parametrize('template_slug', [None, 'yuanfudao-enhanced'])
def test_course_sales_template_outreach_messages_are_short_and_low_pressure(template_slug):
    service = TaskAssistantService(SimpleNamespace())

    template = service.build_course_sales_template_config(template_slug=template_slug)

    messages = []
    for sequence in template['followup_sequences']:
        for message in sequence.get('messages', []):
            if isinstance(message, dict) and message.get('action') != 'continue_long_term_broadcasts':
                messages.append(str(message.get('message') or ''))
    messages.extend(str(broadcast.get('message') or '') for broadcast in template['long_term_broadcasts'])
    conversion_followups = {
        COURSE_SALES_AFTER_LINK_OPEN_MESSAGE,
        COURSE_SALES_ONE_HOUR_FOLLOWUP_MESSAGE,
        COURSE_SALES_EVENING_FOLLOWUP_MESSAGE,
    }
    low_pressure_messages = [message for message in messages if message not in conversion_followups]

    assert messages
    assert all(len(message) <= 90 for message in low_pressure_messages)
    assert all(not message.rstrip().endswith(('。', '．', '.')) for message in low_pressure_messages)
    assert all(any(marker in message for marker in ('吗', '呀', '呢', '能打开吗')) for message in low_pressure_messages)
    pressure_markers = ('名额不多', '一直等您', '恳求', '不忍心', '不能再耽搁', '最后3个', '打扰你千千万万遍')
    assert all(not any(marker in message for marker in pressure_markers) for message in low_pressure_messages)


def test_course_sales_workflow_visualizes_template_capabilities_as_nodes():
    service = TaskAssistantService(SimpleNamespace())

    workflow = service.build_course_sales_workflow_config()

    assert COURSE_SALES_WORKFLOW_PIPELINE_UUID == 'course-sales-workflow-pipeline'
    assert workflow['name'] == '课程销售模板'
    assert workflow['metadata']['scenario'] == COURSE_SALES_SCENARIO
    node_ids = {node['id'] for node in workflow['nodes']}
    required_nodes = {
        'start',
        'channel',
        'media_router',
        'voice_asr',
        'screenshot_input',
        'intent',
        'resource_faq',
        'course_faq',
        'course_product',
        'sales_link',
        'opening_message',
        'radar',
        'radar_followup',
        'long_term_broadcast',
        'stop_rules',
        'handoff',
        'reply',
        'end',
    }
    assert required_nodes <= node_ids
    node_types = {node['type'] for node in workflow['nodes']}
    assert {'knowledge', 'product', 'radar', 'outreach', 'image'} <= node_types
    assert 'voice' not in node_types
    edges = {(edge['source'], edge['target']) for edge in workflow['edges']}
    assert ('start', 'opening_message') in edges
    assert ('opening_message', 'channel') in edges
    assert ('sales_link', 'radar') in edges
    assert ('radar', 'radar_followup') in edges
    assert ('course_product', 'sales_link') in edges
    assert workflow['voice']['enabled'] is True
    assert '您的图书配套学习资源点击' in workflow['opening_message']
    assert '家长，您这边能打开吗？' not in workflow['opening_message']
    opening_node = next(node for node in workflow['nodes'] if node['id'] == 'opening_message')
    assert opening_node['title'] == '首次开场白与资源卡片'
    assert opening_node['config']['link_id'] == 'phonics_resource_card'
    assert opening_node['config']['link_url'] == COURSE_RESOURCE_CARD_LINK
    followup_node = next(node for node in workflow['nodes'] if node['id'] == 'radar_followup')
    assert followup_node['title'] == '主动跟进话术矩阵'
    broadcast_node = next(node for node in workflow['nodes'] if node['id'] == 'long_term_broadcast')
    assert broadcast_node['title'] == 'SOP定时群发'
    radar_node = next(node for node in workflow['nodes'] if node['id'] == 'radar')
    assert radar_node['config']['link_url'] == COURSE_SALES_RADAR_LINK
    assert any(rule['event'] == 'click_apply_button' for rule in radar_node['config']['rules'])
    handoff_node = next(node for node in workflow['nodes'] if node['id'] == 'handoff')
    assert handoff_node['title'] == '转人工'
    assert handoff_node['config']['enabled'] is True
    assert '转人工' in handoff_node['config']['keywords']
    assert any(trigger['id'] == 'payment_issue' for trigger in handoff_node['config']['semantic_triggers'])


def test_course_sales_template_config_includes_human_handoff_rules():
    service = TaskAssistantService(SimpleNamespace())

    template = service.build_course_sales_template_config(template_slug='yuanfudao-enhanced')

    handoff = template['human_handoff']
    assert handoff['enabled'] is True
    assert '转人工' in handoff['keywords']
    assert '投诉' in handoff['keywords']
    assert handoff['stop_ai_reply'] is True
    assert handoff['stop_outreach'] is True
    assert handoff['notify_message'] == '我这边帮您记录好了，稍等我看下具体情况~'
    for forbidden in ['AI', '机器人', '转人工', '转接', '接管', '人工']:
        assert forbidden not in handoff['notify_message']
    assert any(trigger['id'] == 'manual_request' for trigger in handoff['semantic_triggers'])
    assert any(trigger['id'] == 'high_risk_complaint' for trigger in handoff['semantic_triggers'])


def test_yuanfudao_enhanced_template_includes_agent_orchestration_config():
    service = TaskAssistantService(SimpleNamespace())

    template = service.build_course_sales_template_config(template_slug='yuanfudao-enhanced')
    orchestration = template['agent_orchestration']

    assert orchestration['enabled'] is True
    assert orchestration['mode'] == 'multi_agent'
    assert orchestration['profile_memory_enabled'] is True
    assert orchestration['debug_trace_enabled'] is True
    assert [assistant['id'] for assistant in orchestration['assistants']] == [
        'profile_updater',
        'intent_classifier',
        'query_rewriter',
        'knowledge_retriever',
        'reply_composer',
        'followup_planner',
    ]
    assert [assistant['name'] for assistant in orchestration['assistants']] == [
        '画像更新助手',
        '意图识别助手',
        '问题重写助手',
        '知识/产品检索',
        '回复生成助手',
        '跟进计划助手',
    ]
    assistant_by_id = {assistant['id']: assistant for assistant in orchestration['assistants']}
    assert assistant_by_id['profile_updater']['model_uuid'] == 'doubao-seed-2-0-mini-260215'
    assert assistant_by_id['query_rewriter']['model_uuid'] == 'doubao-seed-2-0-mini-260215'
    assert assistant_by_id['reply_composer']['model_uuid'] == 'doubao-seed-2-0-pro-260215'
    assert assistant_by_id['profile_updater']['prompt']
    assert assistant_by_id['intent_classifier']['prompt']
    assert assistant_by_id['query_rewriter']['prompt']

    workflow = service.build_course_sales_workflow_from_template_config(template)

    assert workflow['agent_orchestration'] == orchestration
    assert workflow['variables']['agent_orchestration'] == orchestration
    assert 'user_profile' in workflow['metadata']['langgraph_state']
    assert 'rewritten_query' in workflow['metadata']['langgraph_state']


def test_course_sales_template_mode_builds_active_workflow_from_independent_template():
    service = TaskAssistantService(SimpleNamespace())
    template = service.build_course_sales_template_config(
        overrides={
            'radar': {
                'enabled': True,
                'link_url': 'https://example.com/course/custom',
                'rules': [{'event': 'click', 'delay_minutes': 1, 'message': '自定义雷达跟进'}],
            },
            'voice': {'app_id': 'course-app', 'token': 'course-token'},
        }
    )
    saved_workflow = {
        'version': 1,
        'name': 'kept workflow',
        'metadata': {'scenario': 'custom'},
        'nodes': [],
        'edges': [],
    }

    active = service.active_workflow_from_config(
        {
            'config_mode': 'template',
            'template_config': template,
            'workflow': saved_workflow,
        }
    )

    assert active is not saved_workflow
    assert active['metadata']['scenario'] == COURSE_SALES_SCENARIO
    assert active['voice']['app_id'] == 'course-app'
    radar_node = next(node for node in active['nodes'] if node['id'] == 'radar')
    assert radar_node['config']['link_url'] == 'https://example.com/course/custom'
    assert service.is_task_assistant_pipeline({'config_mode': 'template', 'template_config': template}) is True


def test_course_sales_template_pipeline_rebuilds_legacy_course_sales_workflow():
    service = TaskAssistantService(SimpleNamespace())
    existing_workflow = {
        'version': 1,
        'name': 'old course sales workflow',
        'metadata': {'scenario': COURSE_SALES_SCENARIO},
        'nodes': [],
        'edges': [],
    }

    config = service.build_course_sales_template_pipeline_config(
        existing_config={'workflow': existing_workflow}
    )

    assert config['workflow'] is not existing_workflow
    assert config['workflow']['metadata']['scenario'] == COURSE_SALES_SCENARIO
    assert config['workflow']['nodes']


def test_course_sales_template_preserves_user_disabled_voice_reply():
    service = TaskAssistantService(SimpleNamespace())

    template = service.build_course_sales_template_config(
        overrides={
            'tools': {'voice_reply': False},
            'voice': {'enabled': False, 'voice_type': 'custom-voice'},
        }
    )
    workflow = service.build_course_sales_workflow_from_template_config(template)

    assert template['tools']['voice_reply'] is False
    assert template['voice']['enabled'] is False
    assert workflow['voice']['enabled'] is False
    assert workflow['voice']['voice_type'] == 'custom-voice'


@pytest.mark.asyncio
async def test_prepare_query_handles_course_sales_voice_and_radar_intents():
    service = TaskAssistantService(SimpleNamespace())
    query = voice_query('https://example.com/audio.mp3')
    query.pipeline_config = {'workflow': service.build_course_sales_workflow_config()}
    query.variables = {'user_message_text': '我点了报名链接，什么时候上课'}
    query.prompt = SimpleNamespace(messages=[])
    query.user_message = provider_message.Message(
        role='user',
        content=[provider_message.ContentElement.from_text('我点了报名链接，什么时候上课')],
    )

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert query.variables['workflow_intent']['intent'] in {'course_schedule', 'radar_clicked'}
    assert query.variables['task_assistant_voice_reply'] is True
    assert query.prompt.messages == []
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '如果已启用语音回复' in context_text or '语音咨询' in context_text


class _CourseOutreachSalesService:
    def __init__(self, user_message_count=1):
        self.user_message_count = user_message_count
        self.plans = []
        self.disabled = []
        self.handoffs = []
        self.due_runs = []

    async def count_user_messages_for_session(self, _session_id):
        return self.user_message_count

    async def create_outreach_plan(self, data):
        self.plans.append(data)
        return len(self.plans)

    async def count_outreach_plans_for_target_segments(self, *, bot_uuid, target_type, target_id, segments):
        return sum(
            1
            for plan in self.plans
            if plan.get('bot_uuid') == bot_uuid
            and plan.get('target_type') == target_type
            and plan.get('target_id') == target_id
            and plan.get('segment') in segments
        )

    async def disable_outreach_for_target(self, **kwargs):
        self.disabled.append(kwargs)

    async def open_handoff_from_query(self, query, reason, message_text):
        self.handoffs.append(
            {
                'query': query,
                'reason': reason,
                'message_text': message_text,
            }
        )
        return len(self.handoffs)

    def build_radar_tracking_url(self, **kwargs):
        return 'http://127.0.0.1:5300/api/v1/sales/radar/click/test-token'

    async def run_due_outreach_for_target(self, **kwargs):
        self.due_runs.append(kwargs)
        return 0


class _PersistingRejectionSalesService(_CourseOutreachSalesService):
    def __init__(self, user_message_count=2):
        super().__init__(user_message_count=user_message_count)
        self.rejection_counts: dict[str, int] = {}

    async def get_course_sales_explicit_rejection_count(self, session_id):
        return int(self.rejection_counts.get(session_id) or 0)

    async def increment_course_sales_explicit_rejection_count(self, _query, session_id):
        count = int(self.rejection_counts.get(session_id) or 0) + 1
        self.rejection_counts[session_id] = count
        return count


@pytest.mark.parametrize('confirmation_text', ['好的', '可以的', '我能打开'])
@pytest.mark.asyncio
async def test_course_sales_resource_open_confirmation_asks_grade_before_pitching_course(confirmation_text):
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    query = _query(text_chain(confirmation_text), confirmation_text, session_id='customer-opened')
    query.pipeline_config = {'workflow': service.build_course_sales_workflow_config()}
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = COURSE_SALES_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'resource_confirmed'
    assert 'link_url' not in intent
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '不要重复问能打开吗' in context_text
    assert '先问孩子几年级' in context_text
    assert '要不要报课' in context_text
    assert '本轮要给报名动作和报名链接卡片' not in context_text
    assert not any(plan['segment'] == 'course-sales:followup:purchase' for plan in sales_service.plans)


@pytest.mark.asyncio
async def test_course_sales_first_contact_schedules_opening_resource_card_and_sop_text_only():
    sales_service = _CourseOutreachSalesService(user_message_count=1)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    query = _query(text_chain('我想报名'), '我想报名', session_id='customer-1')
    query.pipeline_config = {'workflow': service.build_course_sales_workflow_config()}
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = COURSE_SALES_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)
    after = datetime.datetime.now()

    assert result['handled'] is True
    opening_plans = [plan for plan in sales_service.plans if plan['segment'].startswith('course-sales:opening')]
    assert len(opening_plans) == 3
    assert all(plan['scheduled_at'] <= after for plan in opening_plans)
    assert sales_service.due_runs == [
        {
            'bot_uuid': 'bot-uuid',
            'target_type': 'person',
            'target_id': 'customer-1',
        }
    ]
    assert any(
        plan['segment'] == 'course-sales:opening:text'
        and plan['message_components'] == [{'type': 'plain', 'text': COURSE_OPENING_MESSAGE}]
        for plan in sales_service.plans
    )
    assert any(
        plan['segment'] == 'course-sales:opening:resource-card'
        and plan['message_components'][0]['type'] == 'link'
        and plan['message_components'][0]['url'] == COURSE_RESOURCE_CARD_LINK
        for plan in sales_service.plans
    )
    assert any(
        plan['segment'] == 'course-sales:opening:open-check'
        and plan['message_components'] == [{'type': 'plain', 'text': '家长，您这边能打开吗？'}]
        for plan in sales_service.plans
    )
    broadcast_plans = [plan for plan in sales_service.plans if plan['segment'] == 'course-sales:broadcast']
    assert len(broadcast_plans) == len(query.pipeline_config['workflow']['long_term_broadcasts'])
    assert all(component['type'] == 'plain' for plan in broadcast_plans for component in plan['message_components'])
    assert all(
        'sop_doc_media' not in str(plan['message_components']).lower()
        and 'image1.png' not in str(plan['message_components']).lower()
        and 'image2.png' not in str(plan['message_components']).lower()
        and 'image3.png' not in str(plan['message_components']).lower()
        for plan in broadcast_plans
    )
    assert not any(plan['segment'] == 'course-sales:followup:purchase' for plan in sales_service.plans)
    assert any(plan['segment'] == 'course-sales:followup:silence_revisit' for plan in sales_service.plans)


@pytest.mark.asyncio
async def test_course_sales_first_contact_skips_duplicate_opening_when_welcome_exists():
    sales_service = _CourseOutreachSalesService(user_message_count=1)
    sales_service.plans.append(
        {
            'bot_uuid': 'bot-uuid',
            'target_type': 'person',
            'target_id': 'customer-1',
            'segment': 'course-sales:opening:text',
            'message_components': [{'type': 'plain', 'text': COURSE_OPENING_MESSAGE}],
        }
    )
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    query = _query(text_chain('好的'), '好的', session_id='customer-1')
    query.pipeline_config = {'workflow': service.build_course_sales_workflow_config()}
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = COURSE_SALES_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    opening_plans = [plan for plan in sales_service.plans if plan['segment'].startswith('course-sales:opening')]
    assert len(opening_plans) == 1
    assert not any(plan['segment'] == 'course-sales:broadcast' for plan in sales_service.plans)


@pytest.mark.asyncio
async def test_course_sales_handoff_keyword_opens_handoff_and_stops_outreach():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    query = _query(text_chain('我要转人工，找真人客服'), '我要转人工，找真人客服', session_id='customer-handoff')
    query.pipeline_config = {'workflow': service.build_course_sales_workflow_config()}
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = COURSE_SALES_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'handoff'
    assert intent['handoff_reason'] == 'manual_request'
    assert sales_service.handoffs[0]['reason'] == 'manual_request'
    assert sales_service.handoffs[0]['message_text'] == '我要转人工，找真人客服'
    assert sales_service.disabled[0]['segment_prefixes'] == ['course-sales:']
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '本轮只回复安抚话术：“我这边帮您记录好了，稍等我看下具体情况~”' in context_text
    assert '不要继续促单' in context_text


@pytest.mark.asyncio
async def test_course_sales_handoff_does_not_trigger_on_ambiguous_service_word():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    query = _query(text_chain('客服发的链接在哪里打开'), '客服发的链接在哪里打开', session_id='customer-service-word')
    query.pipeline_config = {'workflow': service.build_course_sales_workflow_config()}
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = COURSE_SALES_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    assert query.variables['workflow_intent']['intent'] != 'handoff'
    assert sales_service.handoffs == []
    assert sales_service.disabled == []


@pytest.mark.asyncio
async def test_course_sales_handoff_semantic_payment_issue_uses_configured_boundary():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    workflow = service.build_course_sales_workflow_config(
        template_config={
            'human_handoff': {
                'enabled': True,
                'keywords': ['退费'],
                'semantic_triggers': [
                    {
                        'id': 'payment_issue',
                        'label': '支付订单异常',
                        'description': '用户已支付但看不到课程、订单异常、要求退款或退费',
                        'enabled': True,
                    }
                ],
                'stop_ai_reply': True,
                'stop_outreach': True,
                'notify_message': '我这边帮您记录好了，稍等我看下具体情况~',
            }
        }
    )
    query = _query(text_chain('我已经付了但是看不到课'), '我已经付了但是看不到课', session_id='customer-pay-issue')
    query.pipeline_config = {'workflow': workflow}
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = COURSE_SALES_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'handoff'
    assert intent['handoff_reason'] == 'payment_issue'
    assert sales_service.handoffs[0]['reason'] == 'payment_issue'
    assert sales_service.disabled[0]['segment_prefixes'] == ['course-sales:']
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '我这边帮您记录好了，稍等我看下具体情况~' in context_text


@pytest.mark.asyncio
async def test_course_sales_abusive_rejection_opens_handoff_and_stops_all_outreach():
    sales_service = _PersistingRejectionSalesService(user_message_count=3)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    query = _query(text_chain('cnm 我不买了 你这个骗子'), 'cnm 我不买了 你这个骗子', session_id='customer-anger')
    query.pipeline_config = {'workflow': service.build_course_sales_workflow_config()}
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = COURSE_SALES_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert query.variables['workflow_intent']['intent'] == 'handoff'
    assert query.variables['workflow_intent']['handoff_reason'] == 'high_risk_complaint'
    assert sales_service.handoffs[0]['reason'] == 'high_risk_complaint'
    assert sales_service.disabled
    assert sales_service.disabled[0]['segment_prefixes'] == ['course-sales:']
    assert sales_service.plans == []
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '我这边帮您记录好了，稍等我看下具体情况~' in context_text


@pytest.mark.asyncio
async def test_course_sales_purchased_stops_promotional_outreach_and_schedules_excel_qr_image():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    query = _query(text_chain('我已经报名成功了'), '我已经报名成功了', session_id='customer-2')
    query.pipeline_config = {'workflow': service.build_course_sales_workflow_config()}
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = COURSE_SALES_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    assert sales_service.disabled
    assert sales_service.disabled[0]['segment_prefixes'] == ['course-sales:broadcast', 'course-sales:followup']
    assert not any(plan['segment'] == 'course-sales:broadcast' for plan in sales_service.plans)
    assert any(
        component.get('type') == 'image'
        and component.get('file_key') == 'course-sales/phonics/gift_qr.jpeg'
        for plan in sales_service.plans
        for component in plan['message_components']
    )


def test_enhanced_yuanfudao_template_loads_spreadsheet_business_content():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    template = config['template_config']
    workflow = service.active_workflow_from_config(config)

    assert template['name'] == '猿辅导销售助手加强版'
    assert workflow['name'] == '猿辅导销售助手加强版'
    assert workflow['metadata']['scenario'] == COURSE_SALES_SCENARIO
    assert {profile['key'] for profile in template['course_profiles']} == {'phonics', 'reading_thinking'}
    assert template['course_profiles'][0]['facts']['price'] == '9元体验'
    assert any(faq['intent'] == 'reading_thinking_intro' for faq in template['course_faqs'])
    assert any(sequence['stage'] == 'reading_thinking_purchase' for sequence in template['followup_sequences'])
    source_names = '\n'.join(template['source_materials'])
    assert '猿辅导销售知识库索引' in source_names
    assert 'yuanfudao_knowledge_index.md' in source_names
    assert 'yuanfudao_markdown_corpus.md' in source_names
    assert '猿辅导1天2次群发SOP.xlsx' in source_names
    assert '猿辅导课程问答整理.xlsx' in source_names
    assert '猿辅导自然拼读常见问题(1).xlsx' in source_names
    assert template['metadata']['knowledge_pack']['path'] == 'templates/course-sales/yuanfudao-knowledge'
    assert template['metadata']['knowledge_pack']['freshness_range'] == '2024-2026'
    assert '不要整段塞话术' in template['role_prompt']
    assert '课程统一口径：' not in template['role_prompt']
    assert template['stop_policy']['explicit_rejection_threshold'] == 2


def test_yuanfudao_enhanced_template_links_knowledge_base():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    template = config['template_config']

    assert YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID in template['knowledge_base_uuids']
    assert template['tools']['knowledge_base'] is True
    assert config['ai']['local-agent']['knowledge-bases'] == [YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID]


def test_yuanfudao_template_refresh_ignores_legacy_source_materials():
    service = TaskAssistantService(SimpleNamespace())
    stale_overrides = {
        'source_materials': [
            '猿辅导1天2次群发SOP.xlsx',
            '猿辅导课程问答整理.xlsx',
            '猿辅导自然拼读常见问题(1).xlsx',
        ],
    }

    config = service.build_course_sales_template_config(
        overrides=stale_overrides,
        template_slug='yuanfudao-enhanced',
    )
    source_names = '\n'.join(config['source_materials'])

    assert 'yuanfudao_knowledge_index.md' in source_names
    assert '猿辅导销售知识库索引' in source_names


@pytest.mark.asyncio
async def test_ensure_yuanfudao_sales_knowledge_base_inserts_record():
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(side_effect=[_EmptyListResult(), _FirstResult(None), None])
        ),
        rag_mgr=SimpleNamespace(
            load_knowledge_base=AsyncMock(return_value=SimpleNamespace(_on_kb_create=AsyncMock())),
            get_knowledge_base_by_uuid=AsyncMock(return_value=None),
            remove_knowledge_base_from_runtime=AsyncMock(),
        ),
        plugin_connector=SimpleNamespace(is_enable_plugin=False),
        knowledge_service=SimpleNamespace(
            get_files_by_knowledge_base=AsyncMock(return_value=[]),
            _check_doc_capability=AsyncMock(),
            store_file=AsyncMock(),
        ),
        storage_mgr=SimpleNamespace(storage_provider=SimpleNamespace(save=AsyncMock())),
        logger=SimpleNamespace(warning=lambda *_: None),
    )
    service = TaskAssistantService(ap)
    service._is_usable_embedding_model_uuid = AsyncMock(return_value=False)
    service._import_yuanfudao_knowledge_documents_if_needed = AsyncMock()

    await service._ensure_yuanfudao_sales_knowledge_base()

    insert_statement = ap.persistence_mgr.execute_async.await_args_list[2].args[0]
    params = insert_statement.compile().params
    assert params['uuid'] == YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID
    assert params['name'] == '猿辅导销售知识库'
    assert params['knowledge_engine_plugin_id'] == 'langbot/BuiltinRAG'


@pytest.mark.asyncio
async def test_delete_retired_yuanfudao_seed_documents_removes_only_retired_pdf():
    knowledge_service = SimpleNamespace(
        get_files_by_knowledge_base=AsyncMock(
            return_value=[
                {
                    'uuid': 'retired-file-id',
                    'file_name': '猿辅导介绍0317.pdf',
                },
                {
                    'uuid': 'active-file-id',
                    'file_name': '猿辅导课程问答整理.xlsx',
                },
            ]
        ),
        delete_file=AsyncMock(),
    )
    logger = SimpleNamespace(info=Mock(), warning=Mock())
    service = TaskAssistantService(SimpleNamespace())

    await service._delete_retired_yuanfudao_seed_documents(knowledge_service, logger)

    knowledge_service.delete_file.assert_awaited_once_with(
        YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID,
        'retired-file-id',
    )
    logger.info.assert_called_once()
    logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_enhanced_runtime_selects_reading_thinking_product_from_config():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query = _query(text_chain('孩子阅读作文没头绪，数学思维也不会变通'), '孩子阅读作文没头绪，数学思维也不会变通', session_id='customer-reading')
    query.pipeline_config = config
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = 'yuanfudao-enhanced-template-pipeline'
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    intent = query.variables['workflow_intent']
    assert intent['product_key'] == 'reading_thinking'
    assert intent['selected_product_uuid'] == 'yuanfudao-reading-thinking-course'
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '阅读+思维' in context_text
    assert any(plan['segment'] == 'course-sales:followup:reading_thinking_purchase' for plan in sales_service.plans)


@pytest.mark.asyncio
async def test_enhanced_runtime_appends_yuanfudao_knowledge_pack_context():
    service = TaskAssistantService(SimpleNamespace(sales_service=None, logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query = _query(text_chain('私域SOP和课程货盘怎么说'), '私域SOP和课程货盘怎么说', session_id='customer-knowledge')
    query.pipeline_config = config
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = 'yuanfudao-enhanced-template-pipeline'
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '[猿辅导知识库参考]' in context_text
    assert '不得复述参考资料原文' in context_text
    assert '自然拼读' in context_text
    assert '最新活动页和班主任通知为准' in context_text
    knowledge_section = context_text.split('[猿辅导知识库参考]', 1)[1]
    assert len(knowledge_section.strip()) <= 250


def test_compose_course_sales_prompt_is_compact_persona_only():
    service = TaskAssistantService(SimpleNamespace())
    prompt = service.compose_course_sales_prompt()

    assert '不要自称 AI' in prompt
    assert '不要整段塞话术' in prompt
    assert '不得输出 xxx、XXXX' in prompt
    assert '课程统一口径：' not in prompt
    assert '图书资源FAQ：' not in prompt
    assert '雷达模拟规则：' not in prompt


def test_course_sales_pipeline_avoids_duplicate_system_and_enables_multimodal_aggregation():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    system_prompts = [
        message['content']
        for message in config['ai']['local-agent']['prompt']
        if message.get('role') == 'system'
    ]
    assert len(system_prompts) == 1
    assert '不要整段塞话术' in system_prompts[0]
    assert config['trigger']['message-aggregation']['enabled'] is True
    assert config['trigger']['message-aggregation']['delay'] == 10.0
    assert config['template_config']['reply_controls']['merge_reply_enabled'] is True
    assert config['template_config']['reply_controls']['merge_delay_seconds'] == 10.0
    assert config['template_config']['reply_controls']['multi_reply_enabled'] is True
    assert config['output']['misc']['multi-reply']['enabled'] is True
    assert config['output']['force-delay'] == {'min': 0, 'max': 0}
    assert config['ai']['local-agent']['rerank-top-k'] == 2


def test_course_sales_reply_controls_override_runtime_aggregation_and_multi_reply():
    service = TaskAssistantService(SimpleNamespace())
    existing_config = {
        'template_config': {
            'reply_controls': {
                'merge_reply_enabled': False,
                'merge_delay_seconds': 3,
                'multi_reply_enabled': True,
            },
        },
    }

    config = service.build_course_sales_template_pipeline_config(
        template_slug='yuanfudao-enhanced',
        existing_config=existing_config,
    )

    assert config['template_config']['reply_controls']['merge_reply_enabled'] is False
    assert config['template_config']['reply_controls']['merge_delay_seconds'] == 3
    assert config['template_config']['reply_controls']['multi_reply_enabled'] is True
    assert config['trigger']['message-aggregation']['enabled'] is False
    assert config['trigger']['message-aggregation']['delay'] == 3.0
    assert config['output']['misc']['multi-reply'] == {'enabled': True, 'threshold': 200}


def test_select_yuanfudao_knowledge_snippets_only_on_match_and_short():
    service = TaskAssistantService(SimpleNamespace())

    assert service._select_yuanfudao_knowledge_snippets('你好') == []
    snippets = service._select_yuanfudao_knowledge_snippets('自然拼读卖点话术怎么说')
    assert len(snippets) == 1
    assert len(snippets[0]) <= 200


@pytest.mark.asyncio
async def test_course_sales_faq_short_answer_for_single_question():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query = _query(text_chain('什么时候上课'), '什么时候上课', session_id='faq-short')
    query.pipeline_config = config
    query.variables['_knowledge_base_uuids'] = [YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID]
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'course_schedule'
    assert intent.get('faq_short_answer')
    assert intent.get('reply_mode') == 'faq_polish'
    assert query.variables['_knowledge_base_uuids'] == []
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '[短答模板]' in context_text
    assert '先准确说明自然拼读课分两周上' in context_text
    assert '自然、生动地催一下家长给孩子试试' in context_text
    assert '再按课程销售上下文自然、生动地承接报名和活动礼物' in context_text
    assert '[猿辅导知识库参考]' not in context_text


@pytest.mark.asyncio
async def test_course_sales_conflict_context_pushes_gift_and_signup_link():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query = _query(text_chain('和其他课有冲突么'), '和其他课有冲突么', session_id='course-conflict')
    query.pipeline_config = config
    query.variables['_knowledge_base_uuids'] = [YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID]
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'course_conflict'
    assert intent.get('faq_short_answer')
    assert '小猿篮球/护脊书包/小猿手办/宇航员文具盒/铅笔/转笔刀' in intent['faq_short_answer']
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '自然拼读报名链接卡片SOP' in context_text
    assert '赠送实物名额就这一周有' in context_text
    assert '报名链接卡片' in context_text


@pytest.mark.asyncio
async def test_course_sales_replay_context_pushes_gift_and_signup_link():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query = _query(text_chain('支持回放么'), '支持回放么', session_id='course-replay')
    query.pipeline_config = config
    query.variables['_knowledge_base_uuids'] = [YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID]
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'course_replay'
    assert intent.get('faq_short_answer')
    assert '每次也就一小时左右' in intent['faq_short_answer']
    assert '要不要试试看' in intent['faq_short_answer']
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '用户询问是否支持回放' in context_text
    assert '完课后随机发货其一' in context_text
    assert '报名链接卡片' in context_text


@pytest.mark.asyncio
async def test_course_sales_content_context_pushes_gift_and_signup_link():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query = _query(text_chain('学习内容是什么'), '学习内容是什么', session_id='course-content')
    query.pipeline_config = config
    query.variables['_knowledge_base_uuids'] = [YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID]
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'course_content'
    assert intent.get('faq_short_answer')
    assert '每个年级的学习内容不一样' in intent['faq_short_answer']
    assert '根据孩子年级匹配' in intent['faq_short_answer']
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '用户询问学习内容' in context_text
    assert '不要复述“这个是什么课”的课程介绍' in context_text
    assert '报名链接卡片' in context_text


@pytest.mark.asyncio
async def test_course_sales_intro_context_includes_details_and_signup_link():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query = _query(text_chain('这个是什么课'), '这个是什么课', session_id='course-intro')
    query.pipeline_config = config
    query.variables['_knowledge_base_uuids'] = [YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID]
    query.prompt = SimpleNamespace(messages=[])

    result = await service.prepare_query(query)

    assert result['handled'] is True
    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'course_intro'
    assert intent.get('faq_short_answer')
    assert intent.get('step_ids') == []
    assert '5次绘本阅读实践' in intent['faq_short_answer']
    assert '180次开口练习' in intent['faq_short_answer']
    assert '360分钟配套视频' in intent['faq_short_answer']
    assert '报名链接我发您' in intent['faq_short_answer']


@pytest.mark.asyncio
async def test_prepare_query_does_not_inject_duplicate_system_prompt():
    service = TaskAssistantService(SimpleNamespace())
    config = service.build_course_sales_template_pipeline_config()
    existing_prompt = provider_message.Message(role='system', content='pipeline system prompt')
    query = _query(text_chain('什么时候上课'), '什么时候上课', session_id='no-dup')
    query.pipeline_config = config
    query.prompt = SimpleNamespace(messages=[existing_prompt])

    await service.prepare_query(query)

    assert len(query.prompt.messages) == 1
    assert query.prompt.messages[0].content == 'pipeline system prompt'


@pytest.mark.asyncio
async def test_enhanced_runtime_stops_after_second_explicit_rejection():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    first_query = _query(text_chain('不需要'), '不需要', session_id='customer-reject')
    first_query.pipeline_config = config
    first_query.bot_uuid = 'bot-uuid'
    first_query.pipeline_uuid = 'yuanfudao-enhanced-template-pipeline'
    first_query.prompt = SimpleNamespace(messages=[])
    await service.prepare_query(first_query)

    assert sales_service.disabled == []
    assert first_query.variables['workflow_intent']['intent'] == 'objection'
    assert first_query.variables['workflow_intent']['explicit_rejection_count'] == 1
    assert not any(plan['segment'] == 'course-sales:followup:not_buy' for plan in sales_service.plans)

    second_query = _query(text_chain('不要再发了'), '不要再发了', session_id='customer-reject')
    second_query.pipeline_config = config
    second_query.bot_uuid = 'bot-uuid'
    second_query.pipeline_uuid = 'yuanfudao-enhanced-template-pipeline'
    second_query.prompt = SimpleNamespace(messages=[])
    await service.prepare_query(second_query)

    assert sales_service.disabled
    assert sales_service.disabled[0]['segment_prefixes'] == ['course-sales:']
    assert second_query.variables['workflow_intent']['intent'] == 'stop'
    assert second_query.variables['workflow_intent']['explicit_rejection_count'] == 2


@pytest.mark.asyncio
async def test_enhanced_runtime_keeps_text_image_and_voice_reply_modes_distinct():
    service = TaskAssistantService(SimpleNamespace(sales_service=_CourseOutreachSalesService(user_message_count=2), logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    text_query_obj = _query(text_chain('什么时候上课'), '什么时候上课', session_id='customer-text')
    text_query_obj.pipeline_config = config
    text_query_obj.prompt = SimpleNamespace(messages=[])
    await service.prepare_query(text_query_obj)
    assert text_query_obj.variables['task_assistant_voice_reply'] is False

    voice_query_obj = voice_query('https://example.com/audio.mp3')
    voice_query_obj.pipeline_config = config
    voice_query_obj.variables = {'user_message_text': '什么时候上课'}
    voice_query_obj.prompt = SimpleNamespace(messages=[])
    voice_query_obj.user_message = provider_message.Message(
        role='user',
        content=[provider_message.ContentElement.from_file_url('https://example.com/audio.mp3', 'voice')],
    )
    await service.prepare_query(voice_query_obj)
    assert voice_query_obj.variables['task_assistant_voice_reply'] is True

    image_query_obj = _query(
        image_chain(text='帮我看下这个报名截图', url='https://example.com/signup.png'),
        '帮我看下这个报名截图',
        session_id='customer-image',
    )
    image_query_obj.pipeline_config = config
    image_query_obj.prompt = SimpleNamespace(messages=[])
    await service.prepare_query(image_query_obj)

    assert image_query_obj.variables['workflow_intent']['intent'] == 'screenshot_help'
    assert any(item.type.startswith('image') for item in image_query_obj.user_message.content)


@pytest.mark.asyncio
async def test_course_sales_screenshot_text_does_not_trigger_purchased_intent():
    service = TaskAssistantService(SimpleNamespace(sales_service=None, logger=SimpleNamespace(warning=lambda *_: None)))
    workflow = service.build_course_sales_workflow_config()

    screenshot_intent = service.classify_course_sales_intent('我发截图给你看看报名页', text_chain('我发截图给你看看报名页'), workflow)
    purchased_intent = service.classify_course_sales_intent('我已经支付成功了', text_chain('我已经支付成功了'), workflow)

    assert screenshot_intent['intent'] == 'screenshot_help'
    assert purchased_intent['intent'] == 'purchased'


@pytest.mark.asyncio
async def test_course_sales_payment_screenshot_stops_promotional_outreach_before_reply():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = _query(
        image_chain(text='支付成功截图', url='https://example.com/paid.png'),
        '支付成功截图',
        session_id='customer-paid-image',
    )
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    assert query.variables['workflow_intent']['intent'] == 'purchased'
    assert sales_service.disabled == [
        {
            'bot_uuid': 'bot-uuid',
            'target_type': 'person',
            'target_id': 'customer-paid-image',
            'segment_prefixes': ['course-sales:broadcast', 'course-sales:followup'],
        }
    ]


@pytest.mark.asyncio
async def test_course_sales_resource_question_takes_priority_over_purchase_keyword():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = _query(text_chain('答案在哪里看，我要买课'), '答案在哪里看，我要买课', session_id='customer-resource-first')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    assert query.variables['workflow_intent']['intent'] == 'resource_help'
    assert sales_service.plans == []
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '先解决图书资源问题' in context_text
    assert '本轮要给报名动作和报名链接卡片' not in context_text


@pytest.mark.asyncio
async def test_course_sales_resource_open_failure_context_requests_resend_link_and_screenshot():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = _query(text_chain('不能打开'), '不能打开', session_id='customer-resource-fail')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    assert query.variables['workflow_intent']['intent'] == 'resource_help'
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '再发一遍图书配套学习资源卡片链接' in context_text
    assert '方便发我一张截图吗' in context_text
    assert '不要再问“能打开吗”' in context_text
    assert '本轮要给报名动作和报名链接卡片' not in context_text


@pytest.mark.asyncio
async def test_course_sales_explicit_rejection_does_not_push_purchase_link_this_turn():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = _query(text_chain('不需要，别发链接了'), '不需要，别发链接了', session_id='customer-reject-link')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'objection'
    assert intent['explicit_rejection_count'] == 1
    assert sales_service.plans == []
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '不要发报名链接' in context_text
    assert '本轮要给报名动作和报名链接卡片' not in context_text


@pytest.mark.parametrize('message_text', ['不想领取', '没兴趣', '不想报名', '不感兴趣'])
@pytest.mark.asyncio
async def test_course_sales_first_rejection_probes_reason_without_signup_link(message_text):
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = _query(text_chain(message_text), message_text, session_id=f'customer-reject-{message_text}')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    intent = query.variables['workflow_intent']
    assert intent['intent'] == 'objection'
    assert intent['explicit_rejection_count'] == 1
    assert 'link_url' not in intent
    assert sales_service.plans == []
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '不要发报名链接' in context_text
    assert '追问拒绝原因' in context_text
    assert '孩子没时间' in context_text
    assert '觉得不值得' in context_text
    assert '已经学过' in context_text
    assert '本轮要给报名动作和报名链接卡片' not in context_text


@pytest.mark.asyncio
async def test_course_sales_already_registered_moves_to_delivery_support_not_resale():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = _query(text_chain('我已经报名了，资料怎么领取'), '我已经报名了，资料怎么领取', session_id='customer-already-paid')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    assert query.variables['workflow_intent']['intent'] == 'purchased'
    assert sales_service.disabled == [
        {
            'bot_uuid': 'bot-uuid',
            'target_type': 'person',
            'target_id': 'customer-already-paid',
            'segment_prefixes': ['course-sales:broadcast', 'course-sales:followup'],
        }
    ]
    assert not any(plan['segment'] == 'course-sales:followup:purchase' for plan in sales_service.plans)
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '转成交后交付' in context_text
    assert '本轮要给报名动作和报名链接卡片' not in context_text


@pytest.mark.asyncio
async def test_course_sales_smalltalk_does_not_inject_sales_script_or_followup():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = _query(text_chain('今天天气真不错'), '今天天气真不错', session_id='customer-smalltalk')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    assert query.variables['workflow_intent']['intent'] == 'smalltalk'
    assert sales_service.plans == []
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '[猿辅导知识库参考]' not in context_text
    assert '当前选中课程' not in context_text
    assert '报名链接' not in context_text


@pytest.mark.asyncio
async def test_course_sales_unclear_text_asks_low_friction_clarification_without_followup():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    query = _query(text_chain('嗯'), '嗯', session_id='customer-unclear')
    query.pipeline_config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    assert query.variables['workflow_intent']['intent'] == 'clarification'
    assert query.variables['workflow_intent']['confidence'] < 0.7
    assert sales_service.plans == []
    context_text = '\n'.join(item.text for item in query.user_message.content if item.type == 'text')
    assert '只问一个低压力澄清问题' in context_text
    assert '图书资源' in context_text
    assert '课程信息' in context_text
    assert '报名链接' not in context_text


def test_enhanced_yuanfudao_template_uses_latest_tracking_destination_link():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    template = config['template_config']
    links_by_id = {link['id']: link for link in template['sales_links']}

    assert 'yingtao3class' in template['radar']['link_url']
    assert 'reduceProxy' not in template['radar']['link_url']
    assert links_by_id['phonics_radar_apply']['url'] == template['radar']['link_url']


@pytest.mark.asyncio
async def test_enhanced_runtime_persists_explicit_rejection_count_across_service_restart():
    sales_service = _PersistingRejectionSalesService(user_message_count=2)
    config = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    ).build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    first_service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    first_query = _query(text_chain('不需要'), '不需要', session_id='customer-reject-persist')
    first_query.pipeline_config = config
    first_query.bot_uuid = 'bot-uuid'
    first_query.pipeline_uuid = 'yuanfudao-enhanced-template-pipeline'
    first_query.prompt = SimpleNamespace(messages=[])
    await first_service.prepare_query(first_query)

    assert first_query.variables['workflow_intent']['explicit_rejection_count'] == 1
    assert sales_service.rejection_counts['person_customer-reject-persist'] == 1

    restarted_service = TaskAssistantService(
        SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None))
    )
    second_query = _query(text_chain('别推了'), '别推了', session_id='customer-reject-persist')
    second_query.pipeline_config = config
    second_query.bot_uuid = 'bot-uuid'
    second_query.pipeline_uuid = 'yuanfudao-enhanced-template-pipeline'
    second_query.prompt = SimpleNamespace(messages=[])
    await restarted_service.prepare_query(second_query)

    assert second_query.variables['workflow_intent']['intent'] == 'stop'
    assert second_query.variables['workflow_intent']['explicit_rejection_count'] == 2


def test_enhanced_yuanfudao_template_exposes_multimodal_defaults():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    template = config['template_config']
    workflow = service.active_workflow_from_config(config)

    assert template['voice']['enabled'] is True
    assert template['voice']['provider'] == 'volcengine'
    assert template['voice']['voice_type'] == COURSE_SALES_TTS_VOICE_TYPE
    assert template['asr']['provider'] == 'volcengine'
    assert template['asr']['model_uuid'] == 'lna-doubao-bigasr-flash'
    assert template['screenshot_input']['target_steps'] == ['gift_poster', 'gift_qr', 'link_error']
    assert template['screenshot_input']['image_intents'] == ['screenshot_help', 'purchased', 'link_error']

    voice_asr = next(node for node in workflow['nodes'] if node['id'] == 'voice_asr')
    screenshot_input = next(node for node in workflow['nodes'] if node['id'] == 'screenshot_input')
    intent_node = next(node for node in workflow['nodes'] if node['id'] == 'intent')

    assert voice_asr['config']['provider'] == 'volcengine'
    assert voice_asr['config']['model_uuid'] == 'lna-doubao-bigasr-flash'
    assert voice_asr['config']['fallback_text'] == template['asr']['fallback_text']
    assert screenshot_input['config']['target_steps'] == template['screenshot_input']['target_steps']
    assert intent_node['config']['image_intents'] == template['screenshot_input']['image_intents']


def test_task_assistant_template_pipeline_preserves_existing_workflow():
    service = TaskAssistantService(SimpleNamespace())
    existing_workflow = {
        'version': 1,
        'name': 'custom workflow kept independent',
        'metadata': {'scenario': 'custom'},
        'nodes': [],
        'edges': [],
    }

    config = service.build_template_pipeline_config(
        existing_config={
            'workflow': existing_workflow,
            'template_config': {'name': 'template changed only'},
        },
    )

    assert config['workflow'] == existing_workflow
    assert config['template_config']['name'] == 'template changed only'


def test_template_mode_active_workflow_uses_template_config_without_mutating_saved_workflow():
    service = TaskAssistantService(SimpleNamespace())
    saved_workflow = {
        'version': 1,
        'metadata': {'scenario': 'custom-workflow'},
        'nodes': [],
        'edges': [],
    }
    template_config = service.build_template_config(
        overrides={
            'voice': {'app_id': 'template-app', 'token': 'template-token'},
            'interaction_radar': {
                'enabled': True,
                'link_url': 'https://example.com/course',
                'click_reply': '我看到您刚刚点开了课程链接。',
            },
            'image_text_bindings': [
                {
                    'step_id': 'download_qr',
                    'title': 'custom uploaded step',
                    'text': 'custom uploaded text',
                    'file_key': 'uploads/custom-step.png',
                    'trigger_intents': ['task_overview'],
                    'enabled': True,
                },
            ],
        }
    )
    pipeline_config = {
        'config_mode': 'template',
        'workflow': saved_workflow,
        'template_config': template_config,
    }

    active_workflow = service.active_workflow_from_config(pipeline_config)

    assert active_workflow is not saved_workflow
    assert active_workflow['metadata']['scenario'] == 'task_assistant_ant_af'
    assert active_workflow['voice']['app_id'] == 'template-app'
    assert active_workflow['interaction_radar']['link_url'] == 'https://example.com/course'
    assert active_workflow['variables']['interaction_radar']['click_reply'] == '我看到您刚刚点开了课程链接。'
    image_node = next(node for node in active_workflow['nodes'] if node['id'] == 'image_download_qr')
    assert image_node['config']['file_key'] == 'uploads/custom-step.png'
    assert saved_workflow['nodes'] == []
    assert service.is_task_assistant_pipeline(pipeline_config) is True


@pytest.mark.asyncio
async def test_synthesize_reply_voice_uses_lark_friendly_ogg_opus_by_default(monkeypatch):
    logger = SimpleNamespace(warning=Mock())
    service = TaskAssistantService(SimpleNamespace(logger=logger))
    invoke_mock = AsyncMock(return_value='ZmFrZS1hdWRpbw==')
    monkeypatch.setattr(
        'langbot.pkg.api.http.service.task_assistant.tts_invoke.invoke_tts',
        invoke_mock,
    )
    query = SimpleNamespace(
        variables={'task_assistant_voice_reply': True},
        pipeline_config={
            'workflow': {
                'metadata': {'scenario': 'task_assistant_ant_af'},
                'voice': {'enabled': True, 'app_id': 'app-id', 'token': 'token'},
            },
        },
    )

    result = await service.synthesize_reply_voice(query, '下一步我带你点实名认证。')

    assert result == 'data:audio/ogg;base64,ZmFrZS1hdWRpbw=='
    invoke_mock.assert_awaited_once()
    config = invoke_mock.await_args.args[0]
    assert config.encoding == 'ogg_opus'


@pytest.mark.asyncio
async def test_synthesize_reply_voice_uses_template_voice_config_in_template_mode(monkeypatch):
    logger = SimpleNamespace(warning=Mock())
    service = TaskAssistantService(SimpleNamespace(logger=logger))
    invoke_mock = AsyncMock(return_value='ZmFrZS10ZW1wbGF0ZQ==')
    monkeypatch.setattr(
        'langbot.pkg.api.http.service.task_assistant.tts_invoke.invoke_tts',
        invoke_mock,
    )
    query = SimpleNamespace(
        variables={'task_assistant_voice_reply': True},
        pipeline_config={
            'config_mode': 'template',
            'workflow': {'metadata': {'scenario': 'custom-workflow'}, 'voice': {'app_id': 'saved-app'}},
            'template_config': {
                'voice': {
                    'enabled': True,
                    'app_id': 'template-app',
                    'token': 'template-token',
                    'voice_type': 'template-voice',
                    'encoding': 'ogg_opus',
                },
            },
        },
    )

    result = await service.synthesize_reply_voice(query, '下一步我带你点实名认证。')

    assert result == 'data:audio/ogg;base64,ZmFrZS10ZW1wbGF0ZQ=='
    invoke_mock.assert_awaited_once()
    config = invoke_mock.await_args.args[0]
    assert config.app_id == 'template-app'
    assert config.token == 'template-token'
    assert config.voice_type == 'template-voice'


@pytest.mark.asyncio
async def test_synthesize_reply_voice_uses_selected_voice_model_config(monkeypatch):
    logger = SimpleNamespace(warning=Mock())
    voice_model = SimpleNamespace(
        uuid='voice-model-1',
        provider_uuid='provider-1',
        extra_args={
            'app_id': 'extra-app',
            'cluster': 'extra-cluster',
            'voice_type': 'extra-voice',
            'encoding': 'wav',
        },
    )
    provider = SimpleNamespace(
        uuid='provider-1',
        requester='volcengine-tts',
        name='Volcengine',
        base_url='https://openspeech.bytedance.com',
        api_keys=['provider-app', 'provider-token'],
    )
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(side_effect=[_FirstResult(voice_model), _FirstResult(provider)])
    )
    service = TaskAssistantService(SimpleNamespace(logger=logger, persistence_mgr=persistence_mgr))
    invoke_mock = AsyncMock(return_value='ZmFrZS12b2ljZQ==')
    monkeypatch.setattr(
        'langbot.pkg.api.http.service.task_assistant.tts_invoke.invoke_tts',
        invoke_mock,
    )
    query = SimpleNamespace(
        variables={'task_assistant_voice_reply': True},
        pipeline_config={
            'workflow': {
                'metadata': {'scenario': 'task_assistant_ant_af'},
                'voice': {'enabled': True, 'model_uuid': 'voice-model-1'},
            },
        },
    )

    result = await service.synthesize_reply_voice(query, '下一步我带你点实名认证。')

    assert result == 'data:audio/wav;base64,ZmFrZS12b2ljZQ=='
    invoke_mock.assert_awaited_once()
    config = invoke_mock.await_args.args[0]
    assert config.app_id == 'extra-app'
    assert config.token == 'provider-token'
    assert config.cluster == 'extra-cluster'
    assert config.voice_type == 'extra-voice'
    assert config.encoding == 'wav'
    assert config.requester == 'volcengine-tts'


@pytest.mark.asyncio
async def test_synthesize_reply_voice_uses_dashscope_qwen_tts_model_config(monkeypatch):
    logger = SimpleNamespace(warning=Mock())
    voice_model = SimpleNamespace(
        uuid='qwen-tts-model',
        name='qwen3-tts-flash',
        provider_uuid='dashscope-provider',
        extra_args={
            'provider': 'dashscope',
            'voice': 'Cherry',
            'voice_type': 'Cherry',
            'language_type': 'Chinese',
            'encoding': 'wav',
        },
    )
    provider = SimpleNamespace(
        uuid='dashscope-provider',
        requester='bailian-chat-completions',
        name='阿里云百炼 Qwen TTS',
        base_url='https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
        api_keys=['dashscope-token'],
    )
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(side_effect=[_FirstResult(voice_model), _FirstResult(provider)])
    )
    service = TaskAssistantService(SimpleNamespace(logger=logger, persistence_mgr=persistence_mgr))
    invoke_mock = AsyncMock(return_value='ZmFrZS1xd2VuLXR0cw==')
    monkeypatch.setattr(
        'langbot.pkg.api.http.service.task_assistant.tts_invoke.invoke_tts',
        invoke_mock,
    )
    query = SimpleNamespace(
        variables={'task_assistant_voice_reply': True},
        pipeline_config={
            'workflow': {
                'metadata': {'scenario': 'task_assistant_ant_af'},
                'voice': {'enabled': True, 'model_uuid': 'qwen-tts-model'},
            },
        },
    )

    result = await service.synthesize_reply_voice(query, '下一步我带你点实名认证。')

    assert result == 'data:audio/wav;base64,ZmFrZS1xd2VuLXR0cw=='
    invoke_mock.assert_awaited_once()
    config = invoke_mock.await_args.args[0]
    assert config.token == 'dashscope-token'
    assert config.model == 'qwen3-tts-flash'
    assert config.voice == 'Cherry'
    assert config.language_type == 'Chinese'
    assert config.base_url == provider.base_url


def test_parse_volcengine_tts_ws_audio_message_returns_audio_and_final_state():
    audio_bytes = b'fake-audio'
    sequence_number = -1
    message = (
        bytes([0x11, 0xB3, 0x00, 0x00])
        + sequence_number.to_bytes(4, 'big', signed=True)
        + len(audio_bytes).to_bytes(4, 'big')
        + audio_bytes
    )

    chunk, is_final = TaskAssistantService._parse_volcengine_tts_ws_audio_message(message)

    assert chunk == audio_bytes
    assert is_final is True


class _CourseOutreachSalesServiceWithTargetSend(_CourseOutreachSalesService):
    async def run_due_outreach_for_target(self, **kwargs):
        self.target_send = kwargs
        return 3


class _CourseOutreachSalesServiceWithRadarSend(_CourseOutreachSalesService):
    async def run_due_outreach_for_target(self, **kwargs):
        self.target_send = kwargs
        return 1


class _DedupingCourseOutreachSalesService(_CourseOutreachSalesService):
    def __init__(self, user_message_count=0):
        super().__init__(user_message_count=user_message_count)
        self._next_id = 1

    async def create_outreach_plan(self, data):
        dedupe_key = str(data.get('dedupe_key') or '')
        for plan in self.plans:
            if dedupe_key and plan.get('dedupe_key') == dedupe_key:
                if plan.get('last_sent_at') is not None and plan.get('enabled') is False:
                    return plan['id']
                plan.update(data)
                return plan['id']

        stored = dict(data)
        stored['id'] = self._next_id
        self._next_id += 1
        stored.setdefault('last_sent_at', None)
        self.plans.append(stored)
        return stored['id']

    async def run_due_outreach_for_target(self, **kwargs):
        now = datetime.datetime.now()
        sent = 0
        for plan in sorted(self.plans, key=lambda item: (item['scheduled_at'], item['id'])):
            if not plan.get('enabled'):
                continue
            if plan.get('scheduled_at') > now:
                continue
            if plan.get('bot_uuid') != kwargs.get('bot_uuid'):
                continue
            if plan.get('target_type') != kwargs.get('target_type'):
                continue
            if plan.get('target_id') != kwargs.get('target_id'):
                continue
            plan['last_sent_at'] = now
            plan['enabled'] = False
            sent += 1
        return sent


@pytest.mark.asyncio
async def test_handle_course_sales_contact_added_schedules_opening_and_broadcasts():
    sales_service = _CourseOutreachSalesServiceWithTargetSend(user_message_count=0)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    result = await service.handle_course_sales_contact_added(
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='ou_customer',
        pipeline_uuid='yuanfudao-enhanced-template-pipeline',
        user_id='ou_customer',
        pipeline_config=config,
    )

    assert result['handled'] is True
    assert result['scheduled'] is True
    assert result['sent_immediately'] == 3
    assert any(plan['segment'] == 'course-sales:opening:text' for plan in sales_service.plans)
    assert any(plan['segment'] == 'course-sales:opening:resource-card' for plan in sales_service.plans)
    assert any(plan['segment'] == 'course-sales:opening:open-check' for plan in sales_service.plans)
    assert len([plan for plan in sales_service.plans if plan['segment'] == 'course-sales:broadcast']) == len(
        config['workflow']['long_term_broadcasts']
    )


@pytest.mark.asyncio
async def test_handle_course_sales_contact_added_makes_opening_text_and_card_due_immediately():
    sales_service = _CourseOutreachSalesServiceWithTargetSend(user_message_count=0)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    await service.handle_course_sales_contact_added(
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='ou_customer',
        pipeline_uuid='yuanfudao-enhanced-template-pipeline',
        user_id='ou_customer',
        pipeline_config=config,
    )

    after = datetime.datetime.now()
    opening_segments = {
        'course-sales:opening:text',
        'course-sales:opening:resource-card',
        'course-sales:opening:open-check',
    }
    opening_plans = [plan for plan in sales_service.plans if plan['segment'] in opening_segments]
    assert len(opening_plans) == 3
    assert all(plan['scheduled_at'] <= after for plan in opening_plans)
    open_check = next(plan for plan in opening_plans if plan['segment'] == 'course-sales:opening:open-check')
    assert open_check['message_components'] == [{'type': 'plain', 'text': '家长，您这边能打开吗？'}]


@pytest.mark.asyncio
async def test_handle_course_sales_contact_added_sends_opening_before_broadcasts(monkeypatch):
    sales_service = _CourseOutreachSalesServiceWithTargetSend(user_message_count=0)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    observed = {}

    async def capture_broadcasts(_target, _workflow):
        observed['sent_before_broadcasts'] = getattr(sales_service, 'target_send', None) is not None

    monkeypatch.setattr(service, '_schedule_course_sales_broadcasts_for_target', capture_broadcasts)

    await service.handle_course_sales_contact_added(
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='ou_customer',
        pipeline_uuid='yuanfudao-enhanced-template-pipeline',
        user_id='ou_customer',
        pipeline_config=config,
    )

    assert observed == {'sent_before_broadcasts': True}


@pytest.mark.asyncio
async def test_handle_course_sales_contact_added_sends_welcome_only_once_per_target():
    sales_service = _DedupingCourseOutreachSalesService(user_message_count=0)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    first = await service.handle_course_sales_contact_added(
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='ou_customer',
        pipeline_uuid='yuanfudao-enhanced-template-pipeline',
        user_id='ou_customer',
        pipeline_config=config,
    )
    second = await service.handle_course_sales_contact_added(
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='ou_customer',
        pipeline_uuid='yuanfudao-enhanced-template-pipeline',
        user_id='ou_customer',
        pipeline_config=config,
    )

    assert first['sent_immediately'] == 3
    assert second['sent_immediately'] == 0
    opening_segments = {
        'course-sales:opening:text',
        'course-sales:opening:resource-card',
        'course-sales:opening:open-check',
    }
    opening_plans = [plan for plan in sales_service.plans if plan['segment'] in opening_segments]
    assert len(opening_plans) == 3
    assert all(plan['last_sent_at'] is not None and plan['enabled'] is False for plan in opening_plans)


@pytest.mark.asyncio
async def test_handle_course_sales_contact_added_skips_entered_event_after_user_messages():
    sales_service = _CourseOutreachSalesServiceWithTargetSend(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    result = await service.handle_course_sales_contact_added(
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='ou_customer',
        pipeline_uuid='yuanfudao-enhanced-template-pipeline',
        user_id='ou_customer',
        pipeline_config=config,
        source_event='im.chat.access_event.bot_p2p_chat_entered_v1',
    )

    assert result == {'handled': True, 'scheduled': False, 'reason': 'entered event ignored after user messages'}
    assert sales_service.plans == []
    assert not hasattr(sales_service, 'target_send')


@pytest.mark.asyncio
async def test_handle_course_sales_contact_added_skips_entered_event_after_existing_opening_plan():
    sales_service = _CourseOutreachSalesServiceWithTargetSend(user_message_count=0)
    sales_service.plans.append(
        {
            'bot_uuid': 'bot-uuid',
            'target_type': 'person',
            'target_id': 'ou_customer',
            'segment': 'course-sales:opening:text',
        }
    )
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')

    result = await service.handle_course_sales_contact_added(
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='ou_customer',
        pipeline_uuid='yuanfudao-enhanced-template-pipeline',
        user_id='ou_customer',
        pipeline_config=config,
        source_event='im.chat.access_event.bot_p2p_chat_entered_v1',
    )

    assert result == {'handled': True, 'scheduled': False, 'reason': 'entered event ignored after existing welcome plan'}
    assert len(sales_service.plans) == 1
    assert not hasattr(sales_service, 'target_send')


@pytest.mark.asyncio
async def test_course_sales_purchase_intent_schedules_silence_revisit():
    sales_service = _CourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    query = _query(text_chain('我想报名'), '我想报名', session_id='customer-silence')
    query.pipeline_config = {'workflow': service.build_course_sales_workflow_config()}
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = COURSE_SALES_TEMPLATE_PIPELINE_UUID
    query.prompt = SimpleNamespace(messages=[])

    await service.prepare_query(query)

    assert not any(plan['segment'] == 'course-sales:followup:purchase' for plan in sales_service.plans)
    assert any(plan['segment'] == 'course-sales:followup:silence_revisit' for plan in sales_service.plans)


@pytest.mark.asyncio
async def test_course_sales_radar_link_uses_tracking_url():
    sales_service = SimpleNamespace(
        build_radar_tracking_url=lambda **kwargs: "http://127.0.0.1:5300/api/v1/sales/radar/click/test-token",
    )
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    workflow = service.build_course_sales_workflow_config()
    target = {
        'bot_uuid': 'bot-uuid',
        'target_type': 'person',
        'target_id': 'customer-radar',
        'session_id': 'person_customer-radar',
        'pipeline_uuid': COURSE_SALES_TEMPLATE_PIPELINE_UUID,
    }
    links = service._course_sales_links_by_id(workflow)
    link = links['phonics_radar_apply']

    component = service._course_link_component(link, target=target, workflow=workflow)

    assert component['url'].startswith('http://127.0.0.1:5300/api/v1/sales/radar/click/')


@pytest.mark.asyncio
async def test_course_sales_radar_event_does_not_resend_signup_link_followup():
    sales_service = _CourseOutreachSalesServiceWithRadarSend(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    workflow = service.build_course_sales_workflow_config()

    result = await service.handle_course_sales_radar_event(
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='customer-radar',
        link_id='phonics_radar_apply',
        session_id='person_customer-radar',
        pipeline_uuid=COURSE_SALES_TEMPLATE_PIPELINE_UUID,
        event='link_open',
        pipeline_config={'workflow': workflow},
    )

    assert result['handled'] is True
    assert result['stage'] == 'silence_revisit'
    assert not any(plan['segment'] == 'course-sales:followup:radar_clicked' for plan in sales_service.plans)
    assert any(plan['segment'] == 'course-sales:followup:silence_revisit' for plan in sales_service.plans)
    radar_plan = next(plan for plan in sales_service.plans if plan['segment'] == 'course-sales:radar:link_open')
    assert all(component['type'] != 'link' for component in radar_plan['message_components'])
    assert radar_plan['message_components'] == [
        {
            'type': 'plain',
            'text': COURSE_SALES_AFTER_LINK_OPEN_MESSAGE,
        }
    ]
    assert sales_service.target_send == {
        'bot_uuid': 'bot-uuid',
        'target_type': 'person',
        'target_id': 'customer-radar',
    }


@pytest.mark.asyncio
async def test_course_sales_radar_event_sends_message_on_each_link_click():
    sales_service = _DedupingCourseOutreachSalesService(user_message_count=2)
    service = TaskAssistantService(SimpleNamespace(sales_service=sales_service, logger=SimpleNamespace(warning=lambda *_: None)))
    workflow = service.build_course_sales_workflow_config()
    kwargs = {
        'bot_uuid': 'bot-uuid',
        'target_type': 'person',
        'target_id': 'customer-radar',
        'link_id': 'phonics_radar_apply',
        'session_id': 'person_customer-radar',
        'pipeline_uuid': COURSE_SALES_TEMPLATE_PIPELINE_UUID,
        'event': 'link_open',
        'pipeline_config': {'workflow': workflow},
    }

    await service.handle_course_sales_radar_event(**kwargs)
    await service.handle_course_sales_radar_event(**kwargs)

    radar_plans = [plan for plan in sales_service.plans if plan['segment'] == 'course-sales:radar:link_open']
    assert len(radar_plans) == 2
    assert all(plan['last_sent_at'] is not None and plan['enabled'] is False for plan in radar_plans)


def test_enhanced_template_long_term_broadcasts_cover_excel_sop():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced')
    broadcasts = config['template_config']['long_term_broadcasts']

    assert len(broadcasts) == 49
    assert {item['day'] for item in broadcasts} == set(range(1, 39))
    assert any('180次开口练习' in item['message'] for item in broadcasts)
    assert all('最后3个' not in item['message'] for item in broadcasts)
    assert any(item['time'] == '15:40' for item in broadcasts)
    assert any(item['time'] == '21:20' for item in broadcasts)
