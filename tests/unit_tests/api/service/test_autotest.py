from __future__ import annotations

from types import SimpleNamespace

from langbot.pkg.api.http.service.autotest import AutoTestService


def _message(role: str, content: str) -> dict[str, object]:
    return {
        'role': role,
        'sender': '模拟家长' if role == 'user' else '课程顾问',
        'content_type': 'text',
        'content': content,
        'turn': 1,
    }


def test_course_sales_replay_flags_low_quality_ai_reply():
    service = AutoTestService(SimpleNamespace())
    long_reply = (
        '作为一个AI语言模型，我会根据您的需求为您介绍课程。'
        '我们的自然拼读体验课覆盖字母音、拼读规则、阅读启蒙、互动练习、课后巩固、学习反馈、'
        '阶段测评和家长沟通等多个模块，能够帮助孩子逐步建立英语学习兴趣和学习习惯，'
        '并且我们还有很多资料可以查看，链接是 https://example.com/apply ，详情请参考待补充内容。'
    )

    evaluation = service._evaluate_conversation(
        [
            _message('user', '孩子6岁，英语零基础，想问自然拼读体验课适不适合？'),
            _message('assistant', long_reply),
        ]
    )

    assert evaluation['checks']['keeps_readable_reply'] is False
    assert evaluation['checks']['asks_opening_or_next_question'] is False
    assert evaluation['checks']['avoids_ai_phrasing'] is False
    assert evaluation['checks']['avoids_placeholder_links'] is False
    assert '课程销售回复要更短' in evaluation['suggestions']
    assert '补一个自然的开场/下一步问题' in evaluation['suggestions']
    assert '去掉 AI 自称或模板化措辞' in evaluation['suggestions']
    assert '不要输出 example.com、待补充等占位链接或占位文案' in evaluation['suggestions']


def test_course_sales_replay_accepts_concise_human_reply():
    service = AutoTestService(SimpleNamespace())

    evaluation = service._evaluate_conversation(
        [
            _message('user', '孩子6岁，英语零基础，想问自然拼读体验课适不适合？'),
            _message(
                'assistant',
                '适合先体验。6岁零基础可以从字母音和简单拼读开始，我先帮您确认孩子现在会认26个字母吗？',
            ),
            _message('user', '会一点，但读单词不太行。'),
            _message('assistant', '明白，这个顾虑很正常。下一步可以先看9元体验课资料，再决定要不要报名或转人工确认。'),
        ]
    )

    assert evaluation['checks']['keeps_readable_reply'] is True
    assert evaluation['checks']['asks_opening_or_next_question'] is True
    assert evaluation['checks']['avoids_ai_phrasing'] is True
    assert evaluation['checks']['avoids_placeholder_links'] is True
