import axios, { AxiosInstance } from "axios";
import type {
  AskRequest,
  AskResponse,
  ContextRequest,
  ContextResponse,
  GitRefreshResponse,
  HealthResponse,
  IndexResponse,
  StatusResponse,
} from "@local-code-brain/shared";

/** Typed HTTP client for the Python brain daemon. */
export class BrainDaemonClient {
  private readonly http: AxiosInstance;

  constructor(host: string, port: number) {
    this.http = axios.create({
      baseURL: `http://${host}:${port}`,
      timeout: 600_000,
      headers: { "Content-Type": "application/json" },
    });
  }

  async health(): Promise<HealthResponse> {
    const { data } = await this.http.get<HealthResponse>("/health", { timeout: 2_000 });
    return data;
  }

  async isAlive(): Promise<boolean> {
    try {
      await this.health();
      return true;
    } catch {
      return false;
    }
  }

  async index(full = true): Promise<IndexResponse> {
    const { data } = await this.http.post<IndexResponse>("/index", { full });
    return data;
  }

  async status(): Promise<StatusResponse> {
    const { data } = await this.http.get<StatusResponse>("/status");
    return data;
  }

  async context(req: ContextRequest): Promise<ContextResponse> {
    const { data } = await this.http.post<ContextResponse>("/context", req);
    return data;
  }

  /** Public entry point for repository questions; routes local vs AI. */
  async ask(req: AskRequest): Promise<AskResponse> {
    const { data } = await this.http.post<AskResponse>("/ask", req);
    return data;
  }

  async gitRefresh(): Promise<GitRefreshResponse> {
    const { data } = await this.http.post<GitRefreshResponse>("/git-refresh", {});
    return data;
  }

  async enqueueChanges(paths: string[], eventType = "modified"): Promise<void> {
    await this.http.post("/changes/enqueue", { paths, eventType });
  }

  async startWatch(): Promise<void> {
    await this.http.post("/watch/start", {});
  }

  async stopWatch(): Promise<void> {
    await this.http.post("/watch/stop", {});
  }
}
