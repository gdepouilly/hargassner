"""Tests for the HTTP client (token handling and request shapes)."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.hargassner.api import (
    HargassnerApiClient,
    HargassnerApiError,
    HargassnerAuthError,
)
from custom_components.hargassner.const import API_BASE_URL, API_CLIENT_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

LOGIN_URL = f"{API_BASE_URL}/auth/login"
REFRESH_URL = f"{API_BASE_URL}/auth/refresh"
WIDGETS_URL = f"{API_BASE_URL}/installations/12345/widgets"
MODE_RESOURCE = "/installations/12345/widgets/heating-circuits/1/parameters/mode"


def _tokens(n: int) -> dict:
    return {
        "access_token": f"access-{n}",
        "refresh_token": f"refresh-{n}",
        "token_type": "Bearer",
        "expires_in": 10800,
    }


def _client(hass: HomeAssistant) -> HargassnerApiClient:
    return HargassnerApiClient(async_get_clientsession(hass), "u@example.com", "pw")


async def test_login_sends_client_credentials(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Login posts email/password plus the portal client id/secret."""
    aioclient_mock.post(LOGIN_URL, json=_tokens(1))
    aioclient_mock.get(WIDGETS_URL, json={"data": [], "meta": {}})

    await _client(hass).async_get_widgets(12345)

    _, _, login_body, _ = aioclient_mock.mock_calls[0]
    assert login_body["email"] == "u@example.com"
    assert login_body["password"] == "pw"
    assert login_body["client_id"] == API_CLIENT_ID
    assert len(login_body["client_secret"]) == 40
    _, _, _, headers = aioclient_mock.mock_calls[1]
    assert headers["Authorization"] == "Bearer access-1"


async def test_login_invalid_credentials(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 401 on login is an auth error."""
    aioclient_mock.post(
        LOGIN_URL, status=HTTPStatus.UNAUTHORIZED, json={"error": "invalid_grant"}
    )
    with pytest.raises(HargassnerAuthError):
        await _client(hass).async_login()


async def test_expired_token_uses_refresh_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """On 401 the client refreshes the token and retries once."""
    responses = iter(
        [(HTTPStatus.UNAUTHORIZED, {}), (HTTPStatus.OK, {"data": [], "meta": {}})]
    )

    async def widgets(method, url, data):
        status, body = next(responses)
        return AiohttpClientMockResponse(method, url, status=status, json=body)

    aioclient_mock.post(LOGIN_URL, json=_tokens(1))
    aioclient_mock.post(REFRESH_URL, json=_tokens(2))
    aioclient_mock.get(WIDGETS_URL, side_effect=widgets)

    assert await _client(hass).async_get_widgets(12345) == {"data": [], "meta": {}}

    urls = [str(call[1]) for call in aioclient_mock.mock_calls]
    assert urls == [LOGIN_URL, WIDGETS_URL, REFRESH_URL, WIDGETS_URL]
    _, _, refresh_body, _ = aioclient_mock.mock_calls[2]
    assert refresh_body["refresh_token"] == "refresh-1"
    _, _, _, headers = aioclient_mock.mock_calls[3]
    assert headers["Authorization"] == "Bearer access-2"


async def test_failed_refresh_falls_back_to_login(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """When the refresh token is rejected, the client logs in again."""
    responses = iter(
        [(HTTPStatus.UNAUTHORIZED, {}), (HTTPStatus.OK, {"data": [], "meta": {}})]
    )

    async def widgets(method, url, data):
        status, body = next(responses)
        return AiohttpClientMockResponse(method, url, status=status, json=body)

    aioclient_mock.post(LOGIN_URL, json=_tokens(1))
    aioclient_mock.post(REFRESH_URL, status=HTTPStatus.UNAUTHORIZED, json={})
    aioclient_mock.get(WIDGETS_URL, side_effect=widgets)

    await _client(hass).async_get_widgets(12345)

    urls = [str(call[1]) for call in aioclient_mock.mock_calls]
    assert urls == [LOGIN_URL, WIDGETS_URL, REFRESH_URL, LOGIN_URL, WIDGETS_URL]


async def test_set_parameter_patches_resource(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Parameter writes are PATCH <resource> with {"value": ...}."""
    aioclient_mock.post(LOGIN_URL, json=_tokens(1))
    aioclient_mock.patch(f"{API_BASE_URL}{MODE_RESOURCE}", json={})

    await _client(hass).async_set_parameter(MODE_RESOURCE, "MODE_AUTOMATIC")

    method, url, body, _ = aioclient_mock.mock_calls[1]
    assert method == "PATCH"
    assert str(url) == f"{API_BASE_URL}{MODE_RESOURCE}"
    assert body == {"value": "MODE_AUTOMATIC"}


async def test_set_parameter_rejects_foreign_resource(hass: HomeAssistant) -> None:
    """Only installation resources may be written."""
    with pytest.raises(HargassnerApiError):
        await _client(hass).async_set_parameter("https://evil.example/x", 1)


async def test_server_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Non-2xx responses raise HargassnerApiError."""
    aioclient_mock.post(LOGIN_URL, json=_tokens(1))
    aioclient_mock.get(WIDGETS_URL, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    with pytest.raises(HargassnerApiError):
        await _client(hass).async_get_widgets(12345)
