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
import { Loader2, AlertCircle, SearchX, FlaskConical } from "lucide-react";

const IS_DEMO = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";

type AppState = "idle" | "searching" | "done" | "error";

export default function HomePage() {
  const [state, setState] = useState<AppState>(IS_DEMO ? "done" : "idle");
  const [job, setJob] = useState<SearchJob | null>(null);
  const [listings, setListings] = useState<Listing[]>(IS_DEMO ? DEMO_LISTINGS : []);
  const [error, setError] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<JobDebugInfo | null>(null);

  const [sortBy, setSortBy] = useState<"rent" | "size" | "age">("rent");
  const [filterSource, setFilterSource] = useState<string>("all");

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

  const displayedListings = listings
    .filter((l) => filterSource === "all" || l.source === filterSource)
    .sort((a, b) => {
      if (sortBy === "rent") return (a.rent ?? 999999999) - (b.rent ?? 999999999);
      if (sortBy === "size") return (b.size_m2 ?? 0) - (a.size_m2 ?? 0);
      if (sortBy === "age") return (a.building_age_years ?? 9999) - (b.building_age_years ?? 9999);
      return 0;
    });

  const sources = Array.from(new Set(listings.map((l) => l.source)));

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="bg-gradient-to-br from-rose-700 to-rose-900 -mx-6 -mt-8 px-6 pt-10 pb-14 sm:-mx-8 sm:px-8">
        <p className="text-rose-200 text-sm font-medium mb-1 tracking-wide">東京のお部屋を探す</p>
        <h1 className="text-3xl font-bold text-white mb-2">Find your Tokyo apartment</h1>
        <p className="text-rose-200 text-sm">
          We search Suumo, Homes, and Chintai simultaneously and surface the best matches.
        </p>
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
        <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
          <Loader2 className="animate-spin text-blue-500 shrink-0" size={20} />
          <div>
            <div className="font-medium text-blue-800 text-sm">
              {job?.progress ?? (job?.status === "pending" ? "Queuing scrapers…" : "Starting scrapers…")}
            </div>
            <div className="text-xs text-blue-500">
              Running real browsers — takes 30–90 seconds.
            </div>
          </div>
        </div>
      )}

      {state === "error" && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl px-5 py-4">
          <AlertCircle className="text-red-500 shrink-0 mt-0.5" size={18} />
          <div>
            <div className="font-medium text-red-800 text-sm">Search failed</div>
            <div className="text-xs text-red-500">{error}</div>
          </div>
        </div>
      )}

      {/* Results */}
      {state === "done" && (
        <div className="space-y-4">
          {/* Results header */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-gray-600">
              <span className="font-semibold text-gray-900">{displayedListings.length}</span>
              {" "}apartment{displayedListings.length !== 1 ? "s" : ""} found
              {filterSource !== "all" && ` · ${filterSource}`}
              {listings.length !== displayedListings.length && ` (${listings.length} total)`}
            </div>

            <div className="flex items-center gap-3">
              {sources.length > 1 && (
                <div className="flex gap-1.5">
                  <button
                    onClick={() => setFilterSource("all")}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                      filterSource === "all"
                        ? "bg-gray-800 text-white border-gray-800"
                        : "bg-white text-gray-600 border-gray-300 hover:border-gray-500"
                    }`}
                  >All</button>
                  {sources.map((src) => (
                    <button
                      key={src}
                      onClick={() => setFilterSource(src)}
                      className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                        filterSource === src
                          ? "bg-gray-800 text-white border-gray-800"
                          : "bg-white text-gray-600 border-gray-300 hover:border-gray-500"
                      }`}
                    >{src}</button>
                  ))}
                </div>
              )}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-rose-500"
              >
                <option value="rent">Sort: Cheapest first</option>
                <option value="size">Sort: Largest first</option>
                <option value="age">Sort: Newest building</option>
              </select>
            </div>
          </div>

          {displayedListings.length === 0 ? (
            <div className="space-y-4">
              <div className="text-center py-10 text-gray-400">
                <SearchX size={40} className="mx-auto mb-3 opacity-40" />
                <div className="font-medium">No apartments found</div>
                <div className="text-sm mt-1">Try widening your search criteria</div>
              </div>
              {debugInfo && <ScrapeDebugPanel info={debugInfo} defaultOpen={true} />}
            </div>
          ) : (
            <div className="space-y-4">
              <ListingsTable listings={displayedListings} />
              {debugInfo && <ScrapeDebugPanel info={debugInfo} defaultOpen={false} />}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
