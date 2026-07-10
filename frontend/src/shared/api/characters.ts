// =============================================================================
// Story Engine — Characters API
// =============================================================================

import { USE_MOCK, apiFetch } from "@/shared/api/client";
import { resolveAssetStoragePath, resolveAssetUrl } from "@/shared/api/asset-url";
import { getMockCharacters } from "@/shared/api/mock-data";
import type {
  CharacterResponse,
  CharacterListResponse,
  CharacterUpdateRequest,
  CharacterRegenerateResponse,
  CharacterReferenceImagePlanItem,
} from "@/shared/types";

interface BackendCharacterResponse {
  id: string;
  project_id: string;
  character_id: string;
  name: string;
  role_type?: string;
  gender?: string;
  age?: string;
  default_outfit?: string;
  outfit_details?: string;
  identity?: string;
  personality?: string;
  emotion_pack?: string[];
  reference_image_plan?: CharacterReferenceImagePlanItem[];
  reference_assets?: string[];
  created_at: string;
  updated_at: string;
}

interface BackendCharacterListResponse {
  characters: BackendCharacterResponse[];
  total: number;
}

// ---------------------------------------------------------------------------
// List
// ---------------------------------------------------------------------------

export async function listCharacters(
  projectId: string
): Promise<CharacterListResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return getMockCharacters(projectId);
  }
  const response = await apiFetch<BackendCharacterListResponse>(
    `/api/projects/${projectId}/characters`
  );
  return {
    characters: response.characters.map(mapCharacter),
    total: response.total,
  };
}

// ---------------------------------------------------------------------------
// Get
// ---------------------------------------------------------------------------

export async function getCharacter(
  projectId: string,
  characterId: string
): Promise<CharacterResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const list = getMockCharacters(projectId);
    const character = list.characters.find(
      (c) => c.character_id === characterId
    );
    if (!character) throw new Error("Character not found");
    return character;
  }
  const response = await apiFetch<BackendCharacterResponse>(
    `/api/projects/${projectId}/characters/${characterId}`
  );
  return mapCharacter(response);
}

// ---------------------------------------------------------------------------
// Update
// ---------------------------------------------------------------------------

export async function updateCharacter(
  projectId: string,
  characterId: string,
  data: CharacterUpdateRequest
): Promise<CharacterResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    const list = getMockCharacters(projectId);
    const character = list.characters.find(
      (c) => c.character_id === characterId
    );
    if (!character) throw new Error("Character not found");
    return {
      ...character,
      ...data,
      updated_at: new Date().toISOString(),
    };
  }
  const response = await apiFetch<BackendCharacterResponse>(
    `/api/projects/${projectId}/characters/${characterId}`,
    {
      method: "PATCH",
      body: toBackendCharacterUpdate(data),
    }
  );
  return mapCharacter(response);
}

// ---------------------------------------------------------------------------
// Regenerate
// ---------------------------------------------------------------------------

export async function regenerateCharacter(
  projectId: string,
  characterId: string
): Promise<CharacterRegenerateResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 150));
    return {
      character_id: characterId,
      status: "regenerating",
      message: "Character regeneration started",
    };
  }
  const response = await apiFetch<Partial<CharacterRegenerateResponse> & { task_id?: string }>(
    `/api/projects/${projectId}/characters/${characterId}/regenerate`,
    {
      method: "POST",
    }
  );
  return {
    character_id: response.character_id || characterId,
    status: response.status || "pending",
    message: response.message || "Character regeneration started",
  };
}

export function mapCharacter(raw: BackendCharacterResponse): CharacterResponse {
  const outfit = normalizeOutfit(raw);
  const orderedReferenceAssets = orderCharacterReferenceAssets(raw.reference_assets || []);
  const referenceAssetIds = orderedReferenceAssets
    .map(resolveAssetStoragePath)
    .filter((path): path is string => Boolean(path));
  const referenceImageUrls = orderedReferenceAssets
    .map(resolveAssetUrl)
    .filter((path): path is string => Boolean(path));
  const promptPlan = raw.reference_image_plan || [];
  return {
    id: raw.id,
    project_id: raw.project_id,
    character_id: raw.character_id,
    name: raw.name,
    description: raw.personality || raw.identity || "",
    role: normalizeRole(raw.role_type),
    gender: raw.gender || undefined,
    age_range: raw.age || undefined,
    outfit,
    front_image_prompt: findPromptByCategory(promptPlan, "正面全身"),
    turnaround_prompt: findPromptByCategory(promptPlan, "三视图"),
    reference_image_plan: promptPlan,
    avatar_url: referenceImageUrls[0],
    reference_asset_ids: referenceAssetIds,
    reference_image_urls: referenceImageUrls,
    is_locked: false,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
  };
}

function findPromptByCategory(plan: CharacterReferenceImagePlanItem[], keyword: string): string | undefined {
  return plan.find((item) => String(item.category || "").includes(keyword))?.description?.trim() || undefined;
}

export function mergeReferenceImagePlan(
  plan: CharacterReferenceImagePlanItem[],
  updates: { frontImagePrompt?: string; turnaroundPrompt?: string }
): CharacterReferenceImagePlanItem[] {
  let result = plan.map((item) => ({ ...item }));
  result = upsertPlanPrompt(result, "正面全身", updates.frontImagePrompt);
  result = upsertPlanPrompt(result, "三视图", updates.turnaroundPrompt);
  return result;
}

function upsertPlanPrompt(
  plan: CharacterReferenceImagePlanItem[],
  category: string,
  prompt: string | undefined
): CharacterReferenceImagePlanItem[] {
  const cleanPrompt = prompt?.trim();
  if (!cleanPrompt) return plan;
  const index = plan.findIndex((item) => String(item.category || "").includes(category));
  if (index < 0) {
    return [...plan, { category, description: cleanPrompt }];
  }
  return plan.map((item, itemIndex) => (itemIndex === index ? { ...item, description: cleanPrompt } : item));
}

function orderCharacterReferenceAssets(paths: string[]): string[] {
  const front = latestAssetByStem(paths, "front");
  const turnaround = latestAssetByStem(paths, "turnaround");
  const ordered = [front, turnaround].filter((path): path is string => Boolean(path));
  return [...ordered, ...paths.filter((path) => !ordered.includes(path))];
}

function latestAssetByStem(paths: string[], stem: string): string | undefined {
  return paths.find((path) => new RegExp(`/${stem}\\.(png|jpe?g|webp)$`, "i").test(path));
}

function normalizeOutfit(raw: BackendCharacterResponse): string | undefined {
  const outfit = [raw.default_outfit, raw.outfit_details].filter(Boolean).join("，");
  if (outfit && !/符合角色身份|现代服装|通用服装/.test(outfit)) {
    return outfit;
  }
  const identity = raw.identity || raw.personality || raw.role_type || "";
  const isFemale = raw.gender === "女" || /女|妻|未婚妻|母|小姐/.test(identity);
  if (/婚|宴|豪门|富豪|总裁|继承人/.test(identity)) {
    return isFemale
      ? "现代都市婚宴礼服：黑色收腰缎面连衣裙，方领，七分袖，裙摆到小腿，细高跟鞋，珍珠耳钉和小号手拿包"
      : "现代都市高定西装：深炭灰修身三件套西装，白色衬衫，暗纹领带，黑色牛津皮鞋，银色腕表";
  }
  if (/助理|秘书|职场|公司/.test(identity)) {
    return isFemale
      ? "现代职场套装：米白短西装外套，浅蓝真丝衬衫，深灰高腰半身裙，低跟尖头鞋，细框眼镜"
      : "现代职场套装：藏蓝单排扣西装，浅灰衬衫，黑色西裤，商务皮鞋，简洁腕表";
  }
  return isFemale
    ? "现代都市日常穿搭：浅色针织上衣，短款外套，高腰直筒裤，白色低跟鞋，细项链和小耳钉"
    : "现代都市日常穿搭：深色短夹克，白色内搭，修身休闲长裤，黑色运动鞋，简洁腕表";
}

function normalizeRole(roleType?: string): string {
  if (!roleType) return "supporting";
  if (roleType.includes("主") || roleType === "protagonist") return "protagonist";
  if (roleType.includes("反") || roleType === "antagonist") return "antagonist";
  return "supporting";
}

export function toBackendCharacterUpdate(data: CharacterUpdateRequest): Record<string, unknown> {
  const body: Record<string, unknown> = { emotion_pack: [] };
  if (data.name !== undefined) body.name = data.name;
  if (data.description !== undefined) body.personality = data.description;
  if (data.outfit !== undefined) body.default_outfit = data.outfit.trim();
  if (data.reference_image_plan !== undefined) {
    body.reference_image_plan = data.reference_image_plan;
  }
  return body;
}
