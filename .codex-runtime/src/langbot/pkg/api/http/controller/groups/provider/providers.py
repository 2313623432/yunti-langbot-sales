import quart
import mimetypes

from ... import group
from langbot.pkg.provider.modelmgr import (
    builtin_embedding_providers,
    builtin_pdf_providers,
    builtin_text_providers,
    builtin_tts_providers,
    provider_icons,
)
from langbot.pkg.utils import importutil


@group.group_class('models/providers', '/api/v1/provider/providers')
class ModelProvidersRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                providers = await self.ap.provider_service.get_providers()
                # Add model counts
                for provider in providers:
                    counts = await self.ap.provider_service.get_provider_model_counts(provider['uuid'])
                    provider['llm_count'] = counts['llm_count']
                    provider['embedding_count'] = counts['embedding_count']
                    provider['rerank_count'] = counts['rerank_count']
                return self.success(data={'providers': providers})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                provider_uuid = await self.ap.provider_service.create_provider(json_data)
                return self.success(data={'uuid': provider_uuid})

        @self.route('/builtin-text-catalog', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _builtin_text_catalog() -> str:
            return self.success(data={'providers': builtin_text_providers.get_builtin_text_catalog()})

        @self.route('/builtin-tts-catalog', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _builtin_tts_catalog() -> str:
            return self.success(data={'providers': builtin_tts_providers.get_builtin_tts_catalog()})

        @self.route('/builtin-embedding-catalog', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _builtin_embedding_catalog() -> str:
            return self.success(data={'providers': builtin_embedding_providers.get_builtin_embedding_catalog()})

        @self.route('/builtin-pdf-catalog', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _builtin_pdf_catalog() -> str:
            return self.success(data={'providers': builtin_pdf_providers.get_builtin_pdf_catalog()})

        @self.route('/<provider_uuid>/icon', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _provider_icon(provider_uuid: str) -> quart.Response:
            icon_bytes = provider_icons.read_builtin_provider_icon_bytes(provider_uuid)
            if icon_bytes is None:
                provider = await self.ap.provider_service.get_provider(provider_uuid)
                if provider is None:
                    return self.http_status(404, -1, 'provider not found')
                requester_manifest = self.ap.model_mgr.get_available_requester_manifest_by_name(
                    provider.get('requester', '')
                )
                if requester_manifest is None or requester_manifest.icon_rel_path is None:
                    return self.http_status(404, -1, 'icon not found')
                icon_path = requester_manifest.icon_rel_path
                icon_bytes = importutil.read_resource_file_bytes(icon_path)

            icon_path = provider_icons.get_builtin_provider_icon_resource_path(provider_uuid) or 'icon.svg'
            return quart.Response(icon_bytes, mimetype=mimetypes.guess_type(icon_path)[0])

        @self.route(
            '/<provider_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(provider_uuid: str) -> str:
            if quart.request.method == 'GET':
                provider = await self.ap.provider_service.get_provider(provider_uuid)
                if provider is None:
                    return self.http_status(404, -1, 'provider not found')
                counts = await self.ap.provider_service.get_provider_model_counts(provider_uuid)
                provider['llm_count'] = counts['llm_count']
                provider['embedding_count'] = counts['embedding_count']
                provider['rerank_count'] = counts['rerank_count']
                return self.success(data={'provider': provider})
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.provider_service.update_provider(provider_uuid, json_data)
                return self.success()
            elif quart.request.method == 'DELETE':
                try:
                    await self.ap.provider_service.delete_provider(provider_uuid)
                    return self.success()
                except ValueError as e:
                    return self.http_status(400, -1, str(e))

        @self.route('/<provider_uuid>/scan-models', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(provider_uuid: str) -> str:
            try:
                model_type = quart.request.args.get('type')
                result = await self.ap.provider_service.scan_provider_models(provider_uuid, model_type)
                return self.success(data=result)
            except ValueError as e:
                return self.http_status(400, -1, str(e))
