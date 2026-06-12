from __future__ import annotations

import copy
import datetime
import json
import re
import uuid
from typing import Any

import sqlalchemy

from ....core import app
from ....entity.persistence import autotest as persistence_autotest


class AutoTestService:
    ap: app.Application
    MAX_VERSION_HISTORY = 3

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
        sop_text = self._clean_sop_text(data.get('sop_text'))
        sop_filename = str(data.get('sop_filename') or '').strip()
        messages, evaluation = await self._generate_test_conversation(target_type, target, scenario, turns, sop_text)
        if sop_text:
            evaluation['sop'] = {
                'filename': sop_filename,
                'text': sop_text,
                'enabled': True,
            }
            evaluation['sop_checks'] = self._evaluate_against_sop(messages, sop_text)

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
        if sop_text:
            auto_reason = self._sop_auto_optimization_reason(sop_text, evaluation)
            optimization_plan = await self._generate_optimization_plan(payload, target, auto_reason)
            payload['optimization_summary'] = str(
                optimization_plan.get('summary') or self._build_optimization_summary(payload, auto_reason)
            )
            payload['optimization_patch'] = await self._apply_optimization_plan(
                payload,
                target,
                optimization_plan,
                auto_reason,
            )
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
            target_type = str(run.get('target_type') or '')
            target_uuid = str(run.get('target_uuid') or '')
            target = await self._get_target(target_type, target_uuid)
            optimization_plan = await self._generate_optimization_plan(run, target, reason)
            optimization_summary = str(
                optimization_plan.get('summary') or self._build_optimization_summary(run, reason)
            )
            optimization_patch = await self._apply_optimization_plan(run, target, optimization_plan, reason)

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

    async def revert_run_optimization(self, run_uuid: str) -> dict[str, Any]:
        run = await self.get_run(run_uuid)
        if run is None:
            raise ValueError('auto test run not found')

        patch = run.get('optimization_patch') if isinstance(run.get('optimization_patch'), dict) else {}
        if patch.get('operation') != 'apply_config_patch':
            raise ValueError('auto test run has no applied optimization patch')
        if patch.get('reverted_at'):
            raise ValueError('optimization patch already reverted')
        applied_patches = patch.get('applied_patches') if isinstance(patch.get('applied_patches'), list) else []
        if not applied_patches:
            raise ValueError('auto test run has no applied patches')

        target_type = str(run.get('target_type') or '')
        target_uuid = str(run.get('target_uuid') or '')
        reverted_patches: list[dict[str, Any]] = []
        if target_type == 'pipeline':
            pipeline = await self.ap.pipeline_service.get_pipeline(target_uuid)
            if pipeline is None:
                raise ValueError('pipeline not found')
            config = copy.deepcopy(pipeline.get('config') if isinstance(pipeline.get('config'), dict) else {})
            self._append_version_snapshot(config, run, 'Before reverting auto-test optimization', {'config': copy.deepcopy(config)})
            reverted_patches = self._revert_pipeline_patches(config, applied_patches)
            await self.ap.pipeline_service.update_pipeline(target_uuid, {'config': config})
        elif target_type == 'workflow':
            target = await self._get_target('workflow', target_uuid)
            workflow = copy.deepcopy(target.get('workflow') if isinstance(target.get('workflow'), dict) else {})
            self._append_version_snapshot(workflow, run, 'Before reverting auto-test optimization', {'workflow': copy.deepcopy(workflow)})
            reverted_patches = self._revert_workflow_patches(workflow, applied_patches)
            await self.ap.workflow_service.update_workflow(target_uuid, {'workflow': workflow})
        else:
            raise ValueError('target_type must be pipeline or workflow')

        updated_patch = copy.deepcopy(patch)
        updated_patch['reverted_at'] = datetime.datetime.now().isoformat()
        updated_patch['reverted_patches'] = reverted_patches
        updated_patch['version_retention'] = self.MAX_VERSION_HISTORY
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_autotest.AutoTestRun)
            .where(persistence_autotest.AutoTestRun.uuid == run_uuid)
            .values(optimization_patch=updated_patch, updated_at=sqlalchemy.func.now())
        )
        updated_run = copy.deepcopy(run)
        updated_run['optimization_patch'] = updated_patch
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

    async def _generate_test_conversation(
        self,
        target_type: str,
        target: dict[str, Any],
        scenario: str,
        turns: int,
        sop_text: str = '',
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        model_uuid = self._preferred_optimizer_model_uuid({'target_type': target_type}, target)
        if model_uuid:
            try:
                prompt = self._build_test_conversation_prompt(target_type, target, scenario, turns, sop_text)
                response_text, model_name = await self._invoke_optimizer_model(model_uuid, prompt)
                parsed = self._parse_optimizer_response(response_text)
                messages = self._normalize_generated_messages(parsed.get('messages'), target, turns)
                evaluation = parsed.get('evaluation') if isinstance(parsed.get('evaluation'), dict) else {}
                if messages:
                    fallback_evaluation = self._evaluate_conversation(messages)
                    evaluation = {
                        **fallback_evaluation,
                        **evaluation,
                        'ai_generated': True,
                        'model_name': model_name,
                    }
                    return messages, evaluation
            except Exception:
                pass

        messages = self._simulate_conversation(target_type, target, scenario, turns)
        evaluation = self._evaluate_conversation(messages)
        evaluation['ai_generated'] = False
        return messages, evaluation

    def _build_test_conversation_prompt(
        self,
        target_type: str,
        target: dict[str, Any],
        scenario: str,
        turns: int,
        sop_text: str,
    ) -> str:
        payload = {
            'task': 'Simulate a realistic sales customer and customer-service conversation for auto testing.',
            'target_type': target_type,
            'scenario': scenario,
            'turns': turns,
            'sop': sop_text,
            'target': self._optimizer_target_snapshot(target_type, target),
            'required_json_schema': {
                'messages': [
                    {
                        'role': 'user or assistant',
                        'sender': 'short display name',
                        'content_type': 'text',
                        'content': 'realistic chat message',
                        'turn': 1,
                    }
                ],
                'evaluation': {
                    'score': 0,
                    'max_score': 3,
                    'checks': {'sop_followed': False},
                    'suggestions': ['what to improve'],
                },
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    def _normalize_generated_messages(
        self,
        messages: Any,
        target: dict[str, Any],
        turns: int,
    ) -> list[dict[str, Any]]:
        if not isinstance(messages, list):
            return []
        normalized: list[dict[str, Any]] = []
        agent_name = str(target.get('name') or 'AI')
        for index, message in enumerate(messages[: turns * 2], start=1):
            if not isinstance(message, dict):
                continue
            role = str(message.get('role') or '').strip()
            if role not in {'user', 'assistant'}:
                continue
            content = str(message.get('content') or '').strip()
            if not content:
                continue
            turn = message.get('turn')
            if not isinstance(turn, int):
                turn = max(1, (index + 1) // 2)
            normalized.append(
                {
                    'role': role,
                    'sender': str(message.get('sender') or ('模拟客户' if role == 'user' else agent_name)),
                    'content_type': str(message.get('content_type') or 'text'),
                    'content': content,
                    'turn': turn,
                }
            )
        return normalized

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

    def _clean_sop_text(self, value: Any) -> str:
        text = str(value or '').strip()
        if not text:
            return ''
        return text[:20000]

    def _evaluate_against_sop(self, messages: list[dict[str, Any]], sop_text: str) -> dict[str, Any]:
        assistant_text = '\n'.join(
            str(message.get('content') or '')
            for message in messages
            if message.get('role') == 'assistant'
        ).lower()
        sop_lower = sop_text.lower()
        checks = {
            'mentions_handoff_when_required': not any(
                keyword in sop_lower for keyword in ['human', 'handoff', '人工', '转人工']
            )
            or any(keyword in assistant_text for keyword in ['human', 'handoff', '人工', '转人工']),
            'uses_next_step': any(keyword in assistant_text for keyword in ['next', '下一步', '资料', 'link', '链接']),
            'keeps_readable_reply': len(max(assistant_text.split('\n') or [''], key=len)) <= 260,
        }
        suggestions = []
        if not checks['mentions_handoff_when_required']:
            suggestions.append('SOP requires human handoff, but the reply did not clearly hand off.')
        if not checks['uses_next_step']:
            suggestions.append('SOP auto test needs a clearer next step.')
        if not checks['keeps_readable_reply']:
            suggestions.append('Reply is too long for real chat readability.')
        return {
            'score': sum(1 for passed in checks.values() if passed),
            'max_score': len(checks),
            'checks': checks,
            'suggestions': suggestions,
        }

    def _sop_auto_optimization_reason(self, sop_text: str, evaluation: dict[str, Any]) -> str:
        sop_checks = evaluation.get('sop_checks') if isinstance(evaluation.get('sop_checks'), dict) else {}
        suggestions = sop_checks.get('suggestions') if isinstance(sop_checks.get('suggestions'), list) else []
        suggestion_text = '; '.join(str(item) for item in suggestions if item)
        return (
            'Use the uploaded SOP to automatically optimize this target. '
            f'SOP excerpt: {sop_text[:2000]}'
            + (f' Evaluation gaps: {suggestion_text}' if suggestion_text else '')
        )

    def _build_optimization_summary(self, run: dict[str, Any], reason: str) -> str:
        evaluation = run.get('evaluation') if isinstance(run.get('evaluation'), dict) else {}
        suggestions = evaluation.get('suggestions') if isinstance(evaluation.get('suggestions'), list) else []
        suggestion_text = '；'.join(str(item) for item in suggestions if item) or '根据用户不满意原因补强回复策略。'
        return (
            f'自动测试 {run.get("target_name") or run.get("target_uuid")} 需要优化：'
            f'{reason}。建议：{suggestion_text}'
        )

    async def _generate_optimization_plan(
        self,
        run: dict[str, Any],
        target: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        model_uuid = self._preferred_optimizer_model_uuid(run, target)
        optimizer_error = ''
        if model_uuid:
            try:
                prompt = self._build_optimizer_prompt(run, target, reason)
                optimizer_text, model_name = await self._invoke_optimizer_model(model_uuid, prompt)
                plan = self._parse_optimizer_response(optimizer_text)
                plan = self._normalize_optimization_plan(plan)
                if plan.get('patches'):
                    plan['ai_generated'] = True
                    plan['model_uuid'] = model_uuid
                    plan['model_name'] = model_name
                    return plan
            except Exception as exc:  # pragma: no cover - live providers vary widely.
                optimizer_error = str(exc)

        plan = self._fallback_optimization_plan(run, target, reason)
        if optimizer_error:
            plan['optimizer_error'] = optimizer_error
        return plan

    async def _apply_optimization_plan(
        self,
        run: dict[str, Any],
        target: dict[str, Any],
        plan: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        target_type = str(run.get('target_type') or '')
        patches = plan.get('patches') if isinstance(plan.get('patches'), list) else []
        if not any(self._is_allowed_patch_path(target_type, str(patch.get('path') or '')) for patch in patches if isinstance(patch, dict)):
            fallback_plan = self._fallback_optimization_plan(run, target, reason)
            fallback_plan['fallback_reason'] = 'optimizer_returned_no_safe_patch'
            if plan.get('summary'):
                fallback_plan['summary'] = str(plan['summary'])
            plan = fallback_plan

        if target_type == 'pipeline':
            return await self._apply_pipeline_optimization(run, plan, reason)
        if target_type == 'workflow':
            return await self._apply_workflow_optimization(run, target, plan, reason)
        raise ValueError('target_type must be pipeline or workflow')

    async def _apply_pipeline_optimization(
        self,
        run: dict[str, Any],
        plan: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        target_uuid = str(run.get('target_uuid') or '')
        pipeline = await self.ap.pipeline_service.get_pipeline(target_uuid)
        if pipeline is None:
            raise ValueError('pipeline not found')

        config = copy.deepcopy(pipeline.get('config') if isinstance(pipeline.get('config'), dict) else {})
        template = config.get('template_config') if isinstance(config.get('template_config'), dict) else {}
        template = copy.deepcopy(template)
        config['template_config'] = template
        before_config = copy.deepcopy(config)

        applied: list[dict[str, Any]] = []
        ignored: list[dict[str, Any]] = []
        for patch in plan.get('patches', []):
            if not isinstance(patch, dict):
                continue
            path = str(patch.get('path') or '')
            value = str(patch.get('value') or '').strip()
            if not value:
                ignored.append({'path': path, 'reason': 'empty_value'})
                continue
            if path == 'config.template_config.role_prompt':
                before = template.get('role_prompt') or ''
                template['role_prompt'] = value
                applied.append({'path': path, 'before': before, 'after': value})
            elif path == 'config.template_config.opening_message':
                before = template.get('opening_message') or ''
                template['opening_message'] = value
                applied.append({'path': path, 'before': before, 'after': value})
            else:
                ignored.append({'path': path, 'reason': 'path_not_allowed'})

        if not applied:
            fallback_plan = self._fallback_optimization_plan(run, pipeline, reason)
            for patch in fallback_plan.get('patches', []):
                path = str(patch.get('path') or '')
                value = str(patch.get('value') or '').strip()
                if path == 'config.template_config.role_prompt' and value:
                    before = template.get('role_prompt') or ''
                    template['role_prompt'] = value
                    applied.append({'path': path, 'before': before, 'after': value})
                    break

        summary = str(plan.get('summary') or self._build_optimization_summary(run, reason))
        self._append_version_snapshot(config, run, summary, {'config': before_config})
        history_entry = self._optimization_history_entry(run, plan, reason, summary, applied)
        self._append_history(config, history_entry)
        self._append_legacy_note(config, run, summary)

        await self.ap.pipeline_service.update_pipeline(target_uuid, {'config': config})
        return self._optimization_patch_result(run, plan, applied, ignored, 'pipeline')

    async def _apply_workflow_optimization(
        self,
        run: dict[str, Any],
        target: dict[str, Any],
        plan: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        target_uuid = str(run.get('target_uuid') or '')
        workflow = copy.deepcopy(target.get('workflow') if isinstance(target.get('workflow'), dict) else {})
        nodes = workflow.get('nodes') if isinstance(workflow.get('nodes'), list) else []
        workflow['nodes'] = nodes
        before_workflow = copy.deepcopy(workflow)

        applied: list[dict[str, Any]] = []
        ignored: list[dict[str, Any]] = []
        for patch in plan.get('patches', []):
            if not isinstance(patch, dict):
                continue
            applied_patch = self._apply_workflow_patch(nodes, patch)
            if applied_patch is None:
                ignored.append({'path': str(patch.get('path') or ''), 'reason': 'path_not_allowed_or_missing_node'})
            else:
                applied.append(applied_patch)

        if not applied:
            fallback_plan = self._fallback_optimization_plan(run, target, reason)
            for patch in fallback_plan.get('patches', []):
                applied_patch = self._apply_workflow_patch(nodes, patch)
                if applied_patch is not None:
                    applied.append(applied_patch)
                    break

        summary = str(plan.get('summary') or self._build_optimization_summary(run, reason))
        self._append_version_snapshot(workflow, run, summary, {'workflow': before_workflow})
        history_entry = self._optimization_history_entry(run, plan, reason, summary, applied)
        self._append_history(workflow, history_entry)
        self._append_legacy_note(workflow, run, summary)

        await self.ap.workflow_service.update_workflow(target_uuid, {'workflow': workflow})
        return self._optimization_patch_result(run, plan, applied, ignored, 'workflow')

    def _apply_workflow_patch(self, nodes: list[dict[str, Any]], patch: dict[str, Any]) -> dict[str, Any] | None:
        path = str(patch.get('path') or '')
        value = str(patch.get('value') or '').strip()
        if not value or not self._is_allowed_patch_path('workflow', path):
            return None

        parts = path.split('.')
        if len(parts) < 4 or parts[:2] != ['workflow', 'nodes']:
            return None
        node_id = parts[2]
        node = next((item for item in nodes if isinstance(item, dict) and str(item.get('id')) == node_id), None)
        if node is None:
            return None

        field_parts = parts[3:]
        if field_parts == ['description']:
            before = node.get('description') or ''
            node['description'] = value
            return {'path': path, 'before': before, 'after': value}
        if field_parts == ['title']:
            before = node.get('title') or ''
            node['title'] = value
            return {'path': path, 'before': before, 'after': value}
        if len(field_parts) == 2 and field_parts[0] == 'config':
            key = field_parts[1]
            if key not in {'prompt', 'instructions', 'message', 'system_prompt'}:
                return None
            config = node.get('config') if isinstance(node.get('config'), dict) else {}
            config = copy.deepcopy(config)
            before = config.get(key) or ''
            config[key] = value
            node['config'] = config
            return {'path': path, 'before': before, 'after': value}
        return None

    def _preferred_optimizer_model_uuid(self, run: dict[str, Any], target: dict[str, Any]) -> str:
        if run.get('target_type') == 'pipeline':
            config = target.get('config') if isinstance(target.get('config'), dict) else {}
            template = config.get('template_config') if isinstance(config.get('template_config'), dict) else {}
            candidate = str(template.get('model_uuid') or '').strip()
            if candidate:
                return candidate

        workflow = target.get('workflow') if isinstance(target.get('workflow'), dict) else {}
        nodes = workflow.get('nodes') if isinstance(workflow.get('nodes'), list) else []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            config = node.get('config') if isinstance(node.get('config'), dict) else {}
            candidate = str(config.get('model_uuid') or '').strip()
            if candidate:
                return candidate

        model_mgr = getattr(self.ap, 'model_mgr', None)
        for runtime_model in getattr(model_mgr, 'llm_models', []) or []:
            model_entity = getattr(runtime_model, 'model_entity', None)
            candidate = str(getattr(model_entity, 'uuid', '') or '').strip()
            if candidate:
                return candidate
        return ''

    async def _invoke_optimizer_model(self, model_uuid: str, prompt: str) -> tuple[str, str]:
        from langbot_plugin.api.entities.builtin.provider import message as provider_message

        model_mgr = getattr(self.ap, 'model_mgr', None)
        if model_mgr is None:
            raise ValueError('model manager is not available')
        runtime_model = await model_mgr.get_model_by_uuid(model_uuid)
        model_entity = getattr(runtime_model, 'model_entity', None)
        model_name = str(getattr(model_entity, 'name', '') or model_uuid)
        extra_args = copy.deepcopy(getattr(model_entity, 'extra_args', {}) or {})
        messages = [
            provider_message.Message(
                role='system',
                content=(
                    '你是一个销售客服自动优化器。只输出 JSON，不要输出解释文字。'
                    '你只能改允许的 prompt/开场白/工作流节点文案字段，不能删除数据。'
                ),
            ),
            provider_message.Message(role='user', content=prompt),
        ]
        response = await runtime_model.provider.invoke_llm(
            query=None,
            model=runtime_model,
            messages=messages,
            funcs=[],
            extra_args=extra_args,
            remove_think=True,
        )
        return self._message_content_to_text(getattr(response, 'content', response)), model_name

    def _build_optimizer_prompt(self, run: dict[str, Any], target: dict[str, Any], reason: str) -> str:
        target_type = str(run.get('target_type') or '')
        safe_target = self._optimizer_target_snapshot(target_type, target)
        payload = {
            'task': 'Generate a safe config patch that will improve the next customer-service reply.',
            'target_type': target_type,
            'target_name': run.get('target_name') or target.get('name'),
            'scenario': run.get('scenario'),
            'messages': run.get('messages') or [],
            'evaluation': run.get('evaluation') or {},
            'human_unsatisfied_reason': reason,
            'current_target': safe_target,
            'allowed_paths': self._allowed_patch_paths_text(target_type, safe_target),
            'required_json_schema': {
                'summary': 'short Chinese summary of what will improve',
                'patches': [{'path': 'allowed path', 'value': 'complete replacement string'}],
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    def _optimizer_target_snapshot(self, target_type: str, target: dict[str, Any]) -> dict[str, Any]:
        if target_type == 'pipeline':
            config = target.get('config') if isinstance(target.get('config'), dict) else {}
            template = config.get('template_config') if isinstance(config.get('template_config'), dict) else {}
            return {
                'name': target.get('name'),
                'description': target.get('description'),
                'template_config': {
                    'role_prompt': str(template.get('role_prompt') or '')[:6000],
                    'opening_message': str(template.get('opening_message') or '')[:1000],
                    'recommended_questions': template.get('recommended_questions') or [],
                    'stop_rules': template.get('stop_rules') or {},
                },
            }

        workflow = target.get('workflow') if isinstance(target.get('workflow'), dict) else {}
        nodes = workflow.get('nodes') if isinstance(workflow.get('nodes'), list) else []
        safe_nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            config = node.get('config') if isinstance(node.get('config'), dict) else {}
            safe_nodes.append(
                {
                    'id': node.get('id'),
                    'type': node.get('type'),
                    'title': node.get('title'),
                    'description': node.get('description'),
                    'config': {
                        'prompt': str(config.get('prompt') or '')[:4000],
                        'instructions': str(config.get('instructions') or '')[:4000],
                        'message': str(config.get('message') or '')[:2000],
                        'system_prompt': str(config.get('system_prompt') or '')[:4000],
                        'model_uuid': config.get('model_uuid') or '',
                    },
                }
            )
        return {'name': target.get('name'), 'description': target.get('description'), 'nodes': safe_nodes}

    def _allowed_patch_paths_text(self, target_type: str, snapshot: dict[str, Any]) -> list[str]:
        if target_type == 'pipeline':
            return ['config.template_config.role_prompt', 'config.template_config.opening_message']
        return [
            path
            for node in snapshot.get('nodes', [])
            for path in (
                f"workflow.nodes.{node.get('id')}.description",
                f"workflow.nodes.{node.get('id')}.config.prompt",
                f"workflow.nodes.{node.get('id')}.config.instructions",
                f"workflow.nodes.{node.get('id')}.config.message",
                f"workflow.nodes.{node.get('id')}.config.system_prompt",
            )
            if node.get('id')
        ]

    def _parse_optimizer_response(self, text: str) -> dict[str, Any]:
        raw = (text or '').strip()
        if not raw:
            return {}
        fence = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, flags=re.S)
        if fence:
            raw = fence.group(1)
        else:
            start = raw.find('{')
            end = raw.rfind('}')
            if start >= 0 and end > start:
                raw = raw[start : end + 1]
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _normalize_optimization_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        normalized = copy.deepcopy(plan) if isinstance(plan, dict) else {}
        summary = str(normalized.get('summary') or '').strip()
        patches: list[dict[str, str]] = []
        for patch in normalized.get('patches', []):
            if not isinstance(patch, dict):
                continue
            path = str(patch.get('path') or '').strip()
            value = str(patch.get('value') or '').strip()
            if path and value:
                patches.append({'path': path, 'value': value})
        normalized['summary'] = summary
        normalized['patches'] = patches[:8]
        return normalized

    def _fallback_optimization_plan(
        self,
        run: dict[str, Any],
        target: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        summary = self._build_optimization_summary(run, reason)
        run_id = str(run.get('uuid') or '')[:8]
        rule_block = (
            f"\n\n[Auto-test optimization {run_id}]\n"
            f"Human feedback: {reason}\n"
            "Required behavior:\n"
            "1. Acknowledge the customer's exact concern before selling.\n"
            "2. Answer with short, readable, real chat-style sentences.\n"
            "3. Give one clear next step, link/material instruction, or human handoff option.\n"
            "4. If the customer is angry or asks for a human, pause AI takeover and hand off."
        )

        if run.get('target_type') == 'pipeline':
            config = target.get('config') if isinstance(target.get('config'), dict) else {}
            template = config.get('template_config') if isinstance(config.get('template_config'), dict) else {}
            current_prompt = str(template.get('role_prompt') or '').strip()
            current_opening = str(template.get('opening_message') or '').strip()
            return {
                'summary': summary,
                'ai_generated': False,
                'patches': [
                    {
                        'path': 'config.template_config.role_prompt',
                        'value': (current_prompt or 'You are a sales customer-service digital employee.') + rule_block,
                    },
                    {
                        'path': 'config.template_config.opening_message',
                        'value': current_opening
                        or '您好，我先确认您的具体情况，再给您一个明确、可执行的下一步。',
                    },
                ],
            }

        workflow = target.get('workflow') if isinstance(target.get('workflow'), dict) else {}
        nodes = workflow.get('nodes') if isinstance(workflow.get('nodes'), list) else []
        target_node = self._choose_workflow_optimization_node(nodes)
        if target_node is None:
            return {'summary': summary, 'ai_generated': False, 'patches': []}
        config = target_node.get('config') if isinstance(target_node.get('config'), dict) else {}
        current_prompt = str(
            config.get('prompt') or config.get('instructions') or target_node.get('description') or ''
        ).strip()
        return {
            'summary': summary,
            'ai_generated': False,
            'patches': [
                {
                    'path': f"workflow.nodes.{target_node.get('id')}.config.prompt",
                    'value': (current_prompt or 'Reply as a sales customer-service agent.') + rule_block,
                }
            ],
        }

    def _choose_workflow_optimization_node(self, nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
        preferred_types = {'llm', 'knowledge', 'intent', 'task', 'handoff'}
        for node in nodes:
            if isinstance(node, dict) and node.get('type') in preferred_types and node.get('id'):
                return node
        for node in nodes:
            if isinstance(node, dict) and node.get('id'):
                return node
        return None

    def _is_allowed_patch_path(self, target_type: str, path: str) -> bool:
        if target_type == 'pipeline':
            return path in {'config.template_config.role_prompt', 'config.template_config.opening_message'}
        if target_type == 'workflow':
            if not path.startswith('workflow.nodes.'):
                return False
            parts = path.split('.')
            if len(parts) == 4 and parts[3] in {'description', 'title'}:
                return True
            return len(parts) == 5 and parts[3] == 'config' and parts[4] in {
                'prompt',
                'instructions',
                'message',
                'system_prompt',
            }
        return False

    def _optimization_history_entry(
        self,
        run: dict[str, Any],
        plan: dict[str, Any],
        reason: str,
        summary: str,
        applied: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            'run_uuid': run.get('uuid'),
            'reason': reason,
            'summary': summary,
            'created_at': datetime.datetime.now().isoformat(),
            'ai_generated': bool(plan.get('ai_generated')),
            'model_uuid': plan.get('model_uuid') or '',
            'model_name': plan.get('model_name') or '',
            'applied_patches': [{'path': item.get('path')} for item in applied],
        }

    def _append_history(self, container: dict[str, Any], entry: dict[str, Any]) -> None:
        history = container.get('auto_test_optimization_history')
        if not isinstance(history, list):
            history = []
        history.append(entry)
        container['auto_test_optimization_history'] = history

    def _append_version_snapshot(
        self,
        container: dict[str, Any],
        run: dict[str, Any],
        summary: str,
        snapshot: dict[str, Any],
    ) -> None:
        history = container.get('auto_test_version_history')
        if not isinstance(history, list):
            history = []
        history.append(
            {
                'version_uuid': str(uuid.uuid4()),
                'run_uuid': run.get('uuid'),
                'created_at': datetime.datetime.now().isoformat(),
                'summary': summary,
                'snapshot': snapshot,
            }
        )
        container['auto_test_version_history'] = history[-self.MAX_VERSION_HISTORY :]

    def _append_legacy_note(self, container: dict[str, Any], run: dict[str, Any], summary: str) -> None:
        notes = container.get('auto_test_optimization_notes')
        if not isinstance(notes, list):
            notes = []
        notes.append(
            {
                'run_uuid': run.get('uuid'),
                'summary': summary,
                'created_at': datetime.datetime.now().isoformat(),
            }
        )
        container['auto_test_optimization_notes'] = notes

    def _optimization_patch_result(
        self,
        run: dict[str, Any],
        plan: dict[str, Any],
        applied: list[dict[str, Any]],
        ignored: list[dict[str, Any]],
        target_type: str,
    ) -> dict[str, Any]:
        return {
            'operation': 'apply_config_patch',
            'target_type': target_type,
            'target_uuid': run.get('target_uuid'),
            'ai_generated': bool(plan.get('ai_generated')),
            'model_uuid': plan.get('model_uuid') or '',
            'model_name': plan.get('model_name') or '',
            'applied_patches': applied,
            'ignored_patches': ignored,
            'fallback_reason': plan.get('fallback_reason') or '',
            'optimizer_error': plan.get('optimizer_error') or '',
            'version_retention': self.MAX_VERSION_HISTORY,
        }

    def _revert_pipeline_patches(
        self,
        config: dict[str, Any],
        applied_patches: list[Any],
    ) -> list[dict[str, Any]]:
        template = config.get('template_config') if isinstance(config.get('template_config'), dict) else {}
        template = copy.deepcopy(template)
        config['template_config'] = template
        reverted: list[dict[str, Any]] = []
        for patch in reversed(applied_patches):
            if not isinstance(patch, dict):
                continue
            path = str(patch.get('path') or '')
            before = patch.get('before')
            if path == 'config.template_config.role_prompt':
                current = template.get('role_prompt') or ''
                template['role_prompt'] = before if isinstance(before, str) else str(before or '')
                reverted.append({'path': path, 'before_revert': current, 'after_revert': template['role_prompt']})
            elif path == 'config.template_config.opening_message':
                current = template.get('opening_message') or ''
                template['opening_message'] = before if isinstance(before, str) else str(before or '')
                reverted.append({'path': path, 'before_revert': current, 'after_revert': template['opening_message']})
        return reverted

    def _revert_workflow_patches(
        self,
        workflow: dict[str, Any],
        applied_patches: list[Any],
    ) -> list[dict[str, Any]]:
        nodes = workflow.get('nodes') if isinstance(workflow.get('nodes'), list) else []
        workflow['nodes'] = nodes
        reverted: list[dict[str, Any]] = []
        for patch in reversed(applied_patches):
            if not isinstance(patch, dict):
                continue
            path = str(patch.get('path') or '')
            before = patch.get('before')
            if not self._is_allowed_patch_path('workflow', path):
                continue
            parts = path.split('.')
            node = next((item for item in nodes if isinstance(item, dict) and str(item.get('id')) == parts[2]), None)
            if node is None:
                continue
            value = before if isinstance(before, str) else str(before or '')
            if len(parts) == 4 and parts[3] in {'description', 'title'}:
                current = node.get(parts[3]) or ''
                node[parts[3]] = value
                reverted.append({'path': path, 'before_revert': current, 'after_revert': value})
            elif len(parts) == 5 and parts[3] == 'config':
                config = node.get('config') if isinstance(node.get('config'), dict) else {}
                config = copy.deepcopy(config)
                current = config.get(parts[4]) or ''
                config[parts[4]] = value
                node['config'] = config
                reverted.append({'path': path, 'before_revert': current, 'after_revert': value})
        return reverted

    def _message_content_to_text(self, content: Any) -> str:
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
                else:
                    parts.append(str(item))
            return '\n'.join(parts)
        return str(content or '')

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
