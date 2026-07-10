"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Loading } from "@/shared/ui/Loading";
import { ErrorState } from "@/shared/ui/ErrorState";
import { EmptyState } from "@/shared/ui/EmptyState";
import { PageHeader } from "@/shared/ui/PageHeader";
import { Modal } from "@/shared/ui/Modal";
import {
  listCharacters,
  updateCharacter,
  regenerateCharacter,
} from "@/shared/api/characters";
import { cn } from "@/lib/utils";
import type {
  CharacterResponse,
  CharacterUpdateRequest,
} from "@/shared/types";
import {
  Pencil,
  Lock,
  LockOpen,
  RefreshCw,
  Users,
  Loader2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Role badge config
// ---------------------------------------------------------------------------

const roleConfig: Record<string, { label: string; color: string }> = {
  protagonist: { label: "主角", color: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
  antagonist: { label: "反派", color: "bg-red-500/20 text-red-400 border-red-500/30" },
  supporting: { label: "配角", color: "bg-neutral-500/20 text-neutral-400 border-neutral-500/30" },
};

function getRoleBadge(role: string) {
  const conf = roleConfig[role] || roleConfig.supporting;
  return (
    <Badge variant="outline" className={cn("text-xs", conf.color)}>
      {conf.label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Avatar placeholder
// ---------------------------------------------------------------------------

function AvatarPlaceholder({
  name,
  gender,
  size = "md",
}: {
  name: string;
  gender?: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClass =
    size === "sm" ? "size-10 text-sm" : size === "lg" ? "size-16 text-xl" : "size-12 text-base";
  const bgColor =
    gender === "女性"
      ? "bg-pink-500/30 text-pink-300"
      : "bg-blue-500/30 text-blue-300";
  return (
    <div
      className={cn(
        "rounded-full flex items-center justify-center font-bold shrink-0",
        bgColor,
        sizeClass
      )}
    >
      {name.charAt(0)}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Edit character dialog
// ---------------------------------------------------------------------------

function EditCharacterDialog({
  open,
  character,
  onClose,
  onSave,
}: {
  open: boolean;
  character: CharacterResponse | null;
  onClose: () => void;
  onSave: (data: CharacterUpdateRequest) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [outfit, setOutfit] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (character) {
      setName(character.name);
      setDescription(character.description);
      setOutfit(character.outfit || "");
    }
  }, [character]);

  const handleSave = async () => {
    if (!character) return;
    setSaving(true);
    try {
      await onSave({
        name,
        description,
        outfit: outfit || undefined,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  if (!character) return null;

  return (
    <Modal
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={`编辑角色 — ${character.name}`}
      description="修改角色的基本信息和设定"
      footer={
        <div className="flex justify-end gap-3 w-full">
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button
            className="bg-blue-600 hover:bg-blue-500 text-white"
            disabled={!name.trim() || saving}
            onClick={handleSave}
          >
            {saving ? (
              <>
                <Loader2 className="size-4 mr-2 animate-spin" />
                保存中...
              </>
            ) : (
              "保存"
            )}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm text-neutral-400">角色名称</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="bg-neutral-900 border-neutral-700 text-white"
            placeholder="角色名称"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm text-neutral-400">角色描述</label>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="bg-neutral-900 border-neutral-700 text-white min-h-[100px] resize-y"
            placeholder="角色描述..."
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm text-neutral-400">服装设定</label>
          <Input
            value={outfit}
            onChange={(e) => setOutfit(e.target.value)}
            className="bg-neutral-900 border-neutral-700 text-white"
            placeholder="如：白色太空军科研制服"
          />
        </div>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Character card
// ---------------------------------------------------------------------------

function CharacterCard({
  character,
  onEdit,
  onToggleLock,
  onRegenerate,
}: {
  character: CharacterResponse;
  onEdit: (ch: CharacterResponse) => void;
  onToggleLock: (ch: CharacterResponse) => void;
  onRegenerate: (ch: CharacterResponse) => void;
}) {
  const [lockToggling, setLockToggling] = useState(false);
  const [regenConfirm, setRegenConfirm] = useState(false);

  const handleToggleLock = async () => {
    setLockToggling(true);
    try {
      await onToggleLock(character);
    } finally {
      setLockToggling(false);
    }
  };

  return (
    <Card
      className={cn(
        "bg-neutral-800 border-neutral-700 hover:border-neutral-600 transition-colors group relative",
        character.is_locked && "ring-1 ring-yellow-500/30"
      )}
    >
      <CardContent className="p-5 space-y-3">
        {/* Top row: avatar + info */}
        <div className="flex items-start gap-3">
          <AvatarPlaceholder
            name={character.name}
            gender={character.gender}
            size="md"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-white font-semibold text-sm truncate">
                {character.name}
              </h3>
              {getRoleBadge(character.role)}
              {character.is_locked && (
                <Lock className="size-3.5 text-yellow-400 shrink-0" />
              )}
            </div>
            {character.age_range && (
              <p className="text-xs text-neutral-500 mb-1">
                {character.gender && `${character.gender} · `}
                {character.age_range}
              </p>
            )}
            <p className="text-xs text-neutral-400 line-clamp-3 leading-relaxed">
              {character.description}
            </p>
          </div>
        </div>

        {/* Outfit tags */}
        {character.outfit && (
          <div className="space-y-1">
            <p className="text-xs text-neutral-500">
              <span className="text-neutral-600">服装: </span>
              {character.outfit}
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-1 pt-2 border-t border-neutral-700/50">
          {/* Edit */}
          <Button
            variant="ghost"
            size="sm"
            className="text-neutral-400 hover:text-white hover:bg-neutral-700 h-8 px-2"
            onClick={() => onEdit(character)}
          >
            <Pencil className="size-3.5 mr-1" />
            编辑
          </Button>

          {/* Lock toggle */}
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "hover:bg-neutral-700 h-8 px-2",
              character.is_locked
                ? "text-yellow-400 hover:text-yellow-300"
                : "text-neutral-400 hover:text-white"
            )}
            disabled={lockToggling}
            onClick={handleToggleLock}
          >
            {lockToggling ? (
              <Loader2 className="size-3.5 mr-1 animate-spin" />
            ) : character.is_locked ? (
              <Lock className="size-3.5 mr-1" />
            ) : (
              <LockOpen className="size-3.5 mr-1" />
            )}
            {character.is_locked ? "解锁" : "锁定"}
          </Button>

          {/* Regenerate */}
          {!regenConfirm ? (
            <Button
              variant="ghost"
              size="sm"
              className="text-neutral-400 hover:text-amber-400 hover:bg-neutral-700 h-8 px-2 ml-auto"
              onClick={() => setRegenConfirm(true)}
            >
              <RefreshCw className="size-3.5 mr-1" />
              重新生成
            </Button>
          ) : (
            <div className="flex items-center gap-1 ml-auto">
              <Button
                variant="ghost"
                size="sm"
                className="text-red-400 hover:text-red-300 hover:bg-red-950/30 h-8 px-2"
                onClick={() => {
                  onRegenerate(character);
                  setRegenConfirm(false);
                }}
              >
                确认
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-neutral-400 hover:text-white hover:bg-neutral-700 h-8 px-2"
                onClick={() => setRegenConfirm(false)}
              >
                取消
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function CharactersPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [characters, setCharacters] = useState<CharacterResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit dialog
  const [editingCharacter, setEditingCharacter] =
    useState<CharacterResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  // --- Fetch ---
  const fetchCharacters = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCharacters(projectId);
      setCharacters(data.characters);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载角色列表失败");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchCharacters();
  }, [fetchCharacters]);

  // --- Edit ---
  const handleEdit = useCallback((ch: CharacterResponse) => {
    setEditingCharacter(ch);
    setEditOpen(true);
  }, []);

  const handleSaveEdit = useCallback(
    async (data: CharacterUpdateRequest) => {
      if (!editingCharacter) return;
      await updateCharacter(projectId, editingCharacter.character_id, data);
      await fetchCharacters();
    },
    [projectId, editingCharacter, fetchCharacters]
  );

  // --- Lock toggle ---
  const handleToggleLock = useCallback(
    async (ch: CharacterResponse) => {
      await updateCharacter(projectId, ch.character_id, {
        is_locked: !ch.is_locked,
      });
      await fetchCharacters();
    },
    [projectId, fetchCharacters]
  );

  // --- Regenerate ---
  const handleRegenerate = useCallback(
    async (ch: CharacterResponse) => {
      await regenerateCharacter(projectId, ch.character_id);
      await fetchCharacters();
    },
    [projectId, fetchCharacters]
  );

  // --- Render: loading ---
  if (loading) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-6xl mx-auto min-h-[400px] flex items-center justify-center">
          <Loading message="加载角色库..." />
        </div>
      </main>
    );
  }

  // --- Render: error ---
  if (error) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-6xl mx-auto">
          <ErrorState
            message={error}
            retry={() => fetchCharacters()}
          />
        </div>
      </main>
    );
  }

  // --- Render: empty ---
  if (characters.length === 0) {
    return (
      <main className="min-h-screen bg-neutral-950 p-8">
        <div className="max-w-6xl mx-auto">
          <PageHeader
            title="角色库"
            description="管理故事中的角色设定"
            backHref={`/projects/${projectId}`}
          />
          <EmptyState
            icon={<Users className="size-8" />}
            title="暂无角色"
            description="请先完成故事分析以生成角色"
          />
        </div>
      </main>
    );
  }

  // --- Render: populated ---
  return (
    <main className="min-h-screen bg-neutral-950 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <PageHeader
          title="角色库"
          description={`共 ${total} 个角色 — 管理角色设定、锁定关键角色`}
          backHref={`/projects/${projectId}`}
        />

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {characters.map((ch) => (
            <CharacterCard
              key={ch.id}
              character={ch}
              onEdit={handleEdit}
              onToggleLock={handleToggleLock}
              onRegenerate={handleRegenerate}
            />
          ))}
        </div>

        {/* Edit dialog */}
        <EditCharacterDialog
          open={editOpen}
          character={editingCharacter}
          onClose={() => {
            setEditOpen(false);
            setEditingCharacter(null);
          }}
          onSave={handleSaveEdit}
        />
      </div>
    </main>
  );
}
