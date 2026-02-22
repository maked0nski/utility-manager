import { useState } from "react";
import { todayIso } from "@/shared/utils/date";

type TabKey = "calc" | "tenant" | "tariffs" | "owner" | "report" | "property";
type BootstrapInfo = {
  username: string | null;
  password: string | null;
  must_change_password: boolean;
  password_rotation_recommended: boolean;
};

export function useUiState() {
  const [cred, setCred] = useState({ username: "admin", password: "" });
  const [boot, setBoot] = useState<BootstrapInfo>({
    username: null,
    password: null,
    must_change_password: false,
    password_rotation_recommended: false,
  });
  const [tab, setTab] = useState<TabKey>("calc");
  const [err, setErr] = useState("");
  const [drawer, setDrawer] = useState(false);
  const [addProp, setAddProp] = useState(false);
  const [pay, setPay] = useState({
    amount: "",
    paid_at: todayIso(),
    note: "",
  });
  const [pwd, setPwd] = useState({ current_password: "", new_password: "" });

  return {
    cred,
    setCred,
    boot,
    setBoot,
    tab,
    setTab,
    err,
    setErr,
    drawer,
    setDrawer,
    addProp,
    setAddProp,
    pay,
    setPay,
    pwd,
    setPwd,
  };
}
