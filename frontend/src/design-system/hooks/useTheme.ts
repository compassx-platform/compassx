import { useEffect, useState } from "react";

export type ThemeMode = "light" | "dark";

const STORAGE_KEY = "app_theme_config";

export function useTheme() {
  const [theme, setTheme] = useState<ThemeMode>("light");

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { isDarkMode?: boolean };
      setTheme(parsed.isDarkMode ? "dark" : "light");
    } catch {
      setTheme("light");
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ isDarkMode: theme === "dark" }));
  }, [theme]);

  return {
    theme,
    setTheme,
    toggleTheme: () => setTheme((current) => (current === "dark" ? "light" : "dark")),
    isDark: theme === "dark",
  };
}

