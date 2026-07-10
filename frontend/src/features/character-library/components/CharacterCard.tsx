"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Edit3,
  Lock,
  LockOpen,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react"

import { resolveAssetUrl } from "@/shared/api/asset-url"
import type { CharacterResponse } from "@/shared/types"

interface CharacterCardProps {
  character: CharacterResponse
  onEdit: (id: string) => void
  onLock: (id: string) => void
  onRegenerate: (id: string) => void
}

const ROLE_LABELS: Record<string, string> = {
  protagonist: "主角",
  antagonist: "反派",
  supporting: "配角",
}

const ROLE_COLORS: Record<string, string> = {
  protagonist:
    "bg-blue-500/10 text-blue-400 border-blue-500/30",
  antagonist:
    "bg-red-500/10 text-red-400 border-red-500/30",
  supporting:
    "bg-neutral-500/10 text-neutral-300 border-neutral-500/30",
}

function getAvatarColor(name: string): string {
  const colors = [
    "bg-blue-500",
    "bg-emerald-500",
    "bg-violet-500",
    "bg-amber-500",
    "bg-rose-500",
    "bg-cyan-500",
    "bg-fuchsia-500",
    "bg-orange-500",
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}

export function CharacterCard({
  character,
  onEdit,
  onLock,
  onRegenerate,
}: CharacterCardProps) {
  const [expanded, setExpanded] = useState(false)

  const avatarColor = getAvatarColor(character.name)
  const firstChar = character.name.charAt(0)
  const avatarUrl = resolveAssetUrl(character.avatar_url)

  return (
    <Card
      className={cn(
        "bg-neutral-800 border-neutral-700 group",
        "transition-all duration-200"
      )}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start gap-3">
          {/* Avatar placeholder */}
          <div
            className={cn(
              "flex size-11 shrink-0 items-center justify-center",
              "rounded-full text-lg font-semibold text-white",
              avatarColor
            )}
          >
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={character.name}
                className="size-full rounded-full object-cover"
              />
            ) : (
              firstChar
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <CardTitle className="text-sm font-semibold text-white truncate">
                {character.name}
              </CardTitle>
              {character.is_locked && (
                <Lock className="size-3 text-yellow-400 shrink-0" />
              )}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0",
                  ROLE_COLORS[character.role] ??
                    "bg-neutral-500/10 text-neutral-300 border-neutral-500/30"
                )}
              >
                {ROLE_LABELS[character.role] ?? character.role}
              </Badge>
              {character.gender && (
                <span className="text-xs text-neutral-400">
                  {character.gender}
                </span>
              )}
              {character.age_range && (
                <span className="text-xs text-neutral-500">
                  {character.age_range}
                </span>
              )}
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pb-3">
        <div className="relative">
          <CardDescription
            className={cn(
              "text-xs text-neutral-400 leading-relaxed",
              !expanded && "line-clamp-2"
            )}
          >
            {character.description}
          </CardDescription>
          {character.description && character.description.length > 80 && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="mt-1 flex items-center gap-0.5 text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
            >
              {expanded ? (
                <>
                  收起 <ChevronUp className="size-3" />
                </>
              ) : (
                <>
                  展开 <ChevronDown className="size-3" />
                </>
              )}
            </button>
          )}
        </div>
      </CardContent>

      <CardFooter className="flex items-center justify-end gap-1 pt-0">
        <Button
          variant="ghost"
          size="icon-xs"
          className="text-neutral-500 hover:text-white hover:bg-neutral-700"
          onClick={() => onEdit(character.id)}
          title="编辑"
        >
          <Edit3 className="size-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          className={cn(
            "hover:bg-neutral-700",
            character.is_locked
              ? "text-yellow-400 hover:text-yellow-300"
              : "text-neutral-500 hover:text-white"
          )}
          onClick={() => onLock(character.id)}
          title={character.is_locked ? "解锁" : "锁定"}
        >
          {character.is_locked ? (
            <Lock className="size-3.5" />
          ) : (
            <LockOpen className="size-3.5" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          className="text-neutral-500 hover:text-blue-400 hover:bg-neutral-700"
          onClick={() => onRegenerate(character.id)}
          title="重新生成"
        >
          <RefreshCw className="size-3.5" />
        </Button>
      </CardFooter>
    </Card>
  )
}
