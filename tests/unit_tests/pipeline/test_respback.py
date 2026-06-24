from __future__ import annotations

import base64
import io
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from PIL import Image

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from tests.factories import FakeApp, FakeProvider, text_query, voice_query


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


def _white_canvas_sticker_png() -> bytes:
    image = Image.new('RGBA', (100, 100), (255, 255, 255, 255))
    for x in range(36, 64):
        for y in range(32, 68):
            image.putpixel((x, y), (240, 100, 120, 255))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def _decode_data_uri_image(data_uri: str) -> Image.Image:
    _, encoded = data_uri.split(',', 1)
    return Image.open(io.BytesIO(base64.b64decode(encoded))).convert('RGBA')


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
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False, threshold=200)
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
async def test_respback_sends_course_sales_followup_question_as_separate_message():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('这个适合我家孩子吗')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False, threshold=200)
    query.variables['workflow_intent'] = {'intent': 'course_intro', 'confidence': 0.9}
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='这个课程适合零基础孩子，学习自然拼读。')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '这个课程适合零基础孩子，学习自然拼读',
        '孩子现在几年级呀？',
    ]
    assert all('\n' not in text for text in sent_texts)


@pytest.mark.asyncio
async def test_respback_localizes_course_sales_text_reply_to_chinese_terms():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('Do you have Phonics class?')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False, threshold=200)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='Phonics 9元就能学5天，APP里还有VIP服务。')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_text = str(query.adapter.reply_message.await_args_list[0].kwargs['message'])
    assert '自然拼读' in sent_text
    assert '应用' in sent_text
    assert '会员服务' in sent_text
    assert 'Phonics' not in sent_text
    assert 'APP' not in sent_text
    assert 'VIP' not in sent_text


@pytest.mark.asyncio
async def test_respback_localizes_course_sales_voice_reply_before_tts():
    app = FakeApp()
    app.task_assistant_service = SimpleNamespace(
        synthesize_reply_voice=AsyncMock(return_value='data:audio/mpeg;base64,ZmFrZQ==')
    )
    stage = get_respback_stage_class()(app)
    query = voice_query('https://example.com/audio.mp3')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False, threshold=200)
    query.variables['task_assistant_voice_reply'] = True
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='咱们现在有 Phonics 体验课，APP里能看VIP权益。')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    app.task_assistant_service.synthesize_reply_voice.assert_awaited_once()
    tts_text = app.task_assistant_service.synthesize_reply_voice.await_args.args[1]
    assert '自然拼读' in tts_text
    assert '应用' in tts_text
    assert '会员权益' in tts_text
    assert 'Phonics' not in tts_text
    assert 'APP' not in tts_text
    assert 'VIP' not in tts_text


@pytest.mark.asyncio
async def test_respback_splits_course_sales_text_before_image_message():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('您这边有数学课么')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False, threshold=200)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [
                platform_message.Plain(text='有的哦\n我们还有9元的阅读+思维体验课\n适合小学阶段的孩子 还支持回放'),
                platform_message.Image(path='course-sales/phonics/gift_poster.jpeg'),
            ]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [
        kwargs['message']
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert [str(message) for message in sent_messages[:3]] == [
        '有的哦',
        '我们还有9元的阅读+思维体验课',
        '适合小学阶段的孩子 还支持回放',
    ]
    assert isinstance(sent_messages[3][0], platform_message.Image)


@pytest.mark.asyncio
async def test_respback_splits_course_sales_extra_reply_open_question_and_link():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('我要报名')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False, threshold=200)
    query.variables['workflow_intent'] = {'intent': 'purchase', 'confidence': 0.9}
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='报名入口我发您，方便时点开看看 家长，您这边能打开吗？')])
    ]
    stage._queue_extra_reply_chain(
        query,
        '猿辅导阅读+思维9元体验课报名通道\nhttps://example.com/radar/click/token',
    )

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '报名入口我发您，方便时点开看看',
        '家长，您这边能打开吗？',
        '猿辅导阅读+思维9元体验课报名通道',
        'https://example.com/radar/click/token',
    ]


@pytest.mark.asyncio
async def test_respback_adds_gift_intro_before_course_sales_signup_image():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('我要报名')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False, threshold=200)
    query.pipeline_config['workflow']['nodes'] = [
        {
            'id': 'image_gift_poster',
            'type': 'image',
            'config': {
                'file_key': 'course-sales/phonics/gift_poster.jpeg',
                'trigger_intents': ['purchase'],
                'requires_course_sales_signup_link': True,
            },
        }
    ]
    query.variables['workflow_intent'] = {
        'intent': 'purchase',
        'confidence': 0.9,
        'link_url': 'https://m.yuanfudao.com/primary/templates/package?test=gift',
    }
    query.variables['course_sales_radar_link'] = 'https://m.yuanfudao.com/primary/templates/package?test=gift'
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='报名入口我发您。')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [
        kwargs['message']
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    sent_texts = [str(message) for message in sent_messages]
    assert '报课后按活动规则有完课礼，礼品说明我发您看一下' in sent_texts
    image_index = next(index for index, message in enumerate(sent_messages) if isinstance(message[0], platform_message.Image))
    assert sent_texts.index('报课后按活动规则有完课礼，礼品说明我发您看一下') < image_index


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
        '你说的图书资源打不开吗？',
        '我帮您再发一下适配的资源链接哈',
        '方便发我一张截图吗？',
        '图书配套学习资源卡片',
        'https://example.com/resource-card',
    ]
    assert all('家长，您这边能打开吗？' not in text for text in sent_texts)


@pytest.mark.asyncio
async def test_respback_sends_selected_resource_card_before_course_sales_signup_offer():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    tracking_link = 'https://example.com/radar/click/signup'
    resource_link = 'https://example.com/resource-card'
    query = text_query('小学三年级数学图书学习资料')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False, threshold=200)
    query.pipeline_config['workflow']['sales_links'] = [
        {
            'id': 'phonics_resource_card',
            'title': '图书配套学习资源卡片',
            'url': resource_link,
            'radar_enabled': False,
        }
    ]
    query.pipeline_config['workflow']['nodes'] = [
        {
            'id': 'image_gift_poster',
            'type': 'image',
            'config': {
                'file_key': 'course-sales/phonics/gift_poster.jpeg',
                'trigger_intents': ['resource_help'],
                'step_id': 'gift_poster',
                'requires_course_sales_signup_link': True,
            },
        }
    ]
    query.variables['user_message_text'] = '小学三年级数学图书学习资料'
    query.variables['workflow_intent'] = {
        'intent': 'resource_help',
        'confidence': 0.9,
        'step_ids': ['gift_qr', 'gift_poster'],
    }
    query.variables['course_sales_radar_link'] = tracking_link
    query.resp_message_chain = [
        platform_message.MessageChain(
            [
                platform_message.Plain(
                    text='三年级数学的配套资源我这就给您找哈。\n'
                    '现在我们这里有一个猿辅导阅读+思维9元体验课，报名还送完课好礼，报名入口我发您。'
                )
            ]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [
        kwargs['message']
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    sent_texts = [str(message) for message in sent_messages]
    assert sent_texts[:7] == [
        '三年级数学的配套资源我这就给您找哈',
        '现在我们这里有一个猿辅导阅读+思维9元体验课，报名还送完课好礼，报名入口我发您',
        '图书配套学习资源卡片',
        resource_link,
        '家长，您这边能打开吗？',
        '猿辅导英语自然拼读9元体验课点这里👉',
        tracking_link,
    ]
    assert isinstance(sent_messages[7][0], platform_message.Image)


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
        '图书配套学习资源卡片',
        'https://example.com/resource',
        '家长，您这边能打开吗？',
    ]


@pytest.mark.asyncio
async def test_respback_does_not_add_open_question_for_course_sales_clarification():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('你好')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {'intent': 'smalltalk', 'confidence': 0.66}
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='家长是想看图书资源，还是了解课程信息呀')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == ['家长是想看图书资源，还是了解课程信息呀']


@pytest.mark.asyncio
async def test_respback_does_not_add_open_question_when_resource_reply_asks_for_book_name():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('图书资源')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {'intent': 'resource_help', 'confidence': 0.82}
    query.variables['user_message_text'] = '图书资源'
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='家长您要的是哪本图书的对应资源呀，可以说下具体名称吗')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == ['家长您要的是哪本图书的对应资源呀，可以说下具体名称吗']


@pytest.mark.asyncio
async def test_respback_does_not_add_open_question_for_resource_help_without_link_intent():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('图书资源')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {'intent': 'resource_help', 'confidence': 0.82, 'include_link': False}
    query.variables['user_message_text'] = '图书资源'
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='我先帮您确认一下图书资源情况')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == ['我先帮您确认一下图书资源情况']


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
    assert sent_texts == ['好的，', '孩子现在几年级呀？']


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
    assert query.adapter.reply_message.await_count == 2


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
async def test_respback_fetches_provider_chain_meme_when_local_library_disabled(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    fetched = {}

    async def fake_fetch(emotion: str, limit: int) -> str:
        fetched['emotion'] = emotion
        fetched['limit'] = limit
        return 'https://example.com/oiapi-happy.png'

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fake_fetch)
    query = text_query('可以打开')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.pipeline_config['workflow']['memes'] = {
        'enabled': True,
        'library_enabled': False,
    }
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
async def test_respback_ignores_corrupted_feishu_native_emoji_value():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('我报名了')
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
                        'id': 'corrupted-like',
                        'enabled': True,
                        'trigger_keyword': '{like}',
                        'code': 'like',
                        'emotion': 'like',
                        'search_keyword': '赞同',
                        'feishu_emoji': '[??]',
                        'tags': ['like'],
                        'keywords': ['报名', '点赞'],
                    }
                ],
            },
        },
    }
    query.variables['auto_meme_emotion'] = '赞同'
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_text = str(query.adapter.reply_message.await_args.kwargs['message'])
    assert '[??]' not in sent_text
    assert any(emoji in sent_text for emoji in ('[赞]', '[+1]', '[我看行]', '[强]', '[完成]'))


@pytest.mark.asyncio
async def test_respback_sends_lark_local_large_meme_as_tight_sticker_image(monkeypatch):
    storage_provider = SimpleNamespace(load=AsyncMock(return_value=_white_canvas_sticker_png()))
    app = FakeApp(storage_mgr=SimpleNamespace(storage_provider=storage_provider))
    stage = get_respback_stage_class()(app)

    async def fail_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('Local meme library should be used before API fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fail_fetch)
    query = text_query('我报名了')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = {
        **_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'memes': {
                'enabled': True,
                'large_enabled': True,
                'feishu_native_enabled': True,
                'library_enabled': True,
                'library': [
                    {
                        'id': 'local-like',
                        'enabled': True,
                        'meaning': 'polite like reply',
                        'trigger_keyword': '{like}',
                        'code': 'like',
                        'emotion': 'like',
                        'file_key': 'sales-memes/like/soft.png',
                        'feishu_emoji': '[赞]',
                        'tags': ['like'],
                        'keywords': ['报名', '点赞'],
                    }
                ],
            },
        },
    }
    query.variables['auto_meme_emotion'] = '赞同'
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert str(sent_messages[0]) == '报名成功啦 [赞]'
    assert isinstance(sent_messages[1][0], platform_message.Image)
    sticker = _decode_data_uri_image(sent_messages[1][0].base64)
    assert sticker.size[0] < 100
    assert sticker.size[1] < 100
    assert sticker.getpixel((0, 0))[3] == 0


@pytest.mark.asyncio
async def test_respback_appends_large_meme_even_when_course_link_was_queued(monkeypatch):
    storage_provider = SimpleNamespace(load=AsyncMock(return_value=_white_canvas_sticker_png()))
    app = FakeApp(storage_mgr=SimpleNamespace(storage_provider=storage_provider))
    stage = get_respback_stage_class()(app)

    async def fail_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('Local meme library should be used before API fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fail_fetch)
    query = text_query('我报名了')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = {
        **_course_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'metadata': {'scenario': 'course_sales_yuanfudao_phonics'},
            'memes': {
                'enabled': True,
                'large_enabled': True,
                'feishu_native_enabled': True,
                'library_enabled': True,
                'library': [
                    {
                        'id': 'local-like',
                        'enabled': True,
                        'trigger_keyword': '{like}',
                        'code': 'like',
                        'emotion': 'like',
                        'file_key': 'sales-memes/like/soft.png',
                        'feishu_emoji': '[赞]',
                        'tags': ['like'],
                        'keywords': ['报名', '点赞'],
                    }
                ],
            },
        },
    }
    query.variables['auto_meme_emotion'] = '赞同'
    query.variables[stage._COURSE_SALES_SIGNUP_LINK_QUEUED_KEY] = True
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert str(sent_messages[0]) == '报名成功啦 [赞]'
    assert isinstance(sent_messages[1][0], platform_message.Image)
    sticker = _decode_data_uri_image(sent_messages[1][0].base64)
    assert sticker.getpixel((0, 0))[3] == 0


@pytest.mark.asyncio
async def test_respback_respects_lark_native_emoji_interval():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    sent_texts: list[str] = []

    for _ in range(3):
        query = text_query('我报名了', sender_id='same-user')
        query.adapter.__class__.__name__ = 'LarkAdapter'
        query.pipeline_config = {
            **_pipeline_config(multi_reply_enabled=False),
            'workflow': {
                'memes': {
                    'enabled': True,
                    'large_enabled': False,
                    'feishu_native_enabled': True,
                    'library_enabled': True,
                    'smart_judge_enabled': True,
                    'small_interval_rounds': 2,
                    'library': [
                        {
                            'id': 'local-like',
                            'enabled': True,
                            'trigger_keyword': '{like}',
                            'code': 'like',
                            'emotion': 'like',
                            'feishu_emoji': '[赞]',
                            'tags': ['like'],
                            'keywords': ['报名', '点赞'],
                        }
                    ],
                },
            },
        }
        query.variables['auto_meme_emotion'] = '赞同'
        query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

        await stage.process(query, 'SendResponseBackStage')
        sent_texts.append(str(query.adapter.reply_message.await_args.kwargs['message']))

    assert sent_texts == ['报名成功啦 [赞]', '报名成功啦', '报名成功啦 [赞]']


@pytest.mark.asyncio
async def test_respback_respects_large_meme_interval(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)

    async def fail_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('Local meme library should be used before API fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fail_fetch)
    sent_counts: list[int] = []

    for _ in range(3):
        query = text_query('我报名了', sender_id='same-user')
        query.pipeline_config = {
            **_pipeline_config(multi_reply_enabled=False),
            'workflow': {
                'memes': {
                    'enabled': True,
                    'large_enabled': True,
                    'feishu_native_enabled': False,
                    'library_enabled': True,
                    'smart_judge_enabled': True,
                    'large_interval_rounds': 2,
                    'library': [
                        {
                            'id': 'local-like',
                            'enabled': True,
                            'trigger_keyword': '{like}',
                            'code': 'like',
                            'emotion': 'like',
                            'image_url': 'https://example.com/like.png',
                            'tags': ['like'],
                            'keywords': ['报名', '点赞'],
                        }
                    ],
                },
            },
        }
        query.variables['auto_meme_emotion'] = '赞同'
        query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

        await stage.process(query, 'SendResponseBackStage')
        sent_counts.append(len(query.adapter.reply_message.await_args_list))

    assert sent_counts == [2, 1, 2]


@pytest.mark.asyncio
async def test_respback_interval_mode_sends_polite_meme_without_smart_emotion(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)

    async def fail_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('Default local meme should be used before API fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fail_fetch)
    query = text_query('今天先这样', sender_id='same-user')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = {
        **_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'memes': {
                'enabled': True,
                'large_enabled': True,
                'feishu_native_enabled': True,
                'library_enabled': True,
                'smart_judge_enabled': False,
                'small_interval_rounds': 1,
                'large_interval_rounds': 1,
                'library': [],
            },
        },
    }
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='好的，这边继续帮您跟进')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert str(sent_messages[0]).startswith('好的，这边继续帮您跟进 [')
    assert isinstance(sent_messages[1][0], platform_message.Image)
    assert sent_messages[1][0].path == 'sales-memes/polite/soft.png'


@pytest.mark.asyncio
async def test_respback_treats_course_intro_as_smart_meme_moment(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)

    async def fail_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('Default local meme should be used before API fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fail_fetch)
    query = text_query('我想咨询课程')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {'intent': 'course_intro', 'confidence': 0.8}
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='我帮您介绍下课程')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert ' [' in str(sent_messages[0])
    assert str(sent_messages[0]).endswith(']')
    assert isinstance(sent_messages[1][0], platform_message.Image)
    assert sent_messages[1][0].path == 'sales-memes/service/soft.png'


@pytest.mark.asyncio
async def test_respback_forces_small_meme_within_configured_rounds_when_smart_has_no_emotion():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    sent_texts: list[str] = []

    for _ in range(2):
        query = text_query('随便聊聊', sender_id='same-user')
        query.adapter.__class__.__name__ = 'LarkAdapter'
        query.pipeline_config = {
            **_pipeline_config(multi_reply_enabled=False),
            'workflow': {
                'memes': {
                    'enabled': True,
                    'large_enabled': False,
                    'feishu_native_enabled': True,
                    'library_enabled': True,
                    'smart_judge_enabled': True,
                    'small_interval_rounds': 2,
                    'library': [],
                },
            },
        }
        query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='好的，我继续帮您看')])]

        await stage.process(query, 'SendResponseBackStage')
        sent_texts.append(str(query.adapter.reply_message.await_args.kwargs['message']))

    assert sent_texts[0] == '好的，我继续帮您看'
    assert sent_texts[1].startswith('好的，我继续帮您看 [')


@pytest.mark.asyncio
async def test_respback_forces_large_meme_within_configured_rounds_when_smart_has_no_emotion(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)

    async def fail_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('Default local meme should be used before API fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fail_fetch)
    sent_counts: list[int] = []

    for _ in range(2):
        query = text_query('随便聊聊', sender_id='same-user')
        query.pipeline_config = {
            **_pipeline_config(multi_reply_enabled=False),
            'workflow': {
                'memes': {
                    'enabled': True,
                    'large_enabled': True,
                    'feishu_native_enabled': False,
                    'library_enabled': True,
                    'smart_judge_enabled': True,
                    'large_interval_rounds': 2,
                    'library': [],
                },
            },
        }
        query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='好的，我继续帮您看')])]

        await stage.process(query, 'SendResponseBackStage')
        sent_counts.append(len(query.adapter.reply_message.await_args_list))

    assert sent_counts == [1, 2]


@pytest.mark.asyncio
async def test_respback_prefers_template_meme_interval_over_stale_workflow_config(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)

    async def fail_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('Default local meme should be used before API fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fail_fetch)
    sent_summaries: list[tuple[str, int]] = []

    for _ in range(2):
        query = text_query('plain follow up', sender_id='same-user')
        query.adapter.__class__.__name__ = 'LarkAdapter'
        query.pipeline_config = {
            **_pipeline_config(multi_reply_enabled=False),
            'template_config': {
                'memes': {
                    'enabled': True,
                    'large_enabled': True,
                    'feishu_native_enabled': True,
                    'library_enabled': True,
                    'smart_judge_enabled': True,
                    'small_interval_rounds': 1,
                    'large_interval_rounds': 1,
                    'library': [],
                },
            },
            'workflow': {
                'memes': {
                    'enabled': True,
                    'large_enabled': True,
                    'feishu_native_enabled': True,
                    'library_enabled': True,
                    'smart_judge_enabled': True,
                    'small_interval_rounds': 3,
                    'large_interval_rounds': 5,
                    'library': [],
                },
            },
        }
        query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='ok follow up')])]

        await stage.process(query, 'SendResponseBackStage')
        sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
        sent_summaries.append((str(sent_messages[0]), len(sent_messages)))

    assert sent_summaries[0][0].startswith('ok follow up [')
    assert sent_summaries[0][1] == 2
    assert sent_summaries[1][0].startswith('ok follow up [')
    assert sent_summaries[1][1] == 2


def test_respback_matches_meme_usage_scene_and_instruction():
    stage = get_respback_stage_class()(FakeApp())
    item = {
        'id': 'signup-guide',
        'enabled': True,
        'meaning': '报名引导',
        'trigger_keyword': '{signup}',
        'code': 'signup',
        'emotion': 'signup',
        'usage_scene': '客户准备报名、领取课程名额、需要报名链接',
        'usage_instruction': '当客户询问怎么报名、报名链接、领取体验课时可以发送；不要用于投诉、道歉或客户情绪激动场景。',
        'search_keyword': '',
        'keywords': [],
        'tags': [],
    }

    assert stage._meme_entry_matches_emotion(item, '报名链接')
    assert stage._meme_entry_matches_emotion(item, '领取体验课')
    assert not stage._meme_entry_matches_emotion(item, '道歉')


@pytest.mark.asyncio
async def test_respback_replaces_lark_trigger_position_and_appends_large_meme():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('谢谢')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = {
        **_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'memes': {
                'enabled': True,
                'large_enabled': True,
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
                        'image_url': 'https://example.com/thanks.png',
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
    assert isinstance(sent_messages[1][0], platform_message.Image)
    assert sent_messages[1][0].url == 'https://example.com/thanks.png'


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
async def test_respback_adds_default_local_meme_for_generic_platform_purchase_text(monkeypatch):
    app = FakeApp()
    stage = get_respback_stage_class()(app)

    async def fake_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('Default local meme should be used before API fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fake_fetch)
    query = text_query('我报名了')
    query.pipeline_config = _pipeline_config(multi_reply_enabled=False)
    query.variables['user_message_text'] = '我报名了'
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert str(sent_messages[0]) == '报名成功啦'
    assert isinstance(sent_messages[1][0], platform_message.Image)
    assert sent_messages[1][0].path == 'sales-memes/like/soft.png'


def test_respback_uses_feishu_native_emoji_only_for_lark_adapter():
    stage = get_respback_stage_class()(FakeApp())
    lark_query = text_query('我报名了')
    lark_query.adapter.__class__.__name__ = 'LarkAdapter'
    lark_query.variables['auto_meme_emotion'] = '赞同'
    lark_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

    stage._prepend_feishu_native_emoji(lark_query)

    assert str(lark_query.resp_message_chain[-1]).startswith('报名成功啦 [')

    generic_query = text_query('我报名了')
    generic_query.variables['auto_meme_emotion'] = '赞同'
    generic_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='报名成功啦')])]

    stage._prepend_feishu_native_emoji(generic_query)

    assert str(generic_query.resp_message_chain[-1]) == '报名成功啦'


@pytest.mark.asyncio
async def test_respback_lark_course_sales_without_meme_config_still_uses_default_local_meme(monkeypatch):
    storage_provider = SimpleNamespace(load=AsyncMock(return_value=_white_canvas_sticker_png()))
    app = FakeApp(storage_mgr=SimpleNamespace(storage_provider=storage_provider))
    stage = get_respback_stage_class()(app)

    async def fail_fetch(emotion: str, limit: int) -> str:
        raise AssertionError('Course sales defaults should not require API fallback')

    monkeypatch.setattr(stage, '_fetch_provider_chain_meme_url', fail_fetch)
    query = text_query('你好')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {'intent': 'smalltalk', 'confidence': 0.7}
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='您好呀')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_messages = [kwargs['message'] for _, kwargs in query.adapter.reply_message.await_args_list]
    assert str(sent_messages[0]).startswith('您好呀 [')
    assert isinstance(sent_messages[1][0], platform_message.Image)
    sticker = _decode_data_uri_image(sent_messages[1][0].base64)
    assert sticker.getpixel((0, 0))[3] == 0


@pytest.mark.asyncio
async def test_respback_uses_feishu_native_emoji_for_first_course_sales_reply():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('你好')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = {
        **_course_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'metadata': {'scenario': 'course_sales_yuanfudao_phonics'},
            'memes': {
                'enabled': True,
                'large_enabled': False,
                'feishu_native_enabled': True,
                'library_enabled': True,
                'small_interval_rounds': 1,
                'library': [
                    {
                        'id': 'welcome-wave',
                        'enabled': True,
                        'meaning': 'polite welcome reply',
                        'trigger_keyword': '{welcome}',
                        'code': 'welcome',
                        'emotion': 'welcome',
                        'search_keyword': 'welcome',
                        'feishu_emoji': '[挥手]',
                        'tags': ['welcome'],
                        'keywords': ['hello'],
                    }
                ],
            },
        },
    }
    query.variables['course_sales_first_contact'] = True
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='家长您好，孩子现在几年级呀😊')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args.kwargs['message']
    assert str(sent_chain) == '家长您好，孩子现在几年级呀 [挥手]'


@pytest.mark.asyncio
async def test_respback_strips_course_sales_trailing_unicode_emoji_before_feishu_native():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('我想买')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = {
        **_course_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'metadata': {'scenario': 'course_sales_yuanfudao_phonics'},
            'memes': {
                'enabled': True,
                'large_enabled': False,
                'feishu_native_enabled': True,
                'library_enabled': True,
                'small_interval_rounds': 1,
                'library': [
                    {
                        'id': 'signup-ok',
                        'enabled': True,
                        'meaning': 'polite purchase guidance reply',
                        'trigger_keyword': '{signup}',
                        'code': 'signup',
                        'emotion': 'signup',
                        'search_keyword': 'signup',
                        'feishu_emoji': '[完成]',
                        'tags': ['signup'],
                        'keywords': ['buy'],
                    }
                ],
            },
        },
    }
    query.variables['auto_meme_emotion'] = 'signup'
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='我正在整理自然拼读体验课的相关资料哦🫡')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args_list[0].kwargs['message']
    assert str(sent_chain) == '我正在整理自然拼读体验课的相关资料哦 [完成]'


@pytest.mark.asyncio
async def test_respback_uses_received_feishu_native_emoji_for_resource_confirmation():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('可以打开')
    query.adapter.__class__.__name__ = 'LarkAdapter'
    query.pipeline_config = {
        **_course_pipeline_config(multi_reply_enabled=False),
        'workflow': {
            'metadata': {'scenario': 'course_sales_yuanfudao_phonics'},
            'memes': {
                'enabled': True,
                'large_enabled': False,
                'feishu_native_enabled': True,
                'library_enabled': True,
                'small_interval_rounds': 1,
                'library': [
                    {
                        'id': 'received-ok',
                        'enabled': True,
                        'meaning': 'polite received reply',
                        'trigger_keyword': '{received}',
                        'code': 'received',
                        'emotion': 'received',
                        'search_keyword': 'received',
                        'feishu_emoji': '[了解]',
                        'tags': ['received'],
                        'keywords': ['open'],
                    },
                    {
                        'id': 'happy-smile',
                        'enabled': True,
                        'meaning': 'happy reply',
                        'trigger_keyword': '{happy}',
                        'code': 'happy',
                        'emotion': 'happy',
                        'search_keyword': 'happy',
                        'feishu_emoji': '[微笑]',
                        'tags': ['happy'],
                        'keywords': ['happy'],
                    },
                ],
            },
        },
    }
    query.variables['workflow_intent'] = {'intent': 'resource_confirmed', 'confidence': 0.9}
    query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='好的，孩子现在几年级呀')])]

    await stage.process(query, 'SendResponseBackStage')

    sent_chain = query.adapter.reply_message.await_args_list[0].kwargs['message']
    assert str(sent_chain) == '好的，孩子现在几年级呀 [了解]'


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

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == ['我把资源链接发您了，', '家长，您这边能打开吗？']


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

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '我们这个自然拼读课主要帮孩子打好拼读基础，课后也会有老师跟进',
        '孩子现在几年级呀？',
    ]


@pytest.mark.asyncio
async def test_respback_does_not_ask_child_grade_again_when_history_has_grade():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('还有什么课')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.messages = [
        provider_message.Message(role='user', content='三年级'),
        provider_message.Message(role='assistant', content='三年级刚好合适呀 😊'),
    ]
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text='咱们自然拼读大班到四年级都能学，正好补拼读规律和单词记忆方法。')]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '咱们自然拼读大班到四年级都能学，正好补拼读规律和单词记忆方法',
    ]


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

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == ['这个课适合小学阶段孩子，', '孩子现在几年级呀？']


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

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == [
        '如果页面一直报错，我这边可以帮您看一下',
        '方便发我一张截图吗？',
    ]


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
async def test_respback_uses_course_sales_faq_short_answer_verbatim():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('每天几点上课？直播吗？')
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.variables['workflow_intent'] = {
        'intent': 'course_schedule',
        'reply_mode': 'faq_polish',
        'faq_short_answer': '都是晚上19:00-20:00上课，分两周上。',
    }
    query.resp_messages = [
        provider_message.Message(role='assistant', content='是直播课哦，班主任会提前通知。')
    ]
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='是直播课哦，班主任会提前通知。')])
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [str(kwargs['message']) for _, kwargs in query.adapter.reply_message.await_args_list]
    assert sent_texts == ['都是晚上19:00-20:00上课，分两周上']
    assert query.resp_messages[-1].content == '都是晚上19:00-20:00上课，分两周上'


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
async def test_respback_splits_final_course_sales_stream_reply():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('您这边有数学课么')
    query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
    query.pipeline_config = _course_pipeline_config(multi_reply_enabled=False)
    query.resp_messages = [
        provider_message.MessageChunk(
            role='assistant',
            content='有的哦\n我们还有9元的阅读+思维体验课\n适合小学阶段的孩子 还支持回放',
            is_final=True,
        )
    ]
    query.resp_message_chain = [
        platform_message.MessageChain(
            [
                platform_message.Plain(
                    text='有的哦\n我们还有9元的阅读+思维体验课\n适合小学阶段的孩子 还支持回放'
                )
            ]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_chunk_chain = query.adapter.reply_message_chunk.await_args.kwargs['message']
    sent_reply_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert str(sent_chunk_chain) == '有的哦'
    assert sent_reply_texts == [
        '我们还有9元的阅读+思维体验课',
        '适合小学阶段的孩子 还支持回放',
        '孩子现在几年级呀？',
    ]


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
        '猿辅导英语自然拼读9元体验课点这里👉',
        tracking_link,
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
