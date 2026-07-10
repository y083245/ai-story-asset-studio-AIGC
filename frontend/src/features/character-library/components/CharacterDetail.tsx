"use client"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Modal } from "@/shared/ui/Modal"
import {
  User,
  Users,
  Hash,
  Calendar,
  Shirt,
  MessageSquare,
  Image,
  Lock,
} from "lucide-react"

import { resolveAssetUrl } from "@/shared/api/asset-url"
import type { CharacterResponse } from "@/shared/types"

interface CharacterDetailProps {
  character: CharacterResponse
  open: boolean
  onClose: () => void
}

const ROLE_LABELS: Record<string, string> = {
  protagonist: "主角",
  antagonist: "反派",
  supporting: "配角",
}

const ROLE_COLORS: Record<string, string> = {
  protagonist: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  antagonist: "bg-red-500/10 text-red-400 border-red-500/30",
  supporting: "bg-neutral-500/10 text-neutral-300 border-neutral-500/30",
}

interface DetailRowProps {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
}

function DetailRow({ icon, label, children }: DetailRowProps) {
  return (
    <div className="flex items-start gap-3 py-2">
      <span className="mt-0.5 text-neutral-500">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-neutral-400 mb-0.5">{label}</p>
        <div className="text-sm text-neutral-200">{children}</div>
      </div>
    </div>
  )
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

export function CharacterDetail({
  character,
  open,
  onClose,
}: CharacterDetailProps) {
  const avatarColor = getAvatarColor(character.name)
  const firstChar = character.name.charAt(0)
  const avatarUrl = resolveAssetUrl(character.avatar_url)
  const referenceImageUrls = character.reference_image_urls
    .map(resolveAssetUrl)
    .filter((url): url is string => Boolean(url))

  return (
    <Modal
      open={open}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
      title="角色详情"
      description={`角色 ID: ${character.character_id}`}
    >
      <div className="space-y-1">
        {/* Header */}
        <div className="flex items-center gap-4 pb-4 border-b border-neutral-700">
          <div
            className={cn(
              "flex size-16 shrink-0 items-center justify-center",
              "rounded-full text-2xl font-semibold text-white",
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
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-white">
                {character.name}
              </h3>
              {character.is_locked && (
                <Lock className="size-4 text-yellow-400" />
              )}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <Badge
                variant="outline"
                className={cn(
                  "text-xs",
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
                <span className="text-xs text-neutral-400">
                  {character.age_range}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Fields */}
        <DetailRow icon={<User className="size-4" />} label="描述">
          <p className="leading-relaxed">{character.description}</p>
        </DetailRow>

        <DetailRow icon={<Users className="size-4" />} label="角色定位">
          <span>{ROLE_LABELS[character.role] ?? character.role}</span>
        </DetailRow>

        <DetailRow icon={<Hash className="size-4" />} label="性别">
          <span>{character.gender || "未指定"}</span>
        </DetailRow>

        <DetailRow icon={<Calendar className="size-4" />} label="年龄段">
          <span>{character.age_range || "未指定"}</span>
        </DetailRow>

        <DetailRow icon={<Shirt className="size-4" />} label="服装设定">
          <p className="leading-relaxed">{character.outfit || "未设定"}</p>
        </DetailRow>

        <DetailRow icon={<MessageSquare className="size-4" />} label="表情设定">
          <p className="leading-relaxed">
            {character.expression_setting || "未设定"}
          </p>
        </DetailRow>

        {/* Reference Images */}
        <DetailRow icon={<Image className="size-4" />} label="参考图片">
          {referenceImageUrls.length > 0 ? (
            <div className="flex flex-wrap gap-2 mt-1">
              {referenceImageUrls.map((url, index) => (
                <img
                  key={`${character.id}:reference:${index}`}
                  src={url}
                  alt={`参考图 ${index + 1}`}
                  className="w-20 h-20 rounded-md object-cover border border-neutral-700"
                />
              ))}
            </div>
          ) : (
            <span className="text-neutral-500">暂无参考图片</span>
          )}
        </DetailRow>

        {/* Meta */}
        {character.generated_at && (
          <div className="pt-3 border-t border-neutral-700 mt-3">
            <p className="text-xs text-neutral-500">
              生成时间：{new Date(character.generated_at).toLocaleString("zh-CN")}
            </p>
          </div>
        )}
      </div>
    </Modal>
  )
}
