import { ExplainMarkdown } from "@/components/panels/ExplainMarkdown";
import { ContentPanel } from "@/components/ui/ContentPanel";
import { summarizeReasonsJsonForUi } from "@/lib/signal-explain-display";
import type { SignalExplainResponse } from "@/lib/types";

type Translate = (
  key: string,
  vars?: Record<string, string | number>,
) => string;

type Props = Readonly<{
  explain: SignalExplainResponse | null;
  contractVersion: string | undefined;
  t: Translate;
}>;

/**
 * Gespeicherte Erklärung (Explain-API) — ohne Roh-json; Rohdaten nur im Technik-Block.
 */
export function SignalDetailStoredExplainSection({
  explain,
  contractVersion,
  t,
}: Props) {
  return (
    <ContentPanel className="signal-detail-stored-explain">
      <h2 className="h3-quiet">
        {t("pages.signalsDetail.sectionStoredTitle")}
      </h2>
      <p className="muted small">
        {t("pages.signalsDetail.sectionStoredLead")}
      </p>
      {!explain ? (
        <div role="status">
          <h3 className="h3-quiet">
            {t("pages.signalsDetail.explainUnavailableTitle")}
          </h3>
          <p className="muted small">
            {t("pages.signalsDetail.explainUnavailableBody")}
          </p>
        </div>
      ) : (
        <>
          <section className="signal-detail-stored-explain__block">
            <div className="signal-explain-layer__head">
              <h3 className="h3-quiet">
                {t("pages.signalsDetail.explainLayer1Title")}
              </h3>
              <span className="status-pill status-ok">
                {t("pages.signalsDetail.badgeStoredDb")}
              </span>
            </div>
            <p className="muted small">
              {t("pages.signalsDetail.explainLayer1Lead")}
            </p>
            <p className="signal-explain-prose">
              {explain.explain_short?.trim()
                ? explain.explain_short
                : t("pages.signalsDetail.explainShortEmpty")}
            </p>
          </section>
          <section className="signal-detail-stored-explain__block">
            <div className="signal-explain-layer__head">
              <h3 className="h3-quiet">
                {t("pages.signalsDetail.explainLayer2Title")}
              </h3>
              <span className="status-pill status-ok">
                {t("pages.signalsDetail.badgeStoredDb")}
              </span>
            </div>
            <p className="muted small">
              {t("pages.signalsDetail.explainLayer2Lead")}
            </p>
            {explain.explanation_layers?.persisted_narrative != null ? (
              <p className="muted small">
                <strong>
                  {t("pages.signalsDetail.persistedNarrativeNoteLabel")}:
                </strong>{" "}
                {String(
                  (
                    explain.explanation_layers.persisted_narrative as {
                      note_de?: string;
                    }
                  )?.note_de ?? "",
                )}
              </p>
            ) : null}
            <h4 className="h3-quiet signal-detail-stored-explain__md-head">
              {t("pages.signalsDetail.explainMarkdownHeading")}
            </h4>
            {explain.explain_long_md?.trim() ? (
              <ExplainMarkdown markdown={explain.explain_long_md} />
            ) : (
              <p className="muted small">
                {t("pages.signalsDetail.explainLongEmpty")}
              </p>
            )}
          </section>
          <section className="signal-detail-stored-explain__block">
            <div className="signal-explain-layer__head">
              <h3 className="h3-quiet">
                {t("pages.signalsDetail.explainLayer3Title")}
              </h3>
              <span className="status-pill status-warn">
                {t("pages.signalsDetail.badgeEngineAudit")}
              </span>
            </div>
            <p className="muted small">
              {t("pages.signalsDetail.explainLayer3LeadHuman")}
            </p>
            <ul className="news-list">
              {summarizeReasonsJsonForUi(explain.reasons_json).map(
                (line, i) => (
                  <li key={`rsn-${i}-${line.slice(0, 48)}`}>{line}</li>
                ),
              )}
            </ul>
            <p className="muted small">
              {t("pages.signalsDetail.explainLayer3RawHint")}
            </p>
          </section>
          {explain.explanation_layers ? (
            <section className="signal-detail-stored-explain__layers-meta muted small">
              <h4 className="h3-quiet">
                {t("pages.signalsDetail.explanationLayersTitle")}
              </h4>
              <p>{t("pages.signalsDetail.explanationLayersLead")}</p>
              <ul className="news-list">
                <li>
                  <strong>
                    {t("pages.signalsDetail.explanationLayerPersisted")}:
                  </strong>{" "}
                  {String(
                    (
                      explain.explanation_layers.persisted_narrative as {
                        note_de?: string;
                      }
                    )?.note_de ?? "—",
                  )}
                </li>
                <li>
                  <strong>
                    {t("pages.signalsDetail.explanationLayerEngine")}:
                  </strong>{" "}
                  {String(
                    (
                      explain.explanation_layers.deterministic_engine as {
                        note_de?: string;
                      }
                    )?.note_de ?? "—",
                  )}
                </li>
                <li>
                  <strong>
                    {t("pages.signalsDetail.explanationLayerLlm")}:
                  </strong>{" "}
                  {String(
                    (
                      explain.explanation_layers.live_llm_advisory as {
                        note_de?: string;
                      }
                    )?.note_de ?? "—",
                  )}
                </li>
              </ul>
              <p>
                {t("pages.signalsDetail.explanationLayersContractHint", {
                  version:
                    contractVersion ?? explain.signal_contract_version ?? "—",
                })}
              </p>
            </section>
          ) : null}
        </>
      )}
    </ContentPanel>
  );
}
