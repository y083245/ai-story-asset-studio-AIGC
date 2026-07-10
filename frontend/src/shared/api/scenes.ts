// =============================================================================
// Story Engine — Scenes API
// =============================================================================

import { USE_MOCK, apiFetch } from "@/shared/api/client";
import { resolveAssetUrl } from "@/shared/api/asset-url";
import { getMockScenes } from "@/shared/api/mock-data";
import type {
  SceneResponse,
  SceneListResponse,
  SceneUpdateRequest,
  SceneRegenerateResponse,
} from "@/shared/types";

interface BackendSceneResponse {
  id: string;
  project_id: string;
  scene_id: string;
  scene_name: string;
  scene_type?: string;
  time_of_day?: string;
  mood?: string;
  fixed_anchors?: string[];
  scene_prompt?: string;
  empty_scene_prompt?: string;
  reference_assets?: string[];
  created_at: string;
  updated_at: string;
}

interface BackendSceneListResponse {
  scenes: BackendSceneResponse[];
  total: number;
}

// ---------------------------------------------------------------------------
// List
// ---------------------------------------------------------------------------

export async function listScenes(
  projectId: string
): Promise<SceneListResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockScenes(projectId);
  }
  const response = await apiFetch<BackendSceneListResponse>(
    `/api/projects/${projectId}/scenes`
  );
  return {
    scenes: response.scenes.map(mapScene),
    total: response.total,
  };
}

// ---------------------------------------------------------------------------
// Get
// ---------------------------------------------------------------------------

export async function getScene(
  projectId: string,
  sceneId: string
): Promise<SceneResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const list = getMockScenes(projectId);
    const scene = list.scenes.find((s) => s.scene_id === sceneId);
    if (!scene) throw new Error("Scene not found");
    return scene;
  }
  const response = await apiFetch<BackendSceneResponse>(
    `/api/projects/${projectId}/scenes/${sceneId}`
  );
  return mapScene(response);
}

// ---------------------------------------------------------------------------
// Update
// ---------------------------------------------------------------------------

export async function updateScene(
  projectId: string,
  sceneId: string,
  data: SceneUpdateRequest
): Promise<SceneResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const list = getMockScenes(projectId);
    const scene = list.scenes.find((s) => s.scene_id === sceneId);
    if (!scene) throw new Error("Scene not found");
    return {
      ...scene,
      ...data,
      updated_at: new Date().toISOString(),
    };
  }
  const response = await apiFetch<BackendSceneResponse>(
    `/api/projects/${projectId}/scenes/${sceneId}`,
    {
      method: "PATCH",
      body: toBackendSceneUpdate(data),
    }
  );
  return mapScene(response);
}

// ---------------------------------------------------------------------------
// Regenerate
// ---------------------------------------------------------------------------

export async function regenerateScene(
  projectId: string,
  sceneId: string
): Promise<SceneRegenerateResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return {
      scene_id: sceneId,
      status: "regenerating",
      message: "Scene regeneration started",
    };
  }
  const response = await apiFetch<Partial<SceneRegenerateResponse> & { task_id?: string }>(
    `/api/projects/${projectId}/scenes/${sceneId}/regenerate`,
    {
      method: "POST",
    }
  );
  return {
    scene_id: response.scene_id || sceneId,
    status: response.status || "pending",
    message: response.message || "Scene regeneration started",
  };
}

export function mapScene(raw: BackendSceneResponse): SceneResponse {
  return {
    id: raw.id,
    project_id: raw.project_id,
    scene_id: raw.scene_id,
    name: raw.scene_name,
    description: raw.scene_prompt || raw.empty_scene_prompt || "",
    time_period: raw.time_of_day || undefined,
    mood: raw.mood || undefined,
    location: raw.scene_type || undefined,
    scene_prompt: raw.scene_prompt || undefined,
    empty_scene_prompt: raw.empty_scene_prompt || undefined,
    fixed_anchors: raw.fixed_anchors || [],
    thumbnail_url: resolveAssetUrl(latestAssetByStem(raw.reference_assets || [], "empty")),
    is_locked: false,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
  };
}

function latestAssetByStem(paths: string[], stem: string): string | undefined {
  return [...paths].reverse().find((path) => new RegExp(`/${stem}\\.(png|jpe?g|webp)$`, "i").test(path));
}

function toBackendSceneUpdate(data: SceneUpdateRequest): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (data.name !== undefined) body.scene_name = data.name;
  if (data.description !== undefined) body.scene_prompt = data.description;
  if (data.scene_prompt !== undefined) body.scene_prompt = data.scene_prompt;
  if (data.empty_scene_prompt !== undefined) body.empty_scene_prompt = data.empty_scene_prompt;
  if (data.time_period !== undefined) body.time_of_day = data.time_period;
  if (data.mood !== undefined) body.mood = data.mood;
  if (data.location !== undefined) body.scene_type = data.location;
  return body;
}
