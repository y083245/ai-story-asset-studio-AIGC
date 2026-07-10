"use client";
import { useState, useEffect, useCallback } from "react";
import {
  listCharacters,
  updateCharacter,
} from "@/shared/api/characters";
import type { CharacterResponse, CharacterUpdateRequest } from "@/shared/types";

export function useCharacters(projectId: string) {
  const [characters, setCharacters] = useState<CharacterResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCharacter, setSelectedCharacter] = useState<CharacterResponse | null>(null);

  const fetchCharacters = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCharacters(projectId);
      setCharacters(data.characters);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load characters");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) {
      fetchCharacters();
    }
  }, [projectId, fetchCharacters]);

  const selectCharacter = useCallback((character: CharacterResponse | null) => {
    setSelectedCharacter(character);
  }, []);

  const handleUpdateCharacter = useCallback(
    async (characterId: string, data: CharacterUpdateRequest) => {
      setError(null);
      try {
        const updated = await updateCharacter(projectId, characterId, data);
        setCharacters((prev) =>
          prev.map((c) => (c.character_id === characterId ? updated : c))
        );
        setSelectedCharacter((prev) =>
          prev?.character_id === characterId ? updated : prev
        );
        return updated;
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to update character";
        setError(message);
        throw e;
      }
    },
    [projectId]
  );

  const toggleLock = useCallback(
    async (characterId: string) => {
      const character = characters.find((c) => c.character_id === characterId);
      if (!character) return;
      const newLockState = !character.is_locked;
      // Optimistic update
      setCharacters((prev) =>
        prev.map((c) =>
          c.character_id === characterId ? { ...c, is_locked: newLockState } : c
        )
      );
      setSelectedCharacter((prev) =>
        prev?.character_id === characterId
          ? { ...prev, is_locked: newLockState }
          : prev
      );
      try {
        await updateCharacter(projectId, characterId, { is_locked: newLockState });
      } catch (e) {
        // Revert on failure
        setCharacters((prev) =>
          prev.map((c) =>
            c.character_id === characterId
              ? { ...c, is_locked: !newLockState }
              : c
          )
        );
        setSelectedCharacter((prev) =>
          prev?.character_id === characterId
            ? { ...prev, is_locked: !newLockState }
            : prev
        );
        const message = e instanceof Error ? e.message : "Failed to toggle lock";
        setError(message);
      }
    },
    [projectId, characters]
  );

  const handleRegenerateCharacter = useCallback(
    async (characterId: string) => {
      setError(null);
      try {
        const { regenerateCharacter } = await import("@/shared/api/characters");
        const result = await regenerateCharacter(projectId, characterId);
        // After regeneration, refetch to get updated data
        await fetchCharacters();
        return result;
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to regenerate character";
        setError(message);
        throw e;
      }
    },
    [projectId, fetchCharacters]
  );

  return {
    characters,
    loading,
    error,
    selectedCharacter,
    selectCharacter,
    updateCharacter: handleUpdateCharacter,
    toggleLock,
    regenerateCharacter: handleRegenerateCharacter,
    refetch: fetchCharacters,
  };
}
