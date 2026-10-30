"""Hargassner web portal API client — no Home Assistant dependencies."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_CLIENT_ID, API_CLIENT_SECRET

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class HargassnerAuthError(Exception):
    """Raised when credentials or tokens are rejected."""


class HargassnerApiError(Exception):
    """Raised on connection errors or unexpected API responses."""


class HargassnerApiClient:
    """Async client for https://web.hargassner.at/api.

    Tokens are kept in memory only. On a 401 the client first tries the
    refresh token, then falls back to a full login, and retries once.
    """

    def __init__(
        self, session: aiohttp.ClientSession, email: str, password: str
    ) -> None:
        """Store the session and credentials."""
        self._session = session
        self._email = email
        self._password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    async def async_login(self) -> None:
        """Log in with email and password."""
        status, body = await self._send(
            "POST",
            "/auth/login",
            {
                "email": self._email,
                "password": self._password,
                "client_id": API_CLIENT_ID,
                "client_secret": API_CLIENT_SECRET,
            },
            auth=False,
        )
        if status in (400, 401, 422):
            if isinstance(body, dict) and body.get("error") == "invalid_client":
                _LOGGER.error(
                    "Hargassner rejected the client_secret ('invalid_client'). "
                    "The portal may have rotated it; check the login request "
                    "payload on web.hargassner.at"
                )
            raise HargassnerAuthError("Invalid credentials")
        if status != 200:
            raise HargassnerApiError(f"Login failed with status {status}")
        self._store_tokens(body)

    async def async_get_installations(self) -> list[dict[str, Any]]:
        """Return the installations visible to this account."""
        body = await self._request(
            "GET", "/installations?sort=name&pageSize=100&page=1"
        )
        return body.get("data", [])

    async def async_get_widgets(self, installation_id: int) -> dict[str, Any]:
        """Return the widgets payload (`data` list and `meta` dict)."""
        return await self._request("GET", f"/installations/{installation_id}/widgets")

    async def async_get_event_counts(self, installation_id: int) -> dict[str, Any]:
        """Return active/history counts per event type."""
        body = await self._request(
            "GET", f"/installations/{installation_id}/events-counts"
        )
        return body.get("data", {})

    async def async_set_parameter(self, resource: str, value: Any) -> None:
        """Write a widget parameter, e.g. a heating circuit mode.

        `resource` is the path given in `parameters.<name>.resource`.
        """
        if not resource.startswith("/installations/"):
            raise HargassnerApiError(f"Unexpected parameter resource: {resource}")
        await self._request("PATCH", resource, {"value": value})

    async def _request(
        self, method: str, path: str, json_body: dict[str, Any] | None = None
    ) -> Any:
        """Send an authenticated request, renewing the token once on 401."""
        if self._access_token is None:
            await self.async_login()

        status, body = await self._send(method, path, json_body)
        if status == 401:
            if not await self._async_refresh():
                await self.async_login()
            status, body = await self._send(method, path, json_body)
            if status == 401:
                raise HargassnerAuthError("Access token rejected after renewal")

        if not 200 <= status < 300:
            raise HargassnerApiError(f"{method} {path} failed with status {status}")
        return body if body is not None else {}

    async def _async_refresh(self) -> bool:
        """Renew the access token with the refresh token; False if that fails."""
        if self._refresh_token is None:
            return False
        status, body = await self._send(
            "POST",
            "/auth/refresh",
            {
                "refresh_token": self._refresh_token,
                "client_id": API_CLIENT_ID,
                "client_secret": API_CLIENT_SECRET,
            },
            auth=False,
        )
        if status != 200:
            _LOGGER.debug("Token refresh failed with status %s, logging in", status)
            self._access_token = self._refresh_token = None
            return False
        self._store_tokens(body)
        return True

    def _store_tokens(self, body: Any) -> None:
        """Keep the tokens from a login/refresh response."""
        if not isinstance(body, dict) or "access_token" not in body:
            raise HargassnerApiError("Token response without access_token")
        self._access_token = body["access_token"]
        self._refresh_token = body.get("refresh_token")

    async def _send(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        *,
        auth: bool = True,
    ) -> tuple[int, Any]:
        """Perform one HTTP request and return (status, parsed JSON or None)."""
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self._access_token}"
        try:
            async with self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                json=json_body,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                try:
                    body = await response.json(content_type=None)
                except ValueError:
                    body = None
                return response.status, body
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HargassnerApiError(f"Connection error on {method} {path}") from err
