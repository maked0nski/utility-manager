import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useMeterActions } from "@/features/properties/hooks/use-meter-actions";

const apiMock = vi.hoisted(() => vi.fn());

vi.mock("@/shared/api/client", () => ({
  api: (...args: unknown[]) => apiMock(...args),
}));

describe("useMeterActions", () => {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
  );

  it("creates meter via POST /admin/meters", async () => {
    apiMock.mockResolvedValueOnce({ id: 1 });
    const pushToast = vi.fn();
    const reload = vi.fn().mockResolvedValue(undefined);
    const setMeterForm = vi.fn();
    const setEditingMeterId = vi.fn();

    const { result } = renderHook(
      () =>
        useMeterActions({
          tok: "token",
          apartmentId: 11,
          meterForm: {
            service_name: "Вода",
            utility_type: "water",
            serial_number: "W-001",
            initial_reading: "10",
            installed_at: "2026-01-01",
          },
          editingMeterId: null,
          setMeterForm,
          setEditingMeterId,
          pushToast,
          confirmRun: vi.fn(),
          reload,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.submitMeter();
    });

    expect(apiMock).toHaveBeenCalledWith(
      "/admin/meters",
      "token",
      expect.objectContaining({ method: "POST" }),
    );
    expect(reload).toHaveBeenCalled();
  });

  it("updates meter via PUT /admin/meters/{id}", async () => {
    apiMock.mockResolvedValueOnce({ id: 77 });
    const pushToast = vi.fn();
    const reload = vi.fn().mockResolvedValue(undefined);
    const setMeterForm = vi.fn();
    const setEditingMeterId = vi.fn();

    const { result } = renderHook(
      () =>
        useMeterActions({
          tok: "token",
          apartmentId: 11,
          meterForm: {
            service_name: "Електрика",
            utility_type: "electricity",
            serial_number: "E-777",
            initial_reading: "25",
            installed_at: "2026-01-02",
          },
          editingMeterId: 77,
          setMeterForm,
          setEditingMeterId,
          pushToast,
          confirmRun: vi.fn(),
          reload,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.submitMeter();
    });

    expect(apiMock).toHaveBeenCalledWith(
      "/admin/meters/77",
      "token",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(reload).toHaveBeenCalled();
  });

  it("deletes meter after confirmation", async () => {
    apiMock.mockResolvedValueOnce({ status: "deleted" });
    const pushToast = vi.fn();
    const reload = vi.fn().mockResolvedValue(undefined);
    const setMeterForm = vi.fn();
    const setEditingMeterId = vi.fn();
    const confirmRun = vi.fn();

    const { result } = renderHook(
      () =>
        useMeterActions({
          tok: "token",
          apartmentId: 11,
          meterForm: {
            service_name: "",
            utility_type: "other",
            serial_number: "",
            initial_reading: "",
            installed_at: "",
          },
          editingMeterId: null,
          setMeterForm,
          setEditingMeterId,
          pushToast,
          confirmRun,
          reload,
        }),
      { wrapper },
    );

    const meter = {
      id: 42,
      service_name: "Газ",
      utility_type: "gas" as const,
      serial_number: null,
      initial_reading: "0",
      installed_at: "2026-01-01",
    };

    result.current.askDeleteMeter(meter);
    expect(confirmRun).toHaveBeenCalledTimes(1);
    const action = confirmRun.mock.calls[0][2] as () => Promise<void>;

    await act(async () => {
      await action();
    });

    expect(apiMock).toHaveBeenCalledWith(
      "/admin/meters/42",
      "token",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(reload).toHaveBeenCalled();
  });
});
