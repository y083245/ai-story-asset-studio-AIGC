"use client"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Sparkles, Target } from "lucide-react"

interface GenreDisplayProps {
  genre: string
  visualStyle: string
  confidence: number
}

function getConfidenceColor(confidence: number): string {
  const normalized = clampConfidence(confidence)
  if (normalized > 0.75) {
    return "bg-green-500/10 text-green-400 border-green-500/30"
  }
  if (normalized >= 0.5) {
    return "bg-yellow-500/10 text-yellow-400 border-yellow-500/30"
  }
  return "bg-red-500/10 text-red-400 border-red-500/30"
}

function getConfidenceLabel(confidence: number): string {
  const normalized = clampConfidence(confidence)
  if (normalized > 0.75) return "高"
  if (normalized >= 0.5) return "中"
  return "低"
}

function clampConfidence(confidence: number): number {
  if (!Number.isFinite(confidence)) return 0
  return Math.min(Math.max(confidence, 0), 1)
}

export function GenreDisplay({
  genre,
  visualStyle,
  confidence,
}: GenreDisplayProps) {
  const normalizedConfidence = clampConfidence(confidence)
  const confidencePercent = Math.round(normalizedConfidence * 100)

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-800 p-5 space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-neutral-400 uppercase tracking-wider">
            <Target className="size-3.5" />
            题材类型
          </div>
          <p className="text-base font-semibold text-white">{genre}</p>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-neutral-400 uppercase tracking-wider">
            <Sparkles className="size-3.5" />
            视觉风格
          </div>
          <p className="text-base font-semibold text-white">{visualStyle}</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-xs text-neutral-400">AI 置信度</span>
        <Badge
          variant="outline"
          className={cn(
            "text-xs font-medium",
            getConfidenceColor(normalizedConfidence)
          )}
        >
          {confidencePercent}% — {getConfidenceLabel(normalizedConfidence)}
        </Badge>

        <div className="ml-auto flex-1 max-w-[120px]">
          <div className="h-1.5 rounded-full bg-neutral-700 overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                normalizedConfidence > 0.75
                  ? "bg-green-500"
                  : normalizedConfidence >= 0.5
                    ? "bg-yellow-500"
                    : "bg-red-500"
              )}
              style={{ width: `${confidencePercent}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
