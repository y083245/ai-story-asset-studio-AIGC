"use client"

import { cn } from "@/lib/utils"
import { Textarea } from "@/components/ui/textarea"

interface TextPasteInputProps {
  value: string
  onChange: (text: string) => void
  wordCount: number
  error?: string
}

const MIN_WORDS = 1000
const MAX_WORDS = 10000

export function TextPasteInput({
  value,
  onChange,
  wordCount,
  error,
}: TextPasteInputProps) {
  const isValid = wordCount >= MIN_WORDS && wordCount <= MAX_WORDS
  const isTooShort = wordCount > 0 && wordCount < MIN_WORDS
  const isTooLong = wordCount > MAX_WORDS

  const wordCountColor = error
    ? "text-red-400"
    : isValid
      ? "text-green-400"
      : isTooShort || isTooLong
        ? "text-red-400"
        : "text-neutral-400"

  const borderColor = error
    ? "border-red-500/50 focus-visible:ring-red-500/30"
    : isTooShort || isTooLong
      ? "border-red-500/50 focus-visible:ring-red-500/30"
      : isValid
        ? "border-green-500/30 focus-visible:ring-green-500/20"
        : "border-neutral-700 focus-visible:ring-neutral-500/20"

  return (
    <div className="space-y-2">
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="在此粘贴你的小说文本...&#10;&#10;支持中文、英文及其他语言的文本内容。&#10;建议字数范围：1000-10000字。"
        className={cn(
          "min-h-[320px] max-h-[600px] bg-neutral-800 border text-white",
          "placeholder:text-neutral-500 overflow-y-auto field-sizing-fixed",
          "focus-visible:outline-none",
          borderColor
        )}
      />
      <div className="flex items-center justify-between text-sm">
        <span
          className={cn(
            "transition-colors duration-200",
            wordCountColor
          )}
        >
          {wordCount > 0 ? (
            <>
              当前字数：<span className="font-semibold">{wordCount}</span>
              <span className="text-neutral-500">
                {" "}
                / 建议 {MIN_WORDS}-{MAX_WORDS} 字
              </span>
            </>
          ) : (
            <span className="text-neutral-500">
              建议 {MIN_WORDS}-{MAX_WORDS} 字
            </span>
          )}
        </span>

        {isTooShort && (
          <span className="text-xs text-red-400">
            字数不足，至少需要 {MIN_WORDS} 字
          </span>
        )}
        {isTooLong && (
          <span className="text-xs text-red-400">
            字数超出限制，最多 {MAX_WORDS} 字
          </span>
        )}
        {isValid && (
          <span className="text-xs text-green-400">
            字数符合要求
          </span>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}
    </div>
  )
}
