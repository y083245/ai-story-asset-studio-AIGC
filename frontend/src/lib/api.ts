/**
 * Story Asset Studio API 客户端。
 *
 * 封装对后端 FastAPI 的 fetch 调用。
 * 前端只依赖 API 契约，不理解模型原始响应。
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.trim() || "";

export interface HealthResponse {
  status: string;
  version: string;
}

export interface ProjectCreateRequest {
  title: string;
  aspect_ratio: string;
  style_mode: "auto" | "manual";
  manual_style?: string;
}

export interface ProjectResponse {
  project_id: string;
  status: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options?: RequestInit
  ): Promise<T> {
    const url = joinApiUrl(this.baseUrl, path);
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
    if (!res.ok) {
      throw new Error(`API error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async healthCheck(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
  }

  async createProject(data: ProjectCreateRequest): Promise<ProjectResponse> {
    return this.request<ProjectResponse>("/api/projects", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
}

function joinApiUrl(baseUrl: string, path: string): string {
  if (!baseUrl) return path;
  const normalizedBase = baseUrl.replace(/\/+$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (normalizedBase.endsWith("/api") && normalizedPath.startsWith("/api/")) {
    return `${normalizedBase}${normalizedPath.slice(4)}`;
  }

  return `${normalizedBase}${normalizedPath}`;
}

export const api = new ApiClient(API_BASE_URL);
