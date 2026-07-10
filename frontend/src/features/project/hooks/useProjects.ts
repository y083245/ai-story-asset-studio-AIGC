"use client";
import { useState, useEffect, useCallback } from "react";
import { listProjects, createProject, deleteProject } from "@/shared/api/projects";
import type { ProjectResponse, ProjectCreateRequest } from "@/shared/types";

export function useProjects() {
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProjects();
      setProjects(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const handleCreateProject = async (data: ProjectCreateRequest) => {
    return createProject(data);
  };

  const handleDeleteProject = async (projectId: string) => {
    await deleteProject(projectId);
    await fetchProjects();
  };

  return {
    projects,
    loading,
    error,
    refetch: fetchProjects,
    createProject: handleCreateProject,
    deleteProject: handleDeleteProject,
  };
}
