import { useAppStore } from "@/shared/store/app-store";
import { isPeriodAfterMaxAllowed } from "@/shared/utils/date";

export function usePeriod() {
  const period = useAppStore((s) => s.period);
  const setPeriod = useAppStore((s) => s.setPeriod);

  const shiftPeriod = (delta: number) => {
    setPeriod((current) => {
      let month = current.month + delta;
      let year = current.year;
      if (month < 1) {
        month = 12;
        year -= 1;
      }
      if (month > 12) {
        month = 1;
        year += 1;
      }
      if (isPeriodAfterMaxAllowed(year, month)) return current;
      return { year, month };
    });
  };

  return { period, setPeriod, shiftPeriod };
}
