from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy

from ....core import app
from ....entity.persistence import workflow as persistence_workflow
from .task_assistant import TaskAssistantService


DEFAULT_WORKFLOW_FOLDER = '我的项目'
COURSE_SALES_WORKFLOW_TEMPLATE_UUID = 'workflow-template-course-sales'
TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID = 'workflow-template-task-assistant'
BUILTIN_WORKFLOW_TEMPLATE_UUIDS = {
    COURSE_SALES_WORKFLOW_TEMPLATE_UUID,
    TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID,
}


class WorkflowService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_workflow_library(self) -> dict[str, Any]:
        await self._ensure_builtin_workflow_templates()
        folder_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_workflow.WorkflowFolder).order_by(
                persistence_workflow.WorkflowFolder.created_at.asc()
            )
        )
        workflow_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_workflow.WorkflowProject).order_by(
                persistence_workflow.WorkflowProject.updated_at.desc()
            )
        )
        folders = [folder.name for folder in folder_result.all()]
        workflows = [
            self._serialize_workflow(project)
            for project in workflow_result.all()
        ]
        return {'folders': folders or [DEFAULT_WORKFLOW_FOLDER], 'workflows': workflows}

    async def create_folder(self, name: str) -> None:
        folder_name = self._clean_folder(name)
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_workflow.WorkflowFolder).values(name=folder_name)
            )
        except sqlalchemy.exc.IntegrityError:
            return

    async def create_workflow(self, data: dict[str, Any]) -> str:
        workflow_uuid = str(uuid.uuid4())
        folder = self._clean_folder(data.get('folder'))
        await self._ensure_folder(folder)
        payload = {
            'uuid': workflow_uuid,
            'folder': folder,
            'name': self._clean_text(data.get('name'), '新建工作流'),
            'description': self._clean_text(data.get('description'), ''),
            'workflow': self._clean_workflow(data.get('workflow')),
        }
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_workflow.WorkflowProject).values(**payload)
        )
        return workflow_uuid

    async def update_workflow(self, workflow_uuid: str, data: dict[str, Any]) -> None:
        payload: dict[str, Any] = {}
        if 'folder' in data:
            folder = self._clean_folder(data.get('folder'))
            await self._ensure_folder(folder)
            payload['folder'] = folder
        if 'name' in data:
            payload['name'] = self._clean_text(data.get('name'), '未命名工作流')
        if 'description' in data:
            payload['description'] = self._clean_text(data.get('description'), '')
        if 'workflow' in data:
            payload['workflow'] = self._clean_workflow(data.get('workflow'))
        if not payload:
            return
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.WorkflowProject)
            .where(persistence_workflow.WorkflowProject.uuid == workflow_uuid)
            .values(**payload)
        )

    async def delete_workflow(self, workflow_uuid: str) -> None:
        if workflow_uuid in BUILTIN_WORKFLOW_TEMPLATE_UUIDS:
            raise ValueError('Built-in workflow cannot be deleted')
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_workflow.WorkflowProject).where(
                persistence_workflow.WorkflowProject.uuid == workflow_uuid
            )
        )

    async def _ensure_builtin_workflow_templates(self) -> None:
        existing_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_workflow.WorkflowProject).where(
                persistence_workflow.WorkflowProject.uuid.in_(BUILTIN_WORKFLOW_TEMPLATE_UUIDS)
            )
        )
        existing_uuids = {project.uuid for project in existing_result.all()}
        missing_uuids = BUILTIN_WORKFLOW_TEMPLATE_UUIDS - existing_uuids
        if not missing_uuids:
            return

        template_builder = TaskAssistantService(self.ap)
        course_workflow = template_builder.build_course_sales_workflow_config()
        course_workflow['name'] = '课程销售模板'
        task_workflow = template_builder.build_workflow_config()
        task_workflow['name'] = '任务助手模板配置版'

        await self._ensure_folder(DEFAULT_WORKFLOW_FOLDER)
        for payload in (
            {
                'uuid': COURSE_SALES_WORKFLOW_TEMPLATE_UUID,
                'folder': DEFAULT_WORKFLOW_FOLDER,
                'name': '课程销售模板',
                'description': '承接图书资源咨询、自然拼读课程答疑、报名转化、雷达跟进和人工接管。',
                'workflow': course_workflow,
            },
            {
                'uuid': TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID,
                'folder': DEFAULT_WORKFLOW_FOLDER,
                'name': '任务助手模板配置版',
                'description': '引导用户完成蚂蚁阿福实名认证，保留步骤图片、截图识别和语音回复节点。',
                'workflow': task_workflow,
            },
        ):
            if payload['uuid'] not in missing_uuids:
                continue
            try:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_workflow.WorkflowProject).values(**payload)
                )
            except sqlalchemy.exc.IntegrityError:
                continue

    async def _ensure_folder(self, folder: str) -> None:
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_workflow.WorkflowFolder).values(name=folder)
            )
        except sqlalchemy.exc.IntegrityError:
            return

    def _serialize_workflow(self, project: persistence_workflow.WorkflowProject) -> dict[str, Any]:
        return {
            'uuid': project.uuid,
            'folder': project.folder,
            'name': project.name,
            'description': project.description,
            'workflow': project.workflow,
            'is_builtin': project.uuid in BUILTIN_WORKFLOW_TEMPLATE_UUIDS,
            'created_at': project.created_at.isoformat() if project.created_at else None,
            'updated_at': project.updated_at.isoformat() if project.updated_at else None,
        }

    def _clean_folder(self, value: Any) -> str:
        folder = str(value or '').strip()
        return folder or DEFAULT_WORKFLOW_FOLDER

    def _clean_text(self, value: Any, fallback: str) -> str:
        text = str(value or '').strip()
        return text or fallback

    def _clean_workflow(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {'version': 1, 'nodes': [], 'edges': []}
