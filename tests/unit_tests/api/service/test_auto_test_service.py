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


async def test_unsatisfied_feedback_applies_pipeline_prompt_patch_from_optimizer():
    ap = SimpleNamespace()
    ap.persistence_mgr = SimpleNamespace()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.pipeline_service = SimpleNamespace()
    ap.pipeline_service.get_pipeline = AsyncMock(
        return_value={
            'uuid': 'pipeline-1',
            'name': 'Sales Agent',
            'description': '',
            'config': {
                'template_config': {
                    'role_prompt': 'Be helpful',
                    'opening_message': 'Hello',
                }
            },
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
            'scenario': 'Customer asks about price.',
            'messages': [
                {'role': 'user', 'content': 'The price is too high.'},
                {'role': 'assistant', 'content': 'Ok.'},
            ],
            'evaluation': {},
        }
    )
    service._generate_optimization_plan = AsyncMock(
        return_value={
            'summary': 'Handle price objections and guide the next step.',
            'ai_generated': True,
            'model_uuid': 'model-1',
            'model_name': 'optimizer-model',
            'patches': [
                {
                    'path': 'config.template_config.role_prompt',
                    'value': 'Improved prompt for price objections.',
                },
                {
                    'path': 'config.template_config.opening_message',
                    'value': 'Improved opening message.',
                },
            ],
        }
    )

    result = await service.submit_feedback(
        'run-1',
        {'feedback': 'unsatisfied', 'reason': 'Did not answer price objection or guide the next step.'},
    )

    assert result['user_feedback'] == 'unsatisfied'
    assert result['optimization_summary'] == 'Handle price objections and guide the next step.'
    ap.pipeline_service.update_pipeline.assert_awaited_once()
    updated_config = ap.pipeline_service.update_pipeline.call_args.args[1]['config']
    assert updated_config['template_config']['role_prompt'] == 'Improved prompt for price objections.'
    assert updated_config['template_config']['opening_message'] == 'Improved opening message.'
    assert updated_config['auto_test_optimization_history'][-1]['run_uuid'] == 'run-1'
    assert len(updated_config['auto_test_version_history']) == 1
    assert updated_config['auto_test_version_history'][-1]['run_uuid'] == 'run-1'
    assert result['optimization_patch']['operation'] == 'apply_config_patch'
    assert result['optimization_patch']['target_type'] == 'pipeline'
    assert result['optimization_patch']['version_retention'] == 3
    assert result['optimization_patch']['applied_patches'][0]['path'] == 'config.template_config.role_prompt'


async def test_unsatisfied_feedback_applies_workflow_node_prompt_patch_from_optimizer():
    ap = SimpleNamespace()
    ap.persistence_mgr = SimpleNamespace()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.workflow_service = SimpleNamespace()
    ap.workflow_service.get_workflow_library = AsyncMock(
        return_value={
            'workflows': [
                {
                    'uuid': 'workflow-1',
                    'name': 'Sales Workflow',
                    'description': '',
                    'workflow': {
                        'nodes': [
                            {
                                'id': 'llm-node',
                                'type': 'llm',
                                'title': 'AI reply',
                                'description': 'Old description',
                                'config': {'prompt': 'Old prompt'},
                            }
                        ],
                        'edges': [],
                    },
                }
            ]
        }
    )
    ap.workflow_service.update_workflow = AsyncMock()
    service = AutoTestService(ap)
    service.get_run = AsyncMock(
        return_value={
            'uuid': 'run-2',
            'target_type': 'workflow',
            'target_uuid': 'workflow-1',
            'target_name': 'Sales Workflow',
            'scenario': 'Customer asks for a handoff.',
            'messages': [
                {'role': 'user', 'content': 'human please'},
                {'role': 'assistant', 'content': 'ok'},
            ],
            'evaluation': {},
        }
    )
    service._generate_optimization_plan = AsyncMock(
        return_value={
            'summary': 'Escalate angry customers and keep the reply readable.',
            'patches': [
                {
                    'path': 'workflow.nodes.llm-node.config.prompt',
                    'value': 'New workflow prompt with human handoff rules.',
                }
            ],
        }
    )

    result = await service.submit_feedback(
        'run-2',
        {'feedback': 'unsatisfied', 'reason': 'Needs a better handoff rule.'},
    )

    ap.workflow_service.update_workflow.assert_awaited_once()
    updated_workflow = ap.workflow_service.update_workflow.call_args.args[1]['workflow']
    assert updated_workflow['nodes'][0]['config']['prompt'] == 'New workflow prompt with human handoff rules.'
    assert updated_workflow['auto_test_optimization_history'][-1]['run_uuid'] == 'run-2'
    assert len(updated_workflow['auto_test_version_history']) == 1
    assert result['optimization_patch']['target_type'] == 'workflow'
    assert result['optimization_patch']['applied_patches'][0]['path'] == 'workflow.nodes.llm-node.config.prompt'


async def test_start_run_with_sop_auto_applies_pipeline_optimization_patch():
    ap = SimpleNamespace()
    ap.persistence_mgr = SimpleNamespace()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.pipeline_service = SimpleNamespace()
    ap.pipeline_service.get_pipeline = AsyncMock(
        return_value={
            'uuid': 'pipeline-1',
            'name': 'Sales Agent',
            'description': '',
            'config': {
                'template_config': {
                    'role_prompt': 'Original sales prompt',
                    'opening_message': 'Hello',
                }
            },
        }
    )
    ap.pipeline_service.update_pipeline = AsyncMock()
    service = AutoTestService(ap)
    service.get_run = AsyncMock(return_value=None)
    service._generate_test_conversation = AsyncMock(
        return_value=(
            [
                {'role': 'user', 'sender': 'Customer', 'content_type': 'text', 'content': 'I need a human.', 'turn': 1},
                {'role': 'assistant', 'sender': 'Sales Agent', 'content_type': 'text', 'content': 'Ok.', 'turn': 1},
            ],
            {'score': 1, 'max_score': 3, 'checks': {}, 'suggestions': ['Add SOP handoff rule.']},
        )
    )
    service._generate_optimization_plan = AsyncMock(
        return_value={
            'summary': 'Apply the uploaded SOP handoff rule.',
            'patches': [
                {
                    'path': 'config.template_config.role_prompt',
                    'value': 'Prompt updated from uploaded SOP.',
                }
            ],
        }
    )

    result = await service.start_run(
        {
            'target_type': 'pipeline',
            'target_uuid': 'pipeline-1',
            'scenario': 'handoff SOP check',
            'turns': 1,
            'sop_text': 'When the customer asks for a human, transfer immediately.',
            'sop_filename': 'handoff.md',
        }
    )

    assert result['evaluation']['sop']['filename'] == 'handoff.md'
    assert result['optimization_summary'] == 'Apply the uploaded SOP handoff rule.'
    assert result['optimization_patch']['operation'] == 'apply_config_patch'
    ap.pipeline_service.update_pipeline.assert_awaited_once()
    updated_config = ap.pipeline_service.update_pipeline.call_args.args[1]['config']
    assert updated_config['template_config']['role_prompt'] == 'Prompt updated from uploaded SOP.'


async def test_auto_test_version_history_keeps_last_three_snapshots():
    ap = SimpleNamespace()
    ap.persistence_mgr = SimpleNamespace()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.pipeline_service = SimpleNamespace()
    ap.pipeline_service.get_pipeline = AsyncMock(
        return_value={
            'uuid': 'pipeline-1',
            'name': 'Sales Agent',
            'description': '',
            'config': {
                'template_config': {'role_prompt': 'v3 prompt'},
                'auto_test_version_history': [
                    {'run_uuid': 'old-1', 'snapshot': {}},
                    {'run_uuid': 'old-2', 'snapshot': {}},
                    {'run_uuid': 'old-3', 'snapshot': {}},
                ],
            },
        }
    )
    ap.pipeline_service.update_pipeline = AsyncMock()
    service = AutoTestService(ap)
    service.get_run = AsyncMock(
        return_value={
            'uuid': 'run-4',
            'target_type': 'pipeline',
            'target_uuid': 'pipeline-1',
            'target_name': 'Sales Agent',
            'scenario': 'version retention',
            'messages': [],
            'evaluation': {},
        }
    )
    service._generate_optimization_plan = AsyncMock(
        return_value={
            'summary': 'Keep only three versions.',
            'patches': [
                {'path': 'config.template_config.role_prompt', 'value': 'v4 prompt'},
            ],
        }
    )

    await service.submit_feedback('run-4', {'feedback': 'unsatisfied', 'reason': 'Improve.'})

    updated_config = ap.pipeline_service.update_pipeline.call_args.args[1]['config']
    assert [item['run_uuid'] for item in updated_config['auto_test_version_history']] == [
        'old-2',
        'old-3',
        'run-4',
    ]


async def test_revert_run_optimization_restores_pipeline_prompt_from_patch():
    ap = SimpleNamespace()
    ap.persistence_mgr = SimpleNamespace()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.pipeline_service = SimpleNamespace()
    ap.pipeline_service.get_pipeline = AsyncMock(
        return_value={
            'uuid': 'pipeline-1',
            'name': 'Sales Agent',
            'description': '',
            'config': {
                'template_config': {'role_prompt': 'new prompt'},
            },
        }
    )
    ap.pipeline_service.update_pipeline = AsyncMock()
    service = AutoTestService(ap)
    service.get_run = AsyncMock(
        return_value={
            'uuid': 'run-5',
            'target_type': 'pipeline',
            'target_uuid': 'pipeline-1',
            'target_name': 'Sales Agent',
            'optimization_patch': {
                'operation': 'apply_config_patch',
                'applied_patches': [
                    {
                        'path': 'config.template_config.role_prompt',
                        'before': 'old prompt',
                        'after': 'new prompt',
                    }
                ],
            },
        }
    )

    result = await service.revert_run_optimization('run-5')

    updated_config = ap.pipeline_service.update_pipeline.call_args.args[1]['config']
    assert updated_config['template_config']['role_prompt'] == 'old prompt'
    assert updated_config['auto_test_version_history'][-1]['run_uuid'] == 'run-5'
    assert result['optimization_patch']['reverted_at']
    assert result['optimization_patch']['reverted_patches'][0]['path'] == 'config.template_config.role_prompt'


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
            'scenario': 'Customer asks about price.',
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
