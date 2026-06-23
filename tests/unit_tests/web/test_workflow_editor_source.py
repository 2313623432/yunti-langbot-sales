import re
from pathlib import Path


WORKFLOW_EDITOR_PATH = Path(
    'web/src/app/home/pipelines/components/workflow-editor/PipelineWorkflowEditor.tsx'
)
PIPELINE_FORM_PATH = Path(
    'web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx'
)
TEMPLATE_CONFIG_EDITOR_PATH = Path(
    'web/src/app/home/pipelines/components/workflow-editor/PipelineTemplateConfigEditor.tsx'
)
WORKFLOW_TEMPLATES_PATH = Path(
    'web/src/app/home/pipelines/components/workflow-editor/workflowTemplates.ts'
)
TYPES_PATH = Path('web/src/app/home/pipelines/components/workflow-editor/types.ts')
WORKFLOWS_PAGE_PATH = Path('web/src/app/home/workflows/page.tsx')
WORKFLOW_LIBRARY_PAGE_PATH = Path('web/src/app/home/workflows/WorkflowLibraryPage.tsx')
PIPELINE_PAGE_PATH = Path('web/src/app/home/pipelines/page.tsx')
PIPELINE_DETAIL_PATH = Path('web/src/app/home/pipelines/PipelineDetailContent.tsx')
SIDEBAR_CONFIG_PATH = Path('web/src/app/home/components/home-sidebar/sidbarConfigList.tsx')
ROUTER_PATH = Path('web/src/router.tsx')
ADD_MODEL_POPOVER_PATH = Path('web/src/app/home/components/models-dialog/components/AddModelPopover.tsx')
MODEL_ITEM_PATH = Path('web/src/app/home/components/models-dialog/components/ModelItem.tsx')
MODELS_DIALOG_PATH = Path('web/src/app/home/components/models-dialog/ModelsDialog.tsx')
SALES_CHAT_PAGE_PATH = Path('web/src/app/home/sales-chat/page.tsx')

PROVIDER_FORM_PATH = Path(
    'web/src/app/home/components/models-dialog/component/provider-form/ProviderForm.tsx'
)
BACKEND_CLIENT_PATH = Path('web/src/app/infra/http/BackendClient.ts')
API_ENTITIES_PATH = Path('web/src/app/infra/entities/api/index.ts')
PIPELINE_AUTO_TEST_PATH = Path(
    'web/src/app/home/pipelines/components/auto-test/PipelineAutoTestTab.tsx'
)
AUTO_TEST_PAGE_PATH = Path('web/src/app/home/auto-test/page.tsx')
TASK_ASSISTANT_SERVICE_PATH = Path('src/langbot/pkg/api/http/service/task_assistant.py')



def test_added_workflow_nodes_are_scrolled_into_view():
    source = WORKFLOW_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'canvasScrollRef' in source
    assert 'data-workflow-node-id' in source
    assert 'scrollIntoView' in source


def test_workflow_editor_supports_coze_style_drag_connections():
    source = WORKFLOW_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'draftConnection' in source
    assert 'handleConnectionStart' in source
    assert 'handleConnectionEnd' in source
    assert 'data-workflow-port="input"' in source
    assert 'data-workflow-port="output"' in source
    assert 'data-workflow-draft-edge' in source
    assert 'pointerEvents="stroke"' in source


def test_ai_reply_node_can_select_real_model_and_sync_to_pipeline():
    editor_source = WORKFLOW_EDITOR_PATH.read_text(encoding='utf-8')
    form_source = PIPELINE_FORM_PATH.read_text(encoding='utf-8')

    assert 'getProviderLLMModels' in editor_source
    assert 'llmModels' in editor_source
    assert "node.type === 'llm'" in editor_source
    assert 'model_uuid' in editor_source
    assert 'syncTemplateModelIntoAIConfig' in form_source
    assert "['local-agent']" in form_source
    assert 'primary: selectedModelUuid' in form_source
    assert form_source.count('ai: syncTemplateModelIntoAIConfig(templateConfig, values.ai)') == 3


def test_pipeline_editor_keeps_only_agent_template_config():
    form_source = PIPELINE_FORM_PATH.read_text(encoding='utf-8')
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'PipelineTemplateConfigEditor' in form_source
    assert 'config_mode' in form_source
    assert 'template_config' in form_source
    assert 'applyTemplateConfigToWorkflow' not in form_source
    assert 'Agent配置' in form_source
    assert 'Agent配置方式' not in form_source
    assert '工作流编排' not in form_source
    assert 'PipelineWorkflowEditor' not in form_source
    assert 'selectedConfigMode' not in form_source
    assert 'handleConfigModeChange' not in form_source

    assert 'scheduled_push' in template_source
    assert 'push_message' in template_source
    assert 'image_text_bindings' in template_source
    assert 'voice_type' in template_source


def test_template_mode_keeps_template_and_workflow_configs_independent():
    form_source = PIPELINE_FORM_PATH.read_text(encoding='utf-8')

    assert 'applyTemplateConfigToWorkflow' not in form_source
    assert 'const workflow = baseWorkflow' in form_source
    assert "form.setValue('template_config', templateConfig" in form_source
    assert "setWorkflowValue(applyTemplateConfigToWorkflow" not in form_source
    assert "selectedConfigMode === 'template'" not in form_source


def test_pipeline_save_also_syncs_real_scheduled_push_backend():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    form_source = PIPELINE_FORM_PATH.read_text(encoding='utf-8')

    assert 'scheduled_push_backend_synced' in template_source
    assert 'scheduled_push_backend_context' in template_source
    assert 'syncRealScheduledPushBackend' in form_source
    assert 'saveSalesScheduledPushConfig' in form_source
    assert 'await syncRealScheduledPushBackend(templateConfig)' in form_source


def test_pipeline_form_reload_effect_tracks_selected_pipeline_id():
    form_source = PIPELINE_FORM_PATH.read_text(encoding='utf-8')

    assert re.search(
        r"getPipeline\(pipelineId \|\| ''\)[\s\S]+}, \[form, isEditMode, pipelineId\]\);",
        form_source,
    )


def test_template_config_editor_supports_direct_image_upload_and_expanded_controls():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    form_source = PIPELINE_FORM_PATH.read_text(encoding='utf-8')

    assert 'httpClient.uploadImage' in template_source
    assert 'uploadingBindingId' in template_source
    assert 'type="file"' in template_source
    assert 'accept="image/*"' in template_source
    assert 'imageAssetUrl' in template_source
    assert 'addImageTextBinding' in template_source
    assert 'knowledge_base_uuids' in template_source
    assert 'product_uuids' in template_source
    assert 'useSidebarData' in template_source
    assert 'knowledgeBases.map' in template_source
    assert 'getSalesProducts' in template_source
    assert 'groupProductsByLine(salesProducts)' in template_source
    assert 'group.products.map' in template_source
    assert 'toggleTemplateListValue' in template_source
    assert '雷达跟进' in template_source
    assert 'interaction_radar' in template_source
    assert 'link_url' in template_source
    assert '客户可点击的链接' in template_source
    assert 'patchStringList' not in template_source
    assert 'selectedConfigMode' not in form_source
    assert "selectedConfigMode === 'template'" not in form_source
    assert 'overflow-y-auto' in form_source
    assert '每天推送' in template_source
    assert '指定单天' in template_source
    assert '图片文字绑定' in template_source


def test_template_tool_settings_expose_reply_controls():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    workflow_templates_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')
    tool_settings = re.search(
        r'function renderToolSettings\(\) \{([\s\S]+?)\n  function renderKnowledgeSettings',
        template_source,
    ).group(1)

    assert 'reply_controls' in template_source
    assert 'patchReplyControls' in template_source
    assert '多条回复' in tool_settings
    assert '合并回复' in tool_settings
    assert '合并等待时间' in tool_settings
    assert 'merge_reply_enabled' in tool_settings
    assert 'merge_delay_seconds' in tool_settings
    assert 'multi_reply_enabled' in tool_settings
    assert 'merge_delay_seconds: 10' in workflow_templates_source


def test_template_config_editor_supports_meme_library_controls():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    types_source = Path(
        'web/src/app/home/pipelines/components/workflow-editor/types.ts'
    ).read_text(encoding='utf-8')
    workflow_templates_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')

    assert 'PipelineTemplateMemeLibraryItem' in types_source
    assert 'memes?: PipelineTemplateMemeConfig' in types_source
    assert "  | 'memes'" in template_source
    assert "id: 'memes'" in template_source
    assert 'patchMemes' in template_source
    assert 'patchMemeLibraryItem' in template_source
    assert 'addMemeLibraryItem' in template_source
    assert 'removeMemeLibraryItem' in template_source
    assert 'uploadImageForMeme' in template_source
    assert 'trigger_keyword' in template_source
    assert 'meaning' in template_source
    assert 'usage_scene' in types_source
    assert 'usage_instruction' in types_source
    assert '使用场景' in template_source
    assert '使用说明' in template_source
    assert 'usage_scene:' in workflow_templates_source
    assert 'usage_instruction:' in workflow_templates_source
    assert 'large_enabled' in template_source
    assert 'feishu_native_enabled' in template_source
    assert 'smart_judge_enabled' in template_source
    assert '小表情最多几轮必须出现一次' in template_source
    assert '大表情最多几轮必须出现一次' in template_source
    assert '最少间隔轮数' not in template_source
    assert '替换表情包' in template_source
    assert '!builtin &&' not in re.search(
        r'function renderMemeSettings\(\) \{([\s\S]+?)\n  function renderMediaSettings',
        template_source,
    ).group(1)
    assert 'library_enabled' in template_source
    assert 'api_fallback_enabled' in template_source
    assert 'courseMemeConfig' in workflow_templates_source
    assert 'memes: courseMemeConfig' in workflow_templates_source
    assert 'memes: templateConfig.memes' in workflow_templates_source


def test_all_workflow_templates_share_meme_library_config():
    source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')
    for function_name in (
        'createSalesWorkflowTemplate',
        'createSupportWorkflowTemplate',
        'createBlankWorkflow',
        'createTaskAssistantWorkflowTemplate',
        'createCourseSalesWorkflowTemplate',
        'applyTemplateConfigToWorkflow',
    ):
        match = re.search(
            rf'export function {function_name}\([\s\S]+?\n\}}',
            source,
        )
        assert match, function_name
        body = match.group(0)
        assert 'memes:' in body, function_name
    assert source.count('memes: courseMemeConfig') >= 4
    assert source.count('memes: templateConfig.memes') >= 4


def test_meme_library_renders_builtin_stickers_without_internal_codes():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'builtinMemePreviewDataUrl' not in template_source
    assert 'memeStickerPreviewLabel' in template_source
    assert 'customMemePreviewSrc' in template_source
    assert 'const previewItems = library' in template_source
    assert '常用表情预览' in template_source
    assert '飞书官方表情' in template_source
    assert '内置安全表情包' in template_source
    assert 'sales-memes/${code}/${variant}.png' in WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')
    assert 'builtin:sales-meme' not in re.search(
        r'function renderMemeSettings\(\) \{([\s\S]+?)\n  function renderMediaSettings',
        template_source,
    ).group(1)
    assert '表情包图片 file_key' not in re.search(
        r'function renderMemeSettings\(\) \{([\s\S]+?)\n  function renderMediaSettings',
        template_source,
    ).group(1)


def test_template_model_capability_uses_configured_llm_model_select():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    model_settings = re.search(
        r'function renderModelSettings\(\) \{([\s\S]+?)\n  function renderToolSettings',
        template_source,
    ).group(1)
    media_settings = re.search(
        r'function renderMediaSettings\(\) \{([\s\S]+?)\n  function renderPanelByTab',
        template_source,
    ).group(1)

    assert 'getProviderLLMModels' in template_source
    assert "include_space_models: false" in template_source
    assert "include_system_models: false" in template_source
    assert "model_category: 'text'" in template_source
    assert "model_category: 'voice'" in template_source
    assert "model_category: 'asr'" in template_source
    assert 'chatLlmModels' in model_settings
    assert 'voiceModels' in model_settings
    assert 'asrModels' in model_settings
    assert 'handleVoiceModelChange' in model_settings
    assert 'handleAsrModelChange' in model_settings
    assert 'patchAsr' in template_source
    assert 'voiceToneOptionsFromModel' in template_source
    assert 'model_uuid' in model_settings
    assert "space-chat-completions" in template_source
    assert 'llmModels' in template_source
    assert '<Select' in template_source
    assert re.search(
        r"<SelectItem[\s\S]+key=\{model\.uuid\}[\s\S]+value=\{model\.uuid\}",
        template_source,
    )
    assert '选择模型' in template_source
    assert '识别上下文语义' in template_source
    assert '回复多样性' in template_source
    assert 'response_diversity' in template_source
    assert '语音回复模型' in model_settings
    assert '语音模型' in model_settings
    assert 'pipelines.templateConfig.asrModelSectionTitle' in model_settings
    assert 'pipelines.templateConfig.asrModelLabel' in model_settings
    assert '选择音色' in model_settings
    assert '自定义音色 ID' not in model_settings
    assert '音频编码' not in model_settings
    assert "tools: { ...config.tools, voice_reply: checked }" in model_settings
    assert '声音和形象' not in template_source
    assert '图文语音' not in template_source
    assert '语音回复模型' not in media_settings
    assert '最大思考次数' not in template_source
    assert 'max_reasoning_steps' not in template_source
    assert 'value={config.model_uuid}' not in template_source


def test_template_config_editor_exposes_multi_agent_orchestration_tab():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')
    types_source = TYPES_PATH.read_text(encoding='utf-8')

    assert "'orchestration'" in template_source
    assert "label: '智能体编排'" in template_source
    assert 'renderAgentOrchestrationSettings' in template_source
    assert 'PipelineTemplateAgentOrchestration' in types_source
    assert 'agent_orchestration' in workflow_source
    assert 'patchAgentOrchestration' in template_source
    assert 'profile_memory_enabled' in workflow_source
    assert 'debug_trace_enabled' in workflow_source
    assert '画像更新助手' in template_source
    assert '意图识别助手' in template_source
    assert '问题重写助手' in template_source
    assert '知识/产品检索' in template_source
    assert '回复生成助手' in template_source
    assert '跟进计划助手' in template_source


def test_template_config_editor_places_orchestration_after_role_settings():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')

    basic_index = template_source.index("{ id: 'basic', label: '基本信息'")
    role_index = template_source.index("{ id: 'role', label: '角色设定'")
    orchestration_index = template_source.index("{ id: 'orchestration', label: '智能体编排'")
    model_index = template_source.index("{ id: 'model', label: '模型能力'")

    assert basic_index < role_index < orchestration_index < model_index
    assert "useState<TemplateConfigTab>('basic')" in template_source


def test_template_config_editor_supports_agent_model_and_prompt_configuration():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    types_source = TYPES_PATH.read_text(encoding='utf-8')

    assert 'model_uuid?: string' in types_source
    assert 'model_extra_args?: Record<string, unknown>' in types_source
    assert 'prompt: string' in types_source
    assert 'patchAgentAssistant(safeActiveAssistantIndex, {' in template_source
    assert '子智能体提示词' in template_source
    assert '选择子智能体模型' in template_source
    assert 'agentModelOptions' in template_source
    assert 'courseAgentModelDisplayName' in template_source
    assert 'doubao seed2.0 mini' in template_source
    assert 'doubao seed2.0 pro' in template_source
    assert 'model_uuid:' in template_source
    assert 'model: courseAgentModelDisplayName' in template_source
    assert 'model_extra_args: modelExtraArgs(nextModel)' in template_source
    assert 'LEGACY_COURSE_AGENT_PROMPT_MARKERS' in template_source
    assert 'function resolveCourseAgentPrompt' in template_source
    assert 'prompt: resolveCourseAgentPrompt(defaultAssistant, incoming)' in template_source
    assert 'description: defaultAssistant.description' in template_source


def test_template_config_editor_hides_internal_orchestration_runtime_panels():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    render_agent_settings = template_source[
        template_source.index('function renderAgentOrchestrationSettings'):
        template_source.index('function renderBasicInfo')
    ]

    assert 'SelectItem value="multi_agent"' not in render_agent_settings
    assert 'SelectItem value="single_prompt"' not in render_agent_settings
    assert "mode: 'multi_agent'" in template_source
    assert 'toolSignals' not in render_agent_settings
    assert 'SummaryPill active={Boolean(enabled)}' not in render_agent_settings
    assert '已接入' not in render_agent_settings
    assert '未接入' not in render_agent_settings
    assert '调试链路' not in render_agent_settings
    assert 'DEBUG_TRACE_ITEMS' not in render_agent_settings
    assert '用户画像' not in render_agent_settings
    assert 'PROFILE_SIGNAL_ITEMS' not in render_agent_settings


def test_template_config_editor_explains_agent_runtime_orchestration():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    render_agent_settings = template_source[
        template_source.index('function renderAgentOrchestrationSettings'):
        template_source.index('function renderBasicInfo')
    ]

    assert '系统运行时按条件调用' in render_agent_settings
    assert '调用时机' in render_agent_settings
    assert '读取配置' in render_agent_settings
    assert '输出给' in render_agent_settings
    assert '调用规则' in render_agent_settings
    assert '角色设定' in render_agent_settings
    assert '知识和数据' in render_agent_settings
    assert '雷达跟进' in render_agent_settings
    assert '特殊情况处理' in render_agent_settings
    assert '客户消息进入后，系统运行时会按意图和上下文决定是否调用当前子智能体' in render_agent_settings


def _extract_agent_defaults(source: str) -> list[tuple[str, str, str]]:
    blocks = re.findall(
        r"\{\s*\n\s*(?:['\"])?id(?:['\"])?:\s*['\"]([^'\"]+)['\"][\s\S]*?\n\s*\}",
        source,
    )
    defaults: list[tuple[str, str, str]] = []
    for agent_id in blocks:
        start = source.find(f"id': '{agent_id}'")
        if start < 0:
            start = source.find(f"id: '{agent_id}'")
        if start < 0:
            continue
        end = source.find('\n        },', start)
        if end < 0:
            end = source.find('\n    },', start)
        block = source[start:end]
        if 'prompt' not in block:
            continue
        model_match = re.search(r"model_uuid['\"]?:\s*(COURSE_SALES_[A-Z_]+_MODEL_UUID)", block)
        prompt_match = re.search(r"prompt['\"]?:\s*'([^']+)'", block)
        if model_match and prompt_match:
            defaults.append((agent_id, model_match.group(1), prompt_match.group(1)))
        if len(defaults) == 6:
            break
    return defaults


def test_frontend_agent_defaults_match_backend_runtime_defaults():
    backend_source = TASK_ASSISTANT_SERVICE_PATH.read_text(encoding='utf-8')
    backend_source = backend_source[
        backend_source.index('COURSE_AGENT_ORCHESTRATION_CONFIG'):
        backend_source.index('COURSE_PAYMENT_SCREENSHOT_KEYWORDS')
    ]
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')

    assert _extract_agent_defaults(workflow_source) == _extract_agent_defaults(backend_source)


def test_template_config_editor_replaces_legacy_course_role_prompt():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'COMPACT_COURSE_ROLE_PROMPT' in template_source
    assert 'function isLegacyCourseRolePrompt' in template_source
    assert "'成交SOP'" in template_source
    assert "'通用成交SOP'" in template_source
    assert "'5分钟后追问'" in template_source
    assert 'function compactCourseRolePrompt' in template_source
    assert "value?.stop_rules?.stop_keywords || []" in template_source
    assert "replace('{{stop_keywords}}', stopKeywords)" in template_source
    assert '停发关键词（命中即停止打扰）' in template_source
    assert 'role_prompt: rolePrompt ?? defaults.role_prompt' in template_source
    assert '业务边界' in template_source
    assert '最终回复风格' in template_source


def test_frontend_course_stop_defaults_match_runtime_keywords():
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')

    for keyword in [
        '不想买',
        '不想报',
        '不想报名',
        '不想领取',
        '不领取',
        '不感兴趣',
        '没兴趣',
        '别来烦',
        '别联系',
        '滚',
        '骗子',
        '诈骗',
        '垃圾',
    ]:
        assert keyword in workflow_source
    assert "'已报名'" in workflow_source
    assert "'已支付'" in workflow_source


def test_frontend_course_gift_poster_triggers_match_runtime_defaults():
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')
    gift_binding = workflow_source[
        workflow_source.index("step_id: 'gift_poster'"):
        workflow_source.index("step_id: 'gift_qr'")
    ]

    assert "'course_intro'" not in gift_binding
    for intent in ['gift', 'objection', 'course_schedule', 'course_content', 'course_replay', 'course_conflict', 'purchase']:
        assert f"'{intent}'" in gift_binding


def test_frontend_course_faq_and_intent_defaults_match_runtime_intents():
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')

    for intent in [
        'reading_thinking_intro',
        'teacher_service',
        'course_conflict',
        'explicit_rejection',
        'grade',
        'link_error',
        'no_reply',
        'smalltalk',
        'clarification',
    ]:
        assert f"'{intent}'" in workflow_source
    assert '老师伴学服务是什么老师' in workflow_source
    assert '阅读+思维是什么课' in workflow_source
    assert '直播没赶上' in workflow_source
    assert "'卡住'" in workflow_source


def test_template_config_editor_uses_single_agent_card_with_left_right_switching():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'ChevronLeft' in template_source
    assert 'ChevronRight' in template_source
    assert 'activeAssistantIndex' in template_source
    assert 'setActiveAssistantIndex' in template_source
    assert 'previousAssistantIndex' in template_source
    assert 'nextAssistantIndex' in template_source
    assert 'activeAssistant' in template_source
    assert 'patchAgentAssistant(safeActiveAssistantIndex' in template_source
    assert '上一位子智能体' in template_source
    assert '下一位子智能体' in template_source
    assert 'assistants.map((assistant, index)' not in template_source
    render_agent_settings = template_source[
        template_source.index('function renderAgentOrchestrationSettings'):
        template_source.index('function renderBasicInfo')
    ]
    assert '输入：' not in render_agent_settings
    assert '输出：' not in render_agent_settings


def test_models_dialog_includes_pdf_parsing_category():
    source = MODELS_DIALOG_PATH.read_text(encoding='utf-8')

    assert "models.pdfCategory" in source
    assert "models.pdfParseAbility" in source
    assert "'pdf'" in source
    assert 'pdf_parse' in source
    assert 'FileText' in source


def test_model_configuration_can_mark_llm_models_as_tts_capable():
    add_model_source = ADD_MODEL_POPOVER_PATH.read_text(encoding='utf-8')
    model_item_source = MODEL_ITEM_PATH.read_text(encoding='utf-8')

    assert 'ttsAbility' in add_model_source
    assert 'ttsAbility' in model_item_source
    assert re.search(r"toggleScannedModelAbility\(\s*model\.id,\s*'tts'", add_model_source)
    assert re.search(r"abilities\?\.includes\('tts'\)", model_item_source)


def test_model_configuration_supports_asr_models():
    add_model_source = ADD_MODEL_POPOVER_PATH.read_text(encoding='utf-8')
    model_item_source = MODEL_ITEM_PATH.read_text(encoding='utf-8')
    models_dialog_source = MODELS_DIALOG_PATH.read_text(encoding='utf-8')

    assert 'asrAbility' in add_model_source
    assert 'asrAbility' in model_item_source
    assert 'asrCategory' in models_dialog_source
    assert 'test_audio_base64' in models_dialog_source
    assert 'asrTestStart' in models_dialog_source
    assert re.search(r"toggleScannedModelAbility\(\s*model\.id,\s*'asr'", add_model_source)
    assert re.search(r"abilities\?\.includes\('asr'\)", model_item_source)
    assert "modelCategory === 'asr'" in models_dialog_source
    assert "Array.from(new Set([...abilities, 'asr']))" in models_dialog_source


def test_provider_form_can_save_and_scan_models():
    source = PROVIDER_FORM_PATH.read_text(encoding='utf-8')

    assert 'saveAndScanModels' in source
    assert 'handleSaveAndScan' in source
    assert 'scanAfterSave = false' in source
    assert 'onFormSubmit(savedProviderUuid, { scan: scanAfterSave })' in source


def test_models_dialog_can_open_scan_models_for_saved_provider():
    source = MODELS_DIALOG_PATH.read_text(encoding='utf-8')

    assert "options?.scan" in source
    assert "addModelMode === 'scan'" in source
    assert 'initialMode="scan"' in source
    assert "setAddModelMode('scan')" in source


def test_image_file_keys_preserve_path_segments_for_preview_urls():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    editor_source = WORKFLOW_EDITOR_PATH.read_text(encoding='utf-8')
    message_image_source = Path('web/src/app/utils/messageImage.ts').read_text(encoding='utf-8')
    bot_log_source = Path('web/src/app/home/bots/components/bot-log/view/BotLogCard.tsx').read_text(
        encoding='utf-8'
    )
    files_router_source = Path('src/langbot/pkg/api/http/controller/groups/files.py').read_text(
        encoding='utf-8'
    )

    assert 'split(\'/\').map(encodeURIComponent).join(\'/\')' in template_source
    assert 'split(\'/\').map(encodeURIComponent).join(\'/\')' in editor_source
    assert 'split(\'/\').map(encodeURIComponent).join(\'/\')' in message_image_source
    assert 'split(\'/\').map(encodeURIComponent).join(\'/\')' in bot_log_source
    assert '_builtin_image_path' in files_router_source
    assert 'templates/course-sales/phonics/images' in files_router_source


def test_template_config_editor_supports_course_sales_radar_and_link_fields():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')
    types_source = Path('web/src/app/home/pipelines/components/workflow-editor/types.ts').read_text(
        encoding='utf-8'
    )
    editor_source = WORKFLOW_EDITOR_PATH.read_text(encoding='utf-8')

    assert "'radar'" in types_source
    assert 'radar:' in workflow_source
    assert '点击后的自动跟进' in template_source
    assert 'sales_links' in template_source
    assert 'stop_rules' in template_source
    assert 'followup_sequences' in template_source
    assert 'link_id?: string' in types_source
    assert 'image_key?: string' in types_source
    assert 'long_term_broadcasts' in template_source
    assert 'config.radar?.rules' in template_source
    assert 'addRadarRule' in template_source
    assert 'addSalesLink' in template_source
    assert 'addFollowupSequence' in template_source
    assert 'addLongTermBroadcast' in template_source
    assert '首次开场白' in template_source
    assert 'patch({ opening_message: event.target.value })' in template_source
    assert '家长，您这边能打开吗？' not in workflow_source.split('const courseOpeningMessage =', 1)[1].split('const defaultHumanHandoff', 1)[0]
    assert 'SOP定时群发' in template_source
    assert '主动跟进话术矩阵' in template_source
    assert '语音回复' in template_source
    assert "label: '雷达监测'" in editor_source


def test_agent_template_editor_wraps_technical_radar_and_stop_parameters():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    types_source = Path('web/src/app/home/pipelines/components/workflow-editor/types.ts').read_text(
        encoding='utf-8'
    )
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')

    assert 'PipelineTemplateCourseProfile' in types_source
    assert 'PipelineTemplateStopPolicy' in types_source
    assert 'course_profiles?: PipelineTemplateCourseProfile[]' in types_source
    assert 'source_materials?: string[]' in types_source
    assert 'stop_policy?: PipelineTemplateStopPolicy' in types_source
    assert '业务产品线' in template_source
    assert 'toggleProductSelection' in template_source
    assert 'toggleProductLineSelection' in template_source
    assert 'groupProductsByLine' in template_source
    assert '条产品线' in template_source
    assert '启用整线' in template_source
    assert '关联产品' not in template_source
    assert 'addCourseProfileFromProduct' not in template_source
    assert '已挂载知识库' not in template_source
    assert '业务资料来源' not in template_source
    assert '调整关联知识库' not in template_source
    assert '客户打开链接' in template_source
    assert '客户浏览了一会儿' in template_source
    assert '自动跟进场景' in template_source
    assert '展开高级工作流参数' in template_source
    assert '客户明确拒绝几次后停止主动触达' in template_source
    assert '展开关键词配置' in template_source
    assert 'explicit_rejection_threshold' in template_source
    assert 'course_profiles: templateConfig.course_profiles || []' in workflow_source
    assert 'stop_policy: templateConfig.stop_policy' in workflow_source


def test_agent_radar_tab_removes_duplicate_interaction_radar_controls():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    radar_settings = re.search(
        r'function renderRadarSettings\(\) \{([\s\S]+?)\n  function renderPushSettings',
        template_source,
    ).group(1)

    assert '启用互动雷达' not in radar_settings
    assert '点击后 AI 行为回复' not in radar_settings
    assert 'value={config.interaction_radar.link_url}' not in radar_settings
    assert '互动雷达链接' not in template_source
    assert '雷达总开关' in radar_settings
    assert '客户可点击的链接' in radar_settings
    assert '点击后的自动跟进' in radar_settings
    assert '点击后自动追访' in radar_settings
    assert '几分钟后发送' in radar_settings
    assert '0 表示立即发送' in radar_settings
    assert '多久后跟进' not in radar_settings
    assert '0 表示立即跟进' not in radar_settings
    assert radar_settings.index('雷达总开关') < radar_settings.index('客户可点击的链接')
    assert radar_settings.index('客户可点击的链接') < radar_settings.index('点击后的自动跟进')


def test_agent_push_tab_uses_business_friendly_followup_editor():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    push_settings = re.search(
        r'function renderPushSettings\(\) \{([\s\S]+?)\n  function renderHandoffSettings',
        template_source,
    ).group(1)

    assert '跟进消息 JSON' not in push_settings
    assert 'JSON.stringify(sequence.messages' not in push_settings
    assert 'JSON.parse(event.target.value)' not in push_settings
    assert 'font-mono' not in push_settings
    assert '发送节奏' in push_settings
    assert '发送内容' in push_settings
    assert '带报名链接' in push_settings
    assert '发送图片素材' in push_settings
    assert '语音可选' in push_settings
    assert '阶段标识' not in push_settings


def test_template_config_editor_supports_human_handoff_configuration():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    handoff_settings = re.search(
        r'function renderHandoffSettings\(\) \{([\s\S]+?)\n  function renderSpecialCaseSettings',
        template_source,
    ).group(1)
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')
    types_source = Path('web/src/app/home/pipelines/components/workflow-editor/types.ts').read_text(
        encoding='utf-8'
    )

    assert "'handoff'" in template_source
    assert "label: '转人工'" in template_source
    assert 'human_handoff' in template_source
    assert 'patchHumanHandoff' in template_source
    assert '触发关键词' not in handoff_settings
    assert '意图识别场景' in handoff_settings
    assert '关键词兜底' in handoff_settings
    assert '命中后停止 AI 自动回复' in template_source
    assert '命中后停止主动触达' in template_source
    assert '用户可见安抚话术' in template_source
    assert '我这边帮您记录好了，稍等我看下具体情况~' in template_source
    assert 'PipelineTemplateHumanHandoff' in types_source
    assert 'semantic_triggers' in types_source
    assert 'human_handoff: templateConfig.human_handoff' in workflow_source


def test_template_config_editor_supports_special_case_configuration():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')
    types_source = Path('web/src/app/home/pipelines/components/workflow-editor/types.ts').read_text(
        encoding='utf-8'
    )

    assert "'specialCases'" in template_source
    assert "label: '特殊情况处理'" in template_source
    assert 'PipelineTemplateSpecialCase' in types_source
    assert 'special_cases' in types_source
    assert 'patchSpecialCase' in template_source
    assert '用户语义条件' in template_source
    assert '固定回复意思' in template_source
    assert '允许 AI 自然改写话术' in template_source
    assert 'special_cases: templateConfig.special_cases || []' in workflow_source


def test_template_config_editor_shows_only_selected_config_tab():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')

    assert '{renderPanelByTab(activeTab)}' in template_source
    assert 'onClick={() => setActiveTab(tab.id)}' in template_source
    assert 'onClick={() => scrollToSection(tab.id)}' not in template_source
    assert 'syncActiveTabFromScroll' not in template_source


def test_default_workflow_is_blank_start_to_end_canvas():
    source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')

    assert 'createBlankWorkflow' in source
    assert "name: '空白工作流'" in source
    assert "scenario: 'custom'" in source
    assert 'nodes: [start, end]' in source
    assert 'edges: [edge(start, end)]' in source
    assert 'return createBlankWorkflow();' in source


def test_node_library_is_on_demand_instead_of_persistent_sidebar():
    source = WORKFLOW_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'nodePaletteOpen' in source
    assert 'data-node-palette-trigger' in source
    assert '添加到当前画布视野内，不自动连线' in source
    assert 'setLeftPanelCollapsed' not in source
    assert 'PanelLeftOpen' not in source
    assert 'PanelLeftClose' not in source


def test_workflow_canvas_supports_direct_drag_panning():
    source = WORKFLOW_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'canvasPanRef' in source
    assert 'handleCanvasPointerDown' in source
    assert 'handleCanvasPointerMove' in source
    assert 'handleCanvasPointerUp' in source
    assert 'data-workflow-canvas' in source
    assert "closest('[data-workflow-node-id]')" in source
    assert "closest('[data-node-action]')" in source
    assert 'event.currentTarget.scrollLeft' in source
    assert 'event.currentTarget.scrollTop' in source
    assert 'cursor-grab' in source
    assert 'cursor-grabbing' in source


def test_latest_workflow_navigation_opens_n8n_demo_editor():
    sidebar_source = SIDEBAR_CONFIG_PATH.read_text(encoding='utf-8')
    router_source = ROUTER_PATH.read_text(encoding='utf-8')
    workflows_source = WORKFLOWS_PAGE_PATH.read_text(encoding='utf-8')
    workflow_library_source = WORKFLOW_LIBRARY_PAGE_PATH.read_text(encoding='utf-8')

    assert "id: 'pipelines'" in sidebar_source
    assert "name: '数字员工'" in sidebar_source
    assert "route: '/home/pipelines'" in sidebar_source
    assert "id: 'workflows'" in sidebar_source
    assert "name: '工作流'" in sidebar_source
    assert "route: '/home/workflows'" in sidebar_source
    assert sidebar_source.index("id: 'pipelines'") < sidebar_source.index("id: 'workflows'")
    assert "path: '/home/workflows'" in router_source
    workflow_route_block = router_source.split("path: '/home/workflows'", 1)[1].split("path: '/home/monitoring'", 1)[0]
    assert 'import WorkflowsPage' in router_source
    assert 'import WorkflowLibraryPage' in router_source
    assert '<WorkflowsPage />' in workflow_route_block
    assert "path: '/home/workflows/native'" in workflow_route_block
    assert '<WorkflowLibraryPage />' in workflow_route_block
    assert '<PipelinesPage />' not in workflow_route_block
    assert 'VITE_N8N_DEMO_URL' in workflows_source
    assert 'DEFAULT_N8N_DEMO_URL' in workflows_source
    assert '<iframe' in workflows_source
    assert 'title="n8n workflow editor demo"' in workflows_source
    assert 'PipelineWorkflowEditor' not in workflows_source
    assert 'createBlankWorkflow' not in workflows_source

    assert 'PipelineWorkflowEditor' in workflow_library_source
    assert 'createBlankWorkflow' in workflow_library_source
    assert 'getWorkflows' in workflow_library_source
    assert 'fromWorkflowProject' in workflow_library_source
    assert "const defaultFolder = '我的项目';" in workflow_library_source
    assert "useState(() => [defaultFolder])" in workflow_library_source
    assert 'useState(defaultFolder)' in workflow_library_source
    assert 'setFolders' in workflow_library_source
    assert 'newFolderName' in workflow_library_source
    assert 'createFolder' in workflow_library_source
    assert '新目录名称' in workflow_library_source
    assert '创建' in workflow_library_source
    assert 'Upload' not in workflow_library_source
    assert '<Upload' not in workflow_library_source
    assert 'My Projects' not in workflow_library_source
    assert '游轮DEMO' not in workflow_library_source
    assert '示例DEMO' not in workflow_library_source
    assert '销售转化工作流' not in workflow_library_source
    assert '客服接待工作流' not in workflow_library_source


def test_standalone_workflow_templates_preserve_digital_employee_nodes():
    source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')

    assert 'createCourseSalesWorkflowTemplate' in source
    assert 'createTaskAssistantWorkflowTemplate' in source
    assert "name: '课程销售模板'" in source
    assert "name: '任务助手模板配置版'" in source
    assert "scenario: 'course_sales_yuanfudao_phonics'" in source
    assert "scenario: 'task_assistant_ant_af'" in source
    assert 'Task assistant workflow template must keep 28 nodes and 38 edges.' in source
    assert 'Course sales workflow template must keep 21 nodes and 28 edges.' in source

    task_node_ids = [
        'media_router',
        'text_input',
        'voice_asr',
        'screenshot_input',
        'route_intent',
        'knowledge_fallback',
        'voice',
        'step_download_qr',
        'image_download_qr',
        'step_app_store_download',
        'image_app_store_download',
        'step_alipay_login',
        'image_alipay_login',
        'step_alipay_login_confirm',
        'image_alipay_login_confirm',
        'step_open_profile',
        'image_open_profile',
        'step_open_settings',
        'image_open_settings',
        'step_open_real_person_verify',
        'image_open_real_person_verify',
        'step_import_identity',
        'image_import_identity',
    ]
    for node_id in task_node_ids:
        assert f"id: '{node_id}'" in source or "`step_${step.id}`" in source

    course_node_ids = [
        'opening_message',
        'resource_faq',
        'course_faq',
        'course_product',
        'sales_link',
        'radar',
        'radar_followup',
        'long_term_broadcast',
        'handoff',
        'image_gift_poster',
        'image_gift_qr',
    ]
    for node_id in course_node_ids:
        assert f"id: '{node_id}'" in source or "`image_${binding.step_id}`" in source

    assert 'course-sales/phonics/gift_poster.jpeg' in source
    assert 'course-sales/phonics/gift_qr.jpeg' in source
    assert 'task-assistant/ant-af/af_step_01.png' in source
    assert 'task-assistant/ant-af/af_step_08.png' in source


def test_workflow_cards_open_on_click_and_delete_with_confirmation():
    source = WORKFLOW_LIBRARY_PAGE_PATH.read_text(encoding='utf-8')

    assert 'AlertDialog' in source
    assert 'workflowPendingDelete' in source
    assert 'deleteWorkflow' in source
    assert '确认删除工作流' in source
    assert '删除后无法恢复' in source
    assert 'group-hover/card:opacity-100' in source
    assert 'event.stopPropagation()' in source
    assert 'onClick={() => setEditingId(item.id)}' in source

    assert 'Download' not in source
    assert 'Copy' not in source
    assert 'Edit3' not in source
    assert 'workflowCardMeta' not in source
    assert 'selectedIds' not in source
    assert 'toggleSelected' not in source
    assert 'toggleSelectAll' not in source
    assert '全选' not in source
    assert 'type="checkbox"' not in source
    assert '个节点 ·' not in source
    assert 'border-t border-slate-100' not in source
    assert '编辑' not in source


def test_workflow_creation_settings_do_not_bind_agent():
    source = WORKFLOW_LIBRARY_PAGE_PATH.read_text(encoding='utf-8')

    assert 'boundAgent' not in source
    assert '绑定 AI Agent' not in source
    assert '绑定 Agent' not in source


def test_pipeline_create_entry_uses_two_employee_type_choices():
    source = PIPELINE_PAGE_PATH.read_text(encoding='utf-8')
    detail_source = PIPELINE_DETAIL_PATH.read_text(encoding='utf-8')

    assert 'showCreateTypeDialog' in source
    assert '选择数字员工类型' in source
    assert '自定义Agent' in source
    assert '工作流回答' in source
    assert "startCreatePipeline('custom')" in source
    assert "startCreatePipeline('workflow')" in source
    assert 'createBlankCustomPipeline' in source
    assert 'createBlankWorkflowAnswerPipeline' in source
    assert 'httpClient.createPipeline' in source
    assert 'createBlankAgentTemplateConfig()' in source
    assert "config_mode: 'workflow'" in source
    assert "workflow_source: {" in source
    assert "navigate(`/home/pipelines?id=${encodeURIComponent(resp.uuid)}`)" in source
    assert "navigate('/home/pipelines?id=new&type=custom')" not in source
    assert "navigate('/home/pipelines?id=new&type=workflow')" not in source
    assert "createType === 'workflow'" in detail_source
    assert 'createMode={createType}' in detail_source

    assert 'FAQ匹配回答' not in source
    assert '推理回答' not in source
    assert '自定义Prompt回答' not in source
    assert '长记忆回答' not in source


def test_custom_agent_creation_and_editor_defaults_are_blank():
    page_source = PIPELINE_PAGE_PATH.read_text(encoding='utf-8')
    form_source = PIPELINE_FORM_PATH.read_text(encoding='utf-8')
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')
    workflow_source = WORKFLOW_TEMPLATES_PATH.read_text(encoding='utf-8')

    assert 'createBlankAgentTemplateConfig' in workflow_source
    assert "name: ''" in workflow_source
    assert "role_prompt: ''" in workflow_source
    assert "opening_message: ''" in workflow_source
    assert 'recommended_questions: []' in workflow_source
    assert 'image_text_bindings: []' in workflow_source
    assert 'createTaskAssistantTemplateConfig()' not in page_source
    assert 'createBlankAgentTemplateConfig()' in page_source
    assert 'createBlankAgentTemplateConfig()' in form_source
    assert '推荐问题' not in template_source
    assert 'patchRecommendedQuestions' not in template_source
    assert 'config.opening_message ||' not in template_source
    assert '您好，我是您的数字员工' not in template_source


def test_workflow_answer_pipeline_form_uses_library_workflow_selection():
    source = PIPELINE_FORM_PATH.read_text(encoding='utf-8')

    assert "type PipelineCreateMode = 'custom' | 'workflow'" in source
    assert 'workflowProjects' in source
    assert 'getWorkflows' in source
    assert '工作流绑定' in source
    assert 'workflow_source' in source
    assert "config_mode: 'workflow'" in source
    assert 'template_config: templateConfig' in source
    assert "name=\"template_config.opening_message\"" in source
    assert 'selectedWorkflowProject?.workflow' in source
    assert 'renderWorkflowAnswerEditor' in source
    assert 'renderWorkflowPreview' in source
    assert '预览调试' in source
    assert '尚未绑定工作流' in source
    assert '角色设定</CardTitle>' not in source
    assert '选择工作流</CardTitle>' not in source
    assert '请选择工作流' not in source


def test_models_dialog_exposes_embedding_category():
    source = MODELS_DIALOG_PATH.read_text(encoding='utf-8')
    popover_source = ADD_MODEL_POPOVER_PATH.read_text(encoding='utf-8')

    assert "'embedding'" in source or '"embedding"' in source
    assert 'models.embeddingCategory' in source
    assert 'renderEmbeddingModelItem' in source
    assert 'providerBelongsToCategory' in source
    assert 'handleDeleteProvider' in source
    assert 'lockedModelType' in popover_source
    assert 'defaultModelType' in popover_source


def test_sales_chat_renders_normalized_sales_message_components_and_hides_technical_customer_ids():
    source = SALES_CHAT_PAGE_PATH.read_text(encoding='utf-8')
    component_source = Path('web/src/app/home/sales-chat/message-components.tsx').read_text(encoding='utf-8')

    assert 'SalesMessageComponents' in source
    assert '<SalesMessageComponents components={message.components}' in source
    assert "component.kind === 'image'" in component_source
    assert "component.kind === 'voice'" in component_source
    assert "component.kind === 'file'" in component_source
    assert "component.kind === 'link'" in component_source
    assert "component.kind === 'quote'" in component_source
    assert 'function browserSafeMediaSource' in component_source
    assert "startsWith('file://')" in component_source
    assert "'image_url'" in component_source
    assert "'voice_url'" in component_source
    assert "'audio_base64'" in component_source
    assert 'isTechnicalIdentifier' in source
    assert 'LauncherTypes.' in source
    assert 'compactIdentifier' in source
    assert '机器人-{conversationAccountLabel(conversation)}' in source
    assert '${conversation.platform} · ${conversationAccountLabel(conversation)} · ${compactIdentifier' in source
    assert "? '数字员工'" not in source
    assert 'message.bot_name ||' in source
    assert 'void loadMessages(selectedSessionId)' in source
    assert 'extractSalesSuggestionMessage' in source
    assert 'setSuggesting(true)' in source
    assert "'wechat_id'" in source
    assert "'手机号'" in source
    assert 'child_grade' in source
    assert '孩子年级' in source
    assert "'needs'" in source
    assert '关注需求' in source
    assert 'if (!selectedConversation) return;' in source
    assert 'disabled={!conversation || savingMemory}' in source


def test_sales_chat_shows_manual_status_badges_from_real_conversation_counts():
    source = SALES_CHAT_PAGE_PATH.read_text(encoding='utf-8')

    assert 'conversationStatusCounts' in source
    assert 'countConversationStatuses' in source
    assert "tab.value === 'pending_manual' || tab.value === 'manual_handling'" in source
    assert 'bg-[#dc2626]' in source
    assert "status: 'all'," in source


def test_pipeline_detail_exposes_auto_test_tab_for_agents_and_workflows():
    detail_source = PIPELINE_DETAIL_PATH.read_text(encoding='utf-8')
    client_source = BACKEND_CLIENT_PATH.read_text(encoding='utf-8')
    types_source = API_ENTITIES_PATH.read_text(encoding='utf-8')
    auto_test_source = PIPELINE_AUTO_TEST_PATH.read_text(encoding='utf-8')

    assert 'PipelineAutoTestTab' in detail_source
    assert 'autoTestOpen' in detail_source
    assert 'setAutoTestOpen(true)' in detail_source
    assert '自动测试' in detail_source

    assert 'getAutoTestTargets' in client_source
    assert 'startAutoTestRun' in client_source
    assert 'submitAutoTestFeedback' in client_source
    assert 'ApiRespAutoTestTargets' in types_source
    assert 'AutoTestRun' in types_source

    assert "targetType === 'pipeline'" in auto_test_source
    assert "targetType === 'workflow'" in auto_test_source
    assert 'getAutoTestTargets' in auto_test_source
    assert 'startAutoTestRun' in auto_test_source
    assert 'submitAutoTestFeedback' in auto_test_source
    assert 'reason.trim()' in auto_test_source
    assert "feedback === 'unsatisfied'" in auto_test_source


def test_auto_test_ui_surfaces_real_applied_optimizer_patches():
    auto_test_source = PIPELINE_AUTO_TEST_PATH.read_text(encoding='utf-8')
    client_source = BACKEND_CLIENT_PATH.read_text(encoding='utf-8')

    assert 'optimizationPatch' in auto_test_source
    assert 'applied_patches' in auto_test_source
    assert 'apply_config_patch' in auto_test_source
    assert 'model_name' in auto_test_source
    assert 'reverted_at' in auto_test_source
    assert 'revertAutoTestRunOptimization' in auto_test_source
    assert 'version_retention' in auto_test_source
    assert 'revertAutoTestRunOptimization' in client_source


def test_auto_test_ui_supports_uploading_sop_for_auto_optimization():
    auto_test_source = PIPELINE_AUTO_TEST_PATH.read_text(encoding='utf-8')
    client_source = BACKEND_CLIENT_PATH.read_text(encoding='utf-8')

    assert 'sopText' in auto_test_source
    assert 'sopFilename' in auto_test_source
    assert 'file.text()' in auto_test_source
    assert 'sop_text: sopText' in auto_test_source
    assert 'sop_filename: sopFilename' in auto_test_source
    assert 'sop_text?: string' in client_source
    assert 'sop_filename?: string' in client_source


def test_auto_test_has_standalone_home_tab_next_to_workflow_and_database():
    sidebar_source = SIDEBAR_CONFIG_PATH.read_text(encoding='utf-8')
    router_source = ROUTER_PATH.read_text(encoding='utf-8')
    page_source = AUTO_TEST_PAGE_PATH.read_text(encoding='utf-8')

    assert "id: 'auto-test'" in sidebar_source
    assert "route: '/home/auto-test'" in sidebar_source
    assert '自动测试' in sidebar_source
    assert 'Sparkles' in sidebar_source
    assert sidebar_source.index("id: 'workflows'") < sidebar_source.index("id: 'auto-test'")
    assert sidebar_source.index("id: 'auto-test'") < sidebar_source.index("id: 'knowledge'")

    assert 'import AutoTestPage' in router_source
    assert "path: '/home/auto-test'" in router_source
    auto_test_route_block = router_source.split("path: '/home/auto-test'", 1)[1].split("path: '/home/monitoring'", 1)[0]
    assert '<AutoTestPage />' in auto_test_route_block

    assert 'PipelineAutoTestTab' in page_source
    assert '<PipelineAutoTestTab />' in page_source
