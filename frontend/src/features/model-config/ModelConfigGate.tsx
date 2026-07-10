"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, KeyRound, Loader2, RefreshCw, Settings, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getModelConfig,
  getModelProviderPresets,
  listProviderModels,
  saveModelConfig,
  testConnection,
  type LocalModelPublicConfig,
  type ModelOption,
  type ProviderPreset,
  type ProviderPresetResponse,
} from "@/shared/api/model-config";

// ── types ───────────────────────────────────────────────────────────

interface ProviderFormState {
  provider_id: string;
  model: string;
  base_url: string;
  api_key: string;
}

const emptyProvider: ProviderFormState = {
  provider_id: "",
  model: "",
  base_url: "",
  api_key: "",
};

interface ModelListState {
  models: ModelOption[];
  source: "remote" | "preset";
  message: string;
  loading: boolean;
}

const emptyModelList: ModelListState = {
  models: [],
  source: "preset",
  message: "",
  loading: false,
};

interface ConnectionState {
  testing: boolean;
  result: { success: boolean; message: string } | null;
}

// ── provider panel component ────────────────────────────────────────

function ProviderPanel({
  title,
  providers,
  selectedProvider,
  value,
  apiKeyPreview,
  modelList,
  connection,
  showApiKeyInput,
  onProviderChange,
  onChange,
  onRefreshModels,
  onTestConnection,
  onShowApiKeyInput,
}: {
  title: string;
  providers: ProviderPreset[];
  selectedProvider?: ProviderPreset;
  value: ProviderFormState;
  apiKeyPreview?: string;
  modelList: ModelListState;
  connection: ConnectionState;
  showApiKeyInput: boolean;
  onProviderChange: (providerId: string) => void;
  onChange: (value: ProviderFormState) => void;
  onRefreshModels: () => void;
  onTestConnection: () => void;
  onShowApiKeyInput: () => void;
}) {
  return (
    <section className="space-y-3 rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
      {/* header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        {connection.result && (
          <span
            className={
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] " +
              (connection.result.success
                ? "bg-emerald-950/60 text-emerald-300"
                : "bg-red-950/60 text-red-300")
            }
          >
            {connection.result.success ? (
              <CheckCircle2 className="size-3" />
            ) : (
              <XCircle className="size-3" />
            )}
            {connection.result.success ? "已连接" : "未连接"}
          </span>
        )}
      </div>

      {/* provider selector — dropdown */}
      <div className="space-y-1.5">
        <Label className="text-neutral-300">模型厂商</Label>
        <Select value={value.provider_id} onValueChange={onProviderChange}>
          <SelectTrigger className="h-10 w-full border-neutral-700 bg-neutral-950 text-white">
            <SelectValue placeholder="选择厂商" />
          </SelectTrigger>
          <SelectContent className="border-neutral-700 bg-neutral-950 text-white">
            {providers.map((p) => (
              <SelectItem key={p.provider_id} value={p.provider_id}>
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* provider note */}
      {selectedProvider?.note && (
        <p className="text-xs text-neutral-500">{selectedProvider.note}</p>
      )}

      {/* model selector */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <Label className="text-neutral-300">模型</Label>
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 whitespace-nowrap border-neutral-700 px-2 text-xs text-neutral-300 hover:bg-neutral-800"
              onClick={onTestConnection}
              disabled={connection.testing || !value.provider_id}
            >
              {connection.testing ? (
                <Loader2 className="mr-1 size-3 animate-spin" />
              ) : null}
              测试连接
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 whitespace-nowrap border-neutral-700 px-2 text-xs text-neutral-300 hover:bg-neutral-800"
              onClick={onRefreshModels}
              disabled={modelList.loading || !value.provider_id}
            >
              {modelList.loading ? (
                <Loader2 className="mr-1 size-3 animate-spin" />
              ) : (
                <RefreshCw className="mr-1 size-3" />
              )}
              获取上游模型
            </Button>
          </div>
        </div>
        <Select
          value={value.model}
          onValueChange={(model) => onChange({ ...value, model })}
          disabled={modelList.loading || modelList.models.length === 0}
        >
          <SelectTrigger className="h-10 w-full border-neutral-700 bg-neutral-950 text-white">
            <SelectValue placeholder={modelList.loading ? "正在获取模型..." : "选择模型"} />
          </SelectTrigger>
          <SelectContent className="border-neutral-700 bg-neutral-950 text-white">
            {modelList.models.map((model) => (
              <SelectItem key={model.value} value={model.value}>
                {model.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {modelList.message && (
          <p
            className={
              modelList.source === "remote" ? "text-xs text-emerald-300" : "text-xs text-amber-300"
            }
          >
            {modelList.message}
          </p>
        )}
      </div>

      {/* base url */}
      <div className="space-y-1.5">
        <Label className="text-neutral-300">Base URL</Label>
        <Input
          value={value.base_url}
          onChange={(event) => onChange({ ...value, base_url: event.target.value })}
          className="border-neutral-700 bg-neutral-950 text-white"
        />
      </div>

      {/* api key */}
      <div className="space-y-1.5">
        <Label className="text-neutral-300">
          {selectedProvider?.auth_label || "API Key"}
        </Label>
        {showApiKeyInput ? (
          <Input
            type="password"
            value={value.api_key}
            onChange={(event) => onChange({ ...value, api_key: event.target.value })}
            placeholder={apiKeyPreview ? `已保存：${apiKeyPreview}，留空则保留` : "粘贴 API Key"}
            className="border-neutral-700 bg-neutral-950 text-white"
          />
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-9 border-neutral-700 text-neutral-300 hover:bg-neutral-800"
            onClick={() => {
              onChange({ ...value, api_key: "" });
              onShowApiKeyInput();
            }}
          >
            更换 API Key
          </Button>
        )}
        {apiKeyPreview && !showApiKeyInput && (
          <p className="text-xs text-neutral-500">已保存 Key: {apiKeyPreview}</p>
        )}
      </div>

      {/* docs link */}
      {selectedProvider?.docs_url && (
        <a
          href={selectedProvider.docs_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex text-xs text-cyan-300 hover:text-cyan-200"
        >
          查看官方文档 &rarr;
        </a>
      )}
    </section>
  );
}

// ── main gate component ─────────────────────────────────────────────

export function ModelConfigGate() {
  const [open, setOpen] = useState(false);
  const [presets, setPresets] = useState<ProviderPresetResponse | null>(null);
  const [config, setConfig] = useState<LocalModelPublicConfig | null>(null);
  const [textForm, setTextForm] = useState<ProviderFormState>(emptyProvider);
  const [imageForm, setImageForm] = useState<ProviderFormState>(emptyProvider);
  const [textModels, setTextModels] = useState<ModelListState>(emptyModelList);
  const [imageModels, setImageModels] = useState<ModelListState>(emptyModelList);
  const [textConnection, setTextConnection] = useState<ConnectionState>({
    testing: false,
    result: null,
  });
  const [imageConnection, setImageConnection] = useState<ConnectionState>({
    testing: false,
    result: null,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedIndicator, setSavedIndicator] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTextApiKeyInput, setShowTextApiKeyInput] = useState(false);
  const [showImageApiKeyInput, setShowImageApiKeyInput] = useState(false);
  const modelRequestId = useRef({ text: 0, image: 0 });

  // ── load ────────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [nextPresets, nextConfig] = await Promise.all([
          getModelProviderPresets(),
          getModelConfig(),
        ]);
        if (cancelled) return;
        setPresets(nextPresets);
        setConfig(nextConfig);

        const hasTextKey = nextConfig.text.api_key_set;
        const hasImageKey = nextConfig.image.api_key_set;

        setTextForm({
          provider_id: nextConfig.text.provider_id,
          model: nextConfig.text.model,
          base_url: nextConfig.text.base_url,
          api_key: "",
        });
        setImageForm({
          provider_id: nextConfig.image.provider_id,
          model: nextConfig.image.model,
          base_url: nextConfig.image.base_url,
          api_key: "",
        });
        setShowTextApiKeyInput(!hasTextKey);
        setShowImageApiKeyInput(!hasImageKey);

        setTextModels(modelListFromPreset(nextPresets.text_providers, nextConfig.text.provider_id));
        setImageModels(
          modelListFromPreset(nextPresets.image_providers, nextConfig.image.provider_id),
        );
        setOpen(!nextConfig.configured);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "模型配置加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedTextProvider = useMemo(
    () => presets?.text_providers.find((p) => p.provider_id === textForm.provider_id),
    [presets, textForm.provider_id],
  );
  const selectedImageProvider = useMemo(
    () => presets?.image_providers.find((p) => p.provider_id === imageForm.provider_id),
    [presets, imageForm.provider_id],
  );

  // ── computed ────────────────────────────────────────────────────

  const configuredCount = useMemo(() => {
    if (!config) return 0;
    return (config.text.api_key_set ? 1 : 0) + (config.image.api_key_set ? 1 : 0);
  }, [config]);

  // ── actions ─────────────────────────────────────────────────────

  async function refreshProviderModels(kind: "text" | "image", form: ProviderFormState) {
    const requestId = modelRequestId.current[kind] + 1;
    modelRequestId.current[kind] = requestId;
    const setModelState = kind === "text" ? setTextModels : setImageModels;
    const setFormState = kind === "text" ? setTextForm : setImageForm;

    setModelState((current) => ({ ...current, loading: true, message: "正在从上游获取模型列表..." }));
    try {
      const result = await listProviderModels({
        kind,
        provider_id: form.provider_id,
        base_url: form.base_url,
        api_key: form.api_key,
      });
      if (modelRequestId.current[kind] !== requestId) return;
      setModelState({
        models: result.models,
        source: result.source,
        message:
          result.source === "remote"
            ? `已从上游获取 ${result.models.length} 个模型`
            : result.error_message,
        loading: false,
      });
      if (result.models.length > 0) {
        setFormState((current) => {
          if (current.provider_id !== form.provider_id) return current;
          if (result.models.some((m) => m.value === current.model)) return current;
          return { ...current, model: result.models[0].value };
        });
      }
    } catch (err) {
      if (modelRequestId.current[kind] !== requestId) return;
      setModelState((current) => ({
        ...current,
        loading: false,
        source: "preset",
        message: err instanceof Error ? err.message : "获取上游模型失败，已使用内置默认模型",
      }));
    }
  }

  async function testProviderConnection(kind: "text" | "image", form: ProviderFormState) {
    const setConn = kind === "text" ? setTextConnection : setImageConnection;
    setConn({ testing: true, result: null });
    try {
      const result = await testConnection({
        kind,
        provider_id: form.provider_id,
        base_url: form.base_url,
        api_key: form.api_key,
      });
      setConn({ testing: false, result });
    } catch (err) {
      setConn({
        testing: false,
        result: {
          success: false,
          message: err instanceof Error ? err.message : "连接测试失败",
        },
      });
    }
  }

  function applyProvider(kind: "text" | "image", providerId: string) {
    const sourceList = kind === "text" ? presets?.text_providers : presets?.image_providers;
    const provider = sourceList?.find((item) => item.provider_id === providerId);
    if (!provider) return;

    const isSameProvider = providerId === (kind === "text" ? textForm.provider_id : imageForm.provider_id);
    const setForm = kind === "text" ? setTextForm : setImageForm;
    const setModels = kind === "text" ? setTextModels : setImageModels;
    const setConn = kind === "text" ? setTextConnection : setImageConnection;
    const setShowKey = kind === "text" ? setShowTextApiKeyInput : setShowImageApiKeyInput;

    // Reset connection state
    setConn({ testing: false, result: null });

    if (isSameProvider) return; // no-op if same provider

    // Check if we have a saved key for this provider
    const savedConfig = kind === "text" ? config?.text : config?.image;
    const hasSavedKey = savedConfig?.api_key_set && savedConfig.provider_id === providerId;

    setForm((current) => ({
      provider_id: provider.provider_id,
      model: provider.default_model,
      base_url: provider.base_url,
      api_key: "", // always clear in UI for security
    }));
    setShowKey(!hasSavedKey);
    setModels({ models: provider.models, source: "preset", message: "", loading: true });
    void refreshProviderModels(kind, {
      provider_id: provider.provider_id,
      model: provider.default_model,
      base_url: provider.base_url,
      api_key: "",
    });
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const saved = await saveModelConfig({
        text: textForm,
        image: imageForm,
      });
      setConfig(saved);
      setTextForm((current) => ({ ...current, api_key: "" }));
      setImageForm((current) => ({ ...current, api_key: "" }));
      setShowTextApiKeyInput(false);
      setShowImageApiKeyInput(false);
      setSavedIndicator(true);
      setTimeout(() => {
        setSavedIndicator(false);
        setOpen(false);
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存模型配置失败");
    } finally {
      setSaving(false);
    }
  }

  // ── render ──────────────────────────────────────────────────────

  return (
    <>
      {/* floating trigger button */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-5 left-5 z-40 inline-flex h-10 items-center gap-2 rounded-full border border-white/15 bg-neutral-950/80 px-4 text-xs text-white shadow-lg backdrop-blur-md transition-colors hover:border-white/30 hover:bg-neutral-900"
      >
        <Settings className="size-4" />
        模型配置
        {configuredCount > 0 && (
          <span className="inline-flex size-4 items-center justify-center rounded-full bg-cyan-600 text-[10px] font-bold text-white">
            {configuredCount}
          </span>
        )}
      </button>

      {/* dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[92vh] overflow-y-auto border-neutral-700 bg-neutral-950 text-white sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-white">
              <KeyRound className="size-5 text-cyan-200" />
              配置模型 API Key
              {savedIndicator && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-950/60 px-2 py-0.5 text-xs text-emerald-300">
                  <CheckCircle2 className="size-3" />
                  配置已保存
                </span>
              )}
            </DialogTitle>
            <DialogDescription className="text-neutral-400">
              支持国内外 15+ 大模型厂商，选择厂商后填入 API Key 即可使用。密钥保存到本地配置文件。
            </DialogDescription>
          </DialogHeader>

          {loading ? (
            <div className="flex min-h-48 items-center justify-center text-neutral-400">
              <Loader2 className="mr-2 size-4 animate-spin" />
              加载配置...
            </div>
          ) : (
            <div className="space-y-5">
              {error && (
                <div className="rounded-md border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-300">
                  {error}
                </div>
              )}

              <ProviderPanel
                title="提示词提取模型"
                providers={presets?.text_providers ?? []}
                selectedProvider={selectedTextProvider}
                value={textForm}
                apiKeyPreview={
                  config?.text.provider_id === textForm.provider_id
                    ? config.text.api_key_preview
                    : ""
                }
                modelList={textModels}
                connection={textConnection}
                showApiKeyInput={showTextApiKeyInput}
                onProviderChange={(providerId) => applyProvider("text", providerId)}
                onChange={setTextForm}
                onRefreshModels={() => refreshProviderModels("text", textForm)}
                onTestConnection={() => testProviderConnection("text", textForm)}
                onShowApiKeyInput={() => setShowTextApiKeyInput(true)}
              />

              <ProviderPanel
                title="图片生成模型"
                providers={presets?.image_providers ?? []}
                selectedProvider={selectedImageProvider}
                value={imageForm}
                apiKeyPreview={
                  config?.image.provider_id === imageForm.provider_id
                    ? config.image.api_key_preview
                    : ""
                }
                modelList={imageModels}
                connection={imageConnection}
                showApiKeyInput={showImageApiKeyInput}
                onProviderChange={(providerId) => applyProvider("image", providerId)}
                onChange={setImageForm}
                onRefreshModels={() => refreshProviderModels("image", imageForm)}
                onTestConnection={() => testProviderConnection("image", imageForm)}
                onShowApiKeyInput={() => setShowImageApiKeyInput(true)}
              />

              <div className="rounded-md border border-neutral-800 bg-neutral-900/70 px-3 py-2 text-xs leading-5 text-neutral-400">
                本地配置文件：{" "}
                <span className="font-mono text-neutral-200">
                  {config?.config_path || "local_config/model-providers.json"}
                </span>
                。以后可重新打开此弹窗切换，也可直接编辑该 JSON 文件。
              </div>
            </div>
          )}

          <DialogFooter className="border-neutral-800 bg-neutral-900">
            <Button
              variant="outline"
              className="border-neutral-700 text-neutral-200 hover:bg-neutral-800"
              onClick={() => setOpen(false)}
              disabled={saving}
            >
              稍后配置
            </Button>
            <Button
              className="bg-cyan-600 text-white hover:bg-cyan-500"
              onClick={handleSave}
              disabled={saving || loading}
            >
              {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
              保存配置
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── helpers ─────────────────────────────────────────────────────────

function modelListFromPreset(providers: ProviderPreset[], providerId: string): ModelListState {
  const provider = providers.find((item) => item.provider_id === providerId);
  return {
    models: provider?.models ?? [],
    source: "preset",
    message: "",
    loading: false,
  };
}
