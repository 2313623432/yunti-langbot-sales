from __future__ import annotations

import copy
import json
import re
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
BUILTIN_WORKFLOW_TEMPLATE_UUIDS = {
    COURSE_SALES_WORKFLOW_TEMPLATE_UUID,
    YUANFUDAO_ENHANCED_WORKFLOW_TEMPLATE_UUID,
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

    async def generate_workflow_draft(self, data: dict[str, Any]) -> dict[str, Any]:
        instruction = self._clean_text(
            data.get('instruction'),
            '客户咨询课程时先识别意图，再补齐孩子年级、学科需求、预算、联系方式和购买时间；高意向或支付异常转人工，未成交24小时后跟进。',
        )
        scenario = str(data.get('scenario') or 'yuanfudao_sales').strip()
        if scenario not in {'yuanfudao_sales', 'sales'}:
            scenario = 'yuanfudao_sales'

        fallback_rules = self._fallback_workflow_rules(instruction, scenario)
        llm_result = await self._generate_llm_workflow_rules(
            instruction,
            scenario,
            model_uuid=str(data.get('model_uuid') or '').strip(),
        )
        rules_payload = self._normalize_generated_rules(llm_result or fallback_rules, fallback_rules)
        workflow = self._build_generated_workflow(rules_payload, scenario)
        return {
            'draft': {
                'title': rules_payload['title'],
                'summary': rules_payload['summary'],
                'rules': rules_payload['rules'],
                'qualification_fields': rules_payload['qualification_fields'],
                'handoff_rules': rules_payload['handoff_rules'],
                'workflow': workflow,
            },
            'used_llm': llm_result is not None,
            'model_uuid': rules_payload.get('model_uuid', ''),
            'model_name': rules_payload.get('model_name', ''),
            'fallback_reason': '' if llm_result is not None else '未找到可用模型或模型生成失败，已使用规则编译兜底。',
        }

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

    async def _generate_llm_workflow_rules(
        self,
        instruction: str,
        scenario: str,
        model_uuid: str = '',
    ) -> dict[str, Any] | None:
        selected_model_uuid = model_uuid or self._preferred_workflow_generation_model_uuid()
        if not selected_model_uuid:
            return None
        try:
            from langbot_plugin.api.entities.builtin.provider import message as provider_message

            runtime_model = await self.ap.model_mgr.get_model_by_uuid(selected_model_uuid)
            model_entity = getattr(runtime_model, 'model_entity', None)
            model_name = str(getattr(model_entity, 'name', '') or selected_model_uuid)
            response = await runtime_model.provider.invoke_llm(
                query=None,
                model=runtime_model,
                messages=[
                    provider_message.Message(
                        role='system',
                        content=(
                            '你是低代码销售工作流架构师。把自然语言销售规则编译成可审查的业务路径，'
                            '不要只写Prompt。只返回JSON，不要Markdown。'
                        ),
                    ),
                    provider_message.Message(
                        role='user',
                        content=self._build_workflow_generation_prompt(instruction, scenario),
                    ),
                ],
                funcs=[],
                extra_args=copy.deepcopy(getattr(model_entity, 'extra_args', {}) or {}),
                remove_think=True,
            )
            text = self._provider_message_content_to_text(getattr(response, 'content', response)).strip()
            parsed = self._extract_json_object(text)
            if parsed is None:
                return None
            parsed['model_uuid'] = selected_model_uuid
            parsed['model_name'] = model_name
            return parsed
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning(f'[Workflow] LLM workflow draft generation failed, falling back to rules: {exc}')
            return None

    def _build_workflow_generation_prompt(self, instruction: str, scenario: str) -> str:
        scenario_hint = (
            '猿辅导销售助手加强版：必须保留图书资源服务、猿辅导自然拼读/阅读思维课程、9元体验课、'
            '雷达链接跟进、资源问题工单、语音/截图处理、停发规则和人工接管。'
            if scenario == 'yuanfudao_sales'
            else '通用AI销售智能体：面向产品咨询、询价、异议处理、线索资格判断、CRM动作和人工交接。'
        )
        payload = {
            'scenario': scenario,
            'scenario_hint': scenario_hint,
            'user_instruction': instruction,
            'required_output_schema': {
                'title': 'string, 12字以内',
                'summary': 'string, 一句话说明这条流程推进什么业务结果',
                'rules': [
                    {
                        'when': '客户表达或业务条件',
                        'intent': '短英文或中文意图名',
                        'action': 'AI节点或业务动作',
                        'handoff': 'boolean, 是否应转人工',
                    }
                ],
                'qualification_fields': ['销售推进必须补齐的字段'],
                'handoff_rules': ['需要人工接管的条件'],
            },
            'constraints': [
                '必须体现：触发条件 -> AI识别意图 -> 提问补充信息 -> 条件分支 -> 执行动作 -> 转人工或沉淀线索。',
                '销售场景关注推进购买决策，必须输出客户阶段、意向等级、已知需求、缺失信息或下一步相关字段。',
                '不要编造不存在的价格、优惠、链接或承诺。',
                'rules最多8条，qualification_fields最多8个，handoff_rules最多6条。',
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    def _fallback_workflow_rules(self, instruction: str, scenario: str) -> dict[str, Any]:
        if scenario == 'yuanfudao_sales':
            return {
                'title': '猿辅导销售流程',
                'summary': '围绕图书资源服务承接课程咨询，识别意向、补齐家长信息，并把高风险或高意向线索交给人工销售。',
                'rules': [
                    {
                        'when': '家长咨询图书资源、答案、音频或扫码入口',
                        'intent': 'resource_help',
                        'action': '先服务资源问题，发送资源卡片或收集缺失资源信息',
                        'handoff': False,
                    },
                    {
                        'when': '家长询问自然拼读、阅读思维、上课时间或回放',
                        'intent': 'course_intro',
                        'action': '结合课程FAQ和产品库回答，再追问孩子年级与学习需求',
                        'handoff': False,
                    },
                    {
                        'when': '家长询价、问怎么买、点击报名链接或表达近期报名',
                        'intent': 'purchase',
                        'action': '推荐匹配课程，发送报名链接并创建雷达跟进',
                        'handoff': False,
                    },
                    {
                        'when': '家长已支付、支付异常、投诉、退款或要求真人',
                        'intent': 'handoff',
                        'action': '停止AI促单和群发，带摘要转交人工销售',
                        'handoff': True,
                    },
                    {
                        'when': '家长拒绝、无孩子、辱骂或明确不再联系',
                        'intent': 'stop',
                        'action': '触发停发规则，沉淀原因并停止后续触达',
                        'handoff': False,
                    },
                ],
                'qualification_fields': ['孩子年级', '关注学科', '学习痛点', '课程兴趣', '报名意向', '联系方式', '支付状态', '最近互动'],
                'handoff_rules': ['支付或订单异常', '投诉/强烈负面情绪', '明确要求人工/班主任/电话', 'AI无法判断截图或资源问题', '高意向客户需要销售推进'],
                'source_instruction': instruction,
            }
        return {
            'title': 'AI销售流程',
            'summary': '把开放式客户对话转成意图识别、资格判断、产品推荐、业务动作和人工接管的销售推进流程。',
            'rules': [
                {
                    'when': '客户首次咨询产品、价格、方案或试用',
                    'intent': 'product_interest',
                    'action': '识别需求并匹配产品知识',
                    'handoff': False,
                },
                {
                    'when': '关键信息缺失',
                    'intent': 'qualification',
                    'action': '一次只追问最关键字段',
                    'handoff': False,
                },
                {
                    'when': '客户有预算、时间、采购人或明确购买信号',
                    'intent': 'high_intent',
                    'action': '写入CRM字段并推荐销售下一步',
                    'handoff': True,
                },
                {
                    'when': '客户要求合同、报价单、电话、定制方案或人工',
                    'intent': 'handoff',
                    'action': '汇总上下文并转人工',
                    'handoff': True,
                },
            ],
            'qualification_fields': ['客户阶段', '意向等级', '已知需求', '缺失信息', '预算', '购买时间', '联系方式'],
            'handoff_rules': ['明确要求人工', '报价/合同/定制方案', '高意向购买信号', 'AI置信度不足'],
            'source_instruction': instruction,
        }

    def _normalize_generated_rules(self, value: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        source = value if isinstance(value, dict) else {}
        rules = source.get('rules') if isinstance(source.get('rules'), list) else fallback['rules']
        normalized_rules = []
        for rule in rules[:8]:
            if not isinstance(rule, dict):
                continue
            normalized_rules.append(
                {
                    'when': self._clean_text(rule.get('when'), '客户表达明确业务诉求'),
                    'intent': self._clean_text(rule.get('intent'), 'general'),
                    'action': self._clean_text(rule.get('action'), '识别意图并推进下一步'),
                    'handoff': bool(rule.get('handoff')),
                }
            )
        if not normalized_rules:
            normalized_rules = fallback['rules']

        return {
            'title': self._clean_text(source.get('title'), fallback['title'])[:32],
            'summary': self._clean_text(source.get('summary'), fallback['summary'])[:240],
            'rules': normalized_rules,
            'qualification_fields': self._clean_string_list(
                source.get('qualification_fields'),
                fallback['qualification_fields'],
                limit=8,
            ),
            'handoff_rules': self._clean_string_list(source.get('handoff_rules'), fallback['handoff_rules'], limit=6),
            'model_uuid': str(source.get('model_uuid') or ''),
            'model_name': str(source.get('model_name') or ''),
        }

    def _build_generated_workflow(self, rules_payload: dict[str, Any], scenario: str) -> dict[str, Any]:
        if scenario == 'yuanfudao_sales':
            template_builder = TaskAssistantService(self.ap)
            template_config = template_builder.build_course_sales_template_config(
                overrides={'name': rules_payload['title'] or '猿辅导销售助手加强版'},
                template_slug='yuanfudao-enhanced',
            )
            workflow = template_builder.build_course_sales_workflow_config(template_config=template_config)
            workflow['name'] = rules_payload['title'] or '猿辅导销售助手加强版'
        else:
            workflow = self._build_generic_sales_workflow(rules_payload)

        metadata = workflow.setdefault('metadata', {})
        metadata.update(
            {
                'source_mode': 'ai_first_workflow_draft',
                'ai_first_summary': rules_payload['summary'],
                'ai_generated_rules': rules_payload['rules'],
                'qualification_fields': rules_payload['qualification_fields'],
                'handoff_rules': rules_payload['handoff_rules'],
            }
        )
        variables = workflow.setdefault('variables', {})
        variables.update(
            {
                'ai_first_summary': rules_payload['summary'],
                'ai_generated_rules': rules_payload['rules'],
                'qualification_fields': rules_payload['qualification_fields'],
                'handoff_rules': rules_payload['handoff_rules'],
            }
        )
        self._apply_generated_rules_to_nodes(workflow, rules_payload)
        return workflow

    def _build_generic_sales_workflow(self, rules_payload: dict[str, Any]) -> dict[str, Any]:
        nodes = [
            self._workflow_node('start', 'start', '客户进线', '网页、微信、企微或人工标记触发销售接待', 80, 220, {'trigger': 'message'}),
            self._workflow_node(
                'intent',
                'intent',
                'AI识别意图',
                '理解客户开放式表达，而不是只按关键词匹配',
                360,
                220,
                {'intents': [rule['intent'] for rule in rules_payload['rules']], 'confidence_threshold': 0.68},
            ),
            self._workflow_node(
                'lead',
                'lead',
                '资格判断问题',
                '补齐客户阶段、意向等级、需求和缺失信息',
                640,
                220,
                {'fields': rules_payload['qualification_fields'], 'required_fields': rules_payload['qualification_fields'][:3]},
            ),
            self._workflow_node(
                'condition',
                'condition',
                '条件分支',
                '按意向等级、缺失字段、产品匹配度和转人工规则分流',
                920,
                220,
                {'rules': [f"{rule['when']} -> {rule['action']}" for rule in rules_payload['rules']]},
            ),
            self._workflow_node(
                'product',
                'product',
                '产品知识与推荐',
                '根据客户需求推荐产品、内容或下一步动作',
                1200,
                90,
                {'match_by': 'selling_points', 'product_uuids': []},
            ),
            self._workflow_node(
                'memory',
                'memory',
                '沉淀线索',
                '记录客户画像、关键问答、阶段和推荐下一步',
                1200,
                220,
                {'stage': 'consideration', 'fields': rules_payload['qualification_fields']},
            ),
            self._workflow_node(
                'handoff',
                'handoff',
                '人工接管',
                '把摘要、画像、关键问答和推荐话术交给销售',
                1200,
                350,
                {'rules': rules_payload['handoff_rules'], 'reason': '满足销售接管规则'},
            ),
            self._workflow_node(
                'outreach',
                'outreach',
                '持续触达',
                '客户未成交时安排下一次触达',
                1480,
                220,
                {'delay_minutes': 1440, 'message_template': '您好，给您同步一下上次关注的产品资料。'},
            ),
            self._workflow_node('end', 'end', '回复客户', '发送回复、素材或交接通知', 1760, 220, {'close_conversation': False}),
        ]
        edges = [
            self._workflow_edge('e-start-intent', 'start', 'intent'),
            self._workflow_edge('e-intent-lead', 'intent', 'lead'),
            self._workflow_edge('e-lead-condition', 'lead', 'condition'),
            self._workflow_edge('e-condition-product', 'condition', 'product', '推荐产品'),
            self._workflow_edge('e-condition-memory', 'condition', 'memory', '沉淀线索'),
            self._workflow_edge('e-condition-handoff', 'condition', 'handoff', '转人工'),
            self._workflow_edge('e-product-memory', 'product', 'memory'),
            self._workflow_edge('e-memory-outreach', 'memory', 'outreach'),
            self._workflow_edge('e-handoff-end', 'handoff', 'end'),
            self._workflow_edge('e-outreach-end', 'outreach', 'end'),
        ]
        return {
            'version': 1,
            'name': rules_payload['title'] or 'AI销售流程',
            'scenario': 'sales',
            'nodes': nodes,
            'edges': edges,
            'variables': {
                'customer_stage': 'new',
                'intent': '',
                'lead_score': 0,
            },
        }

    def _apply_generated_rules_to_nodes(self, workflow: dict[str, Any], rules_payload: dict[str, Any]) -> None:
        rules = rules_payload['rules']
        intents = [rule['intent'] for rule in rules if rule.get('intent')]
        handoff_rules = rules_payload['handoff_rules']
        for node in workflow.get('nodes', []):
            if not isinstance(node, dict):
                continue
            config = node.setdefault('config', {})
            if node.get('type') == 'intent':
                config['ai_first_intents'] = intents
                config['ai_first_rules'] = rules
            elif node.get('type') == 'lead':
                config['fields'] = rules_payload['qualification_fields']
                config['required_fields'] = rules_payload['qualification_fields'][:3]
            elif node.get('type') == 'condition':
                config['ai_first_rules'] = rules
                config['handoff_rules'] = handoff_rules
            elif node.get('type') == 'handoff':
                config['ai_first_handoff_rules'] = handoff_rules
                config['context_summary_required'] = True
            elif node.get('type') == 'llm':
                config['ai_first_summary'] = rules_payload['summary']
                config['sales_progression_rules'] = rules

    def _workflow_node(
        self,
        node_id: str,
        node_type: str,
        title: str,
        description: str,
        x: int,
        y: int,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            'id': node_id,
            'type': node_type,
            'title': title,
            'description': description,
            'position': {'x': x, 'y': y},
            'config': config,
        }

    def _workflow_edge(self, edge_id: str, source: str, target: str, label: str | None = None) -> dict[str, Any]:
        edge = {'id': edge_id, 'source': source, 'target': target}
        if label:
            edge['label'] = label
        return edge

    def _preferred_workflow_generation_model_uuid(self) -> str:
        model_mgr = getattr(self.ap, 'model_mgr', None)
        for runtime_model in getattr(model_mgr, 'llm_models', []) or []:
            provider = getattr(runtime_model, 'provider', None)
            provider_entity = getattr(provider, 'provider_entity', None)
            requester = str(getattr(provider_entity, 'requester', '') or '')
            provider_uuid = str(getattr(provider_entity, 'uuid', '') or '')
            if requester == 'space-chat-completions' or provider_uuid == '00000000-0000-0000-0000-000000000000':
                continue
            if not self._provider_has_api_key(getattr(provider_entity, 'api_keys', None)):
                continue
            model_entity = getattr(runtime_model, 'model_entity', None)
            model_uuid = str(getattr(model_entity, 'uuid', '') or '').strip()
            if model_uuid:
                return model_uuid
        return ''

    def _provider_has_api_key(self, api_keys: Any) -> bool:
        if isinstance(api_keys, list):
            return any(str(key or '').strip() for key in api_keys)
        if isinstance(api_keys, str):
            text = api_keys.strip()
            if not text:
                return False
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return any(str(key or '').strip() for key in parsed)
            except json.JSONDecodeError:
                return bool(text)
            return bool(text)
        return False

    def _provider_message_content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                text = getattr(item, 'text', None)
                if text is None and isinstance(item, dict):
                    text = item.get('text')
                if text:
                    parts.append(str(text))
            return '\n'.join(parts)
        return str(content or '')

    def _extract_json_object(self, text: str) -> dict[str, Any] | None:
        if not text:
            return None
        candidates = [text]
        match = re.search(r'\{.*\}', text, re.S)
        if match:
            candidates.append(match.group(0))
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _clean_string_list(self, value: Any, fallback: list[str], limit: int) -> list[str]:
        if isinstance(value, list):
            items = [str(item or '').strip() for item in value]
        elif isinstance(value, str):
            items = [item.strip() for item in re.split(r'[,，\n;；]', value)]
        else:
            items = fallback
        cleaned = []
        for item in items:
            if item and item not in cleaned:
                cleaned.append(item[:40])
            if len(cleaned) >= limit:
                break
        return cleaned or fallback[:limit]
