# Stop-Budget und Ausführbarkeit

- Hebel-indexierte Stop-Budget-Kurve: höherer Hebel → engere initiale Stop-Distanz (Zielkorridor ab ca. 7×).
- Wenn Ticksize, Spread, Orderbuch, Volatilität oder Liquidationspuffer die Distanz unhaltbar machen: Hebel senken oder `no_trade` — keine „optisch engen“ Stops ohne Mechanik-Check.
- Quantitative Bewertung erfolgt in der Signal-Engine / Stop-Budget-Policy, nicht durch den LLM-Text.
