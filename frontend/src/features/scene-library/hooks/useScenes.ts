"use client";
import { useState, useEffect, useCallback } from "react";
import { listScenes, updateScene } from "@/shared/api/scenes";
import type { SceneResponse, SceneUpdateRequest } from "@/shared/types";

export function useScenes(projectId: string) {
  const [scenes, setScenes] = useState<SceneResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedScene, setSelectedScene] = useState<SceneResponse | null>(null);

  const fetchScenes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listScenes(projectId);
      setScenes(data.scenes);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scenes");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) {
      fetchScenes();
    }
  }, [projectId, fetchScenes]);

  const selectScene = useCallback((scene: SceneResponse | null) => {
    setSelectedScene(scene);
  }, []);

  const handleUpdateScene = useCallback(
    async (sceneId: string, data: SceneUpdateRequest) => {
      setError(null);
      try {
        const updated = await updateScene(projectId, sceneId, data);
        setScenes((prev) =>
          prev.map((s) => (s.scene_id === sceneId ? updated : s))
        );
        setSelectedScene((prev) =>
          prev?.scene_id === sceneId ? updated : prev
        );
        return updated;
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to update scene";
        setError(message);
        throw e;
      }
    },
    [projectId]
  );

  const toggleLock = useCallback(
    async (sceneId: string) => {
      const scene = scenes.find((s) => s.scene_id === sceneId);
      if (!scene) return;
      const newLockState = !scene.is_locked;
      // Optimistic update
      setScenes((prev) =>
        prev.map((s) =>
          s.scene_id === sceneId ? { ...s, is_locked: newLockState } : s
        )
      );
      setSelectedScene((prev) =>
        prev?.scene_id === sceneId
          ? { ...prev, is_locked: newLockState }
          : prev
      );
      try {
        await updateScene(projectId, sceneId, { is_locked: newLockState });
      } catch (e) {
        // Revert on failure
        setScenes((prev) =>
          prev.map((s) =>
            s.scene_id === sceneId ? { ...s, is_locked: !newLockState } : s
          )
        );
        setSelectedScene((prev) =>
          prev?.scene_id === sceneId
            ? { ...prev, is_locked: !newLockState }
            : prev
        );
        const message = e instanceof Error ? e.message : "Failed to toggle lock";
        setError(message);
      }
    },
    [projectId, scenes]
  );

  const handleRegenerateScene = useCallback(
    async (sceneId: string) => {
      setError(null);
      try {
        const { regenerateScene } = await import("@/shared/api/scenes");
        const result = await regenerateScene(projectId, sceneId);
        await fetchScenes();
        return result;
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to regenerate scene";
        setError(message);
        throw e;
      }
    },
    [projectId, fetchScenes]
  );

  return {
    scenes,
    loading,
    error,
    selectedScene,
    selectScene,
    updateScene: handleUpdateScene,
    toggleLock,
    regenerateScene: handleRegenerateScene,
    refetch: fetchScenes,
  };
}
