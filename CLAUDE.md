# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Story Asset Studio 是「小说文本 → 视觉资产图」的开源工作台。只覆盖资产图链路：上传小说 → 分析要素 → 生成角色/场景/道具图 → 质检重试。不包含分镜、视频、剪辑等影视后续环节。

详细说明见 `AGENTS.md` 和 `README.md`。

## 常用命令

### Docker 启动（推荐）

```bash
docker compose -f docker/docker-compose.yml up --build
```

### 后端本地开发

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

### 前端本地开发

```bash
cd frontend
npm install
npm run dev
```

### 测试和检查

```bash
# 后端
cd backend && pytest                           # 运行所有测试
python -m compileall app alembic               # 编译检查
ruff check .                                   # lint

# 前端
cd frontend
npm run build                                  # 构建检查
npm run lint                                   # lint
npm run test                                   # vitest
npm run test:watch                             # vitest watch 模式

# 环境检查
./scripts/doctor.sh
./scripts/reset-data.sh                        # 清空本地数据和生成资产
```

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x async, Alembic, PostgreSQL, Redis |
| 前端 | Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 4, shadcn/Radix UI, TanStack React Query, Zustand, Vitest |
| 模板 | Jinja2, 题材/风格包/模块提示词分离 |
| 部署 | Docker Compose, nginx |

## 后端分层

```
backend/app/
├── main.py              # create_app() → FastAPI 应用，注册中间件和路由
├── config.py            # pydantic-settings，extra="forbid"
├── db/                  # Base, TimestampMixin, UUIDMixin, async session
├── middleware/          # ErrorHandlerMiddleware, RequestIDMiddleware
├── contracts/           # 跨模块共享 Pydantic schema（请求/响应）
├── security/            # API Key 脱敏、敏感信息清洗
└── modules/             # 业务模块，每个模块一个目录
    ├── project/         # 项目 CRUD、归档、复制
    ├── novel_intake/    # 小说上传、清洗、分章分块
    ├── workflow/        # FakeWorkflowRunner、activity 定义、analysis/generation workflow
    ├── story_bible/     # 故事资产圣经聚合
    ├── character_library/  # 角色提取、版本、生成计划
    ├── scene_library/      # 场景提取、锚点、版本、生成计划
    ├── prop_library/       # 道具提取、别名合并、版本、生成计划
    ├── image_asset/        # 图片 prompt 构建、图片生成、资产管理页（library）、回收站（lifecycle）、审计日志（audit）
    ├── quality_retry/      # 图片质检评分、重试决策
    ├── asset_workbench/    # 前端工作台聚合接口
    ├── model_config/       # 模型厂商/模型/Base URL/API Key 本地配置
    ├── provider_adapter/   # 文本模型、图片模型、视觉 QA provider 统一封装
    ├── template_style/     # 题材模板、风格包、模块提示词读取
    ├── storage/            # 本地文件系统和对象存储适配
    └── observability/      # 日志、审计、指标、provider 调用记录
```

### 编码约束

- **Schema → Service → Router**：新 API 先定义 Pydantic schema（`contracts/`），业务逻辑放 service，router 只做参数/依赖/响应转换。
- **数据库**：新表继承 `Base`，需要时间戳用 `TimestampMixin`，主键用 `UUIDMixin`。`get_session()` 正常结束 commit，异常 rollback。
- **新模块**：放在 `backend/app/modules/<name>/`，包含自己的 models、services、routers、schemas。
- **配置**：通过 `backend/app/config.py` 的 `Settings` 类声明，`extra="forbid"` 会拒绝未声明变量。
- **迁移**：初始迁移在 `backend/alembic/versions/20260705_initial_asset_studio.py`，使用 `Base.metadata.create_all()`。

## 工作流系统

使用仓库内 `FakeWorkflowRunner`（非 Temporal/Celery）：

- 本地执行 activity，支持 retry policy、activity history replay、progress callback、signal（如风格确认）、cancel。
- 默认 activity 定义在 `backend/app/modules/workflow/fake_activities.py`。
- 核心流程：`ProjectAnalyzeWorkflow`（分析）→ `AssetGenerationWorkflow`（生图）→ quality check → auto fix。
- `ProjectFullGenerationWorkflow` 是一键「先分析后生成」流程。

## Provider 适配

`backend/app/modules/provider_adapter/registry.py` 控制 provider 选择：

- **文本模型**：统一走 `OpenAICompatibleTextProvider`（`{base_url}/chat/completions`）。
- **图片模型**：`doubao_seedream` → SeedreamProvider, `replicate` → FluxProProvider, `google_imagen` → ImagenProvider, `openai` → DalleProvider。
- **配置优先级**：`local_config/model-providers.json` > `.env` 中的 fallback。
- `local_config/model-providers.json` 包含真实 API Key，不能提交；返回前端时必须脱敏；日志/审计中不能出现完整 Key。

## 模板系统

```
templates/
├── genres/         # 题材/风格基础定义
├── modules/        # 默认模块提示词（角色/场景/道具等）
└── style_packs/    # 按风格覆盖的提示词模板
```

后端通过 `template_style` 模块和各 library 的 prompt builder 读取。不要硬编码长提示词。

## 前端结构

- **页面**：`frontend/src/app/` 下按 Next.js App Router 组织。主要页面：首页 `/`、项目列表 `/projects`、项目内各页面 `/projects/[id]/...`、全局资产管理 `/asset-library`。
- **业务逻辑**：`frontend/src/features/` 下的 hook/component，按功能域划分：`project/`、`novel-upload/`、`story-analysis/`、`character-library/`、`scene-library/`、`prop-library/`、`asset-library/`、`generation-progress/`、`model-config/`。
- **API 封装**：`frontend/src/shared/api/`，通过 `client.ts` 统一处理 base URL、错误、mock 模式。例外：`model-config.ts` 用直接相对路径 fetch（首次配置弹窗不能走 mock）。

## 图片资产生命周期

`ImageAsset` 包含以下生命周期字段（`deleted_at`、`deleted_by`、`purge_after`、`expires_at`、`delete_reason`）：

- **主资产管理页**：`GET /api/image-asset/library` — 按日期→项目→角色/道具/场景分组，只返回 `deleted_at is null` 且未过期的图片。
- **图片回收站**：`GET /api/image-asset/trash` — 手动删除的图片，30 天后自动清理。
- **手动删除**：设置 `deleted_at` + `purge_after`（30 天），不删除物理文件，可恢复。
- **恢复**：清空 `deleted_at`/`purge_after`/`deleted_by`/`delete_reason`，不恢复项目级回收站。
- **永久删除**：先删存储文件，再删关联 `ImageGenerationTask` 和 `ImageAsset` 行，写入持久化审计日志 `image_asset_audit_logs`。
- **半年自动过期**：`expires_at = created_at + 6 个自然月`，到期直接永久删除，不进入回收站。
- **清理脚本**：`python scripts/purge-image-assets.py [--dry-run] [--limit N]`，清理到期回收站图片和过期图片。
- 批量操作（`/batch-delete`、`/batch-restore`、`/batch-permanent-delete`）逐项校验权限，返回逐项成功/失败明细。
- 审计日志 API：`GET /api/image-asset/audit-logs`，持久化到 `image_asset_audit_logs` 表，服务重启后仍可查询；不记录 prompt、完整 URL、API Key。

## 关键约束

- 不引入分镜、视频、剪辑、时间轴等非资产图功能。
- `local_config/`、`local_storage/`、`.env`、`.env.local`、`node_modules/`、`.next/` 不能提交。
- 修改 model provider、Base URL、默认模型时，同步更新 `README.md`、`docs/model-config.md` 和 `AGENTS.md`。
- 视觉 QA 使用独立配置项（`vision_quality_*`），与图片生成 provider 解耦。
- `prop_usage` 在存在 `owner_character_id` 时覆盖角色持道具图场景，归属道具库。
- 资产管理页 `/asset-library` 是全局跨项目页面，不复用项目内 `/projects/[id]/assets` 工作台。
- 已进入项目级回收站的项目图片仍需在资产管理页展示，并标注「项目已在回收站」。
