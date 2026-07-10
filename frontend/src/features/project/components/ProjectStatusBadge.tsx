"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

import type { ProjectStatus } from "@/shared/types"

interface ProjectStatusBadgeProps {
  status: ProjectStatus
  className?: string
}

const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: "草稿",
  uploaded: "已上传",
  novel_uploaded: "已上传",
  analyzing: "分析中",
  running: "运行中",
  analysis_confirmed: "已确认",
  generating_assets: "生成资产",
  generating_images: "生成图片",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  archived: "已归档",
}

function getStatusColors(status: ProjectStatus): string {
  switch (status) {
    // Completed
    case "completed":
      return "bg-green-500/10 text-green-400 border-green-500/30"

    // Failed
    case "failed":
      return "bg-red-500/10 text-red-400 border-red-500/30"

    // Archived
    case "archived":
    case "cancelled":
      return "bg-neutral-500/10 text-neutral-400 border-neutral-500/30"

    // Draft
    case "draft":
    case "uploaded":
    case "novel_uploaded":
      return "bg-neutral-500/10 text-neutral-300 border-neutral-500/30"

    // Active generating / analysis states — blue
    case "analyzing":
    case "running":
    case "analysis_confirmed":
    case "generating_assets":
    case "generating_images":
      return "bg-blue-500/10 text-blue-400 border-blue-500/30"

    default:
      return "bg-neutral-500/10 text-neutral-300 border-neutral-500/30"
  }
}

export function ProjectStatusBadge({
  status,
  className,
}: ProjectStatusBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-xs font-medium",
        getStatusColors(status),
        className
      )}
    >
      {STATUS_LABELS[status]}
    </Badge>
  )
}
