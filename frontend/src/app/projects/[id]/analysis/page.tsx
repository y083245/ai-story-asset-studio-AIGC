"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/shared/ui/Loading";
import { ErrorState } from "@/shared/ui/ErrorState";
import { PageHeader } from "@/shared/ui/PageHeader";
import { getAnalysis } from "@/shared/api/analysis";
import { startAnalysis } from "@/shared/api/workflow";
import { cn } from "@/lib/utils";
import type {
  AnalysisResponse,
  StyleCandidate,
  CharacterReference,
  SceneReference,
  PropReference,
} from "@/shared/types";
import {
  ArrowRight,
  Sparkles,
  BookOpen,
  Swords,
  Heart,
  Globe,
  Users,
  MapPin,
  Box,
  Palette,
  Check,
  AlertTriangle,
  Play,
  Upload,
  Loader2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Confidence badge helper
// ---------------------------------------------------------------------------

function confidenceColor(score: number): string {
  const normalized = clampConfidence(score);
  if (normalized >= 0.75) return "bg-green-500/20 text-green-400 border-green-500/30";
  if (normalized >= 0.5) return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
  return "bg-red-500/20 text-red-400 border-red-500/30";
}

function clampConfidence(score: number): number {
  if (!Number.isFinite(score)) return 0;
  return Math.min(Math.max(score, 0), 1);
}

// ---------------------------------------------------------------------------
// Style candidate card
// ---------------------------------------------------------------------------

function StyleCandidateCard({
  candidate,
  selected,
  onSelect,
}: {
  candidate: StyleCandidate;
  selected: boolean;
  onSelect: () => void;
}) {
  const confidence = clampConfidence(candidate.confidence);
  return (
    <button
      type="button"
      className={cn(
        "w-full text-left p-4 rounded-xl border transition-all cursor-pointer",
        selected
          ? "border-blue-400 bg-blue-500/10 ring-1 ring-blue-400"
          : "border-neutral-700 bg-neutral-800 hover:border-neutral-600 hover:bg-neutral-750"
      )}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {selected && <Check className="size-4 text-blue-400 shrink-0" />}
          <h4 className="text-white font-semibold">{candidate.style_name}</h4>
        </div>
        <Badge
          variant="outline"
          className={cn("text-xs", confidenceColor(confidence))}
        >
          {Math.round(confidence * 100)}% 匹配
        </Badge>
      </div>
      <p className="text-sm text-neutral-400 mb-2">{candidate.description}</p>
      <div className="flex flex-wrap gap-1.5">
        {candidate.example_keywords.map((kw) => (
          <Badge
            key={kw}
            variant="secondary"
            className="bg-neutral-700 text-neutral-300 text-xs"
          >
            {kw}
          </Badge>
        ))}
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// List display helpers
// ---------------------------------------------------------------------------

function CharacterList({ characters }: { characters: CharacterReference[] }) {
  if (!characters.length) return null;
  const roleLabel: Record<string, string> = {
    protagonist: "主角",
    antagonist: "反派",
    supporting: "配角",
  };
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {characters.map((ch) => (
        <div
          key={ch.character_id}
          className="flex items-start gap-3 p-3 rounded-lg bg-neutral-800/50 border border-neutral-700/50"
        >
          <div className="size-9 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-sm font-bold shrink-0">
            {ch.name.charAt(0)}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-white font-medium text-sm">{ch.name}</span>
              <Badge variant="outline" className="text-xs border-blue-500/30 text-blue-300">
                {roleLabel[ch.role] || ch.role}
              </Badge>
            </div>
            <p className="text-xs text-neutral-400 line-clamp-2">
              {ch.description}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

function SceneList({ scenes }: { scenes: SceneReference[] }) {
  if (!scenes.length) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {scenes.map((sc) => (
        <div
          key={sc.scene_id}
          className="p-3 rounded-lg bg-neutral-800/50 border border-neutral-700/50 space-y-2"
        >
          <div className="flex items-center gap-2">
            <span className="text-white font-medium text-sm">{sc.name}</span>
            {sc.mood && (
              <Badge variant="outline" className="text-xs text-purple-300 border-purple-500/30">
                {sc.mood}
              </Badge>
            )}
          </div>
          <p className="text-xs text-neutral-400 line-clamp-2">
            {sc.description}
          </p>
          {sc.time_period && (
            <p className="text-xs text-neutral-500">{sc.time_period}</p>
          )}
          {sc.fixed_anchors.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {sc.fixed_anchors.map((a) => (
                <Badge
                  key={a}
                  variant="secondary"
                  className="text-xs bg-neutral-700 text-neutral-300"
                >
                  {a}
                </Badge>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function PropList({ props }: { props: PropReference[] }) {
  if (!props.length) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {props.map((pr) => (
        <div
          key={pr.prop_id}
          className="flex items-start gap-3 p-3 rounded-lg bg-neutral-800/50 border border-neutral-700/50"
        >
          <div className="size-9 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center text-sm shrink-0">
            <Box className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-white font-medium text-sm">{pr.name}</span>
              <span className="text-xs text-neutral-500">{pr.function}</span>
            </div>
            <p className="text-xs text-neutral-400 line-clamp-2">
              {pr.description}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Color palette display
// ---------------------------------------------------------------------------

function ColorPalette({ colors }: { colors: string[] }) {
  if (!colors.length) return null;
  return (
    <div className="flex flex-wrap gap-3">
      {colors.map((color, i) => {
        // Format: "name #hex" or just "#hex"
        const parts = color.split(/\s+/);
        const name = parts.length > 1 ? parts.slice(0, -1).join(" ") : "";
        const hex = parts[parts.length - 1];
        return (
          <div key={i} className="flex items-center gap-2">
            <div
              className="size-8 rounded-full border-2 border-neutral-600 shrink-0"
              style={{ backgroundColor: hex.startsWith("#") ? hex : `#${hex}` }}
            />
            <div>
              {name && <p className="text-xs text-white">{name}</p>}
              <p className="text-xs text-neutral-500 font-mono">{hex}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="bg-neutral-800 border-neutral-700">
      <CardHeader>
        <CardTitle className="text-white text-base flex items-center gap-2">
          <Icon className="size-4 text-blue-400" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function AnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  // Style candidate selection
  const [selectedStyle, setSelectedStyle] = useState<string | null>(null);

  useEffect(() => {
    getAnalysis(projectId)
      .then((data) => {
        setAnalysis(data);
        if (data.visual_style) setSelectedStyle(data.visual_style);
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "加载分析数据失败")
      )
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleStartAnalysis = useCallback(async () => {
    setStarting(true);
    setNotice(null);
    try {
      const response = await startAnalysis(projectId);
      setError(null);
      if (response.status === "completed") {
        setNotice("故事分析已完成，正在重新加载结果。");
        window.location.reload();
        return;
      }
      router.push(`/projects/${projectId}/analysis-progress`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动 StoryEngine 失败");
    } finally {
      setStarting(false);
    }
  }, [projectId, router]);

  const handleConfirmStyle = useCallback(() => {
    if (!selectedStyle || !analysis) return;
    setAnalysis({
      ...analysis,
      visual_style: selectedStyle,
      style_confidence: Math.max(analysis.style_confidence, 0.75),
      style_candidates: undefined,
    });
  }, [selectedStyle, analysis]);

  if (loading) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-6xl mx-auto min-h-[400px] flex items-center justify-center">
          <Loading message="加载故事分析..." />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-6xl mx-auto space-y-6">
          <PageHeader
            title="故事分析"
            description="当前项目还没有可展示的完整故事分析"
            backHref={`/projects/${projectId}`}
          />
          <Card className="border-yellow-700 bg-yellow-950/20">
            <CardContent className="space-y-5 p-6">
              <div className="flex items-start gap-4">
                <div className="rounded-full bg-yellow-500/15 p-3 text-yellow-300">
                  <AlertTriangle className="size-6" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-lg font-semibold text-white">
                    故事分析未完成
                  </h2>
                  <p className="max-w-2xl text-sm leading-6 text-neutral-300">
                    {error}
                  </p>
                  {notice && (
                    <p className="text-sm text-blue-300">
                      {notice}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button
                  className="bg-blue-600 text-white hover:bg-blue-500"
                  onClick={handleStartAnalysis}
                  disabled={starting}
                >
                  {starting ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 size-4" />
                  )}
                  启动 StoryEngine
                </Button>
                <Button
                  variant="outline"
                  onClick={() => router.push(`/projects/${projectId}/upload`)}
                >
                  <Upload className="mr-2 size-4" />
                  返回上传页
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    );
  }

  if (!analysis) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-6xl mx-auto">
          <ErrorState message="分析数据为空" />
        </div>
      </main>
    );
  }

  const showStyleCandidates =
    analysis.style_candidates &&
    analysis.style_candidates.length > 0 &&
    analysis.style_confidence < 0.75;

  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* --- Header --- */}
        <PageHeader
          title="故事分析"
          description="AI 自动分析故事要素与视觉风格"
          backHref={`/projects/${projectId}`}
        />

        {/* --- 1. Genre + Style --- */}
        <Card className="bg-neutral-800 border-neutral-700">
          <CardContent className="p-5">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <Sparkles className="size-5 text-blue-400" />
                <span className="text-white font-semibold">类型: </span>
                <span className="text-white">{analysis.genre}</span>
              </div>
              <span className="text-neutral-600">|</span>
              <div className="flex items-center gap-2">
                <span className="text-white font-semibold">风格: </span>
                <span className="text-white">
                  {analysis.visual_style || "待确认"}
                </span>
                <Badge
                  variant="outline"
                  className={cn(
                    "text-xs",
                    confidenceColor(analysis.style_confidence)
                  )}
                >
                  置信度 {Math.round(clampConfidence(analysis.style_confidence) * 100)}%
                </Badge>
              </div>
              <span className="text-neutral-600">|</span>
              <span className="text-xs text-neutral-400">
                {analysis.characters.length} 个角色 · {analysis.scenes.length} 个场景 · {analysis.props.length} 个道具
              </span>
            </div>
          </CardContent>
        </Card>

        {/* --- 2. Style Candidates --- */}
        {showStyleCandidates && (
          <Card className="bg-neutral-800 border-neutral-700 border-yellow-500/30">
            <CardHeader>
              <CardTitle className="text-white text-base flex items-center gap-2">
                <Sparkles className="size-4 text-yellow-400" />
                风格候选（请选择最匹配的风格）
              </CardTitle>
              <CardDescription className="text-neutral-400">
                AI 对最佳风格不确定，请从以下候选中选择一个
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {analysis.style_candidates!.map((c) => (
                  <StyleCandidateCard
                    key={c.style_name}
                    candidate={c}
                    selected={selectedStyle === c.style_name}
                    onSelect={() => setSelectedStyle(c.style_name)}
                  />
                ))}
              </div>
              <div className="flex justify-end">
                <Button
                  className="bg-blue-600 hover:bg-blue-500 text-white"
                  disabled={!selectedStyle}
                  onClick={handleConfirmStyle}
                >
                  <Check className="size-4 mr-2" />
                  确认风格
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* --- 3. Story Summary --- */}
        <Section icon={BookOpen} title="故事概要">
          <p className="text-sm text-neutral-300 leading-relaxed">
            {analysis.story_summary}
          </p>
        </Section>

        {/* --- 4. Main Conflict --- */}
        <Section icon={Swords} title="核心冲突">
          <p className="text-sm text-neutral-300 leading-relaxed">
            {analysis.main_conflict}
          </p>
        </Section>

        {/* --- 5. Emotional Tone + World Setting --- */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Section icon={Heart} title="情感基调">
            <p className="text-sm text-neutral-300">{analysis.emotional_tone}</p>
          </Section>
          <Section icon={Globe} title="世界观">
            <div className="space-y-2">
              <p className="text-sm text-neutral-300 leading-relaxed">
                {analysis.world_setting}
              </p>
              <p className="text-xs text-neutral-500">
                时间设定: {analysis.time_period}
              </p>
            </div>
          </Section>
        </div>

        {/* --- 6. Characters --- */}
        <Section icon={Users} title={`角色列表 (${analysis.characters.length})`}>
          <CharacterList characters={analysis.characters} />
        </Section>

        {/* --- 7. Scenes --- */}
        <Section icon={MapPin} title={`场景列表 (${analysis.scenes.length})`}>
          <SceneList scenes={analysis.scenes} />
        </Section>

        {/* --- 8. Props --- */}
        <Section icon={Box} title={`道具列表 (${analysis.props.length})`}>
          <PropList props={analysis.props} />
        </Section>

        {/* --- 9. Color Palette --- */}
        <Section icon={Palette} title="色彩方案">
          <ColorPalette colors={analysis.color_palette} />
        </Section>

        {/* --- 10. Composition Language --- */}
        <Section icon={Palette} title="构图语言">
          {analysis.composition_language.length > 0 ? (
            <ul className="list-disc list-inside space-y-1">
              {analysis.composition_language.map((item, i) => (
                <li key={i} className="text-sm text-neutral-300">
                  {item}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-neutral-500">暂无构图语言设定</p>
          )}
        </Section>

        {/* --- 11. Action Button --- */}
        <div className="flex justify-end pt-2">
          <Button
            className="bg-blue-600 hover:bg-blue-500 text-white"
            disabled={showStyleCandidates && !selectedStyle}
            onClick={() => router.push(`/projects/${projectId}/assets`)}
          >
            确认并继续
            <ArrowRight className="size-4 ml-2" />
          </Button>
        </div>
      </div>
    </main>
  );
}
