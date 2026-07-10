"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

interface ProgressBarProps {
  value: number
  label?: string
  className?: string
}

function ProgressBar({ value, label, className }: ProgressBarProps) {
  // Clamp value between 0-100
  const clampedValue = Math.min(100, Math.max(0, value))
  const percent = Math.round(clampedValue)

  // Determine color based on progress
  const getColor = (v: number) => {
    if (v >= 100) return { text: "text-emerald-400", bar: "bg-emerald-500", glow: "shadow-emerald-500/25" }
    if (v >= 66) return { text: "text-blue-400", bar: "bg-blue-500", glow: "shadow-blue-500/25" }
    if (v >= 33) return { text: "text-amber-400", bar: "bg-amber-500", glow: "shadow-amber-500/25" }
    return { text: "text-neutral-400", bar: "bg-neutral-500", glow: "" }
  }

  const color = getColor(clampedValue)

  return (
    <div
      data-slot="generation-progress-bar"
      className={cn("flex flex-col items-center gap-3 w-full", className)}
    >
      {/* Percentage number (large, centered) */}
      <span
        className={cn(
          "text-5xl font-bold tabular-nums tracking-tight",
          "transition-colors duration-700",
          color.text
        )}
        aria-valuenow={clampedValue}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        {percent}%
      </span>

      {/* Label */}
      {label && (
        <p className="text-sm text-neutral-400 font-medium">{label}</p>
      )}

      {/* Custom progress bar with animated width */}
      <div
        role="progressbar"
        aria-valuenow={clampedValue}
        aria-valuemin={0}
        aria-valuemax={100}
        className={cn(
          "h-2.5 w-full max-w-md rounded-full bg-neutral-800",
          "ring-1 ring-neutral-700 overflow-hidden",
          "shadow-lg transition-shadow duration-700",
          color.glow
        )}
      >
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700 ease-out",
            color.bar
          )}
          style={{ width: `${clampedValue}%` }}
        />
      </div>
    </div>
  )
}

export { ProgressBar, type ProgressBarProps }
