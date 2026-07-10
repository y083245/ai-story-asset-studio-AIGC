"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  batchPermanentDeleteImageAssets,
  batchRestoreImageAssets,
  listAssetTrash,
  permanentDeleteImageAsset,
  restoreImageAsset,
  type AssetDateGroup,
  type AssetLibraryCategory,
  type AssetTrashItem,
  type AssetMutationSummary,
  type AssetOperationResult,
  type AssetProjectGroup,
  type AssetTrashQuery,
  type AssetTrashResponse,
} from "@/shared/api/image-assets";
import type { AssetLibraryFilters } from "@/features/asset-library/types";

const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 50;

function formatShanghaiDate(iso: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(iso));
  const year = parts.find((part) => part.type === "year")?.value ?? "0000";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

function toQuery(filters: AssetLibraryFilters, page: number, pageSize: number): AssetTrashQuery {
  return {
    keyword: filters.keyword || undefined,
    date_from: filters.startDate || undefined,
    date_to: filters.endDate || undefined,
    project_id: filters.projectId || undefined,
    category: filters.category === "all" ? undefined : filters.category,
    asset_type: filters.assetType === "all" ? undefined : filters.assetType,
    page,
    page_size: pageSize,
  };
}

function groupTrashItems(items: AssetTrashItem[]): AssetDateGroup[] {
  const dateGroups = new Map<string, Map<string, AssetTrashItem[]>>();

  for (const item of items) {
    const dateKey = formatShanghaiDate(item.deleted_at);
    const projects = dateGroups.get(dateKey) ?? new Map<string, AssetTrashItem[]>();
    const projectItems = projects.get(item.project_id) ?? [];
    projectItems.push(item);
    projects.set(item.project_id, projectItems);
    dateGroups.set(dateKey, projects);
  }

  return Array.from(dateGroups.entries())
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, projects]) => {
      const groupedProjects = Array.from(projects.values())
        .map((projectItems) => buildTrashProjectGroup(projectItems))
        .sort((a, b) => b.latest_created_at.localeCompare(a.latest_created_at));

      return {
        date,
        total: groupedProjects.reduce((sum, project) => sum + project.total, 0),
        project_count: groupedProjects.length,
        projects: groupedProjects,
      };
    });
}

function buildTrashProjectGroup(items: AssetTrashItem[]): AssetProjectGroup {
  const firstItem = items[0];
  const categories: Record<AssetLibraryCategory, AssetTrashItem[]> = {
    character: [],
    prop: [],
    scene: [],
  };

  for (const item of [...items].sort((a, b) => b.deleted_at.localeCompare(a.deleted_at))) {
    categories[item.category].push(item);
  }

  return {
    project_id: firstItem.project_id,
    project_title: firstItem.project_title,
    project_status: firstItem.project_status,
    project_deleted_at: firstItem.project_deleted_at ?? null,
    is_project_in_trash: Boolean(firstItem.project_deleted_at) || firstItem.project_status === "archived",
    total: items.length,
    latest_created_at: [...items]
      .map((item) => item.created_at || item.deleted_at)
      .sort((a, b) => b.localeCompare(a))[0] ?? firstItem.deleted_at,
    categories,
  };
}

function normalizeTrashItem(item: AssetTrashItem): AssetTrashItem {
  const prompt = item.prompt?.trim() || "";
  const promptSummary = item.prompt_summary?.trim() || prompt || "暂无 prompt 摘要";

  return {
    ...item,
    created_at: item.created_at || item.deleted_at,
    prompt,
    prompt_summary: promptSummary,
    quality_status: item.quality_status ?? null,
    thumbnail_url: item.thumbnail_url ?? null,
    project_deleted_at: item.project_deleted_at ?? null,
    purge_after: item.purge_after ?? null,
  };
}

export function useAssetTrash(filters: AssetLibraryFilters) {
  const [page, setPage] = useState(DEFAULT_PAGE);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [data, setData] = useState<AssetTrashResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => toQuery(filters, page, pageSize), [filters, page, pageSize]);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await listAssetTrash(query);
      const totalPages = Math.max(DEFAULT_PAGE, Math.ceil(response.total / pageSize));
      if ((response.total === 0 && page !== DEFAULT_PAGE) || (response.total > 0 && page > totalPages)) {
        setPage(response.total === 0 ? DEFAULT_PAGE : totalPages);
        return;
      }
      setData({
        ...response,
        items: response.items.map(normalizeTrashItem),
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "加载回收站失败");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, query]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void refresh();
    }, 0);

    return () => window.clearTimeout(handle);
  }, [refresh]);

  const restoreAsset = useCallback(
    async (assetId: string): Promise<AssetOperationResult> => {
      const result = await restoreImageAsset(assetId);
      await refresh();
      return result;
    },
    [refresh]
  );

  const batchRestoreAssets = useCallback(
    async (assetIds: string[]): Promise<AssetMutationSummary> => {
      const result = await batchRestoreImageAssets(assetIds);
      await refresh();
      return result;
    },
    [refresh]
  );

  const permanentDeleteAsset = useCallback(
    async (assetId: string): Promise<AssetOperationResult> => {
      const result = await permanentDeleteImageAsset(assetId);
      await refresh();
      return result;
    },
    [refresh]
  );

  const batchPermanentDeleteAssets = useCallback(
    async (assetIds: string[]): Promise<AssetMutationSummary> => {
      const result = await batchPermanentDeleteImageAssets(assetIds);
      await refresh();
      return result;
    },
    [refresh]
  );

  return {
    data,
    groups: data ? groupTrashItems(data.items) : [],
    page,
    pageSize,
    setPage,
    previousPage: () => setPage((current) => Math.max(DEFAULT_PAGE, current - 1)),
    nextPage: () => setPage((current) => current + 1),
    resetPage: () => setPage(DEFAULT_PAGE),
    hasPreviousPage: page > DEFAULT_PAGE,
    hasNextPage: data ? page * pageSize < data.total : false,
    totalPages: data ? Math.max(DEFAULT_PAGE, Math.ceil(data.total / pageSize)) : DEFAULT_PAGE,
    loading,
    error,
    refresh,
    restoreAsset,
    batchRestoreAssets,
    permanentDeleteAsset,
    batchPermanentDeleteAssets,
  };
}
