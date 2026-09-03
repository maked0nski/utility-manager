import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import type {
  MeterTypeItem,
  ProviderItem,
  ServiceCalculationKind,
  ServiceCatalogItem,
  UtilityType,
} from "@/shared/api/types";
import { ServiceCatalogSection } from "@/features/references/components/ServiceCatalogSection";
import { MeterTypesSection } from "@/features/references/components/MeterTypesSection";
import { ProvidersSection } from "@/features/references/components/ProvidersSection";

type ServiceCatalogPayload = {
  code: string;
  name: string;
  calculation_kind: ServiceCalculationKind;
  unit_name: string;
  requires_meter: boolean;
  allowed_meter_utility_type: UtilityType | null;
  default_provider_utility_type: UtilityType | null;
  derived_from_service_id: number | null;
  display_order: number;
  is_active: boolean;
};

type MeterTypePayload = {
  name: string;
  utility_type: UtilityType;
  sort_order: number;
  is_active: boolean;
};

type ProviderPayload = {
  name_full: string;
  utility_type: UtilityType;
  adapter_code: string;
  is_active: boolean;
  note: string;
};

export function ReferencesPage({
  onClose,
  providers,
  meterTypes,
  serviceCatalog,
  createProvider,
  updateProvider,
  deleteProvider,
  createMeterType,
  updateMeterType,
  deleteMeterType,
  createServiceCatalogItem,
  updateServiceCatalogItem,
  deleteServiceCatalogItem,
  confirmRun,
  pushToast,
}: {
  onClose: () => void;
  providers: ProviderItem[];
  meterTypes: MeterTypeItem[];
  serviceCatalog: ServiceCatalogItem[];
  createProvider: (payload: ProviderPayload) => Promise<void>;
  updateProvider: (providerId: number, payload: ProviderPayload) => Promise<void>;
  deleteProvider: (providerId: number) => Promise<void>;
  createMeterType: (payload: MeterTypePayload) => Promise<void>;
  updateMeterType: (meterTypeId: number, payload: MeterTypePayload) => Promise<void>;
  deleteMeterType: (meterTypeId: number) => Promise<void>;
  createServiceCatalogItem: (payload: ServiceCatalogPayload) => Promise<void>;
  updateServiceCatalogItem: (serviceCatalogId: number, payload: ServiceCatalogPayload) => Promise<void>;
  deleteServiceCatalogItem: (serviceCatalogId: number) => Promise<void>;
  confirmRun: (title: string, message: string, action: () => void | Promise<void>) => void;
  pushToast: (message: string, type?: "info" | "success" | "error") => void;
}) {
  return (
    <section className="card">
      <div className="title-row">
        <div>
          <h2>Довідники (спільні для всіх об&apos;єктів)</h2>
          <p className="helper">Зміни тут впливають на всі об&apos;єкти нерухомості, а не лише на обраний зараз.</p>
        </div>
        <button className="secondary" onClick={onClose}>
          ← До об&apos;єктів
        </button>
      </div>

      <div className="tabs">
        <NavLink to="/admin/references/services" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
          Послуги
        </NavLink>
        <NavLink to="/admin/references/meter-types" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
          Типи лічильників
        </NavLink>
        <NavLink to="/admin/references/providers" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
          Постачальники
        </NavLink>
      </div>

      <Routes>
        <Route index element={<Navigate to="/admin/references/services" replace />} />
        <Route
          path="services"
          element={
            <ServiceCatalogSection
              serviceCatalog={serviceCatalog}
              createServiceCatalogItem={createServiceCatalogItem}
              updateServiceCatalogItem={updateServiceCatalogItem}
              deleteServiceCatalogItem={deleteServiceCatalogItem}
              confirmRun={confirmRun}
              pushToast={pushToast}
            />
          }
        />
        <Route
          path="meter-types"
          element={
            <MeterTypesSection
              meterTypes={meterTypes}
              createMeterType={createMeterType}
              updateMeterType={updateMeterType}
              deleteMeterType={deleteMeterType}
              confirmRun={confirmRun}
              pushToast={pushToast}
            />
          }
        />
        <Route
          path="providers"
          element={
            <ProvidersSection
              providers={providers}
              createProvider={createProvider}
              updateProvider={updateProvider}
              deleteProvider={deleteProvider}
              confirmRun={confirmRun}
              pushToast={pushToast}
            />
          }
        />
        <Route path="*" element={<Navigate to="/admin/references/services" replace />} />
      </Routes>
    </section>
  );
}
