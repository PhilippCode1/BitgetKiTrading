"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type SignalDetailLlmChartContextValue = Readonly<{
  annotationsRaw: unknown | null;
  setAnnotationsRaw: (v: unknown | null) => void;
  /** strategy_explanation_de o. a. — Zonenrollen (Short/Widerstand) + Popover-Text. */
  rationaleDe: string | null;
  setRationaleDe: (v: string | null) => void;
  layerEnabled: boolean;
  setLayerEnabled: (v: boolean) => void;
}>;

const SignalDetailLlmChartContext =
  createContext<SignalDetailLlmChartContextValue | null>(null);

export function SignalDetailLlmChartProvider({
  children,
}: Readonly<{ children: ReactNode }>) {
  const [annotationsRaw, setAnnotationsRawState] = useState<unknown | null>(
    null,
  );
  const [layerEnabled, setLayerEnabledState] = useState(true);
  const [rationaleDe, setRationaleDeState] = useState<string | null>(null);

  const setAnnotationsRaw = useCallback((v: unknown | null) => {
    setAnnotationsRawState(v);
  }, []);

  const setRationaleDe = useCallback((v: string | null) => {
    setRationaleDeState(v);
  }, []);

  const setLayerEnabled = useCallback((v: boolean) => {
    setLayerEnabledState(v);
  }, []);

  const value = useMemo(
    () =>
      ({
        annotationsRaw,
        setAnnotationsRaw,
        rationaleDe,
        setRationaleDe,
        layerEnabled,
        setLayerEnabled,
      }) satisfies SignalDetailLlmChartContextValue,
    [
      annotationsRaw,
      rationaleDe,
      layerEnabled,
      setAnnotationsRaw,
      setRationaleDe,
      setLayerEnabled,
    ],
  );

  return (
    <SignalDetailLlmChartContext.Provider value={value}>
      {children}
    </SignalDetailLlmChartContext.Provider>
  );
}

export function useSignalDetailLlmChartOptional(): SignalDetailLlmChartContextValue | null {
  return useContext(SignalDetailLlmChartContext);
}
