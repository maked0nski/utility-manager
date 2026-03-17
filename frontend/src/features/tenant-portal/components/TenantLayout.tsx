import { Outlet } from "react-router-dom";
import { TenantHeader } from "@/features/tenant-portal/components/TenantHeader";

export function TenantLayout({
  error,
  notice,
  meLoading,
  meName,
  onLogout,
}: {
  error: string;
  notice: string;
  meLoading: boolean;
  meName: string;
  onLogout: () => void;
}) {
  return (
    <div className="tenant-portal tenant-shell">
      <TenantHeader
        fullName={meLoading ? "Завантаження..." : meName}
        onLogout={onLogout}
      />
      {error ? <div className="tenant-error tenant-inline-error">{error}</div> : null}
      {notice ? <div className="tenant-notice tenant-inline-error">{notice}</div> : null}
      <Outlet />
    </div>
  );
}
