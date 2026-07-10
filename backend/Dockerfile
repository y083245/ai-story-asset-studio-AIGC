FROM python:3.12-slim

WORKDIR /app

# 安装编译依赖（asyncpg 等需要）和运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存层
COPY backend/pyproject.toml ./

# 安装项目依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e "."

# 复制业务代码、迁移和运行时模板文档
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY templates ./templates
COPY docs ./docs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
