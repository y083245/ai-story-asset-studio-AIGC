"use client"

import * as React from "react"
import { Layers } from "lucide-react"

import { cn } from "@/lib/utils"

interface StageIndicatorProps {
  currentStage: string
  stageIndex: number
  totalStages: number
}

function StageIndicator({
  currentStage,
  stageIndex,
  totalStages,
}: StageIndicatorProps) {
  return (
    <div
      data-slot="stage-indicator"
      className="flex flex-col items-center gap-3"
    >
      {/* Stage counter */}
      <div className="flex items-center gap-2">
        <Layers className="size-4 text-neutral-500" />
        <span className="text-sm text-neutral-400">
          阶段 {stageIndex} / {totalStages}
        </span>
      </div>

      {/* Current stage name (large, prominent) */}
      <h2 className="text-2xl font-bold text-white tracking-tight text-center">
        {currentStage}
      </h2>

      {/* Mini step indicators */}
      <div className="flex items-center gap-1.5" role="progressbar">
        {Array.from({ length: totalStages }, (_, i) => {
          const isCompleted = i < stageIndex - 1
          const isCurrent = i === stageIndex - 1
          const isPending = i > stageIndex - 1

          return (
            <div
              key={i}
              className={cn(
                "h-1.5 rounded-full transition-all duration-500",
                isCompleted && "w-8 bg-blue-500/60",
                isCurrent && "w-10 bg-blue-400 shadow-lg shadow-blue-500/30",
                isPending && "w-6 bg-neutral-700"
              )}
              title={`阶段 ${i + 1}`}
            />
          )
        })}
      </div>
    </div>
  )
}

export { StageIndicator, type StageIndicatorProps }
