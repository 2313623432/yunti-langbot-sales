from pathlib import Path


def test_preproc_keeps_image_urls_for_vision_models():
    source = Path('src/langbot/pkg/pipeline/preproc/preproc.py').read_text(encoding='utf-8')

    assert 'from_image_base64(me.base64)' in source
    assert 'from_image_url(me.url)' in source
    assert 'from_image_base64(msg.base64)' in source
    assert 'from_image_url(msg.url)' in source
