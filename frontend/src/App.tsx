import { Suspense, lazy, useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { useLanguage } from "@/shared/i18n/provider";

const AdminApp = lazy(() => import("@/features/admin/AdminApp").then((m) => ({ default: m.AdminApp })));
const TenantApp = lazy(() =>
  import("@/features/tenant-portal/TenantApp").then((m) => ({ default: m.TenantApp })),
);

export default function App() {
  const location = useLocation();
  const { t } = useLanguage();

  useEffect(() => {
    document.querySelectorAll(".drawer-backdrop, .modal-backdrop").forEach((node) => {
      if (node instanceof HTMLElement) node.remove();
    });
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("pointer-events");
  }, [location.pathname]);

  return (
    <Suspense fallback={<div className="app-shell"><section className="card"><p className="helper">{t("common.loading", "Завантаження інтерфейсу...")}</p></section></div>}>
      <Routes>
        <Route path="/admin/*" element={<AdminApp />} />
        <Route path="/*" element={<TenantApp />} />
      </Routes>
    </Suspense>
  );
}
