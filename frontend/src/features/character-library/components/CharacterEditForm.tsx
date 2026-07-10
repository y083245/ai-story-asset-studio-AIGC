"use client"

import { useState, useEffect } from "react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Save, X } from "lucide-react"

import type { CharacterResponse, CharacterUpdateRequest } from "@/shared/types"

interface CharacterEditFormProps {
  character: CharacterResponse
  onSave: (data: CharacterUpdateRequest) => void
  onCancel: () => void
}

export function CharacterEditForm({
  character,
  onSave,
  onCancel,
}: CharacterEditFormProps) {
  const [name, setName] = useState(character.name)
  const [description, setDescription] = useState(character.description)
  const [outfit, setOutfit] = useState(character.outfit ?? "")
  const [expressionSetting, setExpressionSetting] = useState(
    character.expression_setting ?? ""
  )
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    setName(character.name)
    setDescription(character.description)
    setOutfit(character.outfit ?? "")
    setExpressionSetting(character.expression_setting ?? "")
    setErrors({})
  }, [character])

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!name.trim()) {
      newErrors.name = "角色名称不能为空"
    }

    if (!description.trim()) {
      newErrors.description = "角色描述不能为空"
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!validate()) return

    const data: CharacterUpdateRequest = {}

    if (name.trim() !== character.name) {
      data.name = name.trim()
    }
    if (description.trim() !== character.description) {
      data.description = description.trim()
    }

    const trimmedOutfit = outfit.trim()
    const originalOutfit = character.outfit ?? ""
    if (trimmedOutfit !== originalOutfit) {
      data.outfit = trimmedOutfit || undefined
    }

    const trimmedExpression = expressionSetting.trim()
    const originalExpression = character.expression_setting ?? ""
    if (trimmedExpression !== originalExpression) {
      data.expression_setting = trimmedExpression || undefined
    }

    onSave(data)
  }

  const hasChanges =
    name.trim() !== character.name ||
    description.trim() !== character.description ||
    outfit.trim() !== (character.outfit ?? "") ||
    expressionSetting.trim() !== (character.expression_setting ?? "")

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Name */}
      <div className="space-y-1.5">
        <label
          htmlFor="character-name"
          className="text-sm font-medium text-neutral-300"
        >
          角色名称
        </label>
        <Input
          id="character-name"
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            if (errors.name) setErrors((prev) => ({ ...prev, name: "" }))
          }}
          placeholder="输入角色名称"
          className={cn(
            "bg-neutral-800 border-neutral-700 text-white",
            "placeholder:text-neutral-500",
            errors.name && "border-red-500/50 focus-visible:ring-red-500/30"
          )}
        />
        {errors.name && (
          <p className="text-xs text-red-400">{errors.name}</p>
        )}
      </div>

      {/* Description */}
      <div className="space-y-1.5">
        <label
          htmlFor="character-desc"
          className="text-sm font-medium text-neutral-300"
        >
          角色描述
        </label>
        <Textarea
          id="character-desc"
          value={description}
          onChange={(e) => {
            setDescription(e.target.value)
            if (errors.description)
              setErrors((prev) => ({ ...prev, description: "" }))
          }}
          placeholder="描述角色的性格、背景、动机等"
          rows={4}
          className={cn(
            "bg-neutral-800 border-neutral-700 text-white resize-y",
            "placeholder:text-neutral-500",
            errors.description &&
              "border-red-500/50 focus-visible:ring-red-500/30"
          )}
        />
        {errors.description && (
          <p className="text-xs text-red-400">{errors.description}</p>
        )}
      </div>

      {/* Outfit */}
      <div className="space-y-1.5">
        <label
          htmlFor="character-outfit"
          className="text-sm font-medium text-neutral-300"
        >
          服装设定
        </label>
        <Textarea
          id="character-outfit"
          value={outfit}
          onChange={(e) => setOutfit(e.target.value)}
          placeholder="描述角色的服装风格、配饰等"
          rows={3}
          className={cn(
            "bg-neutral-800 border-neutral-700 text-white resize-y",
            "placeholder:text-neutral-500"
          )}
        />
      </div>

      {/* Expression Setting */}
      <div className="space-y-1.5">
        <label
          htmlFor="character-expression"
          className="text-sm font-medium text-neutral-300"
        >
          表情设定
        </label>
        <Textarea
          id="character-expression"
          value={expressionSetting}
          onChange={(e) => setExpressionSetting(e.target.value)}
          placeholder="描述角色的表情特征、常用表情等"
          rows={2}
          className={cn(
            "bg-neutral-800 border-neutral-700 text-white resize-y",
            "placeholder:text-neutral-500"
          )}
        />
      </div>

      {/* Read-only fields */}
      <div className="rounded-md bg-neutral-800/50 border border-neutral-700/50 px-3 py-2">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-neutral-500">角色定位：</span>
            <span className="text-neutral-300">{character.role}</span>
          </div>
          <div>
            <span className="text-neutral-500">性别：</span>
            <span className="text-neutral-300">
              {character.gender ?? "未指定"}
            </span>
          </div>
          <div>
            <span className="text-neutral-500">年龄段：</span>
            <span className="text-neutral-300">
              {character.age_range ?? "未指定"}
            </span>
          </div>
          <div>
            <span className="text-neutral-500">锁定状态：</span>
            <span
              className={cn(
                character.is_locked ? "text-yellow-400" : "text-neutral-300"
              )}
            >
              {character.is_locked ? "已锁定" : "未锁定"}
            </span>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button
          type="button"
          variant="ghost"
          onClick={onCancel}
          className="text-neutral-400 hover:text-white hover:bg-neutral-700"
        >
          <X className="size-4 mr-1.5" />
          取消
        </Button>
        <Button
          type="submit"
          disabled={!hasChanges}
          className={cn(
            "bg-blue-600 hover:bg-blue-500 text-white",
            !hasChanges && "opacity-50 cursor-not-allowed"
          )}
        >
          <Save className="size-4 mr-1.5" />
          保存
        </Button>
      </div>
    </form>
  )
}
