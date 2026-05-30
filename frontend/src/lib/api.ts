import axios from "axios";
import Cookies from "js-cookie";

const api = axios.create({
  baseURL: `http://localhost:8000/api/v1`,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = Cookies.get("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      Cookies.remove("access_token");
      Cookies.remove("refresh_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  register: (data: { email: string; password: string; full_name?: string; org_name: string }) =>
    api.post("/auth/register", data),
  login: (data: { email: string; password: string }) =>
    api.post("/auth/login", data),
  me: () => api.get("/auth/me"),
};

// ── Projects ──────────────────────────────────────────────────────────────────
export const projectsApi = {
  list: () => api.get("/projects"),
  get: (id: string) => api.get(`/projects/${id}`),
  create: (data: object) => api.post("/projects", data),
  update: (id: string, data: object) => api.patch(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
};

// ── Crawls ────────────────────────────────────────────────────────────────────
export const crawlsApi = {
  start: (projectId: string) => api.post(`/projects/${projectId}/crawls`),
  list: (projectId: string) => api.get(`/projects/${projectId}/crawls`),
  getSummary: (projectId: string, crawlId: string) =>
    api.get(`/projects/${projectId}/crawls/${crawlId}`),
  getPages: (projectId: string, crawlId: string, params?: object) =>
    api.get(`/projects/${projectId}/crawls/${crawlId}/pages`, { params }),
  getIssues: (projectId: string, crawlId: string, params?: object) =>
    api.get(`/projects/${projectId}/crawls/${crawlId}/issues`, { params }),
};

// ── Tasks ─────────────────────────────────────────────────────────────────────
export const tasksApi = {
  list: (projectId: string, params?: object) =>
    api.get(`/projects/${projectId}/tasks`, { params }),
  getBoard: (projectId: string) =>
    api.get(`/projects/${projectId}/tasks/board`),
  create: (projectId: string, data: object) =>
    api.post(`/projects/${projectId}/tasks`, data),
  update: (projectId: string, taskId: string, data: object) =>
    api.patch(`/projects/${projectId}/tasks/${taskId}`, data),
  delete: (projectId: string, taskId: string) =>
    api.delete(`/projects/${projectId}/tasks/${taskId}`),
  bulkUpdate: (projectId: string, taskIds: string[], data: object) =>
    api.post(`/projects/${projectId}/tasks/bulk-update`, { task_ids: taskIds, ...data }),
};

// ── Phase 2 API clients ───────────────────────────────────────────────────────

export const keywordsApi = {
  list:     (pid: string, params?: object) => api.get(`/projects/${pid}/keywords`, { params }),
  research: (pid: string, data: object)    => api.post(`/projects/${pid}/keywords/research`, data),
  suggest:  (pid: string, seed: string)    => api.post(`/projects/${pid}/keywords/suggest`, { seed_keyword: seed }),
  cluster:  (pid: string)                  => api.post(`/projects/${pid}/keywords/cluster`),
  update:   (pid: string, kid: string, d: object) => api.patch(`/projects/${pid}/keywords/${kid}`, d),
  delete:   (pid: string, kid: string)     => api.delete(`/projects/${pid}/keywords/${kid}`),
  paa:      (pid: string, kid: string)     => api.get(`/projects/${pid}/keywords/${kid}/paa`),
};

export const rankApi = {
  summary:    (pid: string, params?: object) => api.get(`/projects/${pid}/ranks`, { params }),
  history:    (pid: string, kid: string, params?: object) => api.get(`/projects/${pid}/ranks/history/${kid}`, { params }),
  stats:      (pid: string)                  => api.get(`/projects/${pid}/ranks/stats`),
  checkNow:   (pid: string)                  => api.post(`/projects/${pid}/ranks/check-now`),
};

export const onpageApi = {
  analyze: (pid: string, data: object) => api.post(`/projects/${pid}/onpage/analyze`, data),
  list:    (pid: string)               => api.get(`/projects/${pid}/onpage`),
  get:     (pid: string, aid: string)  => api.get(`/projects/${pid}/onpage/${aid}`),
};

export const contentApi = {
  list:            (pid: string)                       => api.get(`/projects/${pid}/content`),
  create:          (pid: string, data: object)         => api.post(`/projects/${pid}/content`, data),
  get:             (pid: string, cid: string)          => api.get(`/projects/${pid}/content/${cid}`),
  generateArticle: (pid: string, cid: string)          => api.post(`/projects/${pid}/content/${cid}/generate-article`),
  update:          (pid: string, cid: string, d: object) => api.patch(`/projects/${pid}/content/${cid}`, d),
  delete:          (pid: string, cid: string)          => api.delete(`/projects/${pid}/content/${cid}`),
};

export const integrationsApi = {
  list:           (pid: string)              => api.get(`/projects/${pid}/integrations`),
  getOAuthUrl:    (pid: string)              => api.get(`/projects/${pid}/integrations/gsc/oauth-url`),
  connectMock:    (pid: string, data: object)=> api.post(`/projects/${pid}/integrations/gsc/connect-mock`, data),
  disconnect:     (pid: string, iid: string) => api.delete(`/projects/${pid}/integrations/${iid}`),
  sync:           (pid: string, iid: string) => api.post(`/projects/${pid}/integrations/${iid}/sync`),
  gscPerformance: (pid: string, params?: object) => api.get(`/projects/${pid}/integrations/gsc/performance`, { params }),
  gscTopQueries:  (pid: string, params?: object) => api.get(`/projects/${pid}/integrations/gsc/top-queries`, { params }),
};

export const reportsApi = {
  list:     (pid: string)              => api.get(`/projects/${pid}/reports`),
  create:   (pid: string, data: object)=> api.post(`/projects/${pid}/reports`, data),
  download: (pid: string, rid: string) => api.get(`/projects/${pid}/reports/${rid}/download`, { responseType: "blob" }),
  delete:   (pid: string, rid: string) => api.delete(`/projects/${pid}/reports/${rid}`),
};

// ── Phase 3 API clients ───────────────────────────────────────────────────────

export const backlinksApi = {
  fetch:              (pid: string, limit?: number) => api.post(`/projects/${pid}/backlinks/fetch`, {}, { params: { limit } }),
  list:               (pid: string, params?: object) => api.get(`/projects/${pid}/backlinks`, { params }),
  profile:            (pid: string) => api.get(`/projects/${pid}/backlinks/profile`),
  anchorDistribution: (pid: string) => api.get(`/projects/${pid}/backlinks/anchor-distribution`),
  disavowCandidates:  (pid: string, threshold?: number) => api.get(`/projects/${pid}/backlinks/disavow-candidates`, { params: { threshold } }),
  gapAnalysis:        (pid: string, data: object) => api.post(`/projects/${pid}/backlinks/gap-analysis`, data),
};

export const competitorsApi = {
  list:           (pid: string) => api.get(`/projects/${pid}/competitors`),
  add:            (pid: string, data: object) => api.post(`/projects/${pid}/competitors`, data),
  remove:         (pid: string, cid: string) => api.delete(`/projects/${pid}/competitors/${cid}`),
  check:          (pid: string, cid: string) => api.post(`/projects/${pid}/competitors/${cid}/check`),
  events:         (pid: string, cid: string) => api.get(`/projects/${pid}/competitors/${cid}/events`),
  brandMentions:  (pid: string) => api.get(`/projects/${pid}/competitors/brand-mentions`),
};

export const linkBuildingApi = {
  pipeline:    (pid: string) => api.get(`/projects/${pid}/link-building/pipeline`),
  list:        (pid: string, params?: object) => api.get(`/projects/${pid}/link-building`, { params }),
  add:         (pid: string, data: object) => api.post(`/projects/${pid}/link-building`, data),
  update:      (pid: string, lid: string, data: object) => api.patch(`/projects/${pid}/link-building/${lid}`, data),
  remove:      (pid: string, lid: string) => api.delete(`/projects/${pid}/link-building/${lid}`),
  sendEmail:   (pid: string, lid: string, data: object) => api.post(`/projects/${pid}/link-building/${lid}/emails`, data),
  importGap:   (pid: string, domains: string[]) => api.post(`/projects/${pid}/link-building/import-gap`, { domains }),
};

export const analyticsApi = {
  cannibalization: (pid: string, refresh?: boolean) => api.get(`/projects/${pid}/analytics/cannibalization`, { params: { refresh } }),
  roiForecast:     (pid: string, params?: object) => api.get(`/projects/${pid}/analytics/roi-forecast`, { params }),
  keywordForecast: (pid: string, kid: string, params?: object) => api.get(`/projects/${pid}/analytics/keyword/${kid}/forecast`, { params }),
  trafficForecast: (pid: string, params?: object) => api.get(`/projects/${pid}/analytics/traffic-forecast`, { params }),
};

export const billingApi = {
  plans:      () => api.get("/billing/plans"),
  usage:      () => api.get("/billing/usage"),
  checkout:   (data: object) => api.post("/billing/checkout", data),
  devUpgrade: (plan: string) => api.post("/billing/dev-upgrade", { plan }),
};
