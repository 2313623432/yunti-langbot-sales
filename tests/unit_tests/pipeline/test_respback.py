from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from tests.factories import FakeApp, FakeProvider, text_query


def get_respback_stage_class():
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.respback.respback').SendResponseBackStage


def _pipeline_config(*, multi_reply_enabled: bool, threshold: int = 20) -> dict:
    return {
        'output': {
            'force-delay': {'min': 0, 'max': 0},
            'misc': {
                'at-sender': False,
                'quote-origin': False,
                'multi-reply': {
                    'enabled': multi_reply_enabled,
                    'threshold': threshold,
                },
            },
        },
    }


def _pipeline_config_with_special_cases(*, ai_rewrite: bool) -> dict:
    return {
        **_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'metadata': {'source_mode': 'template'},
            'special_cases': [
                {
                    'id': 'listen-resource',
                    'enabled': True,
                    'condition': '用户在问书籍二维码里的听力/答案/音频怎么打开、怎么听、在哪里看',
                    'reply': '书籍二维码听力/答案，点击上面推送的【点击访问扫码前的资源】卡片',
                    'ai_rewrite': ai_rewrite,
                    'image_url': 'https://example.com/listen.png',
                }
            ],
        },
    }


def _runtime_model(fake_provider: FakeProvider) -> SimpleNamespace:
    return SimpleNamespace(
        model_entity=SimpleNamespace(uuid='model-1', name='real-model'),
        provider=fake_provider,
    )


@pytest.mark.asyncio
async def test_respback_splits_long_plain_text_when_multi_reply_enabled():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('hello')
    query.pipeline_config = _pipeline_config(multi_reply_enabled=True, threshold=10)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [
                platform_message.Plain(text='第一段内容很长。\n第二段内容也很长。'),
            ]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == ['第一段内容很长。', '第二段内容也很长。']


@pytest.mark.asyncio
async def test_respback_keeps_plain_text_as_single_message_when_multi_reply_disabled():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('hello')
    query.pipeline_config = _pipeline_config(multi_reply_enabled=False, threshold=10)
    text = '第一段内容很长。\n第二段内容也很长。'
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text=text)])
    ]

    await stage.process(query, 'SendResponseBackStage')

    query.adapter.reply_message.assert_awaited_once()
    assert query.adapter.reply_message.await_args == call(
        message_source=query.message_event,
        message=query.resp_message_chain[-1],
        quote_origin=False,
    )


@pytest.mark.asyncio
async def test_respback_uses_ai_semantic_special_case_without_keyword_match():
    app = FakeApp()
    fake_provider = FakeProvider().returns('{"matched_id":"listen-resource"}')
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=_runtime_model(fake_provider))
    stage = get_respback_stage_class()(app)
    query = text_query('我扫书后那个音频入口在哪里播放')
    query.use_llm_model_uuid = 'model-1'
    query.pipeline_config = _pipeline_config_with_special_cases(ai_rewrite=False)
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='普通 AI 原回复')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    query.adapter.reply_message.assert_awaited_once()
    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert sent_chain[0].text == '书籍二维码听力/答案，点击上面推送的【点击访问扫码前的资源】卡片'
    assert isinstance(sent_chain[1], platform_message.Image)
    assert fake_provider.get_captured_requests()[0]['messages'][0].content.startswith('你是语义路由器')


@pytest.mark.asyncio
async def test_respback_skips_special_case_llm_for_irrelevant_message():
    app = FakeApp()
    app.model_mgr.get_model_by_uuid = AsyncMock()
    stage = get_respback_stage_class()(app)
    query = text_query('怎么样')
    query.use_llm_model_uuid = 'model-1'
    query.pipeline_config = _pipeline_config_with_special_cases(ai_rewrite=False)
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='普通 AI 原回复')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    app.model_mgr.get_model_by_uuid.assert_not_awaited()
    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert sent_chain[0].text == '普通 AI 原回复'


@pytest.mark.asyncio
async def test_respback_rewrites_special_case_reply_when_enabled():
    app = FakeApp()
    responses = [
        provider_message.Message(role='assistant', content='{"matched_id":"listen-resource"}'),
        provider_message.Message(role='assistant', content='可以点上面的资源卡片，里面能听音频也能看答案。'),
    ]
    provider = SimpleNamespace(
        invoke_llm=AsyncMock(side_effect=lambda *args, **kwargs: responses.pop(0)),
    )
    app.model_mgr.get_model_by_uuid = AsyncMock(
        return_value=SimpleNamespace(
            model_entity=SimpleNamespace(uuid='model-1', name='real-model'),
            provider=provider,
        )
    )
    stage = get_respback_stage_class()(app)
    query = text_query('二维码里面答案和听力怎么找')
    query.use_llm_model_uuid = 'model-1'
    query.pipeline_config = _pipeline_config_with_special_cases(ai_rewrite=True)
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='普通 AI 原回复')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert sent_chain[0].text == '可以点上面的资源卡片，里面能听音频也能看答案。'
    assert isinstance(sent_chain[1], platform_message.Image)
    assert provider.invoke_llm.await_count == 2


@pytest.mark.asyncio
async def test_respback_opens_handoff_when_workflow_intent_requests_manual_intervention():
    app = FakeApp()
    app.sales_service = SimpleNamespace(open_handoff_from_query=AsyncMock(return_value={'id': 7}))
    stage = get_respback_stage_class()(app)
    query = text_query('我要转人工')
    query.pipeline_config = _pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {
        'intent': 'handoff',
        'handoff_reason': 'manual_request',
        'handoff_config': {'notify_message': '请稍等，我来帮您看一下。'},
    }
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='normal ai reply')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    app.sales_service.open_handoff_from_query.assert_awaited_once_with(
        query,
        'manual_request',
        '我要转人工',
    )
    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert sent_chain[0].text == '请稍等，我来帮您看一下。'
    assert query.variables['sales_handoff_opened'] is True


@pytest.mark.asyncio
async def test_respback_replaces_course_sales_placeholder_signup_link_with_real_url():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('好的 给我发个链接')
    query.pipeline_config = _pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {'intent': 'purchase', 'confidence': 0.9}
    query.variables['course_sales_radar_link'] = 'https://m.yuanfudao.com/primary/templates/package?pageId=6641'
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='这个是咱们9元课报名链接XXXXXXX，点开后选年级就行。')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    sent_text = str(sent_chain)
    assert 'XXXX' not in sent_text
    assert 'https://m.yuanfudao.com/primary/templates/package?pageId=6641' in sent_text
