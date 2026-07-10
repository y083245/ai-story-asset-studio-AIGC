"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Modal } from "@/shared/ui/Modal";
import type { AssetCardData } from "@/features/asset-library/types";
import { resolveAssetUrl } from "@/shared/api/asset-url";

interface AssetPreviewDialogProps {
  asset: AssetCardData | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AssetPreviewDialog({ asset, open, onOpenChange }: AssetPreviewDialogProps) {
  const [expanded, setExpanded] = useState(false);

  if (!asset) return null;

  const imageUrl = resolveAssetUrl(asset.asset_url);

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next) setExpanded(false);
        onOpenChange(next);
      }}
      title={asset.display_name}
      description={`${asset.project_title} · ${asset.model_name}`}
      footer={null}
    >
      <div className="space-y-4">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={asset.display_name}
            className="max-h-[60vh] w-full rounded-lg border border-neutral-800 object-contain"
          />
        ) : (
          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-6 text-center text-sm text-neutral-400">
            图片不可预览
          </div>
        )}

        <div className="grid gap-2 text-sm text-neutral-300 md:grid-cols-2">
          <div>分类：{asset.category}</div>
          <div>类型：{asset.asset_type_label}</div>
          <div>对象：{asset.related_name || asset.related_id || "未关联"}</div>
          <div>状态：{asset.status}</div>
        </div>

        <section className="space-y-2">
          <h3 className="text-sm font-semibold text-white">Prompt 摘要</h3>
          <p className="rounded-lg border border-neutral-800 bg-neutral-900 p-3 text-sm text-neutral-300">
            {asset.prompt_summary}
          </p>
          <Button variant="outline" size="xs" onClick={() => setExpanded((value) => !value)}>
            {expanded ? "收起全文" : "展开全文"}
          </Button>
          {expanded ? (
            <pre className="overflow-x-auto rounded-lg border border-neutral-800 bg-neutral-950 p-3 text-xs text-neutral-300 whitespace-pre-wrap">
              {asset.prompt}
            </pre>
          ) : null}
        </section>
      </div>
    </Modal>
  );
}
