"use client";

import { useState, useCallback } from "react";
import SearchForm from "@/components/SearchForm";
import ListingCard from "@/components/ListingCard";
import {
  SearchCriteria,
  Listing,
  SearchJob,
  submitSearch,
  pollUntilDone,
  getJobResults,
} from "@/lib/api";
import { Loader2, AlertCircle, SearchX } from "lucide-react";

type AppState = "idle" | "searching" | "done" | "error";

export default function HomePage() {
  const [state, setState] = useState<AppState>("idle");
  const [job, setJob] = useState<SearchJob | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Sort & filter state
  const [sortBy, setSortBy] = useState<"rent" | "size" | "age">("rent");
  const [filterSource, setFilterSource] = useState<string>("all");

  const handleSearch = useCallback(async (criteria: SearchCriteria) => {
    setState("searching");
    setError(null);
    setListings([]);
    setJob(null);

    try {
      const newJob = await submitSearch(criteria);
      setJob(newJob);

      // Poll until the Celery worker finishes
      const finalJob = await pollUntilDone(newJob.id, (updated) => {
        setJob(updated);
      });

      if (finalJob.status === "failed") {
        setError(finalJob.error ?? "Search failed");
        setState("error");
        return;
      }

      // Fetch full results
      const result = await getJobResults(finalJob.id);
      setListings(result.listings ?? []);
      setState("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setState("error");
    }
  }, []);

  // Derived: filtered + sorted listings
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
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-1">Find your Tokyo apartment</h1>
        <p className="text-gray-500 text-sm">
          We search Suumo, Homes, and Chintai simultaneously and aggregate the results.
        </p>
      </div>

      <SearchForm onSubmit={handleSearch} loading={state === "searching"} />

      {/* Status bar */}
      {state === "searching" && job && (
        <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
          <Loader2 className="animate-spin text-blue-500 shrink-0" size={20} />
          <div>
            <div className="font-medium text-blue-800 text-sm">
              {job.status === "pending" ? "Queuing scrapers..." : "Scraping listings..."}
            </div>
            <div className="text-xs text-blue-500">
              This takes 30–90 seconds — we&apos;re running real browsers across multiple sites.
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
              <span className="font-semibold text-gray-900">{displayedListings.length}</span> listings
              {filterSource !== "all" && ` from ${filterSource}`}
              {listings.length !== displayedListings.length && ` (${listings.length} total)`}
            </div>

            <div className="flex items-center gap-3">
              {/* Source filter */}
              {sources.length > 1 && (
                <div className="flex gap-1.5">
                  <button
                    onClick={() => setFilterSource("all")}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                      filterSource === "all"
                        ? "bg-gray-800 text-white border-gray-800"
                        : "bg-white text-gray-600 border-gray-300 hover:border-gray-500"
                    }`}
                  >
                    All
                  </button>
                  {sources.map((src) => (
                    <button
                      key={src}
                      onClick={() => setFilterSource(src)}
                      className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                        filterSource === src
                          ? "bg-gray-800 text-white border-gray-800"
                          : "bg-white text-gray-600 border-gray-300 hover:border-gray-500"
                      }`}
                    >
                      {src}
                    </button>
                  ))}
                </div>
              )}

              {/* Sort */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="rent">Sort: Cheapest first</option>
                <option value="size">Sort: Largest first</option>
                <option value="age">Sort: Newest building</option>
              </select>
            </div>
          </div>

          {displayedListings.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <SearchX size={48} className="mx-auto mb-3 opacity-40" />
              <div className="font-medium">No listings found</div>
              <div className="text-sm mt-1">Try widening your search criteria</div>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {displayedListings.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
