import { useState } from "react";
import { In, Se } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";

type AdminRole = "admin" | "operator" | "read_only";

type AdminUser = {
  id: number;
  username: string;
  role: AdminRole;
  is_active: boolean;
};

type CreateAdminPayload = {
  username: string;
  password: string;
  role: Exclude<AdminRole, "admin"> | "admin";
};

export function AdminUsersModal({
  open,
  onClose,
  users,
  onCreate,
  onUpdate,
}: {
  open: boolean;
  onClose: () => void;
  users: AdminUser[];
  onCreate: (payload: CreateAdminPayload) => void;
  onUpdate: (payload: AdminUser) => void;
}) {
  const [form, setForm] = useState<CreateAdminPayload>({
    username: "",
    password: "",
    role: "operator",
  });
  if (!open) return null;
  return (
    <Modal title="Користувачі адмін-панелі" onClose={onClose}>
      <div className="subcard">
        <h4>Додати користувача</h4>
        <div className="forms-grid">
          <In tip="Логін" value={form.username} onChange={(e) => setForm((s) => ({ ...s, username: e.target.value }))} />
          <In tip="Пароль (мін. 8 символів)" type="password" value={form.password} onChange={(e) => setForm((s) => ({ ...s, password: e.target.value }))} />
          <Se tip="Роль" value={form.role} onChange={(e) => setForm((s) => ({ ...s, role: e.target.value }))}>
            <option value="operator">operator</option>
            <option value="read_only">read_only</option>
            <option value="admin">admin</option>
          </Se>
        </div>
        <button
          disabled={!form.username || !form.password || form.password.length < 8}
          onClick={() => {
            onCreate(form);
            setForm({ username: "", password: "", role: "operator" });
          }}
        >
          Створити
        </button>
      </div>
      <div className="subcard top-gap">
        <h4>Список користувачів</h4>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Логін</th>
                <th>Роль</th>
                <th>Стан</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(users || []).map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>
                    <Se value={u.role} onChange={(e) => onUpdate({ ...u, role: e.target.value })}>
                      <option value="admin">admin</option>
                      <option value="operator">operator</option>
                      <option value="read_only">read_only</option>
                    </Se>
                  </td>
                  <td>
                    <label className="check">
                      <input type="checkbox" checked={u.is_active} onChange={(e) => onUpdate({ ...u, is_active: e.target.checked })} />
                      {u.is_active ? "активний" : "вимкнений"}
                    </label>
                  </td>
                  <td></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Modal>
  );
}
