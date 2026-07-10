"use client";

import { useEffect, useState, useCallback, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Pencil,
  RefreshCw,
  Package,
} from "lucide-react";
import { listProps, updateProp, regenerateProp } from "@/shared/api/props";
import type { PropResponse, PropUpdateRequest } from "@/shared/types";
import { Loading } from "@/shared/ui/Loading";
import { EmptyState } from "@/shared/ui/EmptyState";
import { ErrorState } from "@/shared/ui/ErrorState";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Modal } from "@/shared/ui/Modal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function hashName(name: string): number {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return Math.abs(hash);
}

function gradientStyle(name: string): React.CSSProperties {
  const h = hashName(name) % 360;
  const s = 50 + (hashName(name + "s") % 30);
  const l1 = 30 + (hashName(name + "l1") % 20);
  const l2 = l1 + 20;
  return {
    background: `linear-gradient(135deg, hsl(${h},${s}%,${l1}%), hsl(${(h + 40) % 360},${s}%,${l2}%))`,
  };
}

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function PropLibraryPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = params.id;

  // ---- data state -----------------------------------------------------------
  const [props, setProps] = useState<PropResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // ---- edit dialog state ----------------------------------------------------
  const [editOpen, setEditOpen] = useState(false);
  const [editProp, setEditProp] = useState<PropResponse | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editFunction, setEditFunction] = useState("");
  const [editTimeline, setEditTimeline] = useState("");

  // ---- regenerate confirm state ---------------------------------------------
  const [regenOpen, setRegenOpen] = useState(false);
  const [regenTarget, setRegenTarget] = useState<PropResponse | null>(null);

  // ---- fetch ----------------------------------------------------------------
  const fetchProps = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listProps(projectId);
      setProps(res.props);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "加载道具列表失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchProps();
  }, [fetchProps]);

  // ---- edit handlers --------------------------------------------------------
  const openEdit = (prop: PropResponse) => {
    setEditProp(prop);
    setEditName(prop.name);
    setEditDescription(prop.description);
    setEditFunction(prop.function);
    setEditTimeline(prop.state_timeline.join("\n"));
    setEditOpen(true);
  };

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    if (!editProp) return;
    setActionLoading(`edit-${editProp.prop_id}`);
    try {
      const data: PropUpdateRequest = {
        name: editName.trim() || undefined,
        description: editDescription.trim() || undefined,
        function: editFunction.trim() || undefined,
        state_timeline: editTimeline
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      const updated = await updateProp(projectId, editProp.prop_id, data);
      setProps((prev) =>
        prev.map((p) => (p.prop_id === updated.prop_id ? updated : p))
      );
      setEditOpen(false);
    } catch (e: unknown) {
      console.error(e instanceof Error ? e.message : "更新失败");
    } finally {
      setActionLoading(null);
    }
  };

  // ---- regenerate handler ---------------------------------------------------
  const confirmRegenerate = (prop: PropResponse) => {
    setRegenTarget(prop);
    setRegenOpen(true);
  };

  const handleRegenerate = async () => {
    if (!regenTarget) return;
    setActionLoading(`regen-${regenTarget.prop_id}`);
    try {
      await regenerateProp(projectId, regenTarget.prop_id);
      await fetchProps();
      setRegenOpen(false);
      setRegenTarget(null);
    } catch (e: unknown) {
      console.error(e instanceof Error ? e.message : "重新生成失败");
    } finally {
      setActionLoading(null);
    }
  };

  // ---- render ---------------------------------------------------------------
  const backHref = `/projects/${projectId}`;

  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <PageHeader
          title="道具库"
          description="项目中所有道具及其状态时间线"
          backHref={backHref}
        />

        {loading && <Loading message="正在加载道具列表..." />}

        {!loading && error && (
          <ErrorState message={error} retry={fetchProps} />
        )}

        {!loading && !error && props.length === 0 && (
          <EmptyState
            icon={<Package className="w-12 h-12 text-neutral-500" />}
            title="暂无道具"
            description="当前项目还没有生成道具，请先完成故事分析。"
            action={{ label: "返回项目", onClick: () => router.push(backHref) }}
          />
        )}

        {!loading && !error && props.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {props.map((prop) => (
              <PropCardItem
                key={prop.id}
                prop={prop}
                onEdit={() => openEdit(prop)}
                onRegenerate={() => confirmRegenerate(prop)}
                isLoading={
                  actionLoading === `edit-${prop.prop_id}` ||
                  actionLoading === `regen-${prop.prop_id}`
                }
              />
            ))}
          </div>
        )}
      </div>

      {/* Edit Dialog */}
      <Modal
        open={editOpen}
        onOpenChange={(open) => setEditOpen(open)}
        title="编辑道具"
        description="修改道具的属性信息"
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              取消
            </Button>
            <Button
              onClick={handleSave}
              disabled={!!actionLoading && actionLoading.startsWith("edit-")}
            >
              {actionLoading?.startsWith("edit-") ? "保存中..." : "保存"}
            </Button>
          </div>
        }
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="edit-name">名称</Label>
            <Input
              id="edit-name"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="道具名称"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit-desc">描述</Label>
            <Textarea
              id="edit-desc"
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="道具描述"
              rows={3}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit-func">功能</Label>
            <Input
              id="edit-func"
              value={editFunction}
              onChange={(e) => setEditFunction(e.target.value)}
              placeholder="道具的功能说明"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit-timeline">状态时间线</Label>
            <p className="text-xs text-neutral-400">每行一个状态</p>
            <Textarea
              id="edit-timeline"
              value={editTimeline}
              onChange={(e) => setEditTimeline(e.target.value)}
              placeholder={"完好\n轻微磨损\n损坏\n彻底破碎"}
              rows={4}
            />
          </div>
        </form>
      </Modal>

      {/* Regenerate Confirmation Modal */}
      <Modal
        open={regenOpen}
        onOpenChange={(open) => setRegenOpen(open)}
        title="确认重新生成"
        description={
          regenTarget
            ? `确定要重新生成道具「${regenTarget.name}」吗？这将会覆盖当前的设定。`
            : ""
        }
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setRegenOpen(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleRegenerate}>
              确认重新生成
            </Button>
          </div>
        }
      >
        <p className="text-sm text-neutral-400">
          重新生成将基于故事上下文对道具进行重新分析，可能需要一定时间。
        </p>
      </Modal>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Prop Card Sub-component
// ---------------------------------------------------------------------------

function PropCardItem({
  prop,
  onEdit,
  onRegenerate,
  isLoading,
}: {
  prop: PropResponse;
  onEdit: () => void;
  onRegenerate: () => void;
  isLoading: boolean;
}) {
  return (
    <Card className="bg-neutral-800 border-neutral-700 overflow-hidden hover:border-neutral-600 transition-colors">
      {/* Thumbnail placeholder */}
      <div
        className="h-36 w-full flex items-center justify-center"
        style={gradientStyle(prop.name)}
      >
        <span className="text-white/60 text-lg font-semibold tracking-wide select-none">
          {prop.name}
        </span>
      </div>

      <CardContent className="p-4 space-y-3">
        {/* Name + Lock */}
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-white font-semibold text-base truncate">
            {prop.name}
          </h3>
          {prop.is_locked && (
            <Badge variant="secondary" className="text-xs shrink-0">
              已锁定
            </Badge>
          )}
        </div>

        {/* Description */}
        <p className="text-neutral-400 text-sm line-clamp-2">
          {prop.description || "暂无描述"}
        </p>

        {/* Function */}
        {prop.function && (
          <p className="text-blue-400/80 text-xs">
            <span className="text-neutral-500">功能：</span>
            {prop.function}
          </p>
        )}

        {/* State Timeline as pills */}
        {prop.state_timeline.length > 0 && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
            {prop.state_timeline.map((state, idx) => (
              <div key={idx} className="flex items-center gap-1.5 shrink-0">
                <span className="px-2 py-0.5 rounded-full bg-neutral-700 text-neutral-300 text-xs whitespace-nowrap">
                  {state}
                </span>
                {idx < prop.state_timeline.length - 1 && (
                  <span className="text-neutral-600 text-xs">→</span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={onEdit}
            disabled={isLoading}
            className="text-xs h-8"
          >
            <Pencil className="w-3.5 h-3.5 mr-1" />
            编辑
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onRegenerate}
            disabled={isLoading}
            className="text-xs h-8 text-amber-400 hover:text-amber-300 hover:bg-amber-400/10"
          >
            <RefreshCw
              className={cn("w-3.5 h-3.5 mr-1", isLoading && "animate-spin")}
            />
            重新生成
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
