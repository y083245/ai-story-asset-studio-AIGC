"use client"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Loading } from "@/shared/ui/Loading"
import { Check, Tag } from "lucide-react"

import type { StyleCandidate } from "@/shared/types"

interface StyleCandidateSelectorProps {
  candidates: StyleCandidate[]
  selectedStyle?: string
  onSelect: (styleName: string) => void
  loading?: boolean
}

function clampConfidence(confidence: number): number {
  if (!Number.isFinite(confidence)) return 0
  return Math.min(Math.max(confidence, 0), 1)
}

export function StyleCandidateSelector({
  candidates,
  selectedStyle,
  onSelect,
  loading = false,
}: StyleCandidateSelectorProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-neutral-700 bg-neutral-800 p-8">
        <Loading message="加载风格候选..." />
      </div>
    )
  }

  if (!candidates || candidates.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-700 bg-neutral-800 p-6 text-center">
        <p className="text-sm text-neutral-400">暂无风格候选</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-neutral-400">
        AI 对风格判断的置信度较低，请从以下候选中选择最合适的视觉风格：
      </p>

      <div className="grid gap-3">
        {candidates.map((candidate) => {
          const isSelected = selectedStyle === candidate.style_name
          const confidence = clampConfidence(candidate.confidence)
          const confidencePercent = Math.round(confidence * 100)

          return (
            <button
              key={candidate.style_name}
              type="button"
              onClick={() => onSelect(candidate.style_name)}
              className={cn(
                "relative w-full rounded-lg border p-4 text-left",
                "transition-all duration-200",
                "bg-neutral-800 hover:bg-neutral-700/70",
                isSelected
                  ? "border-blue-500 ring-1 ring-blue-500/50 bg-blue-500/5"
                  : "border-neutral-700"
              )}
            >
              {isSelected && (
                <div className="absolute top-2 right-2 flex size-5 items-center justify-center rounded-full bg-blue-500">
                  <Check className="size-3 text-white" />
                </div>
              )}

              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1.5 flex-1">
                  <h4 className="text-sm font-semibold text-white">
                    {candidate.style_name}
                  </h4>
                  <p className="text-sm text-neutral-400 leading-relaxed">
                    {candidate.description}
                  </p>
                </div>

                <Badge
                  variant="outline"
                  className={cn(
                    "shrink-0 text-xs",
                    confidence > 0.6
                      ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/30"
                      : "bg-red-500/10 text-red-400 border-red-500/30"
                  )}
                >
                  {confidencePercent}%
                </Badge>
              </div>

              {candidate.example_keywords &&
                candidate.example_keywords.length > 0 && (
                  <div className="mt-2.5 flex items-center gap-1.5 flex-wrap">
                    <Tag className="size-3 text-neutral-500" />
                    {candidate.example_keywords.map((keyword) => (
                      <span
                        key={keyword}
                        className="inline-block rounded bg-neutral-700/50 px-2 py-0.5 text-xs text-neutral-400"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
