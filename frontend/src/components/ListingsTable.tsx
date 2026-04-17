"use client";

import { useMemo, useState } from "react";
import { Download, FileJson, X } from "lucide-react";
import { Listing, formatYen } from "@/lib/api";

interface Props {
  listings: Listing[];
}

const SOURCE_COLORS: Record<string, string> = {
  suumo: "bg-green-100 text-green-700",
  homes: "bg-orange-100 text-orange-700",
  chintai: "bg-purple-100 text-purple-700",
};

type SortKey = "rent" | "size" | "walk" | "age";
type SortDir = "asc" | "desc";

function normalizeStation(s: string | null | undefined): string {
  if (!s) return "";
  return s.replace(/\s+/g, " ").replace(/駅.*$/, "駅").trim();
}

function toCsv(rows: Listing[]): string {
  const headers = [
    "source", "building_name", "title", "rent", "management_fee",
    "floor_plan", "size_m2", "nearest_line", "nearest_station", "walk_minutes",
    "building_age_years", "floor", "address", "source_url",
  ];
  const esc = (v: unknown) => {
    if (v == null) return "";
    const s = String(v).replace(/"/g, '""');
    return /[",\n]/.test(s) ? `"${s}"` : s;
  };
  const lines = [headers.join(",")];
  for (const r of rows) {
    lines.push(headers.map((h) => esc((r as unknown as Record<string, unknown>)[h])).join(","));
  }
  return lines.join("\n");
}

function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ListingsTable({ listings }: Props) {
  const [rentMin, setRentMin] = useState("");
  const [rentMax, setRentMax] = useState("");
  const [sizeMin, setSizeMin] = useState("");
  const [sizeMax, setSizeMax] = useState("");
  const [walkMax, setWalkMax] = useState("");
  const [fpFilters, setFpFilters] = useState<string[]>([]);
  const [srcFilters, setSrcFilters] = useState<string[]>([]);
  const [stationFilter, setStationFilter] = useState("");
  const [lineFilters, setLineFilters] = useState<string[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("rent");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const floorPlanOptions = useMemo(() => {
    const set = new Set<string>();
    for (const l of listings) if (l.floor_plan) set.add(l.floor_plan);
    return Array.from(set).sort();
  }, [listings]);

  const sourceOptions = useMemo(() => {
    const set = new Set<string>();
    for (const l of listings) set.add(l.source);
    return Array.from(set).sort();
  }, [listings]);

  const stationOptions = useMemo(() => {
    const set = new Set<string>();
    for (const l of listings) {
      const s = normalizeStation(l.nearest_station);
      if (s) set.add(s);
    }
    return Array.from(set).sort();
  }, [listings]);

  const lineOptions = useMemo(() => {
    const set = new Set<string>();
    for (const l of listings) if (l.nearest_line) set.add(l.nearest_line);
    return Array.from(set).sort();
  }, [listings]);

  const filtered = useMemo(() => {
    const rMin = parseFloat(rentMin);
    const rMax = parseFloat(rentMax);
    const sMin = parseFloat(sizeMin);
    const sMax = parseFloat(sizeMax);
    const wMax = parseFloat(walkMax);

    const out = listings.filter((l) => {
      if (!isNaN(rMin) && (l.rent == null || l.rent / 10000 < rMin)) return false;
      if (!isNaN(rMax) && (l.rent == null || l.rent / 10000 > rMax)) return false;
      if (!isNaN(sMin) && (l.size_m2 == null || l.size_m2 < sMin)) return false;
      if (!isNaN(sMax) && (l.size_m2 == null || l.size_m2 > sMax)) return false;
      if (!isNaN(wMax) && (l.walk_minutes == null || l.walk_minutes > wMax)) return false;
      if (fpFilters.length > 0 && (!l.floor_plan || !fpFilters.includes(l.floor_plan))) return false;
      if (srcFilters.length > 0 && !srcFilters.includes(l.source)) return false;
      if (stationFilter) {
        const n = normalizeStation(l.nearest_station);
        if (!n.includes(stationFilter)) return false;
      }
      if (lineFilters.length > 0 && (!l.nearest_line || !lineFilters.includes(l.nearest_line))) return false;
      return true;
    });

    const pick = (l: Listing): number | null => {
      switch (sortKey) {
        case "rent": return l.rent;
        case "size": return l.size_m2;
        case "walk": return l.walk_minutes;
        case "age": return l.building_age_years;
      }
    };
    out.sort((a, b) => {
      const av = pick(a);
      const bv = pick(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return sortDir === "asc" ? av - bv : bv - av;
    });
    return out;
  }, [listings, rentMin, rentMax, sizeMin, sizeMax, walkMax, fpFilters, srcFilters, stationFilter, lineFilters, sortKey, sortDir]);

  function toggle<T>(list: T[], v: T, setter: (xs: T[]) => void) {
    setter(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  }

  function clearAll() {
    setRentMin(""); setRentMax(""); setSizeMin(""); setSizeMax("");
    setWalkMax(""); setFpFilters([]); setSrcFilters([]); setStationFilter("");
    setLineFilters([]);
  }

  const hasActiveFilter =
    rentMin || rentMax || sizeMin || sizeMax || walkMax ||
    fpFilters.length > 0 || srcFilters.length > 0 || stationFilter ||
    lineFilters.length > 0;

  const stamp = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <Range label="Rent 万円" min={rentMin} max={rentMax} onMin={setRentMin} onMax={setRentMax} step={0.5} />
          <Range label="Size m²" min={sizeMin} max={sizeMax} onMin={setSizeMin} onMax={setSizeMax} step={1} />
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Walk ≤</label>
            <input
              type="number"
              min={0}
              placeholder="min"
              value={walkMax}
              onChange={(e) => setWalkMax(e.target.value)}
              className="w-20 border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Station</label>
            <input
              list="station-list"
              type="text"
              placeholder="Any"
              value={stationFilter}
              onChange={(e) => setStationFilter(e.target.value)}
              className="w-40 border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
            <datalist id="station-list">
              {stationOptions.map((s) => <option key={s} value={s} />)}
            </datalist>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Sort</label>
            <div className="flex gap-1">
              <select
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as SortKey)}
                className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
              >
                <option value="rent">Rent</option>
                <option value="size">Size</option>
                <option value="walk">Walk</option>
                <option value="age">Age</option>
              </select>
              <button
                type="button"
                onClick={() => setSortDir(sortDir === "asc" ? "desc" : "asc")}
                className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm hover:border-rose-400"
              >
                {sortDir === "asc" ? "↑" : "↓"}
              </button>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {hasActiveFilter && (
              <button
                type="button"
                onClick={clearAll}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-rose-600"
              >
                <X size={12} /> Clear
              </button>
            )}
            <button
              type="button"
              onClick={() => download(`listings-${stamp}.csv`, toCsv(filtered), "text/csv;charset=utf-8")}
              disabled={filtered.length === 0}
              className="flex items-center gap-1.5 bg-rose-700 hover:bg-rose-800 disabled:bg-rose-300 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
            >
              <Download size={12} /> CSV
            </button>
            <button
              type="button"
              onClick={() => download(`listings-${stamp}.json`, JSON.stringify(filtered, null, 2), "application/json")}
              disabled={filtered.length === 0}
              className="flex items-center gap-1.5 bg-white border border-gray-300 hover:border-rose-400 text-gray-700 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
            >
              <FileJson size={12} /> JSON
            </button>
          </div>
        </div>

        {floorPlanOptions.length > 0 && (
          <ChipRow
            label="Layout"
            options={floorPlanOptions}
            selected={fpFilters}
            onToggle={(v) => toggle(fpFilters, v, setFpFilters)}
          />
        )}
        {lineOptions.length > 0 && (
          <ChipRow
            label="Line"
            options={lineOptions}
            selected={lineFilters}
            onToggle={(v) => toggle(lineFilters, v, setLineFilters)}
          />
        )}
        {sourceOptions.length > 1 && (
          <ChipRow
            label="Source"
            options={sourceOptions}
            selected={srcFilters}
            onToggle={(v) => toggle(srcFilters, v, setSrcFilters)}
            transform={(s) => s.toUpperCase()}
          />
        )}

        <div className="text-xs text-gray-500">
          Showing <span className="font-semibold text-gray-900">{filtered.length}</span> of {listings.length}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide sticky top-0">
            <tr>
              <th className="px-4 py-3 font-medium">Building</th>
              <th className="px-4 py-3 font-medium">Rent</th>
              <th className="px-4 py-3 font-medium">Mgmt</th>
              <th className="px-4 py-3 font-medium">Layout</th>
              <th className="px-4 py-3 font-medium">Size</th>
              <th className="px-4 py-3 font-medium">Station</th>
              <th className="px-4 py-3 font-medium">Walk</th>
              <th className="px-4 py-3 font-medium">Age</th>
              <th className="px-4 py-3 font-medium">Floor</th>
              <th className="px-4 py-3 font-medium">Source</th>
              <th className="px-4 py-3 font-medium">Link</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.map((l, i) => (
              <tr key={l.id} className={`hover:bg-rose-50/40 transition-colors ${i % 2 === 1 ? "bg-gray-50/60" : ""}`}>
                <td className="px-4 py-3 max-w-[200px]">
                  <div className="font-semibold text-gray-900 truncate" title={l.building_name ?? l.title}>
                    {l.building_name ?? l.title ?? "—"}
                  </div>
                  {l.address && (
                    <div className="text-xs text-gray-400 truncate" title={l.address}>
                      {l.address}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 font-semibold text-rose-700 whitespace-nowrap">
                  {formatYen(l.rent)}
                </td>
                <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                  {l.management_fee ? formatYen(l.management_fee) : "—"}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700">
                  {l.floor_plan ?? "—"}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700">
                  {l.size_m2 != null ? `${l.size_m2}m²` : "—"}
                </td>
                <td className="px-4 py-3 max-w-[180px]">
                  <div className="truncate text-gray-700" title={l.nearest_station ?? undefined}>
                    {l.nearest_station ?? "—"}
                  </div>
                  {l.nearest_line && (
                    <div className="text-xs text-gray-400 truncate" title={l.nearest_line}>
                      {l.nearest_line}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700">
                  {l.walk_minutes != null ? `${l.walk_minutes} min` : "—"}
                </td>
                <td className="px-4 py-3 text-gray-700 whitespace-nowrap">
                  {l.building_age_years != null
                    ? l.building_age_years === 0 ? "New" : `${l.building_age_years} yr`
                    : "—"}
                </td>
                <td className="px-4 py-3 text-gray-700 whitespace-nowrap">
                  {l.floor != null ? `${l.floor}F` : "—"}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SOURCE_COLORS[l.source] ?? "bg-gray-100 text-gray-600"}`}>
                    {l.source.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  {l.source_url ? (
                    <a
                      href={l.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-rose-600 hover:text-rose-800 text-xs font-medium"
                    >
                      View →
                    </a>
                  ) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="text-center py-10 text-sm text-gray-400">
            No listings match the current filters.
          </div>
        )}
      </div>
    </div>
  );
}

function Range({
  label, min, max, onMin, onMax, step,
}: {
  label: string;
  min: string;
  max: string;
  onMin: (v: string) => void;
  onMax: (v: string) => void;
  step: number;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">{label}</label>
      <div className="flex items-center gap-1">
        <input
          type="number"
          min={0}
          step={step}
          placeholder="min"
          value={min}
          onChange={(e) => onMin(e.target.value)}
          className="w-20 border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
        />
        <span className="text-gray-400 text-xs">–</span>
        <input
          type="number"
          min={0}
          step={step}
          placeholder="max"
          value={max}
          onChange={(e) => onMax(e.target.value)}
          className="w-20 border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
        />
      </div>
    </div>
  );
}

function ChipRow({
  label, options, selected, onToggle, transform,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (v: string) => void;
  transform?: (s: string) => string;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{label}</span>
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onToggle(opt)}
          className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
            selected.includes(opt)
              ? "bg-rose-600 text-white border-rose-600"
              : "bg-white text-gray-600 border-gray-300 hover:border-rose-400"
          }`}
        >
          {transform ? transform(opt) : opt}
        </button>
      ))}
    </div>
  );
}
