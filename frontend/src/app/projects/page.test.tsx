import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProjectsPage from "@/app/projects/page";
import * as projectsApi from "@/shared/api/projects";
import type { ProjectResponse } from "@/shared/types";

const pushSpy = vi.fn();
const originalListProjects = projectsApi.listProjects;
const listProjectsSpy = vi.spyOn(projectsApi, "listProjects");

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushSpy,
  }),
}));

describe("projects page", () => {
  beforeEach(async () => {
    pushSpy.mockReset();
    listProjectsSpy.mockReset();
    listProjectsSpy.mockImplementation(originalListProjects);
    try {
      await projectsApi.restoreProject("proj-asset-001");
    } catch {
      // The mock project is present for these tests; ignore if its state is already active.
    }
  });

  it("shows the asset library entry in header actions", async () => {
    render(<ProjectsPage />);

    expect(await screen.findByRole("heading", { name: "我的项目" })).toBeInTheDocument();
    const assetLibraryLink = screen.getByRole("link", { name: "资产管理" });

    expect(assetLibraryLink).toHaveAttribute("href", "/asset-library");
    expect(screen.getByRole("link", { name: "创建新项目" })).toHaveAttribute("href", "/projects/new");
    expect(screen.getByRole("button", { name: "回收站" })).toBeInTheDocument();
  });

  it("keeps completed project cards routing to the project asset workbench", async () => {
    const completedProject: ProjectResponse = {
      project_id: "proj-completed-001",
      user_id: "mock-user",
      title: "已完成项目",
      status: "completed",
      aspect_ratio: "9:16",
      style_mode: "auto",
      manual_style: "",
      generation_mode: "fast_preview",
      progress: 100,
      created_at: "2026-07-08T10:00:00+08:00",
      updated_at: "2026-07-08T10:00:00+08:00",
      deleted_at: null,
      purge_after: null,
    };
    listProjectsSpy.mockResolvedValueOnce({
      items: [completedProject],
      total: 1,
    });

    render(<ProjectsPage />);

    await userEvent.click(await screen.findByRole("heading", { name: "已完成项目" }));

    expect(pushSpy).toHaveBeenCalledWith("/projects/proj-completed-001/assets");
  });

  it("keeps recycle bin toggle and restore interactions working", async () => {
    await projectsApi.deleteProject("proj-asset-001");
    render(<ProjectsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "回收站" }));

    expect(await screen.findByRole("heading", { name: "回收站" })).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "恢复项目 旧怀表" }));

    await waitFor(() => {
      expect(screen.queryByText("旧怀表")).not.toBeInTheDocument();
    });
    expect(screen.getAllByRole("button", { name: "返回项目" }).length).toBeGreaterThan(0);
  });
});
