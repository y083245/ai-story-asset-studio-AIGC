"use client"

import * as React from "react"
import { Lock, Unlock, Edit, MapPin, Clock, Smile } from "lucide-react"

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
import type { SceneResponse } from "@/shared/types"

interface SceneCardProps {
  scene: SceneResponse
  onEdit: (id: string) => void
  onLock: (id: string) => void
}

function SceneCard({ scene, onEdit, onLock }: SceneCardProps) {
  const thumbnailUrl = resolveAssetUrl(scene.thumbnail_url)

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
          "h-36 rounded-t-xl bg-gradient-to-br from-neutral-700 via-neutral-600 to-neutral-800",
          "flex items-center justify-center relative overflow-hidden"
        )}
      >
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={scene.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <span className="text-neutral-500 text-sm font-medium">
            场景缩略图
          </span>
        )}

        {/* Lock indicator overlay */}
        {scene.is_locked && (
          <div className="absolute top-2 right-2 rounded-full bg-neutral-950/70 p-1.5">
            <Lock className="size-3.5 text-amber-400" />
          </div>
        )}
      </div>

      <CardHeader className="pb-1">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-white text-base truncate">
            {scene.name}
          </CardTitle>
          {!scene.is_locked && (
            <Unlock className="size-3.5 text-neutral-500 shrink-0 mt-0.5" />
          )}
        </div>
        <CardDescription className="text-neutral-400 text-xs line-clamp-2">
          {scene.description || "暂无描述"}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-wrap items-center gap-1.5">
        {scene.time_period && (
          <Badge
            variant="secondary"
            className="bg-neutral-700/50 text-neutral-300 border-neutral-600"
          >
            <Clock className="size-3 mr-1" />
            {scene.time_period}
          </Badge>
        )}
        {scene.mood && (
          <Badge
            variant="secondary"
            className="bg-neutral-700/50 text-neutral-300 border-neutral-600"
          >
            <Smile className="size-3 mr-1" />
            {scene.mood}
          </Badge>
        )}
        {scene.location && (
          <Badge
            variant="secondary"
            className="bg-neutral-700/50 text-neutral-300 border-neutral-600"
          >
            <MapPin className="size-3 mr-1" />
            {scene.location}
          </Badge>
        )}
      </CardContent>

      {/* Fixed anchors */}
      {scene.fixed_anchors.length > 0 && (
        <CardContent className="pt-0">
          <div className="flex flex-wrap gap-1">
            {scene.fixed_anchors.map((anchor, i) => (
              <span
                key={i}
                className="inline-flex items-center rounded-md border border-neutral-600 bg-neutral-700/50 px-1.5 py-0.5 text-[10px] text-neutral-300"
              >
                {anchor}
              </span>
            ))}
          </div>
        </CardContent>
      )}

      <CardFooter className="border-neutral-700 bg-neutral-800/50 flex items-center gap-2">
        <Button
          variant="outline"
          size="xs"
          onClick={() => onEdit(scene.id)}
          className="border-neutral-600 text-neutral-300 hover:text-white hover:bg-neutral-700"
        >
          <Edit className="size-3" />
          编辑
        </Button>
        <Button
          variant="outline"
          size="xs"
          onClick={() => onLock(scene.id)}
          className={cn(
            "border-neutral-600 transition-colors",
            scene.is_locked
              ? "text-amber-400 hover:text-amber-300 hover:bg-amber-950/30"
              : "text-neutral-300 hover:text-white hover:bg-neutral-700"
          )}
        >
          {scene.is_locked ? (
            <>
              <Lock className="size-3" />
              已锁定
            </>
          ) : (
            <>
              <Unlock className="size-3" />
              锁定
            </>
          )}
        </Button>
      </CardFooter>
    </Card>
  )
}

export { SceneCard, type SceneCardProps }
