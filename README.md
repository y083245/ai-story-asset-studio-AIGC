# Story Asset Studio

Story Asset Studio 是一个把小说文本转换成角色、场景、道具视觉资产图的开源 AI 工作台。它覆盖小说导入、故事要素分析、提示词生成、图片生成、视觉质检、重试和跨项目资产管理。

项目只处理视觉资产图，不包含分镜、视频生成、剪辑、字幕或时间轴。

> [!IMPORTANT]
> 本项目必须通过 Docker 部署运行。受支持的部署入口是仓库提供的 Docker Compose 与一键启动脚本；宿主机直接运行 Python 后端或 Node.js 前端只适合源码调试，不属于部署方式。

## 核心能力

- 导入或粘贴 TXT、DOCX 小说内容，并完成清洗、分章和分块。
- 分析题材、角色、场景、道具并生成 Story Bible。
- 使用题材模板、风格包和模块模板构建最终生图提示词。
- 生成角色正面图、转身图、表情图、场景图和道具图。
- 支持独立的视觉 QA、自动重试和人工复核状态。
- 提供项目内资产工作台和跨项目 `/asset-library` 资产管理页。
- 支持图片回收站、恢复、永久删除、30 天清理和 6 个自然月保留期。
- 文本模型、图片模型和 API Key 可在网页中本地配置。

## Docker 架构

默认 `docker/docker-compose.yml` 会启动完整的单机环境：

| 服务 | 技术 | 地址/端口 | 作用 |
| --- | --- | --- | --- |
| `frontend` | Next.js 16、React 19、TypeScript | `http://localhost:3000` | Web 界面和后端 API 转发。 |
| `backend` | Python 3.12、FastAPI、SQLAlchemy、Alembic | `http://localhost:8000` | API、工作流、Provider 调度和本地文件服务。 |
| `postgres` | PostgreSQL 16 | `localhost:5432` | 项目、分析结果、资产和审计数据。 |
| `redis` | Redis 7 | `localhost:6379` | 缓存和运行时基础设施。 |

后端容器启动时会先执行 `alembic upgrade head`，迁移成功后才启动 API。前端代码构建进 Docker 镜像；后端应用代码在默认单机 Compose 中通过 bind mount 加载。

## 运行要求

- macOS：Docker Desktop。
- Windows：Docker Desktop，使用 Linux containers 模式。
- Linux：Docker Engine 和 Docker Compose v2 插件。
- Docker daemon 必须已启动。
- 本机端口 `3000`、`8000`、`5432`、`6379` 不能被其他程序占用。

宿主机不需要安装 Python、Node.js、PostgreSQL 或 Redis。

检查 Docker Compose：

```bash
docker compose version
```

输出应为 `Docker Compose version v2...` 或更新版本。

## 一键启动

克隆仓库并进入目录：

```bash
git clone https://github.com/y083245/ai-story-asset-studio-AIGC.git
cd ai-story-asset-studio-AIGC
```

### macOS

```bash
./scripts/setup-macos.sh
```

### Linux

```bash
./scripts/setup-linux.sh
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
```

三个脚本都会：

1. 检查 Docker、Compose v2 和 Docker daemon。
2. 首次运行时把 `.env.example` 复制为 `.env`，不会覆盖已有配置。
3. 创建模型配置和本地图片目录，不删除已有数据。
4. 校验 Compose 配置，构建镜像并在后台启动服务。
5. 等待数据库迁移、后端健康检查和前端页面全部可用。
6. 失败时输出容器状态和最近日志，成功后返回终端。

启动成功后打开：

- 前端：<http://localhost:3000>
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>

## 配置模型和 API Key

首次打开前端时，模型配置窗口会引导选择文本模型和图片模型厂商，并填写模型名、Base URL 和 API Key。配置保存在：

```text
local_config/model-providers.json
```

该文件包含 API Key，已被 `.gitignore` 忽略。后端返回浏览器和写日志时只使用脱敏信息。

配置优先级：

1. `local_config/model-providers.json`
2. 根目录 `.env` 中的兼容 fallback

开发配置没有真实 Key 时，系统可以使用 fake provider 跑通基础流程；真实文本分析和图片生成需要用户自己的 Provider API Key。

仓库提供 [local_config.example.json](local_config.example.json) 作为配置格式参考：

```json
{
  "text": {
    "provider_id": "deepseek",
    "model": "deepseek-v4-flash",
    "base_url": "https://api.deepseek.com",
    "api_key": "replace-with-your-text-model-api-key"
  },
  "image": {
    "provider_id": "doubao_seedream",
    "model": "doubao-seedream-5-0-lite-260128",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "api_key": "replace-with-your-seedream-api-key"
  }
}
```

当前内置 Provider：

| 类型 | `provider_id` |
| --- | --- |
| 文本模型 | `openai`、`anthropic`、`google_gemini`、`xai`、`mistral`、`openrouter`、`together`、`siliconflow`、`deepseek`、`aliyun_bailian`、`baidu_qianfan`、`tencent_hunyuan`、`moonshot_kimi`、`zhipu_bigmodel`、`volcengine_ark` |
| 图片模型 | `doubao_seedream`、`replicate`、`google_imagen`、`openai` |

视觉 QA 与图片生成 Provider 独立，可通过 `.env` 中的 `VISION_QUALITY_ENABLED`、`VISION_QUALITY_PROVIDER`、`VISION_QUALITY_MODEL_NAME`、`VISION_QUALITY_PASS_THRESHOLD` 和 `VISION_QUALITY_MAX_RETRIES` 配置。

## 数据和隐私

| 数据 | 保存位置 | 说明 |
| --- | --- | --- |
| 数据库 | Compose 命名卷 `pgdata` | 普通停止或重新构建不会删除。 |
| 模型配置/API Key | `local_config/model-providers.json` | 只保存在本机，不能提交。 |
| 环境 fallback | `.env` | 只保存在本机，不能提交。 |
| 生成图片 | `backend/local_storage/` | 默认本地对象存储目录，不能提交。 |
| 提示词模板 | `templates/` | 仓库内版本化内容。 |

不要把 `.env`、`local_config/`、`backend/local_storage/`、`frontend/node_modules/` 或 `frontend/.next/` 上传到公开仓库。

## 常用 Docker 命令

查看状态：

```bash
docker compose -f docker/docker-compose.yml ps
```

查看前后端实时日志：

```bash
docker compose -f docker/docker-compose.yml logs -f backend frontend
```

停止服务并保留数据库和本地文件：

```bash
docker compose -f docker/docker-compose.yml down
```

重新启动已有容器：

```bash
docker compose -f docker/docker-compose.yml up -d
```

代码更新后，重新运行当前平台的一键启动脚本即可重新构建并启动最新代码。

### 清空所有本地数据

> [!CAUTION]
> 以下脚本会删除 PostgreSQL 数据卷和 `backend/local_storage/` 中的生成图片，操作不可恢复。

macOS/Linux：

```bash
./scripts/reset-data.sh
```

Windows PowerShell：

```powershell
.\scripts\reset-data.ps1
```

## 高级生产模板

`docker/docker-compose.prod.yml` 是需要自行补齐基础设施的高级模板，不是一键启动入口。它只定义 backend、frontend 和 nginx，要求外部提供 PostgreSQL、Redis 以及以下生产环境变量：

- `DATABASE_URL`
- `DATABASE_URL_SYNC`
- `REDIS_URL`
- 安全的 `APP_SECRET_KEY`
- 与实际域名一致的 `CORS_ALLOWED_ORIGINS`
- 生产级用户鉴权和对象存储配置

公网部署前还需要自行配置 TLS、域名、备份、监控和密钥管理。默认 `docker/docker-compose.yml` 面向本机或受控网络中的单机 Docker 使用。

## 故障排查

### 无法连接 Docker daemon

先启动 Docker Desktop；Linux 启动 Docker 服务后重新运行脚本：

```bash
docker info
```

### 端口已被占用

确认 `3000`、`8000`、`5432`、`6379` 没有被其他程序或容器使用：

```bash
docker ps
```

### 首次构建时间较长

第一次启动需要下载 Python、Node.js、PostgreSQL、Redis 基础镜像并安装依赖。不要关闭 Docker；需要观察进度时重新运行脚本，或查看 Compose 日志。

### 前端或后端没有就绪

```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs --tail=200 backend frontend
```

后端迁移失败、API Key 配置错误和前端启动错误都会保留在容器日志中。

### macOS/Linux 提示没有执行权限

```bash
chmod +x scripts/setup-macos.sh scripts/setup-linux.sh
```

## 项目结构

```text
backend/       FastAPI 后端、SQLAlchemy 模型、Alembic 迁移
frontend/      Next.js 前端
templates/     题材、风格包和模块提示词模板
docker/        默认单机 Compose、生产模板和 nginx 配置
scripts/       三平台启动、环境检查、数据重置和资产清理脚本
docs/          提示词参考和项目设计资料
```

## License

MIT
