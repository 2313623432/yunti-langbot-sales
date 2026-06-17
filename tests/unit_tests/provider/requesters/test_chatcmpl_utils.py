"""Tests for requester pure utility functions.

Tests the helper methods in OpenAIChatCompletions that don't require network calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.utils.import_isolation import isolated_sys_modules


class TestMaskApiKey:
    """Tests for _mask_api_key method."""

    def _create_requester_with_mocks(self):
        """Create requester instance with mocked dependencies."""
        mocks = {
            'langbot.pkg.core.app': MagicMock(),
            'langbot_plugin.api.entities.builtin.resource.tool': MagicMock(),
            'langbot_plugin.api.entities.builtin.pipeline.query': MagicMock(),
            'langbot_plugin.api.entities.builtin.provider.message': MagicMock(),
            'langbot.pkg.provider.modelmgr.errors': MagicMock(),
        }

        with isolated_sys_modules(mocks):
            from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

            mock_app = MagicMock()
            requester = OpenAIChatCompletions(mock_app, {})
            return requester

    def test_mask_api_key_full(self):
        """Mask a full API key."""
        requester = self._create_requester_with_mocks()

        result = requester._mask_api_key('sk-1234567890abcdef')
        assert result == 'sk-1...cdef'

    def test_mask_api_key_short(self):
        """Mask a short API key (<=8 chars)."""
        requester = self._create_requester_with_mocks()

        result = requester._mask_api_key('short')
        assert result == '****'

    def test_mask_api_key_empty(self):
        """Empty API key returns empty string."""
        requester = self._create_requester_with_mocks()

        result = requester._mask_api_key('')
        assert result == ''

    def test_mask_api_key_none(self):
        """None API key returns empty string."""
        requester = self._create_requester_with_mocks()

        result = requester._mask_api_key(None)
        assert result == ''

    def test_mask_api_key_exact_8_chars(self):
        """API key with exactly 8 chars is masked as **** (<=8 threshold)."""
        requester = self._create_requester_with_mocks()

        result = requester._mask_api_key('12345678')
        assert result == '****'  # <= 8 chars gets masked


class TestInferModelType:
    """Tests for _infer_model_type method."""

    def _create_requester_with_mocks(self):
        mocks = {
            'langbot.pkg.core.app': MagicMock(),
            'langbot_plugin.api.entities.builtin.resource.tool': MagicMock(),
            'langbot_plugin.api.entities.builtin.pipeline.query': MagicMock(),
            'langbot_plugin.api.entities.builtin.provider.message': MagicMock(),
            'langbot.pkg.provider.modelmgr.errors': MagicMock(),
        }

        with isolated_sys_modules(mocks):
            from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

            mock_app = MagicMock()
            requester = OpenAIChatCompletions(mock_app, {})
            return requester

    def test_infer_embedding_from_name(self):
        """Infer embedding type from model name."""
        requester = self._create_requester_with_mocks()

        assert requester._infer_model_type('text-embedding-ada-002') == 'embedding'
        assert requester._infer_model_type('bge-large-en') == 'embedding'
        assert requester._infer_model_type('e5-base') == 'embedding'
        assert requester._infer_model_type('m3e-base') == 'embedding'

    def test_infer_llm_from_name(self):
        """Infer LLM type from model name."""
        requester = self._create_requester_with_mocks()

        assert requester._infer_model_type('gpt-4') == 'llm'
        assert requester._infer_model_type('claude-3-opus') == 'llm'
        assert requester._infer_model_type('llama-2-70b') == 'llm'

    def test_infer_model_type_none_id(self):
        """Handle None model_id."""
        requester = self._create_requester_with_mocks()

        result = requester._infer_model_type(None)
        assert result == 'llm'  # Default

    def test_infer_model_type_empty_id(self):
        """Handle empty model_id."""
        requester = self._create_requester_with_mocks()

        result = requester._infer_model_type('')
        assert result == 'llm'  # Default


class TestNormalizeModalities:
    """Tests for _normalize_modalities method."""

    def _create_requester_with_mocks(self):
        mocks = {
            'langbot.pkg.core.app': MagicMock(),
            'langbot_plugin.api.entities.builtin.resource.tool': MagicMock(),
            'langbot_plugin.api.entities.builtin.pipeline.query': MagicMock(),
            'langbot_plugin.api.entities.builtin.provider.message': MagicMock(),
            'langbot.pkg.provider.modelmgr.errors': MagicMock(),
        }

        with isolated_sys_modules(mocks):
            from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

            mock_app = MagicMock()
            requester = OpenAIChatCompletions(mock_app, {})
            return requester

    def test_normalize_string_modality(self):
        """Normalize single string modality."""
        requester = self._create_requester_with_mocks()

        result = requester._normalize_modalities('text,image')
        assert result == ['text', 'image']

    def test_normalize_list_modalities(self):
        """Normalize list of modalities."""
        requester = self._create_requester_with_mocks()

        result = requester._normalize_modalities(['text', 'image', 'audio'])
        assert result == ['text', 'image', 'audio']

    def test_normalize_dict_modalities(self):
        """Normalize dict with nested modalities."""
        requester = self._create_requester_with_mocks()

        result = requester._normalize_modalities({'input': ['text'], 'output': ['text', 'image']})
        assert result == ['text', 'image']

    def test_normalize_none(self):
        """Handle None input."""
        requester = self._create_requester_with_mocks()

        result = requester._normalize_modalities(None)
        assert result == []

    def test_normalize_arrow_separator(self):
        """Handle arrow separator in modality string."""
        requester = self._create_requester_with_mocks()

        result = requester._normalize_modalities('text->image')
        assert result == ['text', 'image']


class TestParseRerankResponse:
    """Tests for _parse_rerank_response static method."""

    def test_parse_cohere_jina_format(self):
        """Parse Cohere/Jina/SiliconFlow format."""
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        data = {
            'results': [
                {'index': 0, 'relevance_score': 0.95},
                {'index': 1, 'relevance_score': 0.80},
            ]
        }

        result = OpenAIChatCompletions._parse_rerank_response(data)
        assert result == [
            {'index': 0, 'relevance_score': 0.95},
            {'index': 1, 'relevance_score': 0.80},
        ]

    def test_parse_voyage_format(self):
        """Parse Voyage AI format."""
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        data = {
            'data': [
                {'index': 0, 'relevance_score': 0.90},
                {'index': 2, 'relevance_score': 0.75},
            ]
        }

        result = OpenAIChatCompletions._parse_rerank_response(data)
        assert result == [
            {'index': 0, 'relevance_score': 0.90},
            {'index': 2, 'relevance_score': 0.75},
        ]

    def test_parse_dashscope_format(self):
        """Parse DashScope format."""
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        data = {
            'output': {
                'results': [
                    {'index': 0, 'relevance_score': 0.85},
                ]
            }
        }

        result = OpenAIChatCompletions._parse_rerank_response(data)
        assert result == [{'index': 0, 'relevance_score': 0.85}]

    def test_parse_unknown_format(self):
        """Handle unknown format returns empty list."""
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        data = {'unknown_key': 'value'}

        result = OpenAIChatCompletions._parse_rerank_response(data)
        assert result == []

    def test_parse_empty_results(self):
        """Handle empty results."""
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        data = {'results': []}

        result = OpenAIChatCompletions._parse_rerank_response(data)
        assert result == []


class TestThinkingContent:
    @pytest.mark.asyncio
    async def test_process_thinking_content_removes_reasoning_and_think_tags(self):
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        requester = OpenAIChatCompletions(MagicMock(), {})

        content, thinking = await requester._process_thinking_content(
            content='<think>internal reasoning</think>\n请问您这边能打开吗？',
            reasoning_content='hidden chain',
            remove_think=True,
        )

        assert content == '请问您这边能打开吗？'
        assert thinking == ''
        assert '<think>' not in content
        assert 'hidden chain' not in content

    def test_remove_think_delta_filters_streaming_content_tags(self):
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        requester = OpenAIChatCompletions(MagicMock(), {})

        first, inside = requester._remove_think_delta('<think>internal', False)
        second, inside = requester._remove_think_delta(' reasoning</think>您好', inside)
        third, inside = requester._remove_think_delta('，家长这边能打开吗？', inside)

        assert first == ''
        assert second == '您好'
        assert third == '，家长这边能打开吗？'
        assert inside is False

    def test_volcark_requester_disables_thinking_by_default(self):
        from langbot.pkg.provider.modelmgr.requesters.volcarkchatcmpl import VolcArkChatCompletions

        requester = VolcArkChatCompletions(MagicMock(), {})

        extra_body = requester._prepare_extra_body({'temperature': 0.4})

        assert extra_body['temperature'] == 0.4
        assert extra_body['thinking'] == {'type': 'disabled'}
        assert extra_body['reasoning_effort'] == 'minimal'


class TestExtractScanMetadata:
    """Tests for _extract_scan_metadata method."""

    def _create_requester_with_mocks(self):
        mocks = {
            'langbot.pkg.core.app': MagicMock(),
            'langbot_plugin.api.entities.builtin.resource.tool': MagicMock(),
            'langbot_plugin.api.entities.builtin.pipeline.query': MagicMock(),
            'langbot_plugin.api.entities.builtin.provider.message': MagicMock(),
            'langbot.pkg.provider.modelmgr.errors': MagicMock(),
        }

        with isolated_sys_modules(mocks):
            from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

            mock_app = MagicMock()
            requester = OpenAIChatCompletions(mock_app, {})
            return requester

    def test_extract_basic_metadata(self):
        """Extract basic model metadata."""
        requester = self._create_requester_with_mocks()

        item = {
            'id': 'gpt-4',
            'name': 'GPT-4 Turbo',
            'description': 'Most capable GPT-4 model',
            'context_length': 128000,
            'owned_by': 'openai',
        }

        result = requester._extract_scan_metadata(item, 'gpt-4')

        assert result['display_name'] == 'GPT-4 Turbo'
        assert result['description'] == 'Most capable GPT-4 model'
        assert result['context_length'] == 128000
        assert result['owned_by'] == 'openai'

    def test_extract_metadata_missing_fields(self):
        """Handle missing metadata fields."""
        requester = self._create_requester_with_mocks()

        item = {'id': 'unknown-model'}

        result = requester._extract_scan_metadata(item, 'unknown-model')

        assert result['display_name'] is None
        assert result['description'] is None
        assert result['context_length'] is None
        assert result['owned_by'] is None

    def test_extract_metadata_top_provider_context(self):
        """Extract context_length from top_provider."""
        requester = self._create_requester_with_mocks()

        item = {
            'id': 'model',
            'top_provider': {
                'context_length': 4096,
            },
        }

        result = requester._extract_scan_metadata(item, 'model')

        assert result['context_length'] == 4096

    def test_extract_metadata_empty_strings(self):
        """Handle empty string values."""
        requester = self._create_requester_with_mocks()

        item = {
            'id': 'model',
            'name': '',  # Empty name
            'description': '   ',  # Whitespace only
            'owned_by': '',
        }

        result = requester._extract_scan_metadata(item, 'model')

        assert result['display_name'] is None
        assert result['description'] is None
        assert result['owned_by'] is None

    def test_extract_metadata_name_matches_id(self):
        """When name equals id, display_name is None."""
        requester = self._create_requester_with_mocks()

        item = {
            'id': 'gpt-4',
            'name': 'gpt-4',  # Same as id
        }

        result = requester._extract_scan_metadata(item, 'gpt-4')

        assert result['display_name'] is None
