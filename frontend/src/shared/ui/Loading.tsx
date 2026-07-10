"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

const sizeClasses = {
  sm: "size-4 border-2",
  md: "size-8 border-2",
  lg: "size-12 border-3",
} as const

const textSizeClasses = {
  sm: "text-xs",
  md: "text-sm",
  lg: "text-base",
} as const

interface LoadingProps {
  message?: string
  size?: "sm" | "md" | "lg"
  className?: string
}

function Loading({
  message,
  size = "md",
  className,
}: LoadingProps) {
  return (
    <div
      data-slot="loading"
      className={cn(
        "flex flex-col items-center justify-center gap-3",
        className
      )}
    >
      <div
        role="status"
        aria-label={message || "Loading"}
        className={cn(
          "rounded-full border-neutral-600 border-t-white animate-spin",
          sizeClasses[size]
        )}
      />
      {message && (
        <p
          className={cn(
            "text-neutral-400 font-medium",
            textSizeClasses[size]
          )}
        >
          {message}
        </p>
      )}
    </div>
  )
}

export { Loading, type LoadingProps }
