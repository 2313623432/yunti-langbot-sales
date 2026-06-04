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
    assert 'applyTemplateConfigToWorkflow' in form_source
    assert '模板配置' in form_source
    assert '工作流编排' in form_source

    assert 'scheduled_push' in template_source
    assert 'push_message' in template_source
    assert 'image_text_bindings' in template_source
    assert 'voice_type' in template_source
    assert '每天推送' in template_source
    assert '指定单天' in template_source
    assert '图片文字绑定' in template_source


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
