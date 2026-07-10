"use client";

import { useMemo, useState } from "react";
import { ImageIcon, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AssetBulkActionBar } from "@/features/asset-library/components/AssetBulkActionBar";
import { AssetDateGroup } from "@/features/asset-library/components/AssetDateGroup";
import { AssetLibraryToolbar } from "@/features/asset-library/components/AssetLibraryToolbar";
import { AssetPreviewDialog } from "@/features/asset-library/components/AssetPreviewDialog";
import { useAssetLibrary } from "@/features/asset-library/hooks/useAssetLibrary";
import { useAssetTrash } from "@/features/asset-library/hooks/useAssetTrash";
import type { AssetCardData, AssetFeedback, AssetLibraryFilters, AssetLibraryTab } from "@/features/asset-library/types";
import { EmptyState } from "@/shared/ui/EmptyState";
import { ErrorState } from "@/shared/ui/ErrorState";
import { Loading } from "@/shared/ui/Loading";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Badge } from "@/components/ui/badge";

const INITIAL_FILTERS: AssetLibraryFilters = {
  keyword: "",
  projectId: "",
  category: "all",
  assetType: "all",
  startDate: "",
  endDate: "",
};

function hasActiveFilters(filters: AssetLibraryFilters): boolean {
  return Object.entries(filters).some(([, value]) => value !== "" && value !== "all");
}

function PaginationBar({
  page,
  totalPages,
  hasPreviousPage,
  hasNextPage,
  onPrevious,
  onNext,
  previousLabel,
  nextLabel,
}: {
  page: number;
  totalPages: number;
  hasPreviousPage: boolean;
  hasNextPage: boolean;
  onPrevious: () => void;
  onNext: () => void;
  previousLabel: string;
  nextLabel: string;
}) {
  return (
    <div className="flex items-center justify-end gap-2 rounded-lg border border-neutral-800 bg-neutral-900/60 px-3 py-2">
      <span className="min-w-20 text-right text-xs text-neutral-400">
        第 {page} / {totalPages} 页
      </span>
      <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onPrevious} disabled={!hasPreviousPage} aria-label={previousLabel}>
        上一页
      </Button>
      <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onNext} disabled={!hasNextPage} aria-label={nextLabel}>
        下一页
      </Button>
    </div>
  );
}

export default function AssetLibraryPage() {
  const [tab, setTab] = useState<AssetLibraryTab>("library");
  const [filters, setFilters] = useState<AssetLibraryFilters>(INITIAL_FILTERS);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [previewAsset, setPreviewAsset] = useState<AssetCardData | null>(null);
  const [feedback, setFeedback] = useState<AssetFeedback | null>(null);

  const library = useAssetLibrary(filters);
  const trash = useAssetTrash(filters);

  const currentProjects = useMemo(() => {
    if (tab === "library") {
      return library.data?.available_projects ?? [];
    }
    return trash.data?.available_projects ?? [];
  }, [library.data?.available_projects, tab, trash.data?.available_projects]);

  function toggleSelect(assetId: string) {
    setSelectedIds((items) => (items.includes(assetId) ? items.filter((item) => item !== assetId) : [...items, assetId]));
  }

  function clearSelection() {
    setSelectedIds([]);
  }

  function handleFiltersChange(nextFilters: AssetLibraryFilters) {
    clearSelection();
    setFeedback(null);
    library.resetPage();
    trash.resetPage();
    setFilters(nextFilters);
  }

  function handleLibraryPreviousPage() {
    clearSelection();
    library.previousPage();
  }

  function handleLibraryNextPage() {
    clearSelection();
    library.nextPage();
  }

  function handleTrashPreviousPage() {
    clearSelection();
    trash.previousPage();
  }

  function handleTrashNextPage() {
    clearSelection();
    trash.nextPage();
  }

  async function handleDelete(asset: AssetCardData) {
    if (!window.confirm("确认删除这张图片？\n删除后图片将进入回收站，30 天内可以恢复；超过 30 天后将自动永久删除。")) return;
    const result = await library.removeAsset(asset.asset_id);
    clearSelection();
    setFeedback({
      tone: result.status === "success" ? "success" : "error",
      message: result.message,
    });
  }

  async function handleBatchDelete() {
    if (!window.confirm("确认删除选中的图片？\n选中的图片将进入回收站，30 天内可以恢复；超过 30 天后将自动永久删除。")) return;
    const result = await library.batchRemoveAssets(selectedIds);
    clearSelection();
    setFeedback(
      result.failure_count > 0
        ? {
            tone: "error",
            message: `失败 ${result.failure_count} 张：${result.first_error?.message || "未知错误"}`,
          }
        : { tone: "success", message: `已删除 ${result.success_count} 张图片` }
    );
  }

  async function handleRestore(asset: AssetCardData) {
    if (!window.confirm("确认恢复这张图片？\n恢复后图片将回到原项目资产库。")) return;
    const result = await trash.restoreAsset(asset.asset_id);
    clearSelection();
    setFeedback({
      tone: result.status === "success" ? "success" : "error",
      message: result.message,
    });
  }

  async function handleBatchRestore() {
    if (!window.confirm("确认恢复选中的图片？\n恢复后图片将回到原项目资产库。")) return;
    const result = await trash.batchRestoreAssets(selectedIds);
    clearSelection();
    setFeedback(
      result.failure_count > 0
        ? {
            tone: "error",
            message: `失败 ${result.failure_count} 张：${result.first_error?.message || "未知错误"}`,
          }
        : { tone: "success", message: `已恢复 ${result.success_count} 张图片` }
    );
  }

  async function handlePermanentDelete(asset: AssetCardData) {
    if (!window.confirm("确认永久删除？\n永久删除后将同时删除图片文件和数据库记录，无法找回。")) return;
    const result = await trash.permanentDeleteAsset(asset.asset_id);
    clearSelection();
    setFeedback({
      tone: result.status === "success" ? "success" : "error",
      message: result.message,
    });
  }

  async function handleBatchPermanentDelete() {
    if (!window.confirm("确认永久删除？\n永久删除后将同时删除图片文件和数据库记录，无法找回。")) return;
    const result = await trash.batchPermanentDeleteAssets(selectedIds);
    clearSelection();
    setFeedback(
      result.failure_count > 0
        ? {
            tone: "error",
            message: `失败 ${result.failure_count} 张：${result.first_error?.message || "未知错误"}`,
          }
        : { tone: "success", message: `已永久删除 ${result.success_count} 张图片` }
    );
  }

  return (
    <main className="min-h-screen bg-neutral-950 p-6 text-white md:p-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <PageHeader
          title="资产管理"
          description="按日期、项目和资产类别集中管理已生成图片。"
          actions={
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="border-neutral-700 text-neutral-300">
                {tab === "library" ? `${library.data?.total ?? 0} 张图片` : `${trash.data?.total ?? 0} 张回收站图片`}
              </Badge>
              <Button variant="outline" size="sm" onClick={() => void (tab === "library" ? library.refresh() : trash.refresh())} aria-label={tab === "library" ? "刷新全部图片" : "刷新回收站"}>
                <RefreshCw className="size-3.5" />
                刷新
              </Button>
            </div>
          }
        />

        <Tabs
          value={tab}
          onValueChange={(value) => {
            setTab(value as AssetLibraryTab);
            clearSelection();
            setFeedback(null);
            library.resetPage();
            trash.resetPage();
          }}
        >
          <TabsList>
            <TabsTrigger value="library">全部图片</TabsTrigger>
            <TabsTrigger value="trash">回收站</TabsTrigger>
          </TabsList>

          <AssetLibraryToolbar filters={filters} onChange={handleFiltersChange} projectOptions={currentProjects} />

          {feedback ? (
            <div className={`rounded-lg border px-4 py-3 text-sm ${feedback.tone === "error" ? "border-red-900 bg-red-950/30 text-red-200" : "border-emerald-900 bg-emerald-950/30 text-emerald-200"}`}>
              {feedback.message}
            </div>
          ) : null}

          <TabsContent value="library" className="space-y-4">
            {library.loading ? <Loading message="加载资产图..." /> : null}
            {library.error ? <ErrorState message={library.error} retry={() => void library.refresh()} /> : null}
            {!library.loading && !library.error ? (
              <>
                {library.data && library.data.groups.length > 0 ? (
                  <>
                    {library.data.groups.map((group) => (
                      <AssetDateGroup
                        key={group.date}
                        group={group}
                        tab="library"
                        selectedIds={selectedIds}
                        onToggleSelect={toggleSelect}
                        onPreview={setPreviewAsset}
                        onDelete={(asset) => void handleDelete(asset)}
                        onRestore={() => undefined}
                        onPermanentDelete={() => undefined}
                      />
                    ))}
                    <PaginationBar
                      page={library.page}
                      totalPages={library.totalPages}
                      hasPreviousPage={library.hasPreviousPage}
                      hasNextPage={library.hasNextPage}
                      onPrevious={handleLibraryPreviousPage}
                      onNext={handleLibraryNextPage}
                      previousLabel="全部图片上一页"
                      nextLabel="全部图片下一页"
                    />
                  </>
                ) : (
                  <EmptyState
                    icon={<ImageIcon className="size-8" />}
                    title={hasActiveFilters(filters) ? "没有符合条件的图片" : "暂无资产图"}
                  />
                )}
              </>
            ) : null}
          </TabsContent>

          <TabsContent value="trash" className="space-y-4">
            {trash.loading ? <Loading message="加载回收站..." /> : null}
            {trash.error ? <ErrorState message={trash.error} retry={() => void trash.refresh()} /> : null}
            {!trash.loading && !trash.error ? (
              <>
                {trash.groups.length > 0 ? (
                  <>
                    {trash.groups.map((group) => (
                      <AssetDateGroup
                        key={group.date}
                        group={group}
                        tab="trash"
                        selectedIds={selectedIds}
                        onToggleSelect={toggleSelect}
                        onPreview={setPreviewAsset}
                        onDelete={() => undefined}
                        onRestore={(item) => void handleRestore(item)}
                        onPermanentDelete={(item) => void handlePermanentDelete(item)}
                      />
                    ))}
                    <PaginationBar
                      page={trash.page}
                      totalPages={trash.totalPages}
                      hasPreviousPage={trash.hasPreviousPage}
                      hasNextPage={trash.hasNextPage}
                      onPrevious={handleTrashPreviousPage}
                      onNext={handleTrashNextPage}
                      previousLabel="回收站上一页"
                      nextLabel="回收站下一页"
                    />
                  </>
                ) : (
                  <EmptyState
                    icon={<ImageIcon className="size-8" />}
                    title="回收站暂无图片"
                  />
                )}
              </>
            ) : null}
          </TabsContent>
        </Tabs>

        <AssetBulkActionBar
          tab={tab}
          selectedCount={selectedIds.length}
          onClear={clearSelection}
          onDelete={() => void handleBatchDelete()}
          onRestore={() => void handleBatchRestore()}
          onPermanentDelete={() => void handleBatchPermanentDelete()}
        />

        <AssetPreviewDialog asset={previewAsset} open={Boolean(previewAsset)} onOpenChange={(open) => !open && setPreviewAsset(null)} />
      </div>
    </main>
  );
}
