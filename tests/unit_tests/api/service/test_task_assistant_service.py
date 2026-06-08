from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.task_assistant import (
    COURSE_RESOURCE_CARD_LINK,
    COURSE_OPENING_MESSAGE,
    COURSE_SALES_SCENARIO,
    COURSE_SALES_RADAR_LINK,
    COURSE_SALES_TEMPLATE_PIPELINE_UUID,
    COURSE_SALES_TTS_VOICE_TYPE,
    COURSE_SALES_WORKFLOW_PIPELINE_UUID,
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
    assert config['ai']['local-agent']['model']['primary'] == TASK_ASSISTANT_MODEL_UUID
    template = config['template_config']
    assert template['name'] == '课程销售模板'
    assert template['course_profile']['course_name'] == '猿辅导英语自然拼读体验课/自然拼读集训营'
    assert template['course_profile']['price'] == '9元体验'
    assert template['course_profile']['target_grade'] == '大班至小学4年级'
    assert len(template['resource_faqs']) >= 7
    assert len(template['course_faqs']) >= 10
    assert len(template['followup_sequences']) >= 5
    assert len(template['long_term_broadcasts']) == 3
    assert template['radar']['enabled'] is True
    assert template['radar']['link_url'] == COURSE_SALES_RADAR_LINK
    assert len(template['radar']['rules']) >= 4
    assert any(rule['event'] == 'browse_30s' for rule in template['radar']['rules'])
    assert template['tools']['voice_reply'] is False
    assert template['voice']['enabled'] is False
    assert template['voice']['voice_type'] == COURSE_SALES_TTS_VOICE_TYPE
    assert template['voice']['encoding'] == 'ogg_opus'
    assert template['opening_message'].startswith('您的图书配套学习资源点击')
    assert COURSE_RESOURCE_CARD_LINK not in template['opening_message']
    assert COURSE_RESOURCE_CARD_LINK not in template['role_prompt']
    assert 'https://mp.bookln.cn/user/history/moment.htm' in template['opening_message']
    assert '#小程序://教辅好帮手/la0KWwjPCx8S26C' in template['opening_message']
    assert 'https://d.codeup.cn/d/UVruQn' in template['opening_message']
    assert len(template['image_text_bindings']) >= 2
    image_file_keys = {binding['file_key'] for binding in template['image_text_bindings']}
    assert 'course-sales/phonics/phonics_poster.jpeg' in image_file_keys
    assert 'course-sales/phonics/gift_qr.jpeg' in image_file_keys
    assert all('day1_' not in file_key and 'day2_' not in file_key and 'day3_' not in file_key for file_key in image_file_keys)
    broadcast_messages = '\n'.join(broadcast['message'] for broadcast in template['long_term_broadcasts'])
    assert '9元共10节名师直播课' in broadcast_messages
    assert '抽一分钟预约一下~我给您登记发送资料礼包激活学习' in broadcast_messages
    assert '猿辅导现在了推出五天共10节【语数英名师直播课】' in broadcast_messages
    assert '高效能力！完课还抽奖地球仪灯' in broadcast_messages
    assert '五天共10节' in broadcast_messages
    assert '优惠马上要截止了，所以我这边和您确定一下这个名额' in broadcast_messages
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
        message.get('image_key') == 'course-sales/phonics/phonics_poster.jpeg'
        for message in followups_by_stage['not_buy']['messages']
    )
    assert any(
        message.get('image_key') == 'course-sales/phonics/gift_qr.jpeg'
        for message in followups_by_stage['purchased']['messages']
    )
    assert all(
        not message.get('voice_optional')
        for sequence in template['followup_sequences']
        for message in sequence['messages']
    )
    assert (
        followups_by_stage['radar_clicked']['messages'][0]['message']
        == '家长，看您进入报名通道了，支付以后麻烦您发我支付成功截图或者报名成功的短信，我给您登记开课并赠送资料'
    )


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
    assert '首次还要单独发送图书配套学习资源卡片' in template['role_prompt']
    assert template['radar']['link_url'] == COURSE_SALES_RADAR_LINK
    links_by_id = {link['id']: link for link in template['sales_links']}
    assert links_by_id['phonics_resource_card']['url'] == COURSE_RESOURCE_CARD_LINK
    assert links_by_id['phonics_radar_apply']['url'] == COURSE_SALES_RADAR_LINK
    assert {binding['file_key'] for binding in template['image_text_bindings']} == {
        'course-sales/phonics/phonics_poster.jpeg',
        'course-sales/phonics/gift_qr.jpeg',
    }
    assert '9元共10节名师直播课' in template['long_term_broadcasts'][0]['message']
    assert all(not broadcast.get('image_key') for broadcast in template['long_term_broadcasts'])
    assert all(
        'sop_doc_media' not in str(value).lower()
        and 'image1.png' not in str(value).lower()
        and 'image2.png' not in str(value).lower()
        and 'image3.png' not in str(value).lower()
        for broadcast in template['long_term_broadcasts']
        for value in broadcast.values()
    )
    assert template['voice']['enabled'] is False
    assert template['tools']['voice_reply'] is False
    migrated_followups = {sequence['stage']: sequence for sequence in template['followup_sequences']}
    assert any(
        message.get('link_id') == 'phonics_radar_apply'
        for message in migrated_followups['purchase']['messages']
    )
    assert any(
        message.get('image_key') == 'course-sales/phonics/phonics_poster.jpeg'
        for message in migrated_followups['not_buy']['messages']
    )


def test_course_sales_workflow_visualizes_template_capabilities_as_nodes():
    service = TaskAssistantService(SimpleNamespace())

    workflow = service.build_course_sales_workflow_config()

    assert COURSE_SALES_WORKFLOW_PIPELINE_UUID == 'course-sales-workflow-pipeline'
    assert workflow['name'] == '课程 销售模板'
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
    assert workflow['voice']['enabled'] is False
    assert workflow['opening_message'].startswith('您的图书配套学习资源点击')
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
    assert query.variables['task_assistant_voice_reply'] is False
    assert '猿辅导英语自然拼读' in query.prompt.messages[0].content
    assert '雷达' in query.prompt.messages[0].content
    assert '课程销售场景只回复文字，不发送语音回复' in query.prompt.messages[0].content


class _CourseOutreachSalesService:
    def __init__(self, user_message_count=1):
        self.user_message_count = user_message_count
        self.plans = []
        self.disabled = []

    async def count_user_messages_for_session(self, _session_id):
        return self.user_message_count

    async def create_outreach_plan(self, data):
        self.plans.append(data)
        return len(self.plans)

    async def disable_outreach_for_target(self, **kwargs):
        self.disabled.append(kwargs)


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

    assert result['handled'] is True
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
    broadcast_plans = [plan for plan in sales_service.plans if plan['segment'] == 'course-sales:broadcast']
    assert len(broadcast_plans) == 3
    assert all(component['type'] == 'plain' for plan in broadcast_plans for component in plan['message_components'])
    assert all(
        'sop_doc_media' not in str(plan['message_components']).lower()
        and 'image1.png' not in str(plan['message_components']).lower()
        and 'image2.png' not in str(plan['message_components']).lower()
        and 'image3.png' not in str(plan['message_components']).lower()
        for plan in broadcast_plans
    )
    assert any(plan['segment'] == 'course-sales:followup:purchase' for plan in sales_service.plans)


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
