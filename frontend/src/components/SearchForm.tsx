"use client";

import { useState } from "react";
import { SearchCriteria } from "@/lib/api";

const WARDS = [
  { slug: "shinjuku", label: "新宿区 Shinjuku" },
  { slug: "shibuya", label: "渋谷区 Shibuya" },
  { slug: "minato", label: "港区 Minato" },
  { slug: "chiyoda", label: "千代田区 Chiyoda" },
  { slug: "chuo", label: "中央区 Chuo" },
  { slug: "bunkyo", label: "文京区 Bunkyo" },
  { slug: "toshima", label: "豊島区 Toshima" },
  { slug: "meguro", label: "目黒区 Meguro" },
  { slug: "setagaya", label: "世田谷区 Setagaya" },
  { slug: "suginami", label: "杉並区 Suginami" },
  { slug: "nakano", label: "中野区 Nakano" },
  { slug: "shinagawa", label: "品川区 Shinagawa" },
  { slug: "ota", label: "大田区 Ota" },
  { slug: "koto", label: "江東区 Koto" },
  { slug: "sumida", label: "墨田区 Sumida" },
  { slug: "taito", label: "台東区 Taito" },
  { slug: "arakawa", label: "荒川区 Arakawa" },
  { slug: "kita", label: "北区 Kita" },
  { slug: "itabashi", label: "板橋区 Itabashi" },
  { slug: "nerima", label: "練馬区 Nerima" },
  { slug: "adachi", label: "足立区 Adachi" },
  { slug: "katsushika", label: "葛飾区 Katsushika" },
  { slug: "edogawa", label: "江戸川区 Edogawa" },
];

const FLOOR_PLANS = ["1R", "1K", "1DK", "1LDK", "2K", "2DK", "2LDK", "3K", "3DK", "3LDK", "4LDK+"];

const SOURCES = [
  { value: "suumo", label: "Suumo" },
  { value: "homes", label: "Homes" },
  { value: "chintai", label: "Chintai" },
];

interface Props {
  onSubmit: (criteria: SearchCriteria) => void;
  loading: boolean;
}

export default function SearchForm({ onSubmit, loading }: Props) {
  const [wards, setWards] = useState<string[]>([]);
  const [rentMin, setRentMin] = useState(5);
  const [rentMax, setRentMax] = useState(15);
  const [sizeMin, setSizeMin] = useState(0);
  const [floorPlans, setFloorPlans] = useState<string[]>([]);
  const [walkMinutes, setWalkMinutes] = useState(9999);
  const [buildingAge, setBuildingAge] = useState(9999);
  const [sources, setSources] = useState(["suumo", "homes", "chintai"]);
  const [maxPages, setMaxPages] = useState(2);

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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    // Map display floor plan strings → API enum values
    const fpMap: Record<string, string> = {
      "1R": "1R", "1K": "1K", "1DK": "1DK", "1LDK": "1LDK",
      "2K": "2K", "2DK": "2DK", "2LDK": "2LDK",
      "3K": "3K", "3DK": "3DK", "3LDK": "3LDK", "4LDK+": "4LDK+",
    };

    onSubmit({
      wards,
      station: null,
      rent_min: rentMin,
      rent_max: rentMax,
      size_min_m2: sizeMin,
      size_max_m2: 9999,
      floor_plans: floorPlans.map((f) => fpMap[f]),
      walk_minutes: walkMinutes,
      building_age_max: buildingAge,
      sources,
      max_pages: maxPages,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-6">
      {/* Ward selection */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          Tokyo Wards <span className="font-normal text-gray-400">(empty = all 23 wards)</span>
        </label>
        <div className="flex flex-wrap gap-2">
          {WARDS.map((ward) => (
            <button
              key={ward.slug}
              type="button"
              onClick={() => toggleWard(ward.slug)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                wards.includes(ward.slug)
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
              }`}
            >
              {ward.label}
            </button>
          ))}
        </div>
      </div>

      {/* Rent range */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">
            Min Rent (万円/mo)
          </label>
          <input
            type="number"
            min={0}
            max={100}
            step={0.5}
            value={rentMin}
            onChange={(e) => setRentMin(Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-400">¥{(rentMin * 10000).toLocaleString()}</span>
        </div>
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">
            Max Rent (万円/mo)
          </label>
          <input
            type="number"
            min={0}
            max={200}
            step={0.5}
            value={rentMax}
            onChange={(e) => setRentMax(Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-400">¥{(rentMax * 10000).toLocaleString()}</span>
        </div>
      </div>

      {/* Floor plans */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          Room Type <span className="font-normal text-gray-400">(empty = any)</span>
        </label>
        <div className="flex flex-wrap gap-2">
          {FLOOR_PLANS.map((fp) => (
            <button
              key={fp}
              type="button"
              onClick={() => toggleFloorPlan(fp)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                floorPlans.includes(fp)
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
              }`}
            >
              {fp}
            </button>
          ))}
        </div>
      </div>

      {/* Size / Walk / Age in a row */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">Min Size (m²)</label>
          <input
            type="number"
            min={0}
            step={5}
            value={sizeMin}
            onChange={(e) => setSizeMin(Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">Walk to Station</label>
          <select
            value={walkMinutes}
            onChange={(e) => setWalkMinutes(Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={9999}>Any</option>
            <option value={5}>Within 5 min</option>
            <option value={10}>Within 10 min</option>
            <option value={15}>Within 15 min</option>
            <option value={20}>Within 20 min</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">Building Age</label>
          <select
            value={buildingAge}
            onChange={(e) => setBuildingAge(Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={9999}>Any</option>
            <option value={1}>New (within 1yr)</option>
            <option value={5}>Within 5 yrs</option>
            <option value={10}>Within 10 yrs</option>
            <option value={20}>Within 20 yrs</option>
            <option value={30}>Within 30 yrs</option>
          </select>
        </div>
      </div>

      {/* Sources + pages */}
      <div className="flex flex-wrap items-end gap-6">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">Sources</label>
          <div className="flex gap-3">
            {SOURCES.map((src) => (
              <label key={src.value} className="flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={sources.includes(src.value)}
                  onChange={() => toggleSource(src.value)}
                  className="rounded accent-blue-600"
                />
                {src.label}
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">Pages per site</label>
          <select
            value={maxPages}
            onChange={(e) => setMaxPages(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {[1, 2, 3, 5].map((n) => (
              <option key={n} value={n}>{n} page{n > 1 ? "s" : ""}</option>
            ))}
          </select>
        </div>
      </div>

      <button
        type="submit"
        disabled={loading || sources.length === 0}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
      >
        {loading ? "Searching..." : "Search Tokyo Apartments"}
      </button>
    </form>
  );
}
