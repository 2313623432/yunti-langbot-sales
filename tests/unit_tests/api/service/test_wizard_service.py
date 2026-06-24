from langbot.pkg.api.http.service.wizard import sanitize_wizard_progress


def test_sanitize_wizard_progress_clears_missing_created_bot():
    progress = {
        'step': 1,
        'selected_adapter': 'lark',
        'created_bot_uuid': 'missing-bot',
        'bot_saved': True,
        'selected_runner': None,
    }

    sanitized = sanitize_wizard_progress(progress, created_bot_exists=False)

    assert sanitized == {
        'step': 1,
        'selected_adapter': 'lark',
        'created_bot_uuid': None,
        'bot_saved': False,
        'selected_runner': None,
    }


def test_sanitize_wizard_progress_keeps_existing_created_bot():
    progress = {
        'step': 1,
        'selected_adapter': 'lark',
        'created_bot_uuid': 'existing-bot',
        'bot_saved': True,
        'selected_runner': None,
    }

    sanitized = sanitize_wizard_progress(progress, created_bot_exists=True)

    assert sanitized == progress
