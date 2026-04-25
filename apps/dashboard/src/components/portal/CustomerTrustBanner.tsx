import { getServerTranslator } from "@/lib/i18n/server-translate";

/**
 * Statische, einheitliche Sicherheits- und Rechts-Informationen (keine Live-Secrets).
 */
export async function CustomerTrustBanner() {
  const t = await getServerTranslator();
  return (
    <section
      className="panel"
      data-e2e="customer-trust-banner"
      style={{
        background: "var(--color-bg-elevated, #1a1d24)",
        border: "1px solid var(--color-border-subtle, #2d3139)",
        marginBottom: 20,
      }}
    >
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>{t("customerPortal.safety.title")}</h2>
      <ul className="muted" style={{ margin: 0, paddingLeft: "1.25rem", lineHeight: 1.6 }}>
        <li>{t("customerPortal.safety.liveGated")}</li>
        <li>{t("customerPortal.safety.keysNeverInBrowser")}</li>
        <li>{t("customerPortal.safety.modesShadowPaperLive")}</li>
      </ul>
    </section>
  );
}
