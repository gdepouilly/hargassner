"""Hargassner API client — no Home Assistant dependencies."""

from __future__ import annotations

import json
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

from .const import API_CLIENT_ID, API_CLIENT_SECRET, API_LOGIN_URL, API_WIDGETS_URL


class HargassnerAuthError(Exception):
    """Raised when the API returns a 401 Unauthorized response."""


class HargassnerApiError(Exception):
    """Raised when the API returns an unexpected error."""


class HargassnerApiClient:
    """Pure-async HTTP client for the Hargassner web API."""

    async def login(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
    ) -> dict:
        """Authenticate and return token data.

        Returns a dict containing access_token, refresh_token, and expires_in.
        Raises HargassnerAuthError on 401, HargassnerApiError on other failures.
        """
        try:
            async with session.post(
                API_LOGIN_URL,
                json={
                    "email": email,
                    "password": password,
                    "client_id": API_CLIENT_ID,
                    "client_secret": API_CLIENT_SECRET,
                },
            ) as response:
                body = await response.text()
                _LOGGER.debug("Login response status=%s body=%s", response.status, body)
                if response.status == 401:
                    try:
                        error = json.loads(body).get("error", "")
                    except ValueError:
                        error = ""
                    if error == "invalid_client":
                        _LOGGER.error(
                            "Hargassner login failed with 'invalid_client'. "
                            "The hardcoded client_secret in const.py may be outdated. "
                            "Check the current value by inspecting the login request on "
                            "web.hargassner.at (DevTools → Network → login → Payload)."
                        )
                    raise HargassnerAuthError("Invalid credentials")
                if not response.ok:
                    raise HargassnerApiError(
                        f"Login failed with status {response.status}"
                    )
                return json.loads(body)
        except HargassnerAuthError:
            raise
        except HargassnerApiError:
            raise
        except aiohttp.ClientError as err:
            raise HargassnerApiError(f"Connection error during login: {err}") from err

    async def get_widgets(
        self,
        session: aiohttp.ClientSession,
        access_token: str,
        installation_id: int | str,
    ) -> dict:
        """Fetch widget data for an installation.

        Returns the parsed JSON response dict.
        Raises HargassnerAuthError on 401, HargassnerApiError on other failures.
        """
        url = API_WIDGETS_URL.format(installation_id=installation_id)
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 401:
                    raise HargassnerAuthError("Token expired or invalid")
                if not response.ok:
                    raise HargassnerApiError(
                        f"Widgets request failed with status {response.status}"
                    )
                return await response.json()
        except HargassnerAuthError:
            raise
        except HargassnerApiError:
            raise
        except aiohttp.ClientError as err:
            raise HargassnerApiError(
                f"Connection error fetching widgets: {err}"
            ) from err
