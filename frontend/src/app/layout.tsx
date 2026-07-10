import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import Link from "next/link";
import { ModelConfigGate } from "@/features/model-config/ModelConfigGate";
import "./globals.css";

export const metadata: Metadata = {
  title: "Story Asset Studio - 小说资产图工作台",
  description: "将小说整理为角色、场景和道具参考图资产",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col bg-[#050608] text-white">
        <nav className="fixed top-0 left-0 right-0 z-50 h-14 border-b border-white/10 bg-[#050608]/70 backdrop-blur-xl">
          <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-5 sm:px-8">
            <Link
              href="/projects"
              className="font-serif text-lg font-semibold tracking-normal text-stone-100 transition-colors hover:text-cyan-100"
            >
              StoryAsset
            </Link>
            <Link
              href="/projects"
              className="rounded-full border border-white/12 px-3 py-1.5 text-xs uppercase tracking-normal text-white/58 transition-colors hover:border-white/25 hover:text-white"
            >
              我的项目
            </Link>
          </div>
        </nav>

        <div className="pt-14 flex-1 flex flex-col">
          {children}
        </div>
        <ModelConfigGate />
      </body>
    </html>
  );
}
