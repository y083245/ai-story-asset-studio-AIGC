import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as imageAssetApi from "@/shared/api/image-assets";
import {
  batchDeleteImageAssets,
  batchPermanentDeleteImageAssets,
  batchRestoreImageAssets,
  deleteImageAsset,
  listAssetLibrary,
  listAssetTrash,
  permanentDeleteImageAsset,
  restoreImageAsset,
  __resetMockImageAssetStore,
} from "@/shared/api/image-assets";
import AssetLibraryPage from "@/app/asset-library/page";

const originalListAssetLibrary = imageAssetApi.listAssetLibrary;
const originalListAssetTrash = imageAssetApi.listAssetTrash;
const listAssetLibrarySpy = vi.spyOn(imageAssetApi, "listAssetLibrary");
const listAssetTrashSpy = vi.spyOn(imageAssetApi, "listAssetTrash");

describe("asset library mock api", () => {
  beforeEach(() => {
    __resetMockImageAssetStore();
    listAssetLibrarySpy.mockClear();
    listAssetTrashSpy.mockClear();
    listAssetLibrarySpy.mockImplementation(originalListAssetLibrary);
    listAssetTrashSpy.mockImplementation(originalListAssetTrash);
  });

  it("lists grouped assets and project filters from mock data", async () => {
    const response = await listAssetLibrary({});

    expect(response.available_projects.map((project) => project.project_id)).toEqual(["project-alpha", "project-archived"]);
    expect(response.groups[0]?.date).toBe("2026-07-08");
    expect(response.groups[0]?.projects[0]?.is_project_in_trash).toBe(false);
    expect(response.groups[1]?.projects[0]?.is_project_in_trash).toBe(true);
    expect(response.groups[0]?.projects[0]?.categories.character[0]?.asset_type).toBe("character_bible_sheet");
  });

  it("moves assets through trash lifecycle in mock mode", async () => {
    const libraryBefore = await listAssetLibrary({});
    expect(libraryBefore.total).toBeGreaterThan(0);
    const initialTrash = await listAssetTrash({});
    expect(initialTrash.total).toBeGreaterThan(0);
    expect(initialTrash.items.some((asset) => asset.asset_id === "asset-trash-restore-fail")).toBe(true);

    await deleteImageAsset("asset-character-sheet");
    let trash = await listAssetTrash({});
    expect(trash.items.some((asset) => asset.asset_id === "asset-character-sheet")).toBe(true);

    await restoreImageAsset("asset-character-sheet");
    trash = await listAssetTrash({});
    expect(trash.items.some((asset) => asset.asset_id === "asset-character-sheet")).toBe(false);

    await deleteImageAsset("asset-character-sheet");
    await permanentDeleteImageAsset("asset-character-sheet");
    const libraryAfter = await listAssetLibrary({});
    expect(libraryAfter.groups.flatMap((group) => group.projects.flatMap((project) => project.categories.character)).some((asset) => asset.asset_id === "asset-character-sheet")).toBe(false);
  });

  it("reports partial batch failures with the first failure reason", async () => {
    const deleteResult = await batchDeleteImageAssets(["asset-character-front", "asset-batch-delete-fail"]);
    expect(deleteResult.success_count).toBe(1);
    expect(deleteResult.failure_count).toBe(1);
    expect(deleteResult.first_error?.message).toContain("asset-batch-delete-fail");

    await deleteImageAsset("asset-trash-restore-fail");
    const restoreResult = await batchRestoreImageAssets(["asset-character-front", "asset-trash-restore-fail"]);
    expect(restoreResult.success_count).toBe(1);
    expect(restoreResult.failure_count).toBe(1);

    await deleteImageAsset("asset-trash-permanent-fail");
    const purgeResult = await batchPermanentDeleteImageAssets(["asset-character-front", "asset-trash-permanent-fail"]);
    expect(purgeResult.success_count).toBe(1);
    expect(purgeResult.failure_count).toBe(1);
  });
});

describe("asset library page", () => {
  beforeEach(() => {
    __resetMockImageAssetStore();
    listAssetLibrarySpy.mockClear();
    listAssetTrashSpy.mockClear();
    listAssetLibrarySpy.mockImplementation(originalListAssetLibrary);
    listAssetTrashSpy.mockImplementation(originalListAssetTrash);
  });

  async function renderPage() {
    render(<AssetLibraryPage />);
  }

  it("renders date, project, category order and trash badge", async () => {
    await renderPage();

    expect(await screen.findByRole("heading", { name: "资产管理" })).toBeInTheDocument();
    expect(screen.getByText("2026-07-08")).toBeInTheDocument();
    expect(screen.getAllByText("星港样片计划").length).toBeGreaterThan(0);
    expect(screen.getAllByText("旧城补完计划").length).toBeGreaterThan(0);
    expect(screen.getByText("项目已在回收站")).toBeInTheDocument();

    const headings = screen.getAllByRole("heading", { level: 3 }).map((node) => node.textContent);
    expect(headings).toEqual(expect.arrayContaining(["角色", "道具", "场景"]));
    expect(headings.indexOf("角色")).toBeLessThan(headings.indexOf("道具"));
    expect(headings.indexOf("道具")).toBeLessThan(headings.indexOf("场景"));
    expect(screen.getAllByText(/^最近生成：/).length).toBeGreaterThan(0);
  });

  it("shows prompt collapsed by default and expands on demand", async () => {
    await renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "查看大图 角色设定板" }));

    expect(screen.getByText("Prompt 摘要")).toBeInTheDocument();
    expect(screen.queryByText(/FULL PROMPT:/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "展开全文" }));
    expect(screen.getByText(/FULL PROMPT:/i)).toBeInTheDocument();
  });

  it("shows fallback when a thumbnail fails to load", async () => {
    await renderPage();

    const image = await screen.findByAltText("角色设定板");
    fireEvent.error(image);

    expect(await screen.findByText("图片加载失败")).toBeInTheDocument();
  });

  it("confirms single delete and refreshes current tab", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    await renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "删除角色设定板" }));

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "删除角色设定板" })).not.toBeInTheDocument();
    });
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("确认删除这张图片"));
  });

  it("restores and permanently deletes from trash with confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await deleteImageAsset("asset-character-front");
    await renderPage();

    await userEvent.click(screen.getByRole("tab", { name: "回收站" }));
    await userEvent.click(await screen.findByRole("button", { name: "恢复林小雨正面图" }));
    await waitFor(() => {
      expect(screen.queryByText("林小雨正面图")).not.toBeInTheDocument();
    });

    await deleteImageAsset("asset-scene-expiring");
    await userEvent.click(screen.getByRole("button", { name: "刷新回收站" }));
    await waitFor(() => {
      expect(screen.getByText("雨夜巷道氛围图")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "永久删除雨夜巷道氛围图" }));
    await waitFor(() => {
      expect(screen.queryByText("雨夜巷道氛围图")).not.toBeInTheDocument();
    });
  });

  it("shows batch partial failure message in trash tab", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await deleteImageAsset("asset-character-front");
    await deleteImageAsset("asset-trash-permanent-fail");
    await renderPage();

    await userEvent.click(screen.getByRole("tab", { name: "回收站" }));

    const frontCard = await screen.findByLabelText("选择 林小雨正面图");
    const failCard = screen.getByLabelText("选择 无法永久删除示例");
    await userEvent.click(frontCard);
    await userEvent.click(failCard);
    await userEvent.click(screen.getByRole("button", { name: /永久删除 2 张/i }));

    expect(await screen.findByText(/失败 1 张/)).toBeInTheDocument();
    expect(screen.getByText(/asset-trash-permanent-fail/)).toBeInTheDocument();
  });

  it("uses only available_projects for project filter options", async () => {
    await renderPage();

    const projectFilter = await screen.findByLabelText("项目筛选");
    await waitFor(() => {
      expect(listAssetLibrarySpy).toHaveBeenCalled();
    });
    const latestResponse = await listAssetLibrary({});
    const availableLabels = latestResponse.available_projects.map((project) => project.project_title);
    const optionLabels = Array.from(projectFilter.querySelectorAll("option")).map((option) => option.textContent);

    expect(optionLabels).toEqual(["全部项目", ...availableLabels]);
  });

  it("filters trash items by deleted date range in mock mode", async () => {
    const response = await listAssetTrash({
      date_from: "2026-07-08",
      date_to: "2026-07-08",
    });

    expect(response.total).toBeGreaterThan(0);
    expect(response.items.map((item) => item.asset_id)).toContain("asset-trash-restore-fail");
  });

  it("wires toolbar filters into library api query and rendered results", async () => {
    await renderPage();
    await screen.findByText("角色设定板");

    const keywordInput = screen.getByLabelText("关键词搜索");
    await userEvent.type(keywordInput, "旧城");

    await waitFor(() => {
      expect(listAssetLibrarySpy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          keyword: "旧城",
          page: 1,
          page_size: 50,
        })
      );
    });
    expect(screen.queryByRole("button", { name: "查看大图 角色设定板" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看大图 旧城街角纯场景" })).toBeInTheDocument();

    const projectFilter = screen.getByLabelText("项目筛选");
    await userEvent.clear(keywordInput);
    await waitFor(() => {
      expect(listAssetLibrarySpy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          keyword: undefined,
          project_id: undefined,
        })
      );
    });
    await userEvent.selectOptions(projectFilter, "project-alpha");

    await waitFor(() => {
      expect(listAssetLibrarySpy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          keyword: undefined,
          project_id: "project-alpha",
        })
      );
    });
    expect(screen.getByRole("button", { name: "查看大图 角色设定板" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "查看大图 旧城街角纯场景" })).not.toBeInTheDocument();
  });

  it("groups trash items by date then project instead of one card per synthetic group", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await deleteImageAsset("asset-character-front");
    await deleteImageAsset("asset-prop-usage");
    await renderPage();

    await userEvent.click(screen.getByRole("tab", { name: "回收站" }));

    expect(await screen.findByText("2026-07-08")).toBeInTheDocument();
    expect(screen.getByText("3 张图片 · 1 个项目")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "星港样片计划" })).toHaveLength(1);
    expect(screen.getByText("林小雨正面图")).toBeInTheDocument();
    expect(screen.getByText("神经终端使用图")).toBeInTheDocument();
  });

  it("formats trash group dates in Asia/Shanghai for UTC timestamps", async () => {
    await renderPage();

    await userEvent.click(screen.getByRole("tab", { name: "回收站" }));

    expect(await screen.findByText("2026-07-08")).toBeInTheDocument();
    expect(screen.getByText("恢复失败示例")).toBeInTheDocument();
    expect(screen.queryByText("2026-07-07")).not.toBeInTheDocument();
  });

  it("requests and renders the next library page", async () => {
    listAssetLibrarySpy.mockImplementation(async (query) => {
      const page = query.page ?? 1;
      if (page === 2) {
        return {
          groups: [
            {
              date: "2026-07-07",
              total: 1,
              project_count: 1,
              projects: [
                {
                  project_id: "project-page-2",
                  project_title: "第二页项目",
                  project_status: "completed",
                  project_deleted_at: null,
                  is_project_in_trash: false,
                  total: 1,
                  latest_created_at: "2026-07-07T10:00:00+08:00",
                  categories: {
                    character: [
                      {
                        asset_id: "asset-page-2",
                        display_name: "第二页角色图",
                        project_id: "project-page-2",
                        project_title: "第二页项目",
                        project_status: "completed",
                        project_deleted_at: null,
                        category: "character",
                        asset_type: "character_front",
                        asset_type_label: "正面图",
                        related_id: "CH_PAGE_2",
                        related_name: "第二页角色",
                        asset_url: "https://example.com/page-2.png",
                        thumbnail_url: "https://example.com/page-2-thumb.png",
                        storage_path: "projects/project-page-2/page-2.png",
                        prompt_summary: "page 2 summary",
                        prompt: "page 2 prompt",
                        model_name: "seedream-3.0",
                        status: "completed",
                        quality_status: "passed",
                        width: 1024,
                        height: 1024,
                        created_at: "2026-07-07T10:00:00+08:00",
                        expires_at: "2027-01-07T10:00:00+08:00",
                        remaining_retention_days: 180,
                        is_expiring_soon: false,
                      },
                    ],
                    prop: [],
                    scene: [],
                  },
                },
              ],
            },
          ],
          available_projects: [
            {
              project_id: "project-page-2",
              project_title: "第二页项目",
              project_status: "completed",
              project_deleted_at: null,
              is_project_in_trash: false,
              total: 1,
            },
          ],
          page: 2,
          page_size: 50,
          total: 51,
        };
      }

      return {
        groups: [
          {
            date: "2026-07-08",
            total: 1,
            project_count: 1,
            projects: [
              {
                project_id: "project-page-1",
                project_title: "第一页项目",
                project_status: "completed",
                project_deleted_at: null,
                is_project_in_trash: false,
                total: 1,
                latest_created_at: "2026-07-08T10:00:00+08:00",
                categories: {
                  character: [
                    {
                      asset_id: "asset-page-1",
                      display_name: "第一页角色图",
                      project_id: "project-page-1",
                      project_title: "第一页项目",
                      project_status: "completed",
                      project_deleted_at: null,
                      category: "character",
                      asset_type: "character_front",
                      asset_type_label: "正面图",
                      related_id: "CH_PAGE_1",
                      related_name: "第一页角色",
                      asset_url: "https://example.com/page-1.png",
                      thumbnail_url: "https://example.com/page-1-thumb.png",
                      storage_path: "projects/project-page-1/page-1.png",
                      prompt_summary: "page 1 summary",
                      prompt: "page 1 prompt",
                      model_name: "seedream-3.0",
                      status: "completed",
                      quality_status: "passed",
                      width: 1024,
                      height: 1024,
                      created_at: "2026-07-08T10:00:00+08:00",
                      expires_at: "2027-01-08T10:00:00+08:00",
                      remaining_retention_days: 180,
                      is_expiring_soon: false,
                    },
                  ],
                  prop: [],
                  scene: [],
                },
              },
            ],
          },
        ],
        available_projects: [
          {
            project_id: "project-page-1",
            project_title: "第一页项目",
            project_status: "completed",
            project_deleted_at: null,
            is_project_in_trash: false,
            total: 1,
          },
        ],
        page: 1,
        page_size: 50,
        total: 51,
      };
    });

    await renderPage();

    expect(await screen.findByText("第一页角色图")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "全部图片下一页" }));

    await waitFor(() => {
      expect(listAssetLibrarySpy).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, page_size: 50 }));
    });
    expect(await screen.findByText("第二页角色图")).toBeInTheDocument();
    expect(screen.queryByText("第一页角色图")).not.toBeInTheDocument();
  });

  it("requires confirmation before restore actions", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    const restoreSpy = vi.spyOn(imageAssetApi, "restoreImageAsset");
    const batchRestoreSpy = vi.spyOn(imageAssetApi, "batchRestoreImageAssets");

    await renderPage();
    await userEvent.click(screen.getByRole("tab", { name: "回收站" }));

    confirmSpy.mockReturnValueOnce(false);
    await userEvent.click(await screen.findByRole("button", { name: "恢复恢复失败示例" }));
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("确认恢复这张图片"));
    expect(restoreSpy).not.toHaveBeenCalled();

    confirmSpy.mockReturnValueOnce(false);
    await userEvent.click(screen.getByLabelText("选择 恢复失败示例"));
    await userEvent.click(screen.getByRole("button", { name: /恢复 1 张/i }));
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("确认恢复选中的图片"));
    expect(batchRestoreSpy).not.toHaveBeenCalled();

    confirmSpy.mockReturnValueOnce(true);
    await userEvent.click(screen.getByRole("button", { name: "恢复恢复失败示例" }));
    await waitFor(() => {
      expect(restoreSpy).toHaveBeenCalledWith("asset-trash-restore-fail");
    });
  });

  it("limits asset type options by category and resets invalid selection", async () => {
    await renderPage();
    await screen.findByText("角色设定板");

    const categoryFilter = screen.getByLabelText("分类筛选");
    const assetTypeFilter = screen.getByLabelText("资产类型筛选") as HTMLSelectElement;

    await userEvent.selectOptions(categoryFilter, "character");
    await waitFor(() => {
      const optionValues = Array.from(assetTypeFilter.options).map((option) => option.value);
      expect(optionValues).toEqual([
        "all",
        "character_bible_sheet",
        "character_front",
        "character_turnaround",
        "character_expression",
      ]);
    });

    await userEvent.selectOptions(assetTypeFilter, "character_front");
    await waitFor(() => {
      expect(listAssetLibrarySpy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          category: "character",
          asset_type: "character_front",
        })
      );
    });

    await userEvent.selectOptions(categoryFilter, "prop");
    await waitFor(() => {
      const optionValues = Array.from(assetTypeFilter.options).map((option) => option.value);
      expect(optionValues).toEqual(["all", "prop_product", "prop_usage"]);
      expect(assetTypeFilter.value).toBe("all");
      expect(listAssetLibrarySpy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          category: "prop",
          asset_type: undefined,
        })
      );
    });
  });
});
