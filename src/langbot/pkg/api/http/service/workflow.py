from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy

from ....core import app
from ....entity.persistence import workflow as persistence_workflow
from .task_assistant import TaskAssistantService


DEFAULT_WORKFLOW_FOLDER = '我的项目'
COURSE_SALES_WORKFLOW_TEMPLATE_UUID = 'workflow-template-course-sales'
YUANFUDAO_ENHANCED_WORKFLOW_TEMPLATE_UUID = 'workflow-template-yuanfudao-enhanced-sales'
TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID = 'workflow-template-task-assistant'
YUANFUDAO_TEST_1_WORKFLOW_TEMPLATE_UUID = 'workflow-template-yuanfudao-test-1'
BUILTIN_WORKFLOW_TEMPLATE_UUIDS = {
    COURSE_SALES_WORKFLOW_TEMPLATE_UUID,
    YUANFUDAO_ENHANCED_WORKFLOW_TEMPLATE_UUID,
    TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID,
    YUANFUDAO_TEST_1_WORKFLOW_TEMPLATE_UUID,
}


class WorkflowService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_component_library(self) -> dict[str, Any]:
        return {
            'version': 1,
            'families': [
                {
                    'id': 'inputs',
                    'label': 'Inputs',
                    'components': [
                        self._component(
                            'start',
                            'Chat Input',
                            '接收用户真实文本、图片、语音和上下文。',
                            'MessageSquare',
                            outputs=[{'name': 'message', 'types': ['Message']}],
                            fields=[self._field('trigger', 'Trigger', 'select', 'message', ['message', 'first_contact'])],
                        ),
                        self._component(
                            'channel',
                            'Channel',
                            '统一接入飞书、微信、企微和网页渠道。',
                            'Cable',
                            inputs=[{'name': 'message', 'types': ['Message']}],
                            outputs=[{'name': 'message', 'types': ['Message']}],
                            fields=[
                                self._field('channels', 'Channels', 'tags', ['lark', 'wechat', 'wecom', 'web']),
                                self._field('keep_session', 'Keep session', 'boolean', True),
                            ],
                        ),
                        self._component(
                            'media',
                            'Media Router',
                            '按文本、图片、语音拆分消息流。',
                            'GitBranch',
                            inputs=[{'name': 'message', 'types': ['Message']}],
                            outputs=[
                                {'name': 'text', 'types': ['Text']},
                                {'name': 'image', 'types': ['Image']},
                                {'name': 'voice', 'types': ['Audio']},
                            ],
                            fields=[self._field('routes', 'Routes', 'json', [])],
                        ),
                    ],
                },
                {
                    'id': 'ai',
                    'label': 'AI',
                    'components': [
                        self._component(
                            'asr',
                            'ASR',
                            '把用户语音转写成客服可理解文本。',
                            'Volume2',
                            inputs=[{'name': 'audio', 'types': ['Audio']}],
                            outputs=[{'name': 'text', 'types': ['Text']}],
                            fields=[
                                self._field('provider', 'Provider', 'text', 'volcengine'),
                                self._field('model_uuid', 'Model UUID', 'text', ''),
                                self._field('fallback_text', 'Fallback text', 'textarea', ''),
                            ],
                        ),
                        self._component(
                            'vision',
                            'Vision',
                            '识别二维码、报名页、支付页、资源页和截图问题。',
                            'Eye',
                            inputs=[{'name': 'image', 'types': ['Image']}],
                            outputs=[{'name': 'vision_text', 'types': ['Text']}],
                            fields=[
                                self._field('model_uuid', 'Model UUID', 'text', ''),
                                self._field('target_steps', 'Target steps', 'tags', []),
                            ],
                        ),
                        self._component(
                            'intent',
                            'Intent Classifier',
                            '识别购买、已报名、拒绝、资源问题、转人工等销售意图。',
                            'Brain',
                            inputs=[{'name': 'text', 'types': ['Text']}],
                            outputs=[{'name': 'intent', 'types': ['Intent']}],
                            fields=[
                                self._field('model_uuid', 'Model UUID', 'text', ''),
                                self._field('intents', 'Intents', 'tags', []),
                                self._field('confidence_threshold', 'Confidence', 'number', 0.55),
                            ],
                        ),
                        self._component(
                            'llm',
                            'LLM Reply',
                            '生成真人客服式短句回复。',
                            'Bot',
                            inputs=[{'name': 'context', 'types': ['Text', 'Intent', 'Data']}],
                            outputs=[{'name': 'reply', 'types': ['Message']}],
                            fields=[
                                self._field('model_uuid', 'Model UUID', 'text', ''),
                                self._field('tone', 'Tone', 'text', '真人客服、短句、先服务后转化'),
                                self._field('prompt', 'Prompt', 'textarea', ''),
                            ],
                        ),
                    ],
                },
                {
                    'id': 'logic',
                    'label': 'Logic',
                    'components': [
                        self._component(
                            'condition',
                            'Condition',
                            '按状态和规则分支，支持停发、拒绝和转人工。',
                            'GitBranch',
                            inputs=[{'name': 'intent', 'types': ['Intent', 'Data']}],
                            outputs=[{'name': 'matched', 'types': ['Data']}, {'name': 'fallback', 'types': ['Data']}],
                            fields=[
                                self._field('stop_keywords', 'Stop keywords', 'tags', []),
                                self._field('stop_tags', 'Stop tags', 'tags', []),
                                self._field('message', 'Message', 'textarea', ''),
                            ],
                        ),
                        self._component(
                            'router',
                            'Router',
                            '把不同意图路由到知识库、产品、转人工或回复节点。',
                            'GitBranch',
                            inputs=[{'name': 'intent', 'types': ['Intent']}],
                            outputs=[{'name': 'route', 'types': ['Data']}],
                            fields=[self._field('rules', 'Rules', 'json', [])],
                        ),
                        self._component(
                            'custom',
                            'Parallel / Transform',
                            '通用转换或同时发送多个动作。',
                            'Sparkles',
                            inputs=[{'name': 'input', 'types': ['Data', 'Message']}],
                            outputs=[{'name': 'output', 'types': ['Data', 'Message']}],
                            fields=[
                                self._field('output_key', 'Output key', 'text', ''),
                                self._field('params', 'Params', 'json', {}),
                                self._field('parallel', 'Parallel', 'boolean', False),
                            ],
                        ),
                    ],
                },
                {
                    'id': 'data',
                    'label': 'Data',
                    'components': [
                        self._component(
                            'knowledge',
                            'Knowledge Base',
                            '调用知识库、FAQ 和 SOP 内容。',
                            'BookOpen',
                            inputs=[{'name': 'query', 'types': ['Text']}],
                            outputs=[{'name': 'documents', 'types': ['Data']}],
                            fields=[
                                self._field('knowledge_base_uuids', 'Knowledge bases', 'tags', []),
                                self._field('top_k', 'Top K', 'number', 5),
                                self._field('resource_faqs', 'Resource FAQs', 'json', []),
                                self._field('course_faqs', 'Course FAQs', 'json', []),
                            ],
                        ),
                        self._component(
                            'product',
                            'Product Profile',
                            '输出课程价格、卖点、适龄、赠品和报名方式。',
                            'PackageSearch',
                            inputs=[{'name': 'intent', 'types': ['Intent']}],
                            outputs=[{'name': 'product', 'types': ['Data']}],
                            fields=[
                                self._field('product_uuids', 'Products', 'tags', []),
                                self._field('course_profiles', 'Course profiles', 'json', []),
                            ],
                        ),
                        self._component(
                            'memory',
                            'Memory',
                            '记录客户阶段、标签、年级、点击和报名状态。',
                            'Tags',
                            inputs=[{'name': 'event', 'types': ['Data']}],
                            outputs=[{'name': 'profile', 'types': ['Data']}],
                            fields=[
                                self._field('stage', 'Stage', 'text', 'resource_service'),
                                self._field('tags', 'Tags', 'tags', []),
                            ],
                        ),
                    ],
                },
                {
                    'id': 'sales',
                    'label': 'Sales',
                    'components': [
                        self._component(
                            'radar',
                            'Radar Link',
                            '包装真实报名链接，监听打开和停留事件。',
                            'RadioTower',
                            inputs=[{'name': 'link', 'types': ['Data']}],
                            outputs=[{'name': 'radar_event', 'types': ['Data']}],
                            fields=[
                                self._field('enabled', 'Enabled', 'boolean', True),
                                self._field('link_title', 'Link title', 'text', ''),
                                self._field('link_url', 'Link URL', 'text', ''),
                                self._field('rules', 'Rules', 'json', []),
                            ],
                        ),
                        self._component(
                            'outreach',
                            'Scheduled Push',
                            '按第 X 天、时间、图片和链接进行定时发送。',
                            'Bell',
                            inputs=[{'name': 'target', 'types': ['Data']}],
                            outputs=[{'name': 'scheduled', 'types': ['Data']}],
                            fields=[
                                self._field('scheduled_push', 'Scheduled push', 'json', {}),
                                self._field('followup_sequences', 'Followups', 'json', []),
                                self._field('broadcasts', 'Broadcasts', 'json', []),
                            ],
                        ),
                        self._component(
                            'handoff',
                            'Human Handoff',
                            '客户激动、投诉或说转人工时流转人工接管。',
                            'Handshake',
                            inputs=[{'name': 'intent', 'types': ['Intent']}],
                            outputs=[{'name': 'handoff', 'types': ['Data']}],
                            fields=[
                                self._field('enabled', 'Enabled', 'boolean', True),
                                self._field('keywords', 'Keywords', 'tags', []),
                                self._field('semantic_triggers', 'Semantic triggers', 'json', []),
                                self._field('notify_message', 'Notify message', 'textarea', ''),
                            ],
                        ),
                        self._component(
                            'lead',
                            'Lead Capture',
                            '收集孩子年级、报名状态和联系方式等线索。',
                            'UserRoundCheck',
                            inputs=[{'name': 'message', 'types': ['Message']}],
                            outputs=[{'name': 'lead', 'types': ['Data']}],
                            fields=[
                                self._field('fields', 'Fields', 'tags', []),
                                self._field('required_fields', 'Required fields', 'tags', []),
                            ],
                        ),
                    ],
                },
                {
                    'id': 'outputs',
                    'label': 'Outputs',
                    'components': [
                        self._component(
                            'image',
                            'Image Output',
                            '按意图发送素材图片，可同时配文。',
                            'Image',
                            inputs=[{'name': 'asset', 'types': ['Image', 'Data']}],
                            outputs=[{'name': 'message', 'types': ['Message']}],
                            fields=[
                                self._field('file_key', 'File key', 'text', ''),
                                self._field('image_url', 'Image URL', 'text', ''),
                                self._field('caption', 'Caption', 'textarea', ''),
                                self._field('trigger_intents', 'Trigger intents', 'tags', []),
                            ],
                        ),
                        self._component(
                            'voice',
                            'Voice Output',
                            '按配置追加语音回复。',
                            'Volume2',
                            inputs=[{'name': 'reply', 'types': ['Message']}],
                            outputs=[{'name': 'voice', 'types': ['Audio']}],
                            fields=[
                                self._field('provider', 'Provider', 'text', 'volcengine'),
                                self._field('model_uuid', 'Model UUID', 'text', ''),
                                self._field('voice_type', 'Voice type', 'text', ''),
                            ],
                        ),
                        self._component(
                            'end',
                            'Chat Output',
                            '把文字、图片、链接卡片和语音发送给真实用户。',
                            'Send',
                            inputs=[{'name': 'message', 'types': ['Message']}],
                            outputs=[],
                            fields=[self._field('close_conversation', 'Close conversation', 'boolean', False)],
                        ),
                    ],
                },
            ],
        }

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
        yuanfudao_enhanced_workflow = template_builder.build_course_sales_workflow_config(
            template_config=template_builder.build_course_sales_template_config(template_slug='yuanfudao-enhanced')
        )
        yuanfudao_enhanced_workflow['name'] = '猿辅导销售助手加强版'
        test_1_workflow = template_builder.build_course_sales_workflow_config(
            template_config=template_builder.build_course_sales_template_config(template_slug='yuanfudao-enhanced')
        )
        test_1_workflow['name'] = '测试1号'
        test_1_metadata = test_1_workflow.setdefault('metadata', {})
        test_1_metadata['source_mode'] = 'langflow_components'
        test_1_metadata['template_name'] = '测试1号'
        test_1_metadata['component_schema'] = 'langflow-compatible'
        test_1_workflow.setdefault('variables', {})['flow_name'] = '测试1号'
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
                'uuid': YUANFUDAO_ENHANCED_WORKFLOW_TEMPLATE_UUID,
                'folder': DEFAULT_WORKFLOW_FOLDER,
                'name': '猿辅导销售助手加强版',
                'description': '基于本地模板数据承接自然拼读、阅读+思维、雷达跟进、图片识别和语音回复。',
                'workflow': yuanfudao_enhanced_workflow,
            },
            {
                'uuid': TASK_ASSISTANT_WORKFLOW_TEMPLATE_UUID,
                'folder': DEFAULT_WORKFLOW_FOLDER,
                'name': '任务助手模板配置版',
                'description': '引导用户完成蚂蚁阿福实名认证，保留步骤图片、截图识别和语音回复节点。',
                'workflow': task_workflow,
            },
            {
                'uuid': YUANFUDAO_TEST_1_WORKFLOW_TEMPLATE_UUID,
                'folder': DEFAULT_WORKFLOW_FOLDER,
                'name': '测试1号',
                'description': 'Langflow 风格组件编排的猿辅导销售数字员工，包含知识库、条件、同时发送、定时发送、雷达和转人工。',
                'workflow': test_1_workflow,
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

    def _component(
        self,
        node_type: str,
        display_name: str,
        description: str,
        icon: str,
        *,
        inputs: list[dict[str, Any]] | None = None,
        outputs: list[dict[str, Any]] | None = None,
        fields: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            'type': node_type,
            'display_name': display_name,
            'description': description,
            'icon': icon,
            'inputs': inputs or [],
            'outputs': outputs or [],
            'fields': fields or [],
        }

    def _field(
        self,
        name: str,
        label: str,
        field_type: str,
        default: Any = None,
        options: list[Any] | None = None,
    ) -> dict[str, Any]:
        field = {
            'name': name,
            'label': label,
            'type': field_type,
            'default': default,
            'advanced': field_type == 'json',
        }
        if options is not None:
            field['options'] = options
        return field
