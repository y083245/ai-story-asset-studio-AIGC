"use client"

import * as React from "react"
import { Clock, Smile, MapPin, Anchor, Lock, Unlock } from "lucide-react"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import type { SceneResponse } from "@/shared/types"

interface SceneDetailProps {
  scene: SceneResponse
  open: boolean
  onClose: () => void
}

function SceneDetail({ scene, open, onClose }: SceneDetailProps) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        className={cn(
          "bg-neutral-950 border-neutral-700 text-white",
          "max-w-lg max-h-[85vh] overflow-y-auto"
        )}
      >
        <DialogHeader>
          <DialogTitle className="text-white text-lg flex items-center gap-2">
            {scene.name}
            {scene.is_locked && (
              <Lock className="size-4 text-amber-400" />
            )}
          </DialogTitle>
          <DialogDescription className="text-neutral-400">
            场景详情
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Description */}
          <div>
            <h4 className="text-sm font-medium text-neutral-400 mb-1.5">
              描述
            </h4>
            <p className="text-sm text-neutral-200 leading-relaxed">
              {scene.description || "暂无描述"}
            </p>
          </div>

          {/* Metadata grid */}
          <div className="grid grid-cols-2 gap-4">
            {scene.time_period && (
              <div className="flex items-start gap-2">
                <Clock className="size-4 text-neutral-500 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs text-neutral-500">时代背景</p>
                  <p className="text-sm text-neutral-200">{scene.time_period}</p>
                </div>
              </div>
            )}
            {scene.mood && (
              <div className="flex items-start gap-2">
                <Smile className="size-4 text-neutral-500 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs text-neutral-500">氛围</p>
                  <p className="text-sm text-neutral-200">{scene.mood}</p>
                </div>
              </div>
            )}
            {scene.location && (
              <div className="flex items-start gap-2">
                <MapPin className="size-4 text-neutral-500 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs text-neutral-500">地点</p>
                  <p className="text-sm text-neutral-200">{scene.location}</p>
                </div>
              </div>
            )}
          </div>

          {/* Fixed anchors */}
          <div>
            <h4 className="text-sm font-medium text-neutral-400 mb-1.5 flex items-center gap-1.5">
              <Anchor className="size-3.5" />
              固定锚点
            </h4>
            {scene.fixed_anchors.length > 0 ? (
              <ul className="flex flex-wrap gap-1.5">
                {scene.fixed_anchors.map((anchor, i) => (
                  <li key={i}>
                    <Badge
                      variant="outline"
                      className="border-neutral-600 text-neutral-300 bg-neutral-800/50"
                    >
                      {anchor}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-neutral-500">无固定锚点</p>
            )}
          </div>

          {/* Lock status */}
          <div className="flex items-center gap-2 pt-1">
            {scene.is_locked ? (
              <>
                <Lock className="size-4 text-amber-400" />
                <span className="text-sm text-amber-400">
                  此场景已锁定，生成资产图时会保持当前设定
                </span>
              </>
            ) : (
              <>
                <Unlock className="size-4 text-neutral-500" />
                <span className="text-sm text-neutral-500">
                  此场景未锁定，AI 可对其进行调整
                </span>
              </>
            )}
          </div>

          {/* Timestamps */}
          <div className="border-t border-neutral-800 pt-3 flex gap-6 text-xs text-neutral-500">
            <span>
              创建: {new Date(scene.created_at).toLocaleString("zh-CN")}
            </span>
            <span>
              更新: {new Date(scene.updated_at).toLocaleString("zh-CN")}
            </span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export { SceneDetail, type SceneDetailProps }
