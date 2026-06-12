from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from tests.factories import FakeApp


pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
def mock_circular_import_chain():
    from tests.utils.import_isolation import MockLifecycleControlScope, isolated_sys_modules

    class FakeMinimalApplication:
        pass

    mock_app = MagicMock()
    mock_app.Application = FakeMinimalApplication

    mock_entities = MagicMock()
    mock_entities.LifecycleControlScope = MockLifecycleControlScope

    clear = [
        'langbot.pkg.api.http.controller.group',
        'langbot.pkg.api.http.controller.groups',
        'langbot.pkg.api.http.controller.groups.sales',
        'langbot.pkg.api.http.controller.main',
    ]

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        import langbot.pkg.api.http.controller.groups.sales as _sales  # noqa: E402, F401

        yield


@pytest.fixture(scope='module')
def fake_sales_app():
    app = FakeApp()
    app.instance_config.data.update({
        'api': {'port': 5300},
        'system': {'allow_modify_login_info': True, 'limitation': {}},
    })

    app.user_service = Mock()
    app.user_service.is_initialized = AsyncMock(return_value=True)
    app.user_service.verify_jwt_token = AsyncMock(return_value='test@example.com')
    app.user_service.get_user_by_email = AsyncMock(return_value=Mock(email='test@example.com'))

    app.sales_service = Mock()
    app.sales_service.open_handoff_from_session = AsyncMock(
        return_value={
            'id': 7,
            'session_id': 'person_customer-1',
            'status': 'open',
        }
    )
    app.sales_service.reply_handoff_from_session = AsyncMock(return_value={'sent': True, 'handoff_id': 7})
    app.sales_service.get_sales_conversations = AsyncMock(
        return_value=[
            {
                'session_id': 'person_customer-1',
                'customer_name': '客户A',
                'latest_message_preview': '真实消息',
                'handoff_status': 'ai_hosted',
            }
        ]
    )
    app.sales_service.get_sales_conversation_messages = AsyncMock(
        return_value={'messages': [{'id': 'msg-1', 'preview': '真实消息'}], 'total': 1}
    )
    app.sales_service.send_operator_message_from_session = AsyncMock(return_value={'sent': True, 'handoff_id': None})
    app.sales_service.restore_ai_hosting_from_session = AsyncMock(return_value={'restored': True, 'handoff_id': 7})

    return app


@pytest.fixture(scope='module')
async def quart_test_client(fake_sales_app, http_controller_cls):
    controller = http_controller_cls(fake_sales_app)
    await controller.initialize()

    client = controller.quart_app.test_client()
    yield client


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestSalesHandoffEndpoint:
    @pytest.mark.asyncio
    async def test_open_handoff_from_session_success(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.post(
            '/api/v1/sales/handoffs/from-session',
            json={
                'session_id': 'person_customer-1',
                'reason': 'Manual takeover',
                'assigned_to': 'sales-admin',
            },
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert data['data']['handoff']['session_id'] == 'person_customer-1'
        fake_sales_app.sales_service.open_handoff_from_session.assert_awaited_once_with(
            'person_customer-1',
            'Manual takeover',
            'sales-admin',
        )

    @pytest.mark.asyncio
    async def test_reply_handoff_from_session_success(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.post(
            '/api/v1/sales/handoffs/from-session/reply',
            json={
                'session_id': 'person_customer-1',
                'reply': '人工已接入',
                'assigned_to': 'sales-admin',
            },
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert data['data']['sent'] is True
        fake_sales_app.sales_service.reply_handoff_from_session.assert_awaited_once_with(
            'person_customer-1',
            '人工已接入',
            'sales-admin',
        )

    @pytest.mark.asyncio
    async def test_get_sales_conversations_success(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.get(
            '/api/v1/sales/conversations?status=ai_hosted',
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['data']['conversations'][0]['latest_message_preview'] == '真实消息'
        fake_sales_app.sales_service.get_sales_conversations.assert_awaited_with(
            status='ai_hosted',
            limit=100,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_get_sales_conversation_messages_success(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.get(
            '/api/v1/sales/conversations/person_customer-1/messages',
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['data']['messages'][0]['preview'] == '真实消息'
        fake_sales_app.sales_service.get_sales_conversation_messages.assert_awaited_with(
            'person_customer-1',
            limit=200,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_normal_manual_reply_does_not_request_ai_pause(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.post(
            '/api/v1/sales/conversations/person_customer-1/manual-reply',
            json={'reply': '人工补充', 'assigned_to': 'sales-admin'},
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        fake_sales_app.sales_service.send_operator_message_from_session.assert_awaited_once_with(
            'person_customer-1',
            '人工补充',
            'sales-admin',
            pause_ai=False,
        )

    @pytest.mark.asyncio
    async def test_restore_ai_hosting_endpoint_success(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.post(
            '/api/v1/sales/conversations/person_customer-1/handoff/restore',
            json={'assigned_to': 'sales-admin'},
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['data']['restored'] is True
        fake_sales_app.sales_service.restore_ai_hosting_from_session.assert_awaited_once_with(
            'person_customer-1',
            'sales-admin',
        )
