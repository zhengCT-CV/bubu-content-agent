import type { Checkpoint, DataCenterArticleDetail, DataCenterOverview, LlmTraceRecord, LlmTraceSummary, Metrics, Project, Publication, RunState } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ code: "HTTP_ERROR", message: response.statusText }));
    throw new ApiError(response.status, error.code, error.message);
  }
  return response.json();
}

export const api = {
  health: () => request<{ status: string; mode: string; skills: Record<string, string[]> }>("/api/health"),
  listProjects: () => request<Project[]>("/api/projects"),
  getProject: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (payload: { name: string; inspiration: string; target_audience: string }) =>
    request<Project>("/api/projects", { method: "POST", body: JSON.stringify(payload) }),
  startRun: (id: string) => request<{ thread_id: string }>(`/api/projects/${id}/runs`, { method: "POST" }),
  getRunState: (threadId: string) => request<RunState>(`/api/runs/${threadId}/state`),
  getRunHistory: (threadId: string) => request<Checkpoint[]>(`/api/runs/${threadId}/history`),
  getLlmTraces: (threadId: string) => request<LlmTraceSummary[]>(`/api/runs/${threadId}/llm-traces`),
  getLlmTrace: (threadId: string, traceId: string) =>
    request<LlmTraceRecord>(`/api/runs/${threadId}/llm-traces/${traceId}`),
  getProjectLlmTraces: (projectId: string) => request<LlmTraceSummary[]>(`/api/projects/${projectId}/llm-traces`),
  getProjectLlmTrace: (projectId: string, traceId: string) =>
    request<LlmTraceRecord>(`/api/projects/${projectId}/llm-traces/${traceId}`),
  resume: (threadId: string, payload: Record<string, unknown>) =>
    request(`/api/runs/${threadId}/resume`, { method: "POST", body: JSON.stringify(payload) }),
  fork: (threadId: string, payload: { checkpoint_id: string; state_patch: Record<string, unknown> }) =>
    request<{ thread_id: string }>(`/api/runs/${threadId}/fork`, { method: "POST", body: JSON.stringify(payload) }),
  publish: (projectId: string, payload: Publication) =>
    request(`/api/projects/${projectId}/publish`, { method: "POST", body: JSON.stringify(payload) }),
  syncMetrics: (projectId: string) =>
    request<{ status: string; synced: number; workflow_resumed?: boolean; matches?: unknown[] }>(`/api/projects/${projectId}/sync-metrics`, { method: "POST" }),
  getMetrics: (projectId: string) => request<Metrics[]>(`/api/projects/${projectId}/metrics`),
  getDataCenterOverview: (refresh = false) =>
    request<DataCenterOverview>(`/api/data-center/overview${refresh ? "?refresh=true" : ""}`),
  getDataCenterArticle: (articleId: string) =>
    request<DataCenterArticleDetail>(`/api/data-center/articles/${encodeURIComponent(articleId)}`),
  eventUrl: (threadId: string) => `${API_BASE}/api/runs/${threadId}/events`,
};
