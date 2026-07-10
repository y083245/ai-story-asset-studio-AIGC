export interface ModelOption {
  value: string;
  label: string;
}

export interface ProviderPreset {
  provider_id: string;
  label: string;
  base_url: string;
  default_model: string;
  models: ModelOption[];
  docs_url: string;
  note: string;
  auth_label: string;
}

export interface ProviderPresetResponse {
  text_providers: ProviderPreset[];
  image_providers: ProviderPreset[];
}

export interface ProviderModelListRequest {
  kind: "text" | "image";
  provider_id: string;
  base_url: string;
  api_key: string;
}

export interface ProviderModelListResponse {
  provider_id: string;
  models: ModelOption[];
  source: "remote" | "preset";
  error_message: string;
}

export interface TestConnectionRequest {
  kind: "text" | "image";
  provider_id: string;
  base_url: string;
  api_key: string;
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
}

export interface ModelProviderPublicConfig {
  provider_id: string;
  model: string;
  base_url: string;
  api_key_set: boolean;
  api_key_preview: string;
}

export interface LocalModelPublicConfig {
  configured: boolean;
  config_path: string;
  text: ModelProviderPublicConfig;
  image: ModelProviderPublicConfig;
}

export interface ModelProviderConfigInput {
  provider_id: string;
  model: string;
  base_url: string;
  api_key: string;
}

export interface LocalModelConfigInput {
  text: ModelProviderConfigInput;
  image: ModelProviderConfigInput;
}

export function getModelProviderPresets(): Promise<ProviderPresetResponse> {
  return modelConfigFetch<ProviderPresetResponse>("/api/model-config/presets");
}

export function getModelConfig(): Promise<LocalModelPublicConfig> {
  return modelConfigFetch<LocalModelPublicConfig>("/api/model-config");
}

export function saveModelConfig(payload: LocalModelConfigInput): Promise<LocalModelPublicConfig> {
  return modelConfigFetch<LocalModelPublicConfig>("/api/model-config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function listProviderModels(payload: ProviderModelListRequest): Promise<ProviderModelListResponse> {
  return modelConfigFetch<ProviderModelListResponse>("/api/model-config/models", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function testConnection(payload: TestConnectionRequest): Promise<TestConnectionResponse> {
  return modelConfigFetch<TestConnectionResponse>("/api/model-config/test-connection", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function modelConfigFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let message = `模型配置请求失败：${response.status}`;
    try {
      const data = await response.json();
      if (typeof data?.detail?.message === "string") message = data.detail.message;
      else if (typeof data?.error?.message === "string") message = data.error.message;
    } catch {
      // keep default message
    }
    throw new Error(message);
  }

  return response.json();
}
