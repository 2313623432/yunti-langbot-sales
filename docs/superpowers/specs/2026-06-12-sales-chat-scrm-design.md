# Sales Chat SCRM Design

## Goal

Rebuild the 聚合聊天 page so it reads like a real SCRM chat workspace. The chat transcript must show the real user and digital-employee conversation from the built-in database, including text, images, voice messages, files, and links. Customer memory, summaries, and handoff metadata may support the view, but they must not appear as chat messages.

## Hard Requirements

- Use the branch-provided built-in database as the source of truth.
- Do not clear, delete, or rewrite historical chat data.
- The chat transcript must read from `monitoring_messages`.
- Both user messages and AI messages must be shown.
- Image and voice messages must be represented from the real message-chain data.
- If media data is playable or previewable from the stored message component, show it inline.
- If media data only has an unavailable reference, show a real attachment card with the source metadata instead of inventing content.
- Customer memory, intent summaries, and handoff records can appear in side panels or status badges only.
- AI must pause while a session is in pending manual intervention or manual handling.
- AI must resume only after an operator clicks restore AI hosting.
- In a normal AI-hosted conversation, an operator can send a manual message directly without creating a handoff and without pausing AI.

## Existing Context

The current 聚合聊天 page is `web/src/app/home/sales-chat/page.tsx`. It builds conversation rows by merging `monitoring_sessions`, `sales_customer_memories`, and `sales_handoffs`. That makes the conversation preview use handoff text or customer summaries when there is no recent message preview, which causes the UI to look like mixed records instead of a real chat transcript.

The real transcript data already exists in `monitoring_messages`. The current built-in database has real message-chain JSON such as `Plain`, `Source`, `Voice`, and assistant replies. The current UI renders `message_content` directly, so JSON appears in chat bubbles and voice/image messages are unreadable.

The backend has a handoff model in `sales_handoffs`. Existing `open` handoffs already block AI in `SalesService.prepare_query`, but the workflow currently treats manual reply as a one-shot handled task. It needs a longer-lived manual handling state and a restore-AI action.

## Recommended Architecture

Add backend sales-conversation endpoints that normalize real monitoring data for the sales chat UI.

The backend should expose:

- Conversation list: real sessions with latest real message preview, customer identity, platform, handoff status, and last activity.
- Conversation messages: parsed message components from `monitoring_messages`, ordered by timestamp.
- Normal manual send: send a real operator message without creating a handoff and without pausing AI.
- Handoff start: create or update a handoff so the session enters pending or manual handling.
- Handoff reply: send a real operator message while AI remains paused. Sending a manual reply must not automatically mark the handoff as handled if that would resume AI.
- AI suggested reply: generate a draft from recent real messages and customer context, but never auto-send it.
- Restore AI hosting: close the active handoff so future user messages can be handled by AI again.

The frontend should consume these normalized endpoints instead of assembling chat rows from mixed raw resources.

## Conversation Status Model

Use `sales_handoffs` as the manual-state controller.

- `ai_hosted`: no active open handoff. AI replies normally. Operator may still send a manual message.
- `pending_manual`: active handoff exists, but no operator has taken it. This appears in the 待人工介入 tab. AI is paused.
- `manual_handling`: active handoff exists and has an assignee or operator activity. This appears in the 人工处理中 tab. AI is paused.
- `ai_resumed`: previous handoff was closed or restored. The conversation returns to AI 托管中.

Implementation can store these states with existing `sales_handoffs.status` plus `assigned_to` and `operator_reply`, or add small incremental fields with an Alembic migration if needed. Any schema change must be additive only. The normalized API status is what the UI consumes; the database may still use `status='open'` for both `pending_manual` and `manual_handling` so AI remains paused until restore.

## Trigger Rules

A session enters 待人工介入 when the customer explicitly asks for a human, for example:

- 转人工
- 人工客服
- 真人
- 找销售
- 电话联系
- 加微信
- 报价单
- 合同

It also enters 待人工介入 when the customer is clearly upset or escalating. The initial implementation can use deterministic keyword rules, for example:

- 投诉
- 生气
- 太差
- 骗人
- 退钱
- 不满意
- 别废话
- 找负责人

The trigger should create or refresh an active handoff and preserve the latest real customer message as the handoff reason context. While active, `prepare_query` must return interrupted and must not let the AI produce an automatic reply.

## Message Normalization

The backend should parse each `monitoring_messages.message_content` value as a message chain when possible.

Supported components:

- `Plain`: render as text.
- `Image`: render image preview if `url`, `base64`, or accessible path exists; otherwise render an image attachment card.
- `Voice`: render audio player if `url`, `base64`, or accessible path exists; otherwise render a voice attachment card.
- `File`: render file card with real file name and metadata.
- `WeChatLink` or link-like components: render a link card.
- `At` and `AtAll`: render mentions as text.
- `Quote`: render quoted text compactly.
- `Source`: keep as metadata but do not render as visible chat content.
- Unknown component: render a compact attachment card with its real type and metadata.

The response should preserve original role, timestamp, bot/user identity, session id, and raw component metadata needed for media playback or preview. It should also include a normalized sender label or sender kind so the UI can distinguish customer, digital employee, and operator messages even when both AI and operator messages are delivered through the assistant side of the platform.

## SCRM UI

The 聚合聊天 first screen should remain the actual chat workspace, not a landing page.

Left panel:

- Tabs: 全部, AI 托管中, 待人工介入, 人工处理中.
- Search by customer, session, platform, and latest real message.
- Each row shows customer name or user id, channel, latest real message preview, time, status badge, and media preview labels such as `[图片]` or `[语音]`.

Center transcript:

- Customer messages on the left.
- AI and operator messages on the right.
- AI messages are labeled 数字员工.
- Operator messages are labeled 人工销售.
- Messages are grouped in timestamp order from the database.
- Text, image, voice, file, and link components render as readable bubbles/cards.

Composer:

- In AI 托管中, typing and sending should send a manual operator message but keep AI hosting active.
- In 待人工介入, show a start handling action. Sending after takeover moves the session to 人工处理中.
- In 人工处理中, sending keeps AI paused.
- AI 推荐回复 creates a draft only. The operator decides whether to edit and send it.
- 恢复 AI 托管 closes the active handoff and returns the session to AI 托管中.

Right panel:

- Customer profile and sales memory.
- Recent intent and handoff reason.
- AI recommendation result and product context.
- These are auxiliary records and must not be mixed into the chat transcript.

## Data Writes

Allowed writes:

- Insert or update `sales_handoffs` for manual-state control.
- Send operator messages through the real bot adapter.
- Append monitoring records for operator messages if the existing send path does not record them automatically.
- Update customer memory only through existing explicit customer-profile actions.

Forbidden writes:

- Clearing any table.
- Deleting historical chat messages.
- Rewriting `monitoring_messages.message_content` for existing rows.
- Converting summaries or memories into fake chat rows.

## Error Handling

- If a media component cannot be played, show a non-destructive attachment card with its real metadata.
- If a manual message cannot be sent because the bot is offline or target metadata is missing, keep the draft and show an error.
- If AI recommendation fails, do not affect the draft or handoff state.
- If restore AI hosting fails, keep the session paused and show an error.

## Testing And Verification

Backend tests:

- Conversation list uses `monitoring_messages` previews instead of customer summaries.
- Message normalization returns text, image, voice, file, and source metadata correctly.
- Explicit human-request keywords create pending manual handoff.
- Upset-customer keywords create pending manual handoff.
- Active pending/manual handoff interrupts AI in `prepare_query`.
- Restore AI hosting allows AI to resume.
- Normal manual send does not create a handoff and does not pause AI.

Frontend tests or manual verification:

- The built-in database's real user and AI messages appear in order.
- JSON message-chain text is no longer displayed directly.
- Existing voice and image messages show as voice/image chat cards.
- 待人工介入 tab appears and filters only pending sessions.
- 人工处理中 tab appears after operator takeover.
- AI 推荐回复 fills a draft but does not auto-send.
- 恢复 AI 托管 returns the session to AI 托管中.

## Implementation Boundaries

This work is limited to the 聚合聊天/SCRM chat experience and the backend endpoints needed to support it. It does not replace the platform adapter system, does not import external data, and does not rebuild the whole sales workbench.
