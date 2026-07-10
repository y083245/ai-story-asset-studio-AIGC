// =============================================================================
// Story Asset Studio — Projects API
// =============================================================================

import { USE_MOCK, apiFetch } from "@/shared/api/client";
import {
  mockProjects,
  getMockProject,
  getMockWorkflowStatus,
  getMockProjectCopy,
} from "@/shared/api/mock-data";
import type {
  ProjectCreateRequest,
  ProjectUpdateRequest,
  ProjectResponse,
  ProjectListResponse,
  ProjectStatusResponse,
  ProjectCopyResponse,
} from "@/shared/types";

// ---------------------------------------------------------------------------
// Create
// ---------------------------------------------------------------------------

export async function createProject(
  data: ProjectCreateRequest
): Promise<ProjectResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const project: ProjectResponse = {
      project_id: `proj-mock-${Date.now()}`,
      user_id: "mock-user",
      title: data.title,
      status: "draft" as const,
      aspect_ratio: data.aspect_ratio,
      style_mode: data.style_mode,
      manual_style: data.manual_style,
      generation_mode: data.generation_mode,
      progress: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    mockProjects.unshift(project);
    return project;
  }
  return apiFetch<ProjectResponse>("/api/projects", {
    method: "POST",
    body: data,
  });
}

// ---------------------------------------------------------------------------
// List
// ---------------------------------------------------------------------------

export async function listProjects(params?: {
  status?: string;
  include_archived?: boolean;
  only_archived?: boolean;
  limit?: number;
  offset?: number;
}): Promise<ProjectListResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    let items = [...mockProjects];
    if (params?.only_archived) {
      items = items.filter((project) => project.status === "archived");
    } else if (!params?.include_archived) {
      items = items.filter((project) => project.status !== "archived");
    }
    return { items, total: items.length };
  }
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.include_archived) query.set("include_archived", "true");
  if (params?.only_archived) query.set("only_archived", "true");
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiFetch<ProjectListResponse>(`/api/projects${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Get
// ---------------------------------------------------------------------------

export async function getProject(
  projectId: string
): Promise<ProjectResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const project = getMockProject(projectId);
    if (!project) throw new Error("Project not found");
    return project;
  }
  return apiFetch<ProjectResponse>(`/api/projects/${projectId}`);
}

// ---------------------------------------------------------------------------
// Update
// ---------------------------------------------------------------------------

export async function updateProject(
  projectId: string,
  data: ProjectUpdateRequest
): Promise<ProjectResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const project = getMockProject(projectId);
    if (!project) throw new Error("Project not found");
    return {
      ...project,
      ...data,
      updated_at: new Date().toISOString(),
    };
  }
  return apiFetch<ProjectResponse>(`/api/projects/${projectId}`, {
    method: "PATCH",
    body: data,
  });
}

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------

export async function deleteProject(projectId: string): Promise<void> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const project = getMockProject(projectId);
    if (!project) throw new Error("Project not found");
    const deletedAt = new Date();
    const purgeAfter = new Date(deletedAt);
    purgeAfter.setDate(purgeAfter.getDate() + 30);
    project.status = "archived";
    project.deleted_at = deletedAt.toISOString();
    project.purge_after = purgeAfter.toISOString();
    project.updated_at = deletedAt.toISOString();
    return;
  }
  return apiFetch<void>(`/api/projects/${projectId}`, {
    method: "DELETE",
  });
}

// ---------------------------------------------------------------------------
// Restore
// ---------------------------------------------------------------------------

export async function restoreProject(projectId: string): Promise<ProjectResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const project = getMockProject(projectId);
    if (!project) throw new Error("Project not found");
    project.status = "draft";
    project.deleted_at = null;
    project.purge_after = null;
    project.updated_at = new Date().toISOString();
    return project;
  }
  return apiFetch<ProjectResponse>(`/api/projects/${projectId}/restore`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

export async function getProjectStatus(
  projectId: string
): Promise<ProjectStatusResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockWorkflowStatus(projectId);
  }
  return apiFetch<ProjectStatusResponse>(
    `/api/projects/${projectId}/status`
  );
}

// ---------------------------------------------------------------------------
// Copy
// ---------------------------------------------------------------------------

export async function copyProject(
  projectId: string
): Promise<ProjectCopyResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockProjectCopy(projectId);
  }
  return apiFetch<ProjectCopyResponse>(`/api/projects/${projectId}/copy`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Archive
// ---------------------------------------------------------------------------

export async function archiveProject(projectId: string): Promise<void> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const project = getMockProject(projectId);
    if (!project) throw new Error("Project not found");
    return;
  }
  return apiFetch<void>(`/api/projects/${projectId}/archive`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Permanent delete (batch)
// ---------------------------------------------------------------------------

export async function permanentDeleteProjects(projectIds: string[]): Promise<void> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    for (const pid of projectIds) {
      const idx = mockProjects.findIndex((p) => p.project_id === pid);
      if (idx !== -1) mockProjects.splice(idx, 1);
    }
    return;
  }
  // Fire deletes in parallel (no dependency between them)
  await Promise.all(
    projectIds.map((pid) =>
      apiFetch<void>(`/api/projects/${pid}/permanent`, { method: "DELETE" })
    )
  );
}
