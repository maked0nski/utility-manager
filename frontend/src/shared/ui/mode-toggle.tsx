import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/shared/i18n/provider";
import { useTheme } from "@/shared/hooks/use-theme";

export function ModeToggle() {
  const { theme, resolvedTheme, cycleTheme } = useTheme();
  const { t } = useLanguage();

  const currentLabel =
    theme === "auto"
      ? t("settings.theme.auto", "Авто")
      : theme === "dark"
        ? t("settings.theme.dark", "Темна")
        : t("settings.theme.light", "Світла");
  const nextLabel =
    theme === "light"
      ? t("settings.theme.dark", "Темна")
      : theme === "dark"
        ? t("settings.theme.auto", "Авто")
        : t("settings.theme.light", "Світла");

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      className={`theme-toggle-trigger mode-${theme} resolved-${resolvedTheme}`}
      aria-label={`${t("settings.theme", "Тема")}: ${currentLabel}. ${t("settings.theme.next", "Наступна")}: ${nextLabel}.`}
      title={`${t("settings.theme", "Тема")}: ${currentLabel}. ${t("settings.theme.next", "Наступна")}: ${nextLabel}.`}
      onClick={cycleTheme}
    >
      {theme === "auto" ? (
        <Monitor className="theme-toggle-icon" />
      ) : theme === "dark" ? (
        <Moon className="theme-toggle-icon" />
      ) : (
        <Sun className="theme-toggle-icon" />
      )}
      <span className="sr-only">{t("settings.theme", "Тема")}</span>
    </Button>
  );
}
