from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

sys.modules.setdefault('dashscope', types.ModuleType('dashscope'))

from langbot.pkg.api.http.service.workflow import (
    COURSE_SALES_WORKFLOW_TEMPLATE_UUID,
    TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID,
    WorkflowService,
)
from langbot.pkg.entity.persistence.workflow import WorkflowFolder, WorkflowProject


pytestmark = pytest.mark.asyncio


def _result(*, items=None, first_item=None):
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    return result


def _workflow(uuid='workflow-1', folder='我的项目', name='流程一', description='说明', workflow=None):
    item = Mock(spec=WorkflowProject)
    item.uuid = uuid
    item.folder = folder
    item.name = name
    item.description = description
    item.workflow = workflow or {'version': 1, 'nodes': [], 'edges': []}
    item.created_at = None
    item.updated_at = None
    return item


def _folder(name='我的项目'):
    item = Mock(spec=WorkflowFolder)
    item.name = name
    item.created_at = None
    item.updated_at = None
    return item


async def test_get_workflow_library_returns_folders_and_workflows():
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(
                side_effect=[
                    _result(
                        items=[
                            _workflow(uuid=COURSE_SALES_WORKFLOW_TEMPLATE_UUID),
                            _workflow(uuid=TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID),
                        ]
                    ),
                    _result(items=[_folder('我的项目')]),
                    _result(items=[_workflow()]),
                ]
            ),
            serialize_model=lambda _model, item: item.__dict__,
        )
    )
    service = WorkflowService(ap)

    data = await service.get_workflow_library()

    assert data['folders'] == ['我的项目']
    assert data['workflows'][0]['uuid'] == 'workflow-1'
    assert data['workflows'][0]['workflow']['nodes'] == []


async def test_get_workflow_library_seeds_builtin_templates_once():
    course_workflow = {'version': 1, 'nodes': [{'id': str(i)} for i in range(21)], 'edges': [{'id': str(i)} for i in range(28)]}
    task_workflow = {'version': 1, 'nodes': [{'id': str(i)} for i in range(28)], 'edges': [{'id': str(i)} for i in range(38)]}
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(
                side_effect=[
                    _result(first_item=None),
                    None,
                    None,
                    None,
                    _result(items=[_folder('我的项目')]),
                    _result(
                        items=[
                            _workflow(
                                uuid='workflow-template-course-sales',
                                name='课程销售模板',
                                workflow=course_workflow,
                            ),
                            _workflow(
                                uuid='workflow-template-task-assistant',
                                name='任务助手模板配置版',
                                workflow=task_workflow,
                            ),
                        ]
                    ),
                ]
            )
        )
    )
    service = WorkflowService(ap)

    data = await service.get_workflow_library()

    seed_inserts = [
        call.args[0].compile().params
        for call in ap.persistence_mgr.execute_async.await_args_list
        if 'INSERT INTO workflow_projects' in str(call.args[0])
    ]
    assert [item['name'] for item in seed_inserts] == ['课程销售模板', '任务助手模板配置版']
    assert len(seed_inserts[0]['workflow']['nodes']) == 21
    assert len(seed_inserts[0]['workflow']['edges']) == 28
    assert len(seed_inserts[1]['workflow']['nodes']) == 28
    assert len(seed_inserts[1]['workflow']['edges']) == 38
    assert [item['name'] for item in data['workflows']] == ['课程销售模板', '任务助手模板配置版']


async def test_get_workflow_library_does_not_reseed_when_builtin_templates_exist():
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(
                side_effect=[
                    _result(
                        items=[
                            _workflow(uuid=COURSE_SALES_WORKFLOW_TEMPLATE_UUID),
                            _workflow(uuid=TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID),
                        ]
                    ),
                    _result(items=[_folder('我的项目')]),
                    _result(items=[]),
                ]
            )
        )
    )
    service = WorkflowService(ap)

    await service.get_workflow_library()

    statements = [str(call.args[0]) for call in ap.persistence_mgr.execute_async.await_args_list]
    assert not any('INSERT INTO workflow_projects' in statement for statement in statements)


async def test_get_workflow_library_restores_missing_builtin_templates_without_overwriting_existing():
    existing_course = _workflow(
        uuid=COURSE_SALES_WORKFLOW_TEMPLATE_UUID,
        name='用户改过的课程销售模板',
        workflow={'version': 1, 'nodes': [{'id': 'custom'}], 'edges': []},
    )
    task_workflow = {'version': 1, 'nodes': [{'id': str(i)} for i in range(28)], 'edges': [{'id': str(i)} for i in range(38)]}
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(
                side_effect=[
                    _result(items=[existing_course]),
                    None,
                    None,
                    _result(items=[_folder('我的项目')]),
                    _result(items=[existing_course, _workflow(uuid=TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID, workflow=task_workflow)]),
                ]
            )
        )
    )
    service = WorkflowService(ap)

    data = await service.get_workflow_library()

    seed_inserts = [
        call.args[0].compile().params
        for call in ap.persistence_mgr.execute_async.await_args_list
        if 'INSERT INTO workflow_projects' in str(call.args[0])
    ]
    assert len(seed_inserts) == 1
    assert seed_inserts[0]['uuid'] == TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID
    assert data['workflows'][0]['name'] == '用户改过的课程销售模板'
    assert data['workflows'][0]['is_builtin'] is True


async def test_create_workflow_persists_folder_and_project():
    ap = SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=AsyncMock()))
    service = WorkflowService(ap)

    workflow_uuid = await service.create_workflow(
        {
            'folder': '销售流程',
            'name': '新工作流',
            'description': '持久化测试',
            'workflow': {'version': 1, 'nodes': [], 'edges': []},
        }
    )

    assert workflow_uuid
    assert ap.persistence_mgr.execute_async.await_count == 2
    first_statement = str(ap.persistence_mgr.execute_async.await_args_list[0].args[0]).upper()
    second_statement = str(ap.persistence_mgr.execute_async.await_args_list[1].args[0]).upper()
    assert 'WORKFLOW_FOLDERS' in first_statement
    assert 'WORKFLOW_PROJECTS' in second_statement


async def test_update_workflow_updates_only_editable_fields():
    ap = SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=AsyncMock()))
    service = WorkflowService(ap)

    await service.update_workflow(
        'workflow-1',
        {
            'uuid': 'ignored',
            'folder': '我的项目',
            'name': '改名',
            'description': '新说明',
            'workflow': {'version': 1, 'nodes': [{'id': 'start'}], 'edges': []},
        },
    )

    update_statement = ap.persistence_mgr.execute_async.await_args_list[-1].args[0]
    params = update_statement.compile().params
    assert params['name'] == '改名'
    assert params['workflow']['nodes'][0]['id'] == 'start'
    assert 'uuid' not in params


async def test_delete_workflow_removes_project():
    ap = SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=AsyncMock()))
    service = WorkflowService(ap)

    await service.delete_workflow('workflow-1')

    statement = str(ap.persistence_mgr.execute_async.await_args.args[0]).upper()
    assert 'DELETE FROM WORKFLOW_PROJECTS' in statement


async def test_delete_workflow_rejects_builtin_templates():
    ap = SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=AsyncMock()))
    service = WorkflowService(ap)

    with pytest.raises(ValueError, match='Built-in workflow cannot be deleted'):
        await service.delete_workflow(COURSE_SALES_WORKFLOW_TEMPLATE_UUID)

    ap.persistence_mgr.execute_async.assert_not_called()
