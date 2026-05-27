"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, FileJson, Star, X } from "lucide-react";
import { Listing, formatYen } from "@/lib/api";

const FAVORITES_KEY = "tokyo-rooms.favorites";

interface Props {
  listings: Listing[];
}

const SOURCE_COLORS: Record<string, string> = {
  suumo: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  homes: "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
  chintai: "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
};

type SortKey = "rent" | "size" | "walk" | "age" | "moto" | "commute";
type SortDir = "asc" | "desc";

// Rank parking 3-state so the default ascending sort floats confirmed parking
// to the top (lower = better), matching rent/walk/age "best first" behavior.
function parkingRank(state: string | null | undefined): number {
  if (state === "available") return 0;
  if (state === "none") return 2;
  return 1; // "unknown" or missing
}

function normalizeStation(s: string | null | undefined): string {
  if (!s) return "";
  return s.replace(/\s+/g, " ").replace(/駅.*$/, "駅").trim();
}

function toCsv(rows: Listing[]): string {
  const headers = [
    "source", "building_name", "title", "rent", "management_fee",
    "floor_plan", "size_m2", "nearest_line", "nearest_station", "walk_minutes",
    "building_age_years", "floor", "commute_tokyo_min", "commute_shinjuku_min",
    "motorcycle_parking", "bicycle_parking",
    "car_parking", "foreigner_ok", "earthquake_standard", "address", "source_url",
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
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [favOnly, setFavOnly] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(FAVORITES_KEY);
      if (raw) setFavorites(new Set(JSON.parse(raw)));
    } catch {
      // ignore corrupt storage
    }
  }, []);

  function toggleFavorite(id: string) {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        localStorage.setItem(FAVORITES_KEY, JSON.stringify(Array.from(next)));
      } catch {
        // ignore quota errors
      }
      return next;
    });
  }

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
      if (favOnly && !favorites.has(l.id)) return false;
      return true;
    });

    const pick = (l: Listing): number | null => {
      switch (sortKey) {
        case "rent": return l.rent;
        case "size": return l.size_m2;
        case "walk": return l.walk_minutes;
        case "age": return l.building_age_years;
        case "moto": return parkingRank(l.motorcycle_parking);
        case "commute": return l.commute_score ?? null;
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
  }, [listings, rentMin, rentMax, sizeMin, sizeMax, walkMax, fpFilters, srcFilters, stationFilter, lineFilters, favorites, favOnly, sortKey, sortDir]);

  function toggle<T>(list: T[], v: T, setter: (xs: T[]) => void) {
    setter(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  }

  function clearAll() {
    setRentMin(""); setRentMax(""); setSizeMin(""); setSizeMax("");
    setWalkMax(""); setFpFilters([]); setSrcFilters([]); setStationFilter("");
    setLineFilters([]); setFavOnly(false);
  }

  const hasActiveFilter =
    rentMin || rentMax || sizeMin || sizeMax || walkMax ||
    fpFilters.length > 0 || srcFilters.length > 0 || stationFilter ||
    lineFilters.length > 0 || favOnly;

  const stamp = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <Range label="Rent 万円" min={rentMin} max={rentMax} onMin={setRentMin} onMax={setRentMax} step={0.5} />
          <Range label="Size m²" min={sizeMin} max={sizeMax} onMin={setSizeMin} onMax={setSizeMax} step={1} />
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Walk ≤</label>
            <input
              type="number"
              min={0}
              placeholder="min"
              value={walkMax}
              onChange={(e) => setWalkMax(e.target.value)}
              className="w-20 border border-gray-300 dark:border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Station</label>
            <input
              list="station-list"
              type="text"
              placeholder="Any"
              value={stationFilter}
              onChange={(e) => setStationFilter(e.target.value)}
              className="w-40 border border-gray-300 dark:border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
            <datalist id="station-list">
              {stationOptions.map((s) => <option key={s} value={s} />)}
            </datalist>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Sort</label>
            <div className="flex gap-1">
              <select
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as SortKey)}
                className="border border-gray-300 dark:border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
              >
                <option value="rent">Rent</option>
                <option value="size">Size</option>
                <option value="walk">Walk</option>
                <option value="age">Age</option>
                <option value="moto">🏍 Parking</option>
                <option value="commute">🚆 Commute</option>
              </select>
              <button
                type="button"
                onClick={() => setSortDir(sortDir === "asc" ? "desc" : "asc")}
                className="border border-gray-300 dark:border-gray-700 rounded-lg px-2 py-1.5 text-sm hover:border-rose-400"
              >
                {sortDir === "asc" ? "↑" : "↓"}
              </button>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => setFavOnly((v) => !v)}
              className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors ${
                favOnly
                  ? "bg-amber-400 text-amber-900 border-amber-400"
                  : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-700 hover:border-amber-400"
              }`}
              title={favOnly ? "Showing only favorites" : "Show only favorites"}
            >
              <Star size={12} className={favOnly ? "fill-current" : ""} />
              {favorites.size > 0 ? favorites.size : ""}
            </button>
            {hasActiveFilter && (
              <button
                type="button"
                onClick={clearAll}
                className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-rose-600"
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
              className="flex items-center gap-1.5 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 hover:border-rose-400 text-gray-700 dark:text-gray-300 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
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

        <div className="text-xs text-gray-500 dark:text-gray-400">
          Showing <span className="font-semibold text-gray-900 dark:text-gray-100">{filtered.length}</span> of {listings.length}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-50 dark:bg-gray-800/60 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide sticky top-0">
            <tr>
              <th className="px-3 py-3 font-medium w-8"></th>
              <th className="px-4 py-3 font-medium">Building</th>
              <th className="px-4 py-3 font-medium">Rent</th>
              <th className="px-4 py-3 font-medium">Mgmt</th>
              <th className="px-4 py-3 font-medium">Layout</th>
              <th className="px-4 py-3 font-medium">Size</th>
              <th className="px-4 py-3 font-medium">Station</th>
              <th className="px-4 py-3 font-medium">Walk</th>
              <th className="px-4 py-3 font-medium" title="Estimated door-to-door: walk + train to Tokyo Station">→Tokyo</th>
              <th className="px-4 py-3 font-medium" title="Estimated door-to-door: walk + train to Shinjuku">→Shinjuku</th>
              <th className="px-4 py-3 font-medium">Age</th>
              <th className="px-4 py-3 font-medium">Floor</th>
              <th className="px-4 py-3 font-medium">Parking</th>
              <th className="px-4 py-3 font-medium">Source</th>
              <th className="px-4 py-3 font-medium">Link</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {filtered.map((l, i) => (
              <tr key={l.id} className={`hover:bg-rose-50/40 dark:hover:bg-rose-950/20 transition-colors ${i % 2 === 1 ? "bg-gray-50/60 dark:bg-gray-800/30" : ""}`}>
                <td className="px-3 py-3 text-center">
                  <button
                    type="button"
                    aria-label={favorites.has(l.id) ? "Unfavorite" : "Favorite"}
                    onClick={() => toggleFavorite(l.id)}
                    className="text-gray-300 dark:text-gray-600 hover:text-amber-400 transition-colors"
                  >
                    <Star
                      size={15}
                      className={favorites.has(l.id) ? "fill-amber-400 text-amber-400" : ""}
                    />
                  </button>
                </td>
                <td className="px-4 py-3 max-w-[200px]">
                  <div className="font-semibold text-gray-900 dark:text-gray-100 truncate" title={l.building_name ?? l.title}>
                    {l.building_name ?? l.title ?? "—"}
                  </div>
                  {l.address && (
                    <div className="text-xs text-gray-400 dark:text-gray-500 truncate" title={l.address}>
                      {l.address}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {l.earthquake_standard === "new" && (
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" title="Post-1981 earthquake standard (新耐震基準)">
                        新耐震
                      </span>
                    )}
                    {l.earthquake_standard === "old" && (
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300" title="Pre-1981 earthquake standard (旧耐震基準)">
                        旧耐震
                      </span>
                    )}
                    {l.foreigner_ok && (
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300" title="Foreigners accepted (外国人相談可)">
                        外国人可
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 font-semibold text-rose-700 dark:text-rose-400 whitespace-nowrap">
                  {formatYen(l.rent)}
                </td>
                <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                  {l.management_fee ? formatYen(l.management_fee) : "—"}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700 dark:text-gray-300">
                  {l.floor_plan ?? "—"}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700 dark:text-gray-300">
                  {l.size_m2 != null ? `${l.size_m2}m²` : "—"}
                </td>
                <td className="px-4 py-3 max-w-[180px]">
                  <div className="truncate text-gray-700 dark:text-gray-300" title={l.nearest_station ?? undefined}>
                    {l.nearest_station ?? "—"}
                  </div>
                  {l.nearest_line && (
                    <div className="text-xs text-gray-400 dark:text-gray-500 truncate" title={l.nearest_line}>
                      {l.nearest_line}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700 dark:text-gray-300">
                  {l.walk_minutes != null ? `${l.walk_minutes} min` : "—"}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700 dark:text-gray-300">
                  {l.commute_tokyo_min != null ? `${l.commute_tokyo_min} min` : "—"}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700 dark:text-gray-300">
                  {l.commute_shinjuku_min != null ? `${l.commute_shinjuku_min} min` : "—"}
                </td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                  {l.building_age_years != null
                    ? l.building_age_years === 0 ? "New" : `${l.building_age_years} yr`
                    : "—"}
                </td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                  {l.floor != null ? `${l.floor}F` : "—"}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <ParkingBadges listing={l} />
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SOURCE_COLORS[l.source] ?? "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300"}`}>
                    {l.source.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  {l.source_url ? (
                    <a
                      href={l.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-rose-600 dark:text-rose-400 hover:text-rose-800 dark:hover:text-rose-300 text-xs font-medium"
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
          <div className="text-center py-10 text-sm text-gray-400 dark:text-gray-500">
            No listings match the current filters.
          </div>
        )}
      </div>
    </div>
  );
}

function ParkingBadges({ listing }: { listing: Listing }) {
  // Each parking type renders only when explicitly available. A missing badge
  // means "not stated on the listing" — not a confirmed absence.
  const items: { icon: string; label: string; state?: string | null }[] = [
    { icon: "🏍", label: "Motorcycle parking", state: listing.motorcycle_parking },
    { icon: "🚲", label: "Bicycle parking", state: listing.bicycle_parking },
    { icon: "🚗", label: "Car parking", state: listing.car_parking },
  ];
  const available = items.filter((i) => i.state === "available");
  if (available.length === 0) {
    return <span className="text-xs text-gray-300 dark:text-gray-600" title="Parking not stated">—</span>;
  }
  return (
    <span className="flex items-center gap-1">
      {available.map((i) => (
        <span key={i.label} title={i.label} className="text-base leading-none">
          {i.icon}
        </span>
      ))}
    </span>
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
      <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">{label}</label>
      <div className="flex items-center gap-1">
        <input
          type="number"
          min={0}
          step={step}
          placeholder="min"
          value={min}
          onChange={(e) => onMin(e.target.value)}
          className="w-20 border border-gray-300 dark:border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
        />
        <span className="text-gray-400 text-xs">–</span>
        <input
          type="number"
          min={0}
          step={step}
          placeholder="max"
          value={max}
          onChange={(e) => onMax(e.target.value)}
          className="w-20 border border-gray-300 dark:border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
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
      <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</span>
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onToggle(opt)}
          className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
            selected.includes(opt)
              ? "bg-rose-600 text-white border-rose-600"
              : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-700 hover:border-rose-400"
          }`}
        >
          {transform ? transform(opt) : opt}
        </button>
      ))}
    </div>
  );
}
