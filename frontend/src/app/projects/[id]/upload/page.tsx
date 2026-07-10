"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Loading } from "@/shared/ui/Loading";
import { ErrorState } from "@/shared/ui/ErrorState";
import { PageHeader } from "@/shared/ui/PageHeader";
import { getProject } from "@/shared/api/projects";
import { uploadNovel } from "@/shared/api/novels";
import { startAnalysis } from "@/shared/api/workflow";
import { cn } from "@/lib/utils";
import type { ProjectResponse, NovelIntakeResponse, PreprocessReportItem } from "@/shared/types";
import {
  ArrowRight,
  FileText,
  Upload,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Word count validation
// ---------------------------------------------------------------------------

const MIN_WORDS = 1000;
const MAX_WORDS = 10000;

function countWords(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  // Count Chinese characters + whitespace-separated words
  const chineseChars = (trimmed.match(/[一-鿿]/g) || []).length;
  const nonChinese = trimmed
    .replace(/[一-鿿]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const englishWords = nonChinese ? nonChinese.split(/\s+/).length : 0;
  return chineseChars + englishWords;
}

// ---------------------------------------------------------------------------
// Preprocess report section
// ---------------------------------------------------------------------------

function PreprocessReport({ report }: { report: PreprocessReportItem }) {
  const items: { label: string; value: string | number }[] = [
    { label: "原始字数", value: report.original_word_count },
    { label: "清洗后字数", value: report.clean_word_count },
    { label: "移除广告", value: `${report.ads_removed} 处` },
    { label: "移除页码", value: `${report.page_numbers_removed} 处` },
    { label: "移除乱码行", value: `${report.garbled_lines_removed} 处` },
    { label: "移除空行", value: `${report.blank_lines_removed} 处` },
    { label: "编码检测", value: report.encoding_detected },
    { label: "输入类型", value: report.input_type },
  ];

  return (
    <Card className="bg-neutral-800 border-neutral-700">
      <CardHeader>
        <CardTitle className="text-white text-base flex items-center gap-2">
          <CheckCircle2 className="size-4 text-green-400" />
          预处理报告
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          {items.map((item) => (
            <div key={item.label} className="flex justify-between items-center">
              <span className="text-sm text-neutral-400">{item.label}</span>
              <span className="text-sm text-white font-medium">{item.value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function NovelUploadPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  // --- Project info ---
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  // --- Input state ---
  const [activeTab, setActiveTab] = useState("text");
  const [textInput, setTextInput] = useState("");

  // --- Submit state ---
  const [uploading, setUploading] = useState(false);
  const [startingAnalysis, setStartingAnalysis] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<NovelIntakeResponse | null>(null);

  // --- Derived ---
  const wordCount = useMemo(() => countWords(textInput), [textInput]);
  const wordValid = wordCount >= MIN_WORDS && wordCount <= MAX_WORDS;
  const hasTextInput = activeTab === "text" && textInput.trim().length > 0 && wordValid;
  const canSubmit = hasTextInput && !uploading;

  // --- Fetch project on mount ---
  useEffect(() => {
    getProject(projectId)
      .then(setProject)
      .catch((e) =>
        setPageError(e instanceof Error ? e.message : "加载项目失败")
      )
      .finally(() => setPageLoading(false));
  }, [projectId]);

  // --- Submit ---
  const handleSubmit = useCallback(async () => {
    setUploadError(null);
    setUploading(true);

    try {
      let result: NovelIntakeResponse;
      if (activeTab === "text") {
        result = await uploadNovel(projectId, {
          input_type: "text",
          text: textInput.trim(),
        });
      } else {
        throw new Error("文件上传暂未接入后端存储，请先使用粘贴文本。");
      }
      setUploadResult(result);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "上传失败，请重试");
    } finally {
      setUploading(false);
    }
  }, [projectId, activeTab, textInput]);

  const handleStartAnalysis = useCallback(async () => {
    setUploadError(null);
    setStartingAnalysis(true);

    try {
      const response = await startAnalysis(projectId);
      router.push(
        response.status === "completed"
          ? `/projects/${projectId}/analysis`
          : `/projects/${projectId}/analysis-progress`
      );
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "启动 StoryEngine 失败，请重试");
    } finally {
      setStartingAnalysis(false);
    }
  }, [projectId, router]);

  // --- Render: loading ---
  if (pageLoading) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-4xl mx-auto">
          <Loading message="加载项目信息..." />
        </div>
      </main>
    );
  }

  // --- Render: error ---
  if (pageError) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-4xl mx-auto">
          <ErrorState
            message={pageError}
            retry={() => window.location.reload()}
          />
        </div>
      </main>
    );
  }

  // --- Render: success ---
  if (uploadResult) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-4xl mx-auto space-y-8">
          <PageHeader
            title="上传成功"
            description={`小说「${uploadResult.title}」已上传，可手动启动 StoryEngine 提取分析内容`}
            backHref={`/projects/${projectId}`}
          />

          <Card className="bg-neutral-800 border-neutral-700 border-green-500/30">
            <CardContent className="p-6 space-y-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-full bg-green-500/10">
                  <CheckCircle2 className="size-6 text-green-400" />
                </div>
                <div>
                  <h3 className="text-white font-semibold text-lg">
                    {uploadResult.title}
                  </h3>
                  <p className="text-sm text-neutral-400">
                    {uploadResult.word_count} 字 · {uploadResult.chapter_list.length} 章节
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <PreprocessReport report={uploadResult.preprocess_report} />

          {uploadError && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-950/30 rounded-lg px-4 py-3">
              <AlertCircle className="size-4 shrink-0" />
              {uploadError}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              className="border-neutral-700 text-white hover:bg-neutral-800"
              onClick={() => router.push(`/projects/${projectId}/analysis`)}
            >
              进入分析页
              <ArrowRight className="size-4 ml-2" />
            </Button>
            <Button
              className="bg-blue-600 hover:bg-blue-500 text-white"
              onClick={handleStartAnalysis}
              disabled={startingAnalysis}
            >
              {startingAnalysis ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  启动中...
                </>
              ) : (
                "启动 StoryEngine"
              )}
            </Button>
          </div>
        </div>
      </main>
    );
  }

  // --- Render: main form ---
  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <PageHeader
          title="上传小说"
          description={project ? `项目: ${project.title} — 请提供您的小说文本` : "请提供您的小说文本"}
          backHref={`/projects/${projectId}`}
        />

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="bg-neutral-800 border border-neutral-700 p-1 rounded-lg">
            <TabsTrigger
              value="text"
              className="data-[state=active]:bg-neutral-700 data-[state=active]:text-white text-neutral-400"
            >
              <FileText className="size-4 mr-2" />
              粘贴文本
            </TabsTrigger>
            <TabsTrigger
              value="file"
              className="data-[state=active]:bg-neutral-700 data-[state=active]:text-white text-neutral-400"
            >
              <Upload className="size-4 mr-2" />
              上传文件
            </TabsTrigger>
          </TabsList>

          {/* ---- TEXT TAB ---- */}
          <TabsContent value="text" className="mt-4 space-y-4">
            <Card className="bg-neutral-800 border-neutral-700">
              <CardContent className="p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-neutral-300">
                    小说文本
                  </label>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "text-sm font-mono",
                        wordCount === 0
                          ? "text-neutral-500"
                          : wordValid
                            ? "text-green-400"
                            : "text-red-400"
                      )}
                    >
                      {wordCount} / {MIN_WORDS}-{MAX_WORDS} 字
                    </span>
                    {wordCount > 0 &&
                      (wordValid ? (
                        <CheckCircle2 className="size-4 text-green-400" />
                      ) : (
                        <AlertCircle className="size-4 text-red-400" />
                      ))}
                  </div>
                </div>

                <Textarea
                  className="min-h-[320px] max-h-[600px] bg-neutral-900 border-neutral-700 text-white placeholder-neutral-500 overflow-y-auto field-sizing-fixed"
                  placeholder="在此粘贴您的小说文本（1000-10000 字）..."
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                />

                {wordCount > 0 && !wordValid && (
                  <div className="flex items-center gap-2 text-red-400 text-sm bg-red-950/30 rounded-lg px-3 py-2">
                    <AlertCircle className="size-4 shrink-0" />
                    {wordCount < MIN_WORDS
                      ? `字数不足，还差 ${MIN_WORDS - wordCount} 字`
                      : `字数超出限制，多出 ${wordCount - MAX_WORDS} 字`}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ---- FILE TAB ---- */}
          <TabsContent value="file" className="mt-4 space-y-4">
            <Card className="bg-neutral-800 border-neutral-700">
              <CardContent className="p-5 space-y-3">
                <div className="flex items-start gap-3 rounded-lg border border-yellow-500/30 bg-yellow-950/20 px-4 py-3">
                  <AlertCircle className="size-5 text-yellow-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-yellow-200">
                      文件上传暂不可用
                    </p>
                    <p className="text-sm text-neutral-300">
                      后端当前还没有浏览器二进制上传入口。请切换到“粘贴文本”提交小说内容。
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* ---- Submit button ---- */}
        {uploadError && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-950/30 rounded-lg px-4 py-3">
            <AlertCircle className="size-4 shrink-0" />
            {uploadError}
          </div>
        )}

        <Button
          className="w-full bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={!canSubmit}
          onClick={handleSubmit}
        >
          {uploading ? (
            <>
              <Loader2 className="size-4 mr-2 animate-spin" />
              正在上传...
            </>
          ) : (
            "上传小说"
          )}
        </Button>
      </div>
    </main>
  );
}
