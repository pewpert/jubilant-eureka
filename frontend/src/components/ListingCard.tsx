import { Listing, formatYen } from "@/lib/api";
import { MapPin, Train, Building2, Ruler, Calendar, ExternalLink } from "lucide-react";

const SOURCE_COLORS: Record<string, string> = {
  suumo: "bg-green-100 text-green-700",
  homes: "bg-orange-100 text-orange-700",
  chintai: "bg-purple-100 text-purple-700",
};

interface Props {
  listing: Listing;
}

export default function ListingCard({ listing }: Props) {
  const totalMonthly =
    listing.rent != null && listing.management_fee != null
      ? listing.rent + listing.management_fee
      : listing.rent;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
      {/* Image */}
      <div className="relative h-44 bg-gray-100">
        {listing.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={listing.image_url}
            alt={listing.building_name ?? listing.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-300">
            <Building2 size={48} />
          </div>
        )}
        {/* Source badge */}
        <span
          className={`absolute top-2 left-2 text-xs font-semibold px-2 py-0.5 rounded-full ${
            SOURCE_COLORS[listing.source] ?? "bg-gray-100 text-gray-600"
          }`}
        >
          {listing.source.toUpperCase()}
        </span>
        {/* Floor plan badge */}
        {listing.floor_plan && (
          <span className="absolute top-2 right-2 bg-white/90 text-gray-700 text-xs font-bold px-2 py-0.5 rounded-full">
            {listing.floor_plan}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Price */}
        <div>
          <div className="text-xl font-bold text-gray-900">
            {formatYen(totalMonthly)}
            <span className="text-sm font-normal text-gray-500">/月</span>
          </div>
          {listing.management_fee != null && listing.management_fee > 0 && (
            <div className="text-xs text-gray-400">
              Rent {formatYen(listing.rent)} + Mgmt {formatYen(listing.management_fee)}
            </div>
          )}
          {(listing.deposit != null || listing.key_money != null) && (
            <div className="text-xs text-gray-400">
              {listing.deposit != null && `Dep ${formatYen(listing.deposit)}`}
              {listing.deposit != null && listing.key_money != null && " · "}
              {listing.key_money != null && `Key ¥ ${formatYen(listing.key_money)}`}
            </div>
          )}
        </div>

        {/* Building name */}
        {listing.building_name && (
          <div className="font-medium text-gray-800 text-sm truncate" title={listing.building_name}>
            {listing.building_name}
          </div>
        )}

        {/* Details grid */}
        <div className="grid grid-cols-2 gap-y-1.5 text-xs text-gray-600">
          {listing.nearest_station && (
            <div className="flex items-center gap-1 col-span-2">
              <Train size={12} className="text-gray-400 shrink-0" />
              <span className="truncate">
                {listing.nearest_station}
                {listing.walk_minutes != null && ` 徒歩${listing.walk_minutes}分`}
              </span>
            </div>
          )}
          {listing.address && (
            <div className="flex items-center gap-1 col-span-2">
              <MapPin size={12} className="text-gray-400 shrink-0" />
              <span className="truncate">{listing.address}</span>
            </div>
          )}
          {listing.size_m2 != null && (
            <div className="flex items-center gap-1">
              <Ruler size={12} className="text-gray-400 shrink-0" />
              <span>{listing.size_m2}m²</span>
            </div>
          )}
          {listing.floor != null && (
            <div className="flex items-center gap-1">
              <Building2 size={12} className="text-gray-400 shrink-0" />
              <span>
                {listing.floor}F
                {listing.total_floors != null && `/${listing.total_floors}F`}
              </span>
            </div>
          )}
          {listing.building_age_years != null && (
            <div className="flex items-center gap-1">
              <Calendar size={12} className="text-gray-400 shrink-0" />
              <span>
                {listing.building_age_years === 0 ? "New build" : `築${listing.building_age_years}年`}
              </span>
            </div>
          )}
        </div>

        {/* View link */}
        {listing.source_url && (
          <a
            href={listing.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            View on {listing.source}
            <ExternalLink size={11} />
          </a>
        )}
      </div>
    </div>
  );
}
