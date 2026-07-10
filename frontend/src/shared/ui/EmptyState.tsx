"use client"

import * as React from "react"
import { Inbox } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: {
    label: string
    onClick: () => void
  }
  className?: string
}

function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      data-slot="empty-state"
      className={cn(
        "flex flex-col items-center justify-center gap-4 py-16 text-center",
        className
      )}
    >
      <div className="rounded-full bg-neutral-800 p-4 text-neutral-400">
        {icon || <Inbox className="size-8" />}
      </div>

      <div className="flex flex-col gap-1">
        <h3 className="text-base font-medium text-white">{title}</h3>
        {description && (
          <p className="text-sm text-neutral-400 max-w-sm">{description}</p>
        )}
      </div>

      {action && (
        <Button variant="outline" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  )
}

export { EmptyState, type EmptyStateProps }
