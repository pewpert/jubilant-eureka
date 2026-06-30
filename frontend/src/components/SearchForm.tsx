"use client";

import { useState } from "react";
import { MapPin, Wallet, Home, Maximize2, Train, Building2, Search } from "lucide-react";
import { SearchCriteria } from "@/lib/api";

const WARDS = [
  { slug: "shinjuku", label: "新宿 Shinjuku" },
  { slug: "shibuya", label: "渋谷 Shibuya" },
  { slug: "minato", label: "港 Minato" },
  { slug: "chiyoda", label: "千代田 Chiyoda" },
  { slug: "chuo", label: "中央 Chuo" },
  { slug: "bunkyo", label: "文京 Bunkyo" },
  { slug: "toshima", label: "豊島 Toshima" },
  { slug: "meguro", label: "目黒 Meguro" },
  { slug: "setagaya", label: "世田谷 Setagaya" },
  { slug: "suginami", label: "杉並 Suginami" },
  { slug: "nakano", label: "中野 Nakano" },
  { slug: "shinagawa", label: "品川 Shinagawa" },
  { slug: "ota", label: "大田 Ota" },
  { slug: "koto", label: "江東 Koto" },
  { slug: "sumida", label: "墨田 Sumida" },
  { slug: "taito", label: "台東 Taito" },
  { slug: "arakawa", label: "荒川 Arakawa" },
  { slug: "kita", label: "北 Kita" },
  { slug: "itabashi", label: "板橋 Itabashi" },
  { slug: "nerima", label: "練馬 Nerima" },
  { slug: "adachi", label: "足立 Adachi" },
  { slug: "katsushika", label: "葛飾 Katsushika" },
  { slug: "edogawa", label: "江戸川 Edogawa" },
];

const FLOOR_PLANS = ["1R", "1K", "1DK", "1LDK", "2K", "2DK", "2LDK", "3K", "3DK", "3LDK", "4LDK+"];

const SOURCES = [
  { value: "suumo", label: "Suumo", hint: "paid fallback" },
  { value: "homes", label: "Homes" },
  { value: "chintai", label: "Chintai" },
  { value: "ehousing", label: "e-Housing", hint: "English / expat" },
];

interface Props {
  onSubmit: (criteria: SearchCriteria) => void;
  loading: boolean;
}

export default function SearchForm({ onSubmit, loading }: Props) {
  const [wards, setWards] = useState<string[]>([]);
  const [wardPickerOpen, setWardPickerOpen] = useState(false);

  const [rentMinStr, setRentMinStr] = useState("5");
  const [rentMaxStr, setRentMaxStr] = useState("15");
  const [rentError, setRentError] = useState<string | null>(null);

  const [sizeMinStr, setSizeMinStr] = useState("");
  const [sizeMaxStr, setSizeMaxStr] = useState("");

  const [floorPlans, setFloorPlans] = useState<string[]>([]);
  const [walkMinutes, setWalkMinutes] = useState(9999);
  const [buildingAge, setBuildingAge] = useState(9999);
  const [commuteTokyo, setCommuteTokyo] = useState(9999);
  const [commuteShinjuku, setCommuteShinjuku] = useState(9999);
  const [sources, setSources] = useState(["suumo", "homes", "chintai", "ehousing"]);
  const [maxPages, setMaxPages] = useState(2);
  const [motoOnly, setMotoOnly] = useState(false);

  function toggleWard(slug: string) {
    setWards((prev) =>
      prev.includes(slug) ? prev.filter((w) => w !== slug) : [...prev, slug]
    );
  }

  function toggleFloorPlan(fp: string) {
    setFloorPlans((prev) =>
      prev.includes(fp) ? prev.filter((f) => f !== fp) : [...prev, fp]
    );
  }

  function toggleSource(src: string) {
    setSources((prev) =>
      prev.includes(src) ? prev.filter((s) => s !== src) : [...prev, src]
    );
  }

  function sanitizeNum(str: string, fallback: string): string {
    const n = parseFloat(str);
    if (isNaN(n) || n < 0) return fallback;
    return str;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const rentMin = parseFloat(rentMinStr) || 0;
    const rentMax = parseFloat(rentMaxStr) || 0;
    if (rentMax > 0 && rentMin > rentMax) {
      setRentError("Min rent cannot exceed max rent");
      return;
    }
    setRentError(null);

    onSubmit({
      wards,
      station: null,
      rent_min: rentMin,
      rent_max: rentMax || 9999,
      size_min_m2: parseFloat(sizeMinStr) || 0,
      size_max_m2: parseFloat(sizeMaxStr) || 9999,
      floor_plans: floorPlans,
      walk_minutes: walkMinutes,
      building_age_max: buildingAge,
      commute_tokyo_max: commuteTokyo,
      commute_shinjuku_max: commuteShinjuku,
      sources,
      max_pages: maxPages,
      enrich_details: true,
      moto_parking_only: motoOnly,
    });
  }

  const rentMinVal = parseFloat(rentMinStr) || 0;
  const rentMaxVal = parseFloat(rentMaxStr) || 0;
  const wardSummary = wards.length === 0
    ? "All 23 wards"
    : wards.length <= 3
      ? wards.map((w) => WARDS.find((x) => x.slug === w)?.label.split(" ")[1] ?? w).join(", ")
      : `${wards.length} wards selected`;

  return (
    <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-900 rounded-2xl shadow-md border border-gray-100 dark:border-gray-800 overflow-hidden">
      <div className="p-6 space-y-5">

        {/* Area */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            <MapPin size={13} className="text-rose-500" /> Area
          </label>
          <div className="relative">
            <button
              type="button"
              onClick={() => setWardPickerOpen((v) => !v)}
              className="w-full flex items-center justify-between border border-gray-300 rounded-lg px-3 py-2 text-sm hover:border-rose-400 focus:outline-none focus:ring-2 focus:ring-rose-500 transition-colors"
            >
              <span className={wards.length === 0 ? "text-gray-400" : "text-gray-900 dark:text-gray-100"}>{wardSummary}</span>
              <span className="text-gray-400 text-xs">{wardPickerOpen ? "▲" : "▼"}</span>
            </button>
            {wardPickerOpen && (
              <div className="absolute z-20 top-full mt-1 left-0 right-0 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl shadow-lg p-3">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs text-gray-500">{wards.length} selected</span>
                  <button
                    type="button"
                    onClick={() => setWards([])}
                    className="text-xs text-rose-500 hover:text-rose-700"
                  >Clear all</button>
                </div>
                <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto">
                  {WARDS.map((ward) => (
                    <button
                      key={ward.slug}
                      type="button"
                      onClick={() => toggleWard(ward.slug)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                        wards.includes(ward.slug)
                          ? "bg-rose-600 text-white border-rose-600"
                          : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-700 hover:border-rose-400"
                      }`}
                    >
                      {ward.label}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setWardPickerOpen(false)}
                  className="mt-2 w-full text-xs text-gray-500 hover:text-gray-700 py-1"
                >Done</button>
              </div>
            )}
          </div>
        </div>

        {/* Budget */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            <Wallet size={13} className="text-rose-500" /> Monthly Budget
          </label>
          <div className="flex items-center gap-2">
            <div className="flex-1">
              <input
                type="number"
                min={0}
                max={100}
                step={0.5}
                placeholder="Min"
                value={rentMinStr}
                onChange={(e) => { setRentMinStr(e.target.value); setRentError(null); }}
                onBlur={(e) => setRentMinStr(sanitizeNum(e.target.value, "0"))}
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500 transition-colors ${rentError ? "border-red-400" : "border-gray-300"}`}
              />
              <span className="text-xs text-gray-400 mt-0.5 block">
                {rentMinVal > 0 ? `¥${(rentMinVal * 10000).toLocaleString()}` : "No min"}
              </span>
            </div>
            <span className="text-gray-400 text-sm pb-5">→</span>
            <div className="flex-1">
              <input
                type="number"
                min={0}
                max={200}
                step={0.5}
                placeholder="Max"
                value={rentMaxStr}
                onChange={(e) => { setRentMaxStr(e.target.value); setRentError(null); }}
                onBlur={(e) => setRentMaxStr(sanitizeNum(e.target.value, ""))}
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500 transition-colors ${rentError ? "border-red-400" : "border-gray-300"}`}
              />
              <span className="text-xs text-gray-400 mt-0.5 block">
                {rentMaxVal > 0 ? `¥${(rentMaxVal * 10000).toLocaleString()}` : "No max"}
              </span>
            </div>
            <span className="text-xs text-gray-400 pb-5">万円/mo</span>
          </div>
          {rentError && <p className="text-xs text-red-500 mt-1">{rentError}</p>}
        </div>

        {/* Room type */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            <Home size={13} className="text-rose-500" /> Room Type <span className="font-normal normal-case text-gray-400 ml-1">(empty = any)</span>
          </label>
          <div className="flex flex-wrap gap-1.5">
            {FLOOR_PLANS.map((fp) => (
              <button
                key={fp}
                type="button"
                onClick={() => toggleFloorPlan(fp)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                  floorPlans.includes(fp)
                    ? "bg-rose-600 text-white border-rose-600"
                    : "bg-white text-gray-600 border-gray-300 hover:border-rose-400"
                }`}
              >
                {fp}
              </button>
            ))}
          </div>
        </div>

        {/* Size / Walk / Age */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <label className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              <Maximize2 size={12} className="text-rose-500" /> Min m²
            </label>
            <input
              type="number"
              min={0}
              step={5}
              placeholder="Any"
              value={sizeMinStr}
              onChange={(e) => setSizeMinStr(e.target.value)}
              onBlur={(e) => setSizeMinStr(sanitizeNum(e.target.value, ""))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
          </div>
          <div>
            <label className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              <Maximize2 size={12} className="text-rose-500" /> Max m²
            </label>
            <input
              type="number"
              min={0}
              step={5}
              placeholder="Any"
              value={sizeMaxStr}
              onChange={(e) => setSizeMaxStr(e.target.value)}
              onBlur={(e) => setSizeMaxStr(sanitizeNum(e.target.value, ""))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
          </div>
          <div>
            <label className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              <Train size={12} className="text-rose-500" /> Walk
            </label>
            <select
              value={walkMinutes}
              onChange={(e) => setWalkMinutes(Number(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            >
              <option value={9999}>Any</option>
              <option value={5}>≤ 5 min</option>
              <option value={10}>≤ 10 min</option>
              <option value={15}>≤ 15 min</option>
              <option value={20}>≤ 20 min</option>
            </select>
          </div>
          <div>
            <label className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              <Building2 size={12} className="text-rose-500" /> Age
            </label>
            <select
              value={buildingAge}
              onChange={(e) => setBuildingAge(Number(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            >
              <option value={9999}>Any</option>
              <option value={1}>New (≤ 1yr)</option>
              <option value={5}>≤ 5 yrs</option>
              <option value={10}>≤ 10 yrs</option>
              <option value={20}>≤ 20 yrs</option>
              <option value={30}>≤ 30 yrs</option>
              <option value={40}>≤ 40 yrs</option>
            </select>
          </div>
          <div>
            <label className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              <Train size={12} className="text-rose-500" /> → Tokyo Stn
            </label>
            <select
              value={commuteTokyo}
              onChange={(e) => setCommuteTokyo(Number(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            >
              <option value={9999}>Any</option>
              <option value={30}>≤ 30 min</option>
              <option value={40}>≤ 40 min</option>
              <option value={50}>≤ 50 min</option>
              <option value={60}>≤ 60 min</option>
            </select>
          </div>
          <div>
            <label className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              <Train size={12} className="text-rose-500" /> → Shinjuku
            </label>
            <select
              value={commuteShinjuku}
              onChange={(e) => setCommuteShinjuku(Number(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            >
              <option value={9999}>Any</option>
              <option value={20}>≤ 20 min</option>
              <option value={30}>≤ 30 min</option>
              <option value={40}>≤ 40 min</option>
              <option value={50}>≤ 50 min</option>
            </select>
          </div>
        </div>

        {/* Sources + pages */}
        <div className="flex flex-wrap items-end gap-6 pt-1 border-t border-gray-100 dark:border-gray-800">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Sources</label>
            <div className="flex gap-3">
              {SOURCES.map((src) => (
                <label key={src.value} className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={sources.includes(src.value)}
                    onChange={() => toggleSource(src.value)}
                    className="rounded accent-rose-600"
                  />
                  <span>
                    {src.label}
                    {src.hint && <span className="text-xs text-gray-400 ml-1">({src.hint})</span>}
                  </span>
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Pages / site</label>
            <select
              value={maxPages}
              onChange={(e) => setMaxPages(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
            >
              {[1, 2, 3, 5].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Parking</label>
            <button
              type="button"
              onClick={() => setMotoOnly((v) => !v)}
              aria-pressed={motoOnly}
              title="Only show listings whose detail page confirms motorcycle parking. Leaves out listings that simply don't state it."
              className={`flex items-center gap-1.5 text-sm font-semibold px-3 py-2 rounded-lg border transition-colors ${
                motoOnly
                  ? "bg-rose-700 text-white border-rose-700"
                  : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-700 hover:border-rose-400"
              }`}
            >
              🏍 Motorcycle parking only
            </button>
          </div>
        </div>
      </div>

      <div className="px-6 pb-6">
        <button
          type="submit"
          disabled={loading || sources.length === 0}
          className="w-full bg-rose-700 hover:bg-rose-800 disabled:bg-rose-300 text-white font-semibold py-3.5 rounded-xl transition-colors text-sm flex items-center justify-center gap-2"
        >
          <Search size={16} />
          {loading ? "Searching…" : "Search Tokyo Apartments"}
        </button>
      </div>
    </form>
  );
}
