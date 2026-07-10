"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { getWorkflowStatus } from "@/shared/api/workflow";
import type { ProjectStatusResponse, TaskStatus } from "@/shared/types";

const POLL_INTERVAL_MS = 2000;

const TERMINAL_STATUSES = new Set([
  "draft",
  "completed",
  "failed",
  "archived",
]);

export function useWorkflowProgress(projectId: string) {
  const [status, setStatus] = useState<ProjectStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getWorkflowStatus(projectId);
      setStatus(data);
      setError(null);

      // Determine if the workflow is actively running
      const active = !TERMINAL_STATUSES.has(data.status);
      setIsRunning(active);
      return data;
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to fetch workflow status"
      );
      setIsRunning(false);
      return null;
    }
  }, [projectId]);

  // Initial fetch + start/stop polling based on status
  useEffect(() => {
    if (!projectId) return;

    // Fetch immediately on mount or projectId change
    fetchStatus().then((data) => {
      if (data && !TERMINAL_STATUSES.has(data.status)) {
        // Start polling if the workflow is active
        intervalRef.current = setInterval(() => {
          fetchStatus().then((latest) => {
            // If the latest status is terminal, stop polling
            if (latest && TERMINAL_STATUSES.has(latest.status)) {
              if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
              }
              setIsRunning(false);
            }
          });
        }, POLL_INTERVAL_MS);
      }
    });

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [projectId, fetchStatus]);

  // Derived values
  const tasks: TaskStatus[] = status?.tasks ?? [];
  const progress: number = status?.progress ?? 0;
  const stageIndex: number = status?.stage_index ?? 0;
  const totalStages: number = status?.total_stages ?? 0;
  const currentStage: string | undefined = status?.current_stage;

  return {
    status,
    tasks,
    progress,
    stageIndex,
    totalStages,
    currentStage,
    isRunning,
    error,
    refetch: fetchStatus,
  };
}
