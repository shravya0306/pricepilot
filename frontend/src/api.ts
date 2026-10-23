import type { JobState } from "./types";

const base = (import.meta.env.VITE_API_BASE || "https://pricepilot-uu1b.onrender.com").replace(/\/$/, "");
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
  } catch {
    throw new Error("Cannot reach the PricePilot API. Start the backend on port 8001.");
  }
  if (!response.ok) {
    const message = await readError(response);
    if (response.status >= 500 && message.startsWith("Request failed")) {
      throw new Error("The PricePilot API is not responding. Start the backend on port 8001.");
    }
    throw new Error(message);
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
