import { Header } from "@/components/layout/Header";
import {
  fetchDemoAssets,
  fetchDemoReadiness,
  fetchDemoStatus,
} from "@/lib/api";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

function asBool(value: unknown): boolean {
  return Boolean(value);
}

export default async function BitgetDemoPage() {
  const t = await getServerTranslator();
  const [status, readiness, assets] = await Promise.all([
    fetchDemoStatus().catch((): Record<string, unknown> => ({})),
    fetchDemoReadiness().catch((): Record<string, unknown> => ({})),
    fetchDemoAssets().catch((): Record<string, unknown> => ({})),
  ]);

  const mode = (status["demo_mode"] ?? {}) as Record<string, unknown>;
  const rows = Array.isArray(assets.items) ? assets.items : [];

  return (
    <>
      <Header
        title={t("console.bitgetDemoPage.title")}
        subtitle={t("console.bitgetDemoPage.subtitle")}
      />
      <section className="panel">
        <h2>{t("console.bitgetDemoPage.modeTitle")}</h2>
        <p>
          {t("console.bitgetDemoPage.liveTrading")}:{" "}
          <strong>
            {asBool(mode.live_trade_enable)
              ? t("console.bitgetDemoPage.onBlocked")
              : t("console.bitgetDemoPage.off")}
          </strong>
        </p>
        <p>
          {t("console.bitgetDemoPage.demoTrading")}:{" "}
          <strong>
            {asBool(mode.bitget_demo_enabled)
              ? t("console.bitgetDemoPage.active")
              : t("console.bitgetDemoPage.notActive")}
          </strong>
        </p>
        <p>
          {t("console.bitgetDemoPage.readiness")}:{" "}
          <strong>
            {String(readiness.result ?? t("console.bitgetDemoPage.unknown"))}
          </strong>
        </p>
      </section>
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>{t("console.bitgetDemoPage.assetsTitle")}</h2>
        {rows.length === 0 ? (
          <p className="muted small">{t("console.bitgetDemoPage.assetsEmpty")}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("console.bitgetDemoPage.colSymbol")}</th>
                  <th>{t("console.bitgetDemoPage.colMarketFamily")}</th>
                  <th>{t("console.bitgetDemoPage.colProductType")}</th>
                  <th>{t("console.bitgetDemoPage.colStatus")}</th>
                  <th>{t("console.bitgetDemoPage.colDemoTradable")}</th>
                  <th>{t("console.bitgetDemoPage.colLiveBlocked")}</th>
                  <th>{t("console.bitgetDemoPage.colBlockReason")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => {
                  const item = row as Record<string, unknown>;
                  return (
                    <tr key={`${String(item.symbol ?? "asset")}-${idx}`}>
                      <td>{String(item.symbol ?? "-")}</td>
                      <td>{String(item.market_family ?? "-")}</td>
                      <td>{String(item.product_type ?? "-")}</td>
                      <td>{String(item.status ?? "-")}</td>
                      <td>
                        {asBool(item.demo_handelbar)
                          ? t("console.bitgetDemoPage.yes")
                          : t("console.bitgetDemoPage.no")}
                      </td>
                      <td>
                        {asBool(item.live_blockiert)
                          ? t("console.bitgetDemoPage.yes")
                          : t("console.bitgetDemoPage.no")}
                      </td>
                      <td>{String(item.block_grund_de ?? "")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
