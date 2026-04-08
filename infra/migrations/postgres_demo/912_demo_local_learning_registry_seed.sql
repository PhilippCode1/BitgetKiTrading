-- Demo-Seed (nur optionaler Demo-Pfad): Model Registry V2 + Strategie fuer leere lokale Panels.
-- Idempotent: nur wenn Zieltabellen keine Zeilen haben bzw. ON CONFLICT greift.

DO $$
DECLARE
    strat_id uuid := '11111111-1111-4111-8111-111111111101'::uuid;
    run_ttp uuid := '22222222-2222-4222-8222-222222222201'::uuid;
    run_mrc uuid := '22222222-2222-4222-8222-222222222202'::uuid;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM learn.strategies LIMIT 1) THEN
        INSERT INTO learn.strategies (strategy_id, name, description, scope_json)
        VALUES (
            strat_id,
            'demo_local_seed',
            'Automatischer Demo-Eintrag (Demo-Migration 912), wenn keine Strategie existiert.',
            '{"seed": true}'::jsonb
        );
        INSERT INTO learn.strategy_status (strategy_id, current_status)
        VALUES (strat_id, 'shadow');
        INSERT INTO learn.strategy_metrics (strategy_id, time_window, metrics_json)
        VALUES (
            strat_id,
            '24h',
            '{"seed": true, "note_de": "Platzhalter bis echte Metriken geschrieben werden."}'::jsonb
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM app.model_registry_v2 LIMIT 1) THEN
        INSERT INTO app.model_runs (
            run_id,
            model_name,
            version,
            dataset_hash,
            promoted_bool,
            calibration_method,
            metadata_json
        )
        VALUES
            (
                run_ttp,
                'take_trade_prob',
                'local-demo-seed',
                'local_demo_dataset_hash',
                true,
                'not_applicable',
                '{"seed": true, "note_de": "Kein echtes Modell — nur UI/Contract-Check."}'::jsonb
            ),
            (
                run_mrc,
                'market_regime_classifier',
                'local-demo-seed',
                'local_demo_dataset_hash',
                true,
                'not_applicable',
                '{"seed": true, "note_de": "Kein echtes Modell — nur UI/Contract-Check."}'::jsonb
            )
        ON CONFLICT (run_id) DO NOTHING;

        INSERT INTO app.model_registry_v2 (
            model_name,
            role,
            run_id,
            calibration_status,
            scope_type,
            scope_key,
            notes
        )
        VALUES
            (
                'take_trade_prob',
                'champion',
                run_ttp,
                'not_applicable',
                'global',
                '',
                'local_demo_seed'
            ),
            (
                'market_regime_classifier',
                'champion',
                run_mrc,
                'not_applicable',
                'global',
                '',
                'local_demo_seed'
            )
        ON CONFLICT (model_name, role, scope_type, scope_key) DO NOTHING;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM learn.recommendations LIMIT 1) THEN
        INSERT INTO learn.recommendations (type, payload_json, status)
        VALUES (
            'promotion',
            '{"seed": true, "note_de": "Platzhalter bis die Learning-Engine Empfehlungen erzeugt."}'::jsonb,
            'new'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM learn.error_patterns LIMIT 1) THEN
        INSERT INTO learn.error_patterns (time_window, pattern_key, count, examples_json)
        VALUES (
            '24h',
            'demo_no_real_errors',
            0,
            '[]'::jsonb
        );
    END IF;
END $$;
