from __future__ import annotations

import copy
import datetime
import uuid
from typing import Any

import sqlalchemy

from ....core import app
from ....entity.persistence import autotest as persistence_autotest


class AutoTestService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_targets(self) -> dict[str, list[dict[str, Any]]]:
        pipelines = []
        workflows = []

        if getattr(self.ap, 'pipeline_service', None) is not None:
            pipelines = [
                {
                    'type': 'pipeline',
                    'uuid': item.get('uuid'),
                    'name': item.get('name') or item.get('uuid'),
                    'description': item.get('description') or '',
                    'is_builtin': bool(item.get('is_builtin')),
                }
                for item in await self.ap.pipeline_service.get_pipelines()
            ]

        if getattr(self.ap, 'workflow_service', None) is not None:
            library = await self.ap.workflow_service.get_workflow_library()
            workflows = [
                {
                    'type': 'workflow',
                    'uuid': item.get('uuid'),
                    'name': item.get('name') or item.get('uuid'),
                    'description': item.get('description') or '',
                    'folder': item.get('folder') or '',
                    'is_builtin': bool(item.get('is_builtin')),
                }
                for item in library.get('workflows', [])
            ]

        return {'pipelines': pipelines, 'workflows': workflows}

    async def list_runs(
        self,
        target_type: str | None = None,
        target_uuid: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 20), 100))
        query = sqlalchemy.select(persistence_autotest.AutoTestRun).order_by(
            persistence_autotest.AutoTestRun.created_at.desc()
        )
        if target_type:
            query = query.where(persistence_autotest.AutoTestRun.target_type == target_type)
        if target_uuid:
            query = query.where(persistence_autotest.AutoTestRun.target_uuid == target_uuid)
        query = query.limit(limit)

        result = await self.ap.persistence_mgr.execute_async(query)
        return [self._serialize_run(row) for row in result.all()]

    async def get_run(self, run_uuid: str) -> dict[str, Any] | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_autotest.AutoTestRun).where(
                persistence_autotest.AutoTestRun.uuid == run_uuid
            )
        )
        row = result.first()
        return self._serialize_run(row) if row is not None else None

    async def start_run(self, data: dict[str, Any]) -> dict[str, Any]:
        target_type = str(data.get('target_type') or '').strip()
        target_uuid = str(data.get('target_uuid') or '').strip()
        if target_type not in {'pipeline', 'workflow'}:
            raise ValueError('target_type must be pipeline or workflow')
        if not target_uuid:
            raise ValueError('target_uuid is required')

        target = await self._get_target(target_type, target_uuid)
        target_name = target.get('name') or target_uuid
        scenario = str(data.get('scenario') or '').strip() or self._default_scenario(target_type, target)
        turns = max(1, min(int(data.get('turns') or 3), 6))
        messages = self._simulate_conversation(target_type, target, scenario, turns)
        evaluation = self._evaluate_conversation(messages)

        run_uuid = str(uuid.uuid4())
        payload = {
            'uuid': run_uuid,
            'target_type': target_type,
            'target_uuid': target_uuid,
            'target_name': target_name,
            'status': 'completed',
            'scenario': scenario,
            'messages': messages,
            'evaluation': evaluation,
            'user_feedback': '',
            'feedback_reason': '',
            'optimization_summary': '',
            'optimization_patch': {},
        }
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_autotest.AutoTestRun).values(**payload)
        )
        return await self.get_run(run_uuid) or payload

    async def submit_feedback(self, run_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        feedback = str(data.get('feedback') or '').strip()
        reason = str(data.get('reason') or '').strip()
        if feedback not in {'satisfied', 'unsatisfied'}:
            raise ValueError('feedback must be satisfied or unsatisfied')
        if feedback == 'unsatisfied' and not reason:
            raise ValueError('reason is required when feedback is unsatisfied')

        run = await self.get_run(run_uuid)
        if run is None:
            raise ValueError('auto test run not found')

        optimization_summary = ''
        optimization_patch: dict[str, Any] = {}
        if feedback == 'unsatisfied':
            optimization_summary = self._build_optimization_summary(run, reason)
            optimization_patch = await self._apply_optimization_note(run, optimization_summary)

        values = {
            'status': 'reviewed',
            'user_feedback': feedback,
            'feedback_reason': reason,
            'optimization_summary': optimization_summary,
            'optimization_patch': optimization_patch,
            'updated_at': sqlalchemy.func.now(),
        }
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_autotest.AutoTestRun)
            .where(persistence_autotest.AutoTestRun.uuid == run_uuid)
            .values(**values)
        )
        updated_run = copy.deepcopy(run)
        updated_run.update(values)
        updated_run['updated_at'] = datetime.datetime.now().isoformat()
        return updated_run

    async def _get_target(self, target_type: str, target_uuid: str) -> dict[str, Any]:
        if target_type == 'pipeline':
            target = await self.ap.pipeline_service.get_pipeline(target_uuid)
            if target is None:
                raise ValueError('pipeline not found')
            return target

        library = await self.ap.workflow_service.get_workflow_library()
        for item in library.get('workflows', []):
            if item.get('uuid') == target_uuid:
                return item
        raise ValueError('workflow not found')

    def _default_scenario(self, target_type: str, target: dict[str, Any]) -> str:
        name = target.get('name') or ('数字员工' if target_type == 'pipeline' else '工作流')
        if target_type == 'workflow':
            return f'客户第一次咨询「{name}」，先询问服务内容，再提出价格/流程顾虑，最后观察客服是否给出下一步。'
        return f'客户第一次咨询「{name}」，先问能解决什么问题，再提出异议并要求更具体的下一步。'

    def _simulate_conversation(
        self,
        target_type: str,
        target: dict[str, Any],
        scenario: str,
        turns: int,
    ) -> list[dict[str, Any]]:
        profile = self._extract_target_profile(target_type, target)
        customer_turns = self._customer_turns(profile, scenario)[:turns]
        messages: list[dict[str, Any]] = []
        for index, customer_text in enumerate(customer_turns, start=1):
            messages.append(
                {
                    'role': 'user',
                    'sender': '模拟客户',
                    'content_type': 'text',
                    'content': customer_text,
                    'turn': index,
                }
            )
            messages.append(
                {
                    'role': 'assistant',
                    'sender': profile['agent_name'],
                    'content_type': 'text',
                    'content': self._assistant_reply(profile, customer_text, index),
                    'turn': index,
                }
            )
        return messages

    def _extract_target_profile(self, target_type: str, target: dict[str, Any]) -> dict[str, Any]:
        if target_type == 'workflow':
            workflow = target.get('workflow') if isinstance(target.get('workflow'), dict) else {}
            nodes = workflow.get('nodes') if isinstance(workflow.get('nodes'), list) else []
            node_names = [
                str(node.get('data', {}).get('title') or node.get('name') or node.get('id') or '').strip()
                for node in nodes
                if isinstance(node, dict)
            ]
            node_names = [name for name in node_names if name][:8]
            return {
                'agent_name': target.get('name') or '工作流客服',
                'role_prompt': target.get('description') or '按照工作流节点回答客户问题。',
                'opening': f'您好，我是{target.get("name") or "工作流客服"}，我会按流程帮您处理。',
                'selling_points': node_names or ['按节点识别客户意图', '给出下一步动作', '必要时转人工'],
                'objections': ['价格顾虑', '流程太复杂', '想转人工'],
                'next_action': '给出明确下一步并记录需要优化的节点',
            }

        config = target.get('config') if isinstance(target.get('config'), dict) else {}
        template = config.get('template_config') if isinstance(config.get('template_config'), dict) else {}
        role_prompt = str(template.get('role_prompt') or target.get('description') or '').strip()
        opening = str(template.get('opening_message') or '').strip()
        selling_points = self._collect_text_list(
            template.get('selling_points'),
            template.get('course_profiles'),
            template.get('source_materials'),
            target.get('description'),
        )
        objections = self._collect_text_list(template.get('stop_rules'), template.get('objections'))
        return {
            'agent_name': target.get('name') or '数字员工',
            'role_prompt': role_prompt or '你是一个负责接待客户的数字员工。',
            'opening': opening or f'您好，我是{target.get("name") or "数字员工"}，我先了解一下您的需求。',
            'selling_points': selling_points[:6] or ['快速理解客户问题', '结合业务资料回复', '给出清晰下一步'],
            'objections': objections[:4] or ['价格顾虑', '效果不确定', '想转人工'],
            'next_action': '确认需求后给出下一步或转人工',
        }

    def _collect_text_list(self, *values: Any) -> list[str]:
        items: list[str] = []
        for value in values:
            if not value:
                continue
            if isinstance(value, str):
                items.append(value)
            elif isinstance(value, list):
                for entry in value:
                    if isinstance(entry, str):
                        items.append(entry)
                    elif isinstance(entry, dict):
                        text = entry.get('name') or entry.get('title') or entry.get('description') or entry.get('text')
                        if text:
                            items.append(str(text))
            elif isinstance(value, dict):
                for key in ('name', 'title', 'description', 'text', 'message'):
                    if value.get(key):
                        items.append(str(value[key]))
        return [item.strip() for item in items if item and item.strip()]

    def _customer_turns(self, profile: dict[str, Any], scenario: str) -> list[str]:
        first_point = profile['selling_points'][0] if profile['selling_points'] else '你们的服务'
        objection = profile['objections'][0] if profile['objections'] else '价格有点高'
        return [
            f'你好，我刚看到你们的信息，想了解一下。我的场景是：{scenario}',
            f'你说的{first_point}具体能解决什么问题？能不能说得像真实客服一样清楚一点？',
            f'我主要担心{objection}，如果现在不确定要不要继续，你会怎么建议？',
            '有没有可以马上看的资料、链接、图片或下一步操作？',
            '如果我想找人工确认细节，你这里会怎么处理？',
            '你能把刚才的重点用一句话总结一下吗？',
        ]

    def _assistant_reply(self, profile: dict[str, Any], customer_text: str, turn: int) -> str:
        points = profile['selling_points']
        point = points[min(turn - 1, len(points) - 1)] if points else '先确认您的核心需求'
        if turn == 1:
            return f'{profile["opening"]} 我会先确认需求，再围绕「{point}」给您说明，避免一上来就硬推。'
        if '担心' in customer_text or '不确定' in customer_text:
            return (
                f'能理解，这个顾虑很正常。关于「{point}」，我建议先用一个低成本步骤验证：'
                f'{profile["next_action"]}。如果您需要人工确认，我可以把会话转给人工继续。'
            )
        if '资料' in customer_text or '链接' in customer_text or '图片' in customer_text:
            return '可以，我会优先给到可查看的资料或下一步入口；如果当前配置里缺少链接/图片，也会把它列为需要补齐的优化项。'
        if '人工' in customer_text:
            return '可以转人工。转人工后 AI 会暂停托管，人工可以继续聊天，也可以让 AI 推荐回复再决定是否采纳。'
        return f'重点是「{point}」。我会用短句说明价值、确认您当前情况，并给出一个明确下一步。'

    def _evaluate_conversation(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        assistant_text = '\n'.join(
            str(message.get('content') or '')
            for message in messages
            if message.get('role') == 'assistant'
        )
        checks = {
            'responds_to_objection': any(keyword in assistant_text for keyword in ['顾虑', '担心', '不确定']),
            'has_next_action': any(keyword in assistant_text for keyword in ['下一步', '资料', '链接', '转人工']),
            'handoff_ready': '转人工' in assistant_text or '人工' in assistant_text,
        }
        score = sum(1 for passed in checks.values() if passed)
        suggestions = []
        if not checks['responds_to_objection']:
            suggestions.append('补充客户异议处理话术。')
        if not checks['has_next_action']:
            suggestions.append('每轮回复要给出下一步动作。')
        if not checks['handoff_ready']:
            suggestions.append('增加转人工触发和人工接管说明。')
        return {
            'score': score,
            'max_score': len(checks),
            'checks': checks,
            'suggestions': suggestions,
        }

    def _build_optimization_summary(self, run: dict[str, Any], reason: str) -> str:
        evaluation = run.get('evaluation') if isinstance(run.get('evaluation'), dict) else {}
        suggestions = evaluation.get('suggestions') if isinstance(evaluation.get('suggestions'), list) else []
        suggestion_text = '；'.join(str(item) for item in suggestions if item) or '根据用户不满意原因补强回复策略。'
        return (
            f'自动测试 {run.get("target_name") or run.get("target_uuid")} 需要优化：'
            f'{reason}。建议：{suggestion_text}'
        )

    async def _apply_optimization_note(self, run: dict[str, Any], summary: str) -> dict[str, Any]:
        note = {
            'run_uuid': run.get('uuid'),
            'summary': summary,
            'created_at': datetime.datetime.now().isoformat(),
        }
        target_type = run.get('target_type')
        target_uuid = run.get('target_uuid')

        if target_type == 'pipeline':
            pipeline = await self.ap.pipeline_service.get_pipeline(target_uuid)
            if pipeline is None:
                raise ValueError('pipeline not found')
            config = copy.deepcopy(pipeline.get('config') if isinstance(pipeline.get('config'), dict) else {})
            notes = config.get('auto_test_optimization_notes')
            if not isinstance(notes, list):
                notes = []
            notes.append(note)
            config['auto_test_optimization_notes'] = notes
            await self.ap.pipeline_service.update_pipeline(target_uuid, {'config': config})
            return {'operation': 'append_note', 'path': 'config.auto_test_optimization_notes', 'note': note}

        workflow_target = await self._get_target('workflow', target_uuid)
        workflow = copy.deepcopy(
            workflow_target.get('workflow') if isinstance(workflow_target.get('workflow'), dict) else {}
        )
        notes = workflow.get('auto_test_optimization_notes')
        if not isinstance(notes, list):
            notes = []
        notes.append(note)
        workflow['auto_test_optimization_notes'] = notes
        await self.ap.workflow_service.update_workflow(target_uuid, {'workflow': workflow})
        return {'operation': 'append_note', 'path': 'workflow.auto_test_optimization_notes', 'note': note}

    def _serialize_run(self, row: Any) -> dict[str, Any]:
        column_names = [column.name for column in persistence_autotest.AutoTestRun.__table__.columns]
        if isinstance(row, dict):
            data = {name: row.get(name) for name in column_names}
        elif not isinstance(row, persistence_autotest.AutoTestRun) and hasattr(row, '_mapping'):
            mapping = row._mapping
            if all(name in mapping for name in column_names):
                data = {name: mapping[name] for name in column_names}
            else:
                mapping_values = list(mapping.values())
                row = mapping_values[0] if mapping_values else row
                data = self.ap.persistence_mgr.serialize_model(persistence_autotest.AutoTestRun, row)
        else:
            if not isinstance(row, persistence_autotest.AutoTestRun) and isinstance(row, (tuple, list)):
                row = row[0]
            data = self.ap.persistence_mgr.serialize_model(persistence_autotest.AutoTestRun, row)

        for key, value in list(data.items()):
            if isinstance(value, datetime.datetime):
                data[key] = value.isoformat()
        data['messages'] = data.get('messages') or []
        data['evaluation'] = data.get('evaluation') or {}
        data['optimization_patch'] = data.get('optimization_patch') or {}
        return data
