declare global {
  interface Window {
    google?: any;
  }
}

let googleMapsLoaderPromise: Promise<any> | null = null;

function injectGoogleMapsLoader(apiKey: string) {
  return new Promise<any>((resolve, reject) => {
    const win = window as Window & { google?: any };
    const googleNamespace = (win.google = win.google || {});
    const mapsNamespace = (googleNamespace.maps = googleNamespace.maps || {});
    const importLibrary = "importLibrary";
    if (mapsNamespace[importLibrary]) {
      resolve(mapsNamespace);
      return;
    }

    let scriptLoadingPromise: Promise<any> | null = null;
    const requestedLibraries = new Set<string>();
    const callbackName = "__ib__";
    const params = new URLSearchParams();

    const ensureScript = () =>
      scriptLoadingPromise ||
      (scriptLoadingPromise = new Promise(async (resolveScript, rejectScript) => {
        const script = document.createElement("script");
        params.set("libraries", [...requestedLibraries].join(","));
        params.set("key", apiKey);
        params.set("v", "weekly");
        params.set("loading", "async");
        params.set("callback", `google.maps.${callbackName}`);
        script.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
        mapsNamespace[callbackName] = resolveScript;
        script.onerror = () => rejectScript(new Error("Google Maps JavaScript API could not load."));
        const nonceSource = document.querySelector("script[nonce]") as HTMLScriptElement | null;
        script.nonce = nonceSource?.nonce || "";
        document.head.append(script);
      }));

    mapsNamespace[importLibrary] = (libraryName: string, ...rest: unknown[]) => {
      requestedLibraries.add(libraryName);
      return ensureScript().then(() => mapsNamespace[importLibrary](libraryName, ...rest));
    };
    ensureScript().then(() => resolve(mapsNamespace)).catch(reject);
  });
}

export async function loadGoogleMapsPlacesLibrary(apiKey: string) {
  if (!apiKey) {
    throw new Error("Google Maps API key is not configured.");
  }
  if (!googleMapsLoaderPromise) {
    googleMapsLoaderPromise = injectGoogleMapsLoader(apiKey);
  }
  await googleMapsLoaderPromise;
  return window.google.maps.importLibrary("places");
}
