from __future__ import annotations

import quart

from .. import group


@group.group_class('workflows', '/api/v1/workflows')
class WorkflowsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data=await self.ap.workflow_service.get_workflow_library())

            data = await quart.request.json
            workflow_uuid = await self.ap.workflow_service.create_workflow(data or {})
            return self.success(data={'uuid': workflow_uuid})

        @self.route('/folders', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            data = await quart.request.json
            await self.ap.workflow_service.create_folder((data or {}).get('name', ''))
            return self.success()

        @self.route('/generate-draft', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            data = await quart.request.json
            return self.success(data=await self.ap.workflow_service.generate_workflow_draft(data or {}))

        @self.route('/<workflow_uuid>', methods=['PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(workflow_uuid: str) -> str:
            if quart.request.method == 'PUT':
                data = await quart.request.json
                await self.ap.workflow_service.update_workflow(workflow_uuid, data or {})
                return self.success()

            await self.ap.workflow_service.delete_workflow(workflow_uuid)
            return self.success()
