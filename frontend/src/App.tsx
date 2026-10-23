import { useEffect, useState } from "react";
import { getJob, startSearch, stopJob } from "./api";
import { DealBoard } from "./components/DealBoard";
import { InsightCard } from "./components/InsightCard";
import { LogsPanel } from "./components/LogsPanel";
import { Navbar } from "./components/Navbar";
import { SearchPanel } from "./components/SearchPanel";
import type { JobState } from "./types";

export default function App() {
  const [product, setProduct] = useState("");
  const [job, setJob] = useState<JobState | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const running = job?.status === "running";
  const bestDeal = lowestCheckout(job?.deals ?? []);
  const statusText = searchStatus(job, starting, error);

  useEffect(() => {
    if (!job || job.status !== "running") {
      return;
    }
    const jobId = job.job_id;
    const timer = window.setInterval(() => {
      getJob(jobId)
        .then((next) => setJob(next))
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "Lost contact with the search");
        });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status]);

  useEffect(() => {
    const deals = job?.deals ?? [];
    if (!deals.length) {
      return;
    }
    setSelected((current) =>
      current && deals.some((deal) => deal.merchant === current) ? current : deals[0].merchant,
    );
  }, [job]);

  async function onStart() {
    setStarting(true);
    setError(null);
    setJob(null);
    setSelected(null);
    try {
      const created = await startSearch(product);
      const first = await getJob(created.job_id);
      setJob(first);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setStarting(false);
    }
  }

  async function onStop() {
    if (!job) {
      return;
    }
    try {
      setJob(await stopJob(job.job_id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not stop the search");
    }
  }

  return (
    <main>
      <Navbar />
      <hr className="rule" />
      {error ? <p className="banner">{error}</p> : null}
      {job?.error && job.status === "failed" ? <p className="banner">{job.error}</p> : null}
      <SearchPanel
        product={product}
        running={Boolean(running)}
        starting={starting}
        status={statusText}
        onProduct={setProduct}
        onStart={() => void onStart()}
        onStop={() => void onStop()}
      />
      <div className="workspace">
        <DealBoard deals={job?.deals ?? []} selected={selected} onSelect={setSelected} />
        <LogsPanel
          logs={job?.logs ?? []}
          running={Boolean(running)}
          expanded={!job?.insight}
          status={job?.status ?? "idle"}
          stopRequested={Boolean(job?.stop_requested && running)}
        />
      </div>
      <hr className="rule" />
      {job?.insight ? <InsightCard insight={job.insight} bestDeal={bestDeal} /> : null}
    </main>
  );
}

function searchStatus(job: JobState | null, starting: boolean, error: string | null): string {
  if (starting) return "Starting search…";
  if (job?.status === "running" && job.stop_requested) return "Stopping search…";
  if (job?.status === "running") return "Search in progress";
  if (job?.status === "completed") return "Search complete";
  if (job?.status === "stopped") return "Search stopped";
  if (job?.status === "failed") return job.error ?? "Search failed";
  if (error) return error;
  return "Ready to search";
}

function lowestCheckout(deals: JobState["deals"]): JobState["deals"][number] | null {
  if (!deals.length) return null;
  return deals.reduce((best, deal) =>
    deal.summary.checkout_price < best.summary.checkout_price ? deal : best,
  );
}
