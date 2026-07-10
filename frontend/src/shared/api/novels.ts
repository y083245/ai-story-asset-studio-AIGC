// =============================================================================
// Story Engine — Novels API
// =============================================================================

import { USE_MOCK, apiFetch } from "@/shared/api/client";
import {
  getMockNovelData,
  getMockNovelDetail,
} from "@/shared/api/mock-data";
import type {
  NovelIntakeRequest,
  NovelIntakeResponse,
  NovelDetailResponse,
} from "@/shared/types";

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

export async function uploadNovel(
  projectId: string,
  data: NovelIntakeRequest
): Promise<NovelIntakeResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockNovelData(projectId);
  }
  return apiFetch<NovelIntakeResponse>(
    `/api/projects/${projectId}/novel`,
    {
      method: "POST",
      body: {
        project_id: projectId,
        ...data,
      },
    }
  );
}

// ---------------------------------------------------------------------------
// Get
// ---------------------------------------------------------------------------

export async function getNovel(
  projectId: string
): Promise<NovelDetailResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockNovelDetail(projectId);
  }
  return apiFetch<NovelDetailResponse>(
    `/api/projects/${projectId}/novel`
  );
}
