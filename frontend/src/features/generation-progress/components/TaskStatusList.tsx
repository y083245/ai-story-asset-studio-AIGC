"use client"

import * as React from "react"
import {
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  RefreshCw,
  AlertTriangle,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { Progress } from "@/components/ui/progress"
import type { TaskStatus } from "@/shared/types"

interface TaskStatusListProps {
  tasks: TaskStatus[]
}

const statusIconMap: Record<
  TaskStatus["state"],
  { Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>; className: string }
> = {
  pending: { Icon: Clock, className: "text-neutral-500" },
  running: { Icon: Loader2, className: "text-blue-400 animate-spin" },
  success: { Icon: CheckCircle2, className: "text-emerald-400" },
  failed: { Icon: XCircle, className: "text-red-400" },
  retrying: { Icon: RefreshCw, className: "text-amber-400 animate-spin" },
  needs_review: { Icon: AlertTriangle, className: "text-orange-400" },
}

const statusLabelMap: Record<TaskStatus["state"], string> = {
  pending: "待执行",
  running: "执行中",
  success: "成功",
  failed: "失败",
  retrying: "重试中",
  needs_review: "需审核",
}

function TaskStatusList({ tasks }: TaskStatusListProps) {
  if (tasks.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-neutral-500">暂无任务</p>
      </div>
    )
  }

  return (
    <div data-slot="task-status-list" className="space-y-2">
      {tasks.map((task) => {
        const { Icon, className: iconClassName } = statusIconMap[task.state]
        const label = statusLabelMap[task.state]
        const isError = task.state === "failed"
        const isWarning = task.state === "needs_review"

        return (
          <div
            key={task.task_id}
            data-slot="task-status-item"
            data-state={task.state}
            className={cn(
              "rounded-lg border p-3 transition-colors",
              "bg-neutral-800/50 border-neutral-700",
              isError && "bg-red-950/20 border-red-900/50",
              isWarning && "bg-orange-950/20 border-orange-900/50"
            )}
          >
            <div className="flex items-start gap-3">
              {/* Status icon */}
              <Icon
                className={cn("size-4 mt-0.5 shrink-0", iconClassName)}
              />

              <div className="flex-1 min-w-0">
                {/* Task name + status label */}
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-sm font-medium text-white truncate">
                    {task.name}
                  </span>
                  <span
                    className={cn(
                      "text-[10px] font-medium px-1.5 py-0.5 rounded-md shrink-0",
                      isError && "bg-red-950/50 text-red-400",
                      isWarning && "bg-orange-950/50 text-orange-400",
                      !isError &&
                        !isWarning &&
                        "bg-neutral-700/50 text-neutral-400"
                    )}
                  >
                    {label}
                  </span>

                  {/* Retry count */}
                  {task.retry_count > 0 && (
                    <span className="text-[10px] text-amber-400 shrink-0">
                      重试 {task.retry_count}/{task.max_retries}
                    </span>
                  )}
                </div>

                {/* Progress bar (small) */}
                <Progress
                  value={task.progress}
                  className="h-1 mb-1.5 bg-neutral-700"
                />

                {/* Error message */}
                {task.error_message && (
                  <p className="text-xs text-red-400 mt-1 leading-relaxed">
                    {task.error_message}
                  </p>
                )}

                {/* Timestamps */}
                {(task.started_at || task.completed_at) && (
                  <div className="flex gap-4 mt-1">
                    {task.started_at && (
                      <span className="text-[10px] text-neutral-500">
                        开始:{" "}
                        {new Date(task.started_at).toLocaleTimeString("zh-CN")}
                      </span>
                    )}
                    {task.completed_at && (
                      <span className="text-[10px] text-neutral-500">
                        完成:{" "}
                        {new Date(task.completed_at).toLocaleTimeString(
                          "zh-CN"
                        )}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export { TaskStatusList, type TaskStatusListProps }
