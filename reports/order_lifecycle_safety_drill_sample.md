# Order-Lifecycle-Safety-Drill

## successful submit
- state: exchange_acknowledged
- reasons: ['keine']

## timeout unknown submit state
- state: unknown_submit_state
- reasons: ['submit_timeout_unknown_state']

## duplicate retry attempt
- state: blocked
- reasons: ['duplicate_client_order_id']

## reduce-only exit
- reasons: ['Exit-Safety OK.']

## emergency flatten simulation
- reasons: ['Exit-Menge ueberschreitet die Position.', 'Emergency-Flatten wuerde neue Position eroeffnen.']

## cancel/replace safety
- duplicate order id in cancel/replace -> block (simuliert)
