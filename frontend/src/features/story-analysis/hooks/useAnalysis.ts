"use client";
import { useState, useEffect, useCallback, useMemo } from "react";
import { getAnalysis, confirmStyle, patchStoryBible } from "@/shared/api/analysis";
import type {
  AnalysisResponse,
  StyleCandidate,
  StoryBiblePatchRequest,
  StoryBibleResponse,
} from "@/shared/types";

const STYLE_CONFIDENCE_THRESHOLD = 0.75;

export function useAnalysis(projectId: string) {
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [styleCandidates, setStyleCandidates] = useState<StyleCandidate[]>([]);
  const [bible, setBible] = useState<StoryBibleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAnalysis(projectId);
      setAnalysis(data);
      setStyleCandidates(data.style_candidates ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load analysis");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) {
      fetchAnalysis();
    }
  }, [projectId, fetchAnalysis]);

  const showStyleSelector = useMemo(() => {
    if (!analysis) return false;
    return (
      analysis.style_confidence < STYLE_CONFIDENCE_THRESHOLD &&
      styleCandidates.length > 0
    );
  }, [analysis, styleCandidates]);

  const handleConfirmStyle = useCallback(
    async (styleName: string) => {
      setError(null);
      try {
        const updated = await confirmStyle(projectId, styleName);
        setAnalysis(updated);
        setStyleCandidates(updated.style_candidates ?? []);
        return updated;
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to confirm style";
        setError(message);
        throw e;
      }
    },
    [projectId]
  );

  const handlePatchBible = useCallback(
    async (data: StoryBiblePatchRequest) => {
      setError(null);
      try {
        const updated = await patchStoryBible(projectId, data);
        setBible(updated);
        return updated;
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to update story bible";
        setError(message);
        throw e;
      }
    },
    [projectId]
  );

  return {
    analysis,
    styleCandidates,
    bible,
    loading,
    error,
    showStyleSelector,
    confirmStyle: handleConfirmStyle,
    patchBible: handlePatchBible,
    refetch: fetchAnalysis,
  };
}
