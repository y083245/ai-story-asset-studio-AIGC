"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertCircle, ArrowRight, CheckCircle2, Clock, Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/shared/ui/PageHeader";
import { ErrorState } from "@/shared/ui/ErrorState";
import { getWorkflowStatus } from "@/shared/api/workflow";
import { cn } from "@/lib/utils";
import type { ProjectStatusResponse, TaskStatus } from "@/shared/types";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

const MODULES = [
  { activity: "parse_novel", stage: "parsing_novel", label: "解析小说", note: "读取粘贴文本并建立小说基础结构" },
  { activity: "clean_text", stage: "cleaning_text", label: "清洗文本", note: "按上传文本清理空行、乱码和冗余内容" },
  { activity: "detect_genre", stage: "detecting_genre", label: "风格识别", note: "DeepSeek 判断小说风格并选择模板" },
  { activity: "extract_characters", stage: "extracting_characters", label: "角色形象提取", note: "逐项提取角色外貌、服装和资产图提示词" },
  { activity: "extract_scenes", stage: "extracting_scenes", label: "场景提取", note: "逐项提取场景锚点、光线、前中后景" },
  { activity: "extract_props", stage: "extracting_props", label: "道具提取", note: "逐项提取材质、状态时间线、道具图提示词" },
  { activity: "build_story_bible", stage: "building_story_bible", label: "故事设定集", note: "汇总人物、场景、道具和世界观" },
  { activity: "publish_analysis", stage: "publishing_analysis", label: "发布分析结果", note: "写入角色库、场景库、道具库和故事设定集" },
];

function moduleState(module: (typeof MODULES)[number], status: ProjectStatusResponse | null): TaskStatus["state"] {
  const task = status?.tasks.find((item) => item.task_id === module.activity);
  if (task) return task.state;
  if (!status) return "pending";
  const currentIndex = MODULES.findIndex((item) => item.stage === status.current_stage);
  const moduleIndex = MODULES.findIndex((item) => item.activity === module.activity);
  if (status.status === "completed") return "success";
  if (status.status === "failed" && module.stage === status.current_stage) return "failed";
  if (currentIndex === moduleIndex) return "running";
  if (currentIndex > moduleIndex) return "success";
  return "pending";
}

function stateIcon(state: TaskStatus["state"]) {
  if (state === "success") return <CheckCircle2 className="size-4 text-emerald-400" />;
  if (state === "failed") return <AlertCircle className="size-4 text-red-400" />;
  if (state === "running") return <Loader2 className="size-4 animate-spin text-blue-400" />;
  return <Clock className="size-4 text-neutral-500" />;
}

function stateLabel(state: TaskStatus["state"]) {
  if (state === "success") return "已完成";
  if (state === "failed") return "失败";
  if (state === "running") return "提取中";
  return "待执行";
}

function formatSummary(summary?: Record<string, unknown>) {
  if (!summary) return "";
  return Object.entries(summary)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.length : String(value)}`)
    .join(" · ");
}

export default function AnalysisProgressPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const [status, setStatus] = useState<ProjectStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function poll() {
      try {
        const next = await getWorkflowStatus(projectId);
        if (cancelled) return;
        setStatus(next);
        setError(null);
        if (TERMINAL_STATUSES.has(next.status) && timer) {
          clearInterval(timer);
          timer = null;
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "获取分析状态失败");
      }
    }

    void poll();
    timer = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [projectId]);

  const progress = status?.progress ?? 0;
  const currentMessage = status?.message || "正在连接分析任务...";
  const taskById = useMemo(() => new Map((status?.tasks ?? []).map((task) => [task.task_id, task])), [status]);

  if (error && !status) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="mx-auto max-w-5xl">
          <ErrorState message={error} retry={() => window.location.reload()} />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <PageHeader
          title="分析详情"
          description="DeepSeek 正按风格模板逐模块提取内容，完成一项显示一项。"
          backHref={`/projects/${projectId}/upload`}
        />

        <Card className="border-neutral-700 bg-neutral-800">
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <CardTitle className="text-white">当前状态</CardTitle>
              <Badge variant="outline" className="border-neutral-600 text-neutral-300">
                {status?.status || "连接中"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between gap-4 text-sm">
              <span className="text-neutral-300">{currentMessage}</span>
              <span className="font-medium text-white">{progress}%</span>
            </div>
            <Progress value={progress} className="h-2 bg-neutral-700" />
            {status?.error_message && (
              <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-4 py-3 text-sm text-red-300">
                {status.error_message}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-3">
          {MODULES.map((module) => {
            const state = moduleState(module, status);
            const task = taskById.get(module.activity);
            const summary = formatSummary(task?.result_summary);
            return (
              <Card
                key={module.activity}
                className={cn(
                  "border-neutral-700 bg-neutral-800/80",
                  state === "running" && "border-blue-500/60 bg-blue-950/20",
                  state === "success" && "border-emerald-900/50",
                  state === "failed" && "border-red-900/60 bg-red-950/20",
                )}
              >
                <CardContent className="flex items-start gap-4 p-4">
                  <div className="mt-0.5">{stateIcon(state)}</div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-medium text-white">{module.label}</h3>
                      <Badge variant="outline" className="border-neutral-600 text-xs text-neutral-300">
                        {stateLabel(state)}
                      </Badge>
                    </div>
                    <p className="mt-1 text-sm text-neutral-400">{module.note}</p>
                    {summary && <p className="mt-2 text-xs text-neutral-500">{summary}</p>}
                    {task?.error_message && <p className="mt-2 text-xs text-red-400">{task.error_message}</p>}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        <div className="flex justify-end gap-3">
          <Button variant="outline" className="border-neutral-600 text-neutral-300" onClick={() => window.location.reload()}>
            <RefreshCw className="mr-2 size-4" />
            刷新
          </Button>
          <Button
            className="bg-blue-600 text-white hover:bg-blue-500"
            disabled={status?.status !== "completed"}
            onClick={() => router.push(`/projects/${projectId}/analysis`)}
          >
            查看分析结果
            <ArrowRight className="ml-2 size-4" />
          </Button>
        </div>
      </div>
    </main>
  );
}
