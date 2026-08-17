import { createContext, useContext, type ReactNode } from "react";
import { useTheme, type ThemeMode } from "../hooks/useTheme";

type ThemeContextValue = {
  theme: ThemeMode;
  isDark: boolean;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const themeState = useTheme();

  return (
    <ThemeContext.Provider
      value={{
        theme: themeState.theme,
        isDark: themeState.isDark,
        setTheme: themeState.setTheme,
        toggleTheme: themeState.toggleTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useThemeContext() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useThemeContext must be used inside ThemeProvider");
  }
  return context;
}

