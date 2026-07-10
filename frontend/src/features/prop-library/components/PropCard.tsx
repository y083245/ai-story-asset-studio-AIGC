"use client"

import * as React from "react"
import { Edit, RefreshCw, Wrench } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card"
import { resolveAssetUrl } from "@/shared/api/asset-url"
import type { PropResponse } from "@/shared/types"

interface PropCardProps {
  prop: PropResponse
  onEdit: (id: string) => void
  onRegenerate: (id: string) => void
}

function PropCard({ prop, onEdit, onRegenerate }: PropCardProps) {
  const thumbnailUrl = resolveAssetUrl(prop.thumbnail_url)

  return (
    <Card
      className={cn(
        "bg-neutral-800 border-neutral-700 text-white",
        "hover:border-neutral-600 transition-colors",
        "group/card"
      )}
    >
      {/* Thumbnail placeholder */}
      <div
        className={cn(
          "h-32 rounded-t-xl bg-gradient-to-br from-neutral-600 via-neutral-700 to-neutral-800",
          "flex items-center justify-center relative overflow-hidden"
        )}
      >
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={prop.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <Wrench className="size-10 text-neutral-500" />
        )}
      </div>

      <CardHeader className="pb-1">
        <CardTitle className="text-white text-base truncate">
          {prop.name}
        </CardTitle>
        <CardDescription className="text-neutral-400 text-xs line-clamp-2">
          {prop.description || "暂无描述"}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Function badge */}
        <div>
          <Badge
            variant="secondary"
            className="bg-neutral-700/50 text-neutral-300 border-neutral-600"
          >
            {prop.function || "未指定功能"}
          </Badge>
        </div>

        {/* State timeline pills */}
        {prop.state_timeline.length > 0 && (
          <div>
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1.5">
              状态时间线
            </p>
            <div className="flex flex-wrap items-center gap-1.5">
              {prop.state_timeline.map((state, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 rounded-full bg-neutral-700/50 border border-neutral-600 px-2 py-0.5 text-[10px] text-neutral-300"
                >
                  <span className="size-1.5 rounded-full bg-blue-400 shrink-0" />
                  {state}
                </span>
              ))}
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="border-neutral-700 bg-neutral-800/50 flex items-center gap-2">
        <Button
          variant="outline"
          size="xs"
          onClick={() => onEdit(prop.id)}
          className="border-neutral-600 text-neutral-300 hover:text-white hover:bg-neutral-700"
        >
          <Edit className="size-3" />
          编辑
        </Button>
        <Button
          variant="outline"
          size="xs"
          onClick={() => onRegenerate(prop.id)}
          className="border-neutral-600 text-neutral-300 hover:text-white hover:bg-neutral-700"
        >
          <RefreshCw className="size-3" />
          重新生成
        </Button>
      </CardFooter>
    </Card>
  )
}

export { PropCard, type PropCardProps }
