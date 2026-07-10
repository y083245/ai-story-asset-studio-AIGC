import type {
  AssetLibraryCategory,
  AssetLibraryItem,
  AssetProjectOption,
  AssetTrashItem,
  ImageAssetType,
} from "@/shared/api/image-assets";

export type AssetLibraryTab = "library" | "trash";

export interface AssetLibraryFilters {
  keyword: string;
  projectId: string;
  category: AssetLibraryCategory | "all";
  assetType: ImageAssetType | "all";
  startDate: string;
  endDate: string;
}

export interface AssetSelectionState {
  selectedIds: string[];
  selectedCount: number;
}

export interface AssetFeedback {
  tone: "success" | "error";
  message: string;
}

export type AssetToolbarProjectOption = AssetProjectOption;

export type AssetCardData = AssetLibraryItem | AssetTrashItem;
