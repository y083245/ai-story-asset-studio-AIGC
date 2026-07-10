"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

interface PageHeaderProps {
  title: string
  description?: string
  backHref?: string
  actions?: React.ReactNode
  className?: string
}

function PageHeader({
  title,
  description,
  backHref,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      data-slot="page-header"
      className={cn(
        "flex flex-col gap-1",
        className
      )}
    >
      <div className="flex items-center gap-3">
        {backHref && (
          <Button
            variant="ghost"
            size="icon-sm"
            asChild
            className="shrink-0"
          >
            <Link href={backHref}>
              <ArrowLeft className="size-4" />
              <span className="sr-only">Back</span>
            </Link>
          </Button>
        )}

        <h1 className="text-lg font-semibold text-white truncate">{title}</h1>

        {actions && (
          <div className="ml-auto flex items-center gap-2 shrink-0">
            {actions}
          </div>
        )}
      </div>

      {description && (
        <p className="text-sm text-neutral-400 ml-0">{description}</p>
      )}
    </div>
  )
}

export { PageHeader, type PageHeaderProps }
