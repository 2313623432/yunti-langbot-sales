from __future__ import annotations

import base64
import copy
import gzip
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import aiohttp
import sqlalchemy
import websockets

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from ....core import app
from ....entity.persistence import model as persistence_model
from ....entity.persistence import pipeline as persistence_pipeline
from ....entity.persistence import sales as persistence_sales
from ....utils import paths as path_utils
from .pipeline_defaults import default_stage_order


TASK_ASSISTANT_SCENARIO = 'task_assistant_ant_af'
TASK_ASSISTANT_PIPELINE_UUID = 'task-assistant-ant-af-pipeline'
TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID = 'task-assistant-ant-af-template-pipeline'
TASK_ASSISTANT_PROVIDER_UUID = 'task-assistant-bailian-provider'
TASK_ASSISTANT_MODEL_UUID = 'task-assistant-qwen-vl-plus'
TASK_ASSISTANT_MODEL_NAME = 'qwen-vl-plus'
TASK_ASSISTANT_TTS_VOICE_TYPE = 'zh_female_yuanqinvyou_moon_bigtts'
COURSE_SALES_SCENARIO = 'course_sales_yuanfudao_phonics'
COURSE_SALES_WORKFLOW_PIPELINE_UUID = 'course-sales-workflow-pipeline'
COURSE_SALES_TEMPLATE_PIPELINE_UUID = 'course-sales-template-pipeline'
COURSE_SALES_PRODUCT_UUID = 'yuanfudao-phonics-course'
COURSE_SALES_TTS_VOICE_TYPE = TASK_ASSISTANT_TTS_VOICE_TYPE
ASSISTED_SCENARIOS = {TASK_ASSISTANT_SCENARIO, COURSE_SALES_SCENARIO}

COURSE_SALES_RADAR_LINK = 'https://radar.yunti.local/course/phonics?campaign=private_domain&product=yuanfudao_phonics'

COURSE_SALES_PROFILE = {
    'course_name': '猿辅导英语自然拼读体验课/自然拼读集训营',
    'price': '9元体验',
    'lesson_count': '5天10节课',
    'target_grade': '大班至小学4年级',
    'schedule': '分两周进行：第一周五、周六；第二周五、周六、周日；晚上19:00-20:00；每天约60分钟。',
    'replay': '3年内无限次回放，手机和平板都可以学习。',
    'content': '5次绘本阅读实践、180次开口练习、360分钟配套视频，帮助孩子掌握自然拼读、口语发音和拼读规则。',
    'selling_point': '见词能拼、听音能写；用拼读方法替代死记硬背；提升英语兴趣和发音基础。',
    'gifts': '报名/完课活动可赠小猿篮球、护脊书包、小猿手办、宇航员文具盒、铅笔、转笔刀等，完课后随机发货其一。',
    'after_purchase': '提醒添加指导老师/班主任，留意电话短信，下载猿辅导素养课APP查看课程和开课时间。',
}

COURSE_RESOURCE_FAQS = [
    {
        'question': '怎么听音频/怎么看答案',
        'answer': '引导用户点击已推送的资源卡片，或重新扫码查看。',
        'keywords': ['音频', '答案', '怎么看', '听力'],
    },
    {
        'question': '验证码在哪里',
        'answer': '提示验证码在书本封面或书上对应位置，主要用于验证正版，一码一书。',
        'keywords': ['验证码', '正版', '码'],
    },
    {
        'question': '扫码看答案',
        'answer': '提示重新扫书上二维码；如果仍无法打开，引导使用答案小程序或资源卡片入口。',
        'keywords': ['扫码', '二维码', '答案小程序'],
    },
    {
        'question': '扫码后暂无资源',
        'answer': '回复资源可能还在更新，请等待后台上传；如用户着急，收集图书二维码所在页清晰照片。',
        'keywords': ['暂无资源', '没有资源', '打不开'],
    },
    {
        'question': '资源不对',
        'answer': '收集图书二维码所在页和有问题页面照片，记录后反馈处理。',
        'keywords': ['资源不对', '不是这本', '错了'],
    },
    {
        'question': '资料能不能下载',
        'answer': '统一回复资料以在线查看为主，不支持直接下载；可打印资料按活动资料包说明引导。',
        'keywords': ['下载', '打印', '保存'],
    },
    {
        'question': '资源类问题是否转人工',
        'answer': '常规资源问题不转人工，由AI直接处理；只有用户强烈投诉或AI无法判断时才转人工。',
        'keywords': ['人工', '客服', '投诉'],
    },
]

COURSE_FAQS = [
    {
        'intent': 'course_schedule',
        'question': '什么时候上课',
        'answer': '分两周上课，第一周五六、第二周五六日，晚上19点到20点；每天大概60分钟。没时间可以看回放，3年内无限次回放，手机平板都能学。',
        'keywords': ['什么时候', '几点', '上课时间', '回放'],
    },
    {
        'intent': 'course_intro',
        'question': '这个是什么课/这是什么/你发是什么',
        'answer': '猿辅导自然拼读课程，9元5天10节，适合大班到小学4年级，主要练自然拼读、绘本阅读和开口表达，内容会按孩子年级匹配。',
        'keywords': ['什么课', '是什么', '自然拼读', '学什么'],
    },
    {
        'intent': 'course_content',
        'question': '学习内容',
        'answer': '每个年级内容会按孩子情况匹配，核心是自然拼读、绘本阅读、口语发音和开口练习。可以先低成本体验一轮，看孩子适不适应。',
        'keywords': ['学习内容', '内容', '学啥', '学什么'],
    },
    {
        'intent': 'course_replay',
        'question': '支持回放吗',
        'answer': '支持回放的，3年内可以无限次看，手机和平板都能学。',
        'keywords': ['回放', '没时间', '错过'],
    },
    {
        'intent': 'course_conflict',
        'question': '和其他课有冲突',
        'answer': '不冲突的，这个更侧重教孩子拼读技巧和方法，支持回放，可以先让孩子试试看。',
        'keywords': ['冲突', '没空', '上班', '时间'],
    },
    {
        'intent': 'purchase',
        'question': '要买/怎么买',
        'answer': '点开报名链接，选择孩子年级，输入手机号验证，确认支付9元后把截图发我，我这边给您登记开课并发资料。',
        'keywords': ['要买', '怎么买', '报名', '链接', '领取'],
    },
    {
        'intent': 'purchased',
        'question': '买了/已报名',
        'answer': '谢谢支持，报名后会分配指导老师；您也可以先下载猿辅导素养课APP查看课程和开课时间，完课礼品后续联系班主任领取。',
        'keywords': ['买了', '已报名', '支付', '付了', '截图'],
    },
    {
        'intent': 'objection',
        'question': '不买/考虑',
        'answer': '没关系家长，这个主要是让孩子低成本体验自然拼读方法，9元压力也小。现在报名还有资料和完课礼，可以先试一轮看看是否适合。',
        'keywords': ['考虑', '不买', '贵', '再说'],
    },
    {
        'intent': 'gift',
        'question': '赠品/资料',
        'answer': '报名还独家赠送资料，完课后随机发实物礼品。具体礼品以班主任登记和活动规则为准。',
        'keywords': ['赠品', '礼品', '资料', '篮球', '书包'],
    },
    {
        'intent': 'grade',
        'question': '适合几年级',
        'answer': '这套自然拼读适合大班到小学4年级。如果孩子年级不在这个范围，我先帮您确认更适合的课程入口。',
        'keywords': ['几年级', '大班', '一年级', '四年级', '初中'],
    },
    {
        'intent': 'link_error',
        'question': '链接打不开/页面异常',
        'answer': '我帮您看下，麻烦截一下当前页面；也可以先退出重进，或复制链接到浏览器打开。',
        'keywords': ['打不开', '白屏', '点不进去', '页面'],
    },
]

COURSE_FOLLOWUP_SEQUENCES = [
    {
        'stage': 'purchase',
        'label': '要买/怎么买',
        'messages': [
            {'delay_minutes': 0, 'message': '好的家长，我把报名通道发您，点开后支付9元就可以。'},
            {'delay_minutes': 5, 'message': '家长领取到了吗？支付成功后截图发我，我给您登记开课和资料。'},
            {'delay_minutes': 60, 'message': '孩子家长，你好，这边您给小孩领取好了吗？后台每个年级名额不多，您没领的话抽空领一下。', 'voice_optional': True},
            {'delay_minutes': 0, 'schedule_time': '21:30', 'message': '晚上好家长，忙完了么？现在方便给孩子预约下吗，赠送名额还给您保留着呢。'},
        ],
    },
    {
        'stage': 'objection',
        'label': '不买/考虑',
        'messages': [
            {'delay_minutes': 0, 'message': '没关系家长，这个课主要是先低成本体验，9元压力小，孩子适合再继续。'},
            {'delay_minutes': 0, 'message': '报名还赠资料和完课礼，名额就这一周有，您可以先给孩子试一轮。'},
        ],
    },
    {
        'stage': 'purchased',
        'label': '买了',
        'messages': [
            {'delay_minutes': 0, 'message': '谢谢支持，报名后会出现指导老师二维码，您添加一下，老师会提醒上课。'},
            {'delay_minutes': 0, 'message': '您也可以先下载猿辅导素养课APP，用报名手机号登录查看课程和开课时间。'},
        ],
    },
    {
        'stage': 'no_reply',
        'label': '不回复',
        'messages': [
            {'delay_minutes': 1440, 'message': '家长，看您还没预约成功，是链接打不开、年级没选对，还是暂时不方便？我可以帮您看一下。'},
        ],
    },
    {
        'stage': 'radar_clicked',
        'label': '点雷达',
        'messages': [
            {'delay_minutes': 0, 'message': '家长，看您进入报名通道了，支付以后麻烦您发我支付成功截图或者报名成功短信，我给您登记开课并赠送资料。'},
            {'delay_minutes': 5, 'message': '家长领取到了吗？'},
            {'delay_minutes': 60, 'message': '孩子家长，你好，这边您给小孩领取好了吗？后台每个年级名额不多，您没领的话抽空领一下。', 'voice_optional': True},
            {'delay_minutes': 0, 'schedule_time': '21:30', 'message': '晚上好家长，忙完了么？现在方便给孩子预约下吗，赠送名额还给您保留着呢。'},
        ],
    },
]

COURSE_LONG_TERM_BROADCASTS = [
    {
        'day': 1,
        'title': '第一天主打介绍',
        'time': '10:05',
        'message': '对了家长，猿辅导现在推出5天共10节自然拼读体验课，9元即可学习，支持回放，适合大班到小学4年级。报名成功后我给您登记资料。',
        'image_key': 'course-sales/phonics/day1_course_intro.png',
    },
    {
        'day': 2,
        'title': '第二天再次提醒',
        'time': '10:05',
        'message': '您好家长，再次打扰您了。9元共10节直播课名额不多了，支持回放，还有资料和完课礼。觉得合适的话抽一分钟预约一下。',
        'image_key': 'course-sales/phonics/day2_gift_followup.png',
    },
    {
        'day': 3,
        'title': '第三天最后确认',
        'time': '10:05',
        'message': '在嘛家长，无论孩子体验不体验，给我个答复就行。9元一顿早饭钱，让孩子感受一下方法也是好的，优惠马上截止了。',
        'image_key': 'course-sales/phonics/day3_final_confirm.png',
    },
]

COURSE_IMAGE_BINDINGS = [
    {
        'step_id': 'resource_card',
        'title': '图书配套资源卡片',
        'text': '用户进线后先发送图书配套学习资源卡片，并询问资源是否能打开。',
        'file_key': 'course-sales/phonics/course_resource_card.png',
        'trigger_intents': ['resource_help'],
        'enabled': True,
    },
    {
        'step_id': 'course_intro',
        'title': '自然拼读课程介绍海报',
        'text': '介绍9元5天10节自然拼读体验课，适合大班至小学4年级，支持回放。',
        'file_key': 'course-sales/phonics/day1_course_intro.png',
        'trigger_intents': ['course_intro'],
        'enabled': True,
    },
    {
        'step_id': 'gift',
        'title': '完课礼和赠品说明',
        'text': '说明报名和完课可获得资料与随机实物礼品。',
        'file_key': 'course-sales/phonics/phonics_poster.jpeg',
        'trigger_intents': ['gift', 'objection'],
        'enabled': True,
    },
    {
        'step_id': 'gift_qr',
        'title': '资料领取二维码',
        'text': '成交后补充资料领取二维码，引导家长保存并等班主任联系。',
        'file_key': 'course-sales/phonics/gift_qr.jpeg',
        'trigger_intents': ['purchased'],
        'enabled': True,
    },
    {
        'step_id': 'registration_link',
        'title': '报名链接卡片',
        'text': '发送带雷达参数的报名通道，并说明支付后截图给客服登记。',
        'file_key': 'course-sales/phonics/day2_gift_followup.png',
        'trigger_intents': ['purchase', 'radar_clicked', 'course_schedule', 'course_replay'],
        'enabled': True,
    },
    {
        'step_id': 'final_confirm',
        'title': '最后确认海报',
        'text': '长期触达第三天用于最后确认名额和停发前收口。',
        'file_key': 'course-sales/phonics/day3_final_confirm.png',
        'trigger_intents': ['no_reply'],
        'enabled': True,
    },
]

COURSE_RADAR_CONFIG = {
    'enabled': True,
    'link_title': '猿辅导自然拼读9元体验课报名通道',
    'link_url': COURSE_SALES_RADAR_LINK,
    'tracking_fields': ['session_id', 'campaign', 'clicked_at', 'browse_seconds', 'clicked_apply_button', 'paid'],
    'rules': [
        {
            'event': 'link_open',
            'delay_minutes': 0,
            'message': '家长，看您进入报名通道了，支付以后麻烦您发我支付成功截图或者报名成功短信，我给您登记开课并赠送资料。',
        },
        {
            'event': 'browse_30s',
            'min_browse_seconds': 30,
            'delay_minutes': 3,
            'message': '家长我看到您刚刚看了报名页，是年级选择、支付还是上课时间这块不确定？我可以直接帮您看。',
        },
        {
            'event': 'click_apply_button',
            'delay_minutes': 1,
            'message': '您已经点到报名按钮了，下一步选择孩子年级并支付9元就行，成功后截图发我登记。',
        },
        {
            'event': 'no_payment_after_click',
            'delay_minutes': 15,
            'message': '家长，刚才报名页如果没有支付成功，可能是年级没选对或链接卡住了，您把页面截图发我，我帮您看。',
        },
    ],
}

COURSE_STOP_RULES = {
    'stop_keywords': ['不需要', '不买', '不要再发', '再发投诉', '没有孩子', '不是目标年级', '我是老师', '已经学过'],
    'stop_tags': ['已报名', '已下单', '付费', '投诉', '明确拒绝', '人工接管', '无孩子', '非目标年级', '老师', '已学过'],
    'message': '好的家长，收到，不再打扰您了。后面有需要可以随时联系我。',
}


ANT_AF_STEPS = [
    {
        'id': 'download_qr',
        'title': '支付宝扫码下载蚂蚁阿福 App',
        'detail': '让用户先用支付宝扫描绑定的渠道码，进入下载页面，点击“下载蚂蚁阿福App”。',
        'image_key': 'task-assistant/ant-af/af_step_01.png',
        'intents': ['task_overview', 'download_app', 'screenshot_help'],
    },
    {
        'id': 'app_store_download',
        'title': '在应用商店点击下载',
        'detail': '如果跳转到应用商店，确认页面是“蚂蚁阿福”，点击下载并等待安装完成。',
        'image_key': 'task-assistant/ant-af/af_step_02.png',
        'intents': ['task_overview', 'download_app', 'screenshot_help'],
    },
    {
        'id': 'alipay_login',
        'title': '打开 App 后使用支付宝一键登录',
        'detail': '进入蚂蚁阿福首页后，点击页面底部的“支付宝一键登录”。',
        'image_key': 'task-assistant/ant-af/af_step_03.png',
        'intents': ['task_overview', 'alipay_login', 'screenshot_help'],
    },
    {
        'id': 'alipay_login_confirm',
        'title': '同意支付宝授权登录',
        'detail': '在支付宝授权页确认申请方是蚂蚁阿福 App，点击“同意”。',
        'image_key': 'task-assistant/ant-af/af_step_04.png',
        'intents': ['task_overview', 'alipay_login', 'screenshot_help'],
    },
    {
        'id': 'open_profile',
        'title': '登录后点击左上角头像/菜单',
        'detail': '登录成功后，在首页点击左上角头像或菜单入口，进入个人中心。',
        'image_key': 'task-assistant/ant-af/af_step_05.png',
        'intents': ['task_overview', 'real_person_verify', 'screenshot_help'],
    },
    {
        'id': 'open_settings',
        'title': '进入设置',
        'detail': '在个人中心页面点击用户信息区域或设置入口，进入“我的/设置”相关页面。',
        'image_key': 'task-assistant/ant-af/af_step_06.png',
        'intents': ['task_overview', 'real_person_verify', 'screenshot_help'],
    },
    {
        'id': 'open_real_person_verify',
        'title': '点击实名认证',
        'detail': '在“我的”页面找到“实名认证”，点击进入。若显示“已认证”，说明这一步已完成。',
        'image_key': 'task-assistant/ant-af/af_step_07.png',
        'intents': ['task_overview', 'real_person_verify', 'finish', 'screenshot_help'],
    },
    {
        'id': 'import_identity',
        'title': '支付宝一键导入身份信息',
        'detail': '在真人认证页面点击“支付宝一键导入”，按支付宝提示完成身份信息授权。',
        'image_key': 'task-assistant/ant-af/af_step_08.png',
        'intents': ['task_overview', 'real_person_verify', 'finish', 'screenshot_help'],
    },
]

ANT_AF_STEP_IDS = [step['id'] for step in ANT_AF_STEPS]
ANT_AF_STEP_INDEX_BY_ID = {step_id: idx for idx, step_id in enumerate(ANT_AF_STEP_IDS)}
CHINESE_STEP_NUMBERS = {
    '一': 0,
    '二': 1,
    '三': 2,
    '四': 3,
    '五': 4,
    '六': 5,
    '七': 6,
    '八': 7,
    '1': 0,
    '2': 1,
    '3': 2,
    '4': 3,
    '5': 4,
    '6': 5,
    '7': 6,
    '8': 7,
}


class TaskAssistantService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self._session_progress: dict[str, dict[str, Any]] = {}

    def _is_task_assistant_workflow(self, workflow: dict[str, Any] | None) -> bool:
        if not isinstance(workflow, dict):
            return False
        metadata = workflow.get('metadata') if isinstance(workflow.get('metadata'), dict) else {}
        return metadata.get('scenario') == TASK_ASSISTANT_SCENARIO

    def _is_assisted_workflow(self, workflow: dict[str, Any] | None) -> bool:
        if not isinstance(workflow, dict):
            return False
        metadata = workflow.get('metadata') if isinstance(workflow.get('metadata'), dict) else {}
        return metadata.get('scenario') in ASSISTED_SCENARIOS

    def _is_course_sales_workflow(self, workflow: dict[str, Any] | None) -> bool:
        if not isinstance(workflow, dict):
            return False
        metadata = workflow.get('metadata') if isinstance(workflow.get('metadata'), dict) else {}
        return metadata.get('scenario') == COURSE_SALES_SCENARIO

    def _template_scenario(self, template_config: dict[str, Any]) -> str:
        metadata = template_config.get('metadata') if isinstance(template_config.get('metadata'), dict) else {}
        scenario = metadata.get('scenario') or template_config.get('scenario')
        if scenario:
            return str(scenario)
        if template_config.get('course_profile') or template_config.get('radar'):
            return COURSE_SALES_SCENARIO
        return TASK_ASSISTANT_SCENARIO

    def active_workflow_from_config(self, pipeline_config: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(pipeline_config, dict):
            return {}
        if pipeline_config.get('config_mode') == 'template':
            template_config = pipeline_config.get('template_config')
            if isinstance(template_config, dict):
                if self._template_scenario(template_config) == COURSE_SALES_SCENARIO:
                    return self.build_course_sales_workflow_from_template_config(template_config)
                return self.build_workflow_from_template_config(template_config)
        workflow = pipeline_config.get('workflow')
        return workflow if isinstance(workflow, dict) else {}

    def is_task_assistant_pipeline(self, pipeline_config: dict[str, Any] | None) -> bool:
        if not isinstance(pipeline_config, dict):
            return False
        return self._is_assisted_workflow(self.active_workflow_from_config(pipeline_config))

    async def prepare_query(self, query: pipeline_query.Query) -> dict[str, Any]:
        workflow = self.active_workflow_from_config(getattr(query, 'pipeline_config', None))
        if not self._is_assisted_workflow(workflow):
            return {'handled': False}

        if self._is_course_sales_workflow(workflow):
            return await self._prepare_course_sales_query(query, workflow)

        if not getattr(query, 'variables', None):
            query.variables = {}

        text = query.variables.get('user_message_text', '')
        session_key = self._query_session_key(query)
        progress = self._session_progress.get(session_key, {}) if session_key else {}
        previous_messages = getattr(query, 'messages', []) or []
        intent = self.classify_intent(text, query.message_chain, previous_messages, progress)
        self._record_progress(session_key, intent)
        query.variables['workflow_intent'] = intent
        query.variables['task_assistant_voice_reply'] = self._has_voice(query.message_chain)
        self._rewrite_user_message_for_multimodal_task(query)
        self._append_step_control_context(query, intent)

        if getattr(query, 'prompt', None) is not None and hasattr(query.prompt, 'messages'):
            if not query.variables.get('_task_assistant_prompt_injected'):
                query.prompt.messages.insert(
                    0,
                    provider_message.Message(role='system', content=self.compose_system_prompt()),
                )
                query.variables['_task_assistant_prompt_injected'] = True

        return {'handled': True, 'intent': intent}

    def classify_intent(
        self,
        text: str,
        message_chain: platform_message.MessageChain | list[platform_message.MessageComponent],
        previous_messages: list[provider_message.Message] | None = None,
        progress: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = (text or '').strip().lower()
        progress = progress or {}
        current_step_id = str(progress.get('current_step_id') or '')
        current_step_index = ANT_AF_STEP_INDEX_BY_ID.get(current_step_id)
        if current_step_index is None:
            current_step_index = self._step_index_from_messages(previous_messages or [])

        explicit_step_index = self._step_index_from_user_text(normalized)
        overview_sent = bool(progress.get('overview_sent'))

        if self._has_image(message_chain):
            step_ids = [ANT_AF_STEPS[current_step_index]['id']] if current_step_index is not None else []
            return {
                'intent': 'screenshot_help',
                'confidence': 0.92,
                'reason': '用户发送了截图，需要识别当前卡住的步骤',
                'step_ids': step_ids,
                'max_images': 1 if step_ids else 0,
                'reply_mode': 'single_step',
                'max_steps_to_describe': 1,
                'include_full_overview': False,
            }
        if self._is_progress_command(normalized):
            next_step_index = self._next_step_index(current_step_index)
            return self._step_intent(
                intent='task_progress',
                confidence=0.84,
                reason='用户表示已完成当前步骤，需要继续下一步',
                step_index=next_step_index,
            )
        if explicit_step_index is not None:
            return self._step_intent(
                intent=self._intent_for_step_index(explicit_step_index),
                confidence=0.86,
                reason='用户明确说明当前卡在某个步骤',
                step_index=explicit_step_index,
            )
        if any(keyword in normalized for keyword in ['完整流程', '完整步骤', '全部流程', '全部步骤', '所有步骤', '一次说完']):
            return self._overview_intent('full_overview', '用户明确要求查看完整流程')
        if any(keyword in normalized for keyword in ['下载', '扫码', '二维码', '安装', 'app']):
            step_id = 'app_store_download' if any(keyword in normalized for keyword in ['应用商店', '安装']) else 'download_qr'
            return self._step_intent(
                intent='download_app',
                confidence=0.82,
                reason='命中下载安装关键词',
                step_index=ANT_AF_STEP_INDEX_BY_ID[step_id],
            )
        if any(keyword in normalized for keyword in ['实名', '真人', '认证', '身份', '导入']):
            step_id = 'import_identity' if '导入' in normalized else 'open_real_person_verify'
            if any(keyword in normalized for keyword in ['设置', '我的']):
                step_id = 'open_settings'
            return self._step_intent(
                intent='real_person_verify',
                confidence=0.86,
                reason='命中实名认证相关关键词',
                step_index=ANT_AF_STEP_INDEX_BY_ID[step_id],
            )
        if any(keyword in normalized for keyword in ['登录', '授权', '一键登录', '同意']):
            step_id = 'alipay_login_confirm' if any(keyword in normalized for keyword in ['授权', '同意']) else 'alipay_login'
            return self._step_intent(
                intent='alipay_login',
                confidence=0.82,
                reason='命中支付宝授权登录关键词',
                step_index=ANT_AF_STEP_INDEX_BY_ID[step_id],
            )
        if any(keyword in normalized for keyword in ['已认证', '认证成功', '任务完成', '完成了', '成功了']):
            return self._step_intent(
                intent='finish',
                confidence=0.78,
                reason='用户确认已完成或接近完成',
                step_index=ANT_AF_STEP_INDEX_BY_ID['import_identity'],
            )
        if self._has_voice(message_chain):
            return self._step_intent(
                intent='voice_reply',
                confidence=0.78,
                reason='用户发送了语音消息',
                step_index=current_step_index or 0,
            )
        if self._is_general_task_question(normalized):
            if overview_sent:
                return self._step_intent(
                    intent='task_overview',
                    confidence=0.7,
                    reason='用户重复询问任务流程，沿用当前步骤继续引导',
                    step_index=current_step_index or 0,
                )
            return self._overview_intent('first_overview', '会话首次咨询任务流程')

        return self._step_intent(
            intent='task_overview',
            confidence=0.64,
            reason='默认从当前步骤继续引导',
            step_index=current_step_index or 0,
        )

    def _step_intent(
        self,
        *,
        intent: str,
        confidence: float,
        reason: str,
        step_index: int,
    ) -> dict[str, Any]:
        step_index = max(0, min(step_index, len(ANT_AF_STEPS) - 1))
        return {
            'intent': intent,
            'confidence': confidence,
            'reason': reason,
            'step_ids': [ANT_AF_STEPS[step_index]['id']],
            'current_step_no': step_index + 1,
            'max_images': 1,
            'reply_mode': 'single_step',
            'max_steps_to_describe': 1,
            'include_full_overview': False,
        }

    def _overview_intent(self, reply_mode: str, reason: str) -> dict[str, Any]:
        return {
            'intent': 'task_overview',
            'confidence': 0.72,
            'reason': reason,
            'step_ids': ['download_qr'],
            'current_step_no': 1,
            'max_images': 1,
            'reply_mode': reply_mode,
            'max_steps_to_describe': 8,
            'include_full_overview': True,
        }

    def _query_session_key(self, query: pipeline_query.Query) -> str:
        session = getattr(query, 'session', None)
        launcher_type = getattr(getattr(session, 'launcher_type', None), 'value', None)
        launcher_id = getattr(session, 'launcher_id', None)
        if launcher_type and launcher_id is not None:
            return f'{launcher_type}_{launcher_id}'

        launcher_type = getattr(getattr(query, 'launcher_type', None), 'value', None) or getattr(query, 'launcher_type', '')
        launcher_id = getattr(query, 'launcher_id', '')
        return f'{launcher_type}_{launcher_id}' if launcher_type and launcher_id != '' else ''

    def _record_progress(self, session_key: str, intent: dict[str, Any]) -> None:
        if not session_key:
            return
        progress = self._session_progress.setdefault(session_key, {})
        step_ids = intent.get('step_ids') if isinstance(intent.get('step_ids'), list) else []
        if step_ids:
            progress['current_step_id'] = str(step_ids[0])
        if intent.get('include_full_overview'):
            progress['overview_sent'] = True

    def _append_step_control_context(self, query: pipeline_query.Query, intent: dict[str, Any]) -> None:
        user_message = getattr(query, 'user_message', None)
        if not isinstance(user_message, provider_message.Message):
            return
        if not isinstance(user_message.content, list):
            user_message.content = [provider_message.ContentElement.from_text(str(user_message.content or ''))]

        step = self._step_from_intent(intent)
        reply_mode = intent.get('reply_mode')
        if reply_mode in {'first_overview', 'full_overview'}:
            control_text = (
                '\n\n[任务办理上下文]\n'
                '可以给一版精简完整流程，每步只写一行；完整流程说完后，立刻聚焦第 1 步。'
                '后续用户再问时不要重复完整流程，只根据当前步骤继续引导。'
            )
        elif step is not None:
            step_no = int(intent.get('current_step_no') or (ANT_AF_STEP_INDEX_BY_ID[step['id']] + 1))
            control_text = (
                '\n\n[任务办理上下文]\n'
                f'本轮只讲第 {step_no} 步：{step["title"]}。本轮只讲这一步，不要列出完整 8 步；'
                '不要重复完整流程。用真人客服口吻告诉用户具体点哪里，最后只补一句做完后可以继续问下一步。'
            )
        else:
            control_text = (
                '\n\n[任务办理上下文]\n'
                '用户发了截图但当前步骤不明确。先根据图片识别页面，再只讲识别出的当前步骤；'
                '如果识别不出来，只问一个最短的问题，不要乱发第一步。'
            )

        user_message.content.append(provider_message.ContentElement.from_text(control_text))

    def _step_from_intent(self, intent: dict[str, Any]) -> dict[str, Any] | None:
        step_ids = intent.get('step_ids') if isinstance(intent.get('step_ids'), list) else []
        if not step_ids:
            return None
        step_index = ANT_AF_STEP_INDEX_BY_ID.get(str(step_ids[0]))
        if step_index is None:
            return None
        return ANT_AF_STEPS[step_index]

    def _is_progress_command(self, normalized: str) -> bool:
        return any(
            keyword in normalized
            for keyword in [
                '下一步',
                '下步',
                '继续',
                '好了',
                '弄好了',
                '做完了',
                '完成这步',
                '完成这一步',
                '然后呢',
                '接下来',
            ]
        )

    def _is_general_task_question(self, normalized: str) -> bool:
        return any(keyword in normalized for keyword in ['怎么做', '怎么完成', '如何完成', '这个任务', '流程', '步骤'])

    def _next_step_index(self, current_step_index: int | None) -> int:
        if current_step_index is None:
            return 0
        return min(current_step_index + 1, len(ANT_AF_STEPS) - 1)

    def _step_index_from_user_text(self, normalized: str) -> int | None:
        for token, step_index in CHINESE_STEP_NUMBERS.items():
            if re.search(rf'第\s*{re.escape(token)}\s*步', normalized):
                return step_index
        step_keywords = [
            ('download_qr', ['二维码', '扫码', '渠道码']),
            ('app_store_download', ['应用商店', '安装']),
            ('alipay_login', ['一键登录', '支付宝登录']),
            ('alipay_login_confirm', ['授权', '同意']),
            ('open_profile', ['头像', '菜单', '个人中心']),
            ('open_settings', ['设置', '我的']),
            ('open_real_person_verify', ['实名认证', '实名']),
            ('import_identity', ['导入身份', '一键导入', '身份信息']),
        ]
        for step_id, keywords in step_keywords:
            if any(keyword in normalized for keyword in keywords):
                return ANT_AF_STEP_INDEX_BY_ID[step_id]
        return None

    def _step_index_from_messages(self, previous_messages: list[provider_message.Message]) -> int | None:
        for message in reversed(previous_messages):
            if getattr(message, 'role', '') not in {'assistant', 'system'}:
                continue
            text = self._message_text(message)
            step_index = self._step_index_from_user_text(text.lower())
            if step_index is not None:
                return step_index
        return None

    def _message_text(self, message: provider_message.Message) -> str:
        content = getattr(message, 'content', '')
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return ''.join(str(getattr(item, 'text', '') or '') for item in content)
        return ''

    def _intent_for_step_index(self, step_index: int) -> str:
        step_id = ANT_AF_STEPS[step_index]['id']
        if step_id in {'download_qr', 'app_store_download'}:
            return 'download_app'
        if step_id in {'alipay_login', 'alipay_login_confirm'}:
            return 'alipay_login'
        if step_id in {'open_profile', 'open_settings', 'open_real_person_verify', 'import_identity'}:
            return 'real_person_verify'
        return 'task_overview'

    def compose_system_prompt(self) -> str:
        step_text = '\n'.join(
            f'{idx}. {step["title"]}：{step["detail"]}' for idx, step in enumerate(ANT_AF_STEPS, 1)
        )
        return f"""你是蚂蚁阿福实名认证办理客服，像真人客服一样自然说话。

说话要求：
- 不要自称 AI、机器人、任务助手、智能助手。
- 不要用官方公告腔，像真人客服一样短句、明确、好懂。
- 用户第一次问完整任务怎么做时，可以先给精简完整流程，每步只写一行，然后马上带他做第 1 步。
- 除了第一次完整概览或用户明确要“完整流程”，每次只讲当前一步和下一步动作，不要一次把 8 个步骤全部列出来。
- 用户说卡住了或发送截图时，先判断他大概在哪一步，再告诉他下一步点哪里。
- 用户发语音时，用短句回复，适合转语音播放。
- 不要编造蚂蚁阿福以外的活动规则、收益承诺或非文档中的入口。

已知标准流程：
{step_text}

回复格式：
1. 先判断用户当前所在步骤。
2. 给出下一步动作，动作要具体到按钮或页面名称。
3. 如果用户缺少上下文，只问一个最短的问题，例如“你现在页面上能看到实名认证吗？”。
4. 如果用户已经完成，提醒他检查是否显示已认证或任务完成。
""".strip()

    def _rewrite_user_message_for_multimodal_task(self, query: pipeline_query.Query) -> None:
        """Keep task-assistant model input compatible with Bailian chat/vision calls."""
        if not isinstance(getattr(query, 'user_message', None), provider_message.Message):
            return

        content: list[provider_message.ContentElement] = []
        plain_text = str(query.variables.get('user_message_text') or '').strip()
        has_voice = self._has_voice(query.message_chain)

        if plain_text:
            content.append(provider_message.ContentElement.from_text(plain_text))

        if has_voice:
            voice_context = (
                '用户发来一条语音咨询。请按蚂蚁阿福实名认证办理场景回复，'
                '口吻像真人客服，短句、自然、适合语音播报；'
                '如果没有明确步骤信息，就先引导他从支付宝扫码下载或让他发当前页面截图。'
            )
            content.append(provider_message.ContentElement.from_text(voice_context))

        for component in query.message_chain:
            if not isinstance(component, platform_message.Image):
                continue
            if component.base64:
                content.append(provider_message.ContentElement.from_image_base64(component.base64))
            elif component.url:
                content.append(provider_message.ContentElement.from_image_url(component.url))

        if not content:
            content.append(
                provider_message.ContentElement.from_text(
                    '用户正在咨询蚂蚁阿福实名认证办理流程，请用真人客服口吻确认他当前卡在哪一步。'
                )
            )

        query.user_message = provider_message.Message(role='user', content=content)

    async def _prepare_course_sales_query(
        self,
        query: pipeline_query.Query,
        workflow: dict[str, Any],
    ) -> dict[str, Any]:
        if not getattr(query, 'variables', None):
            query.variables = {}

        text = query.variables.get('user_message_text', '')
        intent = self.classify_course_sales_intent(text, query.message_chain)
        query.variables['workflow_intent'] = intent
        query.variables['task_assistant_voice_reply'] = self._has_voice(query.message_chain)
        query.variables['course_sales_radar_link'] = intent.get('link_url') or COURSE_SALES_RADAR_LINK
        self._rewrite_user_message_for_course_sales(query, intent)
        self._append_course_sales_control_context(query, intent)

        if getattr(query, 'prompt', None) is not None and hasattr(query.prompt, 'messages'):
            if not query.variables.get('_course_sales_prompt_injected'):
                query.prompt.messages.insert(
                    0,
                    provider_message.Message(role='system', content=self.compose_course_sales_prompt(workflow)),
                )
                query.variables['_course_sales_prompt_injected'] = True

        return {'handled': True, 'intent': intent}

    def classify_course_sales_intent(
        self,
        text: str,
        message_chain: platform_message.MessageChain | list[platform_message.MessageComponent],
    ) -> dict[str, Any]:
        normalized = (text or '').strip().lower()
        if self._has_image(message_chain):
            return self._course_intent(
                'screenshot_help',
                0.9,
                '用户发送了截图，需要识别支付、报名、链接异常或资源页面卡点',
                step_ids=['gift_qr'],
            )
        if any(keyword in normalized for keyword in COURSE_STOP_RULES['stop_keywords']):
            return self._course_intent('stop', 0.94, '用户命中停发或拒绝规则', step_ids=[])
        if any(keyword in normalized for keyword in ['买了', '已报名', '支付了', '付了', '付过', '截图', '报名成功']):
            return self._course_intent('purchased', 0.88, '用户疑似已购买或已报名', step_ids=['gift_qr'])
        if any(keyword in normalized for keyword in ['雷达', '点了', '点击', '打开链接', '看了报名', '进入报名']):
            return self._course_intent(
                'radar_clicked',
                0.86,
                '用户提到点击或进入报名通道，按雷达触发后跟进',
                step_ids=['registration_link'],
                include_link=True,
            )
        resource_keywords = {keyword for faq in COURSE_RESOURCE_FAQS for keyword in faq.get('keywords', [])}
        if any(keyword.lower() in normalized for keyword in resource_keywords):
            return self._course_intent('resource_help', 0.82, '命中图书资源问题', step_ids=['resource_card'])
        for faq in COURSE_FAQS:
            if any(str(keyword).lower() in normalized for keyword in faq.get('keywords', [])):
                intent = str(faq.get('intent') or 'course_intro')
                step_id = self._course_step_for_intent(intent)
                return self._course_intent(intent, 0.82, f'命中课程FAQ：{faq["question"]}', step_ids=[step_id])
        if self._has_voice(message_chain):
            return self._course_intent('voice_reply', 0.76, '用户发送语音，按课程客服短句回复', step_ids=['course_intro'])
        if any(keyword in normalized for keyword in ['报名', '购买', '怎么买', '要买', '链接', '领取']):
            return self._course_intent('purchase', 0.8, '用户咨询报名或购买方式', step_ids=['registration_link'], include_link=True)
        if any(keyword in normalized for keyword in ['不回复', '没人', '没回']):
            return self._course_intent('no_reply', 0.68, '用户处于沉默跟进场景', step_ids=['final_confirm'])
        return self._course_intent('course_intro', 0.64, '默认按自然拼读课程介绍承接', step_ids=['course_intro'])

    def _course_step_for_intent(self, intent: str) -> str:
        if intent in {'purchase', 'course_schedule', 'course_replay', 'link_error', 'radar_clicked'}:
            return 'registration_link'
        if intent in {'purchased', 'screenshot_help'}:
            return 'gift_qr'
        if intent in {'gift', 'objection'}:
            return 'gift'
        if intent in {'resource_help'}:
            return 'resource_card'
        if intent in {'no_reply'}:
            return 'final_confirm'
        return 'course_intro'

    def _course_intent(
        self,
        intent: str,
        confidence: float,
        reason: str,
        *,
        step_ids: list[str],
        include_link: bool = False,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            'intent': intent,
            'confidence': confidence,
            'reason': reason,
            'step_ids': step_ids,
            'max_images': 1 if step_ids else 0,
            'reply_mode': 'course_sales',
            'course_profile': COURSE_SALES_PROFILE,
        }
        if include_link:
            data['link_url'] = COURSE_SALES_RADAR_LINK
            data['radar_enabled'] = True
        return data

    def _rewrite_user_message_for_course_sales(
        self,
        query: pipeline_query.Query,
        intent: dict[str, Any],
    ) -> None:
        if not isinstance(getattr(query, 'user_message', None), provider_message.Message):
            return

        content: list[provider_message.ContentElement] = []
        plain_text = str(query.variables.get('user_message_text') or '').strip()
        if plain_text:
            content.append(provider_message.ContentElement.from_text(plain_text))
        if self._has_voice(query.message_chain):
            content.append(
                provider_message.ContentElement.from_text(
                    '用户发来一条语音咨询。请按猿辅导自然拼读课程客服/销售场景回复，'
                    '短句、自然、像真人客服，适合直接转语音播报。'
                )
            )
        for component in query.message_chain:
            if not isinstance(component, platform_message.Image):
                continue
            if component.base64:
                content.append(provider_message.ContentElement.from_image_base64(component.base64))
            elif component.url:
                content.append(provider_message.ContentElement.from_image_url(component.url))

        if not content:
            content.append(
                provider_message.ContentElement.from_text(
                    '用户正在咨询猿辅导英语自然拼读体验课，请先判断是资源问题、课程问题、报名问题还是售后交付。'
                )
            )
        query.user_message = provider_message.Message(role='user', content=content)

    def _append_course_sales_control_context(
        self,
        query: pipeline_query.Query,
        intent: dict[str, Any],
    ) -> None:
        user_message = getattr(query, 'user_message', None)
        if not isinstance(user_message, provider_message.Message):
            return
        if not isinstance(user_message.content, list):
            user_message.content = [provider_message.ContentElement.from_text(str(user_message.content or ''))]

        intent_name = str(intent.get('intent') or '')
        if intent_name == 'stop':
            control_text = (
                '\n\n[课程销售上下文]\n'
                '用户明确拒绝或命中停发规则。本轮只确认收到并停止打扰，不要再推课、不要发链接、不要发图片。'
            )
        elif intent_name == 'resource_help':
            control_text = (
                '\n\n[课程销售上下文]\n'
                '先解决图书资源问题，不急着推课。只在资源问题解决后，用一句话自然承接自然拼读体验课。'
            )
        elif intent_name in {'purchase', 'radar_clicked'}:
            control_text = (
                '\n\n[课程销售上下文]\n'
                f'本轮要给报名动作和雷达报名链接：{COURSE_SALES_RADAR_LINK}。'
                '说明支付9元后截图或报名成功短信发来，用于登记开课和资料。'
            )
        elif intent_name == 'purchased':
            control_text = (
                '\n\n[课程销售上下文]\n'
                '用户疑似已报名或支付成功。本轮转成交后交付：要截图、提示班主任/短信/猿辅导素养课APP，不要继续促单。'
            )
        elif intent_name == 'screenshot_help':
            control_text = (
                '\n\n[课程销售上下文]\n'
                '用户发了截图。先识别是支付成功、报名页、链接异常、资料页还是二维码页；只针对当前页面给下一步。'
            )
        else:
            control_text = (
                '\n\n[课程销售上下文]\n'
                '围绕猿辅导自然拼读体验课回答：9元、5天10节、大班至小学4年级、支持3年回放、报名后老师安排。'
                '不要夸大提分承诺，不要在用户拒绝后继续骚扰。'
            )

        user_message.content.append(provider_message.ContentElement.from_text(control_text))

    def compose_course_sales_prompt(self, workflow: dict[str, Any] | None = None) -> str:
        workflow = workflow if isinstance(workflow, dict) else {}
        profile = workflow.get('course_profile') if isinstance(workflow.get('course_profile'), dict) else COURSE_SALES_PROFILE
        radar = workflow.get('radar') if isinstance(workflow.get('radar'), dict) else COURSE_RADAR_CONFIG
        resource_faqs = workflow.get('resource_faqs') if isinstance(workflow.get('resource_faqs'), list) else COURSE_RESOURCE_FAQS
        course_faqs = workflow.get('course_faqs') if isinstance(workflow.get('course_faqs'), list) else COURSE_FAQS
        stop_rules = workflow.get('stop_rules') if isinstance(workflow.get('stop_rules'), dict) else COURSE_STOP_RULES
        profile_text = '\n'.join(f'- {key}: {value}' for key, value in profile.items())
        resource_text = '\n'.join(f'- {faq["question"]}: {faq["answer"]}' for faq in resource_faqs)
        course_text = '\n'.join(f'- {faq["question"]}: {faq["answer"]}' for faq in course_faqs)
        stop_text = '、'.join(stop_rules.get('stop_keywords', []))
        radar_rules = radar.get('rules') if isinstance(radar.get('rules'), list) else []
        radar_text = '\n'.join(f'- {rule.get("event")}: {rule.get("message")}' for rule in radar_rules)
        return f"""你是微信/企微私域里的真人课程客服兼销售，负责图书资源承接和猿辅导英语自然拼读体验课转化。

说话要求：
- 不要自称 AI、机器人、智能助手。
- 像真人客服一样短句、明确、自然；先服务，再转化。
- 用户问图书资源，优先解决资源问题，不要急着推课。
- 用户问课程，统一使用下面课程口径，不要自由发挥价格、赠品、课时、链接。
- 用户要买或点击报名链接，发送带雷达参数的报名链接并说明支付后发截图登记。
- 用户已报名/已支付/发支付截图后，立刻停止促单，转班主任、APP、短信、资料交付。
- 用户拒绝、投诉、无孩子、非目标年级、老师身份或人工接管时停止后续触达。
- 不承诺固定提分、效果翻倍、百分百有效等绝对化结果。

课程统一口径：
{profile_text}

图书资源FAQ：
{resource_text}

课程FAQ：
{course_text}

雷达模拟规则：
- 雷达报名链接：{radar.get('link_url') or COURSE_SALES_RADAR_LINK}
{radar_text}

停发关键词：
{stop_text}

回复结构：
1. 先判断用户当前状态。
2. 只回答当前问题，必要时给下一步动作。
3. 需要报名时再发链接；不需要时不要硬推。
4. 需要图片时由工作流追加对应素材图。
""".strip()

    async def synthesize_reply_voice(self, query: pipeline_query.Query, text: str) -> str | None:
        workflow = self.active_workflow_from_config(query.pipeline_config)
        if not self._is_assisted_workflow(workflow):
            return None
        if not query.variables.get('task_assistant_voice_reply'):
            return None

        voice_config = workflow.get('voice') if isinstance(workflow.get('voice'), dict) else {}
        if voice_config.get('enabled') is False:
            return None

        app_id = (
            voice_config.get('app_id')
            or os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_APP_ID')
            or os.getenv('VOLCENGINE_TTS_APP_ID')
        )
        token = (
            voice_config.get('token')
            or os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_TOKEN')
            or os.getenv('VOLCENGINE_TTS_TOKEN')
        )
        if not app_id or not token:
            self.ap.logger.warning('Task assistant TTS skipped: Volcengine app_id/token is not configured')
            return None

        plain_text = self._compact_tts_text(text)
        if not plain_text:
            return None

        encoding = voice_config.get('encoding') or 'ogg_opus'
        audio_base64 = await self._request_volcengine_tts(
            text=plain_text,
            app_id=app_id,
            token=token,
            cluster=voice_config.get('cluster') or 'volcano_tts',
            voice_type=voice_config.get('voice_type') or TASK_ASSISTANT_TTS_VOICE_TYPE,
            encoding=encoding,
        )
        if not audio_base64:
            return None
        return f'data:{self._tts_mime_type(encoding)};base64,{audio_base64}'

    async def ensure_default_resources(self) -> None:
        await self._ensure_task_images()
        await self._ensure_course_sales_images()
        await self._ensure_bailian_model()
        await self._ensure_pipeline()
        await self._ensure_template_pipeline()
        await self._ensure_course_sales_product()
        await self._ensure_course_sales_workflow_pipeline()
        await self._ensure_course_sales_template_pipeline()

    def build_pipeline_config(
        self,
        *,
        bailian_model_uuid: str = TASK_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        config['ai']['runner']['runner'] = 'local-agent'
        config['ai']['runner']['expire-time'] = 0
        config['ai']['local-agent']['model'] = {'primary': bailian_model_uuid, 'fallbacks': []}
        config['ai']['local-agent']['max-round'] = 8
        config['ai']['local-agent']['prompt'] = [
            {'role': 'system', 'content': self.compose_system_prompt()},
        ]
        config['output']['misc']['at-sender'] = False
        config['output']['misc']['quote-origin'] = True
        existing_workflow = existing_config.get('workflow') if isinstance(existing_config, dict) else {}
        existing_voice = existing_workflow.get('voice') if isinstance(existing_workflow, dict) else {}
        config['workflow'] = self.build_workflow_config(
            voice_overrides=existing_voice if isinstance(existing_voice, dict) else None,
        )
        return config

    def build_template_pipeline_config(
        self,
        *,
        bailian_model_uuid: str = TASK_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = self.build_pipeline_config(
            bailian_model_uuid=bailian_model_uuid,
            existing_config=existing_config,
        )
        existing_template = existing_config.get('template_config') if isinstance(existing_config, dict) else {}
        template_config = self.build_template_config(
            overrides=existing_template if isinstance(existing_template, dict) else None,
        )
        existing_workflow = existing_config.get('workflow') if isinstance(existing_config, dict) else None
        config['config_mode'] = 'template'
        config['template_config'] = template_config
        if isinstance(existing_workflow, dict) and existing_workflow:
            config['workflow'] = existing_workflow
        return config

    def build_template_config(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        voice = {
            'provider': 'volcengine',
            'enabled': True,
            'voice_type': TASK_ASSISTANT_TTS_VOICE_TYPE,
            'encoding': 'ogg_opus',
        }
        scheduled_push = {
            'enabled': True,
            'mode': 'daily',
            'time': '10:00',
            'single_date': '',
            'message': '你好，今天继续完成蚂蚁阿福实名认证任务，有卡住的页面直接发截图给我。',
            'push_message': '你好，今天继续完成蚂蚁阿福实名认证任务，有卡住的页面直接发截图给我。',
        }
        interaction_radar = {
            'enabled': False,
            'link_url': '',
            'click_reply': '我看到您刚刚点开了链接，如果有不清楚的地方可以直接问我。',
        }
        template_config = {
            'name': '任务助手模板配置版',
            'role_prompt': self.compose_system_prompt(),
            'opening_message': '我带你一步步完成实名认证。先用支付宝扫码下载蚂蚁阿福 App，完成后跟我说“下一步”。',
            'recommended_questions': [
                '我应该怎么完成这个任务？',
                '我卡在这一步了怎么办？',
                '下一步怎么做？',
            ],
            'model_uuid': TASK_ASSISTANT_MODEL_UUID,
            'max_reasoning_steps': 2,
            'reference_rounds': 2,
            'knowledge_base_uuids': [],
            'product_uuids': [],
            'tools': {
                'intent_recognition': True,
                'knowledge_base': True,
                'product_database': True,
                'image_recognition': True,
                'voice_reply': True,
            },
            'memory': {
                'variables_enabled': True,
                'table_enabled': True,
                'segments_enabled': False,
            },
            'voice': voice,
            'scheduled_push': scheduled_push,
            'interaction_radar': interaction_radar,
            'image_text_bindings': [
                {
                    'step_id': step['id'],
                    'title': step['title'],
                    'text': step['detail'],
                    'file_key': step['image_key'],
                    'trigger_intents': step['intents'],
                    'enabled': True,
                }
                for step in ANT_AF_STEPS
            ],
        }
        if overrides:
            for key, value in overrides.items():
                if key == 'voice' and isinstance(value, dict):
                    template_config['voice'] = {**voice, **value}
                elif key == 'scheduled_push' and isinstance(value, dict):
                    template_config['scheduled_push'] = {**scheduled_push, **value}
                elif key == 'interaction_radar' and isinstance(value, dict):
                    template_config['interaction_radar'] = {**interaction_radar, **value}
                elif key == 'image_text_bindings' and isinstance(value, list) and value:
                    template_config['image_text_bindings'] = value
                else:
                    template_config[key] = value
        return template_config

    def build_workflow_from_template_config(self, template_config: dict[str, Any]) -> dict[str, Any]:
        voice_overrides = template_config.get('voice') if isinstance(template_config.get('voice'), dict) else None
        workflow = self.build_workflow_config(voice_overrides=voice_overrides)
        if isinstance(voice_overrides, dict):
            workflow_voice = workflow.setdefault('voice', {})
            for key, value in voice_overrides.items():
                if value is not None:
                    workflow_voice[key] = value
        workflow['name'] = str(template_config.get('name') or '任务助手模板配置版')
        metadata = workflow.setdefault('metadata', {})
        metadata['source_mode'] = 'template'
        metadata['template_name'] = template_config.get('name') or '任务助手模板配置版'

        model_uuid = str(template_config.get('model_uuid') or TASK_ASSISTANT_MODEL_UUID)
        for node in workflow.get('nodes', []):
            if not isinstance(node, dict):
                continue
            config = node.setdefault('config', {})
            if node.get('type') in {'llm', 'vision'}:
                config['model_uuid'] = model_uuid
            if node.get('type') == 'voice' and isinstance(template_config.get('voice'), dict):
                config.update(template_config['voice'])

        bindings = template_config.get('image_text_bindings')
        if isinstance(bindings, list):
            binding_by_step = {
                str(binding.get('step_id')): binding for binding in bindings if isinstance(binding, dict)
            }
            for node in workflow.get('nodes', []):
                if not isinstance(node, dict):
                    continue
                config = node.setdefault('config', {})
                step_id = str(config.get('step_id') or '')
                node_id = str(node.get('id') or '')
                if not step_id and node_id.startswith('image_'):
                    step_id = node_id.removeprefix('image_')
                binding = binding_by_step.get(step_id)
                if not binding:
                    continue
                if node.get('type') == 'task':
                    node['title'] = str(binding.get('title') or node.get('title') or '')
                    node['description'] = str(binding.get('text') or node.get('description') or '')
                    config['instruction'] = str(binding.get('text') or config.get('instruction') or '')
                    config['enabled'] = binding.get('enabled', True)
                    if isinstance(binding.get('trigger_intents'), list):
                        config['trigger_intents'] = binding['trigger_intents']
                elif node.get('type') == 'image':
                    node['title'] = str(binding.get('title') or node.get('title') or '')
                    config['file_key'] = str(binding.get('file_key') or config.get('file_key') or '')
                    config['image_url'] = str(binding.get('image_url') or config.get('image_url') or '')
                    config['caption'] = str(binding.get('title') or config.get('caption') or '')
                    config['enabled'] = binding.get('enabled', True)
                    if isinstance(binding.get('trigger_intents'), list):
                        config['trigger_intents'] = binding['trigger_intents']

        scheduled_push = template_config.get('scheduled_push')
        if isinstance(scheduled_push, dict):
            workflow['scheduled_push'] = scheduled_push
        interaction_radar = template_config.get('interaction_radar')
        if isinstance(interaction_radar, dict):
            workflow['interaction_radar'] = interaction_radar
            workflow.setdefault('variables', {})['interaction_radar'] = interaction_radar
        return workflow

    def build_workflow_config(self, voice_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        voice_config = {
            'provider': 'volcengine',
            'enabled': True,
            'app_id': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_APP_ID', ''),
            'token': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_TOKEN', ''),
            'cluster': 'volcano_tts',
            'voice_type': TASK_ASSISTANT_TTS_VOICE_TYPE,
            'encoding': 'ogg_opus',
        }
        if voice_overrides:
            for key in ('app_id', 'token'):
                if voice_overrides.get(key):
                    voice_config[key] = voice_overrides[key]

        nodes = [
            {
                'id': 'start',
                'type': 'start',
                'title': '会话触发',
                'description': '用户在网页、微信或企微发来咨询',
                'position': {'x': 80, 'y': 260},
                'config': {'trigger': 'message'},
            },
            {
                'id': 'channel',
                'type': 'channel',
                'title': '渠道接入',
                'description': '统一接收网页、微信、企微等渠道消息',
                'position': {'x': 330, 'y': 260},
                'config': {'channels': ['web', 'wechat', 'wecom'], 'keep_session': True},
            },
            {
                'id': 'media_router',
                'type': 'media',
                'title': '消息类型判断',
                'description': '区分文字、截图和语音',
                'position': {'x': 580, 'y': 260},
                'config': {
                    'routes': [
                        {'when': 'has_text', 'target': 'text_input'},
                        {'when': 'has_voice', 'target': 'voice_asr'},
                        {'when': 'has_image', 'target': 'screenshot_input'},
                    ],
                },
            },
            {
                'id': 'text_input',
                'type': 'custom',
                'title': '文字问题',
                'description': '整理用户文字问题和上下文',
                'position': {'x': 850, 'y': 90},
                'config': {
                    'output_key': 'user_text',
                    'params': '{"from": "message_chain.plain_text"}',
                },
            },
            {
                'id': 'voice_asr',
                'type': 'asr',
                'title': '语音输入处理',
                'description': '语音消息转成适合模型理解的任务上下文，避免聊天请求失败',
                'position': {'x': 850, 'y': 260},
                'config': {
                    'provider': 'bailian',
                    'fallback_text': '用户发来一条语音咨询，请用适合语音播报的短句回复。',
                },
            },
            {
                'id': 'screenshot_input',
                'type': 'vision',
                'title': '截图识别',
                'description': '识别用户卡在哪个页面或步骤',
                'position': {'x': 850, 'y': 430},
                'config': {
                    'model_uuid': TASK_ASSISTANT_MODEL_UUID,
                    'target_steps': [step['id'] for step in ANT_AF_STEPS],
                },
            },
            {
                'id': 'intent',
                'type': 'intent',
                'title': '意图识别',
                'description': '识别下载、登录、实名认证、截图卡点、完成确认等意图',
                'position': {'x': 1130, 'y': 260},
                'config': {
                    'intents': [
                        'task_overview',
                        'download_app',
                        'alipay_login',
                        'real_person_verify',
                        'finish',
                        'screenshot_help',
                        'voice_reply',
                    ],
                    'confidence_threshold': 0.55,
                    'image_intents': ['screenshot_help'],
                },
            },
            {
                'id': 'route_intent',
                'type': 'router',
                'title': '意图路由',
                'description': '把用户问题分发到对应步骤节点',
                'position': {'x': 1400, 'y': 260},
                'config': {
                    'rules': [
                        'download_app -> download_qr, app_store_download',
                        'alipay_login -> alipay_login, alipay_login_confirm',
                        'real_person_verify -> open_profile, open_settings, open_real_person_verify, import_identity',
                        'screenshot_help -> matched_step',
                        'finish -> open_real_person_verify, import_identity',
                    ],
                },
            },
            {
                'id': 'knowledge_fallback',
                'type': 'knowledge',
                'title': '知识库兜底',
                'description': '不属于固定步骤的问题，查知识库后再回答',
                'position': {'x': 1660, 'y': 620},
                'config': {'knowledge_base_uuids': [], 'top_k': 4},
            },
            {
                'id': 'reply',
                'type': 'llm',
                'title': '真人客服式回复',
                'description': '用百炼生成自然、短句、可执行的下一步指引',
                'position': {'x': 3030, 'y': 260},
                'config': {
                    'model_uuid': TASK_ASSISTANT_MODEL_UUID,
                    'tone': '真人客服、短句、具体',
                    'prompt': self.compose_system_prompt(),
                },
            },
            {
                'id': 'voice',
                'type': 'voice',
                'title': '火山语音回复',
                'description': '用户发语音时，把文字回复转成语音一起发回去',
                'position': {'x': 3300, 'y': 160},
                'config': {
                    'provider': 'volcengine',
                    'enabled': True,
                    'voice_type': TASK_ASSISTANT_TTS_VOICE_TYPE,
                    'encoding': 'ogg_opus',
                },
            },
            {
                'id': 'end',
                'type': 'end',
                'title': '发送给用户',
                'description': '发送文字、相关步骤图和必要时的语音',
                'position': {'x': 3300, 'y': 360},
                'config': {},
            },
        ]
        step_positions = [
            {'x': 1660, 'y': 40},
            {'x': 1660, 'y': 200},
            {'x': 1940, 'y': 40},
            {'x': 1940, 'y': 200},
            {'x': 2220, 'y': 40},
            {'x': 2220, 'y': 200},
            {'x': 2500, 'y': 40},
            {'x': 2500, 'y': 200},
        ]
        image_positions = [
            {'x': 1660, 'y': 380},
            {'x': 1660, 'y': 500},
            {'x': 1940, 'y': 380},
            {'x': 1940, 'y': 500},
            {'x': 2220, 'y': 380},
            {'x': 2220, 'y': 500},
            {'x': 2500, 'y': 380},
            {'x': 2500, 'y': 500},
        ]
        for idx, step in enumerate(ANT_AF_STEPS):
            nodes.append(
                {
                    'id': f'step_{step["id"]}',
                    'type': 'task',
                    'title': step['title'],
                    'description': step['detail'],
                    'position': step_positions[idx],
                    'config': {
                        'step_id': step['id'],
                        'step_no': idx + 1,
                        'instruction': step['detail'],
                        'trigger_intents': step['intents'],
                        'completion_check': '用户完成后继续下一步，最后检查是否显示已认证或任务完成。',
                    },
                }
            )
            nodes.append(
                {
                    'id': f'image_{step["id"]}',
                    'type': 'image',
                    'title': f'步骤图 {idx + 1}',
                    'description': step['title'],
                    'position': image_positions[idx],
                    'config': {
                        'file_key': step['image_key'],
                        'caption': step['title'],
                        'trigger_intents': step['intents'],
                        'append_caption': False,
                    },
                }
            )

        edges = [
            {'id': 'e-start-channel', 'source': 'start', 'target': 'channel'},
            {'id': 'e-channel-media', 'source': 'channel', 'target': 'media_router'},
            {'id': 'e-media-text', 'source': 'media_router', 'target': 'text_input', 'label': '文字'},
            {'id': 'e-media-voice', 'source': 'media_router', 'target': 'voice_asr', 'label': '语音'},
            {'id': 'e-media-image', 'source': 'media_router', 'target': 'screenshot_input', 'label': '截图/图片'},
            {'id': 'e-text-intent', 'source': 'text_input', 'target': 'intent'},
            {'id': 'e-voice-intent', 'source': 'voice_asr', 'target': 'intent'},
            {'id': 'e-screenshot-intent', 'source': 'screenshot_input', 'target': 'intent'},
            {'id': 'e-intent-route', 'source': 'intent', 'target': 'route_intent'},
            {'id': 'e-route-knowledge', 'source': 'route_intent', 'target': 'knowledge_fallback', 'label': '兜底问题'},
            {'id': 'e-knowledge-reply', 'source': 'knowledge_fallback', 'target': 'reply'},
            {'id': 'e-reply-voice', 'source': 'reply', 'target': 'voice', 'label': '用户发语音'},
            {'id': 'e-reply-end', 'source': 'reply', 'target': 'end', 'label': '文字/图片'},
            {'id': 'e-voice-end', 'source': 'voice', 'target': 'end'},
        ]
        for step in ANT_AF_STEPS:
            step_node_id = f'step_{step["id"]}'
            image_node_id = f'image_{step["id"]}'
            edges.extend(
                [
                    {
                        'id': f'e-route-{step["id"]}',
                        'source': 'route_intent',
                        'target': step_node_id,
                        'label': '/'.join(step['intents'][:2]),
                    },
                    {'id': f'e-step-image-{step["id"]}', 'source': step_node_id, 'target': image_node_id},
                    {'id': f'e-image-reply-{step["id"]}', 'source': image_node_id, 'target': 'reply'},
                ]
            )

        return {
            'version': 1,
            'name': '任务助手',
            'description': '用真人客服口吻引导用户完成蚂蚁阿福实名认证，支持步骤图片、截图识别和语音回复。',
            'metadata': {
                'scenario': TASK_ASSISTANT_SCENARIO,
                'source': '蚂蚁阿福.docx',
                'model_provider': 'bailian',
                'tts_provider': 'volcengine',
            },
            'nodes': nodes,
            'edges': edges,
            'voice': voice_config,
        }

    def build_course_sales_pipeline_config(
        self,
        *,
        bailian_model_uuid: str = TASK_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        config['ai']['runner']['runner'] = 'local-agent'
        config['ai']['runner']['expire-time'] = 0
        config['ai']['local-agent']['model'] = {'primary': bailian_model_uuid, 'fallbacks': []}
        config['ai']['local-agent']['max-round'] = 8
        config['ai']['local-agent']['prompt'] = [
            {'role': 'system', 'content': self.compose_course_sales_prompt()},
        ]
        config['output']['misc']['at-sender'] = False
        config['output']['misc']['quote-origin'] = True
        existing_workflow = existing_config.get('workflow') if isinstance(existing_config, dict) else {}
        existing_voice = existing_workflow.get('voice') if isinstance(existing_workflow, dict) else {}
        config['workflow'] = self.build_course_sales_workflow_config(
            voice_overrides=existing_voice if isinstance(existing_voice, dict) else None,
        )
        return config

    def build_course_sales_template_pipeline_config(
        self,
        *,
        bailian_model_uuid: str = TASK_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = self.build_course_sales_pipeline_config(
            bailian_model_uuid=bailian_model_uuid,
            existing_config=existing_config,
        )
        existing_template = existing_config.get('template_config') if isinstance(existing_config, dict) else {}
        template_config = self.build_course_sales_template_config(
            overrides=existing_template if isinstance(existing_template, dict) else None,
        )
        existing_workflow = existing_config.get('workflow') if isinstance(existing_config, dict) else None
        config['config_mode'] = 'template'
        config['template_config'] = template_config
        if isinstance(existing_workflow, dict) and existing_workflow:
            config['workflow'] = existing_workflow
        return config

    def build_course_sales_template_config(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        voice = {
            'provider': 'volcengine',
            'enabled': True,
            'voice_type': COURSE_SALES_TTS_VOICE_TYPE,
            'encoding': 'ogg_opus',
        }
        scheduled_push = {
            'enabled': True,
            'mode': 'daily',
            'time': '10:05',
            'single_date': '',
            'message': '家长您好，今天继续同步猿辅导自然拼读体验课名额，有问题直接发我，我帮您看。',
            'push_message': '家长您好，今天继续同步猿辅导自然拼读体验课名额，有问题直接发我，我帮您看。',
        }
        template_config: dict[str, Any] = {
            'name': '课程销售模板',
            'scenario': COURSE_SALES_SCENARIO,
            'metadata': {
                'scenario': COURSE_SALES_SCENARIO,
                'runtime_engine': 'langgraph',
                'source_docs': [
                    'AI客服需求与SOP梳理.docx',
                    'AI销售聊天记录_SOP整理模板_B015资料版.xlsx',
                    '猿辅导自然拼读常见问题(1).xlsx',
                ],
            },
            'role_prompt': self.compose_course_sales_prompt(),
            'opening_message': '家长您好，您扫描的图书配套学习资料已经发您了，您看这个资源能打开吗？',
            'recommended_questions': [
                '这个自然拼读课是什么？',
                '什么时候上课，支持回放吗？',
                '我想报名，怎么操作？',
                '我点了链接但卡住了怎么办？',
            ],
            'model_uuid': TASK_ASSISTANT_MODEL_UUID,
            'max_reasoning_steps': 3,
            'reference_rounds': 4,
            'knowledge_base_uuids': [],
            'product_uuids': [COURSE_SALES_PRODUCT_UUID],
            'tools': {
                'intent_recognition': True,
                'knowledge_base': True,
                'product_database': True,
                'image_recognition': True,
                'voice_reply': True,
                'radar': True,
                'scheduled_push': True,
                'handoff': True,
            },
            'memory': {
                'variables_enabled': True,
                'table_enabled': True,
                'segments_enabled': True,
            },
            'voice': voice,
            'scheduled_push': scheduled_push,
            'course_profile': copy.deepcopy(COURSE_SALES_PROFILE),
            'resource_faqs': copy.deepcopy(COURSE_RESOURCE_FAQS),
            'course_faqs': copy.deepcopy(COURSE_FAQS),
            'sales_links': [
                {
                    'id': 'phonics_radar_apply',
                    'title': '猿辅导自然拼读9元体验课报名通道',
                    'url': COURSE_SALES_RADAR_LINK,
                    'description': '假雷达链接：记录打开、浏览时长、点击报名、未支付等模拟事件。',
                    'radar_enabled': True,
                }
            ],
            'radar': copy.deepcopy(COURSE_RADAR_CONFIG),
            'followup_sequences': copy.deepcopy(COURSE_FOLLOWUP_SEQUENCES),
            'long_term_broadcasts': copy.deepcopy(COURSE_LONG_TERM_BROADCASTS),
            'stop_rules': copy.deepcopy(COURSE_STOP_RULES),
            'image_text_bindings': copy.deepcopy(COURSE_IMAGE_BINDINGS),
        }
        if overrides:
            for key, value in overrides.items():
                if key == 'voice' and isinstance(value, dict):
                    template_config['voice'] = {**voice, **value}
                elif key == 'scheduled_push' and isinstance(value, dict):
                    template_config['scheduled_push'] = {**scheduled_push, **value}
                elif key in {'radar', 'stop_rules', 'course_profile'} and isinstance(value, dict):
                    current = template_config.get(key) if isinstance(template_config.get(key), dict) else {}
                    template_config[key] = {**current, **value}
                elif key in {
                    'image_text_bindings',
                    'resource_faqs',
                    'course_faqs',
                    'followup_sequences',
                    'long_term_broadcasts',
                    'sales_links',
                } and isinstance(value, list) and value:
                    template_config[key] = value
                else:
                    template_config[key] = value
        return template_config

    def build_course_sales_workflow_from_template_config(self, template_config: dict[str, Any]) -> dict[str, Any]:
        voice_overrides = template_config.get('voice') if isinstance(template_config.get('voice'), dict) else None
        workflow = self.build_course_sales_workflow_config(
            voice_overrides=voice_overrides,
            template_config=template_config,
        )
        workflow['name'] = str(template_config.get('name') or '课程销售模板')
        metadata = workflow.setdefault('metadata', {})
        metadata['source_mode'] = 'template'
        metadata['template_name'] = template_config.get('name') or '课程销售模板'
        return workflow

    def build_course_sales_workflow_config(
        self,
        voice_overrides: dict[str, Any] | None = None,
        template_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        template_config = template_config if isinstance(template_config, dict) else {}
        course_profile = (
            copy.deepcopy(template_config.get('course_profile'))
            if isinstance(template_config.get('course_profile'), dict)
            else copy.deepcopy(COURSE_SALES_PROFILE)
        )
        resource_faqs = (
            copy.deepcopy(template_config.get('resource_faqs'))
            if isinstance(template_config.get('resource_faqs'), list)
            else copy.deepcopy(COURSE_RESOURCE_FAQS)
        )
        course_faqs = (
            copy.deepcopy(template_config.get('course_faqs'))
            if isinstance(template_config.get('course_faqs'), list)
            else copy.deepcopy(COURSE_FAQS)
        )
        followups = (
            copy.deepcopy(template_config.get('followup_sequences'))
            if isinstance(template_config.get('followup_sequences'), list)
            else copy.deepcopy(COURSE_FOLLOWUP_SEQUENCES)
        )
        broadcasts = (
            copy.deepcopy(template_config.get('long_term_broadcasts'))
            if isinstance(template_config.get('long_term_broadcasts'), list)
            else copy.deepcopy(COURSE_LONG_TERM_BROADCASTS)
        )
        stop_rules = (
            copy.deepcopy(template_config.get('stop_rules'))
            if isinstance(template_config.get('stop_rules'), dict)
            else copy.deepcopy(COURSE_STOP_RULES)
        )
        radar = (
            copy.deepcopy(template_config.get('radar'))
            if isinstance(template_config.get('radar'), dict)
            else copy.deepcopy(COURSE_RADAR_CONFIG)
        )
        sales_links = (
            copy.deepcopy(template_config.get('sales_links'))
            if isinstance(template_config.get('sales_links'), list) and template_config.get('sales_links')
            else [
                {
                    'id': 'phonics_radar_apply',
                    'title': '猿辅导自然拼读9元体验课报名通道',
                    'url': radar.get('link_url') or COURSE_SALES_RADAR_LINK,
                    'description': '假雷达链接，支持模拟点击、浏览时长和未支付触发。',
                    'radar_enabled': True,
                }
            ]
        )
        image_bindings = (
            copy.deepcopy(template_config.get('image_text_bindings'))
            if isinstance(template_config.get('image_text_bindings'), list)
            else copy.deepcopy(COURSE_IMAGE_BINDINGS)
        )
        model_uuid = str(template_config.get('model_uuid') or TASK_ASSISTANT_MODEL_UUID)
        voice_config = {
            'provider': 'volcengine',
            'enabled': True,
            'app_id': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_APP_ID', ''),
            'token': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_TOKEN', ''),
            'cluster': 'volcano_tts',
            'voice_type': COURSE_SALES_TTS_VOICE_TYPE,
            'encoding': 'ogg_opus',
        }
        if voice_overrides:
            for key, value in voice_overrides.items():
                if value is not None:
                    voice_config[key] = value

        nodes = [
            {
                'id': 'start',
                'type': 'start',
                'title': '用户进线',
                'description': '用户扫码、添加微信/企微或在网页咨询课程与图书资源',
                'position': {'x': 80, 'y': 320},
                'config': {'trigger': 'message'},
            },
            {
                'id': 'channel',
                'type': 'channel',
                'title': '渠道接入',
                'description': '统一接收网页、微信、企微、飞书等渠道消息',
                'position': {'x': 340, 'y': 320},
                'config': {'channels': ['web', 'wechat', 'wecom', 'lark'], 'keep_session': True},
            },
            {
                'id': 'media_router',
                'type': 'media',
                'title': '消息类型判断',
                'description': '区分文字、截图/图片和语音',
                'position': {'x': 600, 'y': 320},
                'config': {
                    'routes': [
                        {'when': 'has_text', 'target': 'text_input'},
                        {'when': 'has_voice', 'target': 'voice_asr'},
                        {'when': 'has_image', 'target': 'screenshot_input'},
                    ],
                },
            },
            {
                'id': 'text_input',
                'type': 'custom',
                'title': '文字问题整理',
                'description': '提取家长问题、孩子年级、是否点击链接、是否已报名',
                'position': {'x': 890, 'y': 120},
                'config': {'output_key': 'user_text', 'params': '{"from": "message_chain.plain_text"}'},
            },
            {
                'id': 'voice_asr',
                'type': 'asr',
                'title': '语音输入处理',
                'description': '用户发语音时，先转成课程咨询上下文，再要求回复也转语音',
                'position': {'x': 890, 'y': 320},
                'config': {'provider': 'bailian', 'fallback_text': '用户发来课程咨询语音，请用短句回复。'},
            },
            {
                'id': 'screenshot_input',
                'type': 'vision',
                'title': '截图识别',
                'description': '识别支付成功页、报名页、白屏、资源页或二维码页',
                'position': {'x': 890, 'y': 520},
                'config': {
                    'model_uuid': model_uuid,
                    'target_steps': ['resource_card', 'registration_link', 'gift_qr', 'link_error'],
                },
            },
            {
                'id': 'intent',
                'type': 'intent',
                'title': '意图识别',
                'description': '识别资源、课程、购买、已报名、拒绝、投诉、雷达点击等状态',
                'position': {'x': 1180, 'y': 320},
                'config': {
                    'intents': [
                        'resource_help',
                        'course_intro',
                        'course_schedule',
                        'course_replay',
                        'course_content',
                        'purchase',
                        'purchased',
                        'objection',
                        'gift',
                        'radar_clicked',
                        'stop',
                        'screenshot_help',
                        'voice_reply',
                    ],
                    'confidence_threshold': 0.55,
                    'image_intents': ['screenshot_help', 'purchased', 'link_error'],
                },
            },
            {
                'id': 'stop_rules',
                'type': 'condition',
                'title': '停发规则',
                'description': '已报名、投诉、拒绝、人工接管、无孩子等状态停止群发和促单',
                'position': {'x': 1460, 'y': 320},
                'config': stop_rules,
            },
            {
                'id': 'resource_faq',
                'type': 'knowledge',
                'title': '图书资源FAQ',
                'description': '听力、答案、验证码、暂无资源、资源不对、下载等问题',
                'position': {'x': 1740, 'y': 80},
                'config': {'resource_faqs': resource_faqs, 'knowledge_base_uuids': [], 'top_k': 5},
            },
            {
                'id': 'course_faq',
                'type': 'knowledge',
                'title': '课程FAQ',
                'description': '自然拼读课程介绍、上课时间、回放、赠品、冲突和年级适配',
                'position': {'x': 1740, 'y': 260},
                'config': {'course_faqs': course_faqs, 'knowledge_base_uuids': [], 'top_k': 5},
            },
            {
                'id': 'course_product',
                'type': 'product',
                'title': '课程产品库',
                'description': '绑定猿辅导自然拼读体验课产品，输出价格、卖点、适龄和报名方式',
                'position': {'x': 1740, 'y': 440},
                'config': {'product_uuids': [COURSE_SALES_PRODUCT_UUID], 'course_profile': course_profile},
            },
            {
                'id': 'sales_link',
                'type': 'custom',
                'title': '发送报名链接',
                'description': '发送带模拟雷达参数的假报名链接',
                'position': {'x': 2040, 'y': 440},
                'config': {'links': sales_links, 'link_url': radar.get('link_url') or COURSE_SALES_RADAR_LINK},
            },
            {
                'id': 'radar',
                'type': 'radar',
                'title': '模拟雷达',
                'description': '记录链接打开、浏览时长、报名按钮点击和点击未支付',
                'position': {'x': 2340, 'y': 440},
                'config': radar,
            },
            {
                'id': 'radar_followup',
                'type': 'outreach',
                'title': '雷达触达',
                'description': '根据模拟雷达事件创建后续跟进消息',
                'position': {'x': 2640, 'y': 440},
                'config': {'followup_sequences': followups, 'radar_rules': radar.get('rules', [])},
            },
            {
                'id': 'long_term_broadcast',
                'type': 'outreach',
                'title': '长期群发',
                'description': 'Day1-Day3 课程介绍、二次提醒、最后确认；可扩展到Day37',
                'position': {'x': 2340, 'y': 700},
                'config': {'broadcasts': broadcasts, 'stop_rules': stop_rules},
            },
            {
                'id': 'handoff',
                'type': 'handoff',
                'title': '人工接管',
                'description': '投诉、高风险、订单纠纷或人工主动介入后停止AI和群发',
                'position': {'x': 1740, 'y': 700},
                'config': {'reason': '课程咨询需要人工处理', 'stop_ai_reply': True, 'stop_outreach': True},
            },
            {
                'id': 'reply',
                'type': 'llm',
                'title': '真人客服回复',
                'description': '按SOP生成短句、明确、有下一步的课程客服/销售回复',
                'position': {'x': 2940, 'y': 320},
                'config': {
                    'model_uuid': model_uuid,
                    'tone': '真人客服、短句、先服务后转化',
                    'prompt': self.compose_course_sales_prompt(
                        {
                            'course_profile': course_profile,
                            'resource_faqs': resource_faqs,
                            'course_faqs': course_faqs,
                            'radar': radar,
                            'stop_rules': stop_rules,
                        }
                    ),
                },
            },
            {
                'id': 'voice',
                'type': 'voice',
                'title': '火山语音回复',
                'description': '用户发语音时，将文字回复转成火山TTS语音一起发出',
                'position': {'x': 3240, 'y': 180},
                'config': voice_config,
            },
            {
                'id': 'end',
                'type': 'end',
                'title': '发送给用户',
                'description': '发送文字、链接、图片和必要时的语音',
                'position': {'x': 3240, 'y': 420},
                'config': {},
            },
        ]

        image_positions = [
            {'x': 2040, 'y': 40},
            {'x': 2040, 'y': 180},
            {'x': 2340, 'y': 40},
            {'x': 2340, 'y': 180},
            {'x': 2640, 'y': 40},
            {'x': 2640, 'y': 180},
        ]
        for idx, binding in enumerate(image_bindings):
            step_id = str(binding.get('step_id') or f'course_image_{idx}')
            nodes.append(
                {
                    'id': f'image_{step_id}',
                    'type': 'image',
                    'title': str(binding.get('title') or '课程素材图'),
                    'description': str(binding.get('text') or ''),
                    'position': image_positions[idx % len(image_positions)],
                    'config': {
                        'step_id': step_id,
                        'file_key': str(binding.get('file_key') or ''),
                        'image_url': str(binding.get('image_url') or ''),
                        'caption': str(binding.get('title') or ''),
                        'trigger_intents': binding.get('trigger_intents') or [],
                        'append_caption': False,
                        'enabled': binding.get('enabled', True),
                    },
                }
            )

        edges = [
            {'id': 'e-start-channel', 'source': 'start', 'target': 'channel'},
            {'id': 'e-channel-media', 'source': 'channel', 'target': 'media_router'},
            {'id': 'e-media-text', 'source': 'media_router', 'target': 'text_input', 'label': '文字'},
            {'id': 'e-media-voice', 'source': 'media_router', 'target': 'voice_asr', 'label': '语音'},
            {'id': 'e-media-image', 'source': 'media_router', 'target': 'screenshot_input', 'label': '截图/图片'},
            {'id': 'e-text-intent', 'source': 'text_input', 'target': 'intent'},
            {'id': 'e-voice-intent', 'source': 'voice_asr', 'target': 'intent'},
            {'id': 'e-screenshot-intent', 'source': 'screenshot_input', 'target': 'intent'},
            {'id': 'e-intent-stop', 'source': 'intent', 'target': 'stop_rules'},
            {'id': 'e-stop-handoff', 'source': 'stop_rules', 'target': 'handoff', 'label': '投诉/接管'},
            {'id': 'e-stop-resource', 'source': 'stop_rules', 'target': 'resource_faq', 'label': '资源问题'},
            {'id': 'e-stop-course', 'source': 'stop_rules', 'target': 'course_faq', 'label': '课程问题'},
            {'id': 'e-stop-product', 'source': 'stop_rules', 'target': 'course_product', 'label': '购买/课程承接'},
            {'id': 'e-product-link', 'source': 'course_product', 'target': 'sales_link'},
            {'id': 'e-link-radar', 'source': 'sales_link', 'target': 'radar'},
            {'id': 'e-radar-followup', 'source': 'radar', 'target': 'radar_followup'},
            {'id': 'e-radar-reply', 'source': 'radar_followup', 'target': 'reply'},
            {'id': 'e-broadcast-reply', 'source': 'long_term_broadcast', 'target': 'reply'},
            {'id': 'e-handoff-reply', 'source': 'handoff', 'target': 'reply'},
            {'id': 'e-resource-reply', 'source': 'resource_faq', 'target': 'reply'},
            {'id': 'e-course-reply', 'source': 'course_faq', 'target': 'reply'},
            {'id': 'e-link-reply', 'source': 'sales_link', 'target': 'reply'},
            {'id': 'e-reply-voice', 'source': 'reply', 'target': 'voice', 'label': '用户发语音'},
            {'id': 'e-reply-end', 'source': 'reply', 'target': 'end', 'label': '文字/图片/链接'},
            {'id': 'e-voice-end', 'source': 'voice', 'target': 'end'},
        ]
        for binding in image_bindings:
            step_id = str(binding.get('step_id') or '')
            if not step_id:
                continue
            source = 'resource_faq' if step_id == 'resource_card' else 'course_product'
            if step_id in {'gift_qr'}:
                source = 'course_faq'
            if step_id in {'final_confirm'}:
                source = 'long_term_broadcast'
            image_node_id = f'image_{step_id}'
            edges.extend(
                [
                    {'id': f'e-{source}-{image_node_id}', 'source': source, 'target': image_node_id},
                    {'id': f'e-{image_node_id}-reply', 'source': image_node_id, 'target': 'reply'},
                ]
            )

        return {
            'version': 1,
            'name': '课程 销售模板',
            'description': '课程客服与销售工作流：图书资源承接、自然拼读课程答疑、报名转化、雷达跟进、停发与人工接管。',
            'metadata': {
                'scenario': COURSE_SALES_SCENARIO,
                'runtime_engine': 'langgraph',
                'source': 'AI客服需求与SOP梳理.docx + B015销售SOP + 自然拼读FAQ',
                'model_provider': 'bailian',
                'tts_provider': 'volcengine',
                'langgraph_state': {
                    'messages': 'list',
                    'intent': 'dict',
                    'customer_stage': 'str',
                    'radar_event': 'dict',
                    'selected_assets': 'list',
                    'outreach_plan': 'dict',
                },
            },
            'scenario': 'sales',
            'course_profile': course_profile,
            'resource_faqs': resource_faqs,
            'course_faqs': course_faqs,
            'sales_links': sales_links,
            'radar': radar,
            'followup_sequences': followups,
            'long_term_broadcasts': broadcasts,
            'stop_rules': stop_rules,
            'nodes': nodes,
            'edges': edges,
            'variables': {
                'customer_stage': 'resource_service',
                'intent': '',
                'radar_event': {},
                'selected_product_uuid': COURSE_SALES_PRODUCT_UUID,
            },
            'voice': voice_config,
            'scheduled_push': template_config.get('scheduled_push') if isinstance(template_config.get('scheduled_push'), dict) else None,
        }

    async def _ensure_task_images(self) -> None:
        image_dir = Path(path_utils.get_resource_path('templates/task-assistant/ant-af/images'))
        for idx, step in enumerate(ANT_AF_STEPS, 1):
            source_path = image_dir / f'af_step_{idx:02d}.png'
            if not source_path.exists():
                continue
            if await self.ap.storage_mgr.storage_provider.exists(step['image_key']):
                continue
            await self.ap.storage_mgr.storage_provider.save(step['image_key'], source_path.read_bytes())

    async def _ensure_course_sales_images(self) -> None:
        image_dir = Path(path_utils.get_resource_path('templates/course-sales/phonics/images'))
        for binding in COURSE_IMAGE_BINDINGS:
            file_key = str(binding.get('file_key') or '')
            if not file_key:
                continue
            source_path = image_dir / Path(file_key).name
            if not source_path.exists():
                continue
            if await self.ap.storage_mgr.storage_provider.exists(file_key):
                continue
            await self.ap.storage_mgr.storage_provider.save(file_key, source_path.read_bytes())

    async def _ensure_bailian_model(self) -> None:
        api_key = os.getenv('LANGBOT_TASK_ASSISTANT_BAILIAN_API_KEY') or os.getenv('DASHSCOPE_API_KEY') or ''
        provider_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == TASK_ASSISTANT_PROVIDER_UUID
            )
        )
        provider = provider_result.first()
        provider_values = {
            'uuid': TASK_ASSISTANT_PROVIDER_UUID,
            'name': '任务助手-阿里云百炼',
            'requester': 'bailian-chat-completions',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'api_keys': [api_key] if api_key else [],
        }
        if provider is None:
            await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_model.ModelProvider).values(provider_values))
        elif api_key:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_model.ModelProvider)
                .where(persistence_model.ModelProvider.uuid == TASK_ASSISTANT_PROVIDER_UUID)
                .values(api_keys=[api_key])
            )

        model_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == TASK_ASSISTANT_MODEL_UUID)
        )
        if model_result.first() is None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_model.LLMModel).values(
                    uuid=TASK_ASSISTANT_MODEL_UUID,
                    name=TASK_ASSISTANT_MODEL_NAME,
                    provider_uuid=TASK_ASSISTANT_PROVIDER_UUID,
                    abilities=['vision'],
                    extra_args={},
                    prefered_ranking=0,
                )
            )

    async def _ensure_pipeline(self) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == TASK_ASSISTANT_PIPELINE_UUID
            )
        )
        existing_pipeline = result.first()
        if existing_pipeline is not None:
            existing_config = existing_pipeline.config if isinstance(existing_pipeline.config, dict) else {}
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == TASK_ASSISTANT_PIPELINE_UUID)
                .values(
                    name='任务助手',
                    description='用真人客服口吻引导用户完成蚂蚁阿福实名认证，支持一步一图、截图识别和语音回复。',
                    emoji='✅',
                    config=self.build_pipeline_config(existing_config=existing_config),
                    extensions_preferences={
                        'enable_all_plugins': True,
                        'enable_all_mcp_servers': True,
                        'plugins': [],
                        'mcp_servers': [],
                    },
                )
            )
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(
                uuid=TASK_ASSISTANT_PIPELINE_UUID,
                name='任务助手',
                description='用真人客服口吻引导用户完成蚂蚁阿福实名认证，支持一步一图、截图识别和语音回复。',
                emoji='✅',
                for_version=self.ap.ver_mgr.get_current_version(),
                is_default=False,
                stages=default_stage_order.copy(),
                config=self.build_pipeline_config(),
                extensions_preferences={
                    'enable_all_plugins': True,
                    'enable_all_mcp_servers': True,
                    'plugins': [],
                    'mcp_servers': [],
                },
            )
        )

    async def _ensure_template_pipeline(self) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID
            )
        )
        existing_pipeline = result.first()
        if existing_pipeline is not None:
            existing_config = existing_pipeline.config if isinstance(existing_pipeline.config, dict) else {}
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID)
                .values(
                    name='任务助手模板配置版',
                    description='用表单模板配置蚂蚁阿福实名认证引导，自动同步为可运行工作流。',
                    emoji='✅',
                    config=self.build_template_pipeline_config(existing_config=existing_config),
                    extensions_preferences={
                        'enable_all_plugins': True,
                        'enable_all_mcp_servers': True,
                        'plugins': [],
                        'mcp_servers': [],
                    },
                )
            )
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(
                uuid=TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID,
                name='任务助手模板配置版',
                description='用表单模板配置蚂蚁阿福实名认证引导，自动同步为可运行工作流。',
                emoji='✅',
                for_version=self.ap.ver_mgr.get_current_version(),
                is_default=False,
                stages=default_stage_order.copy(),
                config=self.build_template_pipeline_config(),
                extensions_preferences={
                    'enable_all_plugins': True,
                    'enable_all_mcp_servers': True,
                    'plugins': [],
                    'mcp_servers': [],
                },
            )
        )

    async def _ensure_course_sales_product(self) -> None:
        product = {
            'uuid': COURSE_SALES_PRODUCT_UUID,
            'name': '猿辅导英语自然拼读体验课',
            'category': '课程销售',
            'price': COURSE_SALES_PROFILE['price'],
            'link': COURSE_SALES_RADAR_LINK,
            'description': (
                f"{COURSE_SALES_PROFILE['course_name']}，{COURSE_SALES_PROFILE['lesson_count']}，"
                f"{COURSE_SALES_PROFILE['target_grade']}，{COURSE_SALES_PROFILE['replay']}"
            ),
            'selling_points': [
                COURSE_SALES_PROFILE['selling_point'],
                COURSE_SALES_PROFILE['content'],
                COURSE_SALES_PROFILE['replay'],
                COURSE_SALES_PROFILE['gifts'],
            ],
            'pain_points': ['家长不知道图书资源怎么用', '孩子英语发音和拼读基础弱', '家长担心时间冲突', '报名后不知道怎么交付'],
            'objections': ['不买/考虑', '和其他课冲突', '没时间', '孩子年级不确定', '链接打不开'],
            'audience': ['大班至小学4年级家长', '自然拼读启蒙需求', '图书扫码资源用户', '微信/企微私域用户'],
            'enabled': True,
        }
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesProduct).where(
                persistence_sales.SalesProduct.uuid == COURSE_SALES_PRODUCT_UUID
            )
        )
        if result.first() is None:
            await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_sales.SalesProduct).values(product))
            return
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesProduct)
            .where(persistence_sales.SalesProduct.uuid == COURSE_SALES_PRODUCT_UUID)
            .values(**product)
        )

    async def _ensure_course_sales_workflow_pipeline(self) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == COURSE_SALES_WORKFLOW_PIPELINE_UUID
            )
        )
        existing_pipeline = result.first()
        if existing_pipeline is not None:
            existing_config = existing_pipeline.config if isinstance(existing_pipeline.config, dict) else {}
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == COURSE_SALES_WORKFLOW_PIPELINE_UUID)
                .values(
                    name='课程 销售模板',
                    description='用工作流编排承接图书资源、自然拼读课程答疑、报名链接、模拟雷达、图片和语音。',
                    emoji='📚',
                    config=self.build_course_sales_pipeline_config(existing_config=existing_config),
                    extensions_preferences={
                        'enable_all_plugins': True,
                        'enable_all_mcp_servers': True,
                        'plugins': [],
                        'mcp_servers': [],
                    },
                )
            )
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(
                uuid=COURSE_SALES_WORKFLOW_PIPELINE_UUID,
                name='课程 销售模板',
                description='用工作流编排承接图书资源、自然拼读课程答疑、报名链接、模拟雷达、图片和语音。',
                emoji='📚',
                for_version=self.ap.ver_mgr.get_current_version(),
                is_default=False,
                stages=default_stage_order.copy(),
                config=self.build_course_sales_pipeline_config(),
                extensions_preferences={
                    'enable_all_plugins': True,
                    'enable_all_mcp_servers': True,
                    'plugins': [],
                    'mcp_servers': [],
                },
            )
        )

    async def _ensure_course_sales_template_pipeline(self) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == COURSE_SALES_TEMPLATE_PIPELINE_UUID
            )
        )
        existing_pipeline = result.first()
        if existing_pipeline is not None:
            existing_config = existing_pipeline.config if isinstance(existing_pipeline.config, dict) else {}
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == COURSE_SALES_TEMPLATE_PIPELINE_UUID)
                .values(
                    name='课程销售模板',
                    description='用傻瓜式模板配置课程客服与销售，能力与工作流版一致。',
                    emoji='📘',
                    config=self.build_course_sales_template_pipeline_config(existing_config=existing_config),
                    extensions_preferences={
                        'enable_all_plugins': True,
                        'enable_all_mcp_servers': True,
                        'plugins': [],
                        'mcp_servers': [],
                    },
                )
            )
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(
                uuid=COURSE_SALES_TEMPLATE_PIPELINE_UUID,
                name='课程销售模板',
                description='用傻瓜式模板配置课程客服与销售，能力与工作流版一致。',
                emoji='📘',
                for_version=self.ap.ver_mgr.get_current_version(),
                is_default=False,
                stages=default_stage_order.copy(),
                config=self.build_course_sales_template_pipeline_config(),
                extensions_preferences={
                    'enable_all_plugins': True,
                    'enable_all_mcp_servers': True,
                    'plugins': [],
                    'mcp_servers': [],
                },
            )
        )

    async def _request_volcengine_tts(
        self,
        *,
        text: str,
        app_id: str,
        token: str,
        cluster: str,
        voice_type: str,
        encoding: str,
    ) -> str | None:
        if voice_type.endswith('_bigtts') or encoding == 'ogg_opus':
            audio_base64 = await self._request_volcengine_tts_ws(
                text=text,
                app_id=app_id,
                token=token,
                cluster=cluster,
                voice_type=voice_type,
                encoding=encoding,
            )
            if audio_base64:
                return audio_base64

        payload = {
            'app': {
                'appid': app_id,
                'token': token,
                'cluster': cluster,
            },
            'user': {'uid': 'langbot-task-assistant'},
            'audio': {
                'voice_type': voice_type,
                'encoding': encoding,
                'speed_ratio': 1.0,
                'volume_ratio': 1.0,
                'pitch_ratio': 1.0,
            },
            'request': {
                'reqid': str(uuid.uuid4()),
                'text': text,
                'text_type': 'plain',
                'operation': 'query',
            },
        }
        for authorization in (f'Bearer;{token}', f'Bearer {token}'):
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://openspeech.bytedance.com/api/v1/tts',
                    json=payload,
                    headers={'Authorization': authorization},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    data = await response.json(content_type=None)
            if response.status == 200 and data.get('code') == 3000 and data.get('data'):
                return data['data']
            self.ap.logger.warning(
                'Volcengine TTS request failed: status=%s code=%s message=%s',
                response.status,
                data.get('code'),
                data.get('message'),
            )
        return None

    async def _request_volcengine_tts_ws(
        self,
        *,
        text: str,
        app_id: str,
        token: str,
        cluster: str,
        voice_type: str,
        encoding: str,
    ) -> str | None:
        payload = {
            'app': {
                'appid': app_id,
                'token': token,
                'cluster': cluster,
            },
            'user': {'uid': 'langbot-task-assistant'},
            'audio': {
                'voice_type': voice_type,
                'encoding': encoding,
                'speed_ratio': 1.0,
                'volume_ratio': 1.0,
                'pitch_ratio': 1.0,
            },
            'request': {
                'reqid': str(uuid.uuid4()),
                'text': text,
                'text_type': 'plain',
                'operation': 'submit',
            },
        }
        body = gzip.compress(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        request_bytes = bytes([0x11, 0x10, 0x11, 0x00]) + len(body).to_bytes(4, 'big') + body

        for authorization in (f'Bearer;{token}', f'Bearer; {token}'):
            audio_chunks: list[bytes] = []
            try:
                async with websockets.connect(
                    'wss://openspeech.bytedance.com/api/v1/tts/ws_binary',
                    additional_headers={'Authorization': authorization},
                    open_timeout=10,
                    close_timeout=5,
                    max_size=None,
                ) as websocket:
                    await websocket.send(request_bytes)
                    async for message in websocket:
                        if isinstance(message, str):
                            continue
                        audio_chunk, is_final = self._parse_volcengine_tts_ws_audio_message(message)
                        if audio_chunk:
                            audio_chunks.append(audio_chunk)
                        if is_final:
                            break
                if audio_chunks:
                    return base64.b64encode(b''.join(audio_chunks)).decode('utf-8')
            except Exception as exc:
                self.ap.logger.warning('Volcengine TTS websocket request failed: %s', exc)
        return None

    @staticmethod
    def _parse_volcengine_tts_ws_audio_message(message: bytes) -> tuple[bytes, bool]:
        if len(message) < 4:
            raise ValueError('Volcengine TTS websocket response is too short')

        header_size = (message[0] & 0x0F) * 4
        message_type = (message[1] & 0xF0) >> 4
        message_flags = message[1] & 0x0F
        compression = message[2] & 0x0F
        payload = message[header_size:]

        if message_type == 0xB:
            if message_flags == 0:
                return b'', False
            if len(payload) < 8:
                raise ValueError('Volcengine TTS websocket audio payload is too short')
            sequence_number = int.from_bytes(payload[:4], 'big', signed=True)
            payload_size = int.from_bytes(payload[4:8], 'big', signed=False)
            return payload[8 : 8 + payload_size], sequence_number < 0

        if message_type == 0xF:
            if len(payload) < 8:
                raise ValueError('Volcengine TTS websocket error payload is too short')
            error_code = int.from_bytes(payload[:4], 'big', signed=False)
            error_size = int.from_bytes(payload[4:8], 'big', signed=False)
            error_payload = payload[8 : 8 + error_size]
            if compression == 1:
                error_payload = gzip.decompress(error_payload)
            error_message = error_payload.decode('utf-8', errors='replace')
            raise ValueError(f'Volcengine TTS websocket error {error_code}: {error_message}')

        return b'', False

    @staticmethod
    def _tts_mime_type(encoding: str) -> str:
        if encoding == 'ogg_opus':
            return 'audio/ogg'
        if encoding == 'wav':
            return 'audio/wav'
        return 'audio/mpeg'

    def _compact_tts_text(self, text: str) -> str:
        normalized = ' '.join((text or '').split())
        if len(normalized) > 350:
            return normalized[:350] + '。'
        return normalized

    def _has_image(self, message_chain: platform_message.MessageChain | list[platform_message.MessageComponent]) -> bool:
        return any(isinstance(component, platform_message.Image) for component in message_chain)

    def _has_voice(self, message_chain: platform_message.MessageChain | list[platform_message.MessageComponent]) -> bool:
        return any(isinstance(component, platform_message.Voice) for component in message_chain)


def audio_bytes_to_data_uri(audio_bytes: bytes, mime_type: str = 'audio/mpeg') -> str:
    return f'data:{mime_type};base64,{base64.b64encode(audio_bytes).decode("utf-8")}'
