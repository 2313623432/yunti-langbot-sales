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
WORKFLOWS_PAGE_PATH = Path('web/src/app/home/workflows/page.tsx')
PIPELINE_PAGE_PATH = Path('web/src/app/home/pipelines/page.tsx')
PIPELINE_DETAIL_PATH = Path('web/src/app/home/pipelines/PipelineDetailContent.tsx')
SIDEBAR_CONFIG_PATH = Path('web/src/app/home/components/home-sidebar/sidbarConfigList.tsx')
ROUTER_PATH = Path('web/src/router.tsx')
ADD_MODEL_POPOVER_PATH = Path('web/src/app/home/components/models-dialog/components/AddModelPopover.tsx')
MODEL_ITEM_PATH = Path('web/src/app/home/components/models-dialog/components/ModelItem.tsx')
MODELS_DIALOG_PATH = Path('web/src/app/home/components/models-dialog/ModelsDialog.tsx')


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
    assert 'salesProducts.map' in template_source
    assert 'toggleTemplateListValue' in template_source
    assert '雷达跟进' in template_source
    assert 'interaction_radar' in template_source
    assert 'link_url' in template_source
    assert '自动跟进链接' in template_source
    assert 'patchStringList' not in template_source
    assert 'selectedConfigMode' not in form_source
    assert "selectedConfigMode === 'template'" not in form_source
    assert 'overflow-y-auto' in form_source
    assert '每天推送' in template_source
    assert '指定单天' in template_source
    assert '图片文字绑定' in template_source


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
    assert 'chatLlmModels' in model_settings
    assert 'voiceModels' in model_settings
    assert 'handleVoiceModelChange' in model_settings
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
    assert "toggleAbility('tts', checked as boolean)" in add_model_source
    assert re.search(r"toggleScannedModelAbility\(\s*model\.id,\s*'tts'", add_model_source)
    assert re.search(r"abilities\?\.includes\('tts'\)", model_item_source)
    assert "editAbilities.includes('tts')" in model_item_source


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
    assert '已接入业务产品线' in template_source
    assert '业务资料来源' in template_source
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
    preview_panel = re.search(
        r'<div className="min-h-\[460px\][\s\S]+?\n\s+\{enabledImageBindings\[0\]',
        template_source,
    ).group(0)

    assert '启用互动雷达' not in radar_settings
    assert '点击后 AI 行为回复' not in radar_settings
    assert 'value={config.interaction_radar.link_url}' not in radar_settings
    assert '互动雷达链接' not in preview_panel
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


def test_latest_workflow_navigation_opens_real_pipeline_orchestration():
    sidebar_source = SIDEBAR_CONFIG_PATH.read_text(encoding='utf-8')
    router_source = ROUTER_PATH.read_text(encoding='utf-8')
    workflows_source = WORKFLOWS_PAGE_PATH.read_text(encoding='utf-8')

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
    assert '<WorkflowsPage />' in workflow_route_block
    assert '<PipelinesPage />' not in workflow_route_block
    assert 'PipelineWorkflowEditor' in workflows_source
    assert 'createBlankWorkflow' in workflows_source
    assert 'getWorkflows' in workflows_source
    assert 'fromWorkflowProject' in workflows_source
    assert "const defaultFolder = '我的项目';" in workflows_source
    assert "useState(() => [defaultFolder])" in workflows_source
    assert 'useState(defaultFolder)' in workflows_source
    assert 'setFolders' in workflows_source
    assert 'newFolderName' in workflows_source
    assert 'createFolder' in workflows_source
    assert '新目录名称' in workflows_source
    assert '创建' in workflows_source
    assert 'Upload' not in workflows_source
    assert '<Upload' not in workflows_source
    assert 'My Projects' not in workflows_source
    assert '游轮DEMO' not in workflows_source
    assert '示例DEMO' not in workflows_source
    assert '销售转化工作流' not in workflows_source
    assert '客服接待工作流' not in workflows_source


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
        assert f"id: '{node_id}'" in source or f"`step_${{step.id}}`" in source

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
        assert f"id: '{node_id}'" in source or f"`image_${{binding.step_id}}`" in source

    assert 'course-sales/phonics/gift_poster.jpeg' in source
    assert 'course-sales/phonics/gift_qr.jpeg' in source
    assert 'task-assistant/ant-af/af_step_01.png' in source
    assert 'task-assistant/ant-af/af_step_08.png' in source


def test_workflow_cards_open_on_click_and_delete_with_confirmation():
    source = WORKFLOWS_PAGE_PATH.read_text(encoding='utf-8')

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
    source = WORKFLOWS_PAGE_PATH.read_text(encoding='utf-8')

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
