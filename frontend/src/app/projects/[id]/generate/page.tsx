"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/shared/ui/Loading";
import { ErrorState } from "@/shared/ui/ErrorState";
import { PageHeader } from "@/shared/ui/PageHeader";
import { getWorkflowStatus, startWorkflow } from "@/shared/api/workflow";
import { getProject } from "@/shared/api/projects";
import type { ProjectStatusResponse, ProjectResponse } from "@/shared/types";
import {
  Activity, Clock, CheckCircle2, XCircle, RefreshCw, AlertTriangle,
  Loader2, Play, Layers, ArrowRight,
} from "lucide-react";

const TASK_ICONS: Record<string, { icon: React.ReactNode; className: string }> = {
  pending: { icon: <Clock className="size-4" />, className: "text-neutral-500" },
  running: { icon: <Loader2 className="size-4 animate-spin" />, className: "text-blue-400" },
  success: { icon: <CheckCircle2 className="size-4" />, className: "text-green-400" },
  failed: { icon: <XCircle className="size-4" />, className: "text-red-400" },
  retrying: { icon: <RefreshCw className="size-4 animate-spin" />, className: "text-yellow-400" },
  needs_review: { icon: <AlertTriangle className="size-4" />, className: "text-orange-400" },
};

const TASK_LABELS: Record<string, string> = {
  pending: "等待中",
  running: "运行中",
  success: "已完成",
  failed: "失败",
  retrying: "重试中",
  needs_review: "需审核",
};

function isActiveStatus(status: string): boolean {
  return [
    "analyzing",
    "generating_assets",
    "generating_images",
  ].includes(status);
}

export default function GeneratePage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<ProjectStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const projectStatus = project?.status as string | undefined;
  const isRunning = projectStatus ? isActiveStatus(projectStatus) : false;

  const fetchStatus = useCallback(async () => {
    try {
      const [proj, wf] = await Promise.all([
        getProject(projectId),
        getWorkflowStatus(projectId),
      ]);
      setProject(proj);
      setWorkflowStatus(wf);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch status");
    }
  }, [projectId]);

  useEffect(() => {
    setLoading(true);
    fetchStatus().finally(() => setLoading(false));
  }, [fetchStatus]);

  useEffect(() => {
    if (isRunning) {
      intervalRef.current = setInterval(fetchStatus, 2000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isRunning, fetchStatus]);

  async function handleStart() {
    setStarting(true);
    try {
      await startWorkflow(projectId);
      await fetchStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Start failed");
    } finally {
      setStarting(false);
    }
  }

  if (loading) return <Loading message="加载生成进度..." />;
  if (error) return <ErrorState message={error} retry={() => window.location.reload()} />;
  if (!project) return <ErrorState message="项目不存在" />;

  const isCompleted = project.status === "completed";
  const isFailed = project.status === "failed";
  const canStart =
    projectStatus === "uploaded" ||
    project.status === "novel_uploaded" ||
    project.status === "analysis_confirmed";

  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <PageHeader
          title="生成进度"
          description={isCompleted ? "资产图生成完成" : isFailed ? "生成失败" : "监控角色、场景和道具资产图生成进度"}
          backHref={`/projects/${projectId}`}
        />

        {/* Overall Progress */}
        {workflowStatus && (
          <Card className="bg-neutral-800 border-neutral-700">
            <CardContent className="py-6 space-y-4">
              <div className="text-center">
                <div className="text-4xl font-bold text-white mb-1">
                  {workflowStatus.progress}%
                </div>
                <Progress value={workflowStatus.progress} className="h-3 max-w-md mx-auto" />
              </div>

              {workflowStatus.current_stage && (
                <div className="text-center">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <Activity className="size-5 text-blue-400" />
                    <span className="text-lg font-semibold text-white">
                      {workflowStatus.current_stage}
                    </span>
                  </div>
                  <div className="flex items-center justify-center gap-2 text-sm text-neutral-400">
                    <Layers className="size-4" />
                    <span>阶段 {workflowStatus.stage_index + 1} / {workflowStatus.total_stages}</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Start Button */}
        {canStart && !isRunning && (
          <div className="text-center">
            <Button
              size="lg"
              onClick={handleStart}
              disabled={starting}
              className="bg-blue-600 hover:bg-blue-500 text-white px-12 h-12 text-lg"
            >
              {starting ? (
                <><Loader2 className="size-5 mr-2 animate-spin" />启动中...</>
              ) : (
                <><Play className="size-5 mr-2" />开始生成</>
              )}
            </Button>
          </div>
        )}

        {/* Completed State */}
        {isCompleted && (
          <Card className="bg-green-950/30 border-green-800">
            <CardContent className="py-6 text-center space-y-4">
              <CheckCircle2 className="size-12 text-green-400 mx-auto" />
              <h2 className="text-xl font-bold text-green-400">生成完成!</h2>
              <p className="text-neutral-300">角色、场景和道具资产图已准备好</p>
              <Link href={`/projects/${projectId}/assets`}>
                <Button className="bg-green-600 hover:bg-green-500 text-white">
                  查看资产库 <ArrowRight className="size-4 ml-2" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}

        {/* Failed State */}
        {isFailed && (
          <Card className="bg-red-950/30 border-red-800">
            <CardContent className="py-6 text-center space-y-4">
              <XCircle className="size-12 text-red-400 mx-auto" />
              <h2 className="text-xl font-bold text-red-400">生成失败</h2>
              <p className="text-neutral-300">
                {workflowStatus?.error_message || "生成过程中出现错误，请重试"}
              </p>
              <Button onClick={handleStart} className="bg-red-600 hover:bg-red-500 text-white">
                <RefreshCw className="size-4 mr-2" />重新开始
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Task Status List */}
        {workflowStatus && workflowStatus.tasks.length > 0 && (
          <Card className="bg-neutral-800 border-neutral-700">
            <CardHeader>
              <CardTitle className="text-white">任务列表</CardTitle>
              <CardDescription>每个生成阶段的状态</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {workflowStatus.tasks.map((task) => {
                const iconConf = TASK_ICONS[task.state] || TASK_ICONS.pending;
                const label = TASK_LABELS[task.state] || task.state;

                return (
                  <div
                    key={task.task_id}
                    className={`p-4 rounded-lg border ${
                      task.state === "running" ? "border-blue-800 bg-blue-950/20" :
                      task.state === "failed" ? "border-red-800 bg-red-950/20" :
                      "border-neutral-700 bg-neutral-900/50"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <span className={iconConf.className}>{iconConf.icon}</span>
                        <span className="text-sm font-medium text-white">{task.name}</span>
                        <Badge
                          variant="outline"
                          className={`text-xs ${iconConf.className} border-current/30`}
                        >
                          {label}
                        </Badge>
                        {task.retry_count > 0 && (
                          <Badge variant="outline" className="text-xs text-yellow-400 border-yellow-800">
                            <RefreshCw className="size-3 mr-1" />重试 {task.retry_count}/{task.max_retries}
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-neutral-500">{task.progress}%</span>
                    </div>
                    <Progress value={task.progress} className="h-1.5" />
                    {task.error_message && (
                      <p className="text-xs text-red-400 mt-2 bg-red-950/30 rounded p-2">
                        {task.error_message}
                      </p>
                    )}
                    {task.completed_at && (
                      <p className="text-xs text-neutral-600 mt-1">
                        完成于 {new Date(task.completed_at).toLocaleTimeString("zh-CN")}
                      </p>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}
