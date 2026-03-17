import { useEffect, useRef, useState } from "react";
import { useLanguage } from "@/shared/i18n/provider";
import { loadGoogleMapsPlacesLibrary } from "@/shared/utils/google-maps";
import { getCountryRegionCode } from "@/features/properties/utils/address";

type PlaceAutocompleteFieldProps = {
  country: string;
  onPlaceSelect: (place: any) => void | Promise<void>;
};

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";

export function PlaceAutocompleteField({ country, onPlaceSelect }: PlaceAutocompleteFieldProps) {
  const { language } = useLanguage();
  const hostRef = useRef<HTMLDivElement | null>(null);
  const listenerRef = useRef<((event: Event) => void) | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "disabled" | "error">(
    GOOGLE_MAPS_API_KEY ? "idle" : "disabled",
  );

  useEffect(() => {
    if (!GOOGLE_MAPS_API_KEY) {
      setStatus("disabled");
      return;
    }
    let disposed = false;
    let widget: any = null;
    let handleError: (() => void) | null = null;

    const setup = async () => {
      try {
        setStatus("loading");
        const placesLibrary = await loadGoogleMapsPlacesLibrary(GOOGLE_MAPS_API_KEY);
        if (disposed || !hostRef.current) return;
        const PlaceAutocompleteElement = placesLibrary?.PlaceAutocompleteElement;
        if (!PlaceAutocompleteElement) throw new Error("PlaceAutocompleteElement is unavailable.");
        widget = new PlaceAutocompleteElement();
        widget.className = "places-element";
        widget.setAttribute("placeholder", language === "en" ? "Search address via Google Maps" : "Почніть вводити адресу через Google Maps");
        widget.setAttribute(
          "aria-label",
          language === "en" ? "Property address autocomplete" : "Автопошук адреси нерухомості",
        );
        widget.requestedLanguage = language;
        const regionCode = getCountryRegionCode(country);
        if (regionCode) {
          widget.includedRegionCodes = [regionCode];
          widget.requestedRegion = regionCode;
        }
        const handleSelect = async (event: Event) => {
          const prediction = (event as any)?.placePrediction;
          if (!prediction?.toPlace) return;
          const place = prediction.toPlace();
          await place.fetchFields({
            fields: ["addressComponents", "formattedAddress", "location", "googleMapsURI"],
          });
          await onPlaceSelect(place);
        };
        handleError = () => {
          if (!disposed) setStatus("error");
        };
        listenerRef.current = handleSelect;
        widget.addEventListener("gmp-select", handleSelect);
        widget.addEventListener("gmp-error", handleError);
        widget.addEventListener("gmp-requesterror", handleError);
        hostRef.current.innerHTML = "";
        hostRef.current.appendChild(widget);
        setStatus("ready");
      } catch {
        if (disposed) return;
        setStatus("error");
      }
    };

    setup();
    return () => {
      disposed = true;
      if (widget && listenerRef.current) {
        widget.removeEventListener("gmp-select", listenerRef.current);
      }
      if (widget && handleError) {
        widget.removeEventListener("gmp-error", handleError);
        widget.removeEventListener("gmp-requesterror", handleError);
      }
      if (hostRef.current) {
        hostRef.current.innerHTML = "";
      }
    };
  }, [country, language, onPlaceSelect]);

  return (
    <div className="field places-field">
      <span className="field-label">
        {language === "en" ? "Google Maps address search" : "Пошук адреси через Google Maps"}
      </span>
      <div ref={hostRef} className="places-field-host" />
      {status === "loading" ? (
        <span className="field-help">
          {language === "en" ? "Loading address suggestions..." : "Завантаження підказок адреси..."}
        </span>
      ) : null}
      {status === "disabled" ? (
        <span className="field-help">
          {language === "en"
            ? "Set VITE_GOOGLE_MAPS_API_KEY in .env to enable autocomplete."
            : "Щоб увімкнути автопідстановку, додайте VITE_GOOGLE_MAPS_API_KEY у .env."}
        </span>
      ) : null}
      {status === "error" ? (
        <span className="field-help">
          {language === "en"
            ? "Google Places is temporarily unavailable. Manual entry still works."
            : "Google Places тимчасово недоступний. Ручне введення адреси продовжує працювати."}
        </span>
      ) : null}
    </div>
  );
}
