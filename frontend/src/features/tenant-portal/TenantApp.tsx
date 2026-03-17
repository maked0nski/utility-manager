import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "@/shared/api/client";
import { TENANT_REFRESH_TOKEN_KEY, TENANT_TOKEN_KEY } from "@/shared/constants/app";
import { TenantRequireAuth, TenantRequireGuest } from "@/features/tenant-portal/components/TenantGuards";
import { TenantLayout } from "@/features/tenant-portal/components/TenantLayout";
import { TenantDashboardPage } from "@/features/tenant-portal/pages/TenantDashboardPage";
import { TenantHistoryPage } from "@/features/tenant-portal/pages/TenantHistoryPage";
import { TenantInvoiceDetailsPage } from "@/features/tenant-portal/pages/TenantInvoiceDetailsPage";
import { TenantLoginPage } from "@/features/tenant-portal/pages/TenantLoginPage";
import { TenantProfilePage } from "@/features/tenant-portal/pages/TenantProfilePage";
import { localizeApiError } from "@/features/tenant-portal/utils";
import type { MeterItem, TenantDashboard, TenantHistory, TenantMe, TenantSession } from "@/shared/api/types";

export function TenantApp() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [token, setToken] = useState(() => localStorage.getItem(TENANT_TOKEN_KEY) || "");
  const [refreshToken, setRefreshToken] = useState(() => localStorage.getItem(TENANT_REFRESH_TOKEN_KEY) || "");
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    // Defensive cleanup for stale overlays that can block tenant UI after route switches.
    document.querySelectorAll(".drawer-backdrop, .modal-backdrop").forEach((node) => {
      if (node instanceof HTMLElement) node.remove();
    });
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("pointer-events");
  }, []);

  const applySession = (session: TenantSession) => {
    localStorage.setItem(TENANT_TOKEN_KEY, session.access_token);
    localStorage.setItem(TENANT_REFRESH_TOKEN_KEY, session.refresh_token);
    setToken(session.access_token);
    setRefreshToken(session.refresh_token);
  };

  const clearSession = (reason = "") => {
    localStorage.removeItem(TENANT_TOKEN_KEY);
    localStorage.removeItem(TENANT_REFRESH_TOKEN_KEY);
    setToken("");
    setRefreshToken("");
    queryClient.removeQueries({ queryKey: ["tenant"] });
    if (reason) setError(reason);
  };

  useEffect(() => {
    const onUnauthorized = async () => {
      if (refreshing) return;
      if (!refreshToken) {
        clearSession("Сесія завершилась. Увійдіть повторно.");
        navigate("/login", { replace: true });
        return;
      }
      try {
        setRefreshing(true);
        const next = await api<TenantSession>("/tenant/refresh", null, {
          method: "POST",
          body: { refresh_token: refreshToken },
        });
        applySession(next);
        setError("");
        queryClient.invalidateQueries({ queryKey: ["tenant"] });
      } catch (refreshError) {
        clearSession(localizeApiError(refreshError, "Сесія завершилась. Увійдіть повторно."));
        navigate("/login", { replace: true });
      } finally {
        setRefreshing(false);
      }
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === TENANT_TOKEN_KEY) setToken(event.newValue || "");
      if (event.key === TENANT_REFRESH_TOKEN_KEY) setRefreshToken(event.newValue || "");
    };

    window.addEventListener("um-unauthorized", onUnauthorized);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("um-unauthorized", onUnauthorized);
      window.removeEventListener("storage", onStorage);
    };
  }, [navigate, queryClient, refreshToken, refreshing]);

  useEffect(() => {
    if (!token || !refreshToken) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api<TenantSession>("/tenant/refresh", null, {
          method: "POST",
          body: { refresh_token: refreshToken },
        });
        applySession(next);
      } catch {
        clearSession("Сесія завершилась. Увійдіть повторно.");
        navigate("/login", { replace: true });
      }
    }, 1000 * 60 * 10);
    return () => window.clearInterval(timer);
  }, [token, refreshToken, navigate]);

  const meQuery = useQuery({
    queryKey: ["tenant", "me", token],
    enabled: Boolean(token),
    queryFn: () => api<TenantMe>("/tenant/me", token),
  });

  const dashboardQuery = useQuery({
    queryKey: ["tenant", "dashboard", token],
    enabled: Boolean(token),
    queryFn: () => api<TenantDashboard>("/tenant/me/dashboard", token),
  });

  const historyQuery = useQuery({
    queryKey: ["tenant", "history", token],
    enabled: Boolean(token),
    queryFn: () => api<TenantHistory>("/tenant/me/history", token),
  });

  const metersQuery = useQuery({
    queryKey: ["tenant", "meters", token],
    enabled: Boolean(token),
    queryFn: () => api<MeterItem[]>("/tenant/me/meters", token),
  });

  const logout = () => {
    clearSession();
    navigate("/login", { replace: true });
  };

  return (
    <Routes>
      <Route element={<TenantRequireGuest token={token} />}>
        <Route
          path="/login"
          element={
            <TenantLoginPage
              onSessionCreated={applySession}
              setError={setError}
              setNotice={setNotice}
              error={error}
            />
          }
        />
      </Route>

      <Route element={<TenantRequireAuth token={token} />}>
        <Route
          element={
            <TenantLayout
              error={error}
              notice={notice}
              meLoading={meQuery.isLoading}
              meName={meQuery.data?.full_name || ""}
              onLogout={logout}
            />
          }
        >
          <Route
            path="/dashboard"
            element={
              <TenantDashboardPage
                token={token}
                canSubmitMeterReadings={Boolean(meQuery.data?.can_submit_meter_readings)}
                dashboard={dashboardQuery}
                meters={metersQuery}
                setError={setError}
                setNotice={setNotice}
              />
            }
          />
          <Route path="/history" element={<TenantHistoryPage history={historyQuery} />} />
          <Route path="/history/:invoiceId" element={<TenantInvoiceDetailsPage history={historyQuery} />} />
          <Route
            path="/profile"
            element={
              <TenantProfilePage
                token={token}
                me={meQuery}
                setError={setError}
                setNotice={setNotice}
                onSessionRevoked={(reason) => {
                  clearSession(reason);
                  navigate("/login", { replace: true });
                }}
              />
            }
          />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
