from __future__ import annotations

from langbot.pkg.provider.modelmgr import provider_request_url


def test_text_openai_compatible_request_url():
    assert (
        provider_request_url.resolve_text_request_url(
            'openai-chat-completions',
            'https://api.openai.com/v1',
        )
        == 'https://api.openai.com/v1/chat/completions'
    )


def test_text_deepseek_request_url_without_v1_suffix():
    assert (
        provider_request_url.resolve_text_request_url(
            'deepseek-chat-completions',
            'https://api.deepseek.com',
        )
        == 'https://api.deepseek.com/chat/completions'
    )


def test_text_anthropic_request_url():
    assert (
        provider_request_url.resolve_text_request_url(
            'anthropic-messages',
            'https://api.anthropic.com',
        )
        == 'https://api.anthropic.com/v1/messages'
    )


def test_text_ollama_request_url():
    assert (
        provider_request_url.resolve_text_request_url(
            'ollama-chat',
            'http://127.0.0.1:11434',
        )
        == 'http://127.0.0.1:11434/api/chat'
    )


def test_embedding_openai_compatible_request_url():
    assert (
        provider_request_url.resolve_embedding_request_url(
            'openai-chat-completions',
            'https://api.openai.com/v1',
        )
        == 'https://api.openai.com/v1/embeddings'
    )


def test_embedding_ollama_request_url():
    assert (
        provider_request_url.resolve_embedding_request_url(
            'ollama-chat',
            'http://127.0.0.1:11434',
        )
        == 'http://127.0.0.1:11434/api/embed'
    )


def test_voice_qwen_request_url():
    assert (
        provider_request_url.resolve_voice_request_url(
            'bailian-chat-completions',
            'https://dashscope.aliyuncs.com/api/v1',
        )
        == 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
    )


def test_voice_volcengine_request_url():
    assert (
        provider_request_url.resolve_voice_request_url(
            'volcengine-tts',
            'https://openspeech.bytedance.com',
        )
        == 'https://openspeech.bytedance.com/api/v1/tts'
    )


def test_voice_azure_request_url():
    assert (
        provider_request_url.resolve_voice_request_url(
            'azure-tts',
            'https://eastus.tts.speech.microsoft.com',
        )
        == 'https://eastus.tts.speech.microsoft.com/cognitiveservices/v1'
    )


def test_voice_elevenlabs_request_url():
    assert (
        provider_request_url.resolve_voice_request_url(
            'elevenlabs-tts',
            'https://api.elevenlabs.io/v1',
        )
        == 'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
    )


def test_voice_zhipu_request_url():
    assert (
        provider_request_url.resolve_voice_request_url(
            'zhipuai-chat-completions',
            'https://open.bigmodel.cn/api/paas/v4',
        )
        == 'https://open.bigmodel.cn/api/paas/v4/audio/speech'
    )


def test_voice_minimax_request_url():
    assert (
        provider_request_url.resolve_voice_request_url(
            'openai-chat-completions',
            'https://api.minimaxi.com',
        )
        == 'https://api.minimaxi.com/v1/t2a_v2'
    )


def test_voice_openai_request_url():
    assert (
        provider_request_url.resolve_voice_request_url(
            'openai-chat-completions',
            'https://api.openai.com/v1',
        )
        == 'https://api.openai.com/v1/audio/speech'
    )


def test_pdf_mineru_cloud_request_url():
    assert (
        provider_request_url.resolve_pdf_request_url(
            'mineru-cloud',
            'https://mineru.net/api/v4',
        )
        == 'https://mineru.net/api/v4/file-urls/batch'
    )


def test_pdf_paddleocr_request_url_matches_base_url():
    jobs_url = 'https://paddleocr.aistudio-app.com/api/v2/ocr/jobs'
    assert (
        provider_request_url.resolve_pdf_request_url('paddleocr-vl', jobs_url)
        == jobs_url
    )


def test_pdf_builtin_request_url_matches_base_url():
    assert (
        provider_request_url.resolve_pdf_request_url('builtin-pdf-parse', 'local://pdf')
        == 'local://pdf'
    )


def test_resolve_provider_request_url_dispatches_by_category():
    assert (
        provider_request_url.resolve_provider_request_url(
            'text',
            'gemini-chat-completions',
            'https://generativelanguage.googleapis.com/v1beta/openai',
        )
        == 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
    )
