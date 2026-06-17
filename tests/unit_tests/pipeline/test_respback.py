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


def _course_pipeline_config(*, multi_reply_enabled: bool = True, threshold: int = 200) -> dict:
    config = _pipeline_config(multi_reply_enabled=multi_reply_enabled, threshold=threshold)
    config['workflow'] = {
        'metadata': {'scenario': 'course_sales_yuanfudao_phonics'},
    }
    return config


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


def _course_pipeline_config_with_special_cases(*, ai_rewrite: bool) -> dict:
    config = _course_pipeline_config(multi_reply_enabled=False)
    config['workflow']['metadata']['source_mode'] = 'template'
    config['workflow']['special_cases'] = [
        {
            'id': 'listen-resource',
            'enabled': True,
            'condition': '用户在问书籍二维码里的听力/答案/音频怎么打开、怎么听、在哪里看',
            'reply': '书籍二维码听力/答案，点击上面推送的【点击访问扫码前的资源】卡片。',
            'ai_rewrite': ai_rewrite,
        }
    ]
    return config


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
async def test_respback_splits_course_sales_short_natural_sentences_by_default():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('帮我写完这篇作文')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=True, threshold=200)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [
                platform_message.Plain(
                    text='老师看到这题也得深思熟虑一下呢，这可是咱们高中的大作文题目呀！我这边主要负责小学阶段阅读和写作指导的。'
                ),
            ]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '老师看到这题也得深思熟虑一下呢，这可是咱们高中的大作文题目呀！',
        '我这边主要负责小学阶段阅读和写作指导的',
    ]


@pytest.mark.asyncio
async def test_respback_resends_resource_link_for_course_sales_resource_open_failure():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('不能打开')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=True, threshold=200)
    query.pipeline_config['workflow']['sales_links'] = [
        {
            'id': 'phonics_resource_card',
            'title': '图书配套学习资源卡片',
            'url': 'https://example.com/resource-card',
            'radar_enabled': False,
        }
    ]
    query.variables['user_message_text'] = '不能打开'
    query.variables['workflow_intent'] = {
        'intent': 'resource_help',
        'confidence': 0.88,
        'resource_issue_type': 'missing_resource',
    }
    query.resp_message_chain = [
        platform_message.MessageChain(
            [
                platform_message.Plain(
                    text='你说的图书资源打不开吗？我帮您再发一下适配的资源链接哈\n'
                    '家长，您这边能打开吗？\n'
                    '方便发我一张截图吗？'
                )
            ]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '你说的图书资源打不开吗？我帮您再发一下适配的资源链接哈',
        '方便发我一张截图吗？',
        '图书配套学习资源卡片\nhttps://example.com/resource-card',
    ]
    assert all('家长，您这边能打开吗？' not in text for text in sent_texts)


@pytest.mark.asyncio
async def test_respback_sends_parent_open_question_as_separate_course_sales_reply():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('链接在哪里')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='图书配套学习资源卡片：https://example.com/resource。')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '图书配套学习资源卡片：https://example.com/resource',
        '家长，您这边能打开吗？',
    ]


@pytest.mark.asyncio
async def test_respback_does_not_repeat_open_question_after_user_confirmed_resource_opens():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('我能打开')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {'intent': 'resource_confirmed', 'confidence': 0.82}
    query.variables['user_message_text'] = '我能打开'
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='好的，孩子现在几年级呀？')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == ['好的，孩子现在几年级呀？']


@pytest.mark.asyncio
async def test_respback_adds_lark_reaction_once_before_replies():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('可以打开')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['lark_reaction_emoji_type'] = 'SMILE'
    query.adapter.add_message_reaction = AsyncMock(return_value=True)
    query.message_event.message_chain.insert(0, platform_message.Source(id='om_user_msg', time=0))
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='好的')])]

    await stage.process(query, 'SendResponseBackStage')

    query.adapter.add_message_reaction.assert_awaited_once_with('om_user_msg', 'SMILE')
    query.adapter.reply_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_respback_appends_configured_meme_image_for_positive_intent():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('我已经报名了')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.pipeline_config['workflow']['memes'] = {
        'enabled': True,
        'emotions': {
            '赞同': ['https://example.com/like.png'],
        },
    }
    query.variables['workflow_intent'] = {'intent': 'purchased', 'confidence': 0.9}
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='好的')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert str(sent_messages[0]) == '好的'
    assert isinstance(sent_messages[1][0], platform_message.Image)
    assert sent_messages[1][0].url == 'https://example.com/like.png'


@pytest.mark.asyncio
async def test_respback_fetches_oiapi_meme_when_workflow_has_no_meme_image(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    fetched = {}

    async def fake_fetch(emotion: str, limit: int) -> str:
        fetched['emotion'] = emotion
        fetched['limit'] = limit
        return 'https://example.com/oiapi-happy.png'

    monkeypatch.setattr(stage, '_fetch_oiapi_meme_url', fake_fetch)
    query = text_query('可以打开')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {'intent': 'resource_confirmed', 'confidence': 0.9}
    query.variables['auto_meme_emotion'] = '开心'
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='太好了')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert fetched == {'emotion': '开心', 'limit': 5}
    assert isinstance(sent_messages[1][0], platform_message.Image)
    assert sent_messages[1][0].url == 'https://example.com/oiapi-happy.png'


def test_respback_rejects_impolite_or_unrelated_meme_titles():
    stage = get_respback_stage_class()(FakeApp())

    assert stage._is_safe_meme_candidate(
        {'url': 'https://example.com/surrender.png', 'title': '我投降我投降'},
        '赞同',
    ) is False
    assert stage._is_safe_meme_candidate(
        {'url': 'https://example.com/like.png', 'title': '点赞收到'},
        '赞同',
    ) is True


@pytest.mark.asyncio
async def test_respback_uses_local_meme_library_for_trigger_code(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)

    async def fail_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('local meme library should be used before api fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fail_fetch)
    query = text_query('done')
    query.pipeline_config = {
        **_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'memes': {
                'enabled': True,
                'large_enabled': True,
                'library_enabled': True,
                'library': [
                    {
                        'id': 'local-happy',
                        'enabled': True,
                        'meaning': 'polite happy reply',
                        'trigger_keyword': '{happy}',
                        'code': 'happy',
                        'emotion': 'happy',
                        'image_url': 'https://example.com/local-happy.png',
                        'tags': ['happy'],
                        'keywords': ['happy'],
                    }
                ],
            },
        },
    }
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='Great {happy}')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert str(sent_messages[0]) == 'Great'
    assert isinstance(sent_messages[1][0], platform_message.Image)
    assert sent_messages[1][0].url == 'https://example.com/local-happy.png'


@pytest.mark.asyncio
async def test_respback_falls_back_to_api_when_trigger_code_has_no_local_image(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    fetched = {}

    async def fake_fetch(emotion: str, limit: int) -> str:
        fetched['emotion'] = emotion
        fetched['limit'] = limit
        return 'https://example.com/api-happy.png'

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fake_fetch)
    query = text_query('done')
    query.pipeline_config = {
        **_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'memes': {
                'enabled': True,
                'large_enabled': True,
                'library_enabled': True,
                'api_fallback_enabled': True,
                'library': [
                    {
                        'id': 'local-happy-empty',
                        'enabled': True,
                        'meaning': 'polite happy reply',
                        'trigger_keyword': '{happy}',
                        'code': 'happy',
                        'emotion': 'happy',
                        'source': 'builtin',
                        'file_key': 'builtin:sales-meme:happy:1',
                        'search_keyword': 'happy',
                        'tags': ['happy'],
                        'keywords': ['happy'],
                    }
                ],
            },
        },
    }
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='Great {happy}')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert fetched == {'emotion': 'happy', 'limit': 5}
    assert str(sent_messages[0]) == 'Great'
    assert isinstance(sent_messages[1][0], platform_message.Image)
    assert sent_messages[1][0].url == 'https://example.com/api-happy.png'


@pytest.mark.asyncio
async def test_respback_inserts_feishu_native_emoji_at_trigger_position():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('谢谢')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = {
        **_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'memes': {
                'enabled': True,
                'large_enabled': False,
                'feishu_native_enabled': True,
                'library_enabled': True,
                'library': [
                    {
                        'id': 'local-thanks',
                        'enabled': True,
                        'meaning': 'polite thanks reply',
                        'trigger_keyword': '{thanks}',
                        'code': 'thanks',
                        'emotion': 'thanks',
                        'search_keyword': '感谢',
                        'feishu_emoji': '[感谢]',
                        'tags': ['thanks'],
                        'keywords': ['谢谢', '感谢'],
                    }
                ],
            },
        },
    }
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='已经帮您登记 {thanks} 这边会继续跟进')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert str(sent_messages[0]) == '已经帮您登记 [感谢] 这边会继续跟进'


@pytest.mark.asyncio
async def test_respback_provider_chain_skips_unsafe_candidates(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    calls = []

    async def fake_fetch(provider, keyword: str, limit: int):
        calls.append((provider['id'], keyword, limit))
        if provider['id'] == 'oiapi':
            return [{'url': 'https://example.com/surrender.png', 'title': '我投降我投降'}]
        if provider['id'] == 'doutula':
            return [{'url': 'https://example.com/like.png', 'title': '点赞收到'}]
        return []

    monkeypatch.setattr(stage, '_fetch_meme_provider_candidates', fake_fetch)

    url = await stage._fetch_provider_chain_meme_url('赞同', 5)

    assert url == 'https://example.com/like.png'
    assert calls[:2] == [('oiapi', '赞同', 5), ('doutula', '点赞', 5)]


@pytest.mark.asyncio
async def test_respback_adds_meme_for_generic_platform_purchase_text(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)

    async def fake_fetch(emotion: str, limit: int) -> str:
        assert emotion == '赞同'
        return 'https://example.com/generic-like.png'

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fake_fetch)
    query = text_query('我报名了')
    query.pipeline_config = _pipeline_config(multi_reply_enabled=False)
    query.variables['user_message_text'] = '我报名了'
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert str(sent_messages[0]) == '报名成功啦'
    assert isinstance(sent_messages[1][0], platform_message.Image)
    assert sent_messages[1][0].url == 'https://example.com/generic-like.png'


def test_respback_uses_feishu_native_emoji_only_for_lark_adapter():
    stage = get_respback_stage_class()(FakeApp())
    lark_query = text_query('我报名了')
    lark_query.adapter.__class__.__name__ = 'LarkAdapter'
    lark_query.variables['auto_meme_emotion'] = '赞同'
    lark_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

    stage._prepend_feishu_native_emoji(lark_query)

    assert str(lark_query.resp_message_chain[-1]) in {
        '报名成功啦 [赞]',
        '报名成功啦 [+1]',
        '报名成功啦 [我看行]',
        '报名成功啦 [强]',
        '报名成功啦 [完成]',
        '报名成功啦 [勾号]',
        '报名成功啦 [100分]',
        '报名成功啦 [鼓掌]',
    }

    generic_query = text_query('我报名了')
    generic_query.variables['auto_meme_emotion'] = '赞同'
    generic_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

    stage._prepend_feishu_native_emoji(generic_query)

    assert str(generic_query.resp_message_chain[-1]) == '报名成功啦'


@pytest.mark.asyncio
async def test_respback_prefixes_first_course_sales_reply_with_light_emoji():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('你好')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['course_sales_first_contact'] = True
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='家长您好，孩子现在几年级呀。')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert str(sent_chain) == '😊 家长您好，孩子现在几年级呀'


@pytest.mark.asyncio
async def test_respback_does_not_duplicate_parent_open_question():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('链接在哪里')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='我把资源链接发您了，家长，您这边能打开吗？')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert str(sent_chain) == '我把资源链接发您了，家长，您这边能打开吗？'


@pytest.mark.asyncio
async def test_respback_does_not_add_open_question_for_negated_link_context():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('不用发链接')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='好的，不给您发链接了。')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert str(sent_chain) == '好的，不给您发链接了'


@pytest.mark.asyncio
async def test_respback_appends_child_grade_question_for_course_sales_intro_reply():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('课程怎么上')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='我们这个自然拼读课主要帮孩子打好拼读基础，课后也会有老师跟进。')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert str(sent_chain) == '我们这个自然拼读课主要帮孩子打好拼读基础，课后也会有老师跟进\n孩子现在几年级呀？'


@pytest.mark.asyncio
async def test_respback_does_not_duplicate_child_grade_question():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('课程怎么上')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='这个课适合小学阶段孩子，孩子现在几年级呀？')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert str(sent_chain) == '这个课适合小学阶段孩子，孩子现在几年级呀？'


@pytest.mark.asyncio
async def test_respback_appends_screenshot_question_for_course_sales_help_reply():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('打不开')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='如果页面一直报错，我这边可以帮您看一下。')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert str(sent_chain) == '如果页面一直报错，我这边可以帮您看一下\n方便发我一张截图吗？'


@pytest.mark.asyncio
async def test_respback_does_not_add_course_sales_question_to_handoff_notice():
    app = FakeApp()
    app.sales_service = SimpleNamespace(open_handoff_from_query=AsyncMock(return_value={'id': 7}))
    stage = get_respback_stage_class()(app)
    query = text_query('我要转人工')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {
        'intent': 'handoff',
        'handoff_reason': 'manual_request',
        'handoff_config': {'notify_message': '请稍等，我帮您转给老师看一下。'},
    }
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='课程价格是9元。')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert str(sent_chain) == '请稍等，我帮您转给老师看一下'


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
async def test_respback_strips_thinking_tags_before_customer_reply():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('打不开')
    query.pipeline_config = _pipeline_config(multi_reply_enabled=False)
    query.resp_messages = [
        provider_message.Message(role='assistant', content='<think>hidden reasoning</think>\n我帮您看看。')
    ]
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='<think>hidden reasoning</think>\n我帮您看看。')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert str(sent_chain) == '我帮您看看。'
    assert query.resp_messages[-1].content == '我帮您看看。'


@pytest.mark.asyncio
async def test_respback_strips_unclosed_thinking_tags_from_stream_chunk():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('打不开')
    query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
    query.pipeline_config = _pipeline_config(multi_reply_enabled=False)
    query.resp_messages = [
        provider_message.MessageChunk(role='assistant', content='收到<think>hidden reasoning', is_final=False)
    ]
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='收到<think>hidden reasoning')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message_chunk.await_args.kwargs['message']
    sent_chunk = query.adapter.reply_message_chunk.await_args.kwargs['bot_message']
    assert str(sent_chain) == '收到'
    assert sent_chunk.content == '收到'


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
async def test_respback_formats_course_sales_special_case_reply():
    app = FakeApp()
    fake_provider = FakeProvider().returns('{"matched_id":"listen-resource"}')
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=_runtime_model(fake_provider))
    stage = get_respback_stage_class()(app)
    query = text_query('二维码里面答案和听力怎么找')
    query.use_llm_model_uuid = 'model-1'
    query.pipeline_config = _course_pipeline_config_with_special_cases(ai_rewrite=False)
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='普通 AI 原回复')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '书籍二维码听力/答案，点击上面推送的【点击访问扫码前的资源】卡片',
        '家长，您这边能打开吗？',
    ]


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


@pytest.mark.asyncio
async def test_respback_replaces_raw_course_sales_link_with_radar_tracking_url():
    tracking_link = 'http://127.0.0.1:5300/api/v1/sales/radar/click/test-token'
    app = FakeApp()
    app.sales_service = SimpleNamespace(build_radar_tracking_url=lambda **_: tracking_link)
    stage = get_respback_stage_class()(app)
    raw_link = 'https://m.yuanfudao.com/primary/templates/package?pageId=6641'
    query = text_query('再给个新链接')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = 'pipeline-uuid'
    query.launcher_id = 'ou_customer'
    query.pipeline_config = _pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {
        'intent': 'purchase',
        'confidence': 0.9,
        'link_url': raw_link,
    }
    query.variables['course_sales_radar_link'] = raw_link
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text=f'好的，链接发您：{raw_link}，支付成功后截图发我。')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    sent_text = str(sent_chain)
    assert tracking_link in sent_text
    assert raw_link not in sent_text
    assert '支付成功后截图发我' in sent_text


@pytest.mark.asyncio
async def test_respback_sends_course_sales_signup_link_as_separate_plain_reply():
    tracking_link = 'http://127.0.0.1:5300/api/v1/sales/radar/click/test-token'
    app = FakeApp()
    app.sales_service = SimpleNamespace(build_radar_tracking_url=lambda **_: tracking_link)
    stage = get_respback_stage_class()(app)
    raw_link = 'https://m.yuanfudao.com/primary/templates/package?pageId=6641'
    query = text_query('我想报名')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = 'pipeline-uuid'
    query.launcher_id = 'ou_customer'
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {
        'intent': 'purchase',
        'confidence': 0.9,
        'link_url': raw_link,
    }
    query.variables['course_sales_radar_link'] = raw_link
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='好哒')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '好哒',
        f'猿辅导英语自然拼读9元体验课点这里👉：{tracking_link}',
    ]
    assert '报名链接' not in sent_texts[1]
    assert '报名入口' not in sent_texts[1]


@pytest.mark.asyncio
async def test_respback_does_not_append_signup_link_after_explicit_rejection():
    tracking_link = 'http://127.0.0.1:5300/api/v1/sales/radar/click/test-token'
    app = FakeApp()
    app.sales_service = SimpleNamespace(build_radar_tracking_url=lambda **_: tracking_link)
    stage = get_respback_stage_class()(app)
    raw_link = 'https://m.yuanfudao.com/primary/templates/package?pageId=6641'
    query = text_query('不想领取')
    query.bot_uuid = 'bot-uuid'
    query.pipeline_uuid = 'pipeline-uuid'
    query.launcher_id = 'ou_customer'
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {
        'intent': 'objection',
        'confidence': 0.9,
        'explicit_rejection_count': 1,
        'link_url': raw_link,
    }
    query.variables['course_sales_radar_link'] = raw_link
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='没关系啦，家长，之后想了解的话我再把链接发给您')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == ['没关系啦，家长，之后想了解的话我再把链接发给您']
    assert all(tracking_link not in text for text in sent_texts)
