from __future__ import annotations

import quart

from .. import group


@group.group_class('sales', '/api/v1/sales')
class SalesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/overview', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            return self.success(data=await self.ap.sales_service.get_overview())

        @self.route('/products', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data={'products': await self.ap.sales_service.get_products()})
            data = await quart.request.json
            try:
                product_uuid = await self.ap.sales_service.create_product(data)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'uuid': product_uuid})

        @self.route('/products/<product_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(product_uuid: str) -> str:
            if quart.request.method == 'GET':
                try:
                    product = await self.ap.sales_service.get_product(product_uuid)
                except ValueError:
                    return self.http_status(404, -1, 'Product not found')
                return self.success(data={'product': product})
            if quart.request.method == 'PUT':
                data = await quart.request.json
                try:
                    await self.ap.sales_service.update_product(product_uuid, data)
                except ValueError as exc:
                    return self.http_status(400, -1, str(exc))
                return self.success()
            try:
                await self.ap.sales_service.delete_product(product_uuid)
            except ValueError:
                return self.http_status(404, -1, 'Product not found')
            return self.success()

        @self.route('/intent', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            data = await quart.request.json
            return self.success(data=self.ap.sales_service.classify_intent(data.get('text', '')))

        @self.route('/assist/pitch', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            data = await quart.request.json
            product = data.get('product')
            if not product and data.get('product_uuid'):
                products = await self.ap.sales_service.get_products(enabled_only=True)
                product = next((p for p in products if p.get('uuid') == data.get('product_uuid')), None)
            if not product:
                products = await self.ap.sales_service.get_products(enabled_only=True)
                product = self.ap.sales_service.select_best_product(data.get('message', ''), products)
            if not product:
                return self.http_status(404, -1, 'No product available')
            pitch = self.ap.sales_service.generate_pitch(
                product,
                customer_profile=data.get('customer_profile', ''),
                intent=data.get('intent', data.get('message', '')),
                tone=data.get('tone', 'consultative'),
            )
            return self.success(data={'pitch': pitch, 'product': product})

        @self.route('/conversations', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            status = quart.request.args.get('status')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))
            conversations = await self.ap.sales_service.get_sales_conversations(
                status=status,
                limit=limit,
                offset=offset,
            )
            return self.success(data={'conversations': conversations, 'limit': limit, 'offset': offset})

        @self.route('/conversations/<path:session_id>/messages', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            limit = int(quart.request.args.get('limit', 200))
            offset = int(quart.request.args.get('offset', 0))
            result = await self.ap.sales_service.get_sales_conversation_messages(
                session_id,
                limit=limit,
                offset=offset,
            )
            return self.success(data={**result, 'limit': limit, 'offset': offset})

        @self.route('/conversations/<path:session_id>/manual-reply', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            reply = data.get('reply', '').strip()
            if not reply:
                return self.http_status(400, -1, 'reply is required')
            result = await self.ap.sales_service.send_operator_message_from_session(
                session_id,
                reply,
                data.get('assigned_to', ''),
                pause_ai=False,
            )
            return self.success(data=result)

        @self.route('/conversations/<path:session_id>/handoff/start', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            handoff = await self.ap.sales_service.open_handoff_from_session(
                session_id,
                data.get('reason', '人工主动介入'),
                data.get('assigned_to', ''),
            )
            return self.success(data={'handoff': handoff})

        @self.route('/conversations/<path:session_id>/handoff/reply', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            reply = data.get('reply', '').strip()
            if not reply:
                return self.http_status(400, -1, 'reply is required')
            result = await self.ap.sales_service.reply_handoff_from_session(
                session_id,
                reply,
                data.get('assigned_to', ''),
            )
            return self.success(data=result)

        @self.route('/conversations/<path:session_id>/handoff/restore', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            result = await self.ap.sales_service.restore_ai_hosting_from_session(
                session_id,
                data.get('assigned_to', ''),
            )
            return self.success(data=result)

        @self.route('/conversations/<path:session_id>/ai-suggestion', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            try:
                suggestion = await self.ap.sales_service.generate_sales_reply_suggestion_from_session(
                    session_id,
                    product_uuid=data.get('product_uuid', ''),
                    tone=data.get('tone', 'consultative'),
                )
            except ValueError as exc:
                return self.http_status(404, -1, str(exc))
            return self.success(data=suggestion)

        @self.route('/memories', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            return self.success(data={'memories': await self.ap.sales_service.get_memories()})

        @self.route('/memories/<session_id>', methods=['PUT'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            memory = await self.ap.sales_service.update_memory(session_id, data or {})
            return self.success(data={'memory': memory})

        @self.route('/handoffs', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            status = quart.request.args.get('status')
            return self.success(data={'handoffs': await self.ap.sales_service.get_handoffs(status=status)})

        @self.route('/handoffs/from-session', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            data = await quart.request.json
            session_id = data.get('session_id', '').strip()
            if not session_id:
                return self.http_status(400, -1, 'session_id is required')
            handoff = await self.ap.sales_service.open_handoff_from_session(
                session_id,
                data.get('reason', '人工主动介入'),
                data.get('assigned_to', ''),
            )
            return self.success(data={'handoff': handoff})

        @self.route('/handoffs/from-session/reply', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            data = await quart.request.json
            session_id = data.get('session_id', '').strip()
            reply = data.get('reply', '').strip()
            if not session_id:
                return self.http_status(400, -1, 'session_id is required')
            if not reply:
                return self.http_status(400, -1, 'reply is required')
            result = await self.ap.sales_service.reply_handoff_from_session(
                session_id,
                reply,
                data.get('assigned_to', ''),
            )
            return self.success(data=result)

        @self.route('/handoffs/<int:handoff_id>/reply', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(handoff_id: int) -> str:
            data = await quart.request.json
            reply = data.get('reply', '').strip()
            if not reply:
                return self.http_status(400, -1, 'reply is required')
            await self.ap.sales_service.reply_handoff(handoff_id, reply, data.get('assigned_to', ''))
            return self.success(data={'sent': True})

        @self.route('/outreach', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data={'plans': await self.ap.sales_service.get_outreach_plans()})
            data = await quart.request.json
            plan_id = await self.ap.sales_service.create_outreach_plan(data)
            return self.success(data={'id': plan_id})

        @self.route('/outreach/run-due', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            sent = await self.ap.sales_service.run_due_outreach_once()
            return self.success(data={'sent': sent})

        @self.route('/radar/click/<token>', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _(token: str):
            try:
                destination = await self.ap.sales_service.handle_radar_tracking_click(token)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return quart.redirect(destination)
