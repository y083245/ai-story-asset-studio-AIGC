"use client"

import * as React from "react"
import { Wrench, GitBranch, Lock, Unlock } from "lucide-react"

import { cn } from "@/lib/utils"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import type { PropResponse } from "@/shared/types"

interface PropDetailProps {
  prop: PropResponse
  open: boolean
  onClose: () => void
}

function PropDetail({ prop, open, onClose }: PropDetailProps) {
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
            {prop.name}
            {prop.is_locked && (
              <Lock className="size-4 text-amber-400" />
            )}
          </DialogTitle>
          <DialogDescription className="text-neutral-400">
            道具详情
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Description */}
          <div>
            <h4 className="text-sm font-medium text-neutral-400 mb-1.5">
              描述
            </h4>
            <p className="text-sm text-neutral-200 leading-relaxed">
              {prop.description || "暂无描述"}
            </p>
          </div>

          {/* Function */}
          <div>
            <h4 className="text-sm font-medium text-neutral-400 mb-1.5 flex items-center gap-1.5">
              <Wrench className="size-3.5" />
              功能
            </h4>
            <p className="text-sm text-neutral-200">
              {prop.function || "未指定功能"}
            </p>
          </div>

          {/* State timeline visualization */}
          <div>
            <h4 className="text-sm font-medium text-neutral-400 mb-3 flex items-center gap-1.5">
              <GitBranch className="size-3.5" />
              状态时间线
            </h4>
            {prop.state_timeline.length > 0 ? (
              <div className="relative pl-6">
                {/* Vertical line */}
                <div className="absolute left-2 top-1 bottom-1 w-px bg-neutral-700" />
                <div className="space-y-4">
                  {prop.state_timeline.map((state, i) => (
                    <div key={i} className="relative">
                      {/* Dot on the timeline */}
                      <div
                        className={cn(
                          "absolute -left-[1.125rem] top-1.5 size-2 rounded-full border-2",
                          i === 0
                            ? "bg-blue-400 border-blue-600"
                            : i === prop.state_timeline.length - 1
                              ? "bg-emerald-400 border-emerald-600"
                              : "bg-neutral-500 border-neutral-600"
                        )}
                      />
                      <div className="bg-neutral-800/50 rounded-lg border border-neutral-700 p-3">
                        <p className="text-xs text-neutral-500 mb-0.5">
                          阶段 {i + 1}
                        </p>
                        <p className="text-sm text-neutral-200">{state}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-neutral-500">无状态时间线数据</p>
            )}
          </div>

          {/* Lock status */}
          <div className="flex items-center gap-2 pt-1">
            {prop.is_locked ? (
              <>
                <Lock className="size-4 text-amber-400" />
                <span className="text-sm text-amber-400">
                  此道具已锁定，将保留在最终影片中
                </span>
              </>
            ) : (
              <>
                <Unlock className="size-4 text-neutral-500" />
                <span className="text-sm text-neutral-500">
                  此道具未锁定，AI 可对其进行调整
                </span>
              </>
            )}
          </div>

          {/* Timestamps */}
          <div className="border-t border-neutral-800 pt-3 flex gap-6 text-xs text-neutral-500">
            <span>
              创建: {new Date(prop.created_at).toLocaleString("zh-CN")}
            </span>
            <span>
              更新: {new Date(prop.updated_at).toLocaleString("zh-CN")}
            </span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export { PropDetail, type PropDetailProps }
