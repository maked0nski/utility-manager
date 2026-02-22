import { useEffect, useState } from "react";
import { useAppStore } from "@/shared/store/app-store";

export function useSession() {
  const token = useAppStore((s) => s.token);
  const sessionError = useAppStore((s) => s.sessionError);
  const setToken = useAppStore((s) => s.setToken);
  const clearTokenState = useAppStore((s) => s.clearToken);
  const setSessionError = useAppStore((s) => s.setSessionError);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    const onUnauthorized = () => {
      clearTokenState();
      setSessionError("Сесія закінчилась. Увійдіть знову.");
    };
    window.addEventListener("um-unauthorized", onUnauthorized);
    setInitialized(true);
    return () => window.removeEventListener("um-unauthorized", onUnauthorized);
  }, [clearTokenState, setSessionError]);

  const saveToken = (nextToken: string) => {
    setToken(nextToken);
  };

  const clearToken = () => {
    clearTokenState();
  };

  return { token, saveToken, clearToken, sessionError, setSessionError, initialized };
}
