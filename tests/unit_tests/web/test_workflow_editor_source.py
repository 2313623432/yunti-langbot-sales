from pathlib import Path


WORKFLOW_EDITOR_PATH = Path(
    'web/src/app/home/pipelines/components/workflow-editor/PipelineWorkflowEditor.tsx'
)
PIPELINE_FORM_PATH = Path(
    'web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx'
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
