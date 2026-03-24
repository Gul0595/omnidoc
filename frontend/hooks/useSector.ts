import { useState, useEffect } from "react";

export interface Sector {
  id: string; label: string; accent: string;
}

export const ACCENT: Record<string, {
  bg: string; text: string; lightBg: string; lightText: string; border: string;
}> = {
  green:  { bg:"bg-green-500",  text:"text-white", lightBg:"bg-green-50",  lightText:"text-green-700",  border:"border-green-200" },
  teal:   { bg:"bg-teal-500",   text:"text-white", lightBg:"bg-teal-50",   lightText:"text-teal-700",   border:"border-teal-200"  },
  purple: { bg:"bg-purple-500", text:"text-white", lightBg:"bg-purple-50", lightText:"text-purple-700", border:"border-purple-200"},
  red:    { bg:"bg-red-500",    text:"text-white", lightBg:"bg-red-50",    lightText:"text-red-700",    border:"border-red-200"   },
  amber:  { bg:"bg-amber-500",  text:"text-white", lightBg:"bg-amber-50",  lightText:"text-amber-700",  border:"border-amber-200" },
  blue:   { bg:"bg-blue-500",   text:"text-white", lightBg:"bg-blue-50",   lightText:"text-blue-700",   border:"border-blue-200"  },
};

export const getAccent = (accent: string) => ACCENT[accent] ?? ACCENT.blue;

export const useSector = () => {
  const [activeSector, setActiveSectorState] = useState("it");

  useEffect(() => {
    const stored = localStorage.getItem("omnidoc_sector");
    if (stored) setActiveSectorState(stored);
  }, []);

  const setActiveSector = (id: string) => {
    setActiveSectorState(id);
    localStorage.setItem("omnidoc_sector", id);
  };

  return { activeSector, setActiveSector };
};
