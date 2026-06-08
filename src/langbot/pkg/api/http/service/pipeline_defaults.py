from __future__ import annotations


default_stage_order = [
    'GroupRespondRuleCheckStage',  # 群响应规则检查
    'BanSessionCheckStage',  # 封禁会话检查
    'PreContentFilterStage',  # 内容过滤前置阶段
    'PreProcessor',  # 预处理器
    'ConversationMessageTruncator',  # 会话消息截断器
    'RequireRateLimitOccupancy',  # 请求速率限制占用
    'MessageProcessor',  # 处理器
    'ReleaseRateLimitOccupancy',  # 释放速率限制占用
    'PostContentFilterStage',  # 内容过滤后置阶段
    'ResponseWrapper',  # 响应包装器
    'LongTextProcessStage',  # 长文本处理
    'SendResponseBackStage',  # 发送响应
]
