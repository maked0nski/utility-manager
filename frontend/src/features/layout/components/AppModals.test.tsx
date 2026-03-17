import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppModals } from "@/features/layout/components/AppModals";

afterEach(() => cleanup());

const baseProps = () => ({
  payModal: false,
  setPayModal: vi.fn(),
  pay: { amount: "", paid_at: "", note: "" },
  savePay: vi.fn().mockResolvedValue(undefined),
  pwdModal: false,
  setPwdModal: vi.fn(),
  pwd: { current_password: "", new_password: "" },
  changePassword: vi.fn().mockResolvedValue(undefined),
  adminsModal: false,
  setAdminsModal: vi.fn(),
  adminUsersQuery: { data: [] },
  createAdminUserMutation: { mutate: vi.fn() },
  updateAdminUserMutation: { mutate: vi.fn() },
  changeAdminPasswordMutation: { mutate: vi.fn() },
  tModal: null,
  tForm: null,
  saveT: vi.fn(),
  delT: vi.fn(),
  meters: [],
  tariffServiceNames: [],
  providers: [],
  setTModal: vi.fn(),
  setTFormModal: vi.fn(),
  ocModal: null,
  ocForm: null,
  setOcModal: vi.fn(),
  setOcForm: vi.fn(),
  saveOc: vi.fn(),
  delOc: vi.fn(),
  mrModal: null,
  mrForm: null,
  setMrModal: vi.fn(),
  setMrForm: vi.fn(),
  saveMr: vi.fn(),
  delMr: vi.fn(),
  confirm: { open: false, title: "", message: "" },
  setConfirm: vi.fn(),
  confirmActionRef: { current: null },
  toasts: [],
  setToasts: vi.fn(),
});

describe("AppModals pay modal", () => {
  it("validates required fields", async () => {
    const user = userEvent.setup();
    const props = baseProps();
    props.payModal = true;
    render(<AppModals {...props} />);

    const saveButtons = screen.getAllByRole("button", { name: "Зберегти" });
    await user.click(saveButtons[saveButtons.length - 1]);
    expect(await screen.findByText("Сума має бути більшою за 0")).toBeInTheDocument();
    expect(props.savePay).not.toHaveBeenCalled();
  });

  it("submits valid payment payload", async () => {
    const user = userEvent.setup();
    const props = baseProps();
    props.payModal = true;
    props.pay = { amount: "100", paid_at: "2025-01-10", note: "test" };
    render(<AppModals {...props} />);

    const amountInputs = screen.getAllByTitle("Сума оплати комуналки");
    const amountInput = amountInputs[amountInputs.length - 1] as HTMLInputElement;
    expect(amountInput).toBeTruthy();
    await user.clear(amountInput);
    await user.type(amountInput, "150");
    await user.click(screen.getByRole("button", { name: "Зберегти" }));

    expect(props.savePay).toHaveBeenCalled();
    const payload = props.savePay.mock.calls[0][0];
    expect(payload).toMatchObject({ amount: 150, paid_at: "2025-01-10", note: "test" });
  });
});
