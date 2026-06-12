from __future__ import annotations

import quart

from .. import group


@group.group_class('autotest', '/api/v1/autotest')
class AutoTestRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/targets', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            return self.success(data=await self.ap.auto_test_service.get_targets())

        @self.route('/runs', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                limit = int(quart.request.args.get('limit', 20))
                runs = await self.ap.auto_test_service.list_runs(
                    target_type=quart.request.args.get('target_type'),
                    target_uuid=quart.request.args.get('target_uuid'),
                    limit=limit,
                )
                return self.success(data={'runs': runs})

            data = await quart.request.json
            try:
                run = await self.ap.auto_test_service.start_run(data or {})
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'run': run})

        @self.route('/runs/<run_uuid>/feedback', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(run_uuid: str) -> str:
            data = await quart.request.json
            try:
                run = await self.ap.auto_test_service.submit_feedback(run_uuid, data or {})
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'run': run})

        @self.route('/runs/<run_uuid>/revert', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(run_uuid: str) -> str:
            try:
                run = await self.ap.auto_test_service.revert_run_optimization(run_uuid)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'run': run})
