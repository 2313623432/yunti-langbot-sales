from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service.autotest import AutoTestService


pytestmark = pytest.mark.asyncio


async def test_unsatisfied_feedback_requires_reason():
    service = AutoTestService(SimpleNamespace())

    with pytest.raises(ValueError, match='reason is required'):
        await service.submit_feedback('run-1', {'feedback': 'unsatisfied', 'reason': '   '})


async def test_unsatisfied_feedback_generates_and_applies_optimization_note():
    ap = SimpleNamespace()
    ap.persistence_mgr = SimpleNamespace()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.pipeline_service = SimpleNamespace()
    ap.pipeline_service.get_pipeline = AsyncMock(
        return_value={
            'uuid': 'pipeline-1',
            'name': 'Sales Agent',
            'description': '',
            'config': {'template_config': {'role_prompt': 'Be helpful'}},
        }
    )
    ap.pipeline_service.update_pipeline = AsyncMock()
    service = AutoTestService(ap)
    service.get_run = AsyncMock(
        return_value={
            'uuid': 'run-1',
            'target_type': 'pipeline',
            'target_uuid': 'pipeline-1',
            'target_name': 'Sales Agent',
            'scenario': '客户说价格太贵',
            'messages': [
                {'role': 'user', 'content': '价格太贵了'},
                {'role': 'assistant', 'content': '好的'},
            ],
            'evaluation': {},
        }
    )

    result = await service.submit_feedback(
        'run-1',
        {'feedback': 'unsatisfied', 'reason': '没有回应价格异议，也没有引导下一步'},
    )

    assert result['user_feedback'] == 'unsatisfied'
    assert '没有回应价格异议' in result['optimization_summary']
    ap.pipeline_service.update_pipeline.assert_awaited_once()
    updated_config = ap.pipeline_service.update_pipeline.call_args.args[1]['config']
    notes = updated_config['auto_test_optimization_notes']
    assert notes[-1]['run_uuid'] == 'run-1'
    assert '没有回应价格异议' in notes[-1]['summary']


def test_serialize_run_accepts_sqlalchemy_column_mapping_row():
    ap = SimpleNamespace()
    ap.persistence_mgr = SimpleNamespace()
    service = AutoTestService(ap)

    row = SimpleNamespace(
        _mapping={
            'uuid': 'run-1',
            'target_type': 'pipeline',
            'target_uuid': 'pipeline-1',
            'target_name': 'Sales Agent',
            'status': 'completed',
            'scenario': '客户咨询价格',
            'messages': [],
            'evaluation': {},
            'user_feedback': '',
            'feedback_reason': '',
            'optimization_summary': '',
            'optimization_patch': {},
            'created_at': None,
            'updated_at': None,
        }
    )

    result = service._serialize_run(row)

    assert result['uuid'] == 'run-1'
    assert result['messages'] == []
    assert result['evaluation'] == {}
