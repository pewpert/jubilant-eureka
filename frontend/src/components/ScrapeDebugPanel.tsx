"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { JobDebugInfo, SourceDebugStats, formatYen } from "@/lib/api";

interface Props {
  info: JobDebugInfo;
  defaultOpen: boolean;
}

const SOURCE_COLORS: Record<string, string> = {
  suumo: "bg-green-100 text-green-700",
  homes: "bg-orange-100 text-orange-700",
  chintai: "bg-purple-100 text-purple-700",
};

const FILTER_LABELS: Record<string, string> = {
  rent: "Rent",
  size: "Size",
  walk: "Walk",
  building_age: "Age",
  floor_plan: "Layout",
  unparseable_rent: "Parse err",
};

function sourceStatus(stats: SourceDebugStats): { label: string; color: string; icon: React.ReactNode } {
  if (stats.blocked) return { label: "Blocked", color: "text-red-600", icon: <XCircle size={14} /> };
  if (stats.error) return { label: "Error", color: "text-red-600", icon: <XCircle size={14} /> };
  if (stats.raw_count === 0) return { label: "No results", color: "text-amber-600", icon: <AlertTriangle size={14} /> };
  if (stats.passed_count === 0) return { label: "All filtered", color: "text-amber-600", icon: <AlertTriangle size={14} /> };
  return { label: `${stats.passed_count} passed`, color: "text-green-600", icon: <CheckCircle size={14} /> };
}

export default function ScrapeDebugPanel({ info, defaultOpen }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [showSamples, setShowSamples] = useState(false);

  const sources = Object.entries(info.per_source);
  const allSamples = sources.flatMap(([, s]) => s.sample_excluded);
  const allNearMiss = sources.flatMap(([, s]) => s.sample_near_miss ?? []);
  const blockedSources = sources.filter(([, s]) => s.blocked).map(([name]) => name);

  const noneScraped = info.total_raw === 0;
  const allFiltered = info.total_raw > 0 && info.total_passed === 0;

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden text-sm">
      {/* Header toggle */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <span className="font-medium text-gray-700 flex items-center gap-2">
          {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          Scrape details
          <span className="text-xs font-normal text-gray-400">
            {info.total_raw} scraped · {info.total_passed} passed filters
          </span>
        </span>
        {(noneScraped || allFiltered) && (
          <span className="text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
            {noneScraped ? "Nothing scraped" : "All excluded by filters"}
          </span>
        )}
      </button>

      {open && (
        <div className="divide-y divide-gray-100">
          {/* Diagnostic banners */}
          {blockedSources.length > 0 && (
            <div className="px-4 py-3 bg-red-50 border-b border-red-100 text-red-800 text-xs">
              <strong>{blockedSources.map((s) => s.toUpperCase()).join(", ")} blocked this request.</strong>{" "}
              The site returned a rate-limit page. Try again later or deploy from a different IP.
            </div>
          )}
          {allFiltered && info.dominant_filter && (
            <div className="px-4 py-3 bg-amber-50 border-b border-amber-100 text-amber-800 text-xs">
              <strong>Filters excluded all {info.total_raw} scraped listings.</strong>{" "}
              Most excluded by: <strong>{FILTER_LABELS[info.dominant_filter] ?? info.dominant_filter}</strong>.
              Try widening that filter.
            </div>
          )}
          {noneScraped && blockedSources.length === 0 && (
            <div className="px-4 py-3 bg-red-50 border-b border-red-100 text-red-800 text-xs">
              <strong>Scrapers returned 0 listings.</strong>{" "}
              Sites may be blocking requests or the search area had no matches.
            </div>
          )}

          {/* Per-source table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-gray-500 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Source</th>
                  <th className="px-4 py-2 text-left font-medium">Status</th>
                  <th className="px-4 py-2 text-right font-medium">Scraped</th>
                  <th className="px-4 py-2 text-right font-medium">Passed</th>
                  <th className="px-4 py-2 text-right font-medium">Rent</th>
                  <th className="px-4 py-2 text-right font-medium">Size</th>
                  <th className="px-4 py-2 text-right font-medium">Walk</th>
                  <th className="px-4 py-2 text-right font-medium">Age</th>
                  <th className="px-4 py-2 text-right font-medium">Layout</th>
                  <th className="px-4 py-2 text-left font-medium">URL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sources.map(([source, stats]) => {
                  const st = sourceStatus(stats);
                  const excl = stats.excluded_by;
                  return (
                    <tr key={source} className="hover:bg-gray-50">
                      <td className="px-4 py-2">
                        <span className={`font-semibold px-2 py-0.5 rounded-full text-xs ${SOURCE_COLORS[source] ?? "bg-gray-100 text-gray-600"}`}>
                          {source.toUpperCase()}
                        </span>
                      </td>
                      <td className={`px-4 py-2 flex items-center gap-1 ${st.color}`}>
                        {st.icon}
                        {stats.error ? (
                          <span title={stats.error} className="truncate max-w-[120px]">{stats.error}</span>
                        ) : st.label}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-700">{stats.raw_count}</td>
                      <td className={`px-4 py-2 text-right font-medium ${stats.passed_count > 0 ? "text-green-700" : "text-gray-400"}`}>
                        {stats.passed_count}
                      </td>
                      {(["rent", "size", "walk", "building_age", "floor_plan"] as const).map((k) => (
                        <td key={k} className={`px-4 py-2 text-right ${(excl as Record<string, number>)[k] > 0 ? "text-red-600 font-medium" : "text-gray-300"}`}>
                          {(excl as Record<string, number>)[k] || "—"}
                        </td>
                      ))}
                      <td className="px-4 py-2">
                        {stats.url_used ? (
                          <a
                            href={stats.url_used}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:text-blue-700 flex items-center gap-1"
                            title={stats.url_used}
                          >
                            <ExternalLink size={11} />
                            <span className="truncate max-w-[160px]">{stats.url_used.replace("https://", "")}</span>
                          </a>
                        ) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Near-miss listings — failed exactly one filter, show first so user sees what loosening would unlock */}
          {allNearMiss.length > 0 && (
            <div className="px-4 py-3 bg-amber-50/50">
              <div className="text-xs font-medium text-amber-900 mb-2">
                {allNearMiss.length} close match{allNearMiss.length !== 1 ? "es" : ""} (failed just one filter)
              </div>
              <div className="overflow-x-auto rounded-lg border border-amber-200">
                <table className="w-full text-xs">
                  <thead className="bg-amber-100/60 text-amber-900 uppercase tracking-wide">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Building</th>
                      <th className="px-3 py-2 text-right font-medium">Rent</th>
                      <th className="px-3 py-2 text-right font-medium">Size</th>
                      <th className="px-3 py-2 text-right font-medium">Walk</th>
                      <th className="px-3 py-2 text-left font-medium">Layout</th>
                      <th className="px-3 py-2 text-left font-medium">Only missed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-amber-100 bg-white">
                    {allNearMiss.map((l, i) => (
                      <tr key={i}>
                        <td className="px-3 py-2 truncate max-w-[180px]" title={l.building_name ?? l.title}>
                          {l.building_name ?? l.title ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-right">{formatYen(l.rent)}</td>
                        <td className="px-3 py-2 text-right">{l.size_m2 != null ? `${l.size_m2}m²` : "—"}</td>
                        <td className="px-3 py-2 text-right">{l.walk_minutes != null ? `${l.walk_minutes}min` : "—"}</td>
                        <td className="px-3 py-2">{l.floor_plan ?? "—"}</td>
                        <td className="px-3 py-2 text-amber-800 font-medium">
                          {FILTER_LABELS[l._missed_filter ?? ""] ?? l._missed_filter ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sample excluded listings toggle */}
          {allSamples.length > 0 && (
            <div className="px-4 py-3 bg-gray-50">
              <button
                onClick={() => setShowSamples((v) => !v)}
                className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
              >
                {showSamples ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                {showSamples ? "Hide" : "Show"} {allSamples.length} excluded sample{allSamples.length !== 1 ? "s" : ""}
              </button>

              {showSamples && (
                <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-100 text-gray-500 uppercase tracking-wide">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">Building</th>
                        <th className="px-3 py-2 text-right font-medium">Rent</th>
                        <th className="px-3 py-2 text-right font-medium">Size</th>
                        <th className="px-3 py-2 text-right font-medium">Walk</th>
                        <th className="px-3 py-2 text-right font-medium">Age</th>
                        <th className="px-3 py-2 text-left font-medium">Layout</th>
                        <th className="px-3 py-2 text-left font-medium text-red-600">Excluded by</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 bg-red-50/30">
                      {allSamples.map((l, i) => (
                        <tr key={i}>
                          <td className="px-3 py-2 truncate max-w-[180px]" title={l.building_name ?? l.title}>
                            {l.building_name ?? l.title ?? "—"}
                          </td>
                          <td className="px-3 py-2 text-right">{formatYen(l.rent)}</td>
                          <td className="px-3 py-2 text-right">{l.size_m2 != null ? `${l.size_m2}m²` : "—"}</td>
                          <td className="px-3 py-2 text-right">{l.walk_minutes != null ? `${l.walk_minutes}min` : "—"}</td>
                          <td className="px-3 py-2 text-right">{l.building_age_years != null ? `${l.building_age_years}yr` : "—"}</td>
                          <td className="px-3 py-2">{l.floor_plan ?? "—"}</td>
                          <td className="px-3 py-2 text-red-600 font-medium">
                            {FILTER_LABELS[l._excluded_reason ?? ""] ?? l._excluded_reason ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
