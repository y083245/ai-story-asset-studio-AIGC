"""Zhipu BigModel / GLM adapter — JWT auth via HS256.

Zhipu API keys are in the format ``{key_id}.{key_secret}``.
Authentication requires signing a JWT with the secret part using HMAC-SHA256.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64encode

import httpx

from app.modules.model_config.adapters.base import BaseProviderAdapter
from app.modules.model_config.schemas import ModelOption

_FETCH_TIMEOUT = 15.0


def _b64(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign_jwt(key_id: str, key_secret: str) -> str:
    header = {"alg": "HS256", "sign_type": "SIGN"}
    now = int(time.time())
    payload = {
        "api_key": key_id,
        "exp": now + 3600,
        "timestamp": now,
    }
    header_b64 = _b64(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    sig = hmac.new(key_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    sig_b64 = _b64(sig)
    return f"{signing_input}.{sig_b64}"


class ZhipuAdapter(BaseProviderAdapter):
    """Zhipu / GLM requires JWT signed with HMAC-SHA256."""

    auth_label = "API Key（格式：{key_id}.{key_secret}）"

    # ------------------------------------------------------------------
    async def authenticate(self, api_key: str) -> str:
        key = api_key.strip()
        if "." not in key:
            raise ValueError(
                "智谱 API Key 格式必须为 {key_id}.{key_secret}，请前往 "
                "https://open.bigmodel.cn/usercenter/apikeys 获取"
            )
        key_id, key_secret = key.split(".", 1)
        if not key_id or not key_secret:
            raise ValueError("智谱 API Key 格式无效：key_id 或 key_secret 为空")
        return _sign_jwt(key_id, key_secret)

    # ------------------------------------------------------------------
    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        """Zhipu does not expose a public models-list endpoint.

        Returns an empty list so the service layer falls back to preset models.
        """
        return []

    # ------------------------------------------------------------------
    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:
        """Send a minimal chat completions request to verify the JWT works."""
        trimmed = base_url.rstrip("/")
        url = f"{trimmed}/chat/completions"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {auth_value}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "glm-4-flash",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=body)
            if resp.status_code in {401, 403}:
                return False, f"鉴权失败 (HTTP {resp.status_code})，请检查 API Key 格式（应为 key_id.key_secret）"
            if resp.status_code < 500:
                return True, "连接成功（API Key 有效）"
            return False, f"服务器错误 (HTTP {resp.status_code})"
        except httpx.RequestError as exc:
            return False, f"网络错误: {exc}"
        except Exception as exc:
            return False, f"连接测试失败: {exc}"


def _parse_zhipu_models(data: object) -> list[ModelOption]:
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    raw = data.get("data") or []
    if not isinstance(raw, list):
        raise ValueError("Expected 'data' array")
    models: list[ModelOption] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or "").strip()
        if not mid or mid in {m.value for m in models}:
            continue
        models.append(ModelOption(value=mid, label=mid))
    models.sort(key=lambda m: m.value)
    return models
