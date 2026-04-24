"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { DashboardPersona } from "@/lib/operator-jwt";

const CustomerPortalContext = createContext<{
  persona: DashboardPersona;
} | null>(null);

type ProviderProps = Readonly<{
  children: ReactNode;
  /** Aus Server-Layout: valides `bitget_portal_jwt` (role/portal_roles). */
  persona: DashboardPersona;
}>;

/**
 * Kunden-Route-Group: Persona (customer vs. unknown) fuer Client-Komponenten
 * — getrennt von BFF-Operator-Session (DASHBOARD_GATEWAY_AUTHORIZATION).
 */
export function CustomerPortalProvider({ persona, children }: ProviderProps) {
  return (
    <CustomerPortalContext.Provider value={{ persona }}>
      {children}
    </CustomerPortalContext.Provider>
  );
}

export function useCustomerPortalPersona(): DashboardPersona {
  const v = useContext(CustomerPortalContext);
  return v?.persona ?? "unknown";
}
