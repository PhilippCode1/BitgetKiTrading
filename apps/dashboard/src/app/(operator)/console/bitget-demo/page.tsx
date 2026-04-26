import { Header } from "@/components/layout/Header";
import { fetchDemoAssets, fetchDemoReadiness, fetchDemoStatus } from "@/lib/api";

export const dynamic = "force-dynamic";

function asBool(value: unknown): boolean {
  return Boolean(value);
}

export default async function BitgetDemoPage() {
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
        title="Bitget Demo"
        subtitle="Bitget Demo-Modus aktiv - Demogeld, kein Echtgeld."
      />
      <section className="panel">
        <h2>Modusstatus</h2>
        <p>
          Echtes Live-Trading: <strong>{asBool(mode.live_trade_enable) ? "AN (blockiert)" : "AUS"}</strong>
        </p>
        <p>
          Demo-Trading: <strong>{asBool(mode.bitget_demo_enabled) ? "AKTIV" : "NICHT AKTIV"}</strong>
        </p>
        <p>
          Readiness: <strong>{String(readiness.result ?? "unbekannt")}</strong>
        </p>
      </section>
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Demo-Asset-Status</h2>
        {rows.length === 0 ? (
          <p className="muted small">Keine Demo-Assets verfügbar oder Endpoint liefert noch keine Daten.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Market Family</th>
                  <th>Product Type</th>
                  <th>Status</th>
                  <th>Demo handelbar</th>
                  <th>Live blockiert</th>
                  <th>Block-Grund</th>
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
                      <td>{asBool(item.demo_handelbar) ? "Ja" : "Nein"}</td>
                      <td>{asBool(item.live_blockiert) ? "Ja" : "Nein"}</td>
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
