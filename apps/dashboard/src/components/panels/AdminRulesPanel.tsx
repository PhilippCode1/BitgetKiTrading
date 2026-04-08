"use client";

import { useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { adminRulesSaveConfirmMessage } from "@/lib/sensitive-action-prompts";
import type { AdminRulesResponse } from "@/lib/types";

type Props = Readonly<{
  initial: AdminRulesResponse;
}>;

export function AdminRulesPanel({ initial }: Props) {
  const { t } = useI18n();
  const [jsonText, setJsonText] = useState(() =>
    JSON.stringify(initial.rule_sets[0]?.rules_json ?? {}, null, 2),
  );
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submitRules() {
    if (
      typeof window !== "undefined" &&
      !window.confirm(adminRulesSaveConfirmMessage())
    ) {
      return;
    }
    setMsg(null);
    setErr(null);
    let rules: Record<string, unknown>;
    try {
      rules = JSON.parse(jsonText) as Record<string, unknown>;
    } catch {
      setErr(t("adminRules.jsonInvalid"));
      return;
    }
    const res = await fetch("/api/dashboard/admin/rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rule_set_id: "default", rules_json: rules }),
    });
    if (!res.ok) {
      setErr(t("adminRules.saveFailed", { status: res.status }));
      return;
    }
    setMsg(t("adminRules.msgSavedProxy"));
  }

  return (
    <div className="panel">
      <h2>{t("adminRules.panelTitle")}</h2>
      <p className="muted">{t("adminRules.intro")}</p>
      <h3>{t("adminRules.envGatewayHeading")}</h3>
      <ul className="news-list">
        {Object.entries(initial.env).map(([k, v]) => (
          <li key={k}>
            <code>{k}</code>: {v ?? "—"}
          </li>
        ))}
      </ul>
      <h3>{t("adminRules.rulesFromDb")}</h3>
      {initial.rule_sets.map((r) => (
        <pre key={r.rule_set_id} className="json-mini">
          {JSON.stringify(r.rules_json, null, 2)}
        </pre>
      ))}
      <h3>{t("adminRules.updateHeadingProxy")}</h3>
      <p className="muted">{t("adminRules.proxyHint")}</p>
      <textarea
        value={jsonText}
        onChange={(e) => setJsonText(e.target.value)}
        rows={12}
        style={{
          width: "100%",
          fontFamily: "monospace",
          fontSize: 12,
          background: "#0d1117",
          color: "#c9d1d9",
          border: "1px solid #30363d",
          borderRadius: 8,
          padding: 8,
        }}
      />
      <div className="btn-row">
        <button type="button" onClick={submitRules}>
          {t("adminRules.saveRulesProxy")}
        </button>
      </div>
      {msg ? <p className="msg-ok">{msg}</p> : null}
      {err ? <p className="msg-err">{err}</p> : null}
    </div>
  );
}
