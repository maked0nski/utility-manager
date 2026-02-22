interface MonthlyCycleInput {
  previousDebt: number | string;
  monthCharges: number | string;
  monthPayments: number | string;
  isLocked: boolean;
}

export const calcCurrentBalance = ({
  previousDebt,
  monthCharges,
  monthPayments,
}: MonthlyCycleInput): number =>
  Number(previousDebt || 0) + Number(monthCharges || 0) - Number(monthPayments || 0);

export const calcNextPreviousDebt = ({
  currentBalance,
  isLocked,
}: {
  currentBalance: number | string;
  isLocked: boolean;
}): number | null => (isLocked ? Number(currentBalance || 0) : null);
