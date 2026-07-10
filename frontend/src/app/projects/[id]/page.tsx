"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Loading } from "@/shared/ui/Loading";
import { ErrorState } from "@/shared/ui/ErrorState";
import { PageHeader } from "@/shared/ui/PageHeader";
import { getProject } from "@/shared/api/projects";
import type { ProjectResponse, ProjectStatus } from "@/shared/types";
import {
  Upload, Search, Images, Activity, Settings, ArrowRight,
} from "lucide-react";

const STATUS_CONFIG: Record<ProjectStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "草稿", variant: "secondary" },
  uploaded: { label: "已上传", variant: "outline" },
  novel_uploaded: { label: "已上传", variant: "outline" },
  analyzing: { label: "分析中", variant: "default" },
  running: { label: "运行中", variant: "default" },
  analysis_confirmed: { label: "已确认", variant: "outline" },
  generating_assets: { label: "生成资产", variant: "default" },
  generating_images: { label: "生成图片", variant: "default" },
  completed: { label: "已完成", variant: "outline" },
  failed: { label: "失败", variant: "destructive" },
  cancelled: { label: "已取消", variant: "secondary" },
  archived: { label: "已归档", variant: "secondary" },
};

const NAV_ITEMS = [
  { href: "upload", label: "上传小说", icon: Upload, description: "粘贴或上传小说文本" },
  { href: "analysis-progress", label: "分析详情", icon: Search, description: "查看模板模块提取进度" },
  { href: "assets", label: "资产工作台", icon: Images, description: "编辑提示词并生成参考图" },
  { href: "generate", label: "生成进度", icon: Activity, description: "监控资产图生成任务" },
  { href: "settings", label: "项目设置", icon: Settings, description: "修改项目配置" },
];

export default function ProjectOverviewPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProject(projectId)
      .then(setProject)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load project"))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <Loading message="加载项目信息..." />;
  if (error) return <ErrorState message={error} />;
  if (!project) return <ErrorState message="项目不存在" />;

  const statusConf = STATUS_CONFIG[project.status] || STATUS_CONFIG.draft;

  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <PageHeader
          title={project.title}
          description={`${project.aspect_ratio} | ${project.generation_mode === "fast_preview" ? "快速" : "高质量"}`}
          backHref="/projects"
          actions={
            <Badge variant={statusConf.variant}>{statusConf.label}</Badge>
          }
        />

        {project.progress > 0 && project.progress < 100 && (
          <Card className="bg-neutral-800 border-neutral-700">
            <CardContent className="py-4">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-neutral-400">总体进度</span>
                <span className="text-white font-semibold">{project.progress}%</span>
              </div>
              <Progress value={project.progress} className="h-3" />
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={`/projects/${projectId}/${item.href}`}
              className="block"
            >
              <Card className="bg-neutral-800 border-neutral-700 hover:border-blue-500/50 hover:bg-neutral-800/80 transition-all group h-full">
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 group-hover:bg-blue-500/20 transition-colors">
                      <item.icon className="size-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-white font-semibold group-hover:text-blue-400 transition-colors">
                        {item.label}
                      </h3>
                      <p className="text-sm text-neutral-400 mt-1">{item.description}</p>
                    </div>
                    <ArrowRight className="size-4 text-neutral-600 group-hover:text-blue-400 group-hover:translate-x-1 transition-all shrink-0 mt-1" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
