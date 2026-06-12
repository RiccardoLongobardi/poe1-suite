/**
 * Lightweight i18n — Italian / English, no external dependency.
 *
 * Translations are co-located with their usage: instead of a central
 * key dictionary, each string is written inline as `t({ it, en })`.
 * For a two-language app this keeps translations next to the markup,
 * with no key bookkeeping and no risk of missing keys.
 *
 *   const t = useT();
 *   <Text>{t({ it: "Ciao", en: "Hi" })}</Text>
 *
 * The chosen language persists to localStorage.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Lang = "it" | "en";

/** A single translatable string. */
export interface Tr {
  it: string;
  en: string;
}

const STORAGE_KEY = "fob_lang";

interface LangContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
}

const LangContext = createContext<LangContextValue>({
  lang: "it",
  setLang: () => {},
});

function initialLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "it" || stored === "en") return stored;
  } catch {
    // localStorage unavailable — fall through to the default.
  }
  return "it";
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // ignore — persistence is best-effort.
    }
  }, []);

  const value = useMemo(() => ({ lang, setLang }), [lang, setLang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

/** Current language + setter. */
export function useLang(): LangContextValue {
  return useContext(LangContext);
}

/** Returns the translator: `t({ it, en }) → string` for the active language. */
export function useT(): (tr: Tr) => string {
  const { lang } = useContext(LangContext);
  return useCallback((tr: Tr) => tr[lang], [lang]);
}
