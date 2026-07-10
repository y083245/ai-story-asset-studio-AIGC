"""Official-provider presets for text extraction and image generation.

Each preset maps to a registered adapter that handles auth and model-list retrieval.
"""

from __future__ import annotations

from app.modules.model_config.adapters.registry import get_adapter_registry
from app.modules.model_config.schemas import (
    ModelOption,
    ProviderPreset,
    ProviderPresetResponse,
)

# ── helpers ──────────────────────────────────────────────────────────


def _auth_label(provider_id: str) -> str:
    return get_adapter_registry().get(provider_id).auth_label


def _preset(
    provider_id: str,
    label: str,
    base_url: str,
    default_model: str,
    models: list[ModelOption],
    docs_url: str,
    note: str = "",
) -> ProviderPreset:
    return ProviderPreset(
        provider_id=provider_id,
        label=label,
        base_url=base_url,
        default_model=default_model,
        models=models,
        docs_url=docs_url,
        note=note,
        auth_label=_auth_label(provider_id),
    )


# ── text providers ───────────────────────────────────────────────────

TEXT_PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    # ── International ──
    _preset(
        "openai",
        "OpenAI",
        "https://api.openai.com/v1",
        "gpt-4o",
        [
            ModelOption(value="gpt-4o", label="GPT-4o"),
            ModelOption(value="gpt-4o-mini", label="GPT-4o Mini"),
            ModelOption(value="gpt-4.1", label="GPT-4.1"),
            ModelOption(value="gpt-4.1-mini", label="GPT-4.1 Mini"),
            ModelOption(value="gpt-4.1-nano", label="GPT-4.1 Nano"),
            ModelOption(value="o4-mini", label="o4 Mini"),
            ModelOption(value="o3", label="o3"),
        ],
        "https://platform.openai.com/docs",
        "标准 OpenAI API。",
    ),
    _preset(
        "anthropic",
        "Anthropic Claude",
        "https://api.anthropic.com/v1",
        "claude-sonnet-4-6",
        [
            ModelOption(value="claude-opus-4-8", label="Claude Opus 4.8"),
            ModelOption(value="claude-sonnet-4-6", label="Claude Sonnet 4.6"),
            ModelOption(value="claude-haiku-4-5-20251001", label="Claude Haiku 4.5"),
            ModelOption(value="claude-fable-5", label="Claude Fable 5"),
            ModelOption(value="claude-opus-4-5", label="Claude Opus 4.5"),
            ModelOption(value="claude-opus-4", label="Claude Opus 4"),
            ModelOption(value="claude-sonnet-4-5", label="Claude Sonnet 4.5"),
            ModelOption(value="claude-sonnet-4", label="Claude Sonnet 4"),
            ModelOption(value="claude-3-5-sonnet-20241022", label="Claude 3.5 Sonnet"),
            ModelOption(value="claude-3-5-haiku-20241022", label="Claude 3.5 Haiku"),
        ],
        "https://docs.anthropic.com/en/docs/about-claude/models",
        "Anthropic 使用 x-api-key 鉴权，模型列表为内置更新。",
    ),
    _preset(
        "google_gemini",
        "Google Gemini",
        "https://generativelanguage.googleapis.com/v1beta",
        "gemini-2.5-flash",
        [
            ModelOption(value="gemini-3-pro-preview", label="Gemini 3 Pro Preview"),
            ModelOption(value="gemini-3-flash-preview", label="Gemini 3 Flash Preview"),
            ModelOption(value="gemini-2.5-pro", label="Gemini 2.5 Pro"),
            ModelOption(value="gemini-2.5-flash", label="Gemini 2.5 Flash"),
            ModelOption(value="gemini-2.0-flash", label="Gemini 2.0 Flash"),
            ModelOption(value="gemini-2.0-flash-lite", label="Gemini 2.0 Flash Lite"),
        ],
        "https://ai.google.dev/gemini-api/docs",
        "Google Gemini 使用 query param 鉴权（?key=）。",
    ),
    _preset(
        "xai",
        "xAI Grok",
        "https://api.x.ai/v1",
        "grok-4",
        [
            ModelOption(value="grok-4", label="Grok 4"),
            ModelOption(value="grok-4-mini", label="Grok 4 Mini"),
            ModelOption(value="grok-3", label="Grok 3"),
        ],
        "https://docs.x.ai/docs",
        "OpenAI 兼容 API。",
    ),
    _preset(
        "mistral",
        "Mistral AI",
        "https://api.mistral.ai/v1",
        "mistral-large-latest",
        [
            ModelOption(value="mistral-large-latest", label="Mistral Large"),
            ModelOption(value="mistral-medium-latest", label="Mistral Medium"),
            ModelOption(value="mistral-small-latest", label="Mistral Small"),
            ModelOption(value="codestral-latest", label="Codestral"),
        ],
        "https://docs.mistral.ai/api/",
        "OpenAI 兼容 API。",
    ),
    _preset(
        "openrouter",
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        "openai/gpt-4o",
        [
            ModelOption(value="openai/gpt-4o", label="GPT-4o"),
            ModelOption(value="anthropic/claude-sonnet-4-6", label="Claude Sonnet 4.6"),
            ModelOption(value="google/gemini-2.5-flash", label="Gemini 2.5 Flash"),
            ModelOption(value="meta-llama/llama-4-maverick", label="Llama 4 Maverick"),
        ],
        "https://openrouter.ai/docs",
        "多厂商 API 聚合网关，一个 Key 访问多个厂商。",
    ),
    _preset(
        "together",
        "Together AI",
        "https://api.together.xyz/v1",
        "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        [
            ModelOption(value="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8", label="Llama 4 Maverick"),
            ModelOption(value="deepseek-ai/DeepSeek-V3", label="DeepSeek V3"),
            ModelOption(value="Qwen/Qwen3-235B-A22B", label="Qwen 3 235B"),
        ],
        "https://docs.together.ai/docs",
        "开源模型推理平台，OpenAI 兼容 API。",
    ),
    _preset(
        "siliconflow",
        "SiliconFlow (硅基流动)",
        "https://api.siliconflow.cn/v1",
        "Qwen/Qwen3-235B-A22B",
        [
            ModelOption(value="Qwen/Qwen3-235B-A22B", label="Qwen 3 235B"),
            ModelOption(value="deepseek-ai/DeepSeek-V3", label="DeepSeek V3"),
            ModelOption(value="Pro/DeepSeek-R1", label="DeepSeek R1"),
        ],
        "https://docs.siliconflow.cn/",
        "国内模型聚合平台，OpenAI 兼容 API。",
    ),

    # ── Domestic ──
    _preset(
        "deepseek",
        "DeepSeek",
        "https://api.deepseek.com",
        "deepseek-v4-flash",
        [
            ModelOption(value="deepseek-v4-flash", label="DeepSeek V4 Flash"),
            ModelOption(value="deepseek-v4-pro", label="DeepSeek V4 Pro"),
            ModelOption(value="deepseek-chat", label="DeepSeek Chat"),
            ModelOption(value="deepseek-reasoner", label="DeepSeek Reasoner"),
        ],
        "https://api-docs.deepseek.com/",
        "OpenAI 兼容 Chat Completions。",
    ),
    _preset(
        "aliyun_bailian",
        "阿里云百炼 / 通义千问",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-plus",
        [
            ModelOption(value="qwen-plus", label="Qwen Plus"),
            ModelOption(value="qwen-max", label="Qwen Max"),
            ModelOption(value="qwen-turbo", label="Qwen Turbo"),
            ModelOption(value="qwen3-235b-a22b", label="Qwen 3 235B"),
        ],
        "https://help.aliyun.com/zh/model-studio/",
        "通过 DashScope 兼容接口使用，需在阿里云控制台获取 API Key。",
    ),
    _preset(
        "baidu_qianfan",
        "百度千帆 / 文心",
        "https://qianfan.baidubce.com/v2",
        "ernie-4.5-turbo-128k",
        [
            ModelOption(value="ernie-4.5-turbo-128k", label="ERNIE 4.5 Turbo 128K"),
            ModelOption(value="ernie-x1-turbo-32k", label="ERNIE X1 Turbo 32K"),
        ],
        "https://cloud.baidu.com/doc/qianfan/s/Hmh4suq26",
        "需要 Access Key + Secret Key（格式 ak:sk）。",
    ),
    _preset(
        "tencent_hunyuan",
        "腾讯混元",
        "https://api.hunyuan.cloud.tencent.com/v1",
        "hunyuan-turbos-latest",
        [
            ModelOption(value="hunyuan-turbos-latest", label="Hunyuan Turbos Latest"),
            ModelOption(value="hunyuan-large", label="Hunyuan Large"),
        ],
        "https://cloud.tencent.com/document/product/1729/111007",
        "使用控制台 OpenAI 兼容 API Key。",
    ),
    _preset(
        "moonshot_kimi",
        "Moonshot / Kimi",
        "https://api.moonshot.cn/v1",
        "kimi-k2.6",
        [
            ModelOption(value="kimi-k2.6", label="Kimi K2.6"),
            ModelOption(value="moonshot-v1-128k", label="Moonshot v1 128K"),
            ModelOption(value="moonshot-v1-32k", label="Moonshot v1 32K"),
        ],
        "https://platform.kimi.ai/docs/api/overview",
        "OpenAI 兼容 Chat Completions。",
    ),
    _preset(
        "zhipu_bigmodel",
        "智谱 BigModel / GLM",
        "https://open.bigmodel.cn/api/paas/v4",
        "glm-5.2",
        [
            ModelOption(value="glm-5.2", label="GLM 5.2"),
            ModelOption(value="glm-4.6", label="GLM 4.6"),
            ModelOption(value="glm-4.5", label="GLM 4.5"),
        ],
        "https://docs.bigmodel.cn/cn/guide/develop/openai/introduction",
        "API Key 格式为 {key_id}.{key_secret}，使用 JWT 鉴权。",
    ),
    _preset(
        "volcengine_ark",
        "火山方舟 / 豆包大模型",
        "https://ark.cn-beijing.volces.com/api/v3",
        "doubao-1-5-pro-32k-250115",
        [
            ModelOption(value="doubao-1-5-pro-32k-250115", label="Doubao 1.5 Pro 32K"),
            ModelOption(value="doubao-1-5-lite-32k-250115", label="Doubao 1.5 Lite 32K"),
        ],
        "https://www.volcengine.com/docs/82379/1330626",
        "方舟也可使用控制台 Endpoint ID 作为模型名。",
    ),
)

# ── image providers ──────────────────────────────────────────────────

IMAGE_PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    _preset(
        "doubao_seedream",
        "豆包 Seedream",
        "https://ark.cn-beijing.volces.com/api/v3",
        "doubao-seedream-5-0-lite-260128",
        [
            ModelOption(value="doubao-seedream-5-0-lite-260128", label="Seedream 5.0 Lite"),
            ModelOption(value="doubao-seedream-5-0-260128", label="Seedream 5.0"),
            ModelOption(value="doubao-seedream-5-0-pro-260628", label="Seedream 5.0 Pro"),
            ModelOption(value="doubao-seedream-4-5-251128", label="Seedream 4.5"),
            ModelOption(value="doubao-seedream-4.0", label="Seedream 4.0"),
        ],
        "https://www.volcengine.com/docs/82379/1541523",
        "图片生成使用豆包 Seedream 系列。",
    ),
    _preset(
        "replicate",
        "Replicate (Flux)",
        "https://api.replicate.com/v1",
        "black-forest-labs/flux-pro",
        [
            ModelOption(value="black-forest-labs/flux-pro", label="Flux Pro"),
            ModelOption(value="black-forest-labs/flux-schnell", label="Flux Schnell"),
            ModelOption(value="black-forest-labs/flux-dev", label="Flux Dev"),
        ],
        "https://replicate.com/docs",
        "Replicate 平台托管的 Flux 图像生成模型。",
    ),
    _preset(
        "google_imagen",
        "Google Imagen",
        "https://generativelanguage.googleapis.com/v1beta",
        "imagen-4.0-generate-001",
        [
            ModelOption(value="imagen-4.0-generate-001", label="Imagen 4"),
            ModelOption(value="imagen-4.0-ultra-generate-001", label="Imagen 4 Ultra"),
            ModelOption(value="imagen-4.0-fast-generate-001", label="Imagen 4 Fast"),
        ],
        "https://ai.google.dev/gemini-api/docs/imagen",
        "Google Imagen 4。官方已标注 Imagen 将于 2026-08-17 下线，后续需迁移 Nano Banana。",
    ),
    _preset(
        "openai",
        "OpenAI DALL·E",
        "https://api.openai.com/v1",
        "dall-e-3",
        [
            ModelOption(value="dall-e-3", label="DALL·E 3"),
            ModelOption(value="dall-e-2", label="DALL·E 2"),
            ModelOption(value="gpt-image-2", label="GPT Image 2"),
        ],
        "https://platform.openai.com/docs/guides/images",
        "通过 OpenAI Images API 生成图片。",
    ),
)


def provider_presets() -> ProviderPresetResponse:
    return ProviderPresetResponse(
        text_providers=list(TEXT_PROVIDER_PRESETS),
        image_providers=list(IMAGE_PROVIDER_PRESETS),
    )
