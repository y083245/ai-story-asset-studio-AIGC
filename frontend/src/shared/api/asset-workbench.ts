// =============================================================================
// Story Engine — Asset Workbench API
// =============================================================================

import { USE_MOCK, apiFetch } from "@/shared/api/client";
import type { ImageAssetType } from "@/shared/api/image-assets";

export type AssetWorkbenchTarget = "characters" | "scenes" | "props";
export type AssetWorkbenchEntityType = "character" | "scene" | "prop";

export interface AssetPromptOverride {
  entity_type: AssetWorkbenchEntityType;
  entity_id: string;
  prompt: string;
}

export interface GenerateAssetWorkbenchRequest {
  targets: AssetWorkbenchTarget[];
  prompt_overrides?: AssetPromptOverride[];
  only_missing?: boolean;
}

export interface PromptPreviewRequestItem {
  entity_type: AssetWorkbenchEntityType;
  entity_id: string;
  asset_type: ImageAssetType;
  reference_asset_ids?: string[];
  extra_constraints?: string | null;
}

export interface PreviewAssetWorkbenchPromptsRequest {
  items: PromptPreviewRequestItem[];
}

export interface PromptPreviewResult {
  entity_type: AssetWorkbenchEntityType;
  entity_id: string;
  asset_type: ImageAssetType;
  prompt: string;
  negative_prompt: string;
}

export interface PreviewAssetWorkbenchPromptsResponse {
  items: PromptPreviewResult[];
}

export interface GeneratedAssetItem {
  entity_type: AssetWorkbenchEntityType;
  entity_id: string;
  asset_type: string;
  status: "generated" | "skipped" | "failed";
  storage_path?: string;
  error?: string;
}

export interface GenerateAssetWorkbenchResponse {
  project_id: string;
  total: number;
  succeeded: number;
  skipped: number;
  failed: number;
  results: GeneratedAssetItem[];
}

export async function generateAssetWorkbench(
  projectId: string,
  request: GenerateAssetWorkbenchRequest
): Promise<GenerateAssetWorkbenchResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 800));
    return {
      project_id: projectId,
      total: 4,
      succeeded: 4,
      skipped: 0,
      failed: 0,
      results: [],
    };
  }

  return apiFetch<GenerateAssetWorkbenchResponse>(
    `/api/projects/${projectId}/asset-workbench/generate`,
    {
      method: "POST",
      body: {
        targets: request.targets,
        prompt_overrides: request.prompt_overrides || [],
        only_missing: request.only_missing ?? false,
      },
    }
  );
}

export async function previewAssetWorkbenchPrompts(
  projectId: string,
  request: PreviewAssetWorkbenchPromptsRequest
): Promise<PreviewAssetWorkbenchPromptsResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return {
      items: request.items.map((item) => ({
        entity_type: item.entity_type,
        entity_id: item.entity_id,
        asset_type: item.asset_type,
        prompt: `${item.asset_type} 最终生图 Prompt`,
        negative_prompt: "",
      })),
    };
  }

  return apiFetch<PreviewAssetWorkbenchPromptsResponse>(
    `/api/projects/${projectId}/asset-workbench/prompts/preview`,
    {
      method: "POST",
      body: {
        items: request.items.map((item) => ({
          entity_type: item.entity_type,
          entity_id: item.entity_id,
          asset_type: item.asset_type,
          reference_asset_ids: item.reference_asset_ids || [],
          extra_constraints: item.extra_constraints ?? null,
        })),
      },
    }
  );
}
