import { Navigate, Outlet } from "react-router-dom";

export function TenantRequireAuth({ token }: { token: string }) {
  if (!token) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export function TenantRequireGuest({ token }: { token: string }) {
  if (token) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}
