"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  batchDeleteImageAssets,
  deleteImageAsset,
  listAssetLibrary,
  type AssetLibraryQuery,
  type AssetLibraryResponse,
  type AssetMutationSummary,
  type AssetOperationResult,
} from "@/shared/api/image-assets";
import type { AssetLibraryFilters } from "@/features/asset-library/types";

const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 50;

function toQuery(filters: AssetLibraryFilters, page: number, pageSize: number): AssetLibraryQuery {
  return {
    keyword: filters.keyword || undefined,
    project_id: filters.projectId || undefined,
    category: filters.category === "all" ? undefined : filters.category,
    asset_type: filters.assetType === "all" ? undefined : filters.assetType,
    date_from: filters.startDate || undefined,
    date_to: filters.endDate || undefined,
    page,
    page_size: pageSize,
  };
}

export function useAssetLibrary(filters: AssetLibraryFilters) {
  const [page, setPage] = useState(DEFAULT_PAGE);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [data, setData] = useState<AssetLibraryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => toQuery(filters, page, pageSize), [filters, page, pageSize]);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await listAssetLibrary(query);
      const totalPages = Math.max(DEFAULT_PAGE, Math.ceil(response.total / pageSize));
      if ((response.total === 0 && page !== DEFAULT_PAGE) || (response.total > 0 && page > totalPages)) {
        setPage(response.total === 0 ? DEFAULT_PAGE : totalPages);
        return;
      }
      setData(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "加载资产失败");
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

  const removeAsset = useCallback(
    async (assetId: string): Promise<AssetOperationResult> => {
      const result = await deleteImageAsset(assetId);
      await refresh();
      return result;
    },
    [refresh]
  );

  const batchRemoveAssets = useCallback(
    async (assetIds: string[]): Promise<AssetMutationSummary> => {
      const result = await batchDeleteImageAssets(assetIds);
      await refresh();
      return result;
    },
    [refresh]
  );

  return {
    data,
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
    removeAsset,
    batchRemoveAssets,
  };
}
