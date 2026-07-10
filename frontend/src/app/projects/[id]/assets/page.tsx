"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { resolveAssetUrl } from "@/shared/api/asset-url";
import {
  previewAssetWorkbenchPrompts,
  type GenerateAssetWorkbenchResponse,
  type PromptPreviewRequestItem,
} from "@/shared/api/asset-workbench";
import { generateImageAssetJob, pollTaskUntilDone, type ImageAssetType } from "@/shared/api/image-assets";
import { listCharacters, mergeReferenceImagePlan, updateCharacter } from "@/shared/api/characters";
import { listProps, updateProp } from "@/shared/api/props";
import { listScenes, updateScene } from "@/shared/api/scenes";
import { ErrorState } from "@/shared/ui/ErrorState";
import { Loading } from "@/shared/ui/Loading";
import { PageHeader } from "@/shared/ui/PageHeader";
import type { CharacterResponse, PropResponse, SceneResponse } from "@/shared/types";
import { cn } from "@/lib/utils";
import {
  Box,
  CheckCircle2,
  Eye,
  ImageIcon,
  Loader2,
  MapPin,
  Maximize2,
  Minimize2,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Users,
  X,
} from "lucide-react";

interface PreviewImageState {
  src: string;
  label: string;
  title: string;
}

const MIN_PREVIEW_SCALE = 0.5;
const MAX_PREVIEW_SCALE = 6;
const PROMPT_PREVIEW_ERROR = "最终提示词预览失败，已显示可编辑的基础提示词";

interface PreviewTransform {
  x: number;
  y: number;
}

function clampPreviewScale(value: number): number {
  return Math.min(MAX_PREVIEW_SCALE, Math.max(MIN_PREVIEW_SCALE, value));
}

function ZoomableImagePreview({ image, onClose }: { image: PreviewImageState; onClose: () => void }) {
  const shellRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const transformRef = useRef<PreviewTransform>({ x: 0, y: 0 });
  const scaleRef = useRef(1);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);
  const [scale, setScale] = useState(1);
  const [transform, setTransform] = useState<PreviewTransform>({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [nativeFullscreen, setNativeFullscreen] = useState(false);

  const applyView = useCallback((nextScale: number, nextTransform: PreviewTransform) => {
    scaleRef.current = nextScale;
    transformRef.current = nextTransform;
    setScale(nextScale);
    setTransform(nextTransform);
  }, []);

  const resetView = useCallback(() => {
    applyView(1, { x: 0, y: 0 });
    dragRef.current = null;
    setDragging(false);
  }, [applyView]);

  const syncNativeFullscreen = useCallback(() => {
    setNativeFullscreen(document.fullscreenElement === shellRef.current);
  }, []);

  useEffect(() => {
    syncNativeFullscreen();
    document.addEventListener("fullscreenchange", syncNativeFullscreen);
    return () => {
      document.removeEventListener("fullscreenchange", syncNativeFullscreen);
      if (document.fullscreenElement && document.exitFullscreen) {
        void document.exitFullscreen();
      }
    };
  }, [syncNativeFullscreen]);

  const toggleNativeFullscreen = useCallback(async () => {
    if (document.fullscreenElement) {
      await document.exitFullscreen?.();
      return;
    }
    await shellRef.current?.requestFullscreen?.();
  }, []);

  const handleWheel = useCallback(
    (event: WheelEvent) => {
      event.preventDefault();
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const currentScale = scaleRef.current;
      const currentTransform = transformRef.current;
      const nextScale = clampPreviewScale(currentScale * Math.exp(-event.deltaY * 0.0015));
      const scaleRatio = nextScale / currentScale;
      const cursorX = event.clientX - rect.left - rect.width / 2;
      const cursorY = event.clientY - rect.top - rect.height / 2;

      applyView(nextScale, {
        x: cursorX - (cursorX - currentTransform.x) * scaleRatio,
        y: cursorY - (cursorY - currentTransform.y) * scaleRatio,
      });
    },
    [applyView]
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      container.removeEventListener("wheel", handleWheel);
    };
  }, [handleWheel]);

  const handlePointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (scaleRef.current <= 1) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const currentTransform = transformRef.current;
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: currentTransform.x,
      originY: currentTransform.y,
    };
    setDragging(true);
  }, []);

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== event.pointerId) return;
      applyView(scaleRef.current, {
        x: drag.originX + event.clientX - drag.startX,
        y: drag.originY + event.clientY - drag.startY,
      });
    },
    [applyView]
  );

  const stopDragging = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId === event.pointerId) {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
      dragRef.current = null;
      setDragging(false);
    }
  }, []);

  return (
    <div ref={shellRef} className="flex h-[100dvh] w-[100vw] flex-col bg-black text-white">
      <div className="flex h-14 shrink-0 items-center gap-3 border-b border-white/10 bg-black/90 px-4">
        <DialogHeader className="min-w-0 flex-1 gap-1">
          <DialogTitle className="truncate text-sm text-white">{image.title}</DialogTitle>
          <DialogDescription className="text-xs text-neutral-400">{image.label}</DialogDescription>
        </DialogHeader>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="text-neutral-200 hover:bg-white/10 hover:text-white"
            aria-label="重置视图"
            title="重置视图"
            onClick={resetView}
          >
            <RotateCcw className="size-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="text-neutral-200 hover:bg-white/10 hover:text-white"
            aria-label={nativeFullscreen ? "退出浏览器全屏" : "进入浏览器全屏"}
            title={nativeFullscreen ? "退出浏览器全屏" : "进入浏览器全屏"}
            onClick={() => void toggleNativeFullscreen()}
          >
            {nativeFullscreen ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="text-neutral-200 hover:bg-white/10 hover:text-white"
            aria-label="关闭预览"
            title="关闭预览"
            onClick={onClose}
          >
            <X className="size-4" />
          </Button>
        </div>
      </div>
      <div
        ref={containerRef}
        data-testid="zoom-preview-canvas"
        className={cn(
          "relative min-h-0 flex-1 touch-none overflow-hidden bg-black",
          scale > 1 ? (dragging ? "cursor-grabbing" : "cursor-grab") : "cursor-zoom-in"
        )}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={stopDragging}
        onPointerCancel={stopDragging}
        onDoubleClick={resetView}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={image.src}
          alt={image.title}
          draggable={false}
          className="absolute left-1/2 top-1/2 max-h-full max-w-full select-none object-contain"
          style={{
            transform: `translate(-50%, -50%) translate(${transform.x}px, ${transform.y}px) scale(${scale})`,
            transformOrigin: "center",
          }}
        />
        <div className="pointer-events-none absolute bottom-3 right-3 rounded-md bg-black/70 px-2.5 py-1 text-xs tabular-nums text-white">
          {Math.round(scale * 100)}%
        </div>
      </div>
    </div>
  );
}

interface AssetThumbProps {
  src?: string;
  label: string;
  title: string;
  generating: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onGenerate: () => void;
  onPreview: (image: PreviewImageState) => void;
}

function AssetThumb({
  src,
  label,
  title,
  generating,
  disabled,
  disabledReason,
  onGenerate,
  onPreview,
}: AssetThumbProps) {
  const resolved = resolveAssetUrl(src);
  const generateLabel = resolved ? "重新生成" : "生成";
  const [loadedAspectRatio, setLoadedAspectRatio] = useState<{ src: string; ratio: number } | null>(null);
  const thumbAspectRatio = loadedAspectRatio && loadedAspectRatio.src === resolved ? loadedAspectRatio.ratio : null;

  const handleImageLoad = useCallback((event: React.SyntheticEvent<HTMLImageElement>) => {
    const { naturalWidth, naturalHeight } = event.currentTarget;
    if (resolved && naturalWidth > 0 && naturalHeight > 0) {
      setLoadedAspectRatio({ src: resolved, ratio: naturalWidth / naturalHeight });
    }
  }, [resolved]);

  return (
    <div className="space-y-2">
      <button
        type="button"
        disabled={!resolved}
        onClick={() => resolved && onPreview({ src: resolved, label, title })}
        style={{ aspectRatio: thumbAspectRatio ?? "4 / 3" }}
        className={cn(
          "group relative w-full overflow-hidden rounded-lg border border-neutral-700 bg-neutral-900",
          "flex items-center justify-center text-left transition",
          resolved ? "cursor-zoom-in hover:border-blue-500/70" : "cursor-default"
        )}
      >
        {resolved ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={resolved} alt={label} className="h-full w-full object-contain" onLoad={handleImageLoad} />
            <span className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-1 bg-black/60 px-2 py-1.5 text-xs text-white opacity-0 transition group-hover:opacity-100">
              <Eye className="size-3" />
              点击查看大图
            </span>
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 text-neutral-500">
            <ImageIcon className="size-6" />
            <span className="text-xs">{label}</span>
          </div>
        )}
      </button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="w-full border-neutral-700 bg-neutral-900 text-neutral-200 hover:bg-neutral-800"
        onClick={onGenerate}
        disabled={generating || disabled}
        title={disabledReason}
      >
        {generating ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
        {generating ? "生成中" : generateLabel}
      </Button>
      {disabledReason && <p className="text-center text-[11px] text-neutral-500">{disabledReason}</p>}
    </div>
  );
}

interface SingleGenerateOptions {
  key: string;
  assetType: ImageAssetType;
  entityType: "character" | "scene" | "prop";
  entityId: string;
  entityRecordId?: string;
  prompt: string;
  label: string;
  referenceAssetIds?: string[];
}

function PromptEditor({
  label,
  value,
  negativePrompt,
  onChange,
}: {
  label: string;
  value: string;
  negativePrompt?: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-neutral-400">{label}</div>
      <Textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-[120px] bg-neutral-900 border-neutral-700 text-neutral-100 resize-y"
      />
      {negativePrompt?.trim() && (
        <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-xs text-neutral-500">
          <span className="font-medium text-neutral-400">负面提示词：</span>
          <span className="whitespace-pre-wrap">{negativePrompt}</span>
        </div>
      )}
    </div>
  );
}

function characterPromptForWorkbench(character: CharacterResponse): string {
  return character.front_image_prompt || character.outfit || character.description || "";
}

function characterTurnaroundPromptForWorkbench(character: CharacterResponse): string {
  return character.turnaround_prompt || character.front_image_prompt || character.outfit || character.description || "";
}

function scenePromptForWorkbench(scene: SceneResponse): string {
  return scene.empty_scene_prompt || scene.scene_prompt || scene.description || "";
}

function propPromptForWorkbench(prop: PropResponse): string {
  return prop.prop_prompt || prop.description || "";
}

function promptKey(recordId: string, assetType: ImageAssetType): string {
  return `${recordId}:${assetType}`;
}

function withAssetRefreshToken(src: string | undefined, token: number | undefined): string | undefined {
  if (!src || !token) return src;
  return `${src}${src.includes("?") ? "&" : "?"}v=${token}`;
}

function buildFallbackPromptValues(
  characters: CharacterResponse[],
  scenes: SceneResponse[],
  props: PropResponse[]
): Record<string, string> {
  return {
    ...Object.fromEntries(
      characters.flatMap((character) => [
        [promptKey(character.id, "character_front"), characterPromptForWorkbench(character)],
        [promptKey(character.id, "character_turnaround"), characterTurnaroundPromptForWorkbench(character)],
      ])
    ),
    ...Object.fromEntries(scenes.map((scene) => [promptKey(scene.id, "scene_empty"), scenePromptForWorkbench(scene)])),
    ...Object.fromEntries(props.map((prop) => [promptKey(prop.id, "prop_product"), propPromptForWorkbench(prop)])),
  };
}

function buildPromptPreviewTargets(
  characters: CharacterResponse[],
  scenes: SceneResponse[],
  props: PropResponse[]
): Array<{ key: string; item: PromptPreviewRequestItem }> {
  return [
    ...characters.flatMap((character) => [
      {
        key: promptKey(character.id, "character_front"),
        item: {
          entity_type: "character" as const,
          entity_id: character.character_id,
          asset_type: "character_front" as const,
        },
      },
      {
        key: promptKey(character.id, "character_turnaround"),
        item: {
          entity_type: "character" as const,
          entity_id: character.character_id,
          asset_type: "character_turnaround" as const,
          reference_asset_ids: character.reference_asset_ids[0] ? [character.reference_asset_ids[0]] : [],
        },
      },
    ]),
    ...scenes.map((scene) => ({
      key: promptKey(scene.id, "scene_empty"),
      item: {
        entity_type: "scene" as const,
        entity_id: scene.scene_id,
        asset_type: "scene_empty" as const,
      },
    })),
    ...props.map((prop) => ({
      key: promptKey(prop.id, "prop_product"),
      item: {
        entity_type: "prop" as const,
        entity_id: prop.prop_id,
        asset_type: "prop_product" as const,
      },
    })),
  ];
}

export default function AssetWorkbenchPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [characters, setCharacters] = useState<CharacterResponse[]>([]);
  const [scenes, setScenes] = useState<SceneResponse[]>([]);
  const [props, setProps] = useState<PropResponse[]>([]);
  const [promptValues, setPromptValues] = useState<Record<string, string>>({});
  const [negativePromptValues, setNegativePromptValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [singleGeneratingKey, setSingleGeneratingKey] = useState<string | null>(null);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationStage, setGenerationStage] = useState("");
  const [generationResult, setGenerationResult] = useState<GenerateAssetWorkbenchResponse | null>(null);
  const [previewImage, setPreviewImage] = useState<PreviewImageState | null>(null);
  const [assetRefreshTokens, setAssetRefreshTokens] = useState<Record<string, number>>({});
  const isGeneratingAny = generating || singleGeneratingKey !== null;

  const plannedTotal = useMemo(
    () => characters.length * 2 + scenes.length + props.length,
    [characters.length, scenes.length, props.length]
  );

  const loadLibraries = useCallback(async () => {
    const [characterList, sceneList, propList] = await Promise.all([
      listCharacters(projectId),
      listScenes(projectId),
      listProps(projectId),
    ]);
    setCharacters(characterList.characters);
    setScenes(sceneList.scenes);
    setProps(propList.props);
    const fallbackPrompts = buildFallbackPromptValues(characterList.characters, sceneList.scenes, propList.props);
    setPromptValues(fallbackPrompts);
    setNegativePromptValues({});

    const previewTargets = buildPromptPreviewTargets(characterList.characters, sceneList.scenes, propList.props);
    if (!previewTargets.length) return;

    try {
      const response = await previewAssetWorkbenchPrompts(projectId, {
        items: previewTargets.map((target) => target.item),
      });
      const nextPrompts = { ...fallbackPrompts };
      const nextNegativePrompts: Record<string, string> = {};
      response.items.forEach((item, index) => {
        const key = previewTargets[index]?.key;
        if (!key) return;
        nextPrompts[key] = item.prompt || nextPrompts[key] || "";
        nextNegativePrompts[key] = item.negative_prompt || "";
      });
      setPromptValues(nextPrompts);
      setNegativePromptValues(nextNegativePrompts);
      setError((current) => (current === PROMPT_PREVIEW_ERROR ? null : current));
    } catch {
      setError(PROMPT_PREVIEW_ERROR);
    }
  }, [projectId]);

  const refreshAssetThumb = useCallback((key: string) => {
    setAssetRefreshTokens((current) => ({ ...current, [key]: Date.now() }));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadLibraries()
        .catch((e) => setError(e instanceof Error ? e.message : "加载素材失败"))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadLibraries]);

  const persistPromptChanges = useCallback(async () => {
    const updates: Promise<unknown>[] = [];
    for (const character of characters) {
      const frontPrompt = promptValues[promptKey(character.id, "character_front")]?.trim();
      const turnaroundPrompt = promptValues[promptKey(character.id, "character_turnaround")]?.trim();
      const frontChanged = frontPrompt && frontPrompt !== characterPromptForWorkbench(character);
      const turnaroundChanged =
        turnaroundPrompt && turnaroundPrompt !== characterTurnaroundPromptForWorkbench(character);
      if (frontChanged || turnaroundChanged) {
        updates.push(
          updateCharacter(projectId, character.character_id, {
            reference_image_plan: mergeReferenceImagePlan(character.reference_image_plan || [], {
              frontImagePrompt: frontChanged ? frontPrompt : undefined,
              turnaroundPrompt: turnaroundChanged ? turnaroundPrompt : undefined,
            }),
          })
        );
      }
    }
    for (const scene of scenes) {
      const prompt = promptValues[promptKey(scene.id, "scene_empty")]?.trim();
      if (prompt && prompt !== scenePromptForWorkbench(scene)) {
        updates.push(updateScene(projectId, scene.scene_id, { empty_scene_prompt: prompt }));
      }
    }
    for (const prop of props) {
      const prompt = promptValues[promptKey(prop.id, "prop_product")]?.trim();
      if (prompt && prompt !== propPromptForWorkbench(prop)) {
        updates.push(updateProp(projectId, prop.prop_id, { prop_prompt: prompt }));
      }
    }
    await Promise.all(updates);
  }, [characters, scenes, props, promptValues, projectId]);

  const persistSinglePromptChange = useCallback(
    async (options: SingleGenerateOptions) => {
      const prompt = options.prompt.trim();
      if (!prompt) return;

      if (options.entityType === "character") {
        const character = characters.find((item) => item.id === options.entityRecordId);
        await updateCharacter(projectId, options.entityId, {
          reference_image_plan: mergeReferenceImagePlan(character?.reference_image_plan || [], {
            frontImagePrompt: options.assetType === "character_front" ? prompt : undefined,
            turnaroundPrompt: options.assetType === "character_turnaround" ? prompt : undefined,
          }),
        });
      } else if (options.entityType === "scene") {
        await updateScene(projectId, options.entityId, { empty_scene_prompt: prompt });
      } else {
        await updateProp(projectId, options.entityId, { prop_prompt: prompt });
      }
    },
    [characters, projectId]
  );

  const handleGenerate = useCallback(async () => {
    setError(null);
    setGenerationResult(null);
    setGenerating(true);
    setGenerationProgress(0);
    setGenerationStage("保存提示词...");
    try {
      await persistPromptChanges();

      // Collect all generation items
      const items: SingleGenerateOptions[] = [];
      for (const character of characters) {
        items.push({
          key: `${character.id}:front`,
          assetType: "character_front",
          entityType: "character",
          entityId: character.character_id,
          entityRecordId: character.id,
          prompt: promptValues[promptKey(character.id, "character_front")]?.trim() || "",
          label: `${character.name}正面图`,
        });
        items.push({
          key: `${character.id}:turnaround`,
          assetType: "character_turnaround",
          entityType: "character",
          entityId: character.character_id,
          entityRecordId: character.id,
          prompt: promptValues[promptKey(character.id, "character_turnaround")]?.trim() || "",
          label: `${character.name}三视图`,
          referenceAssetIds: character.reference_asset_ids[0] ? [character.reference_asset_ids[0]] : [],
        });
      }
      for (const scene of scenes) {
        items.push({
          key: `${scene.id}:empty`,
          assetType: "scene_empty",
          entityType: "scene",
          entityId: scene.scene_id,
          entityRecordId: scene.id,
          prompt: promptValues[promptKey(scene.id, "scene_empty")]?.trim() || "",
          label: `${scene.name}场景图`,
        });
      }
      for (const prop of props) {
        items.push({
          key: `${prop.id}:product`,
          assetType: "prop_product",
          entityType: "prop",
          entityId: prop.prop_id,
          entityRecordId: prop.id,
          prompt: promptValues[promptKey(prop.id, "prop_product")]?.trim() || "",
          label: `${prop.name}道具图`,
        });
      }

      const total = items.length;
      let succeeded = 0;
      let failed = 0;
      const results: GenerateAssetWorkbenchResponse["results"] = [];
      const generatedFrontPaths: Record<string, string> = {};

      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        let referenceAssetIds = item.referenceAssetIds || [];
        if (item.entityType === "character" && item.assetType === "character_turnaround") {
          const entityRecordId = item.entityRecordId;
          if (!entityRecordId) {
            failed++;
            results.push({
              entity_type: "character",
              entity_id: item.entityId,
              asset_type: "character_turnaround",
              status: "failed",
              error: "Cannot generate character_turnaround without a character record id",
            });
            setGenerationProgress(Math.round(((i + 1) / total) * 100));
            continue;
          }
          const character = characters.find((c) => c.id === entityRecordId);
          const frontReferencePath = generatedFrontPaths[entityRecordId] || character?.reference_asset_ids[0];
          if (!frontReferencePath) {
            failed++;
            results.push({
              entity_type: "character",
              entity_id: item.entityId,
              asset_type: "character_turnaround",
              status: "failed",
              error: "Cannot generate character_turnaround without a front reference image",
            });
            setGenerationProgress(Math.round(((i + 1) / total) * 100));
            continue;
          }
          referenceAssetIds = [frontReferencePath];
        }

        setGenerationStage(`正在生成 ${item.label} (${i + 1}/${total})...`);
        setGenerationProgress(Math.round(((i) / total) * 100));

        try {
          const job = await generateImageAssetJob({
            project_id: projectId,
            asset_type: item.assetType,
            related_id: item.entityId,
            reference_asset_ids: referenceAssetIds,
            extra_constraints: null,
          });
          const task = await pollTaskUntilDone(job.task_id, 2000, 300000);
          if (task.status === "success") {
            const storagePath = task.storage_path || undefined;
            succeeded++;
            results.push({
              entity_type: item.entityType,
              entity_id: item.entityId,
              asset_type: item.assetType,
              status: "generated",
              storage_path: storagePath,
            });
            if (item.entityType === "character" && item.assetType === "character_front" && storagePath && item.entityRecordId) {
              generatedFrontPaths[item.entityRecordId] = storagePath;
            }
            if (storagePath) {
              refreshAssetThumb(item.key);
            }
            // Refresh libraries to pick up new reference assets for turnaround dependency
            await loadLibraries();
          } else {
            failed++;
            results.push({
              entity_type: item.entityType,
              entity_id: item.entityId,
              asset_type: item.assetType,
              status: "failed",
              error: task.error_message || undefined,
            });
          }
        } catch (e) {
          failed++;
          results.push({
            entity_type: item.entityType,
            entity_id: item.entityId,
            asset_type: item.assetType,
            status: "failed",
            error: e instanceof Error ? e.message : "生成失败",
          });
        }

        setGenerationProgress(Math.round(((i + 1) / total) * 100));
      }

      setGenerationProgress(100);
      setGenerationStage("素材生成完成");
      setGenerationResult({
        project_id: projectId,
        total,
        succeeded,
        skipped: 0,
        failed,
        results,
      });
      await loadLibraries();
    } catch (e) {
      setGenerationStage("生成失败");
      setError(e instanceof Error ? e.message : "素材生成失败");
    } finally {
      setGenerating(false);
    }
  }, [
    projectId,
    characters,
    scenes,
    props,
    promptValues,
    persistPromptChanges,
    loadLibraries,
    refreshAssetThumb,
  ]);

  const handleGenerateSingle = useCallback(
    async (options: SingleGenerateOptions) => {
      setError(null);
      setGenerationResult(null);
      setSingleGeneratingKey(options.key);
      setGenerationStage(`正在创建${options.label}任务...`);
      try {
        await persistSinglePromptChange(options);
        // Create async job instead of blocking API call
        const job = await generateImageAssetJob({
          project_id: projectId,
          asset_type: options.assetType,
          related_id: options.entityId,
          reference_asset_ids: options.referenceAssetIds || [],
          extra_constraints: null,
        });
        setGenerationStage(`正在生成${options.label}...`);
        // Poll until done (up to 5 minutes)
        const task = await pollTaskUntilDone(job.task_id, 2000, 300000);
        if (task.status === "success") {
          if (task.storage_path) {
            refreshAssetThumb(options.key);
          }
          setGenerationStage(`${options.label}生成完成`);
          setGenerationResult({
            project_id: projectId,
            total: 1,
            succeeded: 1,
            skipped: 0,
            failed: 0,
            results: [
              {
                entity_type: options.entityType,
                entity_id: options.entityId,
                asset_type: options.assetType,
                status: "generated",
                storage_path: task.storage_path || undefined,
              },
            ],
          });
          await loadLibraries();
        } else {
          setGenerationStage(`${options.label}生成失败`);
          setError(task.error_message || `${options.label}生成失败`);
        }
      } catch (e) {
        setGenerationStage(`${options.label}生成失败`);
        setError(e instanceof Error ? e.message : `${options.label}生成失败`);
      } finally {
        setSingleGeneratingKey(null);
      }
    },
    [loadLibraries, persistSinglePromptChange, projectId, refreshAssetThumb]
  );

  if (loading) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-6xl mx-auto">
          <Loading message="加载素材..." />
        </div>
      </main>
    );
  }

  if (error && !characters.length && !scenes.length && !props.length) {
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
      <div className="max-w-6xl mx-auto space-y-6">
        <PageHeader
          title="素材工作台"
          description={`角色 ${characters.length} · 场景 ${scenes.length} · 道具 ${props.length}`}
          backHref={`/projects/${projectId}`}
          actions={
            <div className="flex gap-2">
              <Button variant="outline" onClick={loadLibraries} disabled={isGeneratingAny}>
                <RefreshCw className="size-4 mr-2" />
                刷新
              </Button>
              <Button
                className="bg-blue-600 hover:bg-blue-500 text-white"
                disabled={isGeneratingAny || plannedTotal === 0}
                onClick={handleGenerate}
              >
                {generating ? (
                  <Loader2 className="size-4 mr-2 animate-spin" />
                ) : (
                  <Sparkles className="size-4 mr-2" />
                )}
                一键生成素材
              </Button>
            </div>
          }
        />

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {(generating || singleGeneratingKey || generationProgress > 0) && (
          <Card className="bg-neutral-800 border-neutral-700">
            <CardContent className="p-4 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-neutral-300">{generationStage}</span>
                <span className="text-white font-medium">{generationProgress}%</span>
              </div>
              <Progress value={generationProgress} className="h-2 bg-neutral-700" />
              <div className="text-xs text-neutral-500">
                {plannedTotal} 张计划图：角色正面与三视图、场景图、道具图
              </div>
            </CardContent>
          </Card>
        )}

        {generationResult && (
          <Card className="bg-neutral-800 border-neutral-700">
            <CardContent className="p-4 flex flex-wrap items-center gap-3">
              <CheckCircle2 className="size-5 text-green-400" />
              <span className="text-sm text-neutral-200">
                成功 {generationResult.succeeded} · 跳过 {generationResult.skipped} · 失败 {generationResult.failed}
              </span>
              {generationResult.failed > 0 && (
                <Badge variant="outline" className="border-red-500/30 text-red-300">
                  部分失败
                </Badge>
              )}
            </CardContent>
          </Card>
        )}

        <Tabs defaultValue="characters" className="space-y-4">
          <TabsList className="bg-neutral-800 border border-neutral-700">
            <TabsTrigger value="characters">
              <Users className="size-4 mr-2" />
              角色
            </TabsTrigger>
            <TabsTrigger value="scenes">
              <MapPin className="size-4 mr-2" />
              场景
            </TabsTrigger>
            <TabsTrigger value="props">
              <Box className="size-4 mr-2" />
              道具
            </TabsTrigger>
          </TabsList>

          <TabsContent value="characters" className="space-y-4">
            {characters.map((character) => (
              <Card key={character.id} className="bg-neutral-800 border-neutral-700">
                <CardContent className="p-5 grid grid-cols-1 gap-5 lg:grid-cols-[440px_1fr] xl:grid-cols-[480px_1fr]">
                  <div className="grid grid-cols-2 gap-3">
                    <AssetThumb
                      src={withAssetRefreshToken(
                        character.reference_image_urls[0],
                        assetRefreshTokens[`${character.id}:front`]
                      )}
                      label="正面图"
                      title={`${character.name} · 正面图`}
                      generating={singleGeneratingKey === `${character.id}:front`}
                      disabled={isGeneratingAny && singleGeneratingKey !== `${character.id}:front`}
                      onPreview={setPreviewImage}
                      onGenerate={() =>
                        handleGenerateSingle({
                          key: `${character.id}:front`,
                          assetType: "character_front",
                          entityType: "character",
                          entityId: character.character_id,
                          entityRecordId: character.id,
                          prompt: promptValues[promptKey(character.id, "character_front")]?.trim() || "",
                          label: `${character.name}正面图`,
                        })
                      }
                    />
                    <AssetThumb
                      src={withAssetRefreshToken(
                        character.reference_image_urls[1],
                        assetRefreshTokens[`${character.id}:turnaround`]
                      )}
                      label="三视图"
                      title={`${character.name} · 三视图`}
                      generating={singleGeneratingKey === `${character.id}:turnaround`}
                      disabled={
                        (isGeneratingAny && singleGeneratingKey !== `${character.id}:turnaround`) ||
                        !character.reference_asset_ids[0]
                      }
                      disabledReason={!character.reference_asset_ids[0] ? "先生成正面图" : undefined}
                      onPreview={setPreviewImage}
                      onGenerate={() =>
                        handleGenerateSingle({
                          key: `${character.id}:turnaround`,
                          assetType: "character_turnaround",
                          entityType: "character",
                          entityId: character.character_id,
                          entityRecordId: character.id,
                          prompt: promptValues[promptKey(character.id, "character_turnaround")]?.trim() || "",
                          label: `${character.name}三视图`,
                          referenceAssetIds: character.reference_asset_ids[0] ? [character.reference_asset_ids[0]] : [],
                        })
                      }
                    />
                  </div>
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-white font-semibold">{character.name}</h3>
                      <Badge variant="outline" className="border-blue-500/30 text-blue-300">
                        {character.role}
                      </Badge>
                    </div>
                    <p className="text-sm text-neutral-400">{character.description || character.age_range || "角色设定"}</p>
                    <PromptEditor
                      label="正面角色图 Prompt"
                      value={promptValues[promptKey(character.id, "character_front")] || ""}
                      negativePrompt={negativePromptValues[promptKey(character.id, "character_front")]}
                      onChange={(value) =>
                        setPromptValues((current) => ({ ...current, [promptKey(character.id, "character_front")]: value }))
                      }
                    />
                    <PromptEditor
                      label="角色三视图 Prompt"
                      value={promptValues[promptKey(character.id, "character_turnaround")] || ""}
                      negativePrompt={negativePromptValues[promptKey(character.id, "character_turnaround")]}
                      onChange={(value) =>
                        setPromptValues((current) => ({
                          ...current,
                          [promptKey(character.id, "character_turnaround")]: value,
                        }))
                      }
                    />
                  </div>
                </CardContent>
              </Card>
            ))}
            {!characters.length && <EmptyAssetText text="暂无角色，请先完成故事分析" />}
          </TabsContent>

          <TabsContent value="scenes" className="space-y-4">
            {scenes.map((scene) => (
              <Card key={scene.id} className="bg-neutral-800 border-neutral-700">
                <CardContent className="p-5 grid grid-cols-1 gap-5 lg:grid-cols-[440px_1fr]">
                  <AssetThumb
                    src={withAssetRefreshToken(scene.thumbnail_url, assetRefreshTokens[`${scene.id}:empty`])}
                    label="场景图"
                    title={`${scene.name} · 场景图`}
                    generating={singleGeneratingKey === `${scene.id}:empty`}
                    disabled={isGeneratingAny && singleGeneratingKey !== `${scene.id}:empty`}
                    onPreview={setPreviewImage}
                    onGenerate={() =>
                      handleGenerateSingle({
                        key: `${scene.id}:empty`,
                        assetType: "scene_empty",
                        entityType: "scene",
                        entityId: scene.scene_id,
                        prompt: promptValues[promptKey(scene.id, "scene_empty")]?.trim() || "",
                        label: `${scene.name}场景图`,
                      })
                    }
                  />
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-white font-semibold">{scene.name}</h3>
                      {scene.location && (
                        <Badge variant="outline" className="border-purple-500/30 text-purple-300">
                          {scene.location}
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-neutral-400">{scene.mood || scene.time_period || "场景设定"}</p>
                    <PromptEditor
                      label="无人场景图 Prompt"
                      value={promptValues[promptKey(scene.id, "scene_empty")] || ""}
                      negativePrompt={negativePromptValues[promptKey(scene.id, "scene_empty")]}
                      onChange={(value) =>
                        setPromptValues((current) => ({ ...current, [promptKey(scene.id, "scene_empty")]: value }))
                      }
                    />
                  </div>
                </CardContent>
              </Card>
            ))}
            {!scenes.length && <EmptyAssetText text="暂无场景，请先完成故事分析" />}
          </TabsContent>

          <TabsContent value="props" className="space-y-4">
            {props.map((prop) => (
              <Card key={prop.id} className="bg-neutral-800 border-neutral-700">
                <CardContent className="p-5 grid grid-cols-1 gap-5 lg:grid-cols-[420px_1fr]">
                  <AssetThumb
                    src={withAssetRefreshToken(prop.thumbnail_url, assetRefreshTokens[`${prop.id}:product`])}
                    label="道具图"
                    title={`${prop.name} · 道具图`}
                    generating={singleGeneratingKey === `${prop.id}:product`}
                    disabled={isGeneratingAny && singleGeneratingKey !== `${prop.id}:product`}
                    onPreview={setPreviewImage}
                    onGenerate={() =>
                      handleGenerateSingle({
                        key: `${prop.id}:product`,
                        assetType: "prop_product",
                        entityType: "prop",
                        entityId: prop.prop_id,
                        prompt: promptValues[promptKey(prop.id, "prop_product")]?.trim() || "",
                        label: `${prop.name}道具图`,
                      })
                    }
                  />
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-white font-semibold">{prop.name}</h3>
                      {prop.function && (
                        <Badge variant="outline" className="border-amber-500/30 text-amber-300">
                          {prop.function}
                        </Badge>
                      )}
                    </div>
                    <PromptEditor
                      label="单一道具图 Prompt"
                      value={promptValues[promptKey(prop.id, "prop_product")] || ""}
                      negativePrompt={negativePromptValues[promptKey(prop.id, "prop_product")]}
                      onChange={(value) =>
                        setPromptValues((current) => ({ ...current, [promptKey(prop.id, "prop_product")]: value }))
                      }
                    />
                  </div>
                </CardContent>
              </Card>
            ))}
            {!props.length && <EmptyAssetText text="暂无道具，请先完成故事分析" />}
          </TabsContent>
        </Tabs>

        <div className="flex justify-end">
          <div className="inline-flex items-center gap-2 rounded-md border border-emerald-800 bg-emerald-950/30 px-4 py-2 text-sm text-emerald-300">
            <CheckCircle2 className="size-4" />
            资产图流程到这里完成
          </div>
        </div>
      </div>

      <Dialog open={!!previewImage} onOpenChange={(open) => !open && setPreviewImage(null)}>
        <DialogContent
          showCloseButton={false}
          className="fixed inset-0 left-0 top-0 flex h-[100dvh] w-[100vw] max-h-none max-w-none translate-x-0 translate-y-0 rounded-none border-0 bg-black p-0 text-white ring-0 sm:max-w-none"
        >
          {previewImage && (
            <ZoomableImagePreview key={previewImage.src} image={previewImage} onClose={() => setPreviewImage(null)} />
          )}
        </DialogContent>
      </Dialog>
    </main>
  );
}

function EmptyAssetText({ text }: { text: string }) {
  return (
    <div
      className={cn(
        "rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-10 text-center text-sm text-neutral-500"
      )}
    >
      {text}
    </div>
  );
}
