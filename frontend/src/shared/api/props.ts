// =============================================================================
// Story Engine — Props API
// =============================================================================

import { USE_MOCK, apiFetch } from "@/shared/api/client";
import { resolveAssetUrl } from "@/shared/api/asset-url";
import { getMockProps } from "@/shared/api/mock-data";
import type {
  PropResponse,
  PropListResponse,
  PropUpdateRequest,
  PropRegenerateResponse,
} from "@/shared/types";

interface BackendPropResponse {
  id: string;
  project_id: string;
  prop_id: string;
  name: string;
  visual_features?: string;
  plot_function?: string;
  state_timeline?: Array<{ step_index?: number; state?: string; description?: string }>;
  prop_prompt?: string;
  usage_prompt?: string;
  reference_assets?: string[];
  created_at: string;
  updated_at: string;
}

interface BackendPropListResponse {
  props: BackendPropResponse[];
  total: number;
}

// ---------------------------------------------------------------------------
// List
// ---------------------------------------------------------------------------

export async function listProps(
  projectId: string
): Promise<PropListResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockProps(projectId);
  }
  const response = await apiFetch<BackendPropListResponse>(
    `/api/projects/${projectId}/props`
  );
  return {
    props: response.props.map(mapProp),
    total: response.total,
  };
}

// ---------------------------------------------------------------------------
// Get
// ---------------------------------------------------------------------------

export async function getProp(
  projectId: string,
  propId: string
): Promise<PropResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const list = getMockProps(projectId);
    const prop = list.props.find((p) => p.prop_id === propId);
    if (!prop) throw new Error("Prop not found");
    return prop;
  }
  const response = await apiFetch<BackendPropResponse>(
    `/api/projects/${projectId}/props/${propId}`
  );
  return mapProp(response);
}

// ---------------------------------------------------------------------------
// Update
// ---------------------------------------------------------------------------

export async function updateProp(
  projectId: string,
  propId: string,
  data: PropUpdateRequest
): Promise<PropResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const list = getMockProps(projectId);
    const prop = list.props.find((p) => p.prop_id === propId);
    if (!prop) throw new Error("Prop not found");
    return {
      ...prop,
      ...data,
      updated_at: new Date().toISOString(),
    };
  }
  const response = await apiFetch<BackendPropResponse>(
    `/api/projects/${projectId}/props/${propId}`,
    {
      method: "PATCH",
      body: toBackendPropUpdate(data),
    }
  );
  return mapProp(response);
}

// ---------------------------------------------------------------------------
// Regenerate
// ---------------------------------------------------------------------------

export async function regenerateProp(
  projectId: string,
  propId: string
): Promise<PropRegenerateResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return {
      prop_id: propId,
      status: "regenerating",
      message: "Prop regeneration started",
    };
  }
  const response = await apiFetch<Partial<PropRegenerateResponse> & { task_id?: string }>(
    `/api/projects/${projectId}/props/${propId}/regenerate`,
    {
      method: "POST",
    }
  );
  return {
    prop_id: response.prop_id || propId,
    status: response.status || "pending",
    message: response.message || "Prop regeneration started",
  };
}

export function mapProp(raw: BackendPropResponse): PropResponse {
  return {
    id: raw.id,
    project_id: raw.project_id,
    prop_id: raw.prop_id,
    name: raw.name,
    description: raw.visual_features || "",
    function: raw.plot_function || "",
    state_timeline: (raw.state_timeline || []).map((item) => item.state || item.description || ""),
    prop_prompt: raw.prop_prompt || undefined,
    usage_prompt: raw.usage_prompt || undefined,
    thumbnail_url: resolveAssetUrl(latestAssetByStem(raw.reference_assets || [], "product")),
    is_locked: false,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
  };
}

function latestAssetByStem(paths: string[], stem: string): string | undefined {
  return [...paths].reverse().find((path) => new RegExp(`/${stem}\\.(png|jpe?g|webp)$`, "i").test(path));
}

function toBackendPropUpdate(data: PropUpdateRequest): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (data.name !== undefined) body.name = data.name;
  if (data.description !== undefined) body.visual_features = data.description;
  if (data.function !== undefined) body.plot_function = data.function;
  if (data.prop_prompt !== undefined) body.prop_prompt = data.prop_prompt;
  if (data.usage_prompt !== undefined) body.usage_prompt = data.usage_prompt;
  if (data.state_timeline !== undefined) {
    body.state_timeline = data.state_timeline.map((state, index) => ({
      step_index: index + 1,
      state,
      description: state,
    }));
  }
  return body;
}
