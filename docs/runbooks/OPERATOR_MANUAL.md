# Operator Manual (Live-Trading & Notfälle)

Dieses Runbook beschreibt die Aufgaben und Handlungsanweisungen für Operatoren im BitgetKiTrading-System. Das Frontend-Dashboard (`/console`) ist das primäre Werkzeug für die Überwachung und Intervention.

## 1. Die Operator Konsole (Frontend)

Die Console (`/console`) trennt strikt zwischen Customer-Portal und Admin-Rechten. Als Operator hast du Zugriff auf:
- **Live Terminal (`/console/live`)**: Zeigt den Echtzeit-Datenstrom an (Chart, Orderbuch-Lineage, News). Achte auf die "Freshness"-Pillen. Wenn das System `STREAM_GAP_EVENT` oder `stale` meldet, hat das Netzwerklatenz-Probleme und die SSE-Verbindung (Server-Sent Events) baut sich automatisch neu auf.
- **Signals & Explainability (`/console/signals`)**: Hierarchische Ansicht aller Signale. Du kannst den deterministischen Ablauf (Warum hat das Ensemble eine Order blockiert? Welches Anti-Pattern wurde ausgelöst?) über die `SituationAiExplainPanel` und `SignalDetailStoredExplainSection` einsehen.

## 2. Execution Safety Panel & Notfallsteuerung

Das `ExecutionSafetyPanel` (in `/console/safety`) ist das wichtigste Werkzeug bei drohenden Verlusten, Exchange-Wartungen oder fehlerhaften Modellen. 

**WICHTIG: Jede Aktion hier bedarf einer Checkbox-Bestätigung!**

| Aktion | Funktion & Konsequenz |
|---|---|
| **Kill Switch Arm** | Löst ein Hard-Halt-Event im Redis-Cache aus (`latch:global_halt`). Alle Services stoppen *sofort* das Senden neuer Orders. Stornierungen (Cancels) bleiben erlaubt, um das Risiko zu reduzieren. |
| **Kill Switch Release** | Hebt den globalen Notstopp wieder auf. Muss explizit freigegeben werden, nachdem die Gefahr gebannt ist. |
| **Safety Latch Release** | Bestimmte Module (z.B. der Risk-Adapter bei extremer Volatilität) können einen Soft-Latch auslösen. Hiermit kann dieser nach Prüfung durch den Operator resettet werden. |
| **Cancel All** | Storniert kontrolliert alle noch offenen passiven Limit- und Stop-Orders. Positionen bleiben bestehen, aber es fließt kein neues Kapital ab. |
| **Emergency Flatten** | Sendet Reduce-Only Market-Orders an die Börse, um sämtliche Long- und Short-Positionen sofort zu schließen. **Nur im extremen Notfall (z.B. Flash-Crash ohne funktionierende Stop-Losses) verwenden!** |

## 3. Self-Healing Hub & Alerting

Der `SelfHealingHubClient` (`/console/self-healing`) visualisiert den Systemzustand auf einen Blick.
- Das System versucht, hängende Worker-Prozesse (z.B. in der `signal-engine`) über Kubernetes/Docker API selbständig neuzustarten.
- Alle Incidents werden protokolliert. Ist ein Incident mit `severity: blocking` markiert, erfordert dies sofortige manuelle Intervention.
- Wenn das UI anbietet, einen "Full Recheck" oder "Restart Worker" auszuführen, können diese Aktionen über die Console initiiert werden.
- Kritische Systemausfälle (z.B. P0 Live-Broker Offline, Postgres Connection Refused) werden über die Prometheus Alertmanager Routen (definiert in `prometheus-alerts.yml`) auch per Webhook/Slack direkt an das Operations-Team gefunkt.
