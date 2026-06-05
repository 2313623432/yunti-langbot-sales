from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.task_assistant import (
    TASK_ASSISTANT_MODEL_UUID,
    TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID,
    TASK_ASSISTANT_TTS_VOICE_TYPE,
    TaskAssistantService,
)
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from tests.factories.message import image_chain, text_chain, voice_query


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


def test_task_assistant_pipeline_config_uses_bailian_local_agent_model():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_pipeline_config()

    assert config['ai']['runner']['runner'] == 'local-agent'
    assert config['ai']['local-agent']['model']['primary'] == 'task-assistant-qwen-vl-plus'
    workflow = config['workflow']
    assert workflow['metadata']['model_provider'] == 'bailian'
    reply_node = next(node for node in workflow['nodes'] if node['id'] == 'reply')
    assert reply_node['config']['model_uuid'] == 'task-assistant-qwen-vl-plus'


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


def test_task_assistant_pipeline_uses_real_bailian_local_agent_model():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_pipeline_config()

    assert config['ai']['runner']['runner'] == 'local-agent'
    assert config['ai']['local-agent']['model']['primary'] == TASK_ASSISTANT_MODEL_UUID
    assert config['workflow']['metadata']['model_provider'] == 'bailian'
    assert config['workflow']['voice']['voice_type'] == TASK_ASSISTANT_TTS_VOICE_TYPE
    reply_node = next(node for node in config['workflow']['nodes'] if node['id'] == 'reply')
    voice_node = next(node for node in config['workflow']['nodes'] if node['id'] == 'voice')
    assert reply_node['config']['model_uuid'] == TASK_ASSISTANT_MODEL_UUID
    assert voice_node['config']['voice_type'] == TASK_ASSISTANT_TTS_VOICE_TYPE
    assert config['workflow']['voice']['encoding'] == 'ogg_opus'
    assert voice_node['config']['encoding'] == 'ogg_opus'


def test_task_assistant_template_pipeline_config_matches_workflow_capabilities():
    service = TaskAssistantService(SimpleNamespace())

    config = service.build_template_pipeline_config()

    assert TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID == 'task-assistant-ant-af-template-pipeline'
    assert config['config_mode'] == 'template'
    assert config['ai']['local-agent']['model']['primary'] == TASK_ASSISTANT_MODEL_UUID
    assert config['workflow']['metadata']['scenario'] == 'task_assistant_ant_af'
    assert 'source_mode' not in config['workflow']['metadata']
    template_config = config['template_config']
    assert template_config['name'] == '任务助手模板配置版'
    assert template_config['scheduled_push']['mode'] == 'daily'
    assert template_config['scheduled_push']['message']
    assert template_config['voice']['voice_type'] == TASK_ASSISTANT_TTS_VOICE_TYPE
    assert template_config['voice']['encoding'] == 'ogg_opus'
    assert len(template_config['image_text_bindings']) == 8
    first_binding = template_config['image_text_bindings'][0]
    assert first_binding['step_id'] == 'download_qr'
    assert first_binding['text']
    assert first_binding['file_key'].endswith('af_step_01.png')


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
    image_node = next(node for node in active_workflow['nodes'] if node['id'] == 'image_download_qr')
    assert image_node['config']['file_key'] == 'uploads/custom-step.png'
    assert saved_workflow['nodes'] == []
    assert service.is_task_assistant_pipeline(pipeline_config) is True


@pytest.mark.asyncio
async def test_synthesize_reply_voice_uses_lark_friendly_ogg_opus_by_default():
    logger = SimpleNamespace(warning=Mock())
    service = TaskAssistantService(SimpleNamespace(logger=logger))
    service._request_volcengine_tts = AsyncMock(return_value='ZmFrZS1hdWRpbw==')
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
    service._request_volcengine_tts.assert_awaited_once()
    assert service._request_volcengine_tts.await_args.kwargs['encoding'] == 'ogg_opus'


@pytest.mark.asyncio
async def test_synthesize_reply_voice_uses_template_voice_config_in_template_mode():
    logger = SimpleNamespace(warning=Mock())
    service = TaskAssistantService(SimpleNamespace(logger=logger))
    service._request_volcengine_tts = AsyncMock(return_value='ZmFrZS10ZW1wbGF0ZQ==')
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
    service._request_volcengine_tts.assert_awaited_once()
    kwargs = service._request_volcengine_tts.await_args.kwargs
    assert kwargs['app_id'] == 'template-app'
    assert kwargs['token'] == 'template-token'
    assert kwargs['voice_type'] == 'template-voice'


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
