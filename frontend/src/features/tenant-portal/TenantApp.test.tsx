import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import { api } from "@/shared/api/client";

vi.mock("@/shared/api/client", () => ({
  api: vi.fn(),
}));

const mockedApi = vi.mocked(api);

type ApiOverride = Record<string, unknown | ((path: string, token: string | null | undefined) => unknown)>;

afterEach(() => cleanup());

function setupApi(overrides: ApiOverride = {}) {
  localStorage.clear();
  mockedApi.mockReset();
  mockedApi.mockImplementation(async (path: string, token: string | null | undefined) => {
    if (path in overrides) {
      const value = overrides[path];
      if (typeof value === "function") return value(path, token);
      return value;
    }
    if (path === "/tenant/login")
      return {
        access_token: "tenant-token",
        refresh_token: "tenant-refresh-token",
        expires_in: 1800,
        token_type: "bearer",
      };
    if (path === "/tenant/refresh")
      return {
        access_token: "tenant-token",
        refresh_token: "tenant-refresh-token",
        expires_in: 1800,
        token_type: "bearer",
      };
    if (path === "/tenant/me")
      return {
        id: 1,
        full_name: "Тест Орендар",
        email: "tenant@example.com",
        phone: "+380000000000",
        phones: ["+380000000001"],
        portal_enabled: true,
        can_submit_meter_readings: true,
      };
    if (path === "/tenant/me/dashboard")
      return {
        tenant_id: 1,
        tenant_name: "Тест Орендар",
        apartment_code: "APT-1",
        apartment_address: "Тестова 1",
        current_debt: "123.45",
        latest_payment_amount: "700.00",
        latest_payment_date: "2024-10-13",
        current_invoice: {
          id: 7,
          year: 2026,
          month: 2,
          total_amount: "234.56",
          carry_over_debt: "0.00",
          utility_payment_received: "110.00",
          closing_balance: "123.45",
          status: "unpaid",
          items: [
            {
              service_name: "Електроенергія",
              consumption: "12.000",
              unit_name: "kWh",
              unit_price: "4.5000",
              amount: "54.00",
            },
          ],
        },
      };
    if (path === "/tenant/me/history")
      return {
        invoices: [
          {
            id: 7,
            year: 2026,
            month: 2,
            total_amount: "234.56",
            carry_over_debt: "0.00",
            utility_payment_received: "110.00",
            closing_balance: "123.45",
            status: "unpaid",
            items: [
              {
                service_name: "Електроенергія",
                consumption: "12.000",
                unit_name: "kWh",
                unit_price: "4.5000",
                amount: "54.00",
              },
            ],
          },
        ],
      };
    if (path === "/tenant/me/meters")
      return [
        {
          id: 10,
          service_name: "Електроенергія",
          serial_number: "EL-1",
          utility_type: "electricity",
          initial_reading: "0.000",
          installed_at: "2026-01-01",
          is_active: true,
        },
      ];
    if (path === "/tenant/me/profile")
      return {
        id: 1,
        full_name: "Тест Орендар",
        email: "tenant@example.com",
        phone: "+380000000000",
        phones: ["+380000000001"],
        portal_enabled: true,
        can_submit_meter_readings: true,
      };
    if (path === "/tenant/me/password") return { status: "password_changed", session_revoked: true };
    if (path === "/tenant/me/logout-all") return { status: "logged_out_all_sessions" };
    if (path === "/tenant/me/readings") return { id: 11 };
    throw new Error(`Unhandled path: ${path}`);
  });
}

beforeEach(() => {
  setupApi();
});

function renderApp(initialEntries: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={initialEntries}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Tenant flow", () => {
  async function submitLoginForm(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByLabelText("Email"), "tenant@example.com");
    await user.type(screen.getByLabelText("Пароль"), "StrongPass1");
    await user.click(screen.getByRole("button", { name: "Увійти" }));
  }

  it("supports login -> dashboard -> history details -> profile", async () => {
    const user = userEvent.setup();
    renderApp(["/login"]);

    await submitLoginForm(user);

    expect(await screen.findByRole("heading", { name: "Поточний стан" })).toBeInTheDocument();
    expect(screen.getByLabelText("Лічильник")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Історія" }));
    expect(await screen.findByRole("button", { name: "Деталі" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Деталі" }));
    expect(await screen.findByRole("heading", { name: /Рахунок за/ })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Профіль" }));
    expect(await screen.findByText("Email (логін)")).toBeInTheDocument();
    expect(screen.getByLabelText("Новий пароль")).toBeInTheDocument();

    await waitFor(() => {
      expect(mockedApi).toHaveBeenCalledWith("/tenant/login", null, expect.objectContaining({ method: "POST" }));
      expect(mockedApi).toHaveBeenCalledWith("/tenant/me/dashboard", "tenant-token");
      expect(mockedApi).toHaveBeenCalledWith("/tenant/me/history", "tenant-token");
    });
  });

  it("shows localized error for invalid credentials", async () => {
    setupApi({
      "/tenant/login": () => {
        throw new Error("Invalid credentials.");
      },
    });
    const user = userEvent.setup();
    renderApp(["/login"]);
    await submitLoginForm(user);
    expect(await screen.findByText("Невірний email або пароль.")).toBeInTheDocument();
  });

  it("shows localized error when tenant portal is disabled", async () => {
    setupApi({
      "/tenant/login": () => {
        throw new Error("Tenant portal is disabled.");
      },
    });
    const user = userEvent.setup();
    renderApp(["/login"]);
    await submitLoginForm(user);
    expect(await screen.findByText("Кабінет орендаря вимкнений адміністратором.")).toBeInTheDocument();
  });

  it("shows not found state for unknown invoice id", async () => {
    localStorage.setItem("um_tenant_token", "tenant-token");
    localStorage.setItem("um_tenant_refresh_token", "tenant-refresh-token");
    renderApp(["/history/999"]);
    expect(await screen.findByText("Рахунок не знайдено.")).toBeInTheDocument();
  });

  it("shows submit disabled message when meter readings are not allowed", async () => {
    setupApi({
      "/tenant/me": {
        id: 1,
        full_name: "Тест Орендар",
        email: "tenant@example.com",
        phone: "+380000000000",
        phones: [],
        portal_enabled: true,
        can_submit_meter_readings: false,
      },
    });
    localStorage.setItem("um_tenant_token", "tenant-token");
    localStorage.setItem("um_tenant_refresh_token", "tenant-refresh-token");
    renderApp(["/dashboard"]);
    expect(await screen.findByText("Передача показників наразі вимкнена адміністратором.")).toBeInTheDocument();
  });
});
