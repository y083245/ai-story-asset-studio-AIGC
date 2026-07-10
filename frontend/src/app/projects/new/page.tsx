"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/shared/ui/PageHeader";
import { createProject } from "@/shared/api/projects";
import type { AspectRatio, StyleMode, GenerationMode } from "@/shared/types";
import { Monitor, Sparkles, Zap } from "lucide-react";

const ASPECT_RATIOS: { value: AspectRatio; label: string; description: string }[] = [
  { value: "9:16", label: "9:16 竖屏", description: "手机端" },
  { value: "16:9", label: "16:9 横屏", description: "电脑端" },
];

const STYLE_MODES: { value: StyleMode; label: string; description: string }[] = [
  { value: "auto", label: "智能识别", description: "AI 自动分析小说风格" },
  { value: "manual", label: "手动指定", description: "自行输入风格描述" },
];

const GENERATION_MODES: { value: GenerationMode; label: string; description: string; icon: React.ReactNode }[] = [
  { value: "fast_preview", label: "快速生成", description: "更快的生成速度，适合预览", icon: <Zap className="size-4" /> },
  { value: "high_quality", label: "高质量", description: "最佳画面质量，适合正式资产", icon: <Sparkles className="size-4" /> },
];

export default function NewProjectPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("9:16");
  const [styleMode, setStyleMode] = useState<StyleMode>("auto");
  const [manualStyle, setManualStyle] = useState("");
  const [generationMode, setGenerationMode] = useState<GenerationMode>("high_quality");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function validate(): boolean {
    const newErrors: Record<string, string> = {};
    if (!title.trim()) {
      newErrors.title = "请输入项目名称";
    } else if (title.length > 100) {
      newErrors.title = "项目名称不能超过 100 个字符";
    }
    if (styleMode === "manual" && !manualStyle.trim()) {
      newErrors.manualStyle = "请输入风格描述";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      const project = await createProject({
        title: title.trim(),
        aspect_ratio: aspectRatio,
        style_mode: styleMode,
        manual_style: styleMode === "manual" ? manualStyle.trim() : undefined,
        generation_mode: generationMode,
      });
      router.push(`/projects/${project.project_id}/upload`);
    } catch (err) {
      setErrors({ submit: err instanceof Error ? err.message : "创建失败，请重试" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-2xl mx-auto space-y-8">
        <PageHeader
          title="创建新项目"
          description="设置资产图项目参数，开始小说视觉整理"
          backHref="/projects"
        />

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Project Name */}
          <Card className="bg-neutral-800 border-neutral-700">
            <CardHeader>
              <CardTitle className="text-white">项目名称</CardTitle>
              <CardDescription>给您的资产图项目起个名字</CardDescription>
            </CardHeader>
            <CardContent>
              <Input
                placeholder="输入项目名称，如：星辰大海"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={100}
                className="bg-neutral-900 border-neutral-700 text-white placeholder:text-neutral-500"
              />
              {errors.title && <p className="text-red-400 text-sm mt-2">{errors.title}</p>}
              <p className="text-neutral-500 text-xs mt-1">{title.length}/100</p>
            </CardContent>
          </Card>

          {/* Aspect Ratio */}
          <Card className="bg-neutral-800 border-neutral-700">
            <CardHeader>
              <CardTitle className="text-white">画幅比例</CardTitle>
              <CardDescription>选择资产图的默认画面比例</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                {ASPECT_RATIOS.map((ar) => (
                  <button
                    key={ar.value}
                    type="button"
                    onClick={() => setAspectRatio(ar.value)}
                    className={`p-4 rounded-lg border text-left transition-all ${
                      aspectRatio === ar.value
                        ? "border-blue-500 bg-blue-500/10 text-white"
                        : "border-neutral-700 bg-neutral-900 text-neutral-300 hover:border-neutral-600"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Monitor className="size-4 text-blue-400" />
                      <span className="font-semibold">{ar.label}</span>
                    </div>
                    <span className="text-xs text-neutral-400">{ar.description}</span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Style Mode */}
          <Card className="bg-neutral-800 border-neutral-700">
            <CardHeader>
              <CardTitle className="text-white">风格选择</CardTitle>
              <CardDescription>AI 自动识别风格或自行指定</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {STYLE_MODES.map((sm) => (
                  <button
                    key={sm.value}
                    type="button"
                    onClick={() => setStyleMode(sm.value)}
                    className={`p-4 rounded-lg border text-left transition-all ${
                      styleMode === sm.value
                        ? "border-blue-500 bg-blue-500/10 text-white"
                        : "border-neutral-700 bg-neutral-900 text-neutral-300 hover:border-neutral-600"
                    }`}
                  >
                    <span className="font-semibold block mb-1">{sm.label}</span>
                    <span className="text-xs text-neutral-400">{sm.description}</span>
                  </button>
                ))}
              </div>
              {styleMode === "manual" && (
                <div>
                  <Input
                    placeholder="描述您想要的视觉风格，如：中国传统水墨风格、赛博朋克..."
                    value={manualStyle}
                    onChange={(e) => setManualStyle(e.target.value)}
                    className="bg-neutral-900 border-neutral-700 text-white placeholder:text-neutral-500"
                  />
                  {errors.manualStyle && <p className="text-red-400 text-sm mt-2">{errors.manualStyle}</p>}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Generation Mode */}
          <Card className="bg-neutral-800 border-neutral-700">
            <CardHeader>
              <CardTitle className="text-white">生成模式</CardTitle>
              <CardDescription>选择生成速度与质量平衡</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                {GENERATION_MODES.map((gm) => (
                  <button
                    key={gm.value}
                    type="button"
                    onClick={() => setGenerationMode(gm.value)}
                    className={`p-4 rounded-lg border text-left transition-all ${
                      generationMode === gm.value
                        ? "border-blue-500 bg-blue-500/10 text-white"
                        : "border-neutral-700 bg-neutral-900 text-neutral-300 hover:border-neutral-600"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-blue-400">{gm.icon}</span>
                      <span className="font-semibold">{gm.label}</span>
                    </div>
                    <span className="text-xs text-neutral-400">{gm.description}</span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Error */}
          {errors.submit && (
            <div className="bg-red-950/50 border border-red-800 rounded-lg p-3">
              <p className="text-red-400 text-sm">{errors.submit}</p>
            </div>
          )}

          {/* Submit */}
          <Button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white h-12 text-base"
          >
            {loading ? "创建中..." : "创建项目"}
          </Button>
        </form>
      </div>
    </main>
  );
}
