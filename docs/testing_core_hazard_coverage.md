# Testabdeckung: Kern-Gefahrenklassen

Kurzüberblick, welche Risikotypen die ergänzten Unit-Tests adressieren (ohne Ersatz für Integration/E2E).

| Gefahrenklasse                      | Beispiele                                                                           | Tests (Auszug)                                                                                                                                                       |
| ----------------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Numerische Grenzwerte               | Margin-Limit strikt `>`; Hebel-Caps; ungültige Kalibrierungs-/Hebel-Felder          | `test_risk_governor` (Margin am Limit / epsilon darüber), `test_leverage_allocator` (leere Caps, negativer Cap→0), `test_model_contracts` (Kalibrierung, Hebel 7–75) |
| Inkonsistente / feindliche Eingaben | Modell-Output mit ungültiger Kalibrierung und Hebel außerhalb Kontrakt              | `test_normalize_model_output_flags_invalid_calibration_and_leverage_range`                                                                                           |
| Null- / Leerzustände                | Flat-Position: kein Close trotz Stop-Touch                                          | `test_evaluate_exit_plan_zero_qty_no_close_despite_stop_hit`                                                                                                         |
| Restart / Cold-Start                | Live-Reconcile mit leerem Journal (fehlende Exchange-Snapshots)                     | `test_reconcile_empty_journal_live_mode_degraded_missing_snapshots_no_latch`                                                                                         |
| Safety-Blockaden                    | Safety-Latch vs. normale Orders; Kill-Switch-Idempotenz; Release ohne aktiven Latch | `test_private_rest_client` (Latch, `arm`/`release` idempotent)                                                                                                       |
| Konfigurations-Invarianten          | Drawdown-Hierarchie daily ≤ weekly ≤ account                                        | `test_drawdown_limit_chain_rejects_inverted_hierarchy`                                                                                                               |

**Hinweis:** Property-/Fuzz-Tests sind bewusst nicht als neue Dependency eingeführt; Grenzfälle sind über parametrisierbare Einzeltests und klare Schwellen abgebildet, damit CI deterministisch bleibt.
