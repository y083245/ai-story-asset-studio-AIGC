"""Baidu Qianfan / ERNIE adapter — AK/SK → OAuth access token.

Baidu Qianfan uses API Key + Secret Key to obtain a short-lived access token
via ``https://aip.baidubce.com/oauth/2.0/token``, then uses that token as Bearer.
"""

from __future__ import annotations

import httpx

from app.modules.model_config.adapters.base import BaseProviderAdapter
from app.modules.model_config.schemas import ModelOption

_FETCH_TIMEOUT = 15.0
_OAUTH_URL = "https://aip.baidubce.com/oauth/2.0/token"


class BaiduQianfanAdapter(BaseProviderAdapter):
    """Baidu uses AK/SK to exchange for an access token, then standard Bearer."""

    auth_label = "API Key（格式：{access_key}:{secret_key}）"

    # ------------------------------------------------------------------
    async def authenticate(self, api_key: str) -> str:
        """Exchange AK:SK for an access token."""
        key = api_key.strip()

        # Accept both "ak:sk" and "ak" (if user only pastes one value).
        if ":" in key:
            ak, sk = key.split(":", 1)
        else:
            # Also try "." separator (some users may paste that way).
            if "." in key:
                ak, sk = key.split(".", 1)
            else:
                raise ValueError(
                    "百度千帆需要 Access Key 和 Secret Key，格式为 {ak}:{sk}，"
                    "请前往 https://console.bce.baidu.com/iam/#/iam/accesslist 获取"
                )

        ak = ak.strip()
        sk = sk.strip()
        if not ak or not sk:
            raise ValueError("百度千帆 Access Key 或 Secret Key 为空")

        params = {
            "grant_type": "client_credentials",
            "client_id": ak,
            "client_secret": sk,
        }
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
            resp = await client.post(_OAUTH_URL, params=params, headers={"Accept": "application/json"})
            resp.raise_for_status()
            token_data = resp.json()

        if "access_token" not in token_data:
            error = token_data.get("error_description") or token_data.get("error") or str(token_data)
            raise ValueError(f"获取百度千帆 access_token 失败: {error}")

        return str(token_data["access_token"])

    # ------------------------------------------------------------------
    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        """Baidu Qianfan model listing uses a proprietary HMAC-signed endpoint.

        Returns an empty list so the service layer falls back to preset models.
        """
        return []

    # ------------------------------------------------------------------
    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:
        """Send a minimal chat completions request to verify the token."""
        trimmed = base_url.rstrip("/")
        url = f"{trimmed}/chat/completions"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {auth_value}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "ernie-4.5-turbo-128k",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=body)
            if resp.status_code in {401, 403}:
                return False, f"鉴权失败 (HTTP {resp.status_code})，请检查 Access Key 和 Secret Key"
            if resp.status_code < 500:
                return True, "连接成功（API Key 有效）"
            return False, f"服务器错误 (HTTP {resp.status_code})"
        except httpx.RequestError as exc:
            return False, f"网络错误: {exc}"
        except Exception as exc:
            return False, f"连接测试失败: {exc}"


def _parse_qianfan_models(data: object) -> list[ModelOption]:
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    # Baidu returns {"result": [...]} or {"data": [...]}
    raw = data.get("result") or data.get("data") or []
    if not isinstance(raw, list):
        raise ValueError("Expected model list array")
    models: list[ModelOption] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("modelName") or item.get("id") or "").strip()
        if not mid or mid in {m.value for m in models}:
            continue
        models.append(ModelOption(value=mid, label=mid))
    models.sort(key=lambda m: m.value)
    return models
