"use client"

import { useCallback, useState, useRef } from "react"
import { Upload, FileText, X, AlertTriangle } from "lucide-react"

import { cn } from "@/lib/utils"

interface FileUploaderProps {
  onFileSelected: (file: File) => void
  selectedFile: File | null
  error?: string
}

const ACCEPTED_TYPES = [
  ".txt",
  "text/plain",
  ".docx",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]

const ACCEPTED_EXTENSIONS = ".txt,.docx"
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function FileUploader({
  onFileSelected,
  selectedFile,
  error,
}: FileUploaderProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [rejectionMessage, setRejectionMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = useCallback((file: File): string | null => {
    const name = file.name.toLowerCase()
    const isTxt = name.endsWith(".txt") || file.type === "text/plain"
    const isDocx =
      name.endsWith(".docx") ||
      file.type ===
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    if (name.endsWith(".pdf") || file.type === "application/pdf") {
      return "不支持 PDF 格式，请上传 .txt 或 .docx 文件"
    }

    if (!isTxt && !isDocx) {
      return "仅支持 .txt 和 .docx 格式文件"
    }

    if (file.size > MAX_FILE_SIZE) {
      return `文件大小不能超过 ${formatFileSize(MAX_FILE_SIZE)}`
    }

    return null
  }, [])

  const handleFile = useCallback(
    (file: File) => {
      setRejectionMessage(null)
      const validationError = validateFile(file)
      if (validationError) {
        setRejectionMessage(validationError)
        return
      }
      onFileSelected(file)
    },
    [onFileSelected, validateFile]
  )

  const handleDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragOver(true)
    },
    []
  )

  const handleDragLeave = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragOver(false)
    },
    []
  )

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragOver(false)

      const file = e.dataTransfer.files[0]
      if (file) {
        handleFile(file)
      }
    },
    [handleFile]
  )

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) {
        handleFile(file)
      }
    },
    [handleFile]
  )

  const handleRemoveFile = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onFileSelected(null as unknown as File)
      setRejectionMessage(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
    },
    [onFileSelected]
  )

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        className={cn(
          "relative flex flex-col items-center justify-center gap-3",
          "rounded-lg border-2 border-dashed p-10",
          "cursor-pointer transition-colors duration-200",
          "bg-neutral-800/50",
          isDragOver
            ? "border-blue-400 bg-blue-500/5"
            : selectedFile
              ? "border-green-500/30 bg-green-500/5"
              : "border-neutral-600 hover:border-neutral-500 hover:bg-neutral-800"
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          onChange={handleInputChange}
          className="hidden"
        />

        {selectedFile ? (
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center gap-3 text-neutral-200">
              <FileText className="size-8 text-green-400" />
              <div>
                <p className="text-sm font-medium">{selectedFile.name}</p>
                <p className="text-xs text-neutral-400">
                  {formatFileSize(selectedFile.size)}
                </p>
              </div>
              <button
                type="button"
                onClick={handleRemoveFile}
                className="ml-2 rounded-full p-1 text-neutral-400 hover:bg-neutral-700 hover:text-white transition-colors"
              >
                <X className="size-4" />
              </button>
            </div>
            <p className="text-xs text-neutral-500">点击或拖放以更换文件</p>
          </div>
        ) : (
          <>
            <div className="rounded-full bg-neutral-700 p-3">
              <Upload
                className={cn(
                  "size-6 transition-colors",
                  isDragOver ? "text-blue-400" : "text-neutral-400"
                )}
              />
            </div>
            <div className="text-center">
              <p className="text-sm text-neutral-300">
                <span className="font-medium text-blue-400">点击上传</span>
                {" 或将文件拖放到此处"}
              </p>
              <p className="mt-1 text-xs text-neutral-500">
                支持 .txt 和 .docx 格式，最大 {formatFileSize(MAX_FILE_SIZE)}
              </p>
            </div>
          </>
        )}
      </div>

      {(rejectionMessage || error) && (
        <div className="flex items-center gap-2 rounded-md bg-red-500/10 border border-red-500/30 px-3 py-2">
          <AlertTriangle className="size-4 text-red-400 shrink-0" />
          <p className="text-sm text-red-400">
            {rejectionMessage || error}
          </p>
        </div>
      )}
    </div>
  )
}
