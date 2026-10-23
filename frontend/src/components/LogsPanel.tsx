import { useEffect, useRef } from "react";
import type { JobStatus, LogEntry } from "../types";

interface LogsPanelProps {
  logs: LogEntry[];
  running: boolean;
  expanded: boolean;
  status: JobStatus | "idle";
  stopRequested: boolean;
}

export function LogsPanel({ logs, running, expanded, status, stopRequested }: LogsPanelProps) {
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scroller.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [logs]);

  return (
    <section className="logs-panel">
      <h2>Live Search Logs</h2>
      <p className="section-copy">Timestamped progress from the current search.</p>
      <div className={expanded ? "log-window" : "log-window log-window-compact"}>
        <div className="log-strip">
          <span className={running ? "status-dot status-dot-live" : "status-dot"} aria-hidden="true" />
          <span>{stripLabel(status, running, stopRequested)}</span>
        </div>
        <div className="logs" ref={scroller} aria-live="polite">
          {logs.length === 0 ? (
            <p className="empty">Logs will appear here while the assistant runs.</p>
          ) : (
            logs.map((entry, index) => (
              <p key={`${entry.ts}-${index}`} className={`log log-${entry.type}`}>
                <span className={`status-dot dot-${entry.type}`} aria-hidden="true" />
                <span className="log-time">[{entry.ts}]</span>
                <span className="log-msg">{entry.msg}</span>
              </p>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

function stripLabel(status: JobStatus | "idle", running: boolean, stopRequested: boolean): string {
  if (running && stopRequested) return "Stopping";
  if (running || status === "running") return "Running";
  if (status === "completed") return "Complete";
  if (status === "stopped") return "Stopped";
  if (status === "failed") return "Failed";
  return "Idle";
}
