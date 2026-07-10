"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Loading } from "@/shared/ui/Loading";
import { ErrorState } from "@/shared/ui/ErrorState";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Modal } from "@/shared/ui/Modal";
import { getProject, updateProject, deleteProject, archiveProject } from "@/shared/api/projects";
import type { ProjectResponse, ProjectStatus } from "@/shared/types";
import {
  Lock,
  Save,
  Archive,
  Trash2,
  AlertTriangle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Statuses that indicate the project is actively generating (all fields locked). */
const GENERATING_STATUSES: ProjectStatus[] = [
  "analyzing",
  "generating_assets",
  "generating_images",
];

const ASPECT_LABELS: Record<string, string> = {
  "9:16": "9:16（竖屏）",
  "16:9": "16:9（横屏）",
};

const STYLE_LABELS: Record<string, string> = {
  auto: "智能风格",
  manual: "手动风格",
};

const GENERATION_LABELS: Record<string, string> = {
  fast_preview: "快速生成",
  high_quality: "高质量",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isGenerating(status: ProjectStatus): boolean {
  return GENERATING_STATUSES.includes(status);
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SettingsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Editable form state
  const [title, setTitle] = useState("");
  const [manualStyle, setManualStyle] = useState("");
  const [saving, setSaving] = useState(false);

  // Dialogs
  const [archiveDialogOpen, setArchiveDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [dialogLoading, setDialogLoading] = useState(false);

  const fetchProject = useCallback(() => {
    setLoading(true);
    setError(null);
    getProject(projectId)
      .then((p) => {
        setProject(p);
        setTitle(p.title);
        setManualStyle(p.manual_style || "");
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "加载项目设置失败")
      )
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    fetchProject();
  }, [fetchProject]);

  // ---------------------------------------------------------------------------
  // Has unsaved changes?
  // ---------------------------------------------------------------------------

  const hasChanges = project
    ? title !== project.title ||
      (project.style_mode === "manual" && manualStyle !== (project.manual_style || ""))
    : false;

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  async function handleSave() {
    if (!project) return;
    try {
      setSaving(true);
      const updates: { title?: string; manual_style?: string } = {};
      if (title !== project.title) updates.title = title;
      if (project.style_mode === "manual" && manualStyle !== (project.manual_style || "")) {
        updates.manual_style = manualStyle;
      }

      if (Object.keys(updates).length === 0) return;

      const updated = await updateProject(projectId, updates);
      setProject(updated);
    } catch {
      alert("保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }

  async function handleArchive() {
    try {
      setDialogLoading(true);
      await archiveProject(projectId);
      router.push("/projects");
    } catch {
      alert("归档失败，请重试");
    } finally {
      setDialogLoading(false);
    }
  }

  async function handleDelete() {
    try {
      setDialogLoading(true);
      await deleteProject(projectId);
      router.push("/projects");
    } catch {
      alert("删除失败，请重试");
    } finally {
      setDialogLoading(false);
    }
  }

  // ---------------------------------------------------------------------------
  // States
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-2xl mx-auto">
          <Loading message="加载项目设置..." />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-2xl mx-auto">
          <ErrorState message={error} retry={fetchProject} />
        </div>
      </main>
    );
  }

  if (!project) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-2xl mx-auto">
          <ErrorState message="项目不存在" />
        </div>
      </main>
    );
  }

  const locked = isGenerating(project.status);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <PageHeader
          title="项目设置"
          description={project.title}
          backHref={`/projects/${projectId}`}
        />

        {/* Settings Form */}
        <Card className="bg-neutral-800 border-neutral-700">
          <CardHeader>
            <CardTitle className="text-white">基本信息</CardTitle>
            <CardDescription className="text-neutral-400">
              修改项目的基本配置
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Project Name */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-white">项目名称</label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="输入项目名称"
                className="bg-neutral-900 border-neutral-700 text-white placeholder:text-neutral-500"
              />
            </div>

            {/* Aspect Ratio */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-white flex items-center gap-2">
                画面比例
                {locked && <Lock className="size-3 text-neutral-500" />}
              </label>
              <Input
                value={ASPECT_LABELS[project.aspect_ratio] || project.aspect_ratio}
                disabled
                className={locked
                  ? "bg-neutral-800/50 border-neutral-700/50 text-neutral-500 cursor-not-allowed"
                  : "bg-neutral-900 border-neutral-700 text-white"}
              />
            </div>

            {/* Style Mode */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-white flex items-center gap-2">
                风格模式
                {locked && <Lock className="size-3 text-neutral-500" />}
              </label>
              <Input
                value={STYLE_LABELS[project.style_mode] || project.style_mode}
                disabled
                className={locked
                  ? "bg-neutral-800/50 border-neutral-700/50 text-neutral-500 cursor-not-allowed"
                  : "bg-neutral-900 border-neutral-700 text-white"}
              />
            </div>

            {/* Manual Style (only if manual) */}
            {project.style_mode === "manual" && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-white flex items-center gap-2">
                  手动风格描述
                  {locked && <Lock className="size-3 text-neutral-500" />}
                </label>
                {locked ? (
                  <Input
                    value={manualStyle}
                    disabled
                    className="bg-neutral-800/50 border-neutral-700/50 text-neutral-500 cursor-not-allowed"
                  />
                ) : (
                  <Input
                    value={manualStyle}
                    onChange={(e) => setManualStyle(e.target.value)}
                    placeholder="描述您想要的视觉风格..."
                    className="bg-neutral-900 border-neutral-700 text-white placeholder:text-neutral-500"
                  />
                )}
              </div>
            )}

            {/* Generation Mode */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-white flex items-center gap-2">
                生成模式
                {locked && <Lock className="size-3 text-neutral-500" />}
              </label>
              <Input
                value={GENERATION_LABELS[project.generation_mode] || project.generation_mode}
                disabled
                className={locked
                  ? "bg-neutral-800/50 border-neutral-700/50 text-neutral-500 cursor-not-allowed"
                  : "bg-neutral-900 border-neutral-700 text-white"}
              />
            </div>

            {/* Save Button */}
            <div className="pt-2">
              <Button
                onClick={handleSave}
                disabled={!hasChanges || saving}
                className="bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
              >
                <Save className="size-4 mr-2" />
                {saving ? "保存中..." : "保存设置"}
              </Button>
              {!hasChanges && (
                <p className="text-xs text-neutral-500 mt-1">没有需要保存的更改</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Danger Zone */}
        <Card className="bg-neutral-800 border-red-900/50">
          <CardHeader>
            <CardTitle className="text-red-400 flex items-center gap-2">
              <AlertTriangle className="size-4" />
              危险区域
            </CardTitle>
            <CardDescription className="text-neutral-400">
              以下操作不可撤销，请谨慎操作
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Archive */}
            <div className="flex items-center justify-between gap-4 p-3 rounded-lg bg-neutral-900/50 border border-neutral-700">
              <div className="space-y-1">
                <p className="text-sm font-medium text-white">归档项目</p>
                <p className="text-xs text-neutral-400">
                  将项目标记为已归档，归档后项目将不再出现在主列表中
                </p>
              </div>
              <Button
                variant="outline"
                className="border-neutral-700 text-neutral-400 hover:text-white hover:border-neutral-600 shrink-0"
                onClick={() => setArchiveDialogOpen(true)}
              >
                <Archive className="size-4 mr-2" />
                归档
              </Button>
            </div>

            {/* Delete */}
            <div className="flex items-center justify-between gap-4 p-3 rounded-lg bg-red-950/20 border border-red-900/30">
              <div className="space-y-1">
                <p className="text-sm font-medium text-red-400">删除项目</p>
                <p className="text-xs text-neutral-400">
                  永久删除项目及其所有关联数据，此操作不可恢复
                </p>
              </div>
              <Button
                variant="outline"
                className="border-red-900/50 text-red-400 hover:bg-red-950/30 hover:text-red-300 hover:border-red-800 shrink-0"
                onClick={() => setDeleteDialogOpen(true)}
              >
                <Trash2 className="size-4 mr-2" />
                删除
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Archive Confirmation Dialog */}
        <Modal
          open={archiveDialogOpen}
          onOpenChange={setArchiveDialogOpen}
          title="确认归档"
          description="归档后，项目将不再出现在项目列表中。您可以随时在归档项目中找到它。"
          footer={
            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                className="border-neutral-700 text-white hover:bg-neutral-700"
                onClick={() => setArchiveDialogOpen(false)}
              >
                取消
              </Button>
              <Button
                className="bg-neutral-600 hover:bg-neutral-500 text-white"
                onClick={handleArchive}
                disabled={dialogLoading}
              >
                {dialogLoading ? "归档中..." : "确认归档"}
              </Button>
            </div>
          }
        >
          <p className="text-sm text-neutral-300">
            项目「{project.title}」将被归档。您确定要继续吗？
          </p>
        </Modal>

        {/* Delete Confirmation Dialog */}
        <Modal
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          title="确认删除"
          description="此操作将永久删除项目及其所有关联数据，包括故事分析、角色、场景、道具和资产图。此操作不可撤销。"
          footer={
            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                className="border-neutral-700 text-white hover:bg-neutral-700"
                onClick={() => setDeleteDialogOpen(false)}
              >
                取消
              </Button>
              <Button
                className="bg-red-600 hover:bg-red-500 text-white"
                onClick={handleDelete}
                disabled={dialogLoading}
              >
                {dialogLoading ? "删除中..." : "确认删除"}
              </Button>
            </div>
          }
        >
          <div className="space-y-2">
            <p className="text-sm text-neutral-300">
              项目「{project.title}」将被永久删除。此操作不可撤销。
            </p>
            <div className="flex items-center gap-2 p-2 rounded bg-red-950/30 border border-red-900/30">
              <AlertTriangle className="size-4 text-red-400 shrink-0" />
              <p className="text-xs text-red-300">
                删除后数据无法恢复。如果只是想隐藏项目，请使用「归档」功能。
              </p>
            </div>
          </div>
        </Modal>
      </div>
    </main>
  );
}
