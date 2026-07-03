"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { IconButton } from "@/components/ui/icon-button";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="h-9 w-9" />;

  const isDark = theme === "dark";
  return (
    <IconButton label={isDark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => setTheme(isDark ? "light" : "dark")}>
      {isDark ? <Sun size={17} /> : <Moon size={17} />}
    </IconButton>
  );
}
