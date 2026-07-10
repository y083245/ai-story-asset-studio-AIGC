import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AssetWorkbenchPage from "@/app/projects/[id]/assets/page";
import * as assetWorkbenchApi from "@/shared/api/asset-workbench";
import * as charactersApi from "@/shared/api/characters";
import * as imageAssetsApi from "@/shared/api/image-assets";
import * as propsApi from "@/shared/api/props";
import * as scenesApi from "@/shared/api/scenes";
import type {
  CharacterListResponse,
  PropListResponse,
  SceneListResponse,
} from "@/shared/types";

vi.mock("next/navigation", () => ({
  useParams: () => ({
    id: "proj-asset-001",
  }),
}));

const characterList: CharacterListResponse = {
  characters: [
    {
      id: "db-char-1",
      project_id: "proj-asset-001",
      character_id: "char-1",
      name: "林小雨",
      description: "女主角",
      role: "protagonist",
      outfit: "黑色风衣",
      front_image_prompt: "角色正面站姿",
      turnaround_prompt: "角色三视图",
      reference_image_plan: [],
      reference_asset_ids: [],
      reference_image_urls: [],
      is_locked: false,
      created_at: "2026-07-09T10:00:00+08:00",
      updated_at: "2026-07-09T10:00:00+08:00",
    },
  ],
  total: 1,
};

const sceneList: SceneListResponse = {
  scenes: [
    {
      id: "db-scene-1",
      project_id: "proj-asset-001",
      scene_id: "scene-1",
      name: "夜雨小巷",
      description: "霓虹反光",
      empty_scene_prompt: "夜雨空巷",
      fixed_anchors: [],
      is_locked: false,
      created_at: "2026-07-09T10:00:00+08:00",
      updated_at: "2026-07-09T10:00:00+08:00",
    },
  ],
  total: 1,
};

const propList: PropListResponse = {
  props: [
    {
      id: "db-prop-1",
      project_id: "proj-asset-001",
      prop_id: "prop-1",
      name: "旧怀表",
      description: "银色金属怀表",
      function: "关键线索",
      prop_prompt: "怀表产品图",
      state_timeline: [],
      is_locked: false,
      created_at: "2026-07-09T10:00:00+08:00",
      updated_at: "2026-07-09T10:00:00+08:00",
    },
  ],
  total: 1,
};

const listCharactersSpy = vi.spyOn(charactersApi, "listCharacters");
const listScenesSpy = vi.spyOn(scenesApi, "listScenes");
const listPropsSpy = vi.spyOn(propsApi, "listProps");
const updateCharacterSpy = vi.spyOn(charactersApi, "updateCharacter");
const updateSceneSpy = vi.spyOn(scenesApi, "updateScene");
const updatePropSpy = vi.spyOn(propsApi, "updateProp");
const generateAssetWorkbenchSpy = vi.spyOn(assetWorkbenchApi, "generateAssetWorkbench");
const previewAssetWorkbenchPromptsSpy = vi.spyOn(assetWorkbenchApi, "previewAssetWorkbenchPrompts");
const generateImageAssetJobSpy = vi.spyOn(imageAssetsApi, "generateImageAssetJob");
const pollTaskUntilDoneSpy = vi.spyOn(imageAssetsApi, "pollTaskUntilDone");

function withCharacterFrontImage(): CharacterListResponse {
  return {
    characters: [
      {
        ...characterList.characters[0],
        reference_image_urls: ["/local-storage/projects/proj-asset-001/characters/char-1/front.png"],
        reference_asset_ids: ["projects/proj-asset-001/characters/char-1/front.png"],
      },
    ],
    total: 1,
  };
}

function mockReadonlyProperty<TObject extends object, TValue>(
  target: TObject,
  property: keyof TObject,
  value: TValue
): () => void {
  const original = Object.getOwnPropertyDescriptor(target, property);
  Object.defineProperty(target, property, {
    configurable: true,
    value,
  });
  return () => {
    if (original) {
      Object.defineProperty(target, property, original);
    } else {
      delete target[property];
    }
  };
}

describe("project assets page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listCharactersSpy.mockResolvedValue(characterList);
    listScenesSpy.mockResolvedValue(sceneList);
    listPropsSpy.mockResolvedValue(propList);
    updateCharacterSpy.mockResolvedValue(characterList.characters[0]);
    updateSceneSpy.mockResolvedValue(sceneList.scenes[0]);
    updatePropSpy.mockResolvedValue(propList.props[0]);
    previewAssetWorkbenchPromptsSpy.mockResolvedValue({
      items: [
        {
          entity_type: "character",
          entity_id: "char-1",
          asset_type: "character_front",
          prompt: "最终正面完整 prompt",
          negative_prompt: "正面负面 prompt",
        },
        {
          entity_type: "character",
          entity_id: "char-1",
          asset_type: "character_turnaround",
          prompt: "最终三视图完整 prompt",
          negative_prompt: "三视图负面 prompt",
        },
        {
          entity_type: "scene",
          entity_id: "scene-1",
          asset_type: "scene_empty",
          prompt: "最终场景完整 prompt",
          negative_prompt: "场景负面 prompt",
        },
        {
          entity_type: "prop",
          entity_id: "prop-1",
          asset_type: "prop_product",
          prompt: "最终道具完整 prompt",
          negative_prompt: "道具负面 prompt",
        },
      ],
    });
    generateAssetWorkbenchSpy.mockResolvedValue({
      project_id: "proj-asset-001",
      total: 4,
      succeeded: 4,
      skipped: 0,
      failed: 0,
      results: [],
    });
    generateImageAssetJobSpy.mockResolvedValue({
      task_id: "task-mock-1",
      project_id: "proj-asset-001",
      status: "pending",
      polling_url: "/api/image-asset/tasks/task-mock-1",
    });
    pollTaskUntilDoneSpy.mockResolvedValue({
      task_id: "task-mock-1",
      project_id: "proj-asset-001",
      asset_type: "scene_empty",
      related_id: "scene-1",
      provider: "seedream",
      model_name: "seedream-3.0",
      status: "success",
      retry_count: 0,
      max_retries: 3,
      error_message: null,
      quality_status: null,
      quality_report_id: null,
      asset_id: "asset-scene-1",
      storage_path: "projects/proj-asset-001/generated/default.png",
      created_at: "2026-07-09T10:00:00+08:00",
      updated_at: "2026-07-09T10:00:00+08:00",
    });
  });

  it("renders the workbench and starts bulk generation from the project assets page", async () => {
    render(<AssetWorkbenchPage />);

    expect(await screen.findByRole("heading", { name: "素材工作台" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "一键生成素材" }));

    await waitFor(() => {
      expect(generateImageAssetJobSpy).toHaveBeenCalled();
    });
  });

  it("feeds a newly generated front storage path into bulk turnaround generation", async () => {
    pollTaskUntilDoneSpy.mockResolvedValue({
      task_id: "task-mock-1",
      project_id: "proj-asset-001",
      asset_type: "character_front",
      related_id: "char-1",
      provider: "seedream",
      model_name: "seedream-3.0",
      status: "success",
      retry_count: 0,
      max_retries: 3,
      error_message: null,
      quality_status: null,
      quality_report_id: null,
      asset_id: "asset-char-front-1",
      storage_path: "projects/proj-asset-001/characters/char-1/front.png",
      created_at: "2026-07-09T10:00:00+08:00",
      updated_at: "2026-07-09T10:00:00+08:00",
    });

    render(<AssetWorkbenchPage />);

    expect(await screen.findByRole("heading", { name: "素材工作台" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "一键生成素材" }));

    await waitFor(() => {
      expect(generateImageAssetJobSpy).toHaveBeenCalledWith({
        project_id: "proj-asset-001",
        asset_type: "character_turnaround",
        related_id: "char-1",
        reference_asset_ids: ["projects/proj-asset-001/characters/char-1/front.png"],
        extra_constraints: null,
      });
    });
  });

  it("loads final prompt previews into the workbench prompt editors", async () => {
    render(<AssetWorkbenchPage />);

    expect(await screen.findByDisplayValue("最终正面完整 prompt")).toBeInTheDocument();
    expect(screen.getByDisplayValue("最终三视图完整 prompt")).toBeInTheDocument();
    expect(screen.getByText("角色三视图 Prompt")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "场景" }));
    expect(await screen.findByDisplayValue("最终场景完整 prompt")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "道具" }));
    expect(await screen.findByDisplayValue("最终道具完整 prompt")).toBeInTheDocument();
  });

  it("falls back to short prompts when final prompt preview fails", async () => {
    previewAssetWorkbenchPromptsSpy.mockRejectedValue(new Error("preview unavailable"));

    render(<AssetWorkbenchPage />);

    expect(await screen.findByText("最终提示词预览失败，已显示可编辑的基础提示词")).toBeInTheDocument();
    expect(screen.getByDisplayValue("角色正面站姿")).toBeInTheDocument();
    expect(screen.getByDisplayValue("角色三视图")).toBeInTheDocument();
  });

  it("can trigger single asset generation inside the project assets page", async () => {
    render(<AssetWorkbenchPage />);

    await screen.findByRole("heading", { name: "素材工作台" });
    await userEvent.click(screen.getByRole("tab", { name: "场景" }));

    const sceneTitle = await screen.findByRole("heading", { name: "夜雨小巷" });
    const sceneCard = sceneTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;

    expect(sceneCard).not.toBeNull();

    await userEvent.click(within(sceneCard as HTMLElement).getByRole("button", { name: "生成" }));

    await waitFor(() => {
      expect(generateImageAssetJobSpy).toHaveBeenCalledWith({
        project_id: "proj-asset-001",
        asset_type: "scene_empty",
        related_id: "scene-1",
        reference_asset_ids: [],
        extra_constraints: null,
      });
    });
  });

  it("cache-busts a regenerated front thumbnail when the storage path stays the same", async () => {
    listCharactersSpy.mockResolvedValue(withCharacterFrontImage());
    pollTaskUntilDoneSpy.mockResolvedValue({
      task_id: "task-mock-1",
      project_id: "proj-asset-001",
      asset_type: "character_front",
      related_id: "char-1",
      provider: "seedream",
      model_name: "seedream-3.0",
      status: "success",
      retry_count: 0,
      max_retries: 3,
      error_message: null,
      quality_status: null,
      quality_report_id: null,
      asset_id: "asset-char-front-1",
      storage_path: "projects/proj-asset-001/characters/char-1/front.png",
      created_at: "2026-07-09T10:00:00+08:00",
      updated_at: "2026-07-09T10:00:00+08:00",
    });

    render(<AssetWorkbenchPage />);

    const characterTitle = await screen.findByRole("heading", { name: "林小雨" });
    const characterCard = characterTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;
    expect(characterCard).not.toBeNull();

    const frontImageBefore = within(characterCard as HTMLElement).getByAltText("正面图") as HTMLImageElement;
    expect(frontImageBefore.getAttribute("src")).toBe("/local-storage/projects/proj-asset-001/characters/char-1/front.png");

    await userEvent.click(within(characterCard as HTMLElement).getAllByRole("button", { name: "重新生成" })[0]);

    await waitFor(() => {
      const frontImageAfter = within(characterCard as HTMLElement).getByAltText("正面图") as HTMLImageElement;
      expect(frontImageAfter.getAttribute("src")).toMatch(
        /^\/local-storage\/projects\/proj-asset-001\/characters\/char-1\/front\.png\?v=\d+$/
      );
    });
  });

  it("shows generated thumbnails without cropping and opens a page fullscreen preview", async () => {
    listCharactersSpy.mockResolvedValue(withCharacterFrontImage());

    render(<AssetWorkbenchPage />);

    const characterTitle = await screen.findByRole("heading", { name: "林小雨" });
    const characterCard = characterTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;
    expect(characterCard).not.toBeNull();

    const frontImage = within(characterCard as HTMLElement).getByAltText("正面图") as HTMLImageElement;
    expect(frontImage).toHaveClass("object-contain");

    await userEvent.click(within(characterCard as HTMLElement).getByRole("button", { name: /正面图/ }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveClass("h-[100dvh]", "w-[100vw]", "max-w-none", "rounded-none");
    expect(within(dialog).getByRole("img", { name: "林小雨 · 正面图" })).toHaveClass("object-contain");
  });

  it("resizes a generated thumbnail to the loaded image aspect ratio", async () => {
    listCharactersSpy.mockResolvedValue(withCharacterFrontImage());

    render(<AssetWorkbenchPage />);

    const characterTitle = await screen.findByRole("heading", { name: "林小雨" });
    const characterCard = characterTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;
    expect(characterCard).not.toBeNull();

    const frontImage = within(characterCard as HTMLElement).getByAltText("正面图") as HTMLImageElement;
    const restoreWidth = mockReadonlyProperty(frontImage, "naturalWidth", 900);
    const restoreHeight = mockReadonlyProperty(frontImage, "naturalHeight", 1200);

    fireEvent.load(frontImage);

    await waitFor(() => {
      expect(frontImage.closest("button")).toHaveStyle({ aspectRatio: "0.75" });
    });

    restoreWidth();
    restoreHeight();
  });

  it("calls the browser fullscreen API from the fullscreen preview", async () => {
    listCharactersSpy.mockResolvedValue(withCharacterFrontImage());
    const requestFullscreen = vi.fn().mockResolvedValue(undefined);
    const restoreRequestFullscreen = mockReadonlyProperty(
      HTMLElement.prototype,
      "requestFullscreen",
      requestFullscreen
    );

    render(<AssetWorkbenchPage />);

    const characterTitle = await screen.findByRole("heading", { name: "林小雨" });
    const characterCard = characterTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;
    expect(characterCard).not.toBeNull();

    await userEvent.click(within(characterCard as HTMLElement).getByRole("button", { name: /正面图/ }));
    await userEvent.click(await screen.findByRole("button", { name: "进入浏览器全屏" }));

    expect(requestFullscreen).toHaveBeenCalledTimes(1);
    restoreRequestFullscreen();
  });

  it("zooms the fullscreen preview with the mouse wheel", async () => {
    listCharactersSpy.mockResolvedValue(withCharacterFrontImage());

    render(<AssetWorkbenchPage />);

    const characterTitle = await screen.findByRole("heading", { name: "林小雨" });
    const characterCard = characterTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;
    expect(characterCard).not.toBeNull();

    await userEvent.click(within(characterCard as HTMLElement).getByRole("button", { name: /正面图/ }));

    expect(await screen.findByText("100%")).toBeInTheDocument();
    fireEvent.wheel(screen.getByTestId("zoom-preview-canvas"), {
      clientX: 120,
      clientY: 120,
      deltaY: -600,
    });

    await waitFor(() => {
      expect(screen.queryByText("100%")).not.toBeInTheDocument();
    });
  });

  it("exits browser fullscreen when the preview closes", async () => {
    listCharactersSpy.mockResolvedValue(withCharacterFrontImage());
    let fullscreenElement: Element | null = document.body;
    const exitFullscreen = vi.fn().mockImplementation(() => {
      fullscreenElement = null;
      return Promise.resolve();
    });
    const restoreFullscreenElement = Object.getOwnPropertyDescriptor(document, "fullscreenElement");
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => fullscreenElement,
    });
    const restoreExitFullscreen = mockReadonlyProperty(document, "exitFullscreen", exitFullscreen);

    render(<AssetWorkbenchPage />);

    const characterTitle = await screen.findByRole("heading", { name: "林小雨" });
    const characterCard = characterTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;
    expect(characterCard).not.toBeNull();

    await userEvent.click(within(characterCard as HTMLElement).getByRole("button", { name: /正面图/ }));
    await userEvent.click(await screen.findByRole("button", { name: "关闭预览" }));

    await waitFor(() => {
      expect(exitFullscreen).toHaveBeenCalledTimes(1);
    });

    if (restoreFullscreenElement) {
      Object.defineProperty(document, "fullscreenElement", restoreFullscreenElement);
    } else {
      delete document.fullscreenElement;
    }
    restoreExitFullscreen();
  });

  it("uses character reference storage paths when generating a turnaround asset", async () => {
    listCharactersSpy.mockResolvedValue({
      characters: [
        {
          ...characterList.characters[0],
          reference_image_urls: ["/local-storage/projects/proj-asset-001/characters/char-1/front.png"],
          reference_asset_ids: ["projects/proj-asset-001/characters/char-1/front.png"],
        },
      ],
      total: 1,
    });

    render(<AssetWorkbenchPage />);

    await screen.findByRole("heading", { name: "素材工作台" });

    const characterTitle = await screen.findByRole("heading", { name: "林小雨" });
    const characterCard = characterTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;
    expect(characterCard).not.toBeNull();

    await userEvent.click(within(characterCard as HTMLElement).getByRole("button", { name: "生成" }));

    await waitFor(() => {
      expect(generateImageAssetJobSpy).toHaveBeenCalledWith({
        project_id: "proj-asset-001",
        asset_type: "character_turnaround",
        related_id: "char-1",
        reference_asset_ids: ["projects/proj-asset-001/characters/char-1/front.png"],
        extra_constraints: null,
      });
    });
  });

  it("saves edited turnaround prompt before generating a turnaround asset", async () => {
    listCharactersSpy.mockResolvedValue({
      characters: [
        {
          ...characterList.characters[0],
          reference_image_urls: ["/local-storage/projects/proj-asset-001/characters/char-1/front.png"],
          reference_asset_ids: ["projects/proj-asset-001/characters/char-1/front.png"],
        },
      ],
      total: 1,
    });
    const user = userEvent.setup();

    render(<AssetWorkbenchPage />);

    const turnaroundPrompt = await screen.findByDisplayValue("最终三视图完整 prompt");
    await user.clear(turnaroundPrompt);
    await user.type(turnaroundPrompt, "编辑后的三视图 prompt");

    const characterTitle = await screen.findByRole("heading", { name: "林小雨" });
    const characterCard = characterTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;
    expect(characterCard).not.toBeNull();

    await user.click(within(characterCard as HTMLElement).getByRole("button", { name: "生成" }));

    await waitFor(() => {
      expect(updateCharacterSpy).toHaveBeenCalledWith("proj-asset-001", "char-1", {
        reference_image_plan: expect.arrayContaining([
          expect.objectContaining({
            category: "三视图",
            description: "编辑后的三视图 prompt",
          }),
        ]),
      });
    });
    expect(generateImageAssetJobSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        asset_type: "character_turnaround",
        related_id: "char-1",
      })
    );
  });

  it("renders duplicate business ids without duplicate React keys and still sends business ids", async () => {
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    listScenesSpy.mockResolvedValue({
      scenes: [
        {
          ...sceneList.scenes[0],
          id: "db-scene-1",
          scene_id: "scene-duplicate",
          name: "夜雨小巷 A",
        },
        {
          ...sceneList.scenes[0],
          id: "db-scene-2",
          scene_id: "scene-duplicate",
          name: "夜雨小巷 B",
        },
      ],
      total: 2,
    });

    render(<AssetWorkbenchPage />);

    await screen.findByRole("heading", { name: "素材工作台" });
    await userEvent.click(screen.getByRole("tab", { name: "场景" }));
    await screen.findByRole("heading", { name: "夜雨小巷 A" });
    await screen.findByRole("heading", { name: "夜雨小巷 B" });

    expect(
      consoleErrorSpy.mock.calls.some((call) =>
        call.some((entry) => String(entry).includes("Encountered two children with the same key"))
      )
    ).toBe(false);

    const sceneTitle = screen.getByRole("heading", { name: "夜雨小巷 A" });
    const sceneCard = sceneTitle.closest("[class*='space-y-3']")?.parentElement?.parentElement;
    expect(sceneCard).not.toBeNull();

    await userEvent.click(within(sceneCard as HTMLElement).getByRole("button", { name: "生成" }));

    await waitFor(() => {
      expect(generateImageAssetJobSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          asset_type: "scene_empty",
          related_id: "scene-duplicate",
        })
      );
    });

    consoleErrorSpy.mockRestore();
  });
});
