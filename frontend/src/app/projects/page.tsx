"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/shared/ui/Loading";
import { EmptyState } from "@/shared/ui/EmptyState";
import { ErrorState } from "@/shared/ui/ErrorState";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Modal } from "@/shared/ui/Modal";
import { deleteProject, listProjects, permanentDeleteProjects, restoreProject } from "@/shared/api/projects";
import { startAnalysis } from "@/shared/api/workflow";
import type { ProjectResponse } from "@/shared/types";
import { AlertTriangle, CheckSquare, ChevronRight, Images, Loader2, Play, Plus, RotateCcw, Square, Trash2, X } from "lucide-react";

const STATUS_CONFIG: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "草稿", variant: "secondary" },
  uploaded: { label: "已上传", variant: "outline" },
  novel_uploaded: { label: "已上传", variant: "outline" },
  analyzing: { label: "分析中", variant: "default" },
  analysis_confirmed: { label: "已确认", variant: "outline" },
  generating_assets: { label: "生成资产", variant: "default" },
  generating_images: { label: "生成图片", variant: "default" },
  completed: { label: "已完成", variant: "outline" },
  failed: { label: "失败", variant: "destructive" },
  archived: { label: "已归档", variant: "secondary" },
};

function getProjectRoute(project: ProjectResponse): string {
  switch (project.status as string) {
    case "draft":
      return `/projects/${project.project_id}/upload`;
    case "uploaded":
    case "novel_uploaded":
    case "analyzing":
      return `/projects/${project.project_id}/analysis`;
    case "analysis_confirmed":
    case "generating_assets":
    case "generating_images":
    case "failed":
      return `/projects/${project.project_id}/generate`;
    case "completed":
      return `/projects/${project.project_id}/assets`;
    case "archived":
      return `/projects/${project.project_id}`;
    default:
      return `/projects/${project.project_id}`;
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function formatRecycleDeadline(project: ProjectResponse): string {
  if (!project.purge_after) return "30 天后自动删除";
  const deadline = new Date(project.purge_after);
  const msRemaining = deadline.getTime() - Date.now();
  const daysRemaining = Math.max(0, Math.ceil(msRemaining / (1000 * 60 * 60 * 24)));
  return `${daysRemaining} 天后自动删除`;
}

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [projectToDelete, setProjectToDelete] = useState<ProjectResponse | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [showRecycleBin, setShowRecycleBin] = useState(false);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmBatchDelete, setConfirmBatchDelete] = useState(false);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [batchRestoring, setBatchRestoring] = useState(false);
  const [startingAnalysisId, setStartingAnalysisId] = useState<string | null>(null);

  const fetchProjects = useCallback(async (recycleBin: boolean) => {
    try {
      const data = await listProjects(recycleBin ? { only_archived: true } : undefined);
      setProjects(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchProjects(showRecycleBin);
  }, [fetchProjects, showRecycleBin]);

  async function handleDeleteProject() {
    if (!projectToDelete) return;

    try {
      setDeletingId(projectToDelete.project_id);
      await deleteProject(projectToDelete.project_id);
      setProjects((items) => items.filter((project) => project.project_id !== projectToDelete.project_id));
      setProjectToDelete(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除项目失败，请重试");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleRestoreProject(project: ProjectResponse) {
    try {
      setRestoringId(project.project_id);
      await restoreProject(project.project_id);
      setProjects((items) => items.filter((item) => item.project_id !== project.project_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "恢复项目失败，请重试");
    } finally {
      setRestoringId(null);
    }
  }

  async function handleStartAnalysis(project: ProjectResponse) {
    try {
      setStartingAnalysisId(project.project_id);
      setError(null);
      const response = await startAnalysis(project.project_id);
      setProjects((items) =>
        items.map((item) =>
          item.project_id === project.project_id
            ? {
                ...item,
                status: response.status === "completed" ? "analysis_confirmed" : "analyzing",
                progress: response.status === "completed" ? 100 : Math.max(item.progress, 1),
              }
            : item
        )
      );
      router.push(
        response.status === "completed"
          ? `/projects/${project.project_id}/analysis`
          : `/projects/${project.project_id}/analysis-progress`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动分析失败，请重试");
    } finally {
      setStartingAnalysisId(null);
    }
  }

  // ------------------------------------------------------------------
  // Selection mode helpers
  // ------------------------------------------------------------------

  function toggleSelect(projectId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
      }
      return next;
    });
  }

  function selectAll() {
    setSelectedIds(new Set(projects.map((p) => p.project_id)));
  }

  function deselectAll() {
    setSelectedIds(new Set());
  }

  function cancelSelect() {
    setSelectMode(false);
    setSelectedIds(new Set());
  }

  async function handleBatchPermanentDelete() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    try {
      setBatchDeleting(true);
      await permanentDeleteProjects(ids);
      setProjects((items) => items.filter((p) => !selectedIds.has(p.project_id)));
      setSelectedIds(new Set());
      setSelectMode(false);
      setConfirmBatchDelete(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "永久删除失败，请重试");
    } finally {
      setBatchDeleting(false);
    }
  }

  async function handleBatchRestore() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    try {
      setBatchRestoring(true);
      await Promise.all(ids.map((projectId) => restoreProject(projectId)));
      setProjects((items) => items.filter((p) => !selectedIds.has(p.project_id)));
      setSelectedIds(new Set());
      setSelectMode(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "恢复项目失败，请重试");
    } finally {
      setBatchRestoring(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-6xl mx-auto">
          <Loading message="加载项目列表..." />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-6xl mx-auto">
          <ErrorState message={error} retry={() => window.location.reload()} />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <PageHeader
          title={showRecycleBin ? "回收站" : "我的项目"}
          description={showRecycleBin ? "已删除项目会保留 30 天，到期后自动删除" : "管理和创建您的小说资产图项目"}
          actions={
            <div className="flex items-center gap-2">
              {showRecycleBin && selectMode ? (
                <Button
                  variant="outline"
                  className="border-neutral-700 text-white hover:bg-neutral-800"
                  onClick={cancelSelect}
                >
                  <X className="size-4 mr-2" />
                  取消选择
                </Button>
              ) : (
                <>
                  {!showRecycleBin && (
                    <Button asChild variant="outline" className="border-neutral-700 text-white hover:bg-neutral-800">
                      <Link href="/asset-library">
                        <Images className="size-4 mr-2" />
                        资产管理
                      </Link>
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    className="border-neutral-700 text-white hover:bg-neutral-800"
                    onClick={() => {
                      setLoading(true);
                      setError(null);
                      setShowRecycleBin((value) => !value);
                    }}
                  >
                    {showRecycleBin ? (
                      <>
                        <ChevronRight className="size-4 mr-2 rotate-180" />
                        返回项目
                      </>
                    ) : (
                      <>
                        <Trash2 className="size-4 mr-2" />
                        回收站
                      </>
                    )}
                  </Button>
                  {showRecycleBin && (
                    <Button
                      variant="outline"
                      className="border-neutral-700 text-white hover:bg-neutral-800"
                      onClick={() => setSelectMode(true)}
                    >
                      <CheckSquare className="size-4 mr-2" />
                      选择
                    </Button>
                  )}
                  {!showRecycleBin && (
                    <Link href="/projects/new">
                      <Button className="bg-blue-600 hover:bg-blue-500 text-white">
                        <Plus className="size-4 mr-2" />
                        创建新项目
                      </Button>
                    </Link>
                  )}
                </>
              )}
            </div>
          }
        />

        {projects.length === 0 ? (
          <EmptyState
            title={showRecycleBin ? "回收站为空" : "暂无项目"}
            description={showRecycleBin ? "删除的项目会在这里保留 30 天" : "点击上方按钮创建您的第一个资产图项目"}
            action={
              showRecycleBin
                ? { label: "返回项目", onClick: () => setShowRecycleBin(false) }
                : { label: "创建新项目", onClick: () => router.push("/projects/new") }
            }
          />
        ) : (
          <div className={["grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4", selectMode ? "pb-24" : ""].join(" ")}>
            {projects.map((project) => {
              const statusConf = STATUS_CONFIG[project.status as string] || STATUS_CONFIG.draft;
              const route = getProjectRoute(project);
              const canStartAnalysis = ["uploaded", "novel_uploaded"].includes(project.status as string);

              const isSelected = selectedIds.has(project.project_id);

              return (
                <Card
                  key={project.project_id}
                  className={[
                    "relative transition-colors group",
                    selectMode
                      ? "cursor-pointer border-neutral-700"
                      : "cursor-pointer border-neutral-700 hover:border-neutral-600",
                    isSelected
                      ? "bg-neutral-800 border-blue-500/60 ring-1 ring-blue-500/30"
                      : "bg-neutral-800",
                  ].join(" ")}
                  onClick={() => {
                    if (selectMode) {
                      toggleSelect(project.project_id);
                    } else {
                      router.push(route);
                    }
                  }}
                >
                  <CardContent className="p-5 space-y-4">
                    {/* Selection checkbox — top-left corner */}
                    {selectMode && (
                      <div className="absolute top-3 left-3 z-10">
                        {isSelected ? (
                          <CheckSquare className="size-5 text-blue-400" />
                        ) : (
                          <Square className="size-5 text-neutral-500" />
                        )}
                      </div>
                    )}

                    <div className={["flex items-start justify-between", selectMode ? "ml-7" : ""].join(" ")}>
                      <div className="space-y-1 flex-1 min-w-0">
                        <h3 className={[
                          "font-semibold text-lg truncate transition-colors",
                          selectMode ? "text-white" : "text-white group-hover:text-blue-400",
                        ].join(" ")}>
                          {project.title}
                        </h3>
                        <p className="text-neutral-500 text-xs">
                          {formatDate(project.created_at)}
                        </p>
                      </div>
                      <Badge variant={statusConf.variant} className="shrink-0 ml-2">
                        {statusConf.label}
                      </Badge>
                    </div>

                    {project.progress > 0 && project.progress < 100 && (
                      <div className={["space-y-1", selectMode ? "ml-7" : ""].join(" ")}>
                        <div className="flex justify-between text-xs text-neutral-400">
                          <span>生成进度</span>
                          <span>{project.progress}%</span>
                        </div>
                        <Progress value={project.progress} className="h-2" />
                      </div>
                    )}

                    <div className={["flex items-center gap-3 text-xs text-neutral-400", selectMode ? "ml-7" : ""].join(" ")}>
                      <span>{project.aspect_ratio}</span>
                      <span className="text-neutral-600">|</span>
                      <span>{project.generation_mode === "fast_preview" ? "快速" : "高质量"}</span>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-neutral-700">
                      <span className={["text-xs text-neutral-500", selectMode ? "ml-7" : ""].join(" ")}>
                        {project.style_mode === "manual" && project.manual_style
                          ? `风格: ${project.manual_style}`
                          : "智能风格"}
                      </span>
                      <div className="flex items-center gap-2">
                        {!showRecycleBin && !selectMode && canStartAnalysis && (
                          <Button
                            type="button"
                            size="sm"
                            className="bg-blue-600 text-white hover:bg-blue-500"
                            aria-label={`启动分析 ${project.title}`}
                            disabled={startingAnalysisId === project.project_id}
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              void handleStartAnalysis(project);
                            }}
                          >
                            {startingAnalysisId === project.project_id ? (
                              <Loader2 className="size-3.5 animate-spin" />
                            ) : (
                              <Play className="size-3.5" />
                            )}
                            开始分析
                          </Button>
                        )}
                        {showRecycleBin ? (
                          <>
                            <span className="text-xs text-red-300">{formatRecycleDeadline(project)}</span>
                            {!selectMode && (
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon-sm"
                                className="text-neutral-500 hover:text-blue-300 hover:bg-blue-950/30"
                                aria-label={`恢复项目 ${project.title}`}
                                disabled={restoringId === project.project_id}
                                onClick={(event) => {
                                  event.preventDefault();
                                  event.stopPropagation();
                                  void handleRestoreProject(project);
                                }}
                              >
                                {restoringId === project.project_id ? (
                                  <Loader2 className="size-4 animate-spin" />
                                ) : (
                                  <RotateCcw className="size-4" />
                                )}
                              </Button>
                            )}
                          </>
                        ) : (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            className="text-neutral-500 hover:text-red-300 hover:bg-red-950/30"
                            aria-label={`删除项目 ${project.title}`}
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              setProjectToDelete(project);
                            }}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        )}
                        {!selectMode && (
                          <ChevronRight className="size-4 text-neutral-600 group-hover:text-blue-400 transition-colors" />
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        <Modal
          open={!!projectToDelete}
          onOpenChange={(open) => {
            if (!open && !deletingId) setProjectToDelete(null);
          }}
          title="确认删除项目"
          description="删除后，该项目将进入回收站，并在 30 天后自动删除。"
          footer={
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                className="border-neutral-700 text-white hover:bg-neutral-700"
                onClick={() => setProjectToDelete(null)}
                disabled={!!deletingId}
              >
                取消
              </Button>
              <Button
                className="bg-red-600 hover:bg-red-500 text-white"
                onClick={handleDeleteProject}
                disabled={!!deletingId}
              >
                {deletingId ? (
                  <>
                    <Loader2 className="size-4 mr-2 animate-spin" />
                    删除中...
                  </>
                ) : (
                  <>
                    <Trash2 className="size-4 mr-2" />
                    确认删除
                  </>
                )}
              </Button>
            </div>
          }
        >
          <div className="space-y-3">
            <p className="text-sm text-neutral-300">
              项目「{projectToDelete?.title}」将移入回收站。30 天内可以恢复，超过 30 天后系统会自动删除。
            </p>
            <div className="flex items-start gap-2 rounded-lg border border-red-900/40 bg-red-950/30 p-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-red-400" />
              <p className="text-xs leading-5 text-red-200">
                删除项目可能影响正在进行的分析或生成任务。确认前请确保不再需要继续处理该项目。
              </p>
            </div>
          </div>
        </Modal>

        {/* ────────────────────────────────────────────────────────
            Selection mode — frosted glass bottom action bar
            ──────────────────────────────────────────────────────── */}
        {selectMode && (
          <div
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-[calc(100%-2rem)] max-w-xl
              rounded-3xl
              bg-gradient-to-b from-white/[0.06] via-white/[0.03] to-white/[0.01]
              backdrop-blur-xl backdrop-saturate-150
              border border-white/[0.10]
              shadow-[0_20px_40px_-8px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.06)]"
          >
            <div className="flex items-center justify-between px-6 py-4">
              <div className="flex items-center gap-3">
                {selectedIds.size === projects.length ? (
                  <Button
                    variant="outline"
                    className="border-neutral-600 text-neutral-300 hover:bg-neutral-700 hover:text-white"
                    onClick={deselectAll}
                  >
                    <Square className="size-4 mr-2" />
                    取消全选
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    className="border-neutral-600 text-neutral-300 hover:bg-neutral-700 hover:text-white"
                    onClick={selectAll}
                  >
                    <CheckSquare className="size-4 mr-2" />
                    全部勾选
                  </Button>
                )}
                <span className="text-sm text-neutral-400">
                  已选择 {selectedIds.size} 项
                </span>
              </div>
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  className="border-neutral-600 text-neutral-300 hover:bg-neutral-700 hover:text-white"
                  onClick={cancelSelect}
                  disabled={batchDeleting || batchRestoring}
                >
                  <X className="size-4 mr-2" />
                  取消
                </Button>
                {selectedIds.size > 0 && (
                  <>
                    <Button
                      className="bg-blue-600 hover:bg-blue-500 text-white"
                      onClick={handleBatchRestore}
                      disabled={batchDeleting || batchRestoring}
                    >
                      {batchRestoring ? (
                        <>
                          <Loader2 className="size-4 mr-2 animate-spin" />
                          恢复中...
                        </>
                      ) : (
                        <>
                          <RotateCcw className="size-4 mr-2" />
                          恢复
                        </>
                      )}
                    </Button>
                    <Button
                      className="bg-red-600 hover:bg-red-500 text-white"
                      onClick={() => setConfirmBatchDelete(true)}
                      disabled={batchDeleting || batchRestoring}
                    >
                      <Trash2 className="size-4 mr-2" />
                      删除
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ────────────────────────────────────────────────────────
            Permanent batch-delete confirmation modal
            ──────────────────────────────────────────────────────── */}
        <Modal
          open={confirmBatchDelete}
          onOpenChange={(open) => {
            if (!open && !batchDeleting) setConfirmBatchDelete(false);
          }}
          title="确认永久删除"
          description="此操作不可撤销，选中的项目将从数据库中彻底删除。"
          footer={
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                className="border-neutral-700 text-white hover:bg-neutral-700"
                onClick={() => setConfirmBatchDelete(false)}
                disabled={batchDeleting}
              >
                取消
              </Button>
              <Button
                className="bg-red-600 hover:bg-red-500 text-white"
                onClick={handleBatchPermanentDelete}
                disabled={batchDeleting}
              >
                {batchDeleting ? (
                  <>
                    <Loader2 className="size-4 mr-2 animate-spin" />
                    删除中...
                  </>
                ) : (
                  <>
                    <Trash2 className="size-4 mr-2" />
                    确认永久删除
                  </>
                )}
              </Button>
            </div>
          }
        >
          <div className="space-y-3">
            <p className="text-sm text-neutral-300">
              您已选择 <span className="text-white font-semibold">{selectedIds.size}</span> 个项目进行永久删除。
            </p>
            <div className="flex items-start gap-2 rounded-lg border border-red-900/40 bg-red-950/30 p-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-red-400" />
              <div className="space-y-1">
                <p className="text-xs leading-5 text-red-200">
                  永久删除后，项目及其所有相关数据（分析结果、角色、场景、道具和资产图）将被彻底清除，无法恢复。
                </p>
                <p className="text-xs leading-5 text-red-300 font-medium">
                  建议确认后再执行此操作。
                </p>
              </div>
            </div>
          </div>
        </Modal>
      </div>
    </main>
  );
}
