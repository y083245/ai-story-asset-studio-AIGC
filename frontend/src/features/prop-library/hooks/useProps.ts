"use client";
import { useState, useEffect, useCallback } from "react";
import { listProps, updateProp } from "@/shared/api/props";
import type { PropResponse, PropUpdateRequest } from "@/shared/types";

export function useProps(projectId: string) {
  const [props, setProps] = useState<PropResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProp, setSelectedProp] = useState<PropResponse | null>(null);

  const fetchProps = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProps(projectId);
      setProps(data.props);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load props");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) {
      fetchProps();
    }
  }, [projectId, fetchProps]);

  const selectProp = useCallback((prop: PropResponse | null) => {
    setSelectedProp(prop);
  }, []);

  const handleUpdateProp = useCallback(
    async (propId: string, data: PropUpdateRequest) => {
      setError(null);
      try {
        const updated = await updateProp(projectId, propId, data);
        setProps((prev) =>
          prev.map((p) => (p.prop_id === propId ? updated : p))
        );
        setSelectedProp((prev) =>
          prev?.prop_id === propId ? updated : prev
        );
        return updated;
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to update prop";
        setError(message);
        throw e;
      }
    },
    [projectId]
  );

  const toggleLock = useCallback(
    async (propId: string) => {
      const prop = props.find((p) => p.prop_id === propId);
      if (!prop) return;
      const newLockState = !prop.is_locked;
      // Optimistic update
      setProps((prev) =>
        prev.map((p) =>
          p.prop_id === propId ? { ...p, is_locked: newLockState } : p
        )
      );
      setSelectedProp((prev) =>
        prev?.prop_id === propId
          ? { ...prev, is_locked: newLockState }
          : prev
      );
      try {
        await updateProp(projectId, propId, { is_locked: newLockState });
      } catch (e) {
        // Revert on failure
        setProps((prev) =>
          prev.map((p) =>
            p.prop_id === propId ? { ...p, is_locked: !newLockState } : p
          )
        );
        setSelectedProp((prev) =>
          prev?.prop_id === propId
            ? { ...prev, is_locked: !newLockState }
            : prev
        );
        const message = e instanceof Error ? e.message : "Failed to toggle lock";
        setError(message);
      }
    },
    [projectId, props]
  );

  const handleRegenerateProp = useCallback(
    async (propId: string) => {
      setError(null);
      try {
        const { regenerateProp } = await import("@/shared/api/props");
        const result = await regenerateProp(projectId, propId);
        await fetchProps();
        return result;
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to regenerate prop";
        setError(message);
        throw e;
      }
    },
    [projectId, fetchProps]
  );

  return {
    props,
    loading,
    error,
    selectedProp,
    selectProp,
    updateProp: handleUpdateProp,
    toggleLock,
    regenerateProp: handleRegenerateProp,
    refetch: fetchProps,
  };
}
