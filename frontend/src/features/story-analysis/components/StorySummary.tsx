"use client"

import {
  BookOpen,
  Swords,
  Heart,
  Globe,
  Clock,
  Palette,
} from "lucide-react"

import type { AnalysisResponse } from "@/shared/types"

interface StorySummaryProps {
  summary: AnalysisResponse
}

interface SummarySectionProps {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
}

function SummarySection({ icon, label, children }: SummarySectionProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-neutral-400">{icon}</span>
        <h4 className="text-xs font-medium uppercase tracking-wider text-neutral-400">
          {label}
        </h4>
      </div>
      <div className="pl-7 text-sm text-neutral-200 leading-relaxed">
        {children}
      </div>
    </div>
  )
}

function ColorSwatch({ color }: { color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className="size-5 rounded-full border border-neutral-600 shrink-0"
        style={{ backgroundColor: color }}
      />
      <span className="text-xs text-neutral-400 font-mono">{color}</span>
    </div>
  )
}

export function StorySummary({ summary }: StorySummaryProps) {
  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-800 p-5 space-y-5">
      {/* 故事梗概 */}
      <SummarySection icon={<BookOpen className="size-4" />} label="故事梗概">
        <p>{summary.story_summary}</p>
      </SummarySection>

      {/* 主要冲突 */}
      <SummarySection icon={<Swords className="size-4" />} label="主要冲突">
        <p>{summary.main_conflict}</p>
      </SummarySection>

      {/* 情感基调 */}
      <SummarySection icon={<Heart className="size-4" />} label="情感基调">
        <p>{summary.emotional_tone}</p>
      </SummarySection>

      {/* 世界观 */}
      <SummarySection icon={<Globe className="size-4" />} label="世界观">
        <p>{summary.world_setting}</p>
      </SummarySection>

      {/* 时代背景 */}
      <SummarySection icon={<Clock className="size-4" />} label="时代背景">
        <p>{summary.time_period}</p>
      </SummarySection>

      {/* 色彩方案 */}
      {summary.color_palette && summary.color_palette.length > 0 && (
        <SummarySection icon={<Palette className="size-4" />} label="色彩方案">
          <div className="flex flex-wrap gap-3">
            {summary.color_palette.map((color) => (
              <ColorSwatch key={color} color={color} />
            ))}
          </div>
        </SummarySection>
      )}

      {summary.composition_language && summary.composition_language.length > 0 && (
        <SummarySection icon={<Palette className="size-4" />} label="构图语言">
          <div className="flex flex-wrap gap-2">
            {summary.composition_language.map((item) => (
              <span
                key={item}
                className="inline-block rounded-md bg-neutral-700/50 px-2.5 py-1 text-xs text-neutral-300"
              >
                {item}
              </span>
            ))}
          </div>
        </SummarySection>
      )}
    </div>
  )
}
