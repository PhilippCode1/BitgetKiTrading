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

  const setAnnotationsRaw = useCallback((v: unknown | null) => {
    setAnnotationsRawState(v);
  }, []);

  const setLayerEnabled = useCallback((v: boolean) => {
    setLayerEnabledState(v);
  }, []);

  const value = useMemo(
    () =>
      ({
        annotationsRaw,
        setAnnotationsRaw,
        layerEnabled,
        setLayerEnabled,
      }) satisfies SignalDetailLlmChartContextValue,
    [annotationsRaw, layerEnabled, setAnnotationsRaw, setLayerEnabled],
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
