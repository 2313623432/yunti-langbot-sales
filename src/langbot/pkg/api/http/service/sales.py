from __future__ import annotations

import base64
import copy
import datetime
import json
import mimetypes
import os
import re
from types import SimpleNamespace
import uuid
from typing import Any

import sqlalchemy

from ....core import app
from ....entity.persistence import monitoring as persistence_monitoring
from ....entity.persistence import sales as persistence_sales


YUANFUDAO_SIGNUP_LINK = (
    'https://m.yuanfudao.com/primary/templates/package?'
    'pageId=6641&solutionId=27246&keyfrom=yfd-qudaohezuo-xiaoxue-9yyy-CPA-yunti9-siyu-yangzy-yingtao3class'
)

YUANFUDAO_CATALOG_PRODUCTS = [
    {
        'uuid': 'yuanfudao-phonics-course',
        'product_line': '猿辅导',
        'profile_key': 'phonics',
        'keywords': ['英语', '自然拼读', '拼读', '发音', '单词', '绘本', '口语', '听音能写', '见词能读'],
        'name': '猿辅导英语自然拼读体验课',
        'category': '自然拼读',
        'price': '9元体验',
        'link': YUANFUDAO_SIGNUP_LINK,
        'description': (
            '猿辅导英语自然拼读体验课/自然拼读集训营，5天10节课，'
            '适合大班至小学4年级，帮助孩子掌握自然拼读、口语发音和拼读规则。'
        ),
        'selling_points': [
            '见词能拼、听音能写',
            '用拼读方法替代死记硬背',
            '5次绘本阅读实践、180次开口练习',
            '3年内无限次回放',
        ],
        'pain_points': ['孩子英语发音和拼读基础弱', '家长不知道图书资源怎么用', '家长担心时间冲突'],
        'objections': ['不买/考虑', '和其他课冲突', '没时间', '孩子年级不确定'],
        'audience': ['大班至小学4年级家长', '自然拼读启蒙需求', '图书扫码资源用户'],
        'enabled': True,
    },
    {
        'uuid': 'yuanfudao-reading-thinking-course',
        'product_line': '猿辅导',
        'profile_key': 'reading_thinking',
        'keywords': ['阅读', '作文', '写作', '数学', '思维', '应用题', '粗心', '马虎', '变通', '读写'],
        'name': '猿辅导阅读+思维特训营',
        'category': '阅读+思维',
        'price': '9元体验',
        'link': YUANFUDAO_SIGNUP_LINK,
        'description': (
            '猿辅导阅读+思维特训营，390分钟名师直播精讲，'
            '主要解决阅读没头绪、作文凑字数、数学难变通和常马虎等问题。'
        ),
        'selling_points': [
            '数学思维体系搭建',
            '阅读写作高频技巧',
            '1次双科测评、150次精练与带练',
            '从底层逻辑提升复杂题理解与表达',
        ],
        'pain_points': ['阅读没头绪', '作文凑字数', '数学难变通', '做题常马虎'],
        'objections': ['不确定适不适合', '和其他课冲突', '孩子没时间'],
        'audience': ['小学阶段家长', '阅读写作需要提升的孩子', '数学思维需要提升的孩子'],
        'enabled': True,
    },
]

DEFAULT_SALES_PRODUCTS = [
    {
        'uuid': 'sales-ai-assistant',
        'name': 'AI 销售助手',
        'category': '销售自动化',
        'price': '按项目配置',
        'link': 'https://example.com/ai-sales',
        'description': '把 AI 接入微信、企微、飞书、钉钉、Telegram、网站聊天等现有渠道，自动识别客户意图并辅助成交。',
        'selling_points': ['自动识别客户意图', '根据产品卖点生成销售回复', '高意向客户自动转人工', '沉淀客户记忆与跟进记录'],
        'pain_points': ['销售回复不及时', '客户意向难判断', '多平台咨询分散', '人工跟进容易遗漏'],
        'objections': ['担心 AI 回复不准', '担心接入现有平台麻烦', '担心客户需要人工服务'],
        'audience': ['销售团队', '私域运营', '客服团队', '教育与本地生活商家'],
        'enabled': True,
    },
    {
        'uuid': 'product-knowledge-base',
        'name': '产品知识库',
        'category': '销售资料',
        'price': '内置',
        'link': 'https://example.com/product-kb',
        'description': '集中管理产品卖点、链接、价格、适用客户、异议处理，让 AI 销售回答更稳定。',
        'selling_points': ['统一产品口径', '支持多产品匹配', '可沉淀常见异议', '可结合 RAG 知识库扩展资料'],
        'pain_points': ['销售话术不统一', '产品信息更新慢', '新人难快速掌握卖点'],
        'objections': ['已有文档不好迁移', '担心维护成本高'],
        'audience': ['销售主管', '产品运营', '客服培训负责人'],
        'enabled': True,
    },
]


COURSE_SALES_EXPLICIT_REJECTION_COUNT_KEY = 'course_sales_explicit_rejection_count'
SALES_RESET_COMMANDS = {'/new', '／new'}
HANDOFF_REASON_KEYWORDS = {
    'child_spam': ['child_spam', 'spam_flood', '刷屏', '无意义消息', '乱发', '骚扰'],
    'parent_complaint': ['parent_complaint', '投诉', '不满意', '生气', '骗人', '找负责人'],
    'payment_issue': ['payment_issue', '付款', '支付', '扣款', '退款', '退钱', '没有开通'],
    'resource_missing': ['resource_missing', '资源缺失', '资源为空', '资源没有', '没有资源', '缺资源', '补传'],
    'needs_teacher': ['needs_teacher', '老师', '讲解', '讲题', '答疑', '不会做'],
    'non_target_grade': ['non_target_grade', '非目标年级', '不是目标年级', '初中', '高中', '不适合年级'],
}


SCHEDULED_PUSH_OUTREACH_SEGMENTS = {'course-sales:broadcast'}
FOLLOWUP_OUTREACH_SEGMENT_PREFIXES = ('course-sales:followup', 'course-sales:radar')


class SalesService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    def classify_intent(self, text: str) -> dict[str, Any]:
        normalized = (text or '').strip().lower()
        rules = [
            (
                'handoff',
                [
                    '转人工',
                    '人工',
                    '真人',
                    '销售联系',
                    '电话联系',
                    '加微信',
                    '报价单',
                    '合同',
                    '投诉',
                    '生气',
                    '太差',
                    '骗人',
                    '退钱',
                    '不满意',
                    '别废话',
                    '找负责人',
                ],
                0.9,
                True,
            ),
            ('price', ['价格', '多少钱', '费用', '收费', '报价', '预算', '便宜', '贵'], 0.78, False),
            ('purchase', ['购买', '下单', '开通', '试用', '怎么买', '付款', '成交'], 0.82, False),
            ('comparison', ['对比', '比较', '竞品', '区别', '优势', '为什么选'], 0.72, False),
            ('objection', ['担心', '怕', '不确定', '风险', '麻烦', '不准', '安全'], 0.68, False),
            ('product_interest', ['产品', '功能', '能不能', '支持', '介绍', '方案'], 0.62, False),
        ]
        for intent, keywords, confidence, requires_handoff in rules:
            matched = [keyword for keyword in keywords if keyword in normalized]
            if matched:
                return {
                    'intent': intent,
                    'confidence': confidence,
                    'requires_handoff': requires_handoff,
                    'matched_keywords': matched,
                    'reason': f'命中关键词：{", ".join(matched)}',
                }
        return {
            'intent': 'general',
            'confidence': 0.45,
            'requires_handoff': False,
            'matched_keywords': [],
            'reason': '未命中明确销售意图，按普通咨询处理',
        }

    def select_best_product(self, message: str, products: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not products:
            return None

        normalized = (message or '').lower()
        best_product = None
        best_score = -1

        for product in products:
            score = 0
            searchable_fields = [
                product.get('name', ''),
                product.get('category', ''),
                product.get('description', ''),
                *self._to_list(product.get('selling_points')),
                *self._to_list(product.get('pain_points')),
                *self._to_list(product.get('audience')),
            ]
            for field in searchable_fields:
                field_text = str(field).lower()
                if field_text and field_text in normalized:
                    score += 4
                for token in self._tokenize(field_text):
                    if token and token in normalized:
                        score += 1
            if score > best_score:
                best_product = product
                best_score = score

        return best_product or products[0]

    def generate_pitch(
        self,
        product: dict[str, Any],
        customer_profile: str = '',
        intent: str = '',
        tone: str = 'consultative',
    ) -> dict[str, str]:
        selling_points = self._to_list(product.get('selling_points'))[:3]
        pain_points = self._to_list(product.get('pain_points'))[:2]
        link = product.get('link', '')
        price = product.get('price', '')

        intro = f'这款「{product.get("name", "产品")}」适合你现在的需求。'
        if customer_profile:
            intro = f'结合你的情况（{customer_profile}），{intro}'
        if intent:
            intro += f' 我判断你当前关注点是：{intent}。'

        point_text = '；'.join(selling_points) if selling_points else '提升销售响应与跟进效率'
        pain_text = '，'.join(pain_points) if pain_points else '销售跟进效率和转化稳定性'
        message = f'{intro}它主要解决「{pain_text}」这类问题，核心卖点是：{point_text}。'
        if price:
            message += f' 价格/套餐：{price}。'
        if link:
            message += f' 可以先看这个链接：{link}'

        return {
            'tone': tone,
            'message': message,
            'next_action': 'send_product_link' if link else 'ask_qualifying_question',
        }

    def is_reset_command(self, text: str) -> bool:
        return (text or '').strip().lower() in SALES_RESET_COMMANDS

    def normalize_handoff_reason(self, reason: str) -> str:
        text = str(reason or '').strip()
        if not text:
            return ''
        normalized = text.lower()
        for label, keywords in HANDOFF_REASON_KEYWORDS.items():
            if normalized == label:
                return label
            if any(keyword.lower() in normalized for keyword in keywords):
                return label
        return text

    def compose_sales_prompt(
        self,
        product: dict[str, Any] | None,
        memory: dict[str, Any] | None,
        intent: dict[str, Any] | None,
    ) -> str:
        product = product or {}
        memory = memory or {}
        intent = intent or {'intent': 'general', 'confidence': 0}
        selling_points = '、'.join(self._to_list(product.get('selling_points'))[:5]) or '根据客户问题选择合适卖点'
        objections = '、'.join(self._to_list(product.get('objections'))[:4]) or '如客户有疑虑，先确认原因再解释'

        return f"""
你是一个专业、克制、以成交为目标的 AI 销售顾问。请用用户使用的语言回复。

销售原则：
1. 先理解客户需求，再匹配产品卖点，不要夸大承诺。
2. 如果客户信息不足，只问一个最关键的澄清问题。
3. 当客户表现出购买、价格、对比或试用意向时，主动给出下一步行动。
4. 客户明确要求人工、报价单、合同、电话、加微信或复杂定制时，必须转人工，不要继续硬推。
5. 输出要像真实销售对话，短句、具体、有下一步。
6. 涉及产品链接时，只能使用“当前推荐产品”里的真实链接；不得输出 xxx、XXXX、占位符或自编链接。

当前推荐产品：
- 名称：{product.get('name', '未指定产品')}
- 类目：{product.get('category', '')}
- 价格：{product.get('price', '')}
- 链接：{product.get('link', '')}
- 卖点：{selling_points}
- 常见异议：{objections}

客户记忆：
- 阶段：{memory.get('stage', 'new')}
- 摘要：{memory.get('summary', '暂无')}

本轮意图：
- intent: {intent.get('intent', 'general')}
- confidence: {intent.get('confidence', 0)}
- reason: {intent.get('reason', '')}
""".strip()

    async def ensure_default_products(self) -> None:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_sales.SalesProduct).limit(1))
        if result.first() is not None:
            return
        for product in DEFAULT_SALES_PRODUCTS:
            try:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_sales.SalesProduct).values(product)
                )
            except sqlalchemy.exc.IntegrityError:
                continue

    async def ensure_catalog_products(self) -> None:
        await self.ensure_default_products()
        for product in YUANFUDAO_CATALOG_PRODUCTS:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_sales.SalesProduct).where(
                    persistence_sales.SalesProduct.uuid == product['uuid']
                )
            )
            row = result.first()
            if row is None:
                try:
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.insert(persistence_sales.SalesProduct).values(product)
                    )
                except sqlalchemy.exc.IntegrityError:
                    continue
                continue
            updates = {
                key: product[key]
                for key in ('product_line', 'profile_key', 'keywords', 'name', 'category', 'price', 'link', 'description')
                if product.get(key) and getattr(row, key, None) in (None, '', [])
            }
            if updates:
                updates['updated_at'] = datetime.datetime.now()
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(persistence_sales.SalesProduct)
                    .where(persistence_sales.SalesProduct.uuid == product['uuid'])
                    .values(**updates)
                )

    async def get_products(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        await self.ensure_catalog_products()
        query = sqlalchemy.select(persistence_sales.SalesProduct).order_by(persistence_sales.SalesProduct.created_at.desc())
        if enabled_only:
            query = query.where(persistence_sales.SalesProduct.enabled.is_(True))
        result = await self.ap.persistence_mgr.execute_async(query)
        return [self._serialize(persistence_sales.SalesProduct, row) for row in result.all()]

    async def get_product(self, product_uuid: str) -> dict[str, Any]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesProduct).where(
                persistence_sales.SalesProduct.uuid == product_uuid
            )
        )
        row = result.first()
        if row is None:
            raise ValueError('Product not found')
        return self._serialize(persistence_sales.SalesProduct, row)

    async def create_product(self, data: dict[str, Any]) -> str:
        name = str(data.get('name') or '').strip()
        if not name:
            raise ValueError('Product name is required')
        product = self._clean_product_payload(data)
        product['name'] = name
        product['uuid'] = data.get('uuid') or str(uuid.uuid4())
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_sales.SalesProduct).values(product))
        return product['uuid']

    async def update_product(self, product_uuid: str, data: dict[str, Any]) -> None:
        payload = self._clean_product_payload(data, partial=True)
        if 'name' in payload and not str(payload['name']).strip():
            raise ValueError('Product name is required')
        if not payload:
            return
        payload['updated_at'] = datetime.datetime.now()
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesProduct)
            .where(persistence_sales.SalesProduct.uuid == product_uuid)
            .values(**payload)
        )

    async def delete_product(self, product_uuid: str) -> None:
        existing = await self.get_product(product_uuid)
        if existing is None:
            raise ValueError('Product not found')
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_sales.SalesProduct).where(persistence_sales.SalesProduct.uuid == product_uuid)
        )

    async def prepare_query(self, query: Any) -> dict[str, Any]:
        text = query.variables.get('user_message_text', '') if getattr(query, 'variables', None) else ''
        if not text:
            return {'interrupted': False}

        if self.is_reset_command(text):
            return await self.reset_sales_session_context(query)

        existing_handoff = await self.get_open_handoff_for_query(query)
        if existing_handoff:
            reason = existing_handoff.get('reason') or '客户正在等待人工接入'
            await self.open_handoff_from_query(query, reason, text)
            return {
                'interrupted': True,
                'notice': '人工销售已接入中，请稍等。你的新消息已同步给人工。',
            }

        products = await self.get_products(enabled_only=True)
        product = self.select_best_product(text, products)
        intent = self.classify_intent(text)
        memory = await self.upsert_memory_from_query(query, text, intent, product)

        query.variables['sales_intent'] = intent
        if product:
            query.variables['sales_product_uuid'] = product.get('uuid', '')

        if intent.get('requires_handoff'):
            await self.open_handoff_from_query(query, intent.get('reason', '客户要求人工接入'), text)
            return {
                'interrupted': True,
                'notice': '已为你转接人工销售，请稍等。为了方便同事接手，我已经记录了你的需求和本轮对话重点。',
            }

        prompt_text = self.compose_sales_prompt(product, memory, intent)
        try:
            from langbot_plugin.api.entities.builtin.provider import message as provider_message

            query.prompt.messages.insert(0, provider_message.Message(role='system', content=prompt_text))
        except Exception:
            self.ap.logger.warning('Failed to inject sales prompt into query')

        return {'interrupted': False, 'intent': intent, 'product': product, 'memory': memory}

    async def reset_sales_session_context(self, query: Any) -> dict[str, Any]:
        session_ids = self._query_session_aliases(query)
        target_aliases = self._query_target_aliases(query)
        self._clear_runtime_conversation(query)

        if session_ids:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_monitoring.MonitoringFeedback).where(
                    persistence_monitoring.MonitoringFeedback.session_id.in_(session_ids)
                )
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_monitoring.MonitoringEmbeddingCall).where(
                    persistence_monitoring.MonitoringEmbeddingCall.session_id.in_(session_ids)
                )
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_monitoring.MonitoringLLMCall).where(
                    persistence_monitoring.MonitoringLLMCall.session_id.in_(session_ids)
                )
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_monitoring.MonitoringError).where(
                    persistence_monitoring.MonitoringError.session_id.in_(session_ids)
                )
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_monitoring.MonitoringMessage).where(
                    persistence_monitoring.MonitoringMessage.session_id.in_(session_ids)
                )
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_monitoring.MonitoringSession).where(
                    persistence_monitoring.MonitoringSession.session_id.in_(session_ids)
                )
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_sales.SalesCustomerMemory).where(
                    persistence_sales.SalesCustomerMemory.session_id.in_(session_ids)
                )
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_sales.SalesHandoff).where(
                    persistence_sales.SalesHandoff.session_id.in_(session_ids)
                )
            )

        for target_type, target_id in target_aliases:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_sales.SalesOutreachPlan)
                .where(persistence_sales.SalesOutreachPlan.target_type == target_type)
                .where(persistence_sales.SalesOutreachPlan.target_id == target_id)
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_sales.SalesResourceIssue)
                .where(persistence_sales.SalesResourceIssue.target_type == target_type)
                .where(persistence_sales.SalesResourceIssue.target_id == target_id)
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_sales.SalesHandoff)
                .where(persistence_sales.SalesHandoff.target_type == target_type)
                .where(persistence_sales.SalesHandoff.target_id == target_id)
            )

        return {
            'reset': True,
            'interrupted': True,
            'notice': '已重置当前会话，之前的聊天上下文和客户记忆已清空。请直接发送新的问题继续咨询。',
        }

    async def upsert_memory_from_query(
        self,
        query: Any,
        message_text: str,
        intent: dict[str, Any],
        product: dict[str, Any] | None,
    ) -> dict[str, Any]:
        session_id = self._query_session_id(query)
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory).where(
                persistence_sales.SalesCustomerMemory.session_id == session_id
            )
        )
        existing = result.first()
        stage = self._stage_for_intent(intent.get('intent', 'general'))
        summary = self._summarize_memory(existing.summary if existing else '', message_text, intent, product)
        intents = list(existing.intents if existing and existing.intents else [])
        intents.append(
            {
                'intent': intent.get('intent', 'general'),
                'confidence': intent.get('confidence', 0),
                'message': message_text[:200],
                'at': datetime.datetime.now().isoformat(),
            }
        )
        intents = intents[-20:]
        values = {
            'platform': getattr(query.launcher_type, 'value', str(query.launcher_type)),
            'user_id': str(query.sender_id),
            'summary': summary,
            'stage': stage,
            'last_intent': intent.get('intent', 'general'),
            'preferred_product_uuid': product.get('uuid', '') if product else '',
            'intents': intents,
            'last_seen_at': datetime.datetime.now(),
        }
        if existing:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_sales.SalesCustomerMemory)
                .where(persistence_sales.SalesCustomerMemory.id == existing.id)
                .values(**values)
            )
            memory_id = existing.id
        else:
            values['session_id'] = session_id
            await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_sales.SalesCustomerMemory).values(**values))
            memory_id = None

        return {'id': memory_id, 'session_id': session_id, **values}

    async def get_course_sales_explicit_rejection_count(self, session_id: str) -> int:
        if not session_id:
            return 0
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory).where(
                persistence_sales.SalesCustomerMemory.session_id == session_id
            )
        )
        existing = self._first_row(result)
        if existing is None:
            return 0
        profile = existing.profile if isinstance(existing.profile, dict) else {}
        try:
            return max(0, int(profile.get(COURSE_SALES_EXPLICIT_REJECTION_COUNT_KEY) or 0))
        except (TypeError, ValueError):
            return 0

    async def increment_course_sales_explicit_rejection_count(self, query: Any, session_id: str) -> int:
        if not session_id:
            return 1
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory).where(
                persistence_sales.SalesCustomerMemory.session_id == session_id
            )
        )
        existing = self._first_row(result)
        profile = dict(existing.profile or {}) if existing is not None else {}
        count = max(0, int(profile.get(COURSE_SALES_EXPLICIT_REJECTION_COUNT_KEY) or 0)) + 1
        profile[COURSE_SALES_EXPLICIT_REJECTION_COUNT_KEY] = count
        values: dict[str, Any] = {
            'profile': profile,
            'last_seen_at': datetime.datetime.now(),
            'updated_at': datetime.datetime.now(),
        }
        if existing is not None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_sales.SalesCustomerMemory)
                .where(persistence_sales.SalesCustomerMemory.id == existing.id)
                .values(**values)
            )
            return count

        launcher_type = getattr(query.launcher_type, 'value', str(getattr(query, 'launcher_type', '') or ''))
        values.update(
            {
                'session_id': session_id,
                'platform': launcher_type,
                'user_id': str(getattr(query, 'sender_id', '') or getattr(query, 'launcher_id', '') or ''),
                'stage': 'objection',
                'last_intent': 'explicit_rejection',
            }
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_sales.SalesCustomerMemory).values(**values)
        )
        return count

    async def ensure_memories_from_monitoring_sessions(self, limit: int = 200) -> None:
        """Create customer memories from real monitoring sessions when no sales plugin has written them."""
        memory_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory.session_id)
        )
        existing_session_ids = {
            self._row_value(row)
            for row in memory_result.all()
        }
        session_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringSession)
            .where(persistence_monitoring.MonitoringSession.message_count > 0)
            .order_by(persistence_monitoring.MonitoringSession.last_activity.desc())
            .limit(limit)
        )
        sessions = [self._row_value(row) for row in session_result.all()]
        products = await self.get_products(enabled_only=True)

        for session in sessions:
            session_id = getattr(session, 'session_id', '')
            if not session_id or session_id in existing_session_ids:
                continue
            values = await self._memory_values_from_monitoring_session(session, products)
            if not values:
                continue
            try:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_sales.SalesCustomerMemory).values(**values)
                )
                existing_session_ids.add(session_id)
            except sqlalchemy.exc.IntegrityError:
                existing_session_ids.add(session_id)

    async def get_memories(self) -> list[dict[str, Any]]:
        await self.ensure_memories_from_monitoring_sessions()
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory).order_by(
                persistence_sales.SalesCustomerMemory.updated_at.desc()
            )
        )
        return [self._serialize(persistence_sales.SalesCustomerMemory, row) for row in result.all()]

    async def update_memory(self, session_id: str, data: dict[str, Any]) -> dict[str, Any]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory).where(
                persistence_sales.SalesCustomerMemory.session_id == session_id
            )
        )
        existing = self._first_row(result)
        if existing is None:
            existing = await self._create_memory_from_monitoring_session(session_id)

        profile = dict(existing.profile or {})
        incoming_profile = data.get('profile')
        if isinstance(incoming_profile, dict):
            profile.update(incoming_profile)

        values: dict[str, Any] = {
            'profile': profile,
            'updated_at': datetime.datetime.now(),
        }
        if 'customer_name' in data:
            values['customer_name'] = str(data.get('customer_name') or '').strip()
        if 'stage' in data:
            values['stage'] = str(data.get('stage') or '').strip() or existing.stage
        if 'summary' in data:
            values['summary'] = str(data.get('summary') or '').strip()

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesCustomerMemory)
            .where(persistence_sales.SalesCustomerMemory.session_id == session_id)
            .values(**values)
        )

        updated_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory).where(
                persistence_sales.SalesCustomerMemory.session_id == session_id
            )
        )
        updated = self._first_row(updated_result)
        return self._serialize(persistence_sales.SalesCustomerMemory, updated)

    async def _create_memory_from_monitoring_session(self, session_id: str) -> Any:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringSession).where(
                persistence_monitoring.MonitoringSession.session_id == session_id
            )
        )
        session = self._first_row(result)
        if session is None:
            raise ValueError('Customer memory not found')
        products = await self.get_products(enabled_only=True)
        values = await self._memory_values_from_monitoring_session(session, products, allow_empty=True)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_sales.SalesCustomerMemory).values(**values)
        )
        created_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory).where(
                persistence_sales.SalesCustomerMemory.session_id == session_id
            )
        )
        return self._first_row(created_result)

    async def get_open_handoff_for_query(self, query: Any) -> dict[str, Any] | None:
        session_id = self._query_session_id(query)
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.session_id == session_id)
            .where(persistence_sales.SalesHandoff.status == 'open')
        )
        handoff = result.first()
        if handoff is None:
            return None
        return self._serialize_handoff(self._row_entity(handoff))

    async def open_handoff_from_query(self, query: Any, reason: str, message_text: str) -> dict[str, Any]:
        session_id = self._query_session_id(query)
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.session_id == session_id)
            .where(persistence_sales.SalesHandoff.status == 'open')
        )
        existing = self._first_row(result)
        reason_label = self.normalize_handoff_reason(reason)
        values = {
            'bot_uuid': query.bot_uuid or '',
            'target_type': getattr(query.launcher_type, 'value', str(query.launcher_type)),
            'target_id': str(query.launcher_id),
            'platform': query.adapter.__class__.__name__ if getattr(query, 'adapter', None) else '',
            'user_id': str(query.sender_id),
            'reason': reason_label or reason,
            'last_message': message_text,
            'updated_at': datetime.datetime.now(),
        }
        if existing:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_sales.SalesHandoff)
                .where(persistence_sales.SalesHandoff.id == existing.id)
                .values(**values)
            )
            return self._with_handoff_reason_label({'id': existing.id, 'session_id': session_id, **values})
        values['session_id'] = session_id
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_sales.SalesHandoff).values(**values))
        return self._with_handoff_reason_label({'session_id': session_id, **values})

    async def open_handoff_from_aggregated_messages(self, messages: list[Any], reason: str) -> dict[str, Any]:
        if not messages:
            raise ValueError('No messages to open handoff')
        first = messages[0]
        last_message = '\n'.join(str(getattr(message, 'message_chain', '') or '') for message in messages).strip()
        launcher_type = getattr(first, 'launcher_type', '')
        target_type = getattr(launcher_type, 'value', str(launcher_type))
        target_id = str(getattr(first, 'launcher_id', '') or '')
        session_id = f'{target_type}_{target_id}'
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.session_id == session_id)
            .where(persistence_sales.SalesHandoff.status == 'open')
        )
        existing = self._first_row(result)
        reason_label = self.normalize_handoff_reason(reason)
        values = {
            'bot_uuid': str(getattr(first, 'bot_uuid', '') or ''),
            'target_type': target_type,
            'target_id': target_id,
            'platform': first.adapter.__class__.__name__ if getattr(first, 'adapter', None) else '',
            'user_id': str(getattr(first, 'sender_id', '') or ''),
            'reason': reason_label or reason,
            'last_message': last_message,
            'updated_at': datetime.datetime.now(),
        }
        if existing:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_sales.SalesHandoff)
                .where(persistence_sales.SalesHandoff.id == existing.id)
                .values(**values)
            )
            return self._with_handoff_reason_label({'id': existing.id, 'session_id': session_id, **values})
        values['session_id'] = session_id
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_sales.SalesHandoff).values(**values))
        return self._with_handoff_reason_label({'session_id': session_id, **values})

    async def open_handoff_from_session(
        self,
        session_id: str,
        reason: str = '人工主动介入',
        assigned_to: str = '',
    ) -> dict[str, Any]:
        session_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringSession).where(
                persistence_monitoring.MonitoringSession.session_id == session_id
            )
        )
        session = self._first_row(session_result)
        if session is None:
            raise ValueError('Session not found')

        message_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.session_id == session_id)
            .where(
                sqlalchemy.or_(
                    persistence_monitoring.MonitoringMessage.role == 'user',
                    persistence_monitoring.MonitoringMessage.role.is_(None),
                )
            )
            .order_by(persistence_monitoring.MonitoringMessage.timestamp.desc())
            .limit(1)
        )
        latest_message = self._first_row(message_result)
        target_type, target_id = self._target_from_session(session)
        values = {
            'bot_uuid': getattr(session, 'bot_id', '') or '',
            'target_type': target_type,
            'target_id': target_id,
            'platform': getattr(session, 'platform', '') or '',
            'user_id': getattr(session, 'user_id', '') or target_id,
            'reason': self.normalize_handoff_reason(reason or '人工主动介入') or '人工主动介入',
            'last_message': getattr(latest_message, 'message_content', '') if latest_message else '',
            'assigned_to': assigned_to,
            'updated_at': datetime.datetime.now(),
        }

        existing_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.session_id == session_id)
            .where(persistence_sales.SalesHandoff.status == 'open')
        )
        existing = self._first_row(existing_result)
        if existing:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_sales.SalesHandoff)
                .where(persistence_sales.SalesHandoff.id == existing.id)
                .values(**values)
            )
            return self._with_handoff_reason_label({'id': existing.id, 'session_id': session_id, 'status': 'open', **values})

        values['status'] = 'open'
        values['session_id'] = session_id
        insert_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_sales.SalesHandoff).values(**values)
        )
        inserted_primary_key = getattr(insert_result, 'inserted_primary_key', None)
        if inserted_primary_key:
            values['id'] = int(inserted_primary_key[0])
        return self._with_handoff_reason_label(values)

    async def get_handoffs(self, status: str | None = None) -> list[dict[str, Any]]:
        query = sqlalchemy.select(persistence_sales.SalesHandoff).order_by(persistence_sales.SalesHandoff.updated_at.desc())
        if status:
            query = query.where(persistence_sales.SalesHandoff.status == status)
        result = await self.ap.persistence_mgr.execute_async(query)
        return [self._serialize_handoff(row) for row in result.all()]

    async def reply_handoff(self, handoff_id: int, reply: str, assigned_to: str = '') -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesHandoff).where(persistence_sales.SalesHandoff.id == handoff_id)
        )
        handoff = self._first_row(result)
        if handoff is None:
            raise ValueError('Handoff not found')
        if not handoff.bot_uuid or not handoff.target_id:
            raise ValueError('Handoff target is missing; cannot send manual reply')

        await self._send_operator_message(
            bot_uuid=handoff.bot_uuid,
            target_type=handoff.target_type,
            target_id=handoff.target_id,
            reply=reply,
        )
        await self._record_operator_monitoring_message(
            session_id=handoff.session_id,
            bot_id=handoff.bot_uuid,
            bot_name='',
            pipeline_id='',
            pipeline_name='',
            platform=handoff.platform,
            user_id=handoff.user_id,
            user_name='',
            reply=reply,
            assigned_to=assigned_to,
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.id == handoff_id)
            .values(status='open', operator_reply=reply, assigned_to=assigned_to, updated_at=datetime.datetime.now())
        )

    async def send_operator_message_from_session(
        self,
        session_id: str,
        reply: str,
        assigned_to: str = '',
        pause_ai: bool = False,
    ) -> dict[str, Any]:
        session_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringSession).where(
                persistence_monitoring.MonitoringSession.session_id == session_id
            )
        )
        session = self._first_row(session_result)
        if session is None:
            raise ValueError('Session not found')

        handoff_id: int | None = None
        if pause_ai:
            handoff = await self.open_handoff_from_session(session_id, '人工接入处理中', assigned_to)
            handoff_id = int(handoff['id']) if handoff.get('id') else None

        target_type, target_id = self._target_from_session(session)
        await self._send_operator_message(
            bot_uuid=getattr(session, 'bot_id', '') or '',
            target_type=target_type,
            target_id=target_id,
            reply=reply,
        )
        await self._record_operator_monitoring_message(
            session_id=getattr(session, 'session_id', '') or '',
            bot_id=getattr(session, 'bot_id', '') or '',
            bot_name=getattr(session, 'bot_name', '') or '',
            pipeline_id=getattr(session, 'pipeline_id', '') or '',
            pipeline_name=getattr(session, 'pipeline_name', '') or '',
            platform=getattr(session, 'platform', None),
            user_id=getattr(session, 'user_id', None),
            user_name=getattr(session, 'user_name', None),
            reply=reply,
            assigned_to=assigned_to,
        )
        return {'sent': True, 'handoff_id': handoff_id}

    async def _send_operator_message(self, bot_uuid: str, target_type: str, target_id: str, reply: str) -> None:
        if not bot_uuid or not target_id:
            raise ValueError('Handoff target is missing; cannot send manual reply')
        from langbot_plugin.api.entities.builtin.platform import message as platform_message

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None:
            raise ValueError(f'Bot {bot_uuid} is not running; cannot send manual reply')
        await runtime_bot.adapter.send_message(
            target_type,
            target_id,
            platform_message.MessageChain([platform_message.Plain(text=reply)]),
        )

    async def _record_operator_monitoring_message(
        self,
        *,
        session_id: str,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        platform: str | None,
        user_id: str | None,
        user_name: str | None,
        reply: str,
        assigned_to: str,
    ) -> None:
        monitoring_service = getattr(self.ap, 'monitoring_service', None)
        if monitoring_service is None:
            return
        message_content = json.dumps([{'type': 'Plain', 'text': reply}], ensure_ascii=False)
        variables = json.dumps({'sales_sender_kind': 'operator'}, ensure_ascii=False)
        await monitoring_service.record_message(
            bot_id=bot_id,
            bot_name=bot_name,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            message_content=message_content,
            session_id=session_id,
            status='success',
            level='info',
            platform=platform,
            user_id=user_id,
            user_name=user_name,
            runner_name=assigned_to or '人工销售',
            variables=variables,
            role='assistant',
        )

    async def restore_ai_hosting_from_session(self, session_id: str, assigned_to: str = '') -> dict[str, Any]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.session_id == session_id)
            .where(persistence_sales.SalesHandoff.status == 'open')
        )
        handoff = self._first_row(result)
        if handoff is None:
            return {'restored': True, 'handoff_id': None}
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.id == handoff.id)
            .values(status='ai_resumed', assigned_to=assigned_to or handoff.assigned_to, updated_at=datetime.datetime.now())
        )
        return {'restored': True, 'handoff_id': handoff.id}

    async def reply_handoff_from_session(
        self,
        session_id: str,
        reply: str,
        assigned_to: str = '',
    ) -> dict[str, Any]:
        handoff = await self.open_handoff_from_session(session_id, '人工直接回复', assigned_to)
        handoff_id = handoff.get('id')
        if not handoff_id:
            raise ValueError('Handoff id is missing; cannot send manual reply')
        await self.reply_handoff(int(handoff_id), reply, assigned_to)
        return {'sent': True, 'handoff_id': int(handoff_id)}

    async def create_resource_issue_from_session(self, session_id: str, data: dict[str, Any]) -> dict[str, Any]:
        session_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringSession).where(
                persistence_monitoring.MonitoringSession.session_id == session_id
            )
        )
        session = self._first_row(session_result)
        if session is None:
            raise ValueError('Session not found')

        target_type, target_id = self._target_from_session(session)
        payload = self._clean_resource_issue_payload(data)
        values = {
            **payload,
            'session_id': session_id,
            'bot_uuid': getattr(session, 'bot_id', '') or '',
            'pipeline_uuid': getattr(session, 'pipeline_id', '') or '',
            'target_type': target_type,
            'target_id': target_id,
            'platform': getattr(session, 'platform', '') or '',
            'user_id': getattr(session, 'user_id', '') or target_id,
            'user_name': getattr(session, 'user_name', '') or '',
            'status': 'open',
            'updated_at': datetime.datetime.now(),
        }
        insert_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_sales.SalesResourceIssue).values(**values)
        )
        inserted_primary_key = getattr(insert_result, 'inserted_primary_key', None)
        if inserted_primary_key:
            values['id'] = int(inserted_primary_key[0])
        return values

    async def create_resource_issue_from_query(self, query: Any, data: dict[str, Any]) -> dict[str, Any]:
        payload = self._clean_resource_issue_payload(data)
        session_id = self._query_session_id(query)
        values = {
            **payload,
            'session_id': session_id,
            'bot_uuid': getattr(query, 'bot_uuid', '') or '',
            'pipeline_uuid': getattr(query, 'pipeline_uuid', '') or '',
            'target_type': getattr(query.launcher_type, 'value', str(query.launcher_type)),
            'target_id': str(query.launcher_id),
            'platform': query.adapter.__class__.__name__ if getattr(query, 'adapter', None) else '',
            'user_id': str(getattr(query, 'sender_id', '') or ''),
            'user_name': '',
            'status': 'open',
            'updated_at': datetime.datetime.now(),
        }
        insert_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_sales.SalesResourceIssue).values(**values)
        )
        inserted_primary_key = getattr(insert_result, 'inserted_primary_key', None)
        if inserted_primary_key:
            values['id'] = int(inserted_primary_key[0])
        return values

    async def get_resource_issues(self, status: str | None = None) -> list[dict[str, Any]]:
        query = sqlalchemy.select(persistence_sales.SalesResourceIssue).order_by(
            persistence_sales.SalesResourceIssue.updated_at.desc(),
            persistence_sales.SalesResourceIssue.id.desc(),
        )
        if status:
            query = query.where(persistence_sales.SalesResourceIssue.status == status)
        result = await self.ap.persistence_mgr.execute_async(query)
        return [self._serialize(persistence_sales.SalesResourceIssue, row) for row in result.all()]

    async def resolve_resource_issue(self, issue_id: int, data: dict[str, Any]) -> dict[str, Any]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesResourceIssue).where(
                persistence_sales.SalesResourceIssue.id == issue_id
            )
        )
        issue = self._first_row(result)
        if issue is None:
            raise ValueError('Resource issue not found')

        now = datetime.datetime.now()
        payload = self._clean_resource_issue_update_payload(data)
        status = str(payload.get('status') or getattr(issue, 'status', '') or '').strip()
        if status in {'resolved', 'replied'} and getattr(issue, 'resolved_at', None) is None:
            payload['resolved_at'] = now
        payload['updated_at'] = now

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesResourceIssue)
            .where(persistence_sales.SalesResourceIssue.id == issue_id)
            .values(**payload)
        )

        if data.get('reply_user') and status in {'resolved', 'replied'}:
            reply = str(data.get('completion_reply') or '').strip()
            if not reply:
                reply = self._default_resource_issue_completion_reply(issue)
            await self._send_resource_issue_reply(issue, reply)
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_sales.SalesResourceIssue)
                .where(persistence_sales.SalesResourceIssue.id == issue_id)
                .values(status='replied', completion_reply=reply, replied_at=now, updated_at=now)
            )

        updated_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesResourceIssue).where(
                persistence_sales.SalesResourceIssue.id == issue_id
            )
        )
        updated = self._first_row(updated_result)
        return self._serialize(persistence_sales.SalesResourceIssue, updated)

    async def get_outreach_plans(self, kind: str = 'all') -> list[dict[str, Any]]:
        statement = sqlalchemy.select(persistence_sales.SalesOutreachPlan)
        condition = self._outreach_kind_condition(kind)
        if condition is not None:
            statement = statement.where(condition)
        result = await self.ap.persistence_mgr.execute_async(
            statement.order_by(persistence_sales.SalesOutreachPlan.created_at.desc())
        )
        return [self._serialize(persistence_sales.SalesOutreachPlan, row) for row in result.all()]

    async def get_followup_plans(self) -> list[dict[str, Any]]:
        return await self.get_outreach_plans(kind='followup')

    async def clear_scheduled_push_plans(self) -> int:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_sales.SalesOutreachPlan).where(
                self._outreach_kind_condition('scheduled_push')
            )
        )
        return int(getattr(result, 'rowcount', 0) or 0)

    async def count_outreach_plans_for_target_segments(
        self,
        *,
        bot_uuid: str,
        target_type: str,
        target_id: str,
        segments: list[str],
    ) -> int:
        if not bot_uuid or not target_id or not segments:
            return 0
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(persistence_sales.SalesOutreachPlan)
            .where(persistence_sales.SalesOutreachPlan.bot_uuid == bot_uuid)
            .where(persistence_sales.SalesOutreachPlan.target_type == (target_type or 'person'))
            .where(persistence_sales.SalesOutreachPlan.target_id == target_id)
            .where(persistence_sales.SalesOutreachPlan.segment.in_(segments))
        )
        return int(result.scalar() or 0)

    async def create_outreach_plan(self, data: dict[str, Any]) -> int:
        payload = self._clean_outreach_payload(data)
        dedupe_key = str(payload.get('dedupe_key') or '').strip()
        if dedupe_key:
            existing_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_sales.SalesOutreachPlan).where(
                    persistence_sales.SalesOutreachPlan.dedupe_key == dedupe_key
                )
            )
            existing = self._first_row(existing_result)
            if existing is not None:
                if getattr(existing, 'last_sent_at', None) is not None and getattr(existing, 'enabled', True) is False:
                    return int(existing.id)
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(persistence_sales.SalesOutreachPlan)
                    .where(persistence_sales.SalesOutreachPlan.id == existing.id)
                    .values(**payload, updated_at=datetime.datetime.now())
                )
                return int(existing.id)

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_sales.SalesOutreachPlan).values(**payload)
        )
        return int(result.inserted_primary_key[0]) if result.inserted_primary_key else 0

    async def _claim_due_outreach_plan(self, plan, now: datetime.datetime) -> bool:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesOutreachPlan)
            .where(persistence_sales.SalesOutreachPlan.id == plan.id)
            .where(persistence_sales.SalesOutreachPlan.enabled.is_(True))
            .where(persistence_sales.SalesOutreachPlan.scheduled_at <= now)
            .values(enabled=False, updated_at=now)
        )
        return getattr(result, 'rowcount', 1) != 0

    async def _restore_claimed_outreach_plan(self, plan, now: datetime.datetime) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesOutreachPlan)
            .where(persistence_sales.SalesOutreachPlan.id == plan.id)
            .values(enabled=True, updated_at=now)
        )

    async def _mark_outreach_plan_sent(self, plan, now: datetime.datetime) -> None:
        updates: dict[str, Any] = {'last_sent_at': now, 'updated_at': now}
        if plan.interval_minutes > 0:
            updates['scheduled_at'] = now + datetime.timedelta(minutes=plan.interval_minutes)
            updates['enabled'] = True
        else:
            updates['enabled'] = False
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesOutreachPlan)
            .where(persistence_sales.SalesOutreachPlan.id == plan.id)
            .values(**updates)
        )

    async def run_due_outreach_once(self, kind: str = 'all') -> int:
        now = datetime.datetime.now()
        statement = (
            sqlalchemy.select(persistence_sales.SalesOutreachPlan)
            .where(persistence_sales.SalesOutreachPlan.enabled.is_(True))
            .where(persistence_sales.SalesOutreachPlan.scheduled_at <= now)
        )
        condition = self._outreach_kind_condition(kind)
        if condition is not None:
            statement = statement.where(condition)
        result = await self.ap.persistence_mgr.execute_async(
            statement.order_by(
                persistence_sales.SalesOutreachPlan.scheduled_at.asc(),
                persistence_sales.SalesOutreachPlan.id.asc(),
            )
        )
        sent = 0
        products = {p['uuid']: p for p in await self.get_products(enabled_only=True)}
        for plan in result.all():
            if not plan.bot_uuid or not plan.target_id:
                continue
            product = products.get(plan.product_uuid, {})
            if not await self._claim_due_outreach_plan(plan, now):
                continue
            try:
                runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(plan.bot_uuid)
                if runtime_bot is None:
                    raise ValueError(f'Bot {plan.bot_uuid} is not running')
                await runtime_bot.adapter.send_message(
                    plan.target_type,
                    plan.target_id,
                    await self._build_outreach_message_chain(plan, product),
                )
            except Exception as e:
                await self._restore_claimed_outreach_plan(plan, now)
                self.ap.logger.warning(f'Sales outreach plan {plan.id} failed: {e}')
                continue

            await self._mark_outreach_plan_sent(plan, now)
            sent += 1
        return sent

    async def run_due_scheduled_push_once(self) -> int:
        return await self.run_due_outreach_once(kind='scheduled_push')

    async def run_due_followup_once(self) -> int:
        return await self.run_due_outreach_once(kind='followup')

    async def run_due_outreach_for_target(
        self,
        *,
        bot_uuid: str,
        target_type: str,
        target_id: str,
    ) -> int:
        now = datetime.datetime.now()
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesOutreachPlan)
            .where(persistence_sales.SalesOutreachPlan.enabled.is_(True))
            .where(persistence_sales.SalesOutreachPlan.scheduled_at <= now)
            .where(persistence_sales.SalesOutreachPlan.bot_uuid == bot_uuid)
            .where(persistence_sales.SalesOutreachPlan.target_type == (target_type or 'person'))
            .where(persistence_sales.SalesOutreachPlan.target_id == target_id)
            .order_by(persistence_sales.SalesOutreachPlan.scheduled_at.asc(), persistence_sales.SalesOutreachPlan.id.asc())
        )
        sent = 0
        products = {p['uuid']: p for p in await self.get_products(enabled_only=True)}
        for plan in result.all():
            if not plan.bot_uuid or not plan.target_id:
                continue
            product = products.get(plan.product_uuid, {})
            if not await self._claim_due_outreach_plan(plan, now):
                continue
            try:
                runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(plan.bot_uuid)
                if runtime_bot is None:
                    raise ValueError(f'Bot {plan.bot_uuid} is not running')
                await runtime_bot.adapter.send_message(
                    plan.target_type,
                    plan.target_id,
                    await self._build_outreach_message_chain(plan, product),
                )
            except Exception as e:
                await self._restore_claimed_outreach_plan(plan, now)
                self.ap.logger.warning(f'Sales outreach plan {plan.id} failed: {e}')
                continue

            await self._mark_outreach_plan_sent(plan, now)
            sent += 1
        return sent

    def build_radar_tracking_url(
        self,
        *,
        destination_url: str,
        bot_uuid: str,
        target_type: str,
        target_id: str,
        link_id: str = '',
        session_id: str = '',
        pipeline_uuid: str = '',
        event: str = 'link_open',
        tracking_base_path: str = '/api/v1/sales/radar/click',
    ) -> str:
        payload = {
            'd': destination_url,
            'b': bot_uuid,
            't': target_type or 'person',
            'i': target_id,
            'l': link_id,
            's': session_id,
            'p': pipeline_uuid,
            'e': event,
            'exp': int((datetime.datetime.now() + datetime.timedelta(days=30)).timestamp()),
        }
        token = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode('utf-8')).decode('utf-8').rstrip('=')
        base_url = self.radar_tracking_public_base_url().rstrip('/')
        path = tracking_base_path.rstrip('/')
        return f'{base_url}{path}/{token}'

    def radar_tracking_public_base_url(self) -> str:
        cfg_mgr = getattr(self.ap, 'instance_config', None)
        if isinstance(cfg_mgr, dict):
            instance_config = cfg_mgr
        else:
            instance_config = cfg_mgr.data if cfg_mgr is not None and hasattr(cfg_mgr, 'data') else {}
        sales_cfg = instance_config.get('sales') if isinstance(instance_config.get('sales'), dict) else {}
        api_cfg = instance_config.get('api') if isinstance(instance_config.get('api'), dict) else {}
        for candidate in (
            sales_cfg.get('radar_public_base_url'),
            api_cfg.get('public_base_url'),
            api_cfg.get('webhook_prefix'),
            os.getenv('LANGBOT_RADAR_PUBLIC_BASE_URL'),
        ):
            value = str(candidate or '').strip()
            if value:
                return value.rstrip('/')
        host = str(api_cfg.get('host') or '127.0.0.1')
        port = int(api_cfg.get('port') or 5300)
        if host in {'0.0.0.0', '::'}:
            host = '127.0.0.1'
        return f'http://{host}:{port}'

    def decode_radar_tracking_token(self, token: str) -> dict[str, Any]:
        padding = '=' * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(f'{token}{padding}')
        payload = json.loads(raw.decode('utf-8'))
        if not isinstance(payload, dict):
            raise ValueError('Invalid radar tracking token')
        expires_at = int(payload.get('exp') or 0)
        if expires_at and datetime.datetime.now().timestamp() > expires_at:
            raise ValueError('Radar tracking token expired')
        destination = str(payload.get('d') or '').strip()
        if not destination:
            raise ValueError('Radar tracking destination missing')
        return payload

    async def handle_radar_tracking_click(self, token: str) -> str:
        payload = self.decode_radar_tracking_token(token)
        destination_url = str(payload.get('d') or '')
        bot_uuid = str(payload.get('b') or '')
        target_type = str(payload.get('t') or 'person')
        target_id = str(payload.get('i') or '')
        link_id = str(payload.get('l') or '')
        session_id = str(payload.get('s') or '')
        pipeline_uuid = str(payload.get('p') or '')
        event = str(payload.get('e') or 'link_open')

        task_assistant = getattr(self.ap, 'task_assistant_service', None)
        if task_assistant is not None and bot_uuid and target_id:
            try:
                await task_assistant.handle_course_sales_radar_event(
                    bot_uuid=bot_uuid,
                    target_type=target_type,
                    target_id=target_id,
                    link_id=link_id,
                    session_id=session_id,
                    pipeline_uuid=pipeline_uuid,
                    event=event,
                )
            except Exception as exc:
                self.ap.logger.warning('Failed to handle radar tracking click: %s', exc)

        return destination_url

    async def get_chatted_outreach_targets(
        self,
        *,
        bot_uuid: str = '',
        pipeline_uuids: list[str] | None = None,
    ) -> list[dict[str, str]]:
        message_exists = (
            sqlalchemy.select(persistence_monitoring.MonitoringMessage.id)
            .where(persistence_monitoring.MonitoringMessage.session_id == persistence_monitoring.MonitoringSession.session_id)
            .where(
                sqlalchemy.or_(
                    persistence_monitoring.MonitoringMessage.role == 'user',
                    persistence_monitoring.MonitoringMessage.role.is_(None),
                )
            )
            .exists()
        )
        statement = sqlalchemy.select(persistence_monitoring.MonitoringSession).where(message_exists)
        if bot_uuid:
            statement = statement.where(persistence_monitoring.MonitoringSession.bot_id == bot_uuid)
        if pipeline_uuids:
            statement = statement.where(persistence_monitoring.MonitoringSession.pipeline_id.in_(pipeline_uuids))
        statement = statement.order_by(persistence_monitoring.MonitoringSession.last_activity.desc())

        result = await self.ap.persistence_mgr.execute_async(statement)
        targets: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for session in result.all():
            target_type, target_id = self._target_from_session(session)
            bot_id = str(getattr(session, 'bot_id', '') or '')
            if not bot_id or not target_id:
                continue
            key = (bot_id, target_type, target_id)
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                {
                    'bot_uuid': bot_id,
                    'target_type': target_type,
                    'target_id': target_id,
                    'session_id': str(getattr(session, 'session_id', '') or ''),
                    'pipeline_uuid': str(getattr(session, 'pipeline_id', '') or ''),
                    'user_id': str(getattr(session, 'user_id', '') or target_id),
                }
            )
        return targets

    async def count_user_messages_for_session(self, session_id: str) -> int:
        if not session_id:
            return 0
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringMessage.id))
            .where(persistence_monitoring.MonitoringMessage.session_id == session_id)
            .where(
                sqlalchemy.or_(
                    persistence_monitoring.MonitoringMessage.role == 'user',
                    persistence_monitoring.MonitoringMessage.role.is_(None),
                )
            )
        )
        return int(result.scalar() or 0)

    async def disable_outreach_for_target(
        self,
        *,
        bot_uuid: str,
        target_type: str,
        target_id: str,
        segment_prefixes: list[str] | None = None,
    ) -> None:
        if not bot_uuid or not target_id:
            return
        statement = (
            sqlalchemy.update(persistence_sales.SalesOutreachPlan)
            .where(persistence_sales.SalesOutreachPlan.bot_uuid == bot_uuid)
            .where(persistence_sales.SalesOutreachPlan.target_type == (target_type or 'person'))
            .where(persistence_sales.SalesOutreachPlan.target_id == target_id)
            .where(persistence_sales.SalesOutreachPlan.enabled.is_(True))
        )
        prefixes = [prefix for prefix in (segment_prefixes or []) if prefix]
        if prefixes:
            statement = statement.where(
                sqlalchemy.or_(
                    *[persistence_sales.SalesOutreachPlan.segment.like(f'{prefix}%') for prefix in prefixes]
                )
            )
        await self.ap.persistence_mgr.execute_async(
            statement.values(enabled=False, updated_at=datetime.datetime.now())
        )

    async def get_overview(self) -> dict[str, Any]:
        products = await self.get_products()
        memories = await self.get_memories()
        handoffs = await self.get_handoffs(status='open')
        outreach = await self.get_outreach_plans(kind='scheduled_push')
        followups = await self.get_followup_plans()
        return {
            'products_count': len(products),
            'customers_count': len(memories),
            'open_handoffs_count': len(handoffs),
            'outreach_plans_count': len(outreach),
            'scheduled_push_plans_count': len(outreach),
            'followup_plans_count': len(followups),
            'products': products[:5],
            'recent_memories': memories[:5],
            'open_handoffs': handoffs[:5],
            'outreach_plans': outreach[:5],
            'followup_plans': followups[:5],
        }

    def _serialize(self, model, row: Any) -> dict[str, Any]:
        try:
            return self.ap.persistence_mgr.serialize_model(model, row)
        except (AttributeError, KeyError):
            return self.ap.persistence_mgr.serialize_model(model, self._row_value(row))

    def _serialize_handoff(self, row: Any) -> dict[str, Any]:
        return self._with_handoff_reason_label(self._serialize(persistence_sales.SalesHandoff, row))

    def _with_handoff_reason_label(self, handoff: dict[str, Any]) -> dict[str, Any]:
        payload = dict(handoff)
        payload['reason_label'] = self.normalize_handoff_reason(payload.get('reason', ''))
        return payload

    def _clean_product_payload(self, data: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        fields = {
            'name',
            'product_line',
            'profile_key',
            'keywords',
            'category',
            'price',
            'link',
            'description',
            'selling_points',
            'pain_points',
            'objections',
            'audience',
            'enabled',
        }
        payload = {k: data[k] for k in fields if k in data}
        for key in ('selling_points', 'pain_points', 'objections', 'audience', 'keywords'):
            if key in payload:
                payload[key] = self._to_list(payload[key])
        if not partial:
            payload.setdefault('name', '未命名产品')
            payload.setdefault('product_line', '')
            payload.setdefault('profile_key', '')
            payload.setdefault('keywords', [])
            payload.setdefault('category', '')
            payload.setdefault('price', '')
            payload.setdefault('link', '')
            payload.setdefault('description', '')
            payload.setdefault('selling_points', [])
            payload.setdefault('pain_points', [])
            payload.setdefault('objections', [])
            payload.setdefault('audience', [])
            payload.setdefault('enabled', True)
        return payload

    def _clean_resource_issue_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        issue_type = self._normalize_resource_issue_type(data.get('issue_type') or data.get('type'))
        user_description = str(data.get('user_description') or data.get('description') or '').strip()
        question_location = str(data.get('question_location') or '').strip()
        issue_summary = str(data.get('issue_summary') or '').strip()
        if not issue_summary:
            issue_summary = self._build_resource_issue_summary(
                issue_type=issue_type,
                question_location=question_location,
                user_description=user_description,
            )
        return {
            'issue_type': issue_type,
            'book_id': str(data.get('book_id') or data.get('book_number') or '').strip(),
            'merchant': str(data.get('merchant') or '').strip(),
            'question_location': question_location,
            'issue_summary': issue_summary,
            'user_description': user_description,
            'evidence_images': self._to_list(data.get('evidence_images') or data.get('images')),
            'internal_note': str(data.get('internal_note') or '').strip(),
            'operator': str(data.get('operator') or '').strip(),
            'resolution_note': '',
            'completion_reply': '',
        }

    def _clean_resource_issue_update_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        allowed_fields = {
            'status',
            'issue_type',
            'book_id',
            'merchant',
            'question_location',
            'issue_summary',
            'user_description',
            'evidence_images',
            'internal_note',
            'operator',
            'resolution_note',
            'completion_reply',
        }
        payload = {key: data[key] for key in allowed_fields if key in data}
        if 'issue_type' in payload:
            payload['issue_type'] = self._normalize_resource_issue_type(payload['issue_type'])
        if 'status' in payload:
            payload['status'] = self._normalize_resource_issue_status(payload['status'])
        if 'evidence_images' in payload:
            payload['evidence_images'] = self._to_list(payload['evidence_images'])
        for key in payload:
            if key != 'evidence_images':
                payload[key] = str(payload[key] or '').strip()
        return payload

    def _normalize_resource_issue_type(self, value: Any) -> str:
        text = str(value or '').strip().lower()
        if text == 'uploading':
            return 'resource_uploading'
        if text in {'content_error', 'missing_resource', 'empty_resource', 'resource_uploading', 'resource_error'}:
            return text
        if any(keyword in text for keyword in ['缺失', '暂无', '没有资源', 'missing']):
            return 'missing_resource'
        if any(keyword in text for keyword in ['为空', '空白', 'empty']):
            return 'empty_resource'
        if any(keyword in text for keyword in ['上传', '更新', 'upload']):
            return 'resource_uploading'
        if any(keyword in text for keyword in ['错', '不对', '不匹配', '音频', '答案']):
            return 'content_error'
        return 'resource_error'

    def _normalize_resource_issue_status(self, value: Any) -> str:
        status = str(value or '').strip().lower()
        return status if status in {'open', 'reported', 'resolved', 'replied', 'closed'} else 'open'

    def _build_resource_issue_summary(
        self,
        *,
        issue_type: str,
        question_location: str = '',
        user_description: str = '',
    ) -> str:
        type_labels = {
            'content_error': '资源内容错误',
            'missing_resource': '资源缺失',
            'empty_resource': '资源为空',
            'resource_uploading': '资源正在上传中',
            'resource_error': '资源有问题',
        }
        parts = [type_labels.get(issue_type, '资源有问题')]
        if question_location:
            parts.append(question_location)
        if user_description:
            parts.append(user_description)
        return '：'.join(parts)

    def _default_resource_issue_completion_reply(self, issue: Any) -> str:
        book_id = getattr(issue, 'book_id', '') or ''
        prefix = f'您反馈的图书资源问题（书籍编号：{book_id}）' if book_id else '您反馈的图书资源问题'
        return f'您好，{prefix}已经处理好了，可以再打开试一下哈。'

    async def _send_resource_issue_reply(self, issue: Any, reply: str) -> None:
        if not getattr(issue, 'bot_uuid', '') or not getattr(issue, 'target_id', ''):
            raise ValueError('Resource issue target is missing; cannot send completion reply')

        from langbot_plugin.api.entities.builtin.platform import message as platform_message

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(issue.bot_uuid)
        if runtime_bot is None:
            raise ValueError(f'Bot {issue.bot_uuid} is not running; cannot send completion reply')
        await runtime_bot.adapter.send_message(
            issue.target_type or 'person',
            issue.target_id,
            platform_message.MessageChain([platform_message.Plain(text=reply)]),
        )

    def _clean_outreach_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        scheduled_at = data.get('scheduled_at')
        if isinstance(scheduled_at, str) and scheduled_at:
            scheduled_at = datetime.datetime.fromisoformat(scheduled_at.replace('Z', '+00:00')).replace(tzinfo=None)
        elif not scheduled_at:
            scheduled_at = datetime.datetime.now()
        message_components = self._normalize_message_components(data.get('message_components'))
        return {
            'name': data.get('name') or '产品触达计划',
            'product_uuid': data.get('product_uuid', ''),
            'bot_uuid': data.get('bot_uuid', ''),
            'target_type': data.get('target_type', 'person'),
            'target_id': data.get('target_id', ''),
            'segment': data.get('segment', ''),
            'dedupe_key': data.get('dedupe_key', ''),
            'message_template': data.get('message_template', ''),
            'message_components': message_components,
            'scheduled_at': scheduled_at,
            'interval_minutes': int(data.get('interval_minutes') or 0),
            'enabled': bool(data.get('enabled', True)),
        }

    def _outreach_kind_condition(self, kind: str | None):
        normalized = str(kind or 'all').strip().lower()
        if normalized in {'', 'all'}:
            return None
        if normalized in {'scheduled', 'scheduled_push', 'broadcast', 'push'}:
            return persistence_sales.SalesOutreachPlan.segment.in_(SCHEDULED_PUSH_OUTREACH_SEGMENTS)
        if normalized in {'followup', 'followups'}:
            return sqlalchemy.or_(
                *[
                    persistence_sales.SalesOutreachPlan.segment.like(f'{prefix}%')
                    for prefix in FOLLOWUP_OUTREACH_SEGMENT_PREFIXES
                ]
            )
        return None

    def _normalize_message_components(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            component_type = str(item.get('type') or '').strip().lower()
            if component_type == 'plain':
                text = str(item.get('text') or '')
                if text:
                    normalized.append({'type': 'plain', 'text': text})
            elif component_type == 'image':
                file_key = str(item.get('file_key') or item.get('path') or '').strip()
                image_url = str(item.get('image_url') or item.get('url') or '').strip()
                if file_key or image_url:
                    normalized.append({'type': 'image', 'file_key': file_key, 'image_url': image_url})
            elif component_type in {'link', 'wechat_link'}:
                url = str(item.get('url') or item.get('link_url') or '').strip()
                if not url:
                    continue
                normalized.append(
                    {
                        'type': 'link',
                        'title': str(item.get('title') or item.get('link_title') or '查看链接'),
                        'description': str(item.get('description') or item.get('link_desc') or ''),
                        'url': url,
                        'thumb_url': str(item.get('thumb_url') or item.get('link_thumb_url') or ''),
                        'include_text_fallback': item.get('include_text_fallback') is not False,
                    }
                )
        return normalized

    async def _build_outreach_message_chain(self, plan: Any, product: dict[str, Any]):
        from langbot_plugin.api.entities.builtin.platform import message as platform_message

        components_data = getattr(plan, 'message_components', None)
        components_data = components_data if isinstance(components_data, list) else []
        rendered_components = await self._render_message_components(components_data)
        if not rendered_components:
            message = self._render_outreach_message(getattr(plan, 'message_template', ''), product)
            rendered_components = [platform_message.Plain(text=message)]
        return platform_message.MessageChain(rendered_components)

    async def _render_message_components(self, components_data: list[dict[str, Any]]):
        from langbot_plugin.api.entities.builtin.platform import message as platform_message

        rendered = []
        for component in self._normalize_message_components(components_data):
            component_type = component.get('type')
            if component_type == 'plain':
                rendered.append(platform_message.Plain(text=component['text']))
            elif component_type == 'image':
                rendered.append(await self._image_component(component.get('file_key', ''), component.get('image_url', '')))
            elif component_type == 'link':
                if component.get('include_text_fallback') is not False:
                    rendered.append(platform_message.Plain(text=f"{component['title']}\n{component['url']}"))
                rendered.append(
                    platform_message.WeChatLink(
                        link_title=component['title'],
                        link_desc=component.get('description', ''),
                        link_url=component['url'],
                        link_thumb_url=component.get('thumb_url', ''),
                    )
                )
        return rendered

    async def _image_component(self, file_key: str, image_url: str):
        from langbot_plugin.api.entities.builtin.platform import message as platform_message

        if image_url:
            return platform_message.Image(url=image_url)

        storage_mgr = getattr(self.ap, 'storage_mgr', None)
        storage_provider = getattr(storage_mgr, 'storage_provider', None) if storage_mgr is not None else None
        if storage_provider is not None and file_key:
            try:
                file_content = await storage_provider.load(file_key)
                mime_type = mimetypes.guess_type(file_key)[0] or 'image/png'
                image_base64 = base64.b64encode(file_content).decode('utf-8')
                return platform_message.Image(base64=f'data:{mime_type};base64,{image_base64}')
            except Exception as exc:
                logger = getattr(self.ap, 'logger', None)
                if logger is not None:
                    logger.warning('Failed to load sales outreach image %s from storage: %s', file_key, exc)

        return platform_message.Image(path=file_key)

    def _render_outreach_message(self, template: str, product: dict[str, Any]) -> str:
        if not template:
            template = '给你推荐一个可能适合的方案：{product_name}。核心卖点：{selling_points}。详情：{link}'
        return (
            template.replace('{product_name}', product.get('name', '产品'))
            .replace('{selling_points}', '、'.join(self._to_list(product.get('selling_points'))[:3]))
            .replace('{link}', product.get('link', ''))
            .replace('{price}', product.get('price', ''))
        )

    async def _memory_values_from_monitoring_session(
        self,
        session: Any,
        products: list[dict[str, Any]],
        allow_empty: bool = False,
    ) -> dict[str, Any] | None:
        session_id = getattr(session, 'session_id', '') or ''
        messages = await self._recent_user_messages_for_session(session_id)
        texts = [self._message_content_text(getattr(message, 'message_content', '')) for message in messages]
        texts = [text for text in texts if text]
        if not texts and not allow_empty:
            return None

        conversation_text = '\n'.join(texts[-8:])
        intent = self.classify_intent(conversation_text)
        product = self.select_best_product(conversation_text, products) if conversation_text else None
        profile = self._extract_customer_profile(conversation_text)
        summary = self._summarize_session_memory(conversation_text, intent, product, profile)
        now = datetime.datetime.now()
        return {
            'session_id': session_id,
            'platform': getattr(session, 'platform', '') or '',
            'user_id': getattr(session, 'user_id', '') or '',
            'customer_name': self._customer_name_from_session(session),
            'summary': summary,
            'stage': self._stage_for_intent(intent.get('intent', 'general')),
            'last_intent': intent.get('intent', 'general'),
            'preferred_product_uuid': product.get('uuid', '') if product else '',
            'profile': profile,
            'intents': [
                {
                    'intent': intent.get('intent', 'general'),
                    'confidence': intent.get('confidence', 0),
                    'message': conversation_text[-200:],
                    'at': now.isoformat(),
                    'source': 'monitoring_session',
                }
            ],
            'last_seen_at': getattr(session, 'last_activity', None) or now,
            'updated_at': now,
        }

    async def _recent_user_messages_for_session(self, session_id: str) -> list[Any]:
        if not session_id:
            return []
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.session_id == session_id)
            .where(
                sqlalchemy.or_(
                    persistence_monitoring.MonitoringMessage.role == 'user',
                    persistence_monitoring.MonitoringMessage.role.is_(None),
                )
            )
            .order_by(persistence_monitoring.MonitoringMessage.timestamp.desc())
            .limit(20)
        )
        rows = [self._row_value(row) for row in result.all()]
        return list(reversed(rows))

    def _message_content_text(self, content: str) -> str:
        if not content:
            return ''
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return str(content).strip()
        if not isinstance(parsed, list):
            return str(content).strip()

        parts: list[str] = []
        for component in parsed:
            if not isinstance(component, dict):
                continue
            component_type = component.get('type')
            if component_type == 'Plain':
                parts.append(str(component.get('text') or ''))
            elif component_type == 'At':
                target = component.get('display') or component.get('target') or ''
                if target:
                    parts.append(f'@{target}')
            elif component_type == 'AtAll':
                parts.append('@All')
            elif component_type == 'Image':
                parts.append('[图片]')
            elif component_type == 'File':
                name = component.get('name') or '文件'
                parts.append(f'[文件: {name}]')
            elif component_type == 'Voice':
                length = component.get('length') or ''
                parts.append(f'[语音{f" {length}s" if length else ""}]')
            elif component_type == 'Quote':
                parts.append(self._message_content_text(json.dumps(component.get('origin') or [])))
        return ''.join(parts).strip()

    def _extract_customer_profile(self, text: str) -> dict[str, Any]:
        profile: dict[str, Any] = {}
        phone_match = re.search(r'(?<!\d)(1[3-9]\d{9})(?!\d)', text)
        if phone_match:
            profile['phone'] = phone_match.group(1)
        email_match = re.search(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', text)
        if email_match:
            profile['email'] = email_match.group(0)
        wechat_match = re.search(r'(?:微信号?|wechat|wx)[:：\s]*([A-Za-z][A-Za-z0-9_-]{4,})', text, re.I)
        if wechat_match:
            profile['wechat'] = wechat_match.group(1)
        grade_match = re.search(r'(幼儿园|小班|中班|大班|[一二三四五六七八九1-9]年级|初[一二三]|高[一二三])', text)
        if grade_match:
            profile['child_grade'] = grade_match.group(1)

        needs = []
        need_rules = [
            ('期末复习资料', ['期末', '复习', '资料']),
            ('自然拼读/英语启蒙', ['自然拼读', '拼读', '英语', '发音', '单词']),
            ('阅读写作提升', ['阅读', '作文', '写作']),
            ('数学思维提升', ['数学', '思维', '应用题', '粗心', '马虎']),
        ]
        for label, keywords in need_rules:
            if any(keyword in text for keyword in keywords):
                needs.append(label)
        if needs:
            profile['needs'] = '、'.join(dict.fromkeys(needs))
        return profile

    def _summarize_session_memory(
        self,
        conversation_text: str,
        intent: dict[str, Any],
        product: dict[str, Any] | None,
        profile: dict[str, Any],
    ) -> str:
        if not conversation_text:
            return ''
        facts = []
        if profile.get('child_grade'):
            facts.append(f"孩子年级：{profile['child_grade']}")
        if profile.get('needs'):
            facts.append(f"关注需求：{profile['needs']}")
        if product:
            facts.append(f"关联产品：{product.get('name', '')}")
        facts.append(f"最近意图：{intent.get('intent', 'general')}")
        facts.append(f"客户原话：{conversation_text[-240:]}")
        return '；'.join(item for item in facts if item)

    def _customer_name_from_session(self, session: Any) -> str:
        user_name = getattr(session, 'user_name', '') or ''
        if user_name and not self._is_technical_identifier(user_name):
            return user_name
        platform = getattr(session, 'platform', '') or ''
        if platform == 'group':
            return '群聊客户'
        if platform == 'person':
            return '私聊客户'
        return '客户'

    def _customer_name_from_message(self, message: Any) -> str:
        user_name = getattr(message, 'user_name', '') or ''
        if user_name and not self._is_technical_identifier(user_name):
            return user_name
        platform = getattr(message, 'platform', '') or ''
        if platform == 'group':
            return '群聊客户'
        if platform == 'person':
            return '私聊客户'
        return '客户'

    def _is_technical_identifier(self, value: str) -> bool:
        text = str(value or '').strip()
        if not text:
            return True
        return (
            'LauncherTypes.' in text
            or re.match(r'^(on|om|ou|oc|of)_[A-Za-z0-9_-]{12,}$', text) is not None
            or re.match(r'^[A-Za-z]+Types\.[A-Z_]+_', text) is not None
        )

    def normalize_sales_message_content(self, message_content: str) -> dict[str, Any]:
        components: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        raw_content = message_content or ''
        try:
            parsed = json.loads(raw_content)
        except (TypeError, json.JSONDecodeError):
            parsed = [{'type': 'Plain', 'text': raw_content}] if raw_content else []

        if not isinstance(parsed, list):
            parsed = [{'type': 'Plain', 'text': raw_content}]

        for item in parsed:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_sales_message_component(item)
            if normalized is None:
                source_id = item.get('id')
                if item.get('type') == 'Source' and source_id:
                    metadata['source'] = {key: value for key, value in item.items() if key != 'type'}
                continue
            components.append(normalized)

        return {
            'components': components,
            'preview': self._sales_message_preview(components),
            'metadata': metadata,
        }

    def _normalize_sales_message_component(self, component: dict[str, Any]) -> dict[str, Any] | None:
        component_type = str(component.get('type') or '').strip()
        if component_type == 'Source':
            return None
        if component_type == 'Plain':
            return {
                'kind': 'text',
                'text': str(component.get('text') or ''),
                'raw': component,
            }
        if component_type in ('At', 'AtAll'):
            label = component.get('display') or component.get('target') or 'All'
            return {'kind': 'text', 'text': f'@{label}', 'raw': component}
        if component_type == 'Image':
            url = str(
                component.get('url')
                or component.get('image_url')
                or component.get('file_url')
                or component.get('download_url')
                or ''
            )
            base64_data = str(
                component.get('base64')
                or component.get('data')
                or component.get('image_base64')
                or ''
            )
            path = str(component.get('path') or '')
            return {
                'kind': 'image',
                'url': url,
                'base64': base64_data,
                'path': path,
                'name': str(component.get('name') or component.get('file_name') or ''),
                'available': bool(url or base64_data or path),
                'raw': component,
            }
        if component_type == 'Voice':
            url = str(
                component.get('url')
                or component.get('voice_url')
                or component.get('audio_url')
                or component.get('file_url')
                or component.get('download_url')
                or ''
            )
            base64_data = str(
                component.get('base64')
                or component.get('data')
                or component.get('audio_base64')
                or component.get('voice_base64')
                or ''
            )
            path = str(component.get('path') or '')
            return {
                'kind': 'voice',
                'url': url,
                'base64': base64_data,
                'path': path,
                'length': component.get('length') or component.get('duration') or 0,
                'available': bool(url or base64_data or path),
                'raw': component,
            }
        if component_type == 'File':
            return {
                'kind': 'file',
                'name': str(component.get('name') or component.get('file_name') or '文件'),
                'url': str(component.get('url') or ''),
                'path': str(component.get('path') or ''),
                'available': bool(component.get('url') or component.get('path')),
                'raw': component,
            }
        if component_type in ('WeChatLink', 'Link'):
            return {
                'kind': 'link',
                'title': str(component.get('title') or component.get('name') or '链接'),
                'description': str(component.get('description') or ''),
                'url': str(component.get('url') or component.get('link_url') or ''),
                'thumb_url': str(component.get('thumb_url') or component.get('image') or ''),
                'raw': component,
            }
        if component_type == 'Quote':
            origin = component.get('origin') if isinstance(component.get('origin'), list) else []
            quoted = []
            for origin_item in origin:
                if isinstance(origin_item, dict) and origin_item.get('type') == 'Plain':
                    quoted.append(str(origin_item.get('text') or ''))
            return {'kind': 'quote', 'text': '\n'.join(quoted), 'raw': component}
        return {
            'kind': 'attachment',
            'type': component_type or 'Unknown',
            'label': f'[{component_type or "Unknown"}]',
            'raw': component,
        }

    def _sales_message_preview(self, components: list[dict[str, Any]]) -> str:
        labels = []
        for component in components:
            kind = component.get('kind')
            if kind == 'text':
                text = str(component.get('text') or '').strip()
                if text:
                    labels.append(text)
            elif kind == 'image':
                labels.append('[图片]')
            elif kind == 'voice':
                labels.append('[语音]')
            elif kind == 'file':
                labels.append(f"[文件] {component.get('name') or ''}".strip())
            elif kind == 'link':
                labels.append(f"[链接] {component.get('title') or ''}".strip())
            elif kind == 'quote':
                labels.append('[引用]')
            else:
                labels.append(str(component.get('label') or '[附件]'))
        return ' '.join(label for label in labels if label).strip()

    def _normalized_handoff_status(self, handoff: Any | None) -> str:
        if handoff is None or getattr(handoff, 'status', '') != 'open':
            return 'ai_hosted'
        if getattr(handoff, 'assigned_to', '') or getattr(handoff, 'operator_reply', ''):
            return 'manual_handling'
        return 'pending_manual'

    def _sales_sender_kind(self, message: Any) -> str:
        role = getattr(message, 'role', None)
        variables = getattr(message, 'variables', None)
        if variables:
            try:
                parsed = json.loads(variables)
            except (TypeError, json.JSONDecodeError):
                parsed = {}
            if parsed.get('sales_sender_kind') == 'operator':
                return 'operator'
        if role == 'assistant':
            return 'assistant'
        return 'customer'

    def _serialize_sales_message(self, message: Any) -> dict[str, Any]:
        normalized = self.normalize_sales_message_content(getattr(message, 'message_content', '') or '')
        sender_kind = self._sales_sender_kind(message)
        if sender_kind == 'operator':
            sender_label = getattr(message, 'runner_name', '') or '人工销售'
        elif sender_kind == 'assistant':
            sender_label = getattr(message, 'bot_name', '') or '数字员工'
        else:
            sender_label = self._customer_name_from_message(message)
        return {
            'id': getattr(message, 'id', ''),
            'timestamp': self._format_datetime(getattr(message, 'timestamp', None)),
            'session_id': getattr(message, 'session_id', ''),
            'role': getattr(message, 'role', None),
            'sender_kind': sender_kind,
            'sender_label': sender_label,
            'bot_id': getattr(message, 'bot_id', ''),
            'bot_name': getattr(message, 'bot_name', ''),
            'platform': getattr(message, 'platform', None),
            'user_id': getattr(message, 'user_id', None),
            'user_name': getattr(message, 'user_name', None),
            'runner_name': getattr(message, 'runner_name', None),
            'status': getattr(message, 'status', ''),
            'level': getattr(message, 'level', ''),
            'preview': normalized['preview'],
            'components': normalized['components'],
            'metadata': normalized['metadata'],
            'raw_message_content': getattr(message, 'message_content', ''),
        }

    def _format_datetime(self, value: Any) -> str:
        if value is None:
            return ''
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
            return value.isoformat()
        return str(value)

    async def get_sales_conversations(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        session_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringSession)
            .order_by(persistence_monitoring.MonitoringSession.last_activity.desc())
            .limit(limit)
            .offset(offset)
        )
        sessions = [self._row_entity(row) for row in session_result.all()]
        session_ids = [session.session_id for session in sessions]
        if not session_ids:
            return []

        handoff_session_aliases: dict[str, str] = {}
        candidate_handoff_session_ids = set(session_ids)
        for session in sessions:
            for alias in self._handoff_session_aliases_for_monitoring_session(session):
                candidate_handoff_session_ids.add(alias)
                handoff_session_aliases[alias] = session.session_id

        message_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.session_id.in_(session_ids))
            .order_by(persistence_monitoring.MonitoringMessage.timestamp.desc())
        )
        latest_by_session: dict[str, Any] = {}
        for row in message_result.all():
            message = self._row_entity(row)
            latest_by_session.setdefault(message.session_id, message)

        memory_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory).where(
                persistence_sales.SalesCustomerMemory.session_id.in_(session_ids)
            )
        )
        memories = {}
        for row in memory_result.all():
            memory = self._row_entity(row)
            memories[memory.session_id] = memory

        handoff_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesHandoff).where(
                persistence_sales.SalesHandoff.session_id.in_(candidate_handoff_session_ids)
            )
        )
        handoffs: dict[str, Any] = {}
        for row in handoff_result.all():
            handoff = self._row_entity(row)
            canonical_session_id = handoff_session_aliases.get(handoff.session_id, handoff.session_id)
            current = handoffs.get(canonical_session_id)
            current_time = getattr(current, 'updated_at', datetime.datetime.min) if current is not None else datetime.datetime.min
            handoff_time = getattr(handoff, 'updated_at', datetime.datetime.min) or datetime.datetime.min
            if current is None or handoff_time >= current_time:
                handoffs[canonical_session_id] = handoff

        conversations: list[dict[str, Any]] = []
        for session in sessions:
            handoff = handoffs.get(session.session_id)
            normalized_status = self._normalized_handoff_status(handoff)
            if status and status != 'all' and normalized_status != status:
                continue
            latest_message = latest_by_session.get(session.session_id)
            latest = self._serialize_sales_message(latest_message) if latest_message else None
            memory = memories.get(session.session_id)
            conversations.append(
                {
                    'session_id': session.session_id,
                    'customer_name': getattr(memory, 'customer_name', '') or self._customer_name_from_session(session),
                    'platform': getattr(session, 'platform', '') or '',
                    'user_id': getattr(session, 'user_id', '') or '',
                    'user_name': getattr(session, 'user_name', '') or '',
                    'bot_id': getattr(session, 'bot_id', '') or '',
                    'bot_name': getattr(session, 'bot_name', '') or '',
                    'message_count': getattr(session, 'message_count', 0) or 0,
                    'last_activity': self._format_datetime(getattr(session, 'last_activity', None)),
                    'latest_message': latest,
                    'latest_message_preview': latest['preview'] if latest else '',
                    'handoff_status': normalized_status,
                    'handoff': self._serialize_handoff(handoff) if handoff else None,
                    'memory': self.ap.persistence_mgr.serialize_model(persistence_sales.SalesCustomerMemory, memory)
                    if memory
                    else None,
                }
            )
        return conversations

    async def get_sales_conversation_messages(
        self,
        session_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.session_id == session_id)
            .order_by(persistence_monitoring.MonitoringMessage.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = [self._row_entity(row) for row in result.all()]
        messages = [self._serialize_sales_message(message) for message in sorted(rows, key=lambda item: item.timestamp)]
        return {'messages': messages, 'total': len(messages)}

    async def generate_sales_reply_suggestion_from_session(
        self,
        session_id: str,
        product_uuid: str = '',
        tone: str = 'consultative',
    ) -> dict[str, Any]:
        messages = await self.get_sales_conversation_messages(session_id, limit=20, offset=0)
        context = '\n'.join(message['preview'] for message in messages['messages'][-8:] if message.get('preview'))
        products = await self.get_products(enabled_only=True)
        product = next((item for item in products if item.get('uuid') == product_uuid), None) if product_uuid else None
        if product is None:
            product = self.select_best_product(context, products)
        if product is None:
            raise ValueError('No product available')
        llm_suggestion = await self._generate_llm_sales_reply_suggestion(
            messages['messages'][-12:],
            product,
            tone,
        )
        if llm_suggestion is not None:
            return {
                'suggestion': llm_suggestion['suggestion'],
                'product': product,
                'source': 'llm',
                'model_uuid': llm_suggestion.get('model_uuid', ''),
                'model_name': llm_suggestion.get('model_name', ''),
            }
        pitch = self.generate_pitch(product, customer_profile=context, intent=context, tone=tone)
        return {'suggestion': pitch, 'product': product, 'source': 'fallback', 'model_uuid': '', 'model_name': ''}

    async def _generate_llm_sales_reply_suggestion(
        self,
        messages: list[dict[str, Any]],
        product: dict[str, Any],
        tone: str,
    ) -> dict[str, Any] | None:
        model_uuid = self._preferred_sales_suggestion_model_uuid()
        if not model_uuid:
            return None
        try:
            from langbot_plugin.api.entities.builtin.provider import message as provider_message

            runtime_model = await self.ap.model_mgr.get_model_by_uuid(model_uuid)
            model_entity = getattr(runtime_model, 'model_entity', None)
            model_name = str(getattr(model_entity, 'name', '') or model_uuid)
            prompt = self._build_sales_suggestion_prompt(messages, product, tone)
            response = await runtime_model.provider.invoke_llm(
                query=None,
                model=runtime_model,
                messages=[
                    provider_message.Message(
                        role='system',
                        content=(
                            '你是SCRM人工接管工作台里的销售助理。'
                            '请基于真实聊天上下文给人工客服一条可直接发送的中文回复。'
                            '不要编造不存在的优惠、名额、承诺或链接；如果需要人工确认，就明确说我帮您确认。'
                        ),
                    ),
                    provider_message.Message(role='user', content=prompt),
                ],
                funcs=[],
                extra_args=copy.deepcopy(getattr(model_entity, 'extra_args', {}) or {}),
                remove_think=True,
            )
            text = self._provider_message_content_to_text(getattr(response, 'content', response)).strip()
            if not text:
                return None
            return {
                'suggestion': {
                    'tone': tone,
                    'message': text,
                    'next_action': 'manual_review',
                },
                'model_uuid': model_uuid,
                'model_name': model_name,
            }
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning(f'[Sales] LLM reply suggestion failed, falling back to rule pitch: {exc}')
            return None

    def _preferred_sales_suggestion_model_uuid(self) -> str:
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
        return False

    def _build_sales_suggestion_prompt(
        self,
        messages: list[dict[str, Any]],
        product: dict[str, Any],
        tone: str,
    ) -> str:
        conversation_lines = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = message.get('role') or message.get('sender_type') or ''
            sender = message.get('sender_name') or ('客户' if role == 'user' else 'AI')
            preview = str(message.get('preview') or '').strip()
            if preview:
                conversation_lines.append(f'{sender}: {preview}')
        payload = {
            'tone': tone,
            'conversation': conversation_lines[-12:],
            'product': {
                'name': product.get('name'),
                'price': product.get('price'),
                'link': product.get('link'),
                'description': product.get('description'),
                'selling_points': product.get('selling_points') or [],
                'pain_points': product.get('pain_points') or [],
                'objections': product.get('objections') or [],
                'audience': product.get('audience') or [],
            },
            'requirements': [
                '只输出一条人工客服可直接发送的回复，不要输出标题或解释。',
                '先回应客户刚刚的问题或情绪，再给清晰下一步。',
                '语气像真实SCRM聊天，短句、可读，不要长篇营销。',
                '如果客户要求人工或情绪激动，回复应体现人工正在接入处理。',
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

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


    def _query_session_id(self, query: Any) -> str:
        launcher_type = getattr(query, 'launcher_type', '')
        launcher_id = getattr(query, 'launcher_id', '')
        if getattr(launcher_type, 'name', None) and str(launcher_type):
            return f'{launcher_type}_{launcher_id}'
        launcher_type_value = getattr(launcher_type, 'value', None)
        if launcher_type_value:
            return f'{launcher_type_value}_{launcher_id}'
        return f'{launcher_type}_{launcher_id}'

    def _query_session_aliases(self, query: Any) -> list[str]:
        aliases: set[str] = set()
        variables = getattr(query, 'variables', None)
        if isinstance(variables, dict):
            session_id = str(variables.get('session_id') or '').strip()
            if session_id:
                aliases.add(session_id)

        session = getattr(query, 'session', None)
        for source in (query, session):
            if source is None:
                continue
            launcher_type = getattr(source, 'launcher_type', '')
            launcher_id = str(getattr(source, 'launcher_id', '') or '').strip()
            if not launcher_id:
                continue
            raw_type = str(launcher_type or '').strip()
            value_type = str(getattr(launcher_type, 'value', '') or '').strip()
            if raw_type:
                aliases.add(f'{raw_type}_{launcher_id}')
            if value_type:
                aliases.add(f'{value_type}_{launcher_id}')

        return sorted(aliases)

    def _query_target_aliases(self, query: Any) -> list[tuple[str, str]]:
        aliases: set[tuple[str, str]] = set()
        launcher_type = getattr(getattr(query, 'launcher_type', None), 'value', None) or getattr(query, 'launcher_type', '')
        target_type = str(launcher_type or 'person')
        if target_type not in ('person', 'group'):
            target_type = 'person'
        for value in (getattr(query, 'launcher_id', ''), getattr(query, 'sender_id', '')):
            target_id = str(value or '').strip()
            if target_id:
                aliases.add((target_type, target_id))
        return sorted(aliases)

    def _clear_runtime_conversation(self, query: Any) -> None:
        session = getattr(query, 'session', None)
        conversation = getattr(session, 'using_conversation', None)
        messages = getattr(conversation, 'messages', None)
        if hasattr(messages, 'clear'):
            messages.clear()

    def _handoff_session_aliases_for_monitoring_session(self, session: Any) -> set[str]:
        session_id = str(getattr(session, 'session_id', '') or '')
        platform = str(getattr(session, 'platform', '') or '')
        user_id = str(getattr(session, 'user_id', '') or '')
        aliases = {session_id} if session_id else set()
        if platform and user_id:
            aliases.add(f'{platform}_{user_id}')
        target_type, target_id = self._target_from_session(session)
        if target_type and target_id:
            aliases.add(f'{target_type}_{target_id}')
        return aliases

    def _target_from_session(self, session: Any) -> tuple[str, str]:
        session_id = getattr(session, 'session_id', '') or ''
        prefix, sep, target_id = session_id.partition('_')
        if sep and prefix in ('person', 'group'):
            return prefix, target_id
        platform = getattr(session, 'platform', '') or ''
        target_type = platform if platform in ('person', 'group') else 'person'
        return target_type, getattr(session, 'user_id', '') or session_id

    def _first_row(self, result: Any) -> Any:
        row = result.first()
        return self._row_entity(row)

    def _row_value(self, row: Any) -> Any:
        if row is None:
            return None
        if isinstance(row, (str, int, float, bool, datetime.datetime)):
            return row
        try:
            return row[0]
        except (KeyError, IndexError, TypeError, AttributeError):
            return row

    def _row_entity(self, row: Any) -> Any:
        if isinstance(row, tuple):
            return row[0]
        mapping = getattr(row, '_mapping', None)
        if mapping:
            mapped_values = list(mapping.values())
            for value in mapped_values:
                if hasattr(value, '__table__'):
                    return value
            if len(mapped_values) == 1 and not isinstance(mapped_values[0], (str, int, float, bool, bytes, type(None))):
                return mapped_values[0]
            string_keys = {str(key): value for key, value in mapping.items() if isinstance(key, str)}
            if string_keys:
                return SimpleNamespace(**string_keys)
        try:
            return row[0]
        except (TypeError, KeyError, IndexError):
            return row

    def _stage_for_intent(self, intent: str) -> str:
        if intent in ('purchase', 'price'):
            return 'high_intent'
        if intent in ('comparison', 'objection', 'product_interest'):
            return 'consideration'
        if intent == 'handoff':
            return 'handoff'
        return 'new'

    def _summarize_memory(
        self,
        previous_summary: str,
        message_text: str,
        intent: dict[str, Any],
        product: dict[str, Any] | None,
    ) -> str:
        product_name = product.get('name', '') if product else ''
        addition = f'客户最近表达了「{intent.get("intent", "general")}」意图'
        if product_name:
            addition += f'，关联产品：{product_name}'
        addition += f'。原话：{message_text[:120]}'
        if previous_summary:
            return (previous_summary + '\n' + addition)[-1200:]
        return addition

    def _to_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            if not value.strip():
                return []
            return [v.strip() for v in re.split(r'[,，\n;；]', value) if v.strip()]
        return [str(value)]

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.split(r'[\s,，。；;、/|]+', text)
        return [token for token in tokens if len(token) >= 2]
