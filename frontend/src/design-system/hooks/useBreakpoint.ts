import { useEffect, useState } from "react";

type Breakpoint = "sm" | "md" | "lg" | "xl";

function getBreakpoint(width: number): Breakpoint {
  if (width >= 1280) return "xl";
  if (width >= 1024) return "lg";
  if (width >= 768) return "md";
  return "sm";
}

export function useBreakpoint() {
  const [breakpoint, setBreakpoint] = useState<Breakpoint>(() => getBreakpoint(window.innerWidth));

  useEffect(() => {
    function handleResize() {
      setBreakpoint(getBreakpoint(window.innerWidth));
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return {
    breakpoint,
    isMobile: breakpoint === "sm",
    isTablet: breakpoint === "md",
    isDesktop: breakpoint === "lg" || breakpoint === "xl",
  };
}

