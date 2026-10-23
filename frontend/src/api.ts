import type { JobState } from "./types";

const PRODUCTION_API_BASE = "https://pricepilot-uu1b.onrender.com";
const configuredBase = import.meta.env.VITE_API_BASE?.trim() ?? "";
const base = (configuredBase || (import.meta.env.DEV ? "" : PRODUCTION_API_BASE)).replace(/\/$/, "");
async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      const first = body.detail[0] as { msg?: string };
      if (first?.msg) {
        return first.msg;
      }
    }
  } catch {
    return `Request failed (${response.status})`;
  }
  return `Request failed (${response.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (err: unknown) {
    const detail = err instanceof Error && err.message ? err.message : "network error";
    const target = base || "the local /api proxy";
    throw new Error(
      `Could not reach the PricePilot API at ${target}${path}. The browser blocked the request or the service is offline. (${detail})`,
    );
  }
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return (await response.json()) as T;
}

export function startSearch(product: string): Promise<{ job_id: string }> {
  return request("/api/search", {
    method: "POST",
    body: JSON.stringify({ product }),
  });
}

export function getJob(jobId: string): Promise<JobState> {
  return request(`/api/jobs/${jobId}`);
}

export function stopJob(jobId: string): Promise<JobState> {
  return request(`/api/jobs/${jobId}/stop`, { method: "POST" });
}
