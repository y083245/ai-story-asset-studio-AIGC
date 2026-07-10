"use client";

import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import type { AssetLibraryFilters, AssetToolbarProjectOption } from "@/features/asset-library/types";
import { getAssetTypeOptionsByCategory } from "@/shared/api/image-assets";

interface AssetLibraryToolbarProps {
  filters: AssetLibraryFilters;
  onChange: (next: AssetLibraryFilters) => void;
  projectOptions: AssetToolbarProjectOption[];
}

const CATEGORY_OPTIONS = [
  { value: "all", label: "全部分类" },
  { value: "character", label: "角色" },
  { value: "prop", label: "道具" },
  { value: "scene", label: "场景" },
] as const;

const ASSET_TYPE_OPTIONS = [
  { value: "character_bible_sheet", label: "角色设定板" },
  { value: "character_front", label: "角色正面图" },
  { value: "character_turnaround", label: "角色转身图" },
  { value: "character_expression", label: "角色表情图" },
  { value: "prop_product", label: "单一道具图" },
  { value: "prop_usage", label: "道具使用图" },
  { value: "scene_empty", label: "纯场景图" },
  { value: "scene_with_atmosphere", label: "氛围场景图" },
] as const;

export function AssetLibraryToolbar({
  filters,
  onChange,
  projectOptions,
}: AssetLibraryToolbarProps) {
  const validAssetTypes = getAssetTypeOptionsByCategory(filters.category);
  const assetTypeOptions = ASSET_TYPE_OPTIONS.filter((option) => validAssetTypes.includes(option.value));

  function handleCategoryChange(nextCategory: AssetLibraryFilters["category"]) {
    const nextValidAssetTypes = getAssetTypeOptionsByCategory(nextCategory);
    const nextAssetType =
      filters.assetType !== "all" && !nextValidAssetTypes.includes(filters.assetType) ? "all" : filters.assetType;
    onChange({ ...filters, category: nextCategory, assetType: nextAssetType });
  }

  return (
    <div className="grid gap-3 rounded-xl border border-neutral-800 bg-neutral-900/80 p-4 md:grid-cols-2 xl:grid-cols-5">
      <label className="space-y-1.5">
        <span className="text-xs text-neutral-400">关键词</span>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-neutral-500" />
          <Input
            aria-label="关键词搜索"
            value={filters.keyword}
            onChange={(event) => onChange({ ...filters, keyword: event.target.value })}
            placeholder="项目名 / 对象名 / related_id"
            className="pl-8"
          />
        </div>
      </label>

      <div className="space-y-1.5">
        <span className="text-xs text-neutral-400">项目</span>
        <select
          aria-label="项目筛选"
          value={filters.projectId || "__all__"}
          onChange={(event) => onChange({ ...filters, projectId: event.target.value === "__all__" ? "" : event.target.value })}
          className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm text-white outline-none focus-visible:border-ring"
        >
          <option value="__all__">全部项目</option>
          {projectOptions.map((project) => (
            <option key={project.project_id} value={project.project_id}>
              {project.project_title}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <span className="text-xs text-neutral-400">分类</span>
        <select
          aria-label="分类筛选"
          value={filters.category}
          onChange={(event) => handleCategoryChange(event.target.value as AssetLibraryFilters["category"])}
          className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm text-white outline-none focus-visible:border-ring"
        >
          {CATEGORY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <span className="text-xs text-neutral-400">资产类型</span>
        <select
          aria-label="资产类型筛选"
          value={filters.assetType}
          onChange={(event) => onChange({ ...filters, assetType: event.target.value as AssetLibraryFilters["assetType"] })}
          className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm text-white outline-none focus-visible:border-ring"
        >
          <option value="all">全部类型</option>
          {assetTypeOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="space-y-1.5">
          <span className="text-xs text-neutral-400">开始日期</span>
          <Input
            aria-label="开始日期"
            type="date"
            value={filters.startDate}
            onChange={(event) => onChange({ ...filters, startDate: event.target.value })}
          />
        </label>
        <label className="space-y-1.5">
          <span className="text-xs text-neutral-400">结束日期</span>
          <Input
            aria-label="结束日期"
            type="date"
            value={filters.endDate}
            onChange={(event) => onChange({ ...filters, endDate: event.target.value })}
          />
        </label>
      </div>
    </div>
  );
}
