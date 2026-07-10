"use client"

import { useRouter } from "next/navigation"
import { Calendar, ImageIcon, Monitor, Trash2 } from "lucide-react"

import { cn } from "@/lib/utils"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"
import { ProjectStatusBadge } from "./ProjectStatusBadge"

import type { ProjectResponse } from "@/shared/types"

interface ProjectCardProps {
  project: ProjectResponse
  onDelete?: (id: string) => void
}

export function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const router = useRouter()

  const handleClick = () => {
    router.push(`/projects/${project.project_id}/upload`)
  }

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    onDelete?.(project.project_id)
  }

  const isActive =
    project.status !== "completed" &&
    project.status !== "failed" &&
    project.status !== "archived"

  const formattedDate = new Date(project.created_at).toLocaleDateString(
    "zh-CN",
    {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }
  )

  const generationModeLabel =
    project.generation_mode === "fast_preview" ? "快速" : "高质量"

  return (
    <Card
      className={cn(
        "bg-neutral-800 border-neutral-700 cursor-pointer",
        "hover:border-neutral-500 transition-colors duration-200"
      )}
      onClick={handleClick}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base font-medium text-white line-clamp-1">
            {project.title}
          </CardTitle>
          {onDelete && (
            <Button
              variant="ghost"
              size="icon-xs"
              className="shrink-0 text-neutral-500 hover:text-red-400 hover:bg-neutral-700"
              onClick={handleDelete}
            >
              <Trash2 className="size-3.5" />
            </Button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ProjectStatusBadge status={project.status} />
          {isActive && (
            <span className="text-xs text-neutral-400">
              {project.progress}%
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-neutral-400">
            <span>进度</span>
            <span>{project.progress}%</span>
          </div>
          <Progress value={project.progress} />
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-1.5 text-neutral-400">
            <ImageIcon className="size-3.5" />
            <span>{project.aspect_ratio}</span>
          </div>
          <div className="flex items-center gap-1.5 text-neutral-400">
            <Monitor className="size-3.5" />
            <span>{generationModeLabel}</span>
          </div>
          <div className="flex items-center gap-1.5 text-neutral-400">
            <Calendar className="size-3.5" />
            <span>{formattedDate}</span>
          </div>
        </div>
      </CardContent>

      <CardFooter>
        <CardDescription className="text-xs text-neutral-500">
          {project.style_mode === "auto"
            ? "自动风格"
            : project.manual_style
              ? `风格: ${project.manual_style}`
              : "手动风格"}
        </CardDescription>
      </CardFooter>
    </Card>
  )
}
