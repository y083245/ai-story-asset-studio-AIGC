// =============================================================================
// Story Engine — Analysis & Story Bible API
// =============================================================================

import { USE_MOCK, apiFetch } from "@/shared/api/client";
import {
  getMockAnalysis,
  getMockStoryBible,
  getMockStoryBibleVersions,
} from "@/shared/api/mock-data";
import type {
  AnalysisResponse,
  StoryBibleResponse,
  StoryBiblePatchRequest,
  StoryBibleVersionListResponse,
} from "@/shared/types";

// ---------------------------------------------------------------------------
// Get Analysis
// ---------------------------------------------------------------------------

export async function getAnalysis(
  projectId: string
): Promise<AnalysisResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockAnalysis(projectId);
  }
  return apiFetch<AnalysisResponse>(
    `/api/projects/${projectId}/analysis`
  );
}

// ---------------------------------------------------------------------------
// Get Story Bible
// ---------------------------------------------------------------------------

export async function getStoryBible(
  projectId: string,
  version?: number
): Promise<StoryBibleResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockStoryBible(projectId);
  }
  const query = version != null ? `?version=${version}` : "";
  return apiFetch<StoryBibleResponse>(
    `/api/projects/${projectId}/story-bible${query}`
  );
}

// ---------------------------------------------------------------------------
// Patch Story Bible
// ---------------------------------------------------------------------------

export async function patchStoryBible(
  projectId: string,
  data: StoryBiblePatchRequest
): Promise<StoryBibleResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const bible = getMockStoryBible(projectId);
    return {
      ...bible,
      ...data,
      version: bible.version + 1,
      updated_at: new Date().toISOString(),
    };
  }
  return apiFetch<StoryBibleResponse>(
    `/api/projects/${projectId}/story-bible`,
    {
      method: "PATCH",
      body: data,
    }
  );
}

// ---------------------------------------------------------------------------
// List Story Bible Versions
// ---------------------------------------------------------------------------

export async function listStoryBibleVersions(
  projectId: string
): Promise<StoryBibleVersionListResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockStoryBibleVersions(projectId);
  }
  return apiFetch<StoryBibleVersionListResponse>(
    `/api/projects/${projectId}/story-bible/versions`
  );
}

// ---------------------------------------------------------------------------
// Confirm Style
// ---------------------------------------------------------------------------

export async function confirmStyle(
  projectId: string,
  styleName: string
): Promise<AnalysisResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const analysis = getMockAnalysis(projectId);
    return {
      ...analysis,
      visual_style: styleName,
      style_confidence: 0.95,
      style_candidates: undefined,
    };
  }
  const analysis = await getAnalysis(projectId);
  return {
    ...analysis,
    visual_style: styleName,
    style_confidence: Math.max(analysis.style_confidence, 0.75),
    style_candidates: undefined,
  };
}
