// =============================================================================
// Story Engine — Workflow API
// =============================================================================

import { USE_MOCK, apiFetch } from "@/shared/api/client";
import { getMockWorkflowStatus } from "@/shared/api/mock-data";
import type { ProjectStatusResponse, TaskState, TaskStatus } from "@/shared/types";

export interface WorkflowStartedResponse {
  project_id: string;
  workflow_type: string;
  status: string;
  message: string;
}

interface BackendActivityState {
  activity_name: string;
  status: string;
  attempt?: number;
  error?: string | null;
  result_summary?: Record<string, unknown> | null;
}

interface BackendWorkflowStatusResponse {
  project_id: string;
  workflow_type?: string;
  status: string;
  current_stage?: string;
  progress?: number;
  message?: string;
  error?: string | null;
  error_stage?: string | null;
  activities?: BackendActivityState[];
  stage_index?: number;
  total_stages?: number;
  tasks?: TaskStatus[];
  error_message?: string;
}

const TASK_STATE_MAP: Record<string, TaskState> = {
  pending: "pending",
  running: "running",
  success: "success",
  completed: "success",
  failed: "failed",
  retrying: "retrying",
  needs_review: "needs_review",
  skipped: "pending",
  unknown: "pending",
};

function normalizeProgress(progress: number | undefined): number {
  if (typeof progress !== "number" || Number.isNaN(progress)) return 0;
  const normalized = progress > 0 && progress <= 1 ? progress * 100 : progress;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function normalizeWorkflowStatus(data: BackendWorkflowStatusResponse): ProjectStatusResponse {
  const activities = data.activities ?? [];
  const tasks =
    data.tasks ??
    activities.map((activity): TaskStatus => {
      const state = TASK_STATE_MAP[activity.status] ?? "pending";
      return {
        task_id: activity.activity_name,
        name: activity.activity_name.replace(/_/g, " "),
        state,
        progress: state === "success" ? 100 : state === "running" ? 50 : 0,
        retry_count: Math.max((activity.attempt ?? 1) - 1, 0),
        max_retries: 2,
        error_message: activity.error ?? undefined,
        result_summary: activity.result_summary ?? undefined,
      };
    });

  const stageIndex =
    typeof data.stage_index === "number"
      ? data.stage_index
      : Math.max(tasks.findIndex((task) => task.state === "running"), 0);
  const totalStages =
    typeof data.total_stages === "number"
      ? data.total_stages
      : Math.max(tasks.length, data.current_stage ? 1 : 0);

  return {
    project_id: data.project_id,
    status: data.status as ProjectStatusResponse["status"],
    progress: normalizeProgress(data.progress),
    current_stage: data.current_stage,
    message: data.message,
    stage_index: stageIndex,
    total_stages: totalStages,
    tasks,
    error_message: data.error_message ?? data.error ?? (data.status === "failed" ? data.message : undefined),
  };
}

// ---------------------------------------------------------------------------
// Get Workflow Status
// ---------------------------------------------------------------------------

export async function getWorkflowStatus(
  projectId: string
): Promise<ProjectStatusResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockWorkflowStatus(projectId);
  }
  const data = await apiFetch<BackendWorkflowStatusResponse>(
    `/api/projects/${projectId}/workflow-status`
  );
  return normalizeWorkflowStatus(data);
}

// ---------------------------------------------------------------------------
// Start Workflow
// ---------------------------------------------------------------------------

export async function startWorkflow(
  projectId: string
): Promise<{ status: string; message: string }> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return {
      status: "started",
      message: "Workflow started successfully",
    };
  }
  return apiFetch<{ status: string; message: string }>(
    `/api/projects/${projectId}/generate`,
    { method: "POST" }
  );
}

// ---------------------------------------------------------------------------
// Start Analysis
// ---------------------------------------------------------------------------

export async function startAnalysis(
  projectId: string
): Promise<WorkflowStartedResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return {
      project_id: projectId,
      workflow_type: "analyze",
      status: "completed",
      message: "Analysis completed successfully",
    };
  }
  return apiFetch<WorkflowStartedResponse>(
    `/api/projects/${projectId}/analyze`,
    { method: "POST" }
  );
}
