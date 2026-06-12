"use client";

/**
 * B057 F005 — the selected strategy mode, shared across the workbench surfaces.
 *
 * The B057 platform has multiple strategy modes (Master flagship + regime
 * research mode + future modes). The recommendations + execution surfaces each
 * read/write the SELECTED mode's own target / account / diff / tickets / journal
 * by passing ``?strategy_id=`` to the API (the backend defaults to Master, so an
 * unset mode is the existing single-account behaviour).
 *
 * The selection lives in a small context (localStorage-backed) so switching the
 * mode on one surface persists to the others without threading it through every
 * route. Default = ``master_portfolio`` (the funded flagship the user trades).
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export const DEFAULT_STRATEGY_ID = "master_portfolio";
const STORAGE_KEY = "workbench.strategyMode";

interface StrategyModeContextValue {
  strategyId: string;
  setStrategyId: (id: string) => void;
}

const StrategyModeContext = createContext<StrategyModeContextValue>({
  strategyId: DEFAULT_STRATEGY_ID,
  setStrategyId: () => {},
});

export function StrategyModeProvider({ children }: { children: React.ReactNode }) {
  const [strategyId, setStrategyIdState] = useState<string>(DEFAULT_STRATEGY_ID);

  // Hydrate from localStorage after mount (SSR-safe — the server renders the
  // default, the client adopts the persisted choice on first paint).
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) setStrategyIdState(stored);
    } catch {
      // localStorage unavailable (private mode / SSR) → keep the default.
    }
  }, []);

  const setStrategyId = useCallback((id: string) => {
    setStrategyIdState(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // Non-fatal: the choice still applies for this session.
    }
  }, []);

  const value = useMemo(() => ({ strategyId, setStrategyId }), [strategyId, setStrategyId]);
  return <StrategyModeContext.Provider value={value}>{children}</StrategyModeContext.Provider>;
}

export function useStrategyMode(): StrategyModeContextValue {
  return useContext(StrategyModeContext);
}
