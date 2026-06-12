from __future__ import annotations

import base64
import copy
import datetime
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from ....core import app
from ....entity.persistence import model as persistence_model
from ....entity.persistence import pipeline as persistence_pipeline
from ....entity.persistence import rag as persistence_rag
from ....entity.persistence import sales as persistence_sales
from ....provider.modelmgr import audio_content
from ....provider.modelmgr import asr_invoke
from ....provider.modelmgr import tts_invoke
from ....rag import embedding_bootstrap
from ....rag.knowledge import builtin_engine
from ....rag.knowledge.document_text import extract_text_from_bytes
from ....rag.knowledge.text_normalize import has_extractable_document_text, is_meaningful_document
from ....utils import paths as path_utils
from .pipeline_defaults import default_stage_order


TASK_ASSISTANT_SCENARIO = 'task_assistant_ant_af'
TASK_ASSISTANT_PIPELINE_UUID = 'task-assistant-ant-af-pipeline'
TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID = 'task-assistant-ant-af-template-pipeline'
DEFAULT_ASSISTANT_MODEL_UUID = ''
TASK_ASSISTANT_TTS_VOICE_TYPE = 'zh_female_yuanqinvyou_moon_bigtts'
COURSE_SALES_SCENARIO = 'course_sales_yuanfudao_phonics'
COURSE_SALES_WORKFLOW_PIPELINE_UUID = 'course-sales-workflow-pipeline'
COURSE_SALES_TEMPLATE_PIPELINE_UUID = 'course-sales-template-pipeline'
YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID = 'yuanfudao-enhanced-sales-template-pipeline'
YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID = 'yuanfudao-sales-knowledge-base'
BUILTIN_KNOWLEDGE_ENGINE_ID = builtin_engine.BUILTIN_KNOWLEDGE_ENGINE_ID
YUANFUDAO_KNOWLEDGE_PACK_DIR = 'templates/course-sales/yuanfudao-knowledge'
COURSE_SALES_PRODUCT_UUID = 'yuanfudao-phonics-course'
COURSE_SALES_TTS_MODEL_UUID = 'lnv-doubao-seed-tts-2-0-standard'
COURSE_SALES_TTS_VOICE_TYPE = 'zh_female_vv_uranus_bigtts'
COURSE_SALES_ASR_MODEL_UUID = 'lna-doubao-bigasr-flash'
COURSE_PURCHASE_CONFIRMATION_KEYWORDS = [
    '买了',
    '已报名',
    '支付了',
    '付了',
    '付过',
    '报名成功',
    '支付成功',
    '已支付',
    '已经支付',
    '已完成支付',
]
COURSE_PAYMENT_SCREENSHOT_KEYWORDS = ['付款截图', '支付截图', '付款成功', '订单截图', '订单已支付', '收款成功']
COURSE_SCREENSHOT_TEXT_KEYWORDS = ['截图', '截屏', '截个图', '截一下', '发图']
COURSE_SMALLTALK_KEYWORDS = [
    '你好',
    '您好',
    '在吗',
    '天气',
    '谢谢',
    '辛苦',
    '哈哈',
    '早上好',
    '中午好',
    '晚上好',
    '晚安',
    '收到',
    '好的',
    'ok',
]
ASSISTED_SCENARIOS = {TASK_ASSISTANT_SCENARIO, COURSE_SALES_SCENARIO}

COURSE_SALES_SIGNUP_LINK = (
    'https://m.yuanfudao.com/primary/templates/package?'
    'pageId=6641&solutionId=27246&keyfrom=yfd-qudaohezuo-xiaoxue-9yyy-CPA-yunti9-siyu-yangzy-yingtao3class'
)
COURSE_SALES_RADAR_LINK = COURSE_SALES_SIGNUP_LINK
COURSE_RESOURCE_CARD_LINK = (
    'https://mp.zhizhuma.com/webappv2/videoLecture/video-tbxvm9.htm?'
    'resId=99132427&idSign=f6b025&resType=104&bookId=593223&bookIdSign=04d70c&targetId=2207977'
    '&_wxPage=teaVideo&crId=71099576&crIdSign=4f6334&entityId=593223&entityType=1'
    '&_wxId=593223&_wxType=1&_wxSrc=116&_rand=1773575505347'
)
COURSE_RESOURCE_HISTORY_LINK = 'https://mp.bookln.cn/user/history/moment.htm'
COURSE_RESOURCE_MINI_PROGRAM = '#小程序://教辅好帮手/la0KWwjPCx8S26C'
COURSE_RESOURCE_GOODS_GROUP_LINK = 'https://d.codeup.cn/d/UVruQn'

COURSE_OPENING_MESSAGE = (
    '您的图书配套学习资源点击👇️下方卡片激活查看；\n'
    f'也可点击➡️查看扫码记录  {COURSE_RESOURCE_HISTORY_LINK}\n\n'
    f'✅ 搜本页答案，点击👉{COURSE_RESOURCE_MINI_PROGRAM}\n\n'
    f'✅ 出版社内购好物群：{COURSE_RESOURCE_GOODS_GROUP_LINK}'
)

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
        'keywords': ['买了', '已报名', '支付成功', '付了', '报名成功'],
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
            {
                'delay_minutes': 0,
                'message': '好的',
                'link_id': 'phonics_radar_apply',
                'send_link_card': True,
            },
            {
                'delay_minutes': 0,
                'message': '点开上面报名链接👆🏻支付9元成功了记添加一下班主任辅导老师微信，方便给孩子辅导不懂不会的家庭作业\n\n截图发下这边登记排课，把全科学习资料发给您',
                'link_id': 'phonics_radar_apply',
            },
            {'delay_minutes': 5, 'message': '家长领取到了吗？'},
            {
                'delay_minutes': 60,
                'message': '孩子家长，你好，这边您给小孩领取好了吗？因为后台的话，每个年级的名额都不多了。您没领的话，抽空领一下。',
            },
            {
                'delay_minutes': 0,
                'schedule_time': '21:30',
                'message': '晚上好家长，忙完了么？现在方便给孩子预约下吗，赠送的名额还给您保留着呢。一直等您，辛苦您看到的话回复我一下吧~',
            },
        ],
    },
    {
        'stage': 'not_buy',
        'label': '不买',
        'messages': [
            {
                'delay_minutes': 0,
                'message': '不好意思 报名还独家赠送小猿篮球/护脊书包/小猿手办/宇航员文具盒/铅笔/转笔刀，完课后随机发货其一。\n\n主要是赠送实物的名额，就这一周有。',
                'image_key': 'course-sales/phonics/gift_poster.jpeg',
            },
            {
                'delay_minutes': 0,
                'message': '我感觉可以试试。 这个自然拼读特别适合3-4年级的小朋友。咱们的课主打180次高频次开口跟读，还有AI黑科技精准纠音，让孩子“见词能拼、听音能写”！！\n\n你觉得呢',
            },
            {
                'delay_minutes': 0,
                'message': '报名链接卡片',
                'link_id': 'phonics_radar_apply',
                'send_link_card': True,
            },
        ],
    },
    {
        'stage': 'considering',
        'label': '考虑',
        'messages': [
            {
                'delay_minutes': 0,
                'message': '不好意思 报名还独家赠送小猿篮球/护脊书包/小猿手办/宇航员文具盒/铅笔/转笔刀，完课后随机发货其一。\n\n主要是赠送实物的名额，就这一周有。',
                'image_key': 'course-sales/phonics/gift_poster.jpeg',
            },
            {
                'delay_minutes': 0,
                'message': '我感觉可以试试。 这个自然拼读特别适合3-4年级的小朋友。咱们的课主打180次高频次开口跟读，还有AI黑科技精准纠音，让孩子“见词能拼、听音能写”！！\n\n你觉得呢',
            },
            {
                'delay_minutes': 0,
                'message': '报名链接卡片',
                'link_id': 'phonics_radar_apply',
                'send_link_card': True,
            },
        ],
    },
    {
        'stage': 'purchased',
        'label': '买了',
        'messages': [
            {
                'delay_minutes': 0,
                'message': '谢谢支持 报名后会跳出一个微信二维码，是指导老师的，添加一下 老师会提醒你上课的哈，没添加也没关系，开课时老师也会主动联系你，留意下老师的电话和短信',
            },
            {
                'delay_minutes': 0,
                'message': '家长这个是赠送的资料。您可以长按识别关注一下，有空都可以打开学。一周内会有老师跟您联系的哈，咱们这边注意留意短信，报名成功会短信分配班主任的。9元的猿辅导课程，您可以先下载一个【猿辅导素养课】的APP，里面是可以看到购买的课程和开课时间的。',
                'image_key': 'course-sales/phonics/gift_qr.jpeg',
            },
            {
                'delay_minutes': 0,
                'message': '实物的话，完课后 直接联系 猿辅导班主任就可以，想要什么私下和老师说哈',
            },
        ],
    },
    {
        'stage': 'no_reply',
        'label': '不回复',
        'messages': [
            {'delay_minutes': 1440, 'message': '继续群发', 'action': 'continue_long_term_broadcasts'},
        ],
    },
    {
        'stage': 'silence_revisit',
        'label': '沉默回访',
        'messages': [
            {'delay_minutes': 5, 'message': '家长领取到了吗？'},
            {
                'delay_minutes': 60,
                'message': '孩子家长，你好，这边您给小孩领取好了吗？因为后台的话，每个年级的名额都不多了。您没领的话，抽空领一下。',
            },
            {
                'delay_minutes': 0,
                'schedule_time': '21:30',
                'message': '晚上好家长，忙完了么？现在方便给孩子预约下吗，赠送的名额还给您保留着呢。一直等您，辛苦您看到的话回复我一下吧~',
            },
        ],
    },
    {
        'stage': 'radar_clicked',
        'label': '点雷达',
        'messages': [
            {'delay_minutes': 0, 'message': '家长，看您进入报名通道了，支付以后麻烦您发我支付成功截图或者报名成功的短信，我给您登记开课并赠送资料'},
            {
                'delay_minutes': 0,
                'message': '预约通道已经发给您了👆，支付成功以后截图给我哦，给您登记发赠课~',
                'link_id': 'phonics_radar_apply',
                'send_link_card': True,
            },
            {'delay_minutes': 5, 'message': '家长领取到了吗？'},
            {
                'delay_minutes': 60,
                'message': '孩子家长，你好，这边您给小孩领取好了吗？因为后台的话，每个年级的名额都不多了。您没领的话，抽空领一下。',
            },
            {
                'delay_minutes': 0,
                'schedule_time': '21:30',
                'message': '晚上好家长，忙完了么？现在方便给孩子预约下吗，赠送的名额还给您保留着呢。一直等您，辛苦您看到的话回复我一下吧~',
            },
        ],
    },
]

COURSE_LONG_TERM_BROADCASTS = [
    {
        'day': 1,
        'title': '自然拼读第一天上午',
        'time': '10:20',
        'message': (
            '感谢您使用我们出版社的图书，我们联合【猿辅导】申请的9元【自然拼读专项课】，适合大班-3年级！\n\n'
            '🔤 单词突破：告别死记硬背，见词能拼、听音能写\n'
            '🗣️ 纯正发音：纠正发音不准，让孩子自信开口\n'
            '📖 阅读实战：掌握3步法，轻松搞定绘本与听力\n\n'
            '💪 9元 = 360分钟配套视频 + 5次绘本阅读实践 + 180次开口练习 + 14天专属辅导老师伴学服务\n\n'
            '🎁 完课随机包邮到家一件：小猿宇航员文具盒、小猿篮球、小猿转笔刀、小猿减压护脊书包、小猿手办、桶装铅笔\n\n'
            '要不要让孩子学习下？'
        ),
        'image_key': '',
    },
    {
        'day': 1,
        'title': '自然拼读第一天下午',
        'time': '15:40',
        'message': (
            '只需9元，给孩子报一个吧！猿辅导的课程内容依据新课标设计，确保孩子所学知识符合最新教育标准，'
            '帮助孩子更好地掌握英语发音与拼读核心！'
        ),
        'image_key': '',
    },
    {
        'day': 2,
        'title': '自然拼读第二天上午',
        'time': '10:20',
        'message': (
            '宝贝家长，咱们这个“9元英语课”是支持回放的，完课随机包邮到家一件实物好礼🎁，实在不想您错过！\n\n'
            '不少家长没时间的话，也完全可以等有空的时候看回放。因为1-2年级孩子学一次可能学不会，多看几次就会了（这点真的比线下课强太多）👍\n\n'
            '确实是我个人觉得特别好，又很适合孩子现在的阶段，所以多提醒了您一次。宝贝家长觉得可以的话，抽一分钟报名下~我立马给您登记！'
        ),
        'image_key': '',
    },
    {
        'day': 2,
        'title': '自然拼读第二天晚上',
        'time': '21:20',
        'message': (
            '总共就9块钱10节课，9毛钱一回，还能三年无限制看回放，咱们完全可以让孩子试试。'
            '我们接触的多了，真的明白自然拼读是孩子学习英语的基础。'
        ),
        'image_key': '',
    },
    {
        'day': 3,
        'title': '自然拼读第三天上午',
        'time': '10:20',
        'message': (
            '在嘛？家长，无论学不学，给我个答复就行🤝 这也不是那种几百上千的。\n\n'
            '9元也就是一顿早饭钱，让孩子来感受体验一下效果也是好的嘛~\n\n'
            '🔤 从单词到短句，带着孩子系统进行自然拼读；\n'
            '📺 支持回放不用担心没时间，高效率提升孩子英语技能。\n\n'
            '优惠马上要截止了，所以我这边和您确定一下这个名额！'
        ),
        'image_key': '',
    },
    {
        'day': 3,
        'title': '自然拼读第三天晚上',
        'time': '21:20',
        'message': (
            '孩子也会压力大，作业也会拖拉、对英语也容易有畏难情绪。所以咱们需要的不是做更多的作业、上更多的课，'
            '而是找寻一个方法、一个孩子喜欢的方式，来增加孩子学习的兴趣。'
            '恰巧这个课就是孩子喜欢的，9块钱买不到吃亏试一试，您觉得呢？'
        ),
        'image_key': '',
    },
    {
        'day': 4,
        'title': '自然拼读第四天上午',
        'time': '10:20',
        'message': (
            '咱们猿辅导【5日自然拼读课】（专为5-12岁精心设计），只需9元，孩子特别喜欢学哟~\n\n'
            '学整整5天，相当于1节课才1块多。如果咱家孩子在单词发音、见词能拼、英语阅读方面需要加强的话，\n'
            '【要不要让孩子试着学一下？】\n\n'
            '⭐我直接发您专属报名通道，不需要您点复杂的链接就能领取。您也可以直接回复数字“1”，我先发您了解一下哦！'
        ),
        'image_key': '',
    },
    {
        'day': 4,
        'title': '自然拼读第四天下午',
        'time': '15:40',
        'message': (
            '家长，报名好了么？没时间可以看回放的，猿辅导作为大品牌，没有任何套路，没有其他额外收费了❤️'
        ),
        'image_key': '',
    },
    {
        'day': 5,
        'title': '自然拼读第五天上午',
        'time': '10:20',
        'message': (
            '咱们这边真心不考虑花9块钱，给孩子学习一些学习方法吗？要知道现在新教材改版了，难度升级！'
            '学习就更不能死记硬背！技巧最重要，学习方法技巧肯定没有错，花9元给孩子提升一下肯定没有错的宝贝家长！'
        ),
        'image_key': '',
    },
    {
        'day': 5,
        'title': '自然拼读第五天晚上',
        'time': '21:20',
        'message': '就9块钱因为划算，也希望咱家孩子也能试一试。',
        'image_key': '',
    },
    {
        'day': 6,
        'title': '自然拼读第六天上午',
        'time': '10:10',
        'message': (
            '猿辅导自然拼读特训课程：26个字母巧记法、48个音标拼读规则、18次自拼大爆炸、12次自然拼读、'
            '5次阅读绘本实践、14天贴心服务、180次开口练习、周末直播课(12课时)，一课时30分钟，课程三年有效。\n\n'
            '以上内容仅需9元！9元！9元！\n\n'
            '随机包邮到家一件【小猿宇航员文具盒、小猿篮球、小猿转笔刀、小猿减压护脊书包、小猿手办、桶装铅笔】'
        ),
        'image_key': '',
    },
    {
        'day': 6,
        'title': '自然拼读第六天晚上',
        'time': '21:20',
        'message': (
            '说一句心里话，其实9块钱给孩子买玩具、吃零食也就没有了，但知识不一样，知识是伴随孩子的一生的。'
            '古话3岁看大，7岁看老，您要给孩子将来做打算，孩子英语基础能力、学习习惯越早培养越好，'
            '您这边给孩子买了，我也好为孩子安排学习。'
        ),
        'image_key': '',
    },
    {
        'day': 7,
        'title': '自然拼读第七天下午',
        'time': '15:15',
        'message': (
            '怕您太忙没看到消息，再跟你说一下9块钱值不值：\n\n'
            '🔶5次绘本阅读实践，提升孩子英语阅读兴趣；\n'
            '🔶180次开口练习，表达提升，鼓励孩子多表达，提升口语、拼读能力；\n'
            '🔶360分钟配套视频，课堂高频输出！\n'
            '🔶14天专属辅导老师伴学服务\n'
            '🔶单词口语双提升，走对英语第一步！\n\n'
            '每天小半小时，不耽误其他课业还能学到外面学不到的阅读方法和技巧，何乐而不为呢？\n\n'
            '其实很简单，您回复1⭐学五天咱们看看效果就知道了。'
        ),
        'image_key': '',
    },
    {
        'day': 7,
        'title': '自然拼读第七天晚上',
        'time': '21:20',
        'message': (
            '总共就9块钱，10节课，不到1块钱一回，咱们完全可以让孩子试试。'
            '我们接触的多了，真的明白理解能力是孩子学习的基础。'
        ),
        'image_key': '',
    },
]

COURSE_IMAGE_BINDINGS = [
    {
        'step_id': 'gift_poster',
        'title': '完课好礼海报',
        'text': '表格内置素材：用户不买、考虑、问赠品、问完课礼时发送。不要再发送SOP截图。',
        'file_key': 'course-sales/phonics/gift_poster.jpeg',
        'trigger_intents': ['gift', 'objection', 'course_intro'],
        'enabled': True,
    },
    {
        'step_id': 'gift_qr',
        'title': '书课通资料二维码',
        'text': '表格内置素材：用户已报名/已支付后发送，引导长按识别关注，领取2026年最新幼小资源。',
        'file_key': 'course-sales/phonics/gift_qr.jpeg',
        'trigger_intents': ['purchased', 'resource_help', 'screenshot_help'],
        'enabled': True,
    },
]

COURSE_RADAR_CONFIG = {
    'enabled': True,
    'link_title': '猿辅导自然拼读9元体验课报名通道',
    'link_url': COURSE_SALES_RADAR_LINK,
    'tracking_base_path': '/api/v1/sales/radar/click',
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
        model_info = await self._resolve_primary_llm_model_info(query, workflow)
        supports_native_audio = audio_content.model_supports_native_audio(
            abilities=model_info.get('abilities') if isinstance(model_info.get('abilities'), list) else [],
            requester=str(model_info.get('requester') or ''),
            model_name=str(model_info.get('name') or ''),
        )
        self._rewrite_user_message_for_multimodal_task(query, supports_native_audio=supports_native_audio)
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
        selected_profile = intent.get('course_profile') if isinstance(intent.get('course_profile'), dict) else {}
        product_name = selected_profile.get('course_name')
        if product_name:
            user_message.content.append(
                provider_message.ContentElement.from_text(
                    f'\n\n[当前选中课程]\n{product_name}\n请围绕这条课程线回答，除非用户明确切换需求。'
                )
            )

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

    def _rewrite_user_message_for_multimodal_task(
        self,
        query: pipeline_query.Query,
        *,
        supports_native_audio: bool = False,
    ) -> None:
        """Keep task-assistant model input compatible with multimodal chat/vision/audio calls."""
        if not isinstance(getattr(query, 'user_message', None), provider_message.Message):
            return

        content: list[provider_message.ContentElement] = []
        plain_text = str(query.variables.get('user_message_text') or '').strip()
        has_voice = self._has_voice(query.message_chain)

        if plain_text:
            content.append(provider_message.ContentElement.from_text(plain_text))

        if has_voice:
            voice_hint = (
                '用户发来一条语音咨询。请按蚂蚁阿福实名认证办理场景回复，'
                '口吻像真人客服，短句、自然、适合语音播报；'
                '如果没有明确步骤信息，就先引导他从支付宝扫码下载或让他发当前页面截图。'
            )
            if supports_native_audio:
                self._append_native_voice_content(content, query.message_chain)
                content.append(provider_message.ContentElement.from_text(voice_hint))
            else:
                content.append(provider_message.ContentElement.from_text(voice_hint))

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
        session_key = self._query_session_key(query)
        voice_config = workflow.get('voice') if isinstance(workflow.get('voice'), dict) else {}
        course_voice_enabled = voice_config.get('enabled') is True
        query.variables['task_assistant_voice_reply'] = self._has_voice(query.message_chain) and course_voice_enabled
        model_info = await self._resolve_primary_llm_model_info(query, workflow)
        supports_native_audio = audio_content.model_supports_native_audio(
            abilities=model_info.get('abilities') if isinstance(model_info.get('abilities'), list) else [],
            requester=str(model_info.get('requester') or ''),
            model_name=str(model_info.get('name') or ''),
        )
        has_voice = self._has_voice(query.message_chain)
        if has_voice:
            asr_text = await self._transcribe_course_sales_voice(query, workflow)
            if asr_text:
                query.variables['course_sales_asr_text'] = asr_text
                query.variables['user_message_text'] = asr_text
                text = asr_text

        intent = self.classify_course_sales_intent(text, query.message_chain, workflow)
        intent = await self._apply_course_sales_rejection_policy(intent, text, workflow, session_key, query)
        query.variables['course_sales_radar_link'] = intent.get('link_url') or COURSE_SALES_RADAR_LINK
        await self._schedule_course_sales_outreach_for_query(query, workflow, intent)
        intent = self._apply_course_faq_short_answer(intent, text, workflow, query)
        query.variables['workflow_intent'] = intent
        self._rewrite_user_message_for_course_sales(query, intent, supports_native_audio=supports_native_audio)
        self._append_course_sales_control_context(query, intent)

        return {'handled': True, 'intent': intent}

    def classify_course_sales_intent(
        self,
        text: str,
        message_chain: platform_message.MessageChain | list[platform_message.MessageComponent],
        workflow: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = (text or '').strip().lower()
        workflow = workflow if isinstance(workflow, dict) else {}
        selected_profile = self._select_course_sales_profile(workflow, normalized)
        course_faqs = workflow.get('course_faqs') if isinstance(workflow.get('course_faqs'), list) else COURSE_FAQS
        stop_rules = workflow.get('stop_rules') if isinstance(workflow.get('stop_rules'), dict) else COURSE_STOP_RULES
        stop_policy = workflow.get('stop_policy') if isinstance(workflow.get('stop_policy'), dict) else {}
        immediate_stop_keywords = self._lower_keywords(stop_policy.get('immediate_stop_keywords'))
        explicit_rejection_keywords = self._lower_keywords(stop_policy.get('explicit_rejection_keywords'))
        if self._has_image(message_chain):
            if self._mentions_payment_screenshot_confirmation(normalized):
                return self._course_intent(
                    'purchased',
                    0.9,
                    '用户发送图片且文本提到支付或报名成功截图',
                    step_ids=['gift_qr'],
                    selected_profile=selected_profile,
                )
            return self._course_intent(
                'screenshot_help',
                0.9,
                '用户发送了截图，需要识别支付、报名、链接异常或资源页面卡点',
                step_ids=[],
                selected_profile=selected_profile,
            )
        if self._mentions_purchase_confirmation(normalized):
            return self._course_intent('purchased', 0.88, '用户疑似已购买或已报名', step_ids=['gift_qr'], selected_profile=selected_profile)
        if self._mentions_screenshot_text(normalized):
            return self._course_intent(
                'screenshot_help',
                0.84,
                '用户提到截图但尚未发送图片，需引导发送页面或支付截图并由视觉识别判断',
                step_ids=['gift_qr'],
                selected_profile=selected_profile,
            )
        if any(keyword in normalized for keyword in immediate_stop_keywords):
            return self._course_intent('stop', 0.96, '用户命中立即停发规则', step_ids=[], selected_profile=selected_profile)
        rejection_keywords = explicit_rejection_keywords or self._lower_keywords(stop_rules.get('stop_keywords'))
        if any(keyword in normalized for keyword in rejection_keywords):
            return self._course_intent(
                'explicit_rejection',
                0.9,
                '用户明确拒绝，按配置累计拒绝次数',
                step_ids=[],
                selected_profile=selected_profile,
            )
        if any(keyword in normalized for keyword in ['雷达', '点了', '点击', '打开链接', '看了报名', '进入报名']):
            return self._course_intent(
                'radar_clicked',
                0.86,
                '用户提到点击或进入报名通道，按雷达触发后跟进',
                step_ids=[],
                include_link=True,
                selected_profile=selected_profile,
            )
        resource_keywords = {keyword for faq in COURSE_RESOURCE_FAQS for keyword in faq.get('keywords', [])}
        if any(keyword.lower() in normalized for keyword in resource_keywords):
            return self._course_intent('resource_help', 0.82, '命中图书资源问题', step_ids=['gift_qr'], selected_profile=selected_profile)
        for faq in course_faqs:
            if any(str(keyword).lower() in normalized for keyword in faq.get('keywords', [])):
                intent = str(faq.get('intent') or 'course_intro')
                step_id = self._course_step_for_intent(intent)
                return self._course_intent(
                    intent,
                    0.82,
                    f'命中课程FAQ：{faq["question"]}',
                    step_ids=[step_id] if step_id else [],
                    selected_profile=selected_profile,
                )
        if self._has_voice(message_chain):
            return self._course_intent('course_intro', 0.76, '用户发送语音，按课程客服文字短句承接', step_ids=[], selected_profile=selected_profile)
        if any(keyword in normalized for keyword in ['报名', '购买', '怎么买', '要买', '链接', '领取']):
            return self._course_intent('purchase', 0.8, '用户咨询报名或购买方式', step_ids=[], include_link=True, selected_profile=selected_profile)
        if any(keyword in normalized for keyword in ['不回复', '没人', '没回']):
            return self._course_intent('no_reply', 0.68, '用户处于沉默跟进场景', step_ids=[], selected_profile=selected_profile)
        if self._is_course_sales_smalltalk(normalized):
            return self._course_intent(
                'smalltalk',
                0.66,
                '用户闲聊或寒暄，先自然回应，不主动塞课程话术',
                step_ids=[],
                selected_profile={'key': '', 'product_uuid': '', 'facts': {}},
            )
        if selected_profile.get('key') == 'reading_thinking':
            return self._course_intent(
                'reading_thinking_intro',
                0.78,
                '用户问题命中阅读写作或数学思维产品线',
                step_ids=['gift_poster'],
                selected_profile=selected_profile,
            )
        return self._course_intent('course_intro', 0.64, '默认按自然拼读课程介绍承接', step_ids=[], selected_profile=selected_profile)

    def _course_step_for_intent(self, intent: str) -> str:
        if intent in {'purchase', 'course_schedule', 'course_replay', 'link_error', 'radar_clicked'}:
            return ''
        if intent in {'purchased', 'screenshot_help'}:
            return 'gift_qr'
        if intent in {'gift', 'objection', 'course_intro', 'course_content', 'grade'}:
            return 'gift_poster'
        if intent in {'resource_help'}:
            return 'gift_qr'
        if intent in {'no_reply'}:
            return ''
        return 'gift_poster'

    def _lower_keywords(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(keyword).strip().lower() for keyword in value if str(keyword).strip()]

    def _course_sales_profiles(self, workflow: dict[str, Any]) -> list[dict[str, Any]]:
        profiles = workflow.get('course_profiles') if isinstance(workflow.get('course_profiles'), list) else []
        if not profiles:
            variables = workflow.get('variables') if isinstance(workflow.get('variables'), dict) else {}
            profiles = variables.get('course_profiles') if isinstance(variables.get('course_profiles'), list) else []
        if profiles:
            return [profile for profile in profiles if isinstance(profile, dict)]
        profile = workflow.get('course_profile') if isinstance(workflow.get('course_profile'), dict) else COURSE_SALES_PROFILE
        return [
            {
                'key': 'phonics',
                'product_uuid': COURSE_SALES_PRODUCT_UUID,
                'name': profile.get('course_name', '猿辅导英语自然拼读体验课'),
                'keywords': ['英语', '自然拼读', '拼读', '发音', '单词'],
                'facts': profile,
            }
        ]

    def _select_course_sales_profile(self, workflow: dict[str, Any], normalized_text: str) -> dict[str, Any]:
        profiles = self._course_sales_profiles(workflow)
        if not profiles:
            return {}
        for profile in profiles:
            keywords = self._lower_keywords(profile.get('keywords'))
            if any(keyword and keyword in normalized_text for keyword in keywords):
                return profile
        return profiles[0]

    def _mentions_purchase_confirmation(self, normalized: str) -> bool:
        return any(keyword in normalized for keyword in COURSE_PURCHASE_CONFIRMATION_KEYWORDS)

    def _mentions_payment_screenshot_confirmation(self, normalized: str) -> bool:
        return self._mentions_purchase_confirmation(normalized) or any(
            keyword in normalized for keyword in COURSE_PAYMENT_SCREENSHOT_KEYWORDS
        )

    def _mentions_screenshot_text(self, normalized: str) -> bool:
        return any(keyword in normalized for keyword in COURSE_SCREENSHOT_TEXT_KEYWORDS)

    def _is_course_sales_smalltalk(self, normalized: str) -> bool:
        if not normalized or len(normalized) > 40:
            return False
        sales_keywords = [
            '报名',
            '购买',
            '课程',
            '自然拼读',
            '英语',
            '数学',
            '思维',
            '语文',
            '链接',
            '支付',
            '付款',
            '截图',
            '资源',
            '多少钱',
            '价格',
            '上课',
            '回放',
            '老师',
            '不要',
            '不需要',
            '别发',
        ]
        if any(keyword in normalized for keyword in sales_keywords):
            return False
        return any(keyword in normalized for keyword in COURSE_SMALLTALK_KEYWORDS)

    async def _get_course_sales_explicit_rejection_count(self, session_key: str, query: pipeline_query.Query) -> int:
        sales_service = getattr(self.ap, 'sales_service', None)
        if sales_service is not None and hasattr(sales_service, 'get_course_sales_explicit_rejection_count'):
            try:
                return await sales_service.get_course_sales_explicit_rejection_count(session_key)
            except Exception as exc:
                logger = getattr(self.ap, 'logger', None)
                if logger is not None:
                    logger.warning('Failed to load course sales rejection count: %s', exc)
        progress = self._session_progress.get(session_key, {}) if session_key else {}
        return int(progress.get('course_sales_explicit_rejection_count') or 0)

    async def _increment_course_sales_explicit_rejection_count(
        self,
        session_key: str,
        query: pipeline_query.Query,
    ) -> int:
        sales_service = getattr(self.ap, 'sales_service', None)
        if sales_service is not None and hasattr(sales_service, 'increment_course_sales_explicit_rejection_count'):
            try:
                return await sales_service.increment_course_sales_explicit_rejection_count(query, session_key)
            except Exception as exc:
                logger = getattr(self.ap, 'logger', None)
                if logger is not None:
                    logger.warning('Failed to persist course sales rejection count: %s', exc)
        progress = self._session_progress.setdefault(session_key or '_course_sales_default', {})
        count = int(progress.get('course_sales_explicit_rejection_count') or 0) + 1
        progress['course_sales_explicit_rejection_count'] = count
        return count

    async def _apply_course_sales_rejection_policy(
        self,
        intent: dict[str, Any],
        text: str,
        workflow: dict[str, Any],
        session_key: str,
        query: pipeline_query.Query,
    ) -> dict[str, Any]:
        if intent.get('intent') != 'explicit_rejection':
            return intent
        stop_policy = workflow.get('stop_policy') if isinstance(workflow.get('stop_policy'), dict) else {}
        try:
            threshold = int(stop_policy.get('explicit_rejection_threshold') or 1)
        except (TypeError, ValueError):
            threshold = 1
        threshold = max(1, threshold)
        count = await self._increment_course_sales_explicit_rejection_count(session_key, query)
        intent['explicit_rejection_count'] = count
        if count >= threshold:
            intent['intent'] = 'stop'
            intent['reason'] = f'用户已连续明确拒绝 {count} 次，达到停发阈值'
        else:
            intent['intent'] = 'objection'
            intent['reason'] = f'用户第 {count} 次明确拒绝，先轻量回应并继续保留后续触达'
        return intent

    def _course_intent(
        self,
        intent: str,
        confidence: float,
        reason: str,
        *,
        step_ids: list[str],
        include_link: bool = False,
        selected_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected_profile = selected_profile if isinstance(selected_profile, dict) else {}
        profile_facts = selected_profile.get('facts') if isinstance(selected_profile.get('facts'), dict) else COURSE_SALES_PROFILE
        product_key = str(selected_profile.get('key') or 'phonics')
        selected_product_uuid = str(selected_profile.get('product_uuid') or COURSE_SALES_PRODUCT_UUID)
        if intent == 'smalltalk':
            profile_facts = {}
            product_key = ''
            selected_product_uuid = ''
        data: dict[str, Any] = {
            'intent': intent,
            'confidence': confidence,
            'reason': reason,
            'step_ids': step_ids,
            'max_images': 1 if step_ids else 0,
            'reply_mode': 'course_sales',
            'course_profile': profile_facts,
            'product_key': product_key,
            'selected_product_uuid': selected_product_uuid,
        }
        if include_link:
            data['link_url'] = COURSE_SALES_RADAR_LINK
            data['radar_enabled'] = True
        return data

    def _rewrite_user_message_for_course_sales(
        self,
        query: pipeline_query.Query,
        intent: dict[str, Any],
        *,
        supports_native_audio: bool = False,
    ) -> None:
        if not isinstance(getattr(query, 'user_message', None), provider_message.Message):
            return

        content: list[provider_message.ContentElement] = []
        plain_text = str(query.variables.get('user_message_text') or '').strip()
        if plain_text:
            content.append(provider_message.ContentElement.from_text(plain_text))
        if self._has_voice(query.message_chain):
            voice_hint = (
                '用户发来一条语音咨询。请按猿辅导自然拼读课程客服/销售场景回复，'
                '短句、自然、像真人客服；如果上方已有语音转写文本，必须按转写内容回答，'
                '不要泛泛回复“语音我听到了”；如果用户用语音咨询且语音回复已启用，可生成适合 TTS 的短句。'
            )
            if supports_native_audio:
                self._append_native_voice_content(content, query.message_chain)
                content.append(provider_message.ContentElement.from_text(voice_hint))
            else:
                content.append(provider_message.ContentElement.from_text(voice_hint))
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

    def _yuanfudao_knowledge_sections(self) -> list[dict[str, str]]:
        cached = getattr(self, '_yuanfudao_knowledge_sections_cache', None)
        if isinstance(cached, list):
            return cached

        sections: list[dict[str, str]] = []
        rag_files = [
            'templates/course-sales/yuanfudao-knowledge/rag/yuanfudao_markdown_corpus.md',
            'templates/course-sales/yuanfudao-knowledge/rag/yuanfudao_spreadsheet_catalog.md',
        ]
        for resource_path in rag_files:
            path = Path(path_utils.get_resource_path(resource_path))
            if not path.exists():
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            parts = re.split(r'(?m)^## 来源：', text)
            for index, part in enumerate(parts):
                part = part.strip()
                if not part:
                    continue
                if index == 0:
                    title = path.name
                    body = part
                else:
                    first_line, _, rest = part.partition('\n')
                    title = first_line.strip() or path.name
                    body = rest.strip()
                sections.append({'title': title, 'body': body})

        self._yuanfudao_knowledge_sections_cache = sections
        return sections

    def _yuanfudao_knowledge_keywords(self, text: str) -> list[str]:
        normalized = str(text or '')
        known_terms = [
            '自然拼读',
            '自拼',
            '卖点',
            '话术',
            'SOP',
            '私域',
            '课程货盘',
            '货盘',
            '价格',
            '回放',
            '赠品',
            '礼品',
            '阅读',
            '思维',
            '奥数',
            '人文',
            '英语',
            '报名',
            '支付',
            '截图',
            '班主任',
        ]
        return [term for term in known_terms if term.lower() in normalized.lower()]

    def _truncate_knowledge_excerpt(self, text: str, *, max_chars: int = 150) -> str:
        excerpt = re.sub(r'\s+', ' ', str(text or '')).strip()
        if len(excerpt) <= max_chars:
            return excerpt
        return excerpt[:max_chars].rstrip() + '…'

    def _select_yuanfudao_knowledge_snippets(self, text: str, *, limit: int = 1, min_score: int = 2) -> list[str]:
        keywords = self._yuanfudao_knowledge_keywords(text)
        if not keywords:
            return []

        scored: list[tuple[int, str, str]] = []
        for section in self._yuanfudao_knowledge_sections():
            haystack = f'{section["title"]}\n{section["body"]}'.lower()
            score = sum(2 if keyword.lower() in section['title'].lower() else 1 for keyword in keywords if keyword.lower() in haystack)
            if score >= min_score:
                scored.append((score, section['title'], section['body']))

        snippets: list[str] = []
        for _score, title, body in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]:
            lower_body = body.lower()
            match_positions = [lower_body.find(keyword.lower()) for keyword in keywords if keyword.lower() in lower_body]
            first_match = min((position for position in match_positions if position >= 0), default=0)
            start = max(0, first_match - 40)
            excerpt = self._truncate_knowledge_excerpt(body[start : start + 200])
            if excerpt:
                snippets.append(f'来源：{title}\n{excerpt}')
        return snippets

    def _is_single_user_question(self, text: str) -> bool:
        normalized = (text or '').strip()
        if not normalized or len(normalized) > 80:
            return False
        if normalized.count('?') + normalized.count('？') > 1:
            return False
        if any(marker in normalized for marker in ('还有', '另外', '以及', '顺便', '再问', '同时')):
            return False
        return True

    _COURSE_FAQ_SHORT_ANSWER_INTENTS = frozenset(
        {
            'course_schedule',
            'course_intro',
            'course_content',
            'course_replay',
            'course_conflict',
            'gift',
            'grade',
            'link_error',
            'reading_thinking_intro',
            'purchase',
            'purchased',
            'objection',
        }
    )

    def _faq_answer_for_intent(self, intent_name: str, workflow: dict[str, Any]) -> str | None:
        course_faqs = workflow.get('course_faqs') if isinstance(workflow.get('course_faqs'), list) else COURSE_FAQS
        for faq in course_faqs:
            if str(faq.get('intent') or '') != intent_name:
                continue
            answer = str(faq.get('answer') or '').strip()
            if answer:
                return self._truncate_knowledge_excerpt(answer, max_chars=150)
        return None

    def _apply_course_faq_short_answer(
        self,
        intent: dict[str, Any],
        text: str,
        workflow: dict[str, Any],
        query: pipeline_query.Query,
    ) -> dict[str, Any]:
        if '命中课程FAQ' not in str(intent.get('reason') or ''):
            return intent
        if not self._is_single_user_question(text):
            return intent
        intent_name = str(intent.get('intent') or '')
        if intent_name not in self._COURSE_FAQ_SHORT_ANSWER_INTENTS:
            return intent
        answer = self._faq_answer_for_intent(intent_name, workflow)
        if not answer:
            return intent
        updated = dict(intent)
        updated['faq_short_answer'] = answer
        updated['reply_mode'] = 'faq_polish'
        query.variables['_knowledge_base_uuids'] = []
        return updated

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
                f'本轮要给报名动作和报名链接卡片：{COURSE_SALES_RADAR_LINK}。'
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
        elif intent_name == 'smalltalk':
            control_text = (
                '\n\n[课程销售上下文]\n'
                '用户在闲聊或寒暄。先自然回应当前话题，最多一句轻轻带回学习或课程，不要发链接、不要塞话术。'
            )
        else:
            control_text = (
                '\n\n[课程销售上下文]\n'
                '直接回答用户当前问题，短句、像真人客服；不要整段塞话术或主动背书未问到的内容。'
            )

        faq_short_answer = str(intent.get('faq_short_answer') or '').strip()
        if faq_short_answer:
            control_text += (
                '\n\n[短答模板]\n'
                f'{faq_short_answer}\n'
                '请以此为核心轻量润色成真人客服口吻，不要扩写、不要堆话术，只答用户当前问题。'
            )

        course_profile = intent.get('course_profile') if isinstance(intent.get('course_profile'), dict) else {}
        product_key = str(intent.get('product_key') or '')
        course_name = str(course_profile.get('course_name') or '').strip()
        if course_name and intent_name != 'smalltalk':
            facts = [
                str(course_profile.get('price') or '').strip(),
                str(course_profile.get('duration') or '').strip(),
                str(course_profile.get('target_grade') or '').strip(),
                str(course_profile.get('replay') or '').strip(),
            ]
            fact_text = '；'.join(fact for fact in facts if fact)
            control_text += f'\n[当前选中课程]\n产品线：{product_key or "course"}；课程：{course_name}'
            if fact_text:
                control_text += f'；关键信息：{fact_text}'

        if not faq_short_answer and intent_name != 'smalltalk':
            user_text = str(query.variables.get('user_message_text') or '')
            snippets = self._select_yuanfudao_knowledge_snippets(user_text)
            if snippets:
                control_text += (
                    '\n\n[猿辅导知识库参考]\n'
                    '不得复述参考资料原文，只答用户当前问题。'
                    '价格、排期、权益、赠品以最新活动页和班主任通知为准。\n'
                    + snippets[0]
                )

        user_message.content.append(provider_message.ContentElement.from_text(control_text))

    async def _schedule_course_sales_outreach_for_query(
        self,
        query: pipeline_query.Query,
        workflow: dict[str, Any],
        intent: dict[str, Any],
    ) -> None:
        sales_service = getattr(self.ap, 'sales_service', None)
        if sales_service is None:
            return

        target = self._course_sales_target_from_query(query)
        if not target.get('bot_uuid') or not target.get('target_id'):
            return

        intent_name = str(intent.get('intent') or '')
        text = str(query.variables.get('user_message_text') or '')
        try:
            if intent_name == 'stop':
                await sales_service.disable_outreach_for_target(
                    bot_uuid=target['bot_uuid'],
                    target_type=target['target_type'],
                    target_id=target['target_id'],
                    segment_prefixes=['course-sales:'],
                )
                return

            if intent_name == 'purchased':
                await sales_service.disable_outreach_for_target(
                    bot_uuid=target['bot_uuid'],
                    target_type=target['target_type'],
                    target_id=target['target_id'],
                    segment_prefixes=['course-sales:broadcast', 'course-sales:followup'],
                )
                await self._schedule_course_sales_followup_sequence(target, workflow, 'purchased')
                return

            if await self._is_course_sales_first_contact(query):
                await self._schedule_course_sales_opening_for_target(target, workflow)
                await self._schedule_course_sales_broadcasts_for_target(target, workflow)

            followup_stage = self._course_followup_stage_for_intent(intent, text)
            if followup_stage:
                await self._schedule_course_sales_followup_sequence(target, workflow, followup_stage)
                if followup_stage in {'purchase', 'radar_clicked', 'reading_thinking_purchase'}:
                    await self._schedule_course_sales_silence_followup_if_needed(target, workflow, intent)
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Failed to schedule course sales outreach: %s', exc)

    async def handle_course_sales_contact_added(
        self,
        *,
        bot_uuid: str,
        target_type: str = 'person',
        target_id: str,
        pipeline_uuid: str = '',
        user_id: str = '',
        pipeline_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sales_service = getattr(self.ap, 'sales_service', None)
        if sales_service is None or not bot_uuid or not target_id:
            return {'handled': False, 'reason': 'missing sales service or target'}

        workflow = self.active_workflow_from_config(pipeline_config or {})
        if not self._is_course_sales_workflow(workflow):
            workflow = self.build_course_sales_workflow_config(
                template_config=self.build_course_sales_template_config(template_slug='yuanfudao-enhanced')
            )
            if not self._is_course_sales_workflow(workflow):
                return {'handled': False, 'reason': 'not course sales pipeline'}

        session_id = f'{target_type}_{target_id}'
        target = {
            'bot_uuid': bot_uuid,
            'target_type': target_type or 'person',
            'target_id': target_id,
            'session_id': session_id,
            'pipeline_uuid': pipeline_uuid,
            'user_id': user_id or target_id,
        }
        try:
            await self._schedule_course_sales_opening_for_target(target, workflow)
            await self._schedule_course_sales_broadcasts_for_target(target, workflow)
            sent = await sales_service.run_due_outreach_for_target(
                bot_uuid=bot_uuid,
                target_type=target_type or 'person',
                target_id=target_id,
            )
            return {'handled': True, 'scheduled': True, 'sent_immediately': sent}
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Failed to handle course sales contact added: %s', exc)
            return {'handled': False, 'reason': str(exc)}

    async def handle_course_sales_radar_event(
        self,
        *,
        bot_uuid: str,
        target_type: str,
        target_id: str,
        link_id: str = '',
        session_id: str = '',
        pipeline_uuid: str = '',
        event: str = 'link_open',
        pipeline_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workflow = self.active_workflow_from_config(pipeline_config or {})
        if not self._is_course_sales_workflow(workflow):
            workflow = self.build_course_sales_workflow_config(
                template_config=self.build_course_sales_template_config(template_slug='yuanfudao-enhanced')
            )
        target = {
            'bot_uuid': bot_uuid,
            'target_type': target_type or 'person',
            'target_id': target_id,
            'session_id': session_id or f'{target_type}_{target_id}',
            'pipeline_uuid': pipeline_uuid,
            'user_id': target_id,
        }
        stage_name = 'radar_clicked' if event in {'link_open', 'click_apply_button'} else 'silence_revisit'
        await self._schedule_course_sales_followup_sequence(target, workflow, stage_name)
        radar = workflow.get('radar') if isinstance(workflow.get('radar'), dict) else COURSE_RADAR_CONFIG
        rules = radar.get('rules') if isinstance(radar.get('rules'), list) else []
        matched_rule = next((rule for rule in rules if isinstance(rule, dict) and rule.get('event') == event), None)
        if matched_rule and matched_rule.get('message'):
            links = self._course_sales_links_by_id(workflow)
            link = links.get(link_id) if link_id else None
            components: list[dict[str, Any]] = [{'type': 'plain', 'text': str(matched_rule.get('message') or '')}]
            if link:
                components.append(self._course_link_component(link, target=target, workflow=workflow))
            await self._create_course_sales_outreach_plan(
                target,
                name=f'课程销售雷达跟进-{event}',
                segment=f'course-sales:radar:{event}',
                dedupe_parts=['radar', event, link_id, target.get('session_id', '')],
                scheduled_at=datetime.datetime.now()
                + datetime.timedelta(minutes=max(0, int(matched_rule.get('delay_minutes') or 0))),
                components=components,
            )
        return {'handled': True, 'event': event, 'stage': stage_name}

    async def _schedule_course_sales_silence_followup_if_needed(
        self,
        target: dict[str, str],
        workflow: dict[str, Any],
        intent: dict[str, Any],
    ) -> None:
        intent_name = str(intent.get('intent') or '')
        if intent_name in {'purchased', 'stop'}:
            return
        if intent_name not in {'purchase', 'radar_clicked', 'reading_thinking_purchase'}:
            return
        await self._schedule_course_sales_followup_sequence(target, workflow, 'silence_revisit')

    async def _ensure_course_sales_outreach_for_chatted_users(self) -> None:
        sales_service = getattr(self.ap, 'sales_service', None)
        if sales_service is None:
            return
        try:
            targets = await sales_service.get_chatted_outreach_targets(
                pipeline_uuids=[COURSE_SALES_TEMPLATE_PIPELINE_UUID]
            )
            workflow = self.build_course_sales_workflow_config(template_config=self.build_course_sales_template_config())
            for target in targets:
                await self._schedule_course_sales_broadcasts_for_target(target, workflow)
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Failed to backfill course sales outreach for chatted users: %s', exc)

    def _course_sales_target_from_query(self, query: pipeline_query.Query) -> dict[str, str]:
        target_type = getattr(getattr(query, 'launcher_type', None), 'value', None) or str(getattr(query, 'launcher_type', 'person'))
        target_id = str(getattr(query, 'launcher_id', '') or '')
        session_id = str(getattr(query, 'variables', {}).get('session_id') or self._query_session_key(query))
        return {
            'bot_uuid': str(getattr(query, 'bot_uuid', '') or ''),
            'target_type': target_type,
            'target_id': target_id,
            'session_id': session_id,
            'pipeline_uuid': str(getattr(query, 'pipeline_uuid', '') or ''),
            'user_id': str(getattr(query, 'sender_id', '') or target_id),
        }

    async def _is_course_sales_first_contact(self, query: pipeline_query.Query) -> bool:
        sales_service = getattr(self.ap, 'sales_service', None)
        if sales_service is None:
            return False
        session_id = str(getattr(query, 'variables', {}).get('session_id') or self._query_session_key(query))
        return await sales_service.count_user_messages_for_session(session_id) <= 1

    def _course_followup_stage_for_intent(self, intent: dict[str, Any], text: str) -> str:
        intent_name = str(intent.get('intent') or '')
        product_key = str(intent.get('product_key') or '')
        if product_key == 'reading_thinking' and intent_name in {
            'reading_thinking_intro',
            'course_intro',
            'course_content',
            'purchase',
        }:
            return 'reading_thinking_purchase'
        if intent_name in {'purchase', 'radar_clicked', 'no_reply'}:
            return intent_name
        if intent_name == 'objection':
            return 'considering' if '考虑' in text else 'not_buy'
        return ''

    async def _schedule_course_sales_opening_for_target(self, target: dict[str, str], workflow: dict[str, Any]) -> None:
        now = datetime.datetime.now()
        links = self._course_sales_links_by_id(workflow)
        resource_link = links.get('phonics_resource_card') or {
            'title': '图书配套学习资源卡片',
            'url': COURSE_RESOURCE_CARD_LINK,
            'description': '激活查看图书配套学习资源',
        }
        await self._create_course_sales_outreach_plan(
            target,
            name='课程销售首次开场白',
            segment='course-sales:opening:text',
            dedupe_parts=['opening', 'text', target.get('session_id', '')],
            scheduled_at=now,
            components=[{'type': 'plain', 'text': COURSE_OPENING_MESSAGE}],
        )
        await self._create_course_sales_outreach_plan(
            target,
            name='课程销售首次资源卡片',
            segment='course-sales:opening:resource-card',
            dedupe_parts=['opening', 'resource-card', target.get('session_id', '')],
            scheduled_at=now + datetime.timedelta(seconds=1),
            components=[self._course_link_component(resource_link, target=target, workflow=workflow)],
        )

    async def _schedule_course_sales_broadcasts_for_target(self, target: dict[str, str], workflow: dict[str, Any]) -> None:
        broadcasts = workflow.get('long_term_broadcasts') if isinstance(workflow.get('long_term_broadcasts'), list) else []
        now = datetime.datetime.now()
        for index, broadcast in enumerate(broadcasts):
            if not isinstance(broadcast, dict):
                continue
            message = str(broadcast.get('message') or '').strip()
            if not message:
                continue
            if self._contains_sop_image_reference(broadcast):
                continue
            day_offset = max(0, int(broadcast.get('day') or (index + 1)) - 1)
            scheduled_at = self._next_course_wall_clock(str(broadcast.get('time') or '10:05'), now) + datetime.timedelta(
                days=day_offset
            )
            await self._create_course_sales_outreach_plan(
                target,
                name=f"课程销售SOP定时群发 Day{broadcast.get('day') or index + 1}-{broadcast.get('time') or ''}",
                segment='course-sales:broadcast',
                dedupe_parts=['broadcast', broadcast.get('day') or index + 1, broadcast.get('time') or '', index, target.get('session_id', '')],
                scheduled_at=scheduled_at,
                components=[{'type': 'plain', 'text': message}],
            )

    async def _schedule_course_sales_followup_sequence(
        self,
        target: dict[str, str],
        workflow: dict[str, Any],
        stage_name: str,
    ) -> None:
        followups = workflow.get('followup_sequences') if isinstance(workflow.get('followup_sequences'), list) else []
        sequence = next((item for item in followups if isinstance(item, dict) and item.get('stage') == stage_name), None)
        if not sequence:
            return
        links = self._course_sales_links_by_id(workflow)
        now = datetime.datetime.now()
        for index, message in enumerate(sequence.get('messages') or []):
            if not isinstance(message, dict):
                continue
            if message.get('action') == 'continue_long_term_broadcasts':
                await self._schedule_course_sales_broadcasts_for_target(target, workflow)
                continue
            components = self._course_followup_message_components(message, links, target=target, workflow=workflow)
            if not components:
                continue
            await self._create_course_sales_outreach_plan(
                target,
                name=f"课程销售主动跟进-{stage_name}-{index + 1}",
                segment=f'course-sales:followup:{stage_name}',
                dedupe_parts=['followup', stage_name, index, target.get('session_id', '')],
                scheduled_at=self._course_message_scheduled_at(message, now),
                components=components,
            )

    async def _create_course_sales_outreach_plan(
        self,
        target: dict[str, str],
        *,
        name: str,
        segment: str,
        dedupe_parts: list[Any],
        scheduled_at: datetime.datetime,
        components: list[dict[str, Any]],
    ) -> None:
        sales_service = getattr(self.ap, 'sales_service', None)
        if sales_service is None:
            return
        await sales_service.create_outreach_plan(
            {
                'name': name,
                'product_uuid': COURSE_SALES_PRODUCT_UUID,
                'bot_uuid': target.get('bot_uuid', ''),
                'target_type': target.get('target_type', 'person'),
                'target_id': target.get('target_id', ''),
                'segment': segment,
                'dedupe_key': self._course_sales_dedupe_key(target, dedupe_parts),
                'message_components': components,
                'scheduled_at': scheduled_at,
                'interval_minutes': 0,
                'enabled': True,
            }
        )

    def _course_followup_message_components(
        self,
        message: dict[str, Any],
        links: dict[str, dict[str, Any]],
        *,
        target: dict[str, str] | None = None,
        workflow: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        components: list[dict[str, Any]] = []
        text = str(message.get('message') or '').strip()
        if text and text not in {'报名链接', '报名链接卡片'}:
            components.append({'type': 'plain', 'text': text})
        link = links.get(str(message.get('link_id') or ''))
        if message.get('send_link_card') and link:
            components.append(self._course_link_component(link, target=target, workflow=workflow))
        image_key = str(message.get('image_key') or '').strip()
        if image_key:
            components.append({'type': 'image', 'file_key': image_key})
        return components

    def _course_sales_links_by_id(self, workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
        links = workflow.get('sales_links') if isinstance(workflow.get('sales_links'), list) else []
        return {str(link.get('id') or ''): link for link in links if isinstance(link, dict)}

    def _course_link_component(
        self,
        link: dict[str, Any],
        *,
        target: dict[str, str] | None = None,
        workflow: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = str(link.get('url') or '')
        radar_enabled = link.get('radar_enabled') is True
        if radar_enabled and target and url:
            sales_service = getattr(self.ap, 'sales_service', None)
            radar = {}
            if isinstance(workflow, dict):
                radar = workflow.get('radar') if isinstance(workflow.get('radar'), dict) else COURSE_RADAR_CONFIG
            if sales_service is not None and hasattr(sales_service, 'build_radar_tracking_url') and radar.get('enabled') is not False:
                url = sales_service.build_radar_tracking_url(
                    destination_url=url,
                    bot_uuid=target.get('bot_uuid', ''),
                    target_type=target.get('target_type', 'person'),
                    target_id=target.get('target_id', ''),
                    link_id=str(link.get('id') or ''),
                    session_id=target.get('session_id', ''),
                    pipeline_uuid=target.get('pipeline_uuid', ''),
                    tracking_base_path=str(radar.get('tracking_base_path') or '/api/v1/sales/radar/click'),
                )
        return {
            'type': 'link',
            'title': str(link.get('title') or '报名链接卡片'),
            'description': str(link.get('description') or ''),
            'url': url,
            'thumb_url': str(link.get('thumb_url') or ''),
        }

    def _course_sales_dedupe_key(self, target: dict[str, str], parts: list[Any]) -> str:
        raw = '|'.join(
            [
                target.get('bot_uuid', ''),
                target.get('target_type', ''),
                target.get('target_id', ''),
                *[str(part) for part in parts],
            ]
        )
        return f'course-sales:{uuid.uuid5(uuid.NAMESPACE_URL, raw).hex}'

    def _course_message_scheduled_at(self, message: dict[str, Any], now: datetime.datetime) -> datetime.datetime:
        schedule_time = str(message.get('schedule_time') or '').strip()
        if schedule_time:
            return self._next_course_wall_clock(schedule_time, now)
        try:
            delay_minutes = int(message.get('delay_minutes') or 0)
        except (TypeError, ValueError):
            delay_minutes = 0
        return now + datetime.timedelta(minutes=max(0, delay_minutes))

    def _next_course_wall_clock(self, value: str, now: datetime.datetime) -> datetime.datetime:
        hour, minute = 10, 5
        match = re.match(r'^\s*(\d{1,2}):(\d{1,2})\s*$', value or '')
        if match:
            hour = max(0, min(23, int(match.group(1))))
            minute = max(0, min(59, int(match.group(2))))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled <= now:
            scheduled += datetime.timedelta(days=1)
        return scheduled

    def _contains_sop_image_reference(self, value: dict[str, Any]) -> bool:
        image_key = str(value.get('image_key') or '')
        combined = ' '.join(str(item) for item in value.values())
        return bool(image_key) or any(token in combined for token in ['sop_doc_media', 'image1.png', 'image2.png', 'image3.png'])

    def compose_course_sales_prompt(self, workflow: dict[str, Any] | None = None) -> str:
        workflow = workflow if isinstance(workflow, dict) else {}
        stop_rules = workflow.get('stop_rules') if isinstance(workflow.get('stop_rules'), dict) else COURSE_STOP_RULES
        stop_keywords = '、'.join(stop_rules.get('stop_keywords', [])[:10])
        return f"""你是微信/企微私域里的真人课程客服兼销售，负责猿辅导体验课咨询。

人设与口吻：
- 不要自称 AI、机器人、智能助手。
- 像真人客服：短句、直接、自然；先回答用户当前问题，再视情况引导。
- 用户问图书资源，优先解决资源问题，不要急着推课。
- 用户发来语音时先理解内容；若已启用语音回复，输出适合 TTS 的短句。

禁则：
- 不承诺固定提分、效果翻倍、百分百有效等绝对化结果。
- 不夸大价格、赠品、课时、名额；强时效信息以活动页和班主任通知为准。
- 用户拒绝、投诉、无孩子、非目标年级、老师身份或人工接管时停止促单和群发。
- 用户已报名/已支付后停止促单，转交付（截图、班主任、APP、资料）。
- 停发关键词（命中即停止打扰）：{stop_keywords}

回复原则：
1. 只答用户当前问题，不要整段塞话术或主动背书未问到的内容。
2. 课程事实、FAQ、产品口径、雷达规则由运行时上下文按需注入，勿自行编造。
3. 需要报名时再发链接；不需要时不硬推。
4. 需要图片时由工作流追加素材，不要口头描述图片内容。
""".strip()

    async def synthesize_reply_voice(self, query: pipeline_query.Query, text: str) -> str | None:
        workflow = self.active_workflow_from_config(query.pipeline_config)
        if not self._is_assisted_workflow(workflow):
            return None
        if not query.variables.get('task_assistant_voice_reply'):
            return None

        voice_config = workflow.get('voice') if isinstance(workflow.get('voice'), dict) else {}
        voice_config = await self._resolve_voice_model_config(voice_config)
        if voice_config.get('enabled') is False:
            return None

        plain_text = self._compact_tts_text(text)
        if not plain_text:
            return None

        if not voice_config.get('encoding'):
            voice_config['encoding'] = tts_invoke.default_encoding_for_backend(
                tts_invoke.build_tts_invoke_config(voice_config, plain_text)
            )

        tts_config = tts_invoke.build_tts_invoke_config(voice_config, plain_text)
        audio_base64 = await tts_invoke.invoke_tts(tts_config, logger=self.ap.logger)
        if not audio_base64:
            return None
        encoding = tts_config.encoding or voice_config.get('encoding') or 'mp3'
        return f'data:{tts_invoke.tts_mime_type(encoding)};base64,{audio_base64}'

    async def _resolve_voice_model_config(self, voice_config: dict[str, Any]) -> dict[str, Any]:
        model_uuid = str(voice_config.get('model_uuid') or '')
        if not model_uuid:
            return voice_config

        resolved = copy.deepcopy(voice_config)
        model_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == model_uuid)
        )
        model = model_result.first()
        if model is None:
            return resolved

        model_name = getattr(model, 'name', None)
        if not resolved.get('model') and model_name:
            resolved['model'] = model_name
        extra_args = model.extra_args if isinstance(model.extra_args, dict) else {}
        for key in (
            'provider',
            'app_id',
            'token',
            'cluster',
            'voice_type',
            'voice',
            'encoding',
            'language_type',
            'base_url',
            'instructions',
            'optimize_instructions',
        ):
            if not resolved.get(key) and extra_args.get(key):
                resolved[key] = extra_args[key]

        provider_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == model.provider_uuid
            )
        )
        provider = provider_result.first()
        if provider is not None:
            resolved['requester'] = provider.requester or resolved.get('requester') or ''
            if not resolved.get('provider'):
                resolved['provider'] = provider.requester or provider.name
            base_url = getattr(provider, 'base_url', None)
            if not resolved.get('base_url') and base_url:
                resolved['base_url'] = base_url
            resolved = tts_invoke.apply_provider_api_keys(
                resolved,
                requester=provider.requester or '',
                api_keys=provider.api_keys if isinstance(provider.api_keys, list) else [],
            )

        return resolved

    def _is_dashscope_tts_config(self, voice_config: dict[str, Any]) -> bool:
        return tts_invoke.detect_tts_backend(tts_invoke.build_tts_invoke_config(voice_config, '')) == 'dashscope'

    async def ensure_default_resources(self) -> None:
        await self._ensure_task_images()
        await self._ensure_course_sales_images()
        await self._remove_seeded_workflow_mode_pipelines()
        await self._ensure_template_pipeline()
        await self._ensure_course_sales_template_pipeline()
        await self._ensure_yuanfudao_enhanced_template_pipeline()
        await self._ensure_builtin_pipeline_default_models()
        await self._ensure_course_sales_product()
        await self._ensure_course_sales_outreach_for_chatted_users()

    async def ensure_knowledge_resources(self) -> None:
        await self._ensure_yuanfudao_sales_knowledge_base()

    async def _get_first_configured_text_model_uuid(self) -> str:
        model_service = getattr(self.ap, 'llm_model_service', None)
        if model_service is None:
            self.ap.logger.warning('[DefaultModel] llm_model_service not available')
            return ''
        try:
            models = await model_service.get_llm_models(
                include_secret=False,
                include_space_models=False,
                include_system_models=False,
                only_configured_providers=True,
                model_category='text',
            )
        except Exception as e:
            self.ap.logger.warning('[DefaultModel] Failed to query models: %s', e)
            return ''
        if models:
            uuid = str(models[0].get('uuid') or '')
            self.ap.logger.info('[DefaultModel] Found %d configured text models, using first: %s', len(models), uuid)
            return uuid
        self.ap.logger.info('[DefaultModel] No configured text models found')
        return ''

    async def _ensure_builtin_pipeline_default_models(self) -> None:
        pipeline_uuids = [
            TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID,
            COURSE_SALES_TEMPLATE_PIPELINE_UUID,
            YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID,
        ]
        default_model_uuid = ''
        for pipeline_uuid in pipeline_uuids:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                    persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
                )
            )
            pipeline = result.first()
            if pipeline is None:
                self.ap.logger.debug('[DefaultModel] Pipeline %s not found, skipping', pipeline_uuid)
                continue
            config = pipeline.config if isinstance(pipeline.config, dict) else {}
            template_config = config.get('template_config') if isinstance(config.get('template_config'), dict) else {}
            current_model = str(template_config.get('model_uuid') or '')
            if current_model:
                self.ap.logger.debug('[DefaultModel] Pipeline %s already has model %s', pipeline_uuid, current_model)
                continue
            if not default_model_uuid:
                default_model_uuid = await self._get_first_configured_text_model_uuid()
            if not default_model_uuid:
                self.ap.logger.info('[DefaultModel] No default model available, skipping pipeline defaults')
                return
            self.ap.logger.info('[DefaultModel] Setting default model %s for pipeline %s', default_model_uuid, pipeline_uuid)
            template_config['model_uuid'] = default_model_uuid
            ai_config = config.get('ai') if isinstance(config.get('ai'), dict) else {}
            local_agent = ai_config.get('local-agent') if isinstance(ai_config.get('local-agent'), dict) else {}
            local_agent['model'] = {'primary': default_model_uuid, 'fallbacks': []}
            ai_config['local-agent'] = local_agent
            config['ai'] = ai_config
            config['template_config'] = template_config
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid)
                .values(config=config)
            )

    async def _remove_seeded_workflow_mode_pipelines(self) -> None:
        pipeline_uuids = [
            TASK_ASSISTANT_PIPELINE_UUID,
            COURSE_SALES_WORKFLOW_PIPELINE_UUID,
        ]
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid.in_(pipeline_uuids)
            )
        )
        pipeline_mgr = getattr(self.ap, 'pipeline_mgr', None)
        remove_pipeline = getattr(pipeline_mgr, 'remove_pipeline', None)
        if not callable(remove_pipeline):
            return
        for pipeline_uuid in pipeline_uuids:
            await remove_pipeline(pipeline_uuid)

    def build_pipeline_config(
        self,
        *,
        model_uuid: str = DEFAULT_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        config['ai']['runner']['runner'] = 'local-agent'
        config['ai']['runner']['expire-time'] = 0
        config['ai']['local-agent']['model'] = {'primary': model_uuid, 'fallbacks': []}
        config['ai']['local-agent']['max-round'] = 8
        config['ai']['local-agent']['prompt'] = [
            {'role': 'system', 'content': self.compose_system_prompt()},
        ]
        config['output']['misc']['at-sender'] = False
        config['output']['misc']['quote-origin'] = True
        existing_workflow = existing_config.get('workflow') if isinstance(existing_config, dict) else {}
        existing_voice = existing_workflow.get('voice') if isinstance(existing_workflow, dict) else {}
        config['workflow'] = self.build_workflow_config(
            model_uuid=model_uuid,
            voice_overrides=existing_voice if isinstance(existing_voice, dict) else None,
        )
        self._preserve_existing_basic_config(config, existing_config)
        return config

    def build_template_pipeline_config(
        self,
        *,
        model_uuid: str = DEFAULT_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing_template = existing_config.get('template_config') if isinstance(existing_config, dict) else {}
        template_config = self.build_template_config(
            overrides=existing_template if isinstance(existing_template, dict) else None,
        )
        effective_model_uuid = model_uuid or str(template_config.get('model_uuid') or '')
        config = self.build_pipeline_config(
            model_uuid=effective_model_uuid,
            existing_config=existing_config,
        )
        existing_workflow = existing_config.get('workflow') if isinstance(existing_config, dict) else None
        config['config_mode'] = 'template'
        config['template_config'] = template_config
        if isinstance(existing_workflow, dict) and existing_workflow:
            config['workflow'] = existing_workflow
        return config

    def _preserve_existing_basic_config(
        self,
        config: dict[str, Any],
        existing_config: dict[str, Any] | None,
    ) -> None:
        if not isinstance(existing_config, dict):
            return
        basic = existing_config.get('basic')
        if isinstance(basic, dict):
            config['basic'] = copy.deepcopy(basic)

    def _existing_pipeline_display_values(
        self,
        existing_pipeline: Any,
        *,
        default_name: str,
        default_description: str,
        default_emoji: str,
    ) -> dict[str, Any]:
        return {
            'name': getattr(existing_pipeline, 'name', None) or default_name,
            'description': getattr(existing_pipeline, 'description', None) or default_description,
            'emoji': getattr(existing_pipeline, 'emoji', None) or default_emoji,
        }

    def _existing_pipeline_extensions_preferences(self, existing_pipeline: Any) -> dict[str, Any]:
        preferences = getattr(existing_pipeline, 'extensions_preferences', None)
        if isinstance(preferences, dict):
            return copy.deepcopy(preferences)
        return {
            'enable_all_plugins': True,
            'enable_all_mcp_servers': True,
            'plugins': [],
            'mcp_servers': [],
        }

    def build_template_config(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        voice = {
            'provider': 'volcengine',
            'enabled': True,
            'model_uuid': '',
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
            'model_uuid': DEFAULT_ASSISTANT_MODEL_UUID,
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

        model_uuid = str(template_config.get('model_uuid') or DEFAULT_ASSISTANT_MODEL_UUID)
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

    def build_workflow_config(
        self,
        model_uuid: str = DEFAULT_ASSISTANT_MODEL_UUID,
        voice_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        voice_config = {
            'provider': 'volcengine',
            'enabled': True,
            'model_uuid': '',
            'app_id': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_APP_ID', ''),
            'token': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_TOKEN', ''),
            'cluster': 'volcano_tts',
            'voice_type': TASK_ASSISTANT_TTS_VOICE_TYPE,
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
                    'model_uuid': model_uuid,
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
                'config': {'knowledge_base_uuids': [], 'top_k': 2},
            },
            {
                'id': 'reply',
                'type': 'llm',
                'title': '真人客服式回复',
                'description': '生成自然、短句、可执行的下一步指引',
                'position': {'x': 3030, 'y': 260},
                'config': {
                    'model_uuid': model_uuid,
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
                    'model_uuid': '',
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
                'tts_provider': 'volcengine',
            },
            'nodes': nodes,
            'edges': edges,
            'voice': voice_config,
        }

    def _load_course_sales_template_by_slug(self, template_slug: str | None) -> dict[str, Any]:
        slug = str(template_slug or '').strip()
        if not slug:
            return {}
        safe_slug = re.sub(r'[^a-zA-Z0-9_-]', '', slug)
        if not safe_slug:
            return {}
        template_path = Path(path_utils.get_resource_path(f'templates/course-sales/{safe_slug}.json'))
        if not template_path.exists():
            return {}
        with open(template_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, dict) else {}

    def _merge_course_template_data(self, base: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
        merged = copy.deepcopy(base)
        for key, value in loaded.items():
            if key == 'voice' and isinstance(value, dict):
                current = merged.get('voice') if isinstance(merged.get('voice'), dict) else {}
                merged['voice'] = {**current, **copy.deepcopy(value)}
            elif key == 'tools' and isinstance(value, dict):
                current = merged.get('tools') if isinstance(merged.get('tools'), dict) else {}
                merged['tools'] = {**current, **copy.deepcopy(value)}
            elif key == 'memory' and isinstance(value, dict):
                current = merged.get('memory') if isinstance(merged.get('memory'), dict) else {}
                merged['memory'] = {**current, **copy.deepcopy(value)}
            elif key == 'scheduled_push' and isinstance(value, dict):
                current = merged.get('scheduled_push') if isinstance(merged.get('scheduled_push'), dict) else {}
                merged['scheduled_push'] = {**current, **copy.deepcopy(value)}
            elif key == 'metadata' and isinstance(value, dict):
                current = merged.get('metadata') if isinstance(merged.get('metadata'), dict) else {}
                merged['metadata'] = {**current, **copy.deepcopy(value)}
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    def build_course_sales_pipeline_config(
        self,
        *,
        model_uuid: str = DEFAULT_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
        template_slug: str | None = None,
        template_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        active_template = (
            copy.deepcopy(template_config)
            if isinstance(template_config, dict)
            else self.build_course_sales_template_config(template_slug=template_slug)
        )
        config['ai']['runner']['runner'] = 'local-agent'
        config['ai']['runner']['expire-time'] = 0
        config['ai']['local-agent']['model'] = {'primary': model_uuid, 'fallbacks': []}
        config['ai']['local-agent']['max-round'] = 8
        config['ai']['local-agent']['prompt'] = [
            {'role': 'system', 'content': self.compose_course_sales_prompt(active_template)},
        ]
        config['ai']['local-agent']['rerank-top-k'] = 2
        aggregation_config = config['trigger'].setdefault('message-aggregation', {})
        aggregation_config['enabled'] = True
        aggregation_config['delay'] = 3.0
        config['output']['force-delay'] = {'min': 0, 'max': 0}
        config['output']['misc']['at-sender'] = False
        config['output']['misc']['quote-origin'] = True
        existing_workflow = existing_config.get('workflow') if isinstance(existing_config, dict) else {}
        existing_voice = existing_workflow.get('voice') if isinstance(existing_workflow, dict) else {}
        config['workflow'] = self.build_course_sales_workflow_config(
            model_uuid=model_uuid,
            voice_overrides=existing_voice if isinstance(existing_voice, dict) else None,
            template_config=active_template,
        )
        tools = active_template.get('tools') if isinstance(active_template.get('tools'), dict) else {}
        kb_uuids = active_template.get('knowledge_base_uuids') if isinstance(active_template.get('knowledge_base_uuids'), list) else []
        if tools.get('knowledge_base'):
            config['ai']['local-agent']['knowledge-bases'] = [str(kb_uuid) for kb_uuid in kb_uuids if str(kb_uuid)]
        else:
            config['ai']['local-agent']['knowledge-bases'] = []
        self._preserve_existing_basic_config(config, existing_config)
        return config

    def build_course_sales_template_pipeline_config(
        self,
        *,
        model_uuid: str = DEFAULT_ASSISTANT_MODEL_UUID,
        existing_config: dict[str, Any] | None = None,
        template_slug: str | None = None,
    ) -> dict[str, Any]:
        existing_template = existing_config.get('template_config') if isinstance(existing_config, dict) else {}
        template_config = self.build_course_sales_template_config(
            overrides=existing_template if isinstance(existing_template, dict) else None,
            template_slug=template_slug,
        )
        effective_model_uuid = model_uuid or str(template_config.get('model_uuid') or '')
        config = self.build_course_sales_pipeline_config(
            model_uuid=effective_model_uuid,
            existing_config=existing_config,
            template_slug=template_slug,
            template_config=template_config,
        )
        existing_workflow = existing_config.get('workflow') if isinstance(existing_config, dict) else None
        config['config_mode'] = 'template'
        config['template_config'] = template_config
        if (
            isinstance(existing_workflow, dict)
            and existing_workflow
            and not self._is_course_sales_workflow(existing_workflow)
        ):
            config['workflow'] = existing_workflow
        return config

    def _is_legacy_course_opening_message(self, value: str) -> bool:
        return COURSE_RESOURCE_CARD_LINK in value or value.strip() != COURSE_OPENING_MESSAGE

    def _is_legacy_course_role_prompt(self, value: str) -> bool:
        return bool(
            'radar.yunti.local' in value
            or COURSE_RESOURCE_CARD_LINK in value
            or '发送带雷达参数的报名链接' in value
            or '课程统一口径：' in value
            or '图书资源FAQ：' in value
            or '雷达模拟规则：' in value
        )

    def _is_legacy_course_image_bindings(self, value: list[Any]) -> bool:
        step_ids = {str(item.get('step_id') or '') for item in value if isinstance(item, dict)}
        file_keys = {str(item.get('file_key') or '') for item in value if isinstance(item, dict)}
        return bool(
            {'resource_card', 'course_intro', 'registration_link', 'final_confirm'} & step_ids
            or any(('day1_' in key or 'day2_' in key or 'day3_' in key) for key in file_keys)
        )

    def _is_legacy_course_broadcasts(self, value: list[Any]) -> bool:
        if not value:
            return False
        image_keys = {str(item.get('image_key') or '') for item in value if isinstance(item, dict)}
        messages = '\n'.join(str(item.get('message') or '') for item in value if isinstance(item, dict))
        if '阅读+思维' in messages:
            return False
        return bool(
            any(('day1_' in key or 'day2_' in key or 'day3_' in key) for key in image_keys)
            or '9元共10节名师直播课' not in messages
            or '优惠马上要截止' not in messages
        )

    def _is_legacy_course_followups(self, value: list[Any]) -> bool:
        if not value:
            return False
        messages = [
            message
            for sequence in value
            if isinstance(sequence, dict)
            for message in sequence.get('messages', [])
            if isinstance(message, dict)
        ]
        stages = {str(sequence.get('stage') or '') for sequence in value if isinstance(sequence, dict)}
        if 'reading_thinking_purchase' in stages:
            return False
        has_signup_link = any(message.get('link_id') == 'phonics_radar_apply' for message in messages)
        has_poster = any(
            message.get('image_key')
            in {'course-sales/phonics/gift_poster.jpeg', 'course-sales/phonics/phonics_poster.jpeg'}
            for message in messages
        )
        has_gift_qr = any(message.get('image_key') == 'course-sales/phonics/gift_qr.jpeg' for message in messages)
        return bool({'objection'} & stages or not (has_signup_link and has_poster and has_gift_qr))

    def _is_legacy_course_sales_links(self, value: list[Any]) -> bool:
        if not value:
            return False
        ids = {str(item.get('id') or '') for item in value if isinstance(item, dict)}
        urls = {str(item.get('url') or '') for item in value if isinstance(item, dict)}
        zhizhuma_as_radar = any(
            isinstance(item, dict)
            and 'zhizhuma.com' in str(item.get('url') or '')
            and (item.get('id') != 'phonics_resource_card' or item.get('radar_enabled') is not False)
            for item in value
        )
        return bool(
            'phonics_resource_card' not in ids
            or any('radar.yunti.local' in url for url in urls)
            or zhizhuma_as_radar
        )

    def _normalize_course_radar_config(self, value: dict[str, Any]) -> dict[str, Any]:
        normalized = {**value}
        link_url = str(normalized.get('link_url') or '')
        if not link_url or 'radar.yunti.local' in link_url or 'zhizhuma.com' in link_url:
            normalized['link_url'] = COURSE_SALES_RADAR_LINK
        if not normalized.get('link_title'):
            normalized['link_title'] = COURSE_RADAR_CONFIG['link_title']
        return normalized

    def _normalize_course_media_key(self, value: Any) -> Any:
        if value == 'course-sales/phonics/phonics_poster.jpeg':
            return 'course-sales/phonics/gift_poster.jpeg'
        return value

    def _is_legacy_yuanfudao_source_materials(self, value: list[Any]) -> bool:
        if not value:
            return False
        joined = '\n'.join(str(item) for item in value)
        if 'yuanfudao_knowledge_index' in joined or '猿辅导销售知识库索引' in joined:
            return False
        return True

    def _refresh_yuanfudao_enhanced_template_fields(
        self,
        template_config: dict[str, Any],
        loaded_template: dict[str, Any],
    ) -> None:
        for key in (
            'source_materials',
            'knowledge_base_uuids',
            'course_profiles',
            'course_faqs',
            'product_uuids',
            'model_uuid',
            'voice',
            'asr',
            'screenshot_input',
        ):
            loaded_value = loaded_template.get(key)
            if key in {'voice', 'asr', 'screenshot_input'} and isinstance(loaded_value, dict):
                current = template_config.get(key) if isinstance(template_config.get(key), dict) else {}
                template_config[key] = {**current, **copy.deepcopy(loaded_value)}
            elif isinstance(loaded_value, list) and loaded_value:
                template_config[key] = copy.deepcopy(loaded_value)
            elif key == 'model_uuid' and loaded_value is not None:
                if str(loaded_value):
                    template_config[key] = str(loaded_value)
        loaded_metadata = loaded_template.get('metadata')
        if isinstance(loaded_metadata, dict):
            current_metadata = template_config.get('metadata') if isinstance(template_config.get('metadata'), dict) else {}
            template_config['metadata'] = {**current_metadata, **copy.deepcopy(loaded_metadata)}
        loaded_tools = loaded_template.get('tools')
        if isinstance(loaded_tools, dict) and loaded_tools.get('knowledge_base'):
            current_tools = template_config.get('tools') if isinstance(template_config.get('tools'), dict) else {}
            template_config['tools'] = {**current_tools, 'knowledge_base': True}

    _INVALID_PROVIDER_UUIDS = frozenset({'', '00000000-0000-0000-0000-000000000000'})

    async def _is_usable_embedding_model_uuid(self, model_uuid: str) -> bool:
        normalized = str(model_uuid or '').strip()
        if not normalized:
            return False
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.EmbeddingModel).where(
                persistence_model.EmbeddingModel.uuid == normalized
            )
        )
        row = result.first()
        if row is None:
            return False
        model_data = self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, row)
        provider_uuid = str(model_data.get('provider_uuid') or '').strip()
        if provider_uuid in self._INVALID_PROVIDER_UUIDS:
            return False
        provider_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == provider_uuid
            )
        )
        provider_row = provider_result.first()
        if provider_row is None:
            return False
        provider_data = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider_row)
        api_keys = provider_data.get('api_keys') or []
        return bool(api_keys) and bool(str(provider_data.get('base_url') or '').strip())

    async def _get_preferred_embedding_model_uuid(self) -> str:
        for candidate in embedding_bootstrap.PREFERRED_EMBEDDING_MODEL_UUIDS:
            if await self._is_usable_embedding_model_uuid(candidate):
                return candidate
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.EmbeddingModel).order_by(
                persistence_model.EmbeddingModel.prefered_ranking
            )
        )
        for row in result.all():
            model_data = self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, row)
            model_uuid = str(model_data.get('uuid') or '').strip()
            if await self._is_usable_embedding_model_uuid(model_uuid):
                return model_uuid
        return ''

    async def _ensure_yuanfudao_sales_knowledge_base(self) -> None:
        embedding_model_uuid = await self._get_preferred_embedding_model_uuid()
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.KnowledgeBase).where(
                persistence_rag.KnowledgeBase.uuid == YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID
            )
        )
        existing = result.first()
        rag_mgr = getattr(self.ap, 'rag_mgr', None)

        if existing is None:
            creation_settings = {'embedding_model_uuid': embedding_model_uuid} if embedding_model_uuid else {}
            kb_data: dict[str, Any] = {
                'uuid': YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID,
                'name': '猿辅导销售知识库',
                'description': '猿辅导课程销售话术、FAQ、产品资料与私域 SOP（2024-2026）',
                'emoji': '📚',
                'knowledge_engine_plugin_id': BUILTIN_KNOWLEDGE_ENGINE_ID,
                'collection_id': YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID,
                'creation_settings': creation_settings,
                'retrieval_settings': {'top_k': 2},
            }
            await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_rag.KnowledgeBase).values(kb_data))
            if rag_mgr is not None:
                try:
                    runtime_kb = await rag_mgr.load_knowledge_base(kb_data)
                    await runtime_kb._on_kb_create()
                except Exception as exc:
                    logger = getattr(self.ap, 'logger', None)
                    if logger is not None:
                        logger.warning('Failed to load Yuanfudao knowledge base into runtime: %s', exc)
        else:
            existing_data = self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, existing)
            updates: dict[str, Any] = {}
            if not existing_data.get('knowledge_engine_plugin_id'):
                updates['knowledge_engine_plugin_id'] = BUILTIN_KNOWLEDGE_ENGINE_ID
            creation_settings = existing_data.get('creation_settings') or {}
            current_embedding_uuid = str(creation_settings.get('embedding_model_uuid') or '').strip()
            if embedding_model_uuid and (
                not current_embedding_uuid
                or not await self._is_usable_embedding_model_uuid(current_embedding_uuid)
                or current_embedding_uuid in embedding_bootstrap.DEPRECATED_EMBEDDING_MODEL_UUIDS
            ):
                updates['creation_settings'] = {
                    **creation_settings,
                    'embedding_model_uuid': embedding_model_uuid,
                }
            if updates:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(persistence_rag.KnowledgeBase)
                    .values(updates)
                    .where(persistence_rag.KnowledgeBase.uuid == YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID)
                )
                if rag_mgr is not None:
                    merged = {**existing_data, **updates}
                    try:
                        await rag_mgr.remove_knowledge_base_from_runtime(YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID)
                        runtime_kb = await rag_mgr.load_knowledge_base(merged)
                        if not existing_data.get('knowledge_engine_plugin_id'):
                            await runtime_kb._on_kb_create()
                    except Exception as exc:
                        logger = getattr(self.ap, 'logger', None)
                        if logger is not None:
                            logger.warning('Failed to upgrade Yuanfudao knowledge base runtime: %s', exc)

        await self._import_yuanfudao_knowledge_documents_if_needed()

    async def _import_yuanfudao_knowledge_documents_if_needed(self) -> None:
        knowledge_service = getattr(self.ap, 'knowledge_service', None)
        rag_mgr = getattr(self.ap, 'rag_mgr', None)
        storage_mgr = getattr(self.ap, 'storage_mgr', None)
        logger = getattr(self.ap, 'logger', None)
        if knowledge_service is None or rag_mgr is None or storage_mgr is None:
            if logger is not None:
                logger.warning('Yuanfudao KB document import skipped: knowledge services not ready')
            return

        runtime_kb = await rag_mgr.get_knowledge_base_by_uuid(YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID)
        if runtime_kb is None:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_rag.KnowledgeBase).where(
                    persistence_rag.KnowledgeBase.uuid == YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID
                )
            )
            row = result.first()
            if row is None:
                if logger is not None:
                    logger.warning('Yuanfudao KB document import skipped: knowledge base record not found')
                return
            runtime_kb = await rag_mgr.load_knowledge_base(row)

        kb_info = await knowledge_service.get_knowledge_base(YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID)
        if kb_info is None:
            if logger is not None:
                logger.warning('Yuanfudao KB document import skipped: knowledge base record not found')
            return
        plugin_id = str(kb_info.get('knowledge_engine_plugin_id') or '')
        if not builtin_engine.is_builtin_knowledge_engine(plugin_id):
            if logger is not None:
                logger.warning(
                    'Yuanfudao KB document import skipped: knowledge base must use builtin engine (%s)',
                    plugin_id or 'unset',
                )
            return

        await self._retry_failed_yuanfudao_seed_documents(knowledge_service, logger)

        existing_files = await knowledge_service.get_files_by_knowledge_base(YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID)
        existing_names: set[str] = set()
        for file in existing_files:
            raw_name = str(file.get('file_name') or '')
            if raw_name:
                existing_names.add(raw_name)
                existing_names.add(Path(raw_name).name)

        import_targets = self._iter_yuanfudao_document_import_targets()
        queued_count = 0
        for full_path, file_name in import_targets:
            if file_name in existing_names:
                continue
            try:
                await storage_mgr.storage_provider.save(file_name, full_path.read_bytes())
                await knowledge_service.store_file(YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID, file_name)
                queued_count += 1
                if logger is not None:
                    logger.info('Queued Yuanfudao knowledge document import: %s', file_name)
            except Exception as exc:
                if logger is not None:
                    logger.warning(
                        'Failed to import Yuanfudao knowledge document %s: %s',
                        full_path,
                        exc,
                    )
        if logger is not None:
            logger.info(
                'Yuanfudao KB document import finished: queued %s new files (%s available, %s already present)',
                queued_count,
                len(import_targets),
                len(existing_names),
            )

    async def _retry_failed_yuanfudao_seed_documents(
        self,
        knowledge_service: Any,
        logger: Any,
    ) -> None:
        seed_names = {file_name for _, file_name in self._iter_yuanfudao_document_import_targets()}
        if not seed_names:
            return
        existing_files = await knowledge_service.get_files_by_knowledge_base(
            YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID
        )
        retry_count = 0
        for file in existing_files:
            if str(file.get('status') or '') != 'failed':
                continue
            raw_name = str(file.get('file_name') or '')
            if raw_name not in seed_names and Path(raw_name).name not in seed_names:
                continue
            file_uuid = str(file.get('uuid') or '').strip()
            if not file_uuid:
                continue
            try:
                await knowledge_service.delete_file(YUANFUDAO_SALES_KNOWLEDGE_BASE_UUID, file_uuid)
                retry_count += 1
            except Exception as exc:
                if logger is not None:
                    logger.warning('Failed to reset Yuanfudao seed document %s: %s', raw_name, exc)
        if logger is not None and retry_count > 0:
            logger.info('Reset %s failed Yuanfudao seed documents for retry', retry_count)

    def _yuanfudao_document_is_importable(self, full_path: Path) -> bool:
        if full_path.suffix.lower() != '.pdf':
            return True
        try:
            raw_text = extract_text_from_bytes(full_path.name, full_path.read_bytes())
        except OSError:
            return False
        return has_extractable_document_text(raw_text) and is_meaningful_document(raw_text)

    def _iter_yuanfudao_document_import_targets(self) -> list[tuple[Path, str]]:
        pack_dir = Path(path_utils.get_resource_path(YUANFUDAO_KNOWLEDGE_PACK_DIR))
        manifest_path = pack_dir / 'manifest.json'
        targets: list[tuple[Path, str]] = []

        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                manifest = {}
            for item in manifest.get('document_files') or []:
                if not isinstance(item, dict):
                    continue
                rel_path = str(item.get('path') or '').strip()
                if not rel_path:
                    continue
                full_path = pack_dir / rel_path
                if not full_path.is_file():
                    continue
                file_name = str(item.get('storage_name') or full_path.name)
                if Path(file_name).suffix.lower() in {'.ppt', '.pptx'}:
                    continue
                if not self._yuanfudao_document_is_importable(full_path):
                    continue
                targets.append((full_path, file_name))

        if targets:
            return targets

        documents_dir = pack_dir / 'documents'
        if not documents_dir.exists():
            return []
        for full_path in sorted(documents_dir.rglob('*')):
            if full_path.is_file() and full_path.suffix.lower() not in {'.ppt', '.pptx'}:
                if not self._yuanfudao_document_is_importable(full_path):
                    continue
                targets.append((full_path, full_path.name))
        return targets

    def _normalize_course_template_media_keys(self, template_config: dict[str, Any]) -> None:
        bindings = template_config.get('image_text_bindings')
        if isinstance(bindings, list):
            for binding in bindings:
                if isinstance(binding, dict) and 'file_key' in binding:
                    binding['file_key'] = self._normalize_course_media_key(binding.get('file_key'))
        sequences = template_config.get('followup_sequences')
        if isinstance(sequences, list):
            for sequence in sequences:
                if not isinstance(sequence, dict):
                    continue
                messages = sequence.get('messages')
                if not isinstance(messages, list):
                    continue
                for message in messages:
                    if isinstance(message, dict) and 'image_key' in message:
                        message['image_key'] = self._normalize_course_media_key(message.get('image_key'))

    def build_course_sales_template_config(
        self,
        overrides: dict[str, Any] | None = None,
        template_slug: str | None = None,
    ) -> dict[str, Any]:
        voice = {
            'provider': 'volcengine',
            'enabled': True,
            'model_uuid': COURSE_SALES_TTS_MODEL_UUID,
            'voice_type': COURSE_SALES_TTS_VOICE_TYPE,
            'encoding': 'ogg_opus',
        }
        asr = {
            'provider': 'volcengine',
            'model_uuid': COURSE_SALES_ASR_MODEL_UUID,
            'fallback_text': '用户发来课程咨询语音，请用文字短句回复。',
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
                    'SOP.doc（群发截图已转文字）',
                    '猿辅导自然拼读常见问题(1).xlsx',
                ],
            },
            'role_prompt': self.compose_course_sales_prompt(),
            'opening_message': COURSE_OPENING_MESSAGE,
            'recommended_questions': [
                '这个自然拼读课是什么？',
                '什么时候上课，支持回放吗？',
                '我想报名，怎么操作？',
                '我点了链接但卡住了怎么办？',
            ],
            'model_uuid': DEFAULT_ASSISTANT_MODEL_UUID,
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
            'asr': asr,
            'scheduled_push': scheduled_push,
            'course_profile': copy.deepcopy(COURSE_SALES_PROFILE),
            'resource_faqs': copy.deepcopy(COURSE_RESOURCE_FAQS),
            'course_faqs': copy.deepcopy(COURSE_FAQS),
            'sales_links': [
                {
                    'id': 'phonics_resource_card',
                    'title': '图书配套学习资源卡片',
                    'url': COURSE_RESOURCE_CARD_LINK,
                    'description': '首次打招呼发送，用于激活查看图书配套学习资源。',
                    'radar_enabled': False,
                },
                {
                    'id': 'phonics_radar_apply',
                    'title': '猿辅导自然拼读9元体验课报名通道',
                    'url': COURSE_SALES_RADAR_LINK,
                    'description': '报名链接卡片：模拟记录打开、浏览时长、点击报名、未支付等雷达事件。',
                    'radar_enabled': True,
                }
            ],
            'radar': copy.deepcopy(COURSE_RADAR_CONFIG),
            'followup_sequences': copy.deepcopy(COURSE_FOLLOWUP_SEQUENCES),
            'long_term_broadcasts': copy.deepcopy(COURSE_LONG_TERM_BROADCASTS),
            'stop_rules': copy.deepcopy(COURSE_STOP_RULES),
            'image_text_bindings': copy.deepcopy(COURSE_IMAGE_BINDINGS),
        }
        loaded_template = self._load_course_sales_template_by_slug(template_slug)
        if loaded_template:
            template_config = self._merge_course_template_data(template_config, loaded_template)
        if overrides:
            for key, value in overrides.items():
                if key == 'voice' and isinstance(value, dict):
                    template_config['voice'] = {**voice, **value}
                elif key == 'asr' and isinstance(value, dict):
                    current_asr = template_config.get('asr') if isinstance(template_config.get('asr'), dict) else asr
                    template_config['asr'] = {**current_asr, **value}
                elif key == 'tools' and isinstance(value, dict):
                    current_tools = template_config.get('tools') if isinstance(template_config.get('tools'), dict) else {}
                    template_config['tools'] = {**current_tools, **value}
                elif key == 'scheduled_push' and isinstance(value, dict):
                    template_config['scheduled_push'] = {**scheduled_push, **value}
                elif key == 'radar' and isinstance(value, dict):
                    template_config['radar'] = {
                        **COURSE_RADAR_CONFIG,
                        **self._normalize_course_radar_config(value),
                    }
                elif key in {'stop_rules', 'course_profile'} and isinstance(value, dict):
                    current = template_config.get(key) if isinstance(template_config.get(key), dict) else {}
                    template_config[key] = {**current, **value}
                elif key == 'opening_message' and isinstance(value, str):
                    if not self._is_legacy_course_opening_message(value):
                        template_config['opening_message'] = value
                elif key == 'role_prompt' and isinstance(value, str):
                    if not self._is_legacy_course_role_prompt(value):
                        template_config['role_prompt'] = value
                elif key == 'image_text_bindings' and isinstance(value, list) and value:
                    if not self._is_legacy_course_image_bindings(value):
                        template_config[key] = value
                elif key == 'long_term_broadcasts' and isinstance(value, list) and value:
                    if not self._is_legacy_course_broadcasts(value):
                        template_config[key] = value
                elif key == 'sales_links' and isinstance(value, list) and value:
                    if not self._is_legacy_course_sales_links(value):
                        template_config[key] = value
                elif key == 'followup_sequences' and isinstance(value, list) and value:
                    if not self._is_legacy_course_followups(value):
                        template_config[key] = value
                elif key == 'source_materials' and isinstance(value, list) and value:
                    if template_slug == 'yuanfudao-enhanced' and self._is_legacy_yuanfudao_source_materials(value):
                        pass
                    else:
                        template_config[key] = value
                elif key in {
                    'resource_faqs',
                    'course_faqs',
                    'course_profiles',
                } and isinstance(value, list) and value:
                    template_config[key] = value
                elif key == 'stop_policy' and isinstance(value, dict):
                    current = template_config.get(key) if isinstance(template_config.get(key), dict) else {}
                    template_config[key] = {**current, **value}
                else:
                    template_config[key] = value
        if template_slug == 'yuanfudao-enhanced' and loaded_template:
            self._refresh_yuanfudao_enhanced_template_fields(template_config, loaded_template)
        self._normalize_course_template_media_keys(template_config)
        template_config['role_prompt'] = self.compose_course_sales_prompt(template_config)
        for sequence in template_config.get('followup_sequences', []):
            if not isinstance(sequence, dict):
                continue
            for message in sequence.get('messages', []):
                if isinstance(message, dict):
                    message.pop('voice_optional', None)
        return template_config

    def build_course_sales_workflow_from_template_config(self, template_config: dict[str, Any]) -> dict[str, Any]:
        template_config = self.build_course_sales_template_config(overrides=template_config)
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
        model_uuid: str = DEFAULT_ASSISTANT_MODEL_UUID,
        voice_overrides: dict[str, Any] | None = None,
        template_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        template_config = template_config if isinstance(template_config, dict) else {}
        course_profile = (
            copy.deepcopy(template_config.get('course_profile'))
            if isinstance(template_config.get('course_profile'), dict)
            else copy.deepcopy(COURSE_SALES_PROFILE)
        )
        course_profiles = (
            copy.deepcopy(template_config.get('course_profiles'))
            if isinstance(template_config.get('course_profiles'), list)
            else [
                {
                    'key': 'phonics',
                    'product_uuid': COURSE_SALES_PRODUCT_UUID,
                    'name': course_profile.get('course_name', '猿辅导英语自然拼读体验课'),
                    'keywords': ['英语', '自然拼读', '拼读', '发音', '单词'],
                    'facts': copy.deepcopy(course_profile),
                }
            ]
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
        stop_policy = (
            copy.deepcopy(template_config.get('stop_policy'))
            if isinstance(template_config.get('stop_policy'), dict)
            else {
                'explicit_rejection_threshold': 1,
                'explicit_rejection_keywords': COURSE_STOP_RULES['stop_keywords'],
                'immediate_stop_keywords': ['投诉', '没有孩子', '没孩子', '打错', '我是老师', '已报名', '已支付'],
            }
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
                    'id': 'phonics_resource_card',
                    'title': '图书配套学习资源卡片',
                    'url': COURSE_RESOURCE_CARD_LINK,
                    'description': '首次打招呼发送，用于激活查看图书配套学习资源。',
                    'radar_enabled': False,
                },
                {
                    'id': 'phonics_radar_apply',
                    'title': '猿辅导自然拼读9元体验课报名通道',
                    'url': radar.get('link_url') or COURSE_SALES_RADAR_LINK,
                    'description': '报名链接卡片，支持模拟点击、浏览时长和未支付触发。',
                    'radar_enabled': True,
                }
            ]
        )
        image_bindings = (
            copy.deepcopy(template_config.get('image_text_bindings'))
            if isinstance(template_config.get('image_text_bindings'), list)
            else copy.deepcopy(COURSE_IMAGE_BINDINGS)
        )
        for binding in image_bindings:
            if isinstance(binding, dict) and 'file_key' in binding:
                binding['file_key'] = self._normalize_course_media_key(binding.get('file_key'))
        for sequence in followups:
            if not isinstance(sequence, dict):
                continue
            for message in sequence.get('messages', []):
                if isinstance(message, dict) and 'image_key' in message:
                    message['image_key'] = self._normalize_course_media_key(message.get('image_key'))
        opening_message = str(template_config.get('opening_message') or COURSE_OPENING_MESSAGE)
        model_uuid = str(template_config.get('model_uuid') or model_uuid)
        asr_config = template_config.get('asr') if isinstance(template_config.get('asr'), dict) else {}
        screenshot_config = (
            template_config.get('screenshot_input') if isinstance(template_config.get('screenshot_input'), dict) else {}
        )
        screenshot_model_uuid = str(screenshot_config.get('model_uuid') or model_uuid)
        asr_model_uuid = str(asr_config.get('model_uuid') or COURSE_SALES_ASR_MODEL_UUID)
        product_uuids = [
            str(profile.get('product_uuid') or '')
            for profile in course_profiles
            if isinstance(profile, dict) and str(profile.get('product_uuid') or '')
        ] or [COURSE_SALES_PRODUCT_UUID]
        template_name = str(template_config.get('name') or '课程销售模板')
        template_kb_uuids = [
            str(kb_uuid) for kb_uuid in (template_config.get('knowledge_base_uuids') or []) if str(kb_uuid)
        ]
        source_materials = (
            copy.deepcopy(template_config.get('source_materials'))
            if isinstance(template_config.get('source_materials'), list)
            else []
        )
        voice_config = {
            'provider': 'volcengine',
            'enabled': True,
            'model_uuid': COURSE_SALES_TTS_MODEL_UUID,
            'app_id': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_APP_ID', ''),
            'token': os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_TOKEN', ''),
            'cluster': 'seed-tts-2.0',
            'voice_type': COURSE_SALES_TTS_VOICE_TYPE,
            'encoding': 'ogg_opus',
        }
        if voice_overrides:
            for key, value in voice_overrides.items():
                if value is not None and key != 'encoding':
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
                'id': 'opening_message',
                'type': 'custom',
                'title': '首次开场白与资源卡片',
                'description': '用户加好友/首次进线时先发开场白，再单独发送图书配套学习资源卡片',
                'position': {'x': 340, 'y': 320},
                'config': {
                    'trigger': 'first_contact',
                    'message': opening_message,
                    'link_id': 'phonics_resource_card',
                    'link_url': COURSE_RESOURCE_CARD_LINK,
                    'send_link_card': True,
                    'radar_enabled': False,
                },
            },
            {
                'id': 'channel',
                'type': 'channel',
                'title': '渠道接入',
                'description': '统一接收网页、微信、企微、飞书等渠道消息',
                'position': {'x': 600, 'y': 320},
                'config': {'channels': ['web', 'wechat', 'wecom', 'lark'], 'keep_session': True},
            },
            {
                'id': 'media_router',
                'type': 'media',
                'title': '消息类型判断',
                'description': '区分文字、截图/图片和语音',
                'position': {'x': 860, 'y': 320},
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
                'position': {'x': 1160, 'y': 120},
                'config': {'output_key': 'user_text', 'params': '{"from": "message_chain.plain_text"}'},
            },
            {
                'id': 'voice_asr',
                'type': 'asr',
                'title': '语音输入处理',
                'description': '用户发语音时先理解课程咨询内容，语音回复开关开启时可用语音回复',
                'position': {'x': 1160, 'y': 320},
                'config': {
                    'provider': str(asr_config.get('provider') or 'volcengine'),
                    'model_uuid': asr_model_uuid,
                    'fallback_text': str(
                        asr_config.get('fallback_text') or '用户发来课程咨询语音，请用文字短句回复。'
                    ),
                },
            },
            {
                'id': 'screenshot_input',
                'type': 'vision',
                'title': '截图识别',
                'description': '识别支付成功页、报名页、白屏、资源页或二维码页',
                'position': {'x': 1160, 'y': 520},
                'config': {
                    'model_uuid': screenshot_model_uuid,
                    'target_steps': screenshot_config.get('target_steps')
                    if isinstance(screenshot_config.get('target_steps'), list)
                    else ['gift_poster', 'gift_qr', 'link_error'],
                },
            },
            {
                'id': 'intent',
                'type': 'intent',
                'title': '意图识别',
                'description': '识别资源、课程、购买、已报名、拒绝、投诉、雷达点击等状态',
                'position': {'x': 1460, 'y': 320},
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
                    ],
                    'confidence_threshold': 0.55,
                    'image_intents': screenshot_config.get('image_intents')
                    if isinstance(screenshot_config.get('image_intents'), list)
                    else ['screenshot_help', 'purchased', 'link_error'],
                },
            },
            {
                'id': 'stop_rules',
                'type': 'condition',
                'title': '停发规则',
                'description': '已报名、投诉、拒绝、人工接管、无孩子等状态停止群发和促单',
                'position': {'x': 1740, 'y': 320},
                'config': stop_rules,
            },
            {
                'id': 'resource_faq',
                'type': 'knowledge',
                'title': '图书资源FAQ',
                'description': '听力、答案、验证码、暂无资源、资源不对、下载等问题',
                'position': {'x': 2040, 'y': 80},
                'config': {
                    'resource_faqs': resource_faqs,
                    'knowledge_base_uuids': template_kb_uuids,
                    'top_k': 2,
                },
            },
            {
                'id': 'course_faq',
                'type': 'knowledge',
                'title': '课程FAQ',
                'description': '自然拼读课程介绍、上课时间、回放、赠品、冲突和年级适配',
                'position': {'x': 2040, 'y': 260},
                'config': {
                    'course_faqs': course_faqs,
                    'knowledge_base_uuids': template_kb_uuids,
                    'top_k': 2,
                },
            },
            {
                'id': 'course_product',
                'type': 'product',
                'title': '课程产品库',
                'description': '绑定猿辅导自然拼读体验课产品，输出价格、卖点、适龄和报名方式',
                'position': {'x': 2040, 'y': 440},
                'config': {
                    'product_uuids': product_uuids,
                    'course_profile': course_profile,
                    'course_profiles': course_profiles,
                },
            },
            {
                'id': 'sales_link',
                'type': 'custom',
                'title': '发送报名链接',
                'description': '发送指定报名链接卡片，雷达链接自动包装 tracking URL',
                'position': {'x': 2340, 'y': 440},
                'config': {'links': sales_links, 'link_url': radar.get('link_url') or COURSE_SALES_RADAR_LINK},
            },
            {
                'id': 'radar',
                'type': 'radar',
                'title': '链接点击雷达',
                'description': '通过 tracking URL 回调感知链接打开，并按规则触发跟进',
                'position': {'x': 2640, 'y': 440},
                'config': radar,
            },
            {
                'id': 'radar_followup',
                'type': 'outreach',
                'title': '主动跟进话术矩阵',
                'description': '按Excel跟进表在马上、5分钟、1小时、21:30主动跟进，必要时发送Excel素材图或报名链接卡片',
                'position': {'x': 2940, 'y': 440},
                'config': {'followup_sequences': followups, 'radar_rules': radar.get('rules', [])},
            },
            {
                'id': 'long_term_broadcast',
                'type': 'outreach',
                'title': 'SOP定时群发',
                'description': '按猿辅导1天2次群发SOP在每日指定时间群发；不发送SOP图片',
                'position': {'x': 2640, 'y': 700},
                'config': {'broadcasts': broadcasts, 'stop_rules': stop_rules, 'stop_policy': stop_policy},
            },
            {
                'id': 'handoff',
                'type': 'handoff',
                'title': '人工接管',
                'description': '投诉、高风险、订单纠纷或人工主动介入后停止AI和群发',
                'position': {'x': 2040, 'y': 700},
                'config': {'reason': '课程咨询需要人工处理', 'stop_ai_reply': True, 'stop_outreach': True},
            },
            {
                'id': 'reply',
                'type': 'llm',
                'title': '真人客服回复',
                'description': '按SOP生成短句、明确、有下一步的课程客服/销售回复',
                'position': {'x': 3240, 'y': 320},
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
                'id': 'end',
                'type': 'end',
                'title': '发送给用户',
                'description': '发送文字、链接卡片、Excel素材图；用户语音咨询时可按配置追加语音回复',
                'position': {'x': 3540, 'y': 420},
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
            {'id': 'e-start-opening', 'source': 'start', 'target': 'opening_message'},
            {'id': 'e-opening-channel', 'source': 'opening_message', 'target': 'channel'},
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
            {'id': 'e-reply-end', 'source': 'reply', 'target': 'end', 'label': '文字/图片/链接'},
        ]
        for binding in image_bindings:
            step_id = str(binding.get('step_id') or '')
            if not step_id:
                continue
            source = 'course_product'
            if step_id in {'gift_qr'}:
                source = 'course_faq'
            image_node_id = f'image_{step_id}'
            edges.extend(
                [
                    {'id': f'e-{source}-{image_node_id}', 'source': source, 'target': image_node_id},
                    {'id': f'e-{image_node_id}-reply', 'source': image_node_id, 'target': 'reply'},
                ]
            )

        return {
            'version': 1,
            'name': template_name,
            'description': '课程客服与销售工作流：图书资源承接、自然拼读课程答疑、报名转化、雷达跟进、停发与人工接管。',
            'metadata': {
                **(copy.deepcopy(template_config.get('metadata')) if isinstance(template_config.get('metadata'), dict) else {}),
                'scenario': COURSE_SALES_SCENARIO,
                'runtime_engine': 'langgraph',
                'source': ' + '.join(source_materials) if source_materials else 'SOP.doc（群发截图转文字）+ 猿辅导自然拼读常见问题(1).xlsx',
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
            'opening_message': opening_message,
            'course_profile': course_profile,
            'course_profiles': course_profiles,
            'resource_faqs': resource_faqs,
            'course_faqs': course_faqs,
            'sales_links': sales_links,
            'radar': radar,
            'followup_sequences': followups,
            'long_term_broadcasts': broadcasts,
            'stop_rules': stop_rules,
            'stop_policy': stop_policy,
            'source_materials': source_materials,
            'nodes': nodes,
            'edges': edges,
            'variables': {
                'customer_stage': 'resource_service',
                'intent': '',
                'opening_message': opening_message,
                'radar_event': {},
                'selected_product_uuid': product_uuids[0],
                'course_profiles': course_profiles,
                'source_materials': source_materials,
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
            display_values = self._existing_pipeline_display_values(
                existing_pipeline,
                default_name='任务助手模板配置版',
                default_description='用表单模板配置蚂蚁阿福实名认证引导，自动同步为可运行工作流。',
                default_emoji='✅',
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == TASK_ASSISTANT_TEMPLATE_PIPELINE_UUID)
                .values(
                    **display_values,
                    config=self.build_template_pipeline_config(existing_config=existing_config),
                    extensions_preferences=self._existing_pipeline_extensions_preferences(existing_pipeline),
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
        if result.first() is not None:
            return
        existing_product_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesProduct).limit(1)
        )
        if existing_product_result.first() is not None:
            return
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_sales.SalesProduct).values(product))

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
            display_values = self._existing_pipeline_display_values(
                existing_pipeline,
                default_name='课程销售模板',
                default_description='用傻瓜式模板配置课程客服与销售，能力与工作流版一致。',
                default_emoji='📘',
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == COURSE_SALES_TEMPLATE_PIPELINE_UUID)
                .values(
                    **display_values,
                    config=self.build_course_sales_template_pipeline_config(existing_config=existing_config),
                    extensions_preferences=self._existing_pipeline_extensions_preferences(existing_pipeline),
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

    async def _ensure_yuanfudao_enhanced_template_pipeline(self) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID
            )
        )
        existing_pipeline = result.first()
        if existing_pipeline is not None:
            existing_config = existing_pipeline.config if isinstance(existing_pipeline.config, dict) else {}
            display_values = self._existing_pipeline_display_values(
                existing_pipeline,
                default_name='猿辅导销售助手加强版',
                default_description='基于本地模板数据配置课程销售客服，支持多产品线、雷达跟进、图片识别和语音回复。',
                default_emoji='🎓',
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID)
                .values(
                    **display_values,
                    config=self.build_course_sales_template_pipeline_config(
                        existing_config=existing_config,
                        template_slug='yuanfudao-enhanced',
                    ),
                    extensions_preferences=self._existing_pipeline_extensions_preferences(existing_pipeline),
                )
            )
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(
                uuid=YUANFUDAO_ENHANCED_TEMPLATE_PIPELINE_UUID,
                name='猿辅导销售助手加强版',
                description='基于本地模板数据配置课程销售客服，支持多产品线、雷达跟进、图片识别和语音回复。',
                emoji='🎓',
                for_version=self.ap.ver_mgr.get_current_version(),
                is_default=False,
                stages=default_stage_order.copy(),
                config=self.build_course_sales_template_pipeline_config(template_slug='yuanfudao-enhanced'),
                extensions_preferences={
                    'enable_all_plugins': True,
                    'enable_all_mcp_servers': True,
                    'plugins': [],
                    'mcp_servers': [],
                },
            )
        )

    @staticmethod
    def _parse_volcengine_tts_ws_audio_message(message: bytes) -> tuple[bytes, bool]:
        return tts_invoke.parse_volcengine_tts_ws_audio_message(message)

    @staticmethod
    def _tts_mime_type(encoding: str) -> str:
        return tts_invoke.tts_mime_type(encoding)

    def _compact_tts_text(self, text: str) -> str:
        normalized = ' '.join((text or '').split())
        if len(normalized) > 350:
            return normalized[:350] + '。'
        return normalized

    def _has_image(self, message_chain: platform_message.MessageChain | list[platform_message.MessageComponent]) -> bool:
        return any(isinstance(component, platform_message.Image) for component in message_chain)

    def _has_voice(self, message_chain: platform_message.MessageChain | list[platform_message.MessageComponent]) -> bool:
        return any(isinstance(component, platform_message.Voice) for component in message_chain)

    def _append_native_voice_content(
        self,
        content: list[provider_message.ContentElement],
        message_chain: platform_message.MessageChain | list[platform_message.MessageComponent],
    ) -> None:
        for component in message_chain:
            if not isinstance(component, platform_message.Voice):
                continue
            voice_content = audio_content.voice_to_file_content(component)
            if voice_content is not None:
                content.append(voice_content)

    def _resolve_asr_model_uuid(
        self,
        query: pipeline_query.Query,
        workflow: dict[str, Any] | None = None,
    ) -> str:
        pipeline_config = getattr(query, 'pipeline_config', None)
        if isinstance(pipeline_config, dict):
            template_config = pipeline_config.get('template_config')
            if isinstance(template_config, dict):
                asr_config = template_config.get('asr') if isinstance(template_config.get('asr'), dict) else {}
                model_uuid = str(asr_config.get('model_uuid') or '').strip()
                if model_uuid:
                    return model_uuid

        workflow = workflow if isinstance(workflow, dict) else {}
        for node in workflow.get('nodes', []):
            if not isinstance(node, dict) or node.get('type') != 'asr':
                continue
            config = node.get('config') if isinstance(node.get('config'), dict) else {}
            model_uuid = str(config.get('model_uuid') or '').strip()
            if model_uuid:
                return model_uuid
        return ''

    async def _transcribe_course_sales_voice(
        self,
        query: pipeline_query.Query,
        workflow: dict[str, Any],
    ) -> str:
        model_uuid = self._resolve_asr_model_uuid(query, workflow)
        if not model_uuid:
            return ''

        voice_content: provider_message.ContentElement | None = None
        for component in query.message_chain:
            if isinstance(component, platform_message.Voice):
                voice_content = audio_content.voice_to_file_content(component)
                break
        if voice_content is None:
            return ''

        try:
            model_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == model_uuid)
            )
            model = model_result.first()
            if model is None:
                return ''

            provider_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_model.ModelProvider).where(
                    persistence_model.ModelProvider.uuid == model.provider_uuid
                )
            )
            provider = provider_result.first()
            if provider is None:
                return ''

            extra_args = model.extra_args if isinstance(model.extra_args, dict) else {}
            asr_config = asr_invoke.apply_provider_api_keys(
                {
                    'requester': provider.requester or '',
                    'provider': extra_args.get('provider') or provider.requester or '',
                    'model': model.name or '',
                    'base_url': provider.base_url or '',
                    'audio_base64': getattr(voice_content, 'file_base64', '') or '',
                    'audio_url': getattr(voice_content, 'file_url', '') or '',
                    'language_type': extra_args.get('language_type') or 'zh-CN',
                    **extra_args,
                },
                requester=provider.requester or '',
                api_keys=provider.api_keys if isinstance(provider.api_keys, list) else [],
            )
            text = await asr_invoke.invoke_asr(
                asr_invoke.build_asr_invoke_config(asr_config),
                logger=getattr(self.ap, 'logger', None),
            )
            return str(text or '').strip()
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning('Course sales ASR fallback failed: %s', exc)
            return ''

    def _resolve_primary_model_uuid(
        self,
        query: pipeline_query.Query,
        workflow: dict[str, Any] | None = None,
    ) -> str:
        pipeline_config = getattr(query, 'pipeline_config', None)
        if isinstance(pipeline_config, dict):
            template_config = pipeline_config.get('template_config')
            if isinstance(template_config, dict):
                model_uuid = str(template_config.get('model_uuid') or '').strip()
                if model_uuid:
                    return model_uuid

            ai_config = pipeline_config.get('ai')
            if isinstance(ai_config, dict):
                local_agent = ai_config.get('local-agent')
                if isinstance(local_agent, dict):
                    model_config = local_agent.get('model')
                    if isinstance(model_config, dict):
                        primary = str(model_config.get('primary') or '').strip()
                        if primary:
                            return primary

        workflow = workflow if isinstance(workflow, dict) else {}
        for node in workflow.get('nodes', []):
            if not isinstance(node, dict):
                continue
            if node.get('type') not in {'llm', 'vision', 'intent_router'}:
                continue
            config = node.get('config') if isinstance(node.get('config'), dict) else {}
            model_uuid = str(config.get('model_uuid') or '').strip()
            if model_uuid:
                return model_uuid
        return ''

    async def _resolve_primary_llm_model_info(
        self,
        query: pipeline_query.Query,
        workflow: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model_uuid = self._resolve_primary_model_uuid(query, workflow)
        if not model_uuid:
            return {}

        model_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == model_uuid)
        )
        model = model_result.first()
        if model is None:
            return {}

        info: dict[str, Any] = {
            'uuid': model_uuid,
            'name': getattr(model, 'name', '') or '',
            'abilities': model.abilities if isinstance(model.abilities, list) else [],
            'requester': '',
        }

        provider_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == model.provider_uuid
            )
        )
        provider = provider_result.first()
        if provider is not None:
            info['requester'] = provider.requester or provider.name or ''
        return info


def audio_bytes_to_data_uri(audio_bytes: bytes, mime_type: str = 'audio/mpeg') -> str:
    return f'data:{mime_type};base64,{base64.b64encode(audio_bytes).decode("utf-8")}'
