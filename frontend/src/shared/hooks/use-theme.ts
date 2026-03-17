import { useEffect, useMemo, useRef, useState } from "react";

export type UiTheme = "light" | "dark" | "auto";
type ResolvedTheme = "light" | "dark";

const THEME_KEY = "um-ui-theme";
const GEO_KEY = "um-ui-theme-geo";

type CachedGeo = {
  lat: number;
  lon: number;
  savedAt: number;
};

const detectSystemTheme = (): ResolvedTheme => {
  if (typeof window === "undefined" || !window.matchMedia) return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

const readStoredTheme = (): UiTheme | null => {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem(THEME_KEY);
  return stored === "dark" || stored === "light" || stored === "auto" ? stored : null;
};

const readStoredGeo = (): CachedGeo | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(GEO_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CachedGeo>;
    if (
      typeof parsed.lat === "number" &&
      Number.isFinite(parsed.lat) &&
      typeof parsed.lon === "number" &&
      Number.isFinite(parsed.lon)
    ) {
      return {
        lat: parsed.lat,
        lon: parsed.lon,
        savedAt: typeof parsed.savedAt === "number" ? parsed.savedAt : Date.now(),
      };
    }
  } catch {
    return null;
  }
  return null;
};

const storeGeo = (geo: CachedGeo | null) => {
  if (typeof window === "undefined") return;
  if (!geo) {
    window.localStorage.removeItem(GEO_KEY);
    return;
  }
  window.localStorage.setItem(GEO_KEY, JSON.stringify(geo));
};

const resolveInitialTheme = (): UiTheme => readStoredTheme() || "auto";

const degToRad = (value: number) => (value * Math.PI) / 180;
const radToDeg = (value: number) => (value * 180) / Math.PI;

const getDayOfYear = (date: Date) => {
  const start = new Date(date.getFullYear(), 0, 0);
  const diff = date.getTime() - start.getTime();
  return Math.floor(diff / 86400000);
};

const normalizeAngle = (value: number) => {
  let normalized = value % 360;
  if (normalized < 0) normalized += 360;
  return normalized;
};

const calculateSunEvent = (date: Date, lat: number, lon: number, isSunrise: boolean): Date | null => {
  const zenith = 90.833;
  const dayOfYear = getDayOfYear(date);
  const lngHour = lon / 15;
  const approxTime = dayOfYear + ((isSunrise ? 6 : 18) - lngHour) / 24;
  const meanAnomaly = 0.9856 * approxTime - 3.289;
  let trueLongitude =
    meanAnomaly +
    1.916 * Math.sin(degToRad(meanAnomaly)) +
    0.02 * Math.sin(degToRad(2 * meanAnomaly)) +
    282.634;
  trueLongitude = normalizeAngle(trueLongitude);

  let rightAscension = radToDeg(Math.atan(0.91764 * Math.tan(degToRad(trueLongitude))));
  rightAscension = normalizeAngle(rightAscension);
  const lQuadrant = Math.floor(trueLongitude / 90) * 90;
  const raQuadrant = Math.floor(rightAscension / 90) * 90;
  rightAscension = (rightAscension + (lQuadrant - raQuadrant)) / 15;

  const sinDeclination = 0.39782 * Math.sin(degToRad(trueLongitude));
  const cosDeclination = Math.cos(Math.asin(sinDeclination));
  const cosHourAngle =
    (Math.cos(degToRad(zenith)) - sinDeclination * Math.sin(degToRad(lat))) /
    (cosDeclination * Math.cos(degToRad(lat)));

  if (cosHourAngle < -1 || cosHourAngle > 1) return null;

  let hourAngle = isSunrise ? 360 - radToDeg(Math.acos(cosHourAngle)) : radToDeg(Math.acos(cosHourAngle));
  hourAngle /= 15;

  const localMeanTime = hourAngle + rightAscension - 0.06571 * approxTime - 6.622;
  const utcHour = (localMeanTime - lngHour + 24) % 24;
  const hours = Math.floor(utcHour);
  const minutesFloat = (utcHour - hours) * 60;
  const minutes = Math.floor(minutesFloat);
  const seconds = Math.floor((minutesFloat - minutes) * 60);

  return new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), hours, minutes, seconds));
};

const resolveAutoTheme = (now: Date, geo: CachedGeo | null): ResolvedTheme => {
  const systemTheme = detectSystemTheme();
  if (!geo) return systemTheme;
  const sunrise = calculateSunEvent(now, geo.lat, geo.lon, true);
  const sunset = calculateSunEvent(now, geo.lat, geo.lon, false);
  if (!sunrise || !sunset) return systemTheme;
  const current = now.getTime();
  return current >= sunrise.getTime() && current < sunset.getTime() ? "light" : "dark";
};

const applyTheme = (theme: ResolvedTheme) => {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.classList.toggle("dark", theme === "dark");
};

export function useTheme() {
  const [theme, setTheme] = useState<UiTheme>(resolveInitialTheme);
  const [geo, setGeo] = useState<CachedGeo | null>(readStoredGeo);
  const [now, setNow] = useState(() => new Date());
  const requestedGeoRef = useRef(false);

  const resolvedTheme = useMemo<ResolvedTheme>(() => {
    if (theme === "light" || theme === "dark") return theme;
    return resolveAutoTheme(now, geo);
  }, [theme, now, geo]);

  useEffect(() => {
    applyTheme(resolvedTheme);
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme, resolvedTheme]);

  useEffect(() => {
    if (theme !== "auto") return;
    const intervalId = window.setInterval(() => setNow(new Date()), 60000);
    return () => window.clearInterval(intervalId);
  }, [theme]);

  useEffect(() => {
    if (theme !== "auto" || requestedGeoRef.current || typeof window === "undefined") return;
    if (!("geolocation" in navigator)) return;
    requestedGeoRef.current = true;
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const nextGeo = {
          lat: position.coords.latitude,
          lon: position.coords.longitude,
          savedAt: Date.now(),
        };
        setGeo(nextGeo);
        setNow(new Date());
        storeGeo(nextGeo);
      },
      () => {
        setNow(new Date());
      },
      {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 1000 * 60 * 60 * 12,
      },
    );
  }, [theme]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === THEME_KEY) {
        const next = readStoredTheme();
        if (next) setTheme(next);
        return;
      }
      if (event.key === GEO_KEY) {
        setGeo(readStoredGeo());
        setNow(new Date());
      }
    };
    const onThemeChanged = (event: Event) => {
      const custom = event as CustomEvent<UiTheme>;
      if ((custom.detail === "dark" || custom.detail === "light" || custom.detail === "auto") && custom.detail !== theme) {
        setTheme(custom.detail);
      }
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener("um-theme-changed", onThemeChanged as EventListener);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("um-theme-changed", onThemeChanged as EventListener);
    };
  }, [theme]);

  return {
    theme,
    resolvedTheme,
    isDark: resolvedTheme === "dark",
    setTheme,
    cycleTheme: () =>
      setTheme((prev) => {
        if (prev === "light") return "dark";
        if (prev === "dark") return "auto";
        return "light";
      }),
  };
}
