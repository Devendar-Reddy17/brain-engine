import axios, { AxiosInstance } from "axios";
import type {
  AskRequest,
  AskResponse,
  ContextRequest,
  ContextResponse,
  HealthResponse,
} from "@local-code-brain/shared";

/** Minimal daemon client for the MCP server (read-only context retrieval). */
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

  async context(req: ContextRequest): Promise<ContextResponse> {
    const { data } = await this.http.post<ContextResponse>("/context", req);
    return data;
  }

  /** Public entry point for repository questions; routes local vs AI. */
  async ask(req: AskRequest): Promise<AskResponse> {
    const { data } = await this.http.post<AskResponse>("/ask", req);
    return data;
  }
}
