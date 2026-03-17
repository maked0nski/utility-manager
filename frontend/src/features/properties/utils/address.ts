import type { ApartmentProfileForm } from "@/shared/api/types";

function clean(value: string | null | undefined) {
  return String(value || "").trim();
}

export function buildShortPropertyAddress(apartment: ApartmentProfileForm) {
  const street = clean(apartment.street);
  const houseNumber = clean(apartment.house_number);
  const apartmentNumber = clean(apartment.apartment_number);
  const base = [street, houseNumber].filter(Boolean).join(" ").trim();
  if (apartmentNumber) {
    return `${base} кв ${apartmentNumber}`.trim();
  }
  return base;
}

export function buildFullPropertyAddress(apartment: ApartmentProfileForm) {
  const shortAddress = buildShortPropertyAddress(apartment);
  const locality = clean(apartment.locality);
  const region = clean(apartment.region);
  const postalCode = clean(apartment.postal_code);
  const country = clean(apartment.country);
  const hasStructuredAddress = Boolean(shortAddress || locality || region || postalCode);
  if (!hasStructuredAddress) {
    return clean(apartment.address);
  }
  const structured = [
    shortAddress,
    locality,
    region,
    country,
    postalCode,
  ].filter(Boolean);
  return structured.join(", ").trim() || clean(apartment.address);
}

export function buildPropertyGoogleMapsUrl(apartment: ApartmentProfileForm) {
  const latitude = clean(apartment.latitude);
  const longitude = clean(apartment.longitude);
  if (latitude && longitude) {
    return `https://www.google.com/maps?q=${latitude},${longitude}`;
  }
  const address = buildFullPropertyAddress(apartment);
  if (!address) return "";
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
}

type GoogleAddressComponent = {
  longText?: string;
  shortText?: string;
  long_name?: string;
  short_name?: string;
  types?: string[];
};

function getComponentValue(
  components: GoogleAddressComponent[],
  types: string[],
  mode: "long" | "short" = "long",
) {
  const found = components.find((component) => types.some((type) => component.types?.includes(type)));
  if (!found) return "";
  if (mode === "short") return found.shortText || found.short_name || found.longText || found.long_name || "";
  return found.longText || found.long_name || found.shortText || found.short_name || "";
}

function normalizeCoordinate(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return String(value);
  if (typeof value === "function") return String(value());
  return String(value);
}

export function getCountryRegionCode(country: string) {
  const normalized = clean(country).toLowerCase();
  if (!normalized) return "ua";
  const map: Record<string, string> = {
    україна: "ua",
    ukraine: "ua",
    польща: "pl",
    poland: "pl",
    сша: "us",
    "united states": "us",
    usa: "us",
    великобританія: "gb",
    "united kingdom": "gb",
    britain: "gb",
  };
  return map[normalized] || "";
}

export function buildApartmentFormFromGooglePlace(place: any, current: ApartmentProfileForm): Partial<ApartmentProfileForm> {
  const components = Array.isArray(place?.addressComponents) ? place.addressComponents : [];
  const latitude = normalizeCoordinate(place?.location?.lat);
  const longitude = normalizeCoordinate(place?.location?.lng);
  const nextValues: Partial<ApartmentProfileForm> = {
    country: getComponentValue(components, ["country"]) || current.country || "Україна",
    region:
      getComponentValue(components, ["administrative_area_level_1"]) ||
      current.region,
    locality:
      getComponentValue(components, ["locality", "postal_town", "administrative_area_level_2", "sublocality_level_1"]) ||
      current.locality,
    street: getComponentValue(components, ["route"]) || current.street,
    house_number: getComponentValue(components, ["street_number"]) || current.house_number,
    apartment_number: getComponentValue(components, ["subpremise"]) || current.apartment_number,
    postal_code: getComponentValue(components, ["postal_code"]) || current.postal_code,
    latitude: latitude || current.latitude,
    longitude: longitude || current.longitude,
  };
  const merged = { ...current, ...nextValues };
  return {
    ...nextValues,
    short_address: buildShortPropertyAddress(merged),
    address: place?.formattedAddress || buildFullPropertyAddress(merged),
    google_maps_url: place?.googleMapsURI || buildPropertyGoogleMapsUrl(merged),
  };
}
