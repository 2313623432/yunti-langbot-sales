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
        library = {
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
        return self._simplify_component_library(library)

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

    def _simplify_component_library(self, library: dict[str, Any]) -> dict[str, Any]:
        family_labels = {
            'inputs': '消息入口',
            'ai': 'AI处理',
            'logic': '条件与流程',
            'data': '资料与记忆',
            'sales': '销售动作',
            'outputs': '发送给客户',
        }
        component_copy = {
            'ai_suggestion': ('人工回复推荐', '人工接管时，点击后由 AI 生成建议回复，客服决定是否采用。', 'Sparkles'),
            'special_case': ('特殊情况处理', '客户问到固定场景时，按语义触发指定回复，可选择固定回复或 AI 换种说法。', 'ListChecks'),
            'resource_capture': ('资源问题收集', '客户说扫码、资源、答案、二维码打不开时，追问问题描述和相关照片，并沉淀到资源问题表。', 'BookOpen'),
            'scheduled_message': ('单条定时消息', '配置第几天、几点、发什么内容，可带图片和链接。', 'Bell'),
            'followup': ('多轮跟进', '客户未回复、打开链接、犹豫或已报名时，自动安排下一轮跟进。', 'ListChecks'),
            'resume_ai': ('恢复AI托管', '人工处理结束后，一键恢复 AI 自动回复和自动跟进。', 'Bot'),
            'link_card': ('链接卡片', '发送报名、资源、扫码记录等链接卡片，可接入雷达跟踪。', 'RadioTower'),
            'meme': ('发送表情包', '按客户情绪或对话节点发送礼貌、可爱的飞书表情或大表情包。', 'Image'),
        }

        extra_by_family = {
            'ai': [
                self._component(
                    'ai_suggestion',
                    *component_copy['ai_suggestion'],
                    inputs=[{'name': 'conversation', 'types': ['Message', 'Data']}],
                    outputs=[{'name': 'suggestion', 'types': ['Message']}],
                    fields=[
                        self._field('enabled', '启用推荐回复', 'boolean', True),
                        self._field('style', '推荐风格', 'select', '自然客服', ['自然客服', '专业顾问', '简短确认']),
                        self._field('prompt', '推荐回复要求', 'textarea', '结合完整聊天历史，给人工客服一条可直接发送的短回复。'),
                    ],
                ),
            ],
            'logic': [
                self._component(
                    'special_case',
                    *component_copy['special_case'],
                    inputs=[{'name': 'message', 'types': ['Message']}],
                    outputs=[{'name': 'reply', 'types': ['Message']}],
                    fields=[
                        self._field('condition', '如果客户表达类似意思', 'textarea', '例如：问怎么听、资源在哪里、答案怎么看'),
                        self._field('reply', 'AI回复类似意思', 'textarea', '书籍二维码听力/答案，点击上面推送的“点击访问扫码前的资源”卡片。'),
                        self._field('ai_rewrite', '打开后让AI每次换种说法', 'boolean', True),
                        self._field('image_url', '可选图片链接', 'text', ''),
                    ],
                ),
            ],
            'data': [
                self._component(
                    'resource_capture',
                    *component_copy['resource_capture'],
                    inputs=[{'name': 'message', 'types': ['Message']}],
                    outputs=[{'name': 'resource_issue', 'types': ['Data']}],
                    fields=[
                        self._field('enabled', '启用资源问题收集', 'boolean', True),
                        self._field('trigger_keywords', '哪些表达算资源问题', 'tags', ['二维码打不开', '听力在哪里', '答案在哪里', '扫码失败', '资源打不开']),
                        self._field('required_image_count', '最少需要几张照片', 'number', 2),
                        self._field('max_followup_rounds', '最多追问几次', 'number', 3),
                        self._field('ask_message', '第一次追问话术', 'textarea', '您具体是哪个资源打不开呀？可以描述一下问题，再拍一下出问题的二维码和页面截图发我。'),
                        self._field('completed_message', '收集完成后回复', 'textarea', '收到，我已经帮您记录了，会尽快帮您处理。'),
                    ],
                ),
            ],
            'sales': [
                self._component(
                    'scheduled_message',
                    *component_copy['scheduled_message'],
                    inputs=[{'name': 'target', 'types': ['Data']}],
                    outputs=[{'name': 'scheduled', 'types': ['Data']}],
                    fields=[
                        self._field('day', '第几天发送', 'number', 1),
                        self._field('time', '发送时间', 'text', '10:20'),
                        self._field('message', '发送内容', 'textarea', ''),
                        self._field('image_url', '图片链接（可选）', 'text', ''),
                        self._field('link_title', '链接标题（可选）', 'text', ''),
                        self._field('link_url', '链接地址（可选）', 'text', ''),
                    ],
                ),
                self._component(
                    'followup',
                    *component_copy['followup'],
                    inputs=[{'name': 'profile', 'types': ['Data']}],
                    outputs=[{'name': 'followup_plan', 'types': ['Data']}],
                    fields=[
                        self._field('stage', '适用客户阶段', 'select', '未报名', ['未报名', '已领资料', '已打开链接', '已报名', '拒绝/停发']),
                        self._field('delay_minutes', '多久后跟进（分钟）', 'number', 1440),
                        self._field('message', '跟进内容', 'textarea', ''),
                        self._field('stop_when_replied', '客户回复后停止这轮跟进', 'boolean', True),
                    ],
                ),
                self._component(
                    'resume_ai',
                    *component_copy['resume_ai'],
                    inputs=[{'name': 'handoff', 'types': ['Data']}],
                    outputs=[{'name': 'message', 'types': ['Message']}],
                    fields=[
                        self._field('enabled', '允许恢复AI托管', 'boolean', True),
                        self._field('resume_message', '恢复后提示语', 'textarea', '好的，后面我会继续帮您跟进。'),
                    ],
                ),
                self._component(
                    'link_card',
                    *component_copy['link_card'],
                    inputs=[{'name': 'message', 'types': ['Message']}],
                    outputs=[{'name': 'link_card', 'types': ['Message']}],
                    fields=[
                        self._field('title', '卡片标题', 'text', '点击访问扫码前的资源'),
                        self._field('url', '链接地址', 'text', ''),
                        self._field('description', '卡片说明', 'textarea', ''),
                        self._field('radar_enabled', '启用雷达跟踪', 'boolean', True),
                    ],
                ),
            ],
            'outputs': [
                self._component(
                    'meme',
                    *component_copy['meme'],
                    inputs=[{'name': 'reply', 'types': ['Message']}],
                    outputs=[{'name': 'message', 'types': ['Message']}],
                    fields=[
                        self._field('enabled', '启用表情包', 'boolean', True),
                        self._field('emotion', '适合的情绪/场景', 'select', '开心鼓励', ['开心鼓励', '感谢', '收到', '加油', '早上好', '疑问解释', '抱歉安抚']),
                        self._field('small_enabled', '允许飞书小表情', 'boolean', True),
                        self._field('large_enabled', '允许大表情包', 'boolean', True),
                        self._field('min_rounds', '几轮内至少出现一次', 'number', 3),
                    ],
                ),
            ],
        }

        for family in library.get('families', []):
            family_id = family.get('id')
            family['label'] = family_labels.get(family_id, family.get('label', '组件'))
            family.setdefault('components', []).extend(extra_by_family.get(family_id, []))
            for component in family.get('components', []):
                component.update(self._component_copy(component.get('type', '')))
                for field in component.get('fields', []):
                    self._simplify_component_field(field)
        return library

    def _component_copy(self, node_type: str) -> dict[str, Any]:
        copy = {
            'start': ('用户消息入口', '收到客户真实消息后开始执行，支持文字、图片、语音和上下文。'),
            'channel': ('渠道接入', '统一接入飞书、微信、企微和网页渠道，保持同一个客户会话。'),
            'media': ('消息类型判断', '自动判断客户发来的是文字、图片、语音还是文件，并送到对应处理组件。'),
            'asr': ('语音转文字', '把客户语音转成客服可理解的文字，失败时可使用兜底提示。'),
            'vision': ('图片/截图识别', '识别二维码、报名页、支付页、资源页和截图里的问题。'),
            'intent': ('客户意图识别', '识别购买、已报名、拒绝、资源问题、转人工等销售意图。'),
            'llm': ('AI客服回复', '生成像真人客服一样的短句回复，回答问题并自然推进下一步。'),
            'condition': ('条件判断', '按客户状态和规则分支，支持停发、拒绝、转人工和素材触发。'),
            'router': ('分流路由', '把不同意图送到知识库、课程资料、人工介入或回复节点。'),
            'custom': ('同时执行', '同时发送多种动作，例如回复文字、记录客户标签、安排后续跟进。'),
            'knowledge': ('知识库问答', '调用知识库、FAQ 和 SOP 内容回答客户问题。'),
            'product': ('课程产品信息', '输出课程价格、卖点、适龄、赠品和报名方式。'),
            'memory': ('客户记忆', '记录客户阶段、标签、年级、点击和报名状态。'),
            'radar': ('雷达链接', '包装真实报名链接，监听打开、停留和点击行为。'),
            'outreach': ('定时发送计划', '按第 X 天、推送时间、文字、图片和链接进行定时发送。'),
            'handoff': ('转人工', '客户情绪激动、投诉或说转人工时，流转到待人工介入。'),
            'lead': ('线索收集', '收集孩子年级、报名状态、手机号、购买意向等线索。'),
            'image': ('发送图片', '按客户意图发送素材图片，也可以同时配一段文字。'),
            'voice': ('发送语音', '按配置追加语音回复，适合需要真人感的售前沟通。'),
            'end': ('回复客户', '把文字、图片、链接卡片、表情包和语音发送给真实客户。'),
        }
        if node_type not in copy:
            return {}
        display_name, description = copy[node_type]
        return {'display_name': display_name, 'description': description}

    def _simplify_component_field(self, field: dict[str, Any]) -> None:
        label_map = {
            'Trigger': '触发方式',
            'Channels': '启用渠道',
            'Keep session': '同一客户保持同一会话',
            'Routes': '内部分流规则',
            'Provider': '服务类型',
            'Model UUID': '指定模型',
            'Fallback text': '识别失败时怎么回复',
            'Target steps': '重点识别内容',
            'Intents': '需要识别的意图',
            'Confidence': '识别严格程度',
            'Tone': '回复风格',
            'Prompt': '回复要求',
            'Stop keywords': '客户说这些就停止自动跟进',
            'Stop tags': '命中这些客户标签就停止',
            'Message': '命中后回复',
            'Rules': '高级规则',
            'Output key': '内部输出名称',
            'Params': '高级动作参数',
            'Parallel': '同时执行后续动作',
            'Knowledge bases': '选择知识库',
            'Top K': '最多参考几条资料',
            'Resource FAQs': '资源问题FAQ',
            'Course FAQs': '课程FAQ',
            'Products': '选择课程/产品',
            'Course profiles': '课程详细资料',
            'Stage': '默认客户阶段',
            'Tags': '自动添加标签',
            'Enabled': '启用',
            'Link title': '链接标题',
            'Link URL': '真实链接',
            'Scheduled push': '定时发送内容',
            'Followups': '跟进序列',
            'Broadcasts': '群发计划',
            'Keywords': '明显触发词',
            'Semantic triggers': '语义触发规则',
            'Notify message': '进入人工前回复',
            'Fields': '需要收集的信息',
            'Required fields': '必须收集的信息',
            'File key': '内部图片文件',
            'Image URL': '图片链接',
            'Caption': '图片配文',
            'Trigger intents': '什么情况下发送',
            'Voice type': '声音类型',
            'Close conversation': '回复后关闭会话',
        }
        field['label'] = label_map.get(field.get('label'), field.get('label'))
        if field.get('name') in {
            'provider',
            'model_uuid',
            'routes',
            'rules',
            'output_key',
            'params',
            'resource_faqs',
            'course_faqs',
            'course_profiles',
            'scheduled_push',
            'followup_sequences',
            'broadcasts',
            'semantic_triggers',
            'file_key',
        }:
            field['advanced'] = True
        if field.get('name') == 'trigger':
            field['default'] = '收到消息'
            field['options'] = ['收到消息', '首次开口']

    def _field(
        self,
        name: str,
        label: str,
        field_type: str,
        default: Any = None,
        options: list[Any] | None = None,
        advanced: bool | None = None,
    ) -> dict[str, Any]:
        field = {
            'name': name,
            'label': label,
            'type': field_type,
            'default': default,
            'advanced': field_type == 'json' if advanced is None else advanced,
        }
        if options is not None:
            field['options'] = options
        return field
