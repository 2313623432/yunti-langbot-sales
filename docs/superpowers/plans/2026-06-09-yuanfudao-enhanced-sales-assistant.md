# Yuanfudao Enhanced Sales Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a configurable "猿辅导销售助手加强版" digital employee/workflow using the three provided SOP spreadsheets as a demo scenario, while keeping the runtime reusable for future sales scenarios.

**Architecture:** Move demo business content into a scenario template file that is loaded into local persisted workflow/pipeline configs instead of being coded directly in runtime branches. Keep runtime logic generic where possible: derive product facts, FAQs, follow-up plans, stop policy, image bindings, and voice behavior from the active workflow/template config. Reuse the existing sales outreach scheduler, image component rendering, and workflow template editor.

**Tech Stack:** Python backend services/tests with `uv`/pytest, SQLAlchemy persistence, Next.js/React frontend, existing workflow template editor, existing sales outreach scheduler.

---

### Task 1: Configurable Scenario Data

**Files:**
- Create: `src/langbot/templates/course-sales/yuanfudao-enhanced.json`
- Modify: `src/langbot/pkg/api/http/service/task_assistant.py`
- Test: `tests/unit_tests/api/service/test_task_assistant_service.py`

- [ ] **Step 1: Write failing tests**
  - Assert the enhanced template pipeline/workflow name is `猿辅导销售助手加强版`.
  - Assert the active workflow contains two product profiles: `phonics` and `reading_thinking`.
  - Assert loaded source metadata mentions all three spreadsheet names.

- [ ] **Step 2: Run tests to verify RED**
  - Run: `uv run pytest tests/unit_tests/api/service/test_task_assistant_service.py -k "enhanced_yuanfudao" -q`
  - Expected: FAIL because enhanced loader/constants do not exist yet.

- [ ] **Step 3: Implement minimal loader**
  - Add JSON scenario data with course profiles, FAQs, links, radar, follow-up sequences, broadcasts, stop policy, and image bindings.
  - Add service methods to load the JSON and build enhanced template/workflow configs from it.

- [ ] **Step 4: Run tests to verify GREEN**
  - Run: `uv run pytest tests/unit_tests/api/service/test_task_assistant_service.py -k "enhanced_yuanfudao" -q`
  - Expected: PASS.

### Task 2: Runtime Behavior From Active Config

**Files:**
- Modify: `src/langbot/pkg/api/http/service/task_assistant.py`
- Test: `tests/unit_tests/api/service/test_task_assistant_service.py`

- [ ] **Step 1: Write failing tests**
  - Assert a reading/thinking user message selects the reading/thinking product profile.
  - Assert first explicit refusal does not disable outreach.
  - Assert second explicit refusal disables outreach.
  - Assert text input does not set voice reply, while voice input does when voice is enabled.
  - Assert image input is classified as screenshot/image help and keeps image content in the model message.

- [ ] **Step 2: Run tests to verify RED**
  - Run: `uv run pytest tests/unit_tests/api/service/test_task_assistant_service.py -k "enhanced_runtime" -q`
  - Expected: FAIL on missing data-driven product selection and two-refusal policy.

- [ ] **Step 3: Implement minimal runtime changes**
  - Pass workflow into the course-sales classifier.
  - Select product/FAQ/link content from workflow variables/config.
  - Track explicit refusal counts per target/session and disable outreach only at the configured threshold.
  - Preserve existing stop-immediate behavior for complaint, no-child, wrong number, purchased, and handoff states.

- [ ] **Step 4: Run tests to verify GREEN**
  - Run: `uv run pytest tests/unit_tests/api/service/test_task_assistant_service.py -k "enhanced_runtime" -q`
  - Expected: PASS.

### Task 3: Frontend Template Visibility

**Files:**
- Modify: `web/src/app/home/pipelines/components/workflow-editor/types.ts`
- Modify: `web/src/app/home/pipelines/components/workflow-editor/PipelineTemplateConfigEditor.tsx`
- Test: `tests/unit_tests/web/test_workflow_editor_source.py`

- [ ] **Step 1: Write failing source tests**
  - Assert template config types include `course_profiles` and `stop_policy`.
  - Assert editor renders a course profile section and explicit refusal threshold field.

- [ ] **Step 2: Run tests to verify RED**
  - Run: `uv run pytest tests/unit_tests/web/test_workflow_editor_source.py -k "enhanced_yuanfudao" -q`
  - Expected: FAIL because fields are not in the editor yet.

- [ ] **Step 3: Implement minimal frontend support**
  - Extend types for generic multi-product course profiles.
  - Show profile count/details and stop threshold in the existing template editor.
  - Keep existing links/radar/follow-up/broadcast/image sections unchanged.

- [ ] **Step 4: Run tests to verify GREEN**
  - Run: `uv run pytest tests/unit_tests/web/test_workflow_editor_source.py -k "enhanced_yuanfudao" -q`
  - Expected: PASS.

### Task 4: Verification Sweep

**Files:**
- Backend and frontend files touched above.

- [ ] **Step 1: Run focused backend tests**
  - Run: `uv run pytest tests/unit_tests/api/service/test_task_assistant_service.py tests/unit_tests/api/service/test_sales_service.py -q`

- [ ] **Step 2: Run focused frontend source tests**
  - Run: `uv run pytest tests/unit_tests/web/test_workflow_editor_source.py -q`

- [ ] **Step 3: Inspect status**
  - Run: `git status --short`
  - Confirm only expected files changed and no unrelated user changes were reverted.
