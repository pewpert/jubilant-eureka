const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SearchCriteria {
  wards: string[];
  station: string | null;
  rent_min: number;
  rent_max: number;
  size_min_m2: number;
  size_max_m2: number;
  floor_plans: string[];
  walk_minutes: number;
  building_age_max: number;
  sources: string[];
  max_pages: number;
}

export interface Listing {
  id: string;
  source: string;
  source_url: string;
  title: string;
  building_name: string | null;
  rent: number | null;
  management_fee: number | null;
  deposit: number | null;
  key_money: number | null;
  address: string | null;
  ward: string | null;
  nearest_station: string | null;
  nearest_line: string | null;
  walk_minutes: number | null;
  floor_plan: string | null;
  size_m2: number | null;
  floor: number | null;
  total_floors: number | null;
  building_age_years: number | null;
  built_year: number | null;
  building_type: string | null;
  features: string[] | null;
  image_url: string | null;
  scraped_at: string;
  _excluded_reason?: string;
  _missed_filter?: string;
}

export interface SearchJob {
  id: string;
  status: "pending" | "running" | "completed" | "failed";
  criteria: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
  total_results: number;
  error: string | null;
  progress: string | null;
  scrape_stats: Record<string, unknown> | null;
  listings?: Listing[];
}

// --- Debug types ---

export interface ExclusionBreakdown {
  rent: number;
  size: number;
  walk: number;
  building_age: number;
  floor_plan: number;
  unparseable_rent: number;
}

export interface SourceDebugStats {
  url_used: string | null;
  raw_count: number;
  passed_count: number;
  excluded_by: ExclusionBreakdown;
  error: string | null;
  blocked: boolean;
  sample_excluded: Listing[];
  sample_near_miss: Listing[];
}

export interface JobDebugInfo {
  job_id: string;
  status: string;
  criteria: Record<string, unknown>;
  per_source: Record<string, SourceDebugStats>;
  total_raw: number;
  total_passed: number;
  dominant_filter: string | null;
}

// --- API functions ---

export async function submitSearch(criteria: SearchCriteria): Promise<SearchJob> {
  const res = await fetch(`${API_BASE}/api/search/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(criteria),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Failed to submit search");
  }
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<SearchJob> {
  const res = await fetch(`${API_BASE}/api/search/${jobId}/status`);
  if (!res.ok) throw new Error("Failed to fetch job status");
  return res.json();
}

export async function getJobResults(jobId: string): Promise<SearchJob> {
  const res = await fetch(`${API_BASE}/api/search/${jobId}/results`);
  if (!res.ok) throw new Error("Failed to fetch results");
  return res.json();
}

export async function getJobDebug(jobId: string): Promise<JobDebugInfo> {
  const res = await fetch(`${API_BASE}/api/search/${jobId}/debug`);
  if (!res.ok) throw new Error("Failed to fetch debug info");
  return res.json();
}

/** Poll job status until completed or failed. Calls onUpdate on each tick. */
export async function pollUntilDone(
  jobId: string,
  onUpdate: (job: SearchJob) => void,
  intervalMs = 3000,
): Promise<SearchJob> {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const job = await getJobStatus(jobId);
        onUpdate(job);
        if (job.status === "completed" || job.status === "failed") {
          clearInterval(interval);
          resolve(job);
        }
      } catch (e) {
        clearInterval(interval);
        reject(e);
      }
    }, intervalMs);
  });
}

export function formatYen(yen: number | null | undefined): string {
  if (yen == null) return "—";
  if (yen >= 10000) return `¥${(yen / 10000).toFixed(1)}万`;
  return `¥${yen.toLocaleString()}`;
}
