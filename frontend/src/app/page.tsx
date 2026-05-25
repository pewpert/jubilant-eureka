"use client";

import { useState, useCallback } from "react";
import SearchForm from "@/components/SearchForm";
import ListingsTable from "@/components/ListingsTable";
import ScrapeDebugPanel from "@/components/ScrapeDebugPanel";
import {
  SearchCriteria,
  Listing,
  SearchJob,
  JobDebugInfo,
  submitSearch,
  pollUntilDone,
  getJobResults,
  getJobDebug,
} from "@/lib/api";
import { DEMO_LISTINGS } from "@/lib/demo-data";
import { Loader2, AlertCircle, SearchX, FlaskConical, Upload } from "lucide-react";

const IS_DEMO = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";

type AppState = "idle" | "searching" | "done" | "error";

export default function HomePage() {
  const [state, setState] = useState<AppState>(IS_DEMO ? "done" : "idle");
  const [job, setJob] = useState<SearchJob | null>(null);
  const [listings, setListings] = useState<Listing[]>(IS_DEMO ? DEMO_LISTINGS : []);
  const [error, setError] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<JobDebugInfo | null>(null);

  const [importNote, setImportNote] = useState<string | null>(null);

  const handleImport = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const raw = JSON.parse(String(ev.target?.result ?? "[]"));
        const arr = Array.isArray(raw) ? raw : Array.isArray(raw?.listings) ? raw.listings : null;
        if (!arr) throw new Error("Expected a JSON array of listings");
        setListings(arr as Listing[]);
        setState("done");
        setError(null);
        setJob(null);
        setDebugInfo(null);
        setImportNote(`Imported ${arr.length} listings from ${file.name}`);
      } catch (err) {
        setError(`Import failed: ${err instanceof Error ? err.message : "invalid JSON"}`);
        setState("error");
      }
    };
    reader.readAsText(file);
  }, []);

  const handleSearch = useCallback(async (criteria: SearchCriteria) => {
    setState("searching");
    setError(null);
    setListings([]);
    setJob(null);
    setDebugInfo(null);

    try {
      if (IS_DEMO) {
        await new Promise((r) => setTimeout(r, 1500));
        setListings(DEMO_LISTINGS);
        setState("done");
        return;
      }

      const newJob = await submitSearch(criteria);
      setJob(newJob);

      const finalJob = await pollUntilDone(newJob.id, (updated) => {
        setJob(updated);
      });

      if (finalJob.status === "failed") {
        setError(finalJob.error ?? "Search failed");
        setState("error");
        return;
      }

      const result = await getJobResults(finalJob.id);
      setListings(result.listings ?? []);
      setState("done");

      // Fetch debug info non-blocking — failure should not break the page
      try {
        const debug = await getJobDebug(finalJob.id);
        setDebugInfo(debug);
      } catch {
        // debug info is optional
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setState("error");
    }
  }, []);

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="bg-gradient-to-br from-rose-700 to-rose-900 dark:from-rose-900 dark:to-rose-950 -mx-6 -mt-8 px-6 pt-10 pb-14 sm:-mx-8 sm:px-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-rose-200 text-sm font-medium mb-1 tracking-wide">東京のお部屋を探す</p>
            <h1 className="text-3xl font-bold text-white mb-2">Find your Tokyo apartment</h1>
            <p className="text-rose-200 text-sm">
              We search Suumo, Homes, and Chintai simultaneously and surface the best matches.
            </p>
          </div>
          <label className="shrink-0 inline-flex items-center gap-1.5 bg-white/10 hover:bg-white/20 border border-white/20 text-white text-xs font-medium px-3 py-1.5 rounded-full cursor-pointer transition-colors">
            <Upload size={12} />
            Import JSON
            <input type="file" accept="application/json,.json" onChange={handleImport} className="hidden" />
          </label>
        </div>
        {IS_DEMO && (
          <div className="mt-4 inline-flex items-center gap-2 bg-white/10 border border-white/20 text-white text-xs font-medium px-3 py-1.5 rounded-full">
            <FlaskConical size={13} />
            Demo mode — showing 5 confirmed listings from April 2026 research.
          </div>
        )}
      </div>

      {/* Search form overlapping hero */}
      <div className="-mt-10 relative z-10">
        <SearchForm onSubmit={handleSearch} loading={state === "searching"} />
      </div>

      {/* Status bar */}
      {state === "searching" && (
        <div className="flex items-center gap-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 rounded-xl px-5 py-4">
          <Loader2 className="animate-spin text-blue-500 shrink-0" size={20} />
          <div>
            <div className="font-medium text-blue-800 dark:text-blue-200 text-sm">
              {job?.progress ?? (job?.status === "pending" ? "Queuing scrapers…" : "Starting scrapers…")}
            </div>
            <div className="text-xs text-blue-500 dark:text-blue-400">
              Running real browsers — takes 30–90 seconds.
            </div>
          </div>
        </div>
      )}

      {state === "error" && (
        <div className="flex items-start gap-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-xl px-5 py-4">
          <AlertCircle className="text-red-500 shrink-0 mt-0.5" size={18} />
          <div>
            <div className="font-medium text-red-800 dark:text-red-200 text-sm">Search failed</div>
            <div className="text-xs text-red-500 dark:text-red-400">{error}</div>
          </div>
        </div>
      )}

      {importNote && state === "done" && (
        <div className="text-xs text-gray-500 dark:text-gray-400 italic">{importNote}</div>
      )}

      {/* Results */}
      {state === "done" && (
        <div className="space-y-4">
          {listings.length === 0 ? (
            <div className="space-y-4">
              <div className="text-center py-10 text-gray-400 dark:text-gray-500">
                <SearchX size={40} className="mx-auto mb-3 opacity-40" />
                <div className="font-medium">No apartments found</div>
                <div className="text-sm mt-1">Try widening your search criteria or import a prior JSON export.</div>
              </div>
              {debugInfo && <ScrapeDebugPanel info={debugInfo} defaultOpen={true} />}
            </div>
          ) : (
            <div className="space-y-4">
              <ListingsTable listings={listings} />
              {debugInfo && <ScrapeDebugPanel info={debugInfo} defaultOpen={false} />}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
