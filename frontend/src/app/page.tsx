"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  Aperture,
  ArrowRight,
  Bot,
  Flame,
  Images,
  MountainSnow,
  Sparkles,
  Wand2,
} from "lucide-react";

import { Button } from "@/components/ui/button";

const scenes = [
  {
    key: "forest",
    title: "Whale Forest",
    label: "场景资产",
    description: "暗蓝紫的远景、雾化森林和微粒漂浮，用于建立小说空间设定。",
    progress: 42,
    accent: "text-cyan-100",
    icon: MountainSnow,
  },
  {
    key: "fire",
    title: "Fire Beneath",
    label: "角色参考",
    description: "黑底、浅景深、琥珀边缘光，适合悬念、转折和章节收束。",
    progress: 68,
    accent: "text-amber-100",
    icon: Flame,
  },
  {
    key: "edit",
    title: "Asset Board",
    label: "资产看板",
    description: "角色、场景、道具进入同一套可复用视觉资产工作流。",
    progress: 86,
    accent: "text-violet-100",
    icon: Images,
  },
];

const pipeline = [
  { label: "Story", value: "小说解析", icon: Bot },
  { label: "Style", value: "风格识别", icon: Aperture },
  { label: "Extract", value: "资产提取", icon: Wand2 },
  { label: "Image", value: "图片生成", icon: Images },
];

export default function HomePage() {
  const [activeScene, setActiveScene] = useState(scenes[0]);

  return (
    <main className="cinematic-shell relative isolate min-h-[calc(100vh-3.5rem)] overflow-x-hidden bg-[#050608] text-white">
      <Image
        className="absolute inset-0 h-full w-full object-cover opacity-90"
        src="/cinematic-poster.jpg"
        alt=""
        fill
        priority
        sizes="100vw"
        aria-hidden="true"
      />
      <div className="cinematic-vignette absolute inset-0" />
      <div className="cinematic-grain absolute inset-0" />

      <section className="relative z-10 flex min-h-[calc(100vh-3.5rem)] flex-col px-5 py-6 sm:px-8 lg:px-12">
        <div className="flex items-center justify-between text-[0.68rem] uppercase tracking-normal text-white/55">
          <span>Novel Asset Console</span>
          <span className="hidden sm:inline">Character / Scene / Prop Image Pipeline</span>
        </div>

        <div className="grid flex-1 items-center gap-8 py-10 lg:grid-cols-[minmax(0,1fr)_24rem] lg:gap-12">
          <div className="min-w-0 w-full max-w-[calc(100vw-2.5rem)] sm:max-w-3xl">
            <p className="mb-5 flex items-center gap-2 text-xs uppercase tracking-normal text-white/55">
              <Sparkles className="size-3.5 text-cyan-100" />
              Novel to visual asset images
            </p>

            <h1 className="max-w-2xl font-serif text-6xl font-semibold leading-[0.88] tracking-normal text-stone-100 sm:text-7xl lg:text-8xl">
              THE
              <br />
              ASSET
              <br />
              STUDIO
            </h1>

            <p className="mt-7 w-full max-w-[21.75rem] break-words text-sm leading-7 text-white/62 [overflow-wrap:anywhere] sm:max-w-lg sm:text-base">
              上传小说，自动整理人物、场景和道具设定，把文本推进到可生成、可复用的资产图工作流。
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button
                asChild
                size="lg"
                className="h-11 w-full rounded-full border border-white/20 bg-stone-100 px-5 text-neutral-950 shadow-[0_20px_60px_rgba(255,255,255,0.12)] hover:bg-white sm:w-auto"
              >
                <Link href="/projects/new">
                  <Sparkles className="size-4" />
                  创建资产项目
                </Link>
              </Button>
              <Button
                asChild
                variant="outline"
                size="lg"
                className="h-11 w-full rounded-full border-white/18 bg-black/20 px-5 text-white backdrop-blur-md hover:bg-white/10 hover:text-white sm:w-auto"
              >
                <Link href="/projects">
                  打开工作台
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            </div>
          </div>

          <aside className="min-w-0 w-full max-w-sm justify-self-stretch rounded-[8px] border border-white/12 bg-black/28 p-4 shadow-[0_24px_80px_rgba(0,0,0,0.38)] backdrop-blur-xl lg:justify-self-end">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[0.68rem] uppercase tracking-normal text-white/45">Current sequence</p>
                <h2 className="mt-2 font-serif text-3xl leading-none tracking-normal text-stone-100">
                  {activeScene.title}
                </h2>
              </div>
              <span className="rounded-full border border-white/12 px-3 py-1 text-[0.65rem] uppercase tracking-normal text-white/58">
                {activeScene.progress}%
              </span>
            </div>

            <p className="mt-5 min-h-14 break-words text-sm leading-6 text-white/58 [overflow-wrap:anywhere]">
              {activeScene.description}
            </p>

            <div className="mt-6 space-y-3">
              {pipeline.map((item, index) => {
                const Icon = item.icon;

                return (
                  <div key={item.label} className="grid grid-cols-[1.6rem_1fr_auto] items-center gap-3">
                    <span className="grid size-6 place-items-center rounded-full border border-white/12 bg-white/[0.04]">
                      <Icon className="size-3.5 text-white/70" />
                    </span>
                    <div>
                      <p className="text-xs text-white/78">{item.value}</p>
                      <p className="text-[0.65rem] uppercase tracking-normal text-white/35">{item.label}</p>
                    </div>
                    <span className={index < 3 ? "text-cyan-100/80" : "text-amber-100/80"}>
                      {index < 3 ? "ready" : "live"}
                    </span>
                  </div>
                );
              })}
            </div>
          </aside>
        </div>

        <div className="grid gap-4 border-t border-white/10 pt-4 lg:grid-cols-[1fr_auto] lg:items-end">
          <div className="grid gap-2 sm:grid-cols-3">
            {scenes.map((scene) => {
              const Icon = scene.icon;
              const active = activeScene.key === scene.key;

              return (
                <button
                  key={scene.key}
                  type="button"
                  onClick={() => setActiveScene(scene)}
                  className={[
                    "group min-h-24 rounded-[8px] border p-4 text-left transition-all duration-300",
                    active
                      ? "border-white/28 bg-white/[0.10] shadow-[0_18px_60px_rgba(0,0,0,0.28)]"
                      : "border-white/10 bg-black/18 hover:border-white/22 hover:bg-white/[0.07]",
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase tracking-normal text-white/42">0{scenes.indexOf(scene) + 1}</span>
                    <Icon className={`size-4 ${active ? scene.accent : "text-white/42"}`} />
                  </div>
                  <p className="mt-4 text-sm font-medium text-stone-100">{scene.label}</p>
                  <div className="mt-3 h-px overflow-hidden bg-white/10">
                    <div
                      className="h-full bg-stone-100 transition-all duration-500"
                      style={{ width: active ? `${scene.progress}%` : "18%" }}
                    />
                  </div>
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-4 text-[0.68rem] uppercase tracking-normal text-white/45 lg:justify-end">
            <span>CH</span>
            <div className="h-px w-24 bg-white/16">
              <div className="h-px w-2/3 bg-white/70" />
            </div>
            <span>PR</span>
          </div>
        </div>
      </section>
    </main>
  );
}
