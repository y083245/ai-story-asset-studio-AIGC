import { resolveAssetUrl } from "@/shared/api/asset-url";
import { USE_MOCK, apiFetch } from "@/shared/api/client";

export type ImageAssetType =
  | "character_bible_sheet"
  | "character_front"
  | "character_turnaround"
  | "character_expression"
  | "prop_product"
  | "prop_usage"
  | "scene_empty"
  | "scene_with_atmosphere";

export type AssetLibraryCategory = "character" | "prop" | "scene";

export interface GenerateImageAssetRequest {
  project_id: string;
  asset_type: ImageAssetType;
  related_id?: string | null;
  reference_asset_ids?: string[];
  extra_constraints?: string | null;
}

export interface ImageAssetResponse {
  asset_id: string;
  project_id: string;
  asset_type: ImageAssetType;
  related_id?: string | null;
  asset_url: string;
  thumbnail_url?: string | null;
  storage_path: string;
  prompt: string;
  negative_prompt: string;
  model_name: string;
  provider_task_id?: string | null;
  generation_task_id?: string | null;
  width: number;
  height: number;
  reference_asset_ids: string[];
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AssetLibraryQuery {
  date_from?: string;
  date_to?: string;
  project_id?: string;
  category?: AssetLibraryCategory;
  asset_type?: ImageAssetType;
  keyword?: string;
  page?: number;
  page_size?: number;
}

export interface AssetTrashQuery {
  date_from?: string;
  date_to?: string;
  project_id?: string;
  category?: AssetLibraryCategory;
  asset_type?: ImageAssetType;
  keyword?: string;
  page?: number;
  page_size?: number;
}

export interface AssetProjectOption {
  project_id: string;
  project_title: string;
  project_status: string;
  project_deleted_at?: string | null;
  is_project_in_trash: boolean;
  total: number;
}

export interface AssetLibraryItem {
  asset_id: string;
  display_name: string;
  project_id: string;
  project_title: string;
  project_status: string;
  project_deleted_at?: string | null;
  category: AssetLibraryCategory;
  asset_type: ImageAssetType;
  asset_type_label: string;
  related_id?: string | null;
  related_name?: string | null;
  asset_url: string;
  thumbnail_url?: string | null;
  storage_path: string;
  prompt_summary: string;
  prompt: string;
  model_name: string;
  status: string;
  quality_status?: string | null;
  width: number;
  height: number;
  created_at: string;
  expires_at: string;
  remaining_retention_days: number;
  is_expiring_soon: boolean;
}

export interface AssetProjectGroup {
  project_id: string;
  project_title: string;
  project_status: string;
  project_deleted_at?: string | null;
  is_project_in_trash: boolean;
  total: number;
  latest_created_at: string;
  categories: Record<AssetLibraryCategory, Array<AssetLibraryItem | AssetTrashItem>>;
}

export interface AssetDateGroup {
  date: string;
  total: number;
  project_count: number;
  projects: AssetProjectGroup[];
}

export interface AssetLibraryResponse {
  groups: AssetDateGroup[];
  available_projects: AssetProjectOption[];
  page: number;
  page_size: number;
  total: number;
}

export interface AssetTrashItem {
  asset_id: string;
  display_name: string;
  project_id: string;
  project_title: string;
  project_status: string;
  project_deleted_at?: string | null;
  category: AssetLibraryCategory;
  asset_type: ImageAssetType;
  asset_type_label: string;
  related_id?: string | null;
  related_name?: string | null;
  asset_url: string;
  thumbnail_url?: string | null;
  prompt_summary: string;
  prompt: string;
  model_name: string;
  status: string;
  quality_status?: string | null;
  created_at: string;
  deleted_at: string;
  purge_after?: string | null;
  expires_at: string;
  remaining_cleanup_days: number;
  can_restore: boolean;
}

export interface AssetTrashResponse {
  items: AssetTrashItem[];
  available_projects: AssetProjectOption[];
  page: number;
  page_size: number;
  total: number;
}

type AssetTrashApiItem = AssetTrashItem & {
  display_name?: string | null;
  prompt_summary?: string | null;
  prompt?: string | null;
  quality_status?: string | null;
  created_at?: string | null;
};

export interface AssetOperationResult {
  asset_id: string;
  status: "success" | "failed";
  code: string;
  message: string;
}

export interface AssetBatchOperationResponse {
  results: AssetOperationResult[];
  total: number;
  succeeded: number;
  failed: number;
}

export interface AssetMutationSummary {
  success_count: number;
  failure_count: number;
  first_error?: AssetOperationResult;
  results: AssetOperationResult[];
}

type MockProject = {
  project_id: string;
  project_title: string;
  project_status: string;
  project_deleted_at?: string | null;
};

type MockAsset = {
  asset_id: string;
  project_id: string;
  project_title: string;
  project_status: string;
  project_deleted_at?: string | null;
  category: AssetLibraryCategory;
  asset_type: ImageAssetType;
  asset_type_label: string;
  display_name: string;
  related_id?: string | null;
  related_name?: string | null;
  asset_url: string;
  thumbnail_url?: string | null;
  storage_path: string;
  prompt_summary: string;
  prompt: string;
  model_name: string;
  status: string;
  quality_status?: string | null;
  width: number;
  height: number;
  created_at: string;
  expires_at: string;
  deleted_at?: string | null;
  purge_after?: string | null;
  mock_behavior?: "delete_fail" | "restore_fail" | "permanent_fail";
};

const CATEGORY_ORDER: AssetLibraryCategory[] = ["character", "prop", "scene"];

const CATEGORY_ASSET_TYPE_OPTIONS: Record<AssetLibraryCategory, ImageAssetType[]> = {
  character: [
    "character_bible_sheet",
    "character_front",
    "character_turnaround",
    "character_expression",
  ],
  prop: ["prop_product", "prop_usage"],
  scene: ["scene_empty", "scene_with_atmosphere"],
};

const PROJECTS: MockProject[] = [
  {
    project_id: "project-alpha",
    project_title: "星港样片计划",
    project_status: "completed",
    project_deleted_at: null,
  },
  {
    project_id: "project-archived",
    project_title: "旧城补完计划",
    project_status: "archived",
    project_deleted_at: "2026-07-06T08:00:00+08:00",
  },
];

const SHANGHAI_DATE_FORMATTER = new Intl.DateTimeFormat("en-US", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

function formatShanghaiDate(iso: string): string {
  const parts = SHANGHAI_DATE_FORMATTER.formatToParts(new Date(iso));
  const year = parts.find((part) => part.type === "year")?.value ?? "0000";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

function buildPromptSummary(prefix: string): string {
  return `${prefix}，保留主体设计，控制背景干扰，提升材质和边缘清晰度。`;
}

function buildPrompt(prefix: string): string {
  return `FULL PROMPT: ${prefix}，高细节，电影级光照，构图稳定，背景噪点受控。`;
}

function initialMockAssets(): MockAsset[] {
  return [
    {
      asset_id: "asset-character-sheet",
      project_id: "project-alpha",
      project_title: "星港样片计划",
      project_status: "completed",
      project_deleted_at: null,
      category: "character",
      asset_type: "character_bible_sheet",
      asset_type_label: "设定板",
      display_name: "角色设定板",
      related_id: "CH_001",
      related_name: "林小雨",
      asset_url: "https://example.com/assets/character-sheet.png",
      thumbnail_url: "https://example.com/assets/character-sheet-thumb.png",
      storage_path: "projects/project-alpha/character-sheet.png",
      prompt_summary: buildPromptSummary("角色设定板，三视图与材质板同画面"),
      prompt: buildPrompt("角色设定板，三视图与材质板同画面"),
      model_name: "gpt-image-1",
      status: "completed",
      quality_status: "passed",
      width: 1024,
      height: 1024,
      created_at: "2026-07-08T10:20:00+08:00",
      expires_at: "2027-01-08T10:20:00+08:00",
    },
    {
      asset_id: "asset-character-front",
      project_id: "project-alpha",
      project_title: "星港样片计划",
      project_status: "completed",
      project_deleted_at: null,
      category: "character",
      asset_type: "character_front",
      asset_type_label: "正面图",
      display_name: "林小雨正面图",
      related_id: "CH_001",
      related_name: "林小雨",
      asset_url: "https://example.com/assets/character-front.png",
      thumbnail_url: "https://example.com/assets/character-front-thumb.png",
      storage_path: "projects/project-alpha/character-front.png",
      prompt_summary: buildPromptSummary("角色正面站姿，全身，服装细节清晰"),
      prompt: buildPrompt("角色正面站姿，全身，服装细节清晰"),
      model_name: "seedream-3.0",
      status: "completed",
      quality_status: "passed",
      width: 1024,
      height: 1536,
      created_at: "2026-07-08T09:50:00+08:00",
      expires_at: "2027-01-08T09:50:00+08:00",
    },
    {
      asset_id: "asset-prop-usage",
      project_id: "project-alpha",
      project_title: "星港样片计划",
      project_status: "completed",
      project_deleted_at: null,
      category: "prop",
      asset_type: "prop_usage",
      asset_type_label: "道具使用图",
      display_name: "神经终端使用图",
      related_id: "PR_001",
      related_name: "神经终端",
      asset_url: "https://example.com/assets/prop-usage.png",
      thumbnail_url: "https://example.com/assets/prop-usage-thumb.png",
      storage_path: "projects/project-alpha/prop-usage.png",
      prompt_summary: buildPromptSummary("道具在角色手中使用，强调交互关系"),
      prompt: buildPrompt("道具在角色手中使用，强调交互关系"),
      model_name: "seedream-3.0",
      status: "completed",
      quality_status: "needs_retry",
      width: 1280,
      height: 720,
      created_at: "2026-07-08T08:10:00+08:00",
      expires_at: "2027-01-08T08:10:00+08:00",
    },
    {
      asset_id: "asset-scene-expiring",
      project_id: "project-alpha",
      project_title: "星港样片计划",
      project_status: "completed",
      project_deleted_at: null,
      category: "scene",
      asset_type: "scene_with_atmosphere",
      asset_type_label: "氛围场景图",
      display_name: "雨夜巷道氛围图",
      related_id: "SC_001",
      related_name: "雨夜巷道",
      asset_url: "https://example.com/assets/scene-atmosphere.png",
      thumbnail_url: "https://example.com/assets/scene-atmosphere-thumb.png",
      storage_path: "projects/project-alpha/scene-atmosphere.png",
      prompt_summary: buildPromptSummary("低饱和雨夜场景，霓虹反射明显"),
      prompt: buildPrompt("低饱和雨夜场景，霓虹反射明显"),
      model_name: "imagen-4",
      status: "completed",
      quality_status: "passed",
      width: 1536,
      height: 864,
      created_at: "2026-07-08T07:20:00+08:00",
      expires_at: "2026-07-13T07:20:00+08:00",
    },
    {
      asset_id: "asset-archived-scene",
      project_id: "project-archived",
      project_title: "旧城补完计划",
      project_status: "archived",
      project_deleted_at: "2026-07-06T08:00:00+08:00",
      category: "scene",
      asset_type: "scene_empty",
      asset_type_label: "纯场景图",
      display_name: "旧城街角纯场景",
      related_id: "SC_007",
      related_name: "旧城街角",
      asset_url: "https://example.com/assets/archived-scene.png",
      thumbnail_url: "https://example.com/assets/archived-scene-thumb.png",
      storage_path: "projects/project-archived/scene-empty.png",
      prompt_summary: buildPromptSummary("无人纯场景，街角结构干净"),
      prompt: buildPrompt("无人纯场景，街角结构干净"),
      model_name: "flux-pro",
      status: "completed",
      quality_status: "passed",
      width: 1280,
      height: 720,
      created_at: "2026-07-07T22:15:00+08:00",
      expires_at: "2027-01-07T22:15:00+08:00",
    },
    {
      asset_id: "asset-batch-delete-fail",
      project_id: "project-alpha",
      project_title: "星港样片计划",
      project_status: "completed",
      project_deleted_at: null,
      category: "prop",
      asset_type: "prop_product",
      asset_type_label: "单一道具图",
      display_name: "删除失败示例",
      related_id: "PR_999",
      related_name: "删除失败示例",
      asset_url: "https://example.com/assets/delete-fail.png",
      thumbnail_url: "https://example.com/assets/delete-fail-thumb.png",
      storage_path: "projects/project-alpha/delete-fail.png",
      prompt_summary: buildPromptSummary("用于批量删除失败测试"),
      prompt: buildPrompt("用于批量删除失败测试"),
      model_name: "seedream-3.0",
      status: "completed",
      quality_status: "passed",
      width: 1024,
      height: 1024,
      created_at: "2026-07-08T06:30:00+08:00",
      expires_at: "2027-01-08T06:30:00+08:00",
      mock_behavior: "delete_fail",
    },
    {
      asset_id: "asset-trash-restore-fail",
      project_id: "project-alpha",
      project_title: "星港样片计划",
      project_status: "completed",
      project_deleted_at: null,
      category: "character",
      asset_type: "character_expression",
      asset_type_label: "表情图",
      display_name: "恢复失败示例",
      related_id: "CH_009",
      related_name: "恢复失败示例",
      asset_url: "https://example.com/assets/restore-fail.png",
      thumbnail_url: "https://example.com/assets/restore-fail-thumb.png",
      storage_path: "projects/project-alpha/restore-fail.png",
      prompt_summary: buildPromptSummary("用于恢复失败测试"),
      prompt: buildPrompt("用于恢复失败测试"),
      model_name: "seedream-3.0",
      status: "completed",
      quality_status: "passed",
      width: 1024,
      height: 1024,
      created_at: "2026-07-06T18:30:00+08:00",
      deleted_at: "2026-07-07T16:30:00Z",
      purge_after: "2026-08-07T11:10:00+08:00",
      expires_at: "2027-01-06T18:30:00+08:00",
      mock_behavior: "restore_fail",
    },
    {
      asset_id: "asset-trash-permanent-fail",
      project_id: "project-alpha",
      project_title: "星港样片计划",
      project_status: "completed",
      project_deleted_at: null,
      category: "prop",
      asset_type: "prop_product",
      asset_type_label: "单一道具图",
      display_name: "无法永久删除示例",
      related_id: "PR_777",
      related_name: "无法永久删除示例",
      asset_url: "https://example.com/assets/permanent-fail.png",
      thumbnail_url: "https://example.com/assets/permanent-fail-thumb.png",
      storage_path: "projects/project-alpha/permanent-fail.png",
      prompt_summary: buildPromptSummary("用于永久删除失败测试"),
      prompt: buildPrompt("用于永久删除失败测试"),
      model_name: "seedream-3.0",
      status: "completed",
      quality_status: "passed",
      width: 1024,
      height: 1024,
      created_at: "2026-07-05T12:00:00+08:00",
      expires_at: "2027-01-05T12:00:00+08:00",
      mock_behavior: "permanent_fail",
    },
  ];
}

let mockAssets = initialMockAssets();

function nowIso(): string {
  return new Date().toISOString();
}

function toAssetProjectOption(project: MockProject, total: number): AssetProjectOption {
  return {
    project_id: project.project_id,
    project_title: project.project_title,
    project_status: project.project_status,
    project_deleted_at: project.project_deleted_at ?? null,
    is_project_in_trash: Boolean(project.project_deleted_at) || project.project_status === "archived",
    total,
  };
}

function toLibraryItem(asset: MockAsset): AssetLibraryItem {
  return {
    asset_id: asset.asset_id,
    display_name: asset.display_name,
    project_id: asset.project_id,
    project_title: asset.project_title,
    project_status: asset.project_status,
    project_deleted_at: asset.project_deleted_at ?? null,
    category: asset.category,
    asset_type: asset.asset_type,
    asset_type_label: asset.asset_type_label,
    related_id: asset.related_id ?? null,
    related_name: asset.related_name ?? null,
    asset_url: resolveAssetUrl(asset.asset_url) ?? "",
    thumbnail_url: resolveAssetUrl(asset.thumbnail_url) ?? null,
    storage_path: asset.storage_path,
    prompt_summary: asset.prompt_summary,
    prompt: asset.prompt,
    model_name: asset.model_name,
    status: asset.status,
    quality_status: asset.quality_status ?? null,
    width: asset.width,
    height: asset.height,
    created_at: asset.created_at,
    expires_at: asset.expires_at,
    remaining_retention_days: remainingDays(asset.expires_at),
    is_expiring_soon: remainingDays(asset.expires_at) < 7,
  };
}

function toTrashItem(asset: MockAsset): AssetTrashItem {
  return {
    asset_id: asset.asset_id,
    display_name: asset.display_name,
    project_id: asset.project_id,
    project_title: asset.project_title,
    project_status: asset.project_status,
    project_deleted_at: asset.project_deleted_at ?? null,
    category: asset.category,
    asset_type: asset.asset_type,
    asset_type_label: asset.asset_type_label,
    related_id: asset.related_id ?? null,
    related_name: asset.related_name ?? null,
    asset_url: resolveAssetUrl(asset.asset_url) ?? "",
    thumbnail_url: resolveAssetUrl(asset.thumbnail_url) ?? null,
    prompt_summary: asset.prompt_summary,
    prompt: asset.prompt,
    model_name: asset.model_name,
    status: asset.status,
    quality_status: asset.quality_status ?? null,
    created_at: asset.created_at,
    deleted_at: asset.deleted_at ?? nowIso(),
    purge_after: asset.purge_after ?? null,
    expires_at: asset.expires_at,
    remaining_cleanup_days: asset.purge_after ? remainingDays(asset.purge_after) : 0,
    can_restore: remainingDays(asset.expires_at) > 0,
  };
}

function remainingDays(deadlineIso: string): number {
  const deadline = new Date(deadlineIso).getTime();
  const diff = deadline - new Date("2026-07-08T00:00:00+08:00").getTime();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

function filterLibraryAssets(query: AssetLibraryQuery): MockAsset[] {
  return mockAssets
    .filter((asset) => !asset.deleted_at)
    .filter((asset) => remainingDays(asset.expires_at) > 0)
    .filter((asset) => !query.project_id || asset.project_id === query.project_id)
    .filter((asset) => !query.category || asset.category === query.category)
    .filter((asset) => !query.asset_type || asset.asset_type === query.asset_type)
    .filter((asset) => !query.date_from || asset.created_at.slice(0, 10) >= query.date_from)
    .filter((asset) => !query.date_to || asset.created_at.slice(0, 10) <= query.date_to)
    .filter((asset) => {
      if (!query.keyword) return true;
      const keyword = query.keyword.toLowerCase();
      return [
        asset.project_title,
        asset.related_name,
        asset.related_id,
        asset.display_name,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(keyword));
    })
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
}

function filterTrashAssets(query: AssetTrashQuery): MockAsset[] {
  return mockAssets
    .filter((asset) => Boolean(asset.deleted_at))
    .filter((asset) => !query.project_id || asset.project_id === query.project_id)
    .filter((asset) => !query.category || asset.category === query.category)
    .filter((asset) => !query.asset_type || asset.asset_type === query.asset_type)
    .filter((asset) => !query.date_from || formatShanghaiDate(asset.deleted_at ?? nowIso()) >= query.date_from)
    .filter((asset) => !query.date_to || formatShanghaiDate(asset.deleted_at ?? nowIso()) <= query.date_to)
    .filter((asset) => {
      if (!query.keyword) return true;
      const keyword = query.keyword.toLowerCase();
      return [
        asset.project_title,
        asset.related_name,
        asset.related_id,
        asset.display_name,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(keyword));
    })
    .sort((a, b) => (b.deleted_at ?? "").localeCompare(a.deleted_at ?? ""));
}

function paginate<T>(items: T[], page = 1, pageSize = 20): T[] {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

function groupLibraryAssets(items: MockAsset[]): AssetDateGroup[] {
  const byDate = new Map<string, MockAsset[]>();

  for (const asset of items) {
    const dateKey = asset.created_at.slice(0, 10);
    const group = byDate.get(dateKey) ?? [];
    group.push(asset);
    byDate.set(dateKey, group);
  }

  return Array.from(byDate.entries())
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, dateAssets]) => {
      const byProject = new Map<string, MockAsset[]>();
      for (const asset of dateAssets) {
        const group = byProject.get(asset.project_id) ?? [];
        group.push(asset);
        byProject.set(asset.project_id, group);
      }

      const projects = Array.from(byProject.entries())
        .map(([projectId, projectAssets]) => {
          const latestCreatedAt = [...projectAssets]
            .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]?.created_at ?? date;
          const project = PROJECTS.find((item) => item.project_id === projectId);
          const categories: Record<AssetLibraryCategory, AssetLibraryItem[]> = {
            character: [],
            prop: [],
            scene: [],
          };

          for (const category of CATEGORY_ORDER) {
            categories[category] = projectAssets
              .filter((asset) => asset.category === category)
              .sort((a, b) => b.created_at.localeCompare(a.created_at))
              .map(toLibraryItem);
          }

          return {
            project_id: projectId,
            project_title: project?.project_title ?? projectAssets[0]?.project_title ?? "",
            project_status: project?.project_status ?? projectAssets[0]?.project_status ?? "completed",
            project_deleted_at: project?.project_deleted_at ?? projectAssets[0]?.project_deleted_at ?? null,
            is_project_in_trash:
              Boolean(project?.project_deleted_at ?? projectAssets[0]?.project_deleted_at) ||
              (project?.project_status ?? projectAssets[0]?.project_status) === "archived",
            total: projectAssets.length,
            latest_created_at: latestCreatedAt,
            categories,
          } satisfies AssetProjectGroup;
        })
        .sort((a, b) => b.latest_created_at.localeCompare(a.latest_created_at));

      return {
        date,
        total: dateAssets.length,
        project_count: projects.length,
        projects,
      };
    });
}

function buildProjectOptions(items: MockAsset[]): AssetProjectOption[] {
  return PROJECTS
    .map((project) => {
      const total = items.filter((asset) => asset.project_id === project.project_id).length;
      return total > 0 ? toAssetProjectOption(project, total) : null;
    })
    .filter((item): item is AssetProjectOption => Boolean(item));
}

function summarizeBatch(response: AssetBatchOperationResponse): AssetMutationSummary {
  return {
    success_count: response.succeeded,
    failure_count: response.failed,
    first_error: response.results.find((result) => result.status === "failed"),
    results: response.results,
  };
}

function mockFailure(assetId: string, code: string, message: string): AssetOperationResult {
  return {
    asset_id: assetId,
    status: "failed",
    code,
    message,
  };
}

function mockSuccess(assetId: string, code: string, message: string): AssetOperationResult {
  return {
    asset_id: assetId,
    status: "success",
    code,
    message,
  };
}

function findMockAsset(assetId: string): MockAsset | undefined {
  return mockAssets.find((asset) => asset.asset_id === assetId);
}

function runMockDelete(assetId: string): AssetOperationResult {
  const asset = findMockAsset(assetId);
  if (!asset) return mockFailure(assetId, "IMAGE_ASSET_NOT_FOUND", `Asset ${assetId} not found`);
  if (asset.mock_behavior === "delete_fail") {
    return mockFailure(assetId, "IMAGE_ASSET_DELETE_FAILED", `${assetId} delete failed`);
  }
  if (asset.deleted_at) return mockSuccess(assetId, "IMAGE_ASSET_ALREADY_TRASHED", "Asset already in trash");

  asset.deleted_at = "2026-07-08T12:00:00+08:00";
  asset.purge_after = "2026-08-07T12:00:00+08:00";
  return mockSuccess(assetId, "IMAGE_ASSET_TRASHED", "Asset moved to trash");
}

function runMockRestore(assetId: string): AssetOperationResult {
  const asset = findMockAsset(assetId);
  if (!asset) return mockFailure(assetId, "IMAGE_ASSET_NOT_FOUND", `Asset ${assetId} not found`);
  if (asset.mock_behavior === "restore_fail") {
    return mockFailure(assetId, "IMAGE_ASSET_RESTORE_FAILED", `${assetId} restore failed`);
  }
  asset.deleted_at = null;
  asset.purge_after = null;
  return mockSuccess(assetId, "IMAGE_ASSET_RESTORED", "Asset restored from trash");
}

function runMockPermanentDelete(assetId: string): AssetOperationResult {
  const asset = findMockAsset(assetId);
  if (!asset) return mockFailure(assetId, "IMAGE_ASSET_NOT_FOUND", `Asset ${assetId} not found`);
  if (asset.mock_behavior === "permanent_fail") {
    return mockFailure(assetId, "IMAGE_ASSET_PERMANENT_DELETE_FAILED", `${assetId} permanent delete failed`);
  }
  mockAssets = mockAssets.filter((item) => item.asset_id !== assetId);
  return mockSuccess(assetId, "IMAGE_ASSET_PERMANENTLY_DELETED", "Asset permanently deleted");
}

function encodeQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

function normalizeBatchResponse(response: AssetBatchOperationResponse): AssetMutationSummary {
  return summarizeBatch(response);
}

function normalizeProjectOption(option: {
  project_id: string;
  project_title: string;
  project_status: string;
  project_deleted_at?: string | null;
  is_project_in_trash: boolean;
  total: number;
}): AssetProjectOption {
  return {
    project_id: option.project_id,
    project_title: option.project_title,
    project_status: option.project_status,
    project_deleted_at: option.project_deleted_at ?? null,
    is_project_in_trash: option.is_project_in_trash,
    total: option.total,
  };
}

function normalizeTrashItem(item: AssetTrashApiItem): AssetTrashItem {
  const prompt = item.prompt?.trim() || "";
  const promptSummary = item.prompt_summary?.trim() || prompt || "暂无 prompt 摘要";
  const displayName = item.display_name?.trim() || item.related_name?.trim() || item.related_id || item.asset_type_label || item.asset_id;

  return {
    ...item,
    display_name: displayName,
    prompt,
    prompt_summary: promptSummary,
    quality_status: item.quality_status ?? null,
    created_at: item.created_at ?? item.deleted_at,
    project_deleted_at: item.project_deleted_at ?? null,
    purge_after: item.purge_after ?? null,
    asset_url: resolveAssetUrl(item.asset_url) ?? "",
    thumbnail_url: resolveAssetUrl(item.thumbnail_url) ?? null,
  };
}

function normalizeImageAssetResponse(item: ImageAssetResponse): ImageAssetResponse {
  return {
    ...item,
    asset_url: resolveAssetUrl(item.asset_url) ?? "",
    thumbnail_url: resolveAssetUrl(item.thumbnail_url) ?? null,
  };
}

function normalizeAssetCardItem<T extends AssetLibraryItem | AssetTrashItem>(item: T): T {
  return {
    ...item,
    asset_url: resolveAssetUrl(item.asset_url) ?? "",
    thumbnail_url: resolveAssetUrl(item.thumbnail_url) ?? null,
    project_deleted_at: item.project_deleted_at ?? null,
    quality_status: item.quality_status ?? null,
  };
}

function normalizeLibraryResponse(response: AssetLibraryResponse): AssetLibraryResponse {
  return {
    ...response,
    groups: response.groups.map((group) => ({
      ...group,
      projects: group.projects.map((project) => ({
        ...project,
        project_deleted_at: project.project_deleted_at ?? null,
        categories: {
          character: project.categories.character.map(normalizeAssetCardItem),
          prop: project.categories.prop.map(normalizeAssetCardItem),
          scene: project.categories.scene.map(normalizeAssetCardItem),
        },
      })),
    })),
    available_projects: response.available_projects.map(normalizeProjectOption),
  };
}

export interface GenerateJobResponse {
  task_id: string;
  project_id: string;
  status: string;
  polling_url: string;
}

export interface GenerationTaskResponse {
  task_id: string;
  project_id: string;
  asset_type: string;
  related_id?: string | null;
  provider: string;
  model_name: string;
  status: string;
  retry_count: number;
  max_retries: number;
  error_message?: string | null;
  quality_status?: string | null;
  quality_report_id?: string | null;
  asset_id?: string | null;
  storage_path?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export async function generateImageAssetJob(
  request: GenerateImageAssetRequest
): Promise<GenerateJobResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 50));
    return {
      task_id: `mock-task-${Date.now()}`,
      project_id: request.project_id,
      status: "pending",
      polling_url: `/api/image-asset/tasks/mock-task-${Date.now()}`,
    };
  }

  return apiFetch<GenerateJobResponse>("/api/image-asset/generate-jobs", {
    method: "POST",
    body: {
      project_id: request.project_id,
      asset_type: request.asset_type,
      related_id: request.related_id ?? null,
      reference_asset_ids: request.reference_asset_ids || [],
      extra_constraints: request.extra_constraints || null,
    },
  });
}

export async function getGenerationTask(
  taskId: string
): Promise<GenerationTaskResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 50));
    return {
      task_id: taskId,
      project_id: "mock-project",
      asset_type: "character_front",
      provider: "mock",
      model_name: "mock",
      status: "success",
      retry_count: 0,
      max_retries: 3,
      error_message: null,
      quality_status: null,
      quality_report_id: null,
      asset_id: `mock-asset-${Date.now()}`,
      storage_path: `projects/${taskId}/mock/character-front.png`,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }

  return apiFetch<GenerationTaskResponse>(
    `/api/image-asset/tasks/${taskId}`
  );
}

export async function pollTaskUntilDone(
  taskId: string,
  intervalMs: number = 2000,
  timeoutMs: number = 300000
): Promise<GenerationTaskResponse> {
  const startedAt = Date.now();

  while (true) {
    const task = await getGenerationTask(taskId);

    if (task.status === "success" || task.status === "failed" || task.status === "cancelled") {
      return task;
    }

    if (Date.now() - startedAt >= timeoutMs) {
      throw new Error(`任务 ${taskId} 超时：超过 ${Math.round(timeoutMs / 1000)} 秒未完成`);
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export async function generateImageAsset(request: GenerateImageAssetRequest): Promise<ImageAssetResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 50));
    return {
      asset_id: `mock-${Date.now()}`,
      project_id: request.project_id,
      asset_type: request.asset_type,
      related_id: request.related_id,
      asset_url: "",
      storage_path: `projects/${request.project_id}/mock/${request.asset_type}.png`,
      prompt: request.extra_constraints || "",
      negative_prompt: "",
      model_name: "mock",
      width: 1024,
      height: 1024,
      reference_asset_ids: request.reference_asset_ids || [],
      status: "completed",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }

  const response = await apiFetch<ImageAssetResponse>("/api/image-asset/generate", {
    method: "POST",
    body: {
      project_id: request.project_id,
      asset_type: request.asset_type,
      related_id: request.related_id ?? null,
      reference_asset_ids: request.reference_asset_ids || [],
      extra_constraints: request.extra_constraints || null,
    },
  });
  return normalizeImageAssetResponse(response);
}

export async function listAssetLibrary(query: AssetLibraryQuery): Promise<AssetLibraryResponse> {
  if (USE_MOCK) {
    const page = query.page ?? 1;
    const pageSize = query.page_size ?? 20;
    const filtered = filterLibraryAssets(query);
    const paged = paginate(filtered, page, pageSize);
    return {
      groups: groupLibraryAssets(paged),
      available_projects: buildProjectOptions(filtered),
      page,
      page_size: pageSize,
      total: filtered.length,
    };
  }

  const response = await apiFetch<AssetLibraryResponse>(
    `/api/image-asset/library${encodeQuery({
      date_from: query.date_from,
      date_to: query.date_to,
      project_id: query.project_id,
      category: query.category,
      asset_type: query.asset_type,
      keyword: query.keyword,
      page: query.page,
      page_size: query.page_size,
    })}`
  );

  return normalizeLibraryResponse(response);
}

export async function listAssetTrash(query: AssetTrashQuery): Promise<AssetTrashResponse> {
  if (USE_MOCK) {
    const page = query.page ?? 1;
    const pageSize = query.page_size ?? 20;
    const filtered = filterTrashAssets(query);
    const paged = paginate(filtered, page, pageSize);
    return {
      items: paged.map(toTrashItem),
      available_projects: buildProjectOptions(filtered),
      page,
      page_size: pageSize,
      total: filtered.length,
    };
  }

  const response = await apiFetch<{
    items: AssetTrashApiItem[];
    available_projects: Array<{
      project_id: string;
      project_title: string;
      project_status: string;
      project_deleted_at?: string | null;
      is_project_in_trash: boolean;
      total: number;
    }>;
    page: number;
    page_size: number;
    total: number;
  }>(
    `/api/image-asset/trash${encodeQuery({
      date_from: query.date_from,
      date_to: query.date_to,
      project_id: query.project_id,
      category: query.category,
      asset_type: query.asset_type,
      keyword: query.keyword,
      page: query.page,
      page_size: query.page_size,
    })}`
  );

  return {
    ...response,
    items: response.items.map(normalizeTrashItem),
    available_projects: response.available_projects.map(normalizeProjectOption),
  };
}

export function getAssetTypeOptionsByCategory(category: AssetLibraryCategory | "all"): ImageAssetType[] {
  if (category === "all") {
    return CATEGORY_ORDER.flatMap((key) => CATEGORY_ASSET_TYPE_OPTIONS[key]);
  }
  return CATEGORY_ASSET_TYPE_OPTIONS[category];
}

export async function deleteImageAsset(assetId: string): Promise<AssetOperationResult> {
  if (USE_MOCK) {
    return runMockDelete(assetId);
  }

  return apiFetch<AssetOperationResult>(`/api/image-asset/${assetId}`, {
    method: "DELETE",
  });
}

export async function batchDeleteImageAssets(assetIds: string[]): Promise<AssetMutationSummary> {
  if (USE_MOCK) {
    const results = assetIds.map(runMockDelete);
    return summarizeBatch({
      results,
      total: results.length,
      succeeded: results.filter((result) => result.status === "success").length,
      failed: results.filter((result) => result.status === "failed").length,
    });
  }

  const response = await apiFetch<AssetBatchOperationResponse>("/api/image-asset/batch-delete", {
    method: "POST",
    body: { asset_ids: assetIds },
  });

  return normalizeBatchResponse(response);
}

export async function restoreImageAsset(assetId: string): Promise<AssetOperationResult> {
  if (USE_MOCK) {
    return runMockRestore(assetId);
  }

  return apiFetch<AssetOperationResult>(`/api/image-asset/${assetId}/restore`, {
    method: "POST",
  });
}

export async function batchRestoreImageAssets(assetIds: string[]): Promise<AssetMutationSummary> {
  if (USE_MOCK) {
    const results = assetIds.map(runMockRestore);
    return summarizeBatch({
      results,
      total: results.length,
      succeeded: results.filter((result) => result.status === "success").length,
      failed: results.filter((result) => result.status === "failed").length,
    });
  }

  const response = await apiFetch<AssetBatchOperationResponse>("/api/image-asset/batch-restore", {
    method: "POST",
    body: { asset_ids: assetIds },
  });

  return normalizeBatchResponse(response);
}

export async function permanentDeleteImageAsset(assetId: string): Promise<AssetOperationResult> {
  if (USE_MOCK) {
    return runMockPermanentDelete(assetId);
  }

  return apiFetch<AssetOperationResult>(`/api/image-asset/${assetId}/permanent`, {
    method: "DELETE",
  });
}

export async function batchPermanentDeleteImageAssets(assetIds: string[]): Promise<AssetMutationSummary> {
  if (USE_MOCK) {
    const results = assetIds.map(runMockPermanentDelete);
    return summarizeBatch({
      results,
      total: results.length,
      succeeded: results.filter((result) => result.status === "success").length,
      failed: results.filter((result) => result.status === "failed").length,
    });
  }

  const response = await apiFetch<AssetBatchOperationResponse>("/api/image-asset/batch-permanent-delete", {
    method: "POST",
    body: {
      requests: assetIds.map((asset_id) => ({
        asset_id,
        reason: "manual_permanent",
      })),
    },
  });

  return normalizeBatchResponse(response);
}

export function __resetMockImageAssetStore(): void {
  mockAssets = initialMockAssets();
}
