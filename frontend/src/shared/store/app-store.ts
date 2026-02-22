import { create } from "zustand";
import { TOKEN_KEY } from "@/shared/constants/app";

export interface Period {
  year: number;
  month: number;
}

interface AppState {
  token: string;
  sessionError: string;
  selectedApartmentId: number | null;
  period: Period;
  setToken: (token: string) => void;
  clearToken: () => void;
  setSessionError: (sessionError: string) => void;
  setSelectedApartmentId: (selectedApartmentId: number | null) => void;
  setPeriod: (periodOrUpdater: Period | ((period: Period) => Period)) => void;
}

const now = new Date();
const defaultPeriod: Period = {
  year: now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear(),
  month: now.getMonth() === 0 ? 12 : now.getMonth(),
};

export const useAppStore = create<AppState>((set) => ({
  token: localStorage.getItem(TOKEN_KEY) || "",
  sessionError: "",
  selectedApartmentId: Number(localStorage.getItem("selected_apartment_id") || 0) || null,
  period: defaultPeriod,

  setToken: (token) =>
    set(() => {
      localStorage.setItem(TOKEN_KEY, token);
      return { token, sessionError: "" };
    }),
  clearToken: () =>
    set(() => {
      localStorage.removeItem(TOKEN_KEY);
      return { token: "", sessionError: "" };
    }),
  setSessionError: (sessionError) => set({ sessionError }),
  setSelectedApartmentId: (selectedApartmentId) =>
    set(() => {
      if (selectedApartmentId) localStorage.setItem("selected_apartment_id", String(selectedApartmentId));
      else localStorage.removeItem("selected_apartment_id");
      return { selectedApartmentId: selectedApartmentId || null };
    }),
  setPeriod: (periodOrUpdater) =>
    set((state) => ({
      period: typeof periodOrUpdater === "function" ? periodOrUpdater(state.period) : periodOrUpdater,
    })),
}));
