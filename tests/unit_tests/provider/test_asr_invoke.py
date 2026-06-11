import pytest

from langbot.pkg.provider.modelmgr import asr_invoke


def test_apply_provider_api_keys_for_volcengine_asr_single_key():
    resolved = asr_invoke.apply_provider_api_keys(
        {'model': 'bigmodel'},
        requester='volcengine-asr',
        api_keys=['speech-api-key'],
    )

    assert resolved['token'] == 'speech-api-key'
    assert resolved['requester'] == 'volcengine-asr'


@pytest.mark.asyncio
async def test_request_volcengine_asr_uses_api_key_header(monkeypatch):
    captured = {}

    class _Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def json(self, content_type=None):
            return {'result': {'text': '你好，想了解课程。'}}

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        def post(self, url, **kwargs):
            captured['url'] = url
            captured['kwargs'] = kwargs
            return _Response()

    monkeypatch.setattr(asr_invoke.aiohttp, 'ClientSession', lambda: _Session())

    text = await asr_invoke.invoke_asr(
        asr_invoke.ASRInvokeConfig(
            requester='volcengine-asr',
            provider='volcengine-asr',
            model='bigmodel',
            token='speech-api-key',
            base_url='https://openspeech.bytedance.com',
            audio_base64='data:audio/mpeg;base64,YWJj',
            extra_args={'resource_id': 'volc.bigasr.auc_turbo'},
        )
    )

    assert text == '你好，想了解课程。'
    assert captured['url'] == 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash'
    assert captured['kwargs']['headers']['X-Api-Key'] == 'speech-api-key'
    assert captured['kwargs']['headers']['X-Api-Resource-Id'] == 'volc.bigasr.auc_turbo'
    assert captured['kwargs']['headers']['X-Api-Sequence'] == '-1'
    assert captured['kwargs']['json']['audio']['data'] == 'YWJj'
