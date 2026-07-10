import { describe, expect, it } from "vitest";

import { mapCharacter, mergeReferenceImagePlan, toBackendCharacterUpdate } from "@/shared/api/characters";
import { mapProp } from "@/shared/api/props";
import { mapScene } from "@/shared/api/scenes";

describe("asset prompt API mapping", () => {
  it("preserves character front and turnaround prompts from reference image plans", () => {
    const character = mapCharacter({
      id: "1",
      project_id: "p1",
      character_id: "CH_001",
      name: "林晓",
      role_type: "主角",
      reference_image_plan: [
        { category: "正面全身", description: "真人电影级正面站立全身角色资产图" },
        { category: "三视图", description: "一张高精度、干净极简的角色设定板" },
      ],
      reference_assets: [],
      created_at: "2026-07-05T00:00:00Z",
      updated_at: "2026-07-05T00:00:00Z",
    });

    expect(character.front_image_prompt).toBe("真人电影级正面站立全身角色资产图");
    expect(character.turnaround_prompt).toBe("一张高精度、干净极简的角色设定板");
  });

  it("maps character reference assets to browser-loadable URLs", () => {
    const character = mapCharacter({
      id: "1",
      project_id: "p1",
      character_id: "CH_001",
      name: "林晓",
      role_type: "主角",
      reference_assets: [
        "file:///app/local_storage/projects/p1/characters/CH_001/front.png",
        "projects/p1/characters/CH_001/turnaround.webp",
      ],
      created_at: "2026-07-05T00:00:00Z",
      updated_at: "2026-07-05T00:00:00Z",
    });

    expect(character.avatar_url).toBe("/local-storage/projects/p1/characters/CH_001/front.png");
    expect(character.reference_asset_ids).toEqual([
      "projects/p1/characters/CH_001/front.png",
      "projects/p1/characters/CH_001/turnaround.webp",
    ]);
    expect(character.reference_image_urls).toEqual([
      "/local-storage/projects/p1/characters/CH_001/front.png",
      "/local-storage/projects/p1/characters/CH_001/turnaround.webp",
    ]);
  });

  it("prefers the newest character front reference when old front assets remain", () => {
    const character = mapCharacter({
      id: "1",
      project_id: "p1",
      character_id: "CH_001",
      name: "林晓",
      role_type: "主角",
      reference_assets: [
        "projects/p1/characters/CH_001/front.jpg",
        "projects/p1/characters/CH_001/front.png",
        "projects/p1/characters/CH_001/turnaround.jpg",
      ],
      created_at: "2026-07-05T00:00:00Z",
      updated_at: "2026-07-05T00:00:00Z",
    });

    expect(character.avatar_url).toBe("/local-storage/projects/p1/characters/CH_001/front.jpg");
    expect(character.reference_image_urls[0]).toBe("/local-storage/projects/p1/characters/CH_001/front.jpg");
    expect(character.reference_image_urls[1]).toBe("/local-storage/projects/p1/characters/CH_001/turnaround.jpg");
  });

  it("merges character prompt edits without dropping style metadata or other plan entries", () => {
    const existingPlan = [
      { category: "正面全身", description: "old front", style_id: "xianxia", priority: "required" },
      { category: "三视图", description: "old turnaround", style_id: "xianxia", priority: "required" },
      { category: "表情", description: "expression sheet", style_id: "xianxia", priority: "optional" },
    ];

    const merged = mergeReferenceImagePlan(existingPlan, { frontImagePrompt: "new front" });

    expect(merged).toEqual([
      { category: "正面全身", description: "new front", style_id: "xianxia", priority: "required" },
      { category: "三视图", description: "old turnaround", style_id: "xianxia", priority: "required" },
      { category: "表情", description: "expression sheet", style_id: "xianxia", priority: "optional" },
    ]);
    expect(toBackendCharacterUpdate({ reference_image_plan: merged })).toEqual({ emotion_pack: [], reference_image_plan: merged });
  });

  it("preserves scene prompts separately from display description", () => {
    const scene = mapScene({
      id: "1",
      project_id: "p1",
      scene_id: "SC_001",
      scene_name: "雨夜下层霓虹巷",
      scene_prompt: "有人物版场景提示词",
      empty_scene_prompt: "不能出现其他人，无人，纯场景，雨夜下层霓虹巷",
      fixed_anchors: ["湿润混凝土", "全息光幕"],
      reference_assets: [],
      created_at: "2026-07-05T00:00:00Z",
      updated_at: "2026-07-05T00:00:00Z",
    });

    expect(scene.scene_prompt).toBe("有人物版场景提示词");
    expect(scene.empty_scene_prompt).toBe("不能出现其他人，无人，纯场景，雨夜下层霓虹巷");
    expect(scene.description).toBe("有人物版场景提示词");
  });

  it("maps scene thumbnails to browser-loadable URLs", () => {
    const scene = mapScene({
      id: "1",
      project_id: "p1",
      scene_id: "SC_001",
      scene_name: "雨夜下层霓虹巷",
      fixed_anchors: [],
      reference_assets: ["file:///Users/example/story-asset-studio/backend/local_storage/projects/p1/scenes/SC_001/empty.png"],
      created_at: "2026-07-05T00:00:00Z",
      updated_at: "2026-07-05T00:00:00Z",
    });

    expect(scene.thumbnail_url).toBe("/local-storage/projects/p1/scenes/SC_001/empty.png");
  });

  it("preserves prop product and usage prompts", () => {
    const prop = mapProp({
      id: "1",
      project_id: "p1",
      prop_id: "PR_001",
      name: "神经入侵终端",
      visual_features: "黑色碳纤维设备",
      plot_function: "入侵系统",
      prop_prompt: "单一道具资产图，黑色反射台面，神经入侵终端",
      usage_prompt: "神经入侵终端在剧情场景中的摆放参考图",
      reference_assets: [],
      created_at: "2026-07-05T00:00:00Z",
      updated_at: "2026-07-05T00:00:00Z",
    });

    expect(prop.prop_prompt).toBe("单一道具资产图，黑色反射台面，神经入侵终端");
    expect(prop.usage_prompt).toBe("神经入侵终端在剧情场景中的摆放参考图");
  });

  it("maps prop thumbnails to browser-loadable URLs", () => {
    const prop = mapProp({
      id: "1",
      project_id: "p1",
      prop_id: "PR_001",
      name: "神经入侵终端",
      reference_assets: ["projects/p1/props/PR_001/product.png"],
      created_at: "2026-07-05T00:00:00Z",
      updated_at: "2026-07-05T00:00:00Z",
    });

    expect(prop.thumbnail_url).toBe("/local-storage/projects/p1/props/PR_001/product.png");
  });
});
