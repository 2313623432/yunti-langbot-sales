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
SIDEBAR_CONFIG_PATH = Path('web/src/app/home/components/home-sidebar/sidbarConfigList.tsx')
ROUTER_PATH = Path('web/src/router.tsx')


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
    assert 'syncWorkflowModelIntoAIConfig' in form_source
    assert "['local-agent']" in form_source
    assert 'primary: selectedModelUuid' in form_source


def test_pipeline_editor_supports_template_and_workflow_modes():
    form_source = PIPELINE_FORM_PATH.read_text(encoding='utf-8')
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'PipelineTemplateConfigEditor' in form_source
    assert 'config_mode' in form_source
    assert 'template_config' in form_source
    assert 'applyTemplateConfigToWorkflow' not in form_source
    assert 'Agent配置' in form_source
    assert '工作流编排' in form_source

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
    assert '互动雷达' in template_source
    assert 'interaction_radar' in template_source
    assert 'link_url' in template_source
    assert 'click_reply' in template_source
    assert 'patchStringList' not in template_source
    assert 'selectedConfigMode' in form_source
    assert "selectedConfigMode === 'template'" in form_source
    assert 'overflow-y-auto' in form_source
    assert '每天推送' in template_source
    assert '指定单天' in template_source
    assert '图片文字绑定' in template_source


def test_template_model_capability_uses_configured_llm_model_select():
    template_source = TEMPLATE_CONFIG_EDITOR_PATH.read_text(encoding='utf-8')

    assert 'getProviderLLMModels' in template_source
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
    assert '最大思考次数' not in template_source
    assert 'max_reasoning_steps' not in template_source
    assert 'value={config.model_uuid}' not in template_source


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
    assert '模拟雷达' in template_source
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
    assert '语音回复（课程销售请关闭）' in template_source
    assert "label: '雷达监测'" in editor_source


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
    assert 'createCourseSalesWorkflowTemplate' in workflows_source
    assert 'createTaskAssistantWorkflowTemplate' in workflows_source
    assert 'createInitialWorkflowItems' in workflows_source
    assert "const initialFolders = ['我的项目'];" in workflows_source
    assert "useState(() => [...initialFolders])" in workflows_source
    assert "useState('我的项目')" in workflows_source
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
    assert '空白工作流' not in workflows_source
    assert "name: '课程销售模板'" in workflows_source
    assert "name: '任务助手模板配置版'" in workflows_source
    assert 'useState<WorkflowItem[]>(() => createInitialWorkflowItems())' in workflows_source


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


def test_workflow_creation_settings_do_not_bind_agent():
    source = WORKFLOWS_PAGE_PATH.read_text(encoding='utf-8')

    assert 'boundAgent' not in source
    assert '绑定 AI Agent' not in source
    assert '绑定 Agent' not in source
