"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Loading } from "@/shared/ui/Loading";
import { EmptyState } from "@/shared/ui/EmptyState";
import { ErrorState } from "@/shared/ui/ErrorState";
import { PageHeader } from "@/shared/ui/PageHeader";
import { listScenes, updateScene } from "@/shared/api/scenes";
import type { SceneResponse, SceneUpdateRequest } from "@/shared/types";
import { Map, Lock, LockOpen, Edit3, Clock, Cloud } from "lucide-react";

export default function ScenesPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [scenes, setScenes] = useState<SceneResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingScene, setEditingScene] = useState<SceneResponse | null>(null);
  const [editForm, setEditForm] = useState<SceneUpdateRequest>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    listScenes(projectId)
      .then((d) => setScenes(d.scenes))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load scenes"))
      .finally(() => setLoading(false));
  }, [projectId]);

  function openEdit(scene: SceneResponse) {
    setEditingScene(scene);
    setEditForm({
      name: scene.name,
      description: scene.description,
      time_period: scene.time_period,
      mood: scene.mood,
      location: scene.location,
    });
  }

  async function handleSave() {
    if (!editingScene) return;
    setSaving(true);
    try {
      await updateScene(projectId, editingScene.scene_id, editForm);
      setScenes((prev) =>
        prev.map((s) =>
          s.scene_id === editingScene.scene_id
            ? { ...s, ...editForm, updated_at: new Date().toISOString() }
            : s
        )
      );
      setEditingScene(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggleLock(scene: SceneResponse) {
    try {
      await updateScene(projectId, scene.scene_id, { is_locked: !scene.is_locked });
      setScenes((prev) =>
        prev.map((s) =>
          s.scene_id === scene.scene_id ? { ...s, is_locked: !s.is_locked } : s
        )
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Toggle failed");
    }
  }

  if (loading) return <Loading message="加载场景库..." />;
  if (error) return <ErrorState message={error} retry={() => window.location.reload()} />;

  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <PageHeader
          title="场景库"
          description={`${scenes.length} 个场景`}
          backHref={`/projects/${projectId}`}
        />
        {scenes.length === 0 ? (
          <EmptyState title="暂无场景" description="请先上传小说并完成分析" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {scenes.map((scene) => (
              <Card key={scene.id} className="bg-neutral-800 border-neutral-700 overflow-hidden">
                <div className="h-32 bg-gradient-to-br from-blue-900/50 to-purple-900/50 flex items-center justify-center relative">
                  <Map className="size-10 text-neutral-600" />
                  {scene.is_locked && (
                    <div className="absolute top-2 right-2 bg-yellow-500/20 rounded-full p-1">
                      <Lock className="size-3 text-yellow-400" />
                    </div>
                  )}
                </div>
                <CardHeader><CardTitle className="text-white">{scene.name}</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-neutral-400 line-clamp-2">{scene.description}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {scene.time_period && <Badge variant="outline" className="text-xs"><Clock className="size-3 mr-1" />{scene.time_period}</Badge>}
                    {scene.mood && <Badge variant="outline" className="text-xs"><Cloud className="size-3 mr-1" />{scene.mood}</Badge>}
                  </div>
                  {scene.location && <p className="text-xs text-neutral-500">地点: {scene.location}</p>}
                  {scene.fixed_anchors.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {scene.fixed_anchors.map((a, i) => (
                        <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-300">{a}</span>
                      ))}
                    </div>
                  )}
                </CardContent>
                <CardFooter className="gap-2">
                  <Button size="sm" variant="outline" onClick={() => openEdit(scene)}><Edit3 className="size-3 mr-1" />编辑</Button>
                  <Button size="sm" variant="ghost" onClick={() => toggleLock(scene)}>
                    {scene.is_locked ? <><Lock className="size-3 mr-1 text-yellow-400" />已锁定</> : <><LockOpen className="size-3 mr-1" />锁定</>}
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
        <Dialog open={!!editingScene} onOpenChange={() => setEditingScene(null)}>
          <DialogContent className="bg-neutral-900 border-neutral-700 text-white max-w-lg">
            <DialogHeader>
              <DialogTitle>编辑场景</DialogTitle>
              <DialogDescription className="text-neutral-400">修改场景的详细信息</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div><label className="text-sm text-neutral-300 mb-1 block">场景名称</label><Input value={editForm.name || ""} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} className="bg-neutral-800 border-neutral-700 text-white" /></div>
              <div><label className="text-sm text-neutral-300 mb-1 block">描述</label><Input value={editForm.description || ""} onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} className="bg-neutral-800 border-neutral-700 text-white" /></div>
              <div><label className="text-sm text-neutral-300 mb-1 block">时间段</label><Input value={editForm.time_period || ""} onChange={(e) => setEditForm((f) => ({ ...f, time_period: e.target.value }))} className="bg-neutral-800 border-neutral-700 text-white" /></div>
              <div><label className="text-sm text-neutral-300 mb-1 block">氛围</label><Input value={editForm.mood || ""} onChange={(e) => setEditForm((f) => ({ ...f, mood: e.target.value }))} className="bg-neutral-800 border-neutral-700 text-white" /></div>
              <div><label className="text-sm text-neutral-300 mb-1 block">地点</label><Input value={editForm.location || ""} onChange={(e) => setEditForm((f) => ({ ...f, location: e.target.value }))} className="bg-neutral-800 border-neutral-700 text-white" /></div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditingScene(null)}>取消</Button>
              <Button onClick={handleSave} disabled={saving} className="bg-blue-600 hover:bg-blue-500">{saving ? "保存中..." : "保存"}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </main>
  );
}
