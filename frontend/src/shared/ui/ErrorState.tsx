"use client"

import * as React from "react"
import { AlertTriangle } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

interface ErrorStateProps {
  title?: string
  message: string
  retry?: () => void
  className?: string
}

function ErrorState({
  title = "Something went wrong",
  message,
  retry,
  className,
}: ErrorStateProps) {
  return (
    <div
      data-slot="error-state"
      className={cn(
        "flex flex-col items-center justify-center gap-4 py-16 text-center",
        className
      )}
    >
      <div className="rounded-full bg-red-950/50 p-4 text-red-400">
        <AlertTriangle className="size-8" />
      </div>

      <div className="flex flex-col gap-1">
        <h3 className="text-base font-medium text-white">{title}</h3>
        <p className="text-sm text-neutral-400 max-w-sm">{message}</p>
      </div>

      {retry && (
        <Button variant="outline" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export { ErrorState, type ErrorStateProps }
