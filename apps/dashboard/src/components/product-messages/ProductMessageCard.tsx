import { Suspense, type ReactNode } from "react";

import type { TranslateFn } from "@/lib/user-facing-fetch-error";
import type { ProductMessage } from "@/lib/product-messages/schema";

import { ProductMessageActionBar } from "./ProductMessageActionBar";
import { ProductMessageSituationExplainSlot } from "./ProductMessageSituationExplainSlot";

type Props = Readonly<{
  message: ProductMessage;
  /** Technische Klappe (Rohdaten) — typisch ?diagnostic=1 */
  showTechnical: boolean;
  t: TranslateFn;
  /** Standard: Aktionsleiste einblenden */
  showActions?: boolean;
  /** Zusätzliche Erklärblöcke (deterministisch + optional KI) ab Schwere „Hinweis“ */
  situationExplain?: boolean;
  className?: string;
  children?: ReactNode;
}>;

function sectionRow(
  label: string,
  body: string,
  key: string,
): ReactNode {
  const b = body.trim();
  if (!b) return null;
  return (
    <div className="product-message-card__section" key={key}>
      <div className="product-message-card__label">{label}</div>
      <div className="product-message-card__value">{b}</div>
    </div>
  );
}

/**
 * Einheitliche, ruhige Fehler- und Statuskommunikation mit Dringlichkeit und Klappe für Technik.
 */
export function ProductMessageCard({
  message,
  showTechnical,
  t,
  showActions = true,
  situationExplain = true,
  className = "",
  children,
}: Props) {
  const rootClass = [
    "product-message-card",
    `product-message-card--${message.severity}`,
    className.trim(),
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <article
      className={rootClass}
      role="status"
      data-product-message-id={message.id}
      data-severity={message.severity}
      data-dedupe-key={message.dedupeKey}
    >
      <header className="product-message-card__header">
        <span
          className="product-message-card__severity"
          data-severity={message.severity}
        >
          {t(`productMessage.severity.${message.severity}`)}
        </span>
        <span className="product-message-card__area">{message.areaLabel}</span>
      </header>
      <h3 className="product-message-card__headline">{message.headline}</h3>
      <div className="product-message-card__sections">
        {sectionRow(
          t("productMessage.section.summary"),
          message.summary,
          "summary",
        )}
        {sectionRow(
          t("productMessage.section.impact"),
          message.impact,
          "impact",
        )}
        {sectionRow(
          t("productMessage.section.urgency"),
          message.urgency,
          "urgency",
        )}
        {sectionRow(
          t("productMessage.section.appDoing"),
          message.appDoing,
          "app",
        )}
        {sectionRow(
          t("productMessage.section.userAction"),
          message.userAction,
          "user",
        )}
      </div>
      <ProductMessageSituationExplainSlot
        message={message}
        enabled={situationExplain}
      />
      {children}
      {showActions ? (
        <Suspense fallback={null}>
          <ProductMessageActionBar />
        </Suspense>
      ) : null}
      {showTechnical && message.technicalDetail.trim() ? (
        <details className="product-message-card__technical">
          <summary>{t("productMessage.section.technical")}</summary>
          <pre className="product-message-card__pre">
            {message.technicalDetail}
          </pre>
        </details>
      ) : null}
    </article>
  );
}
