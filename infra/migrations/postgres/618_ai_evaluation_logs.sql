-- Prompt 20: Operator-Explain / Produktions-Ausrichtung — Audit-Tabelle fuer KI-Bewertungen

CREATE TABLE IF NOT EXISTS public.ai_evaluation_logs (
    log_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id uuid NULL,
    task_type text NOT NULL DEFAULT 'operator_explain',
    orchestrator_status text NULL,
    response_ok boolean NOT NULL,
    provider text NULL,
    model text NULL,
    response_json jsonb NOT NULL,
    ai_warned boolean NOT NULL,
    request_trace_id text NULL,
    request_correlation_id text NULL,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_evaluation_logs_execution_created
    ON public.ai_evaluation_logs (execution_id, created_ts DESC)
    WHERE execution_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ai_evaluation_logs_created
    ON public.ai_evaluation_logs (created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_ai_evaluation_logs_task_created
    ON public.ai_evaluation_logs (task_type, created_ts DESC);

COMMENT ON TABLE public.ai_evaluation_logs IS
    'Quality-Feedback-Trace: LLM-Operator-Explain (und spaetere Task-Typen) mit optionaler execution_id (live.execution_decisions).';
COMMENT ON COLUMN public.ai_evaluation_logs.ai_warned IS
    'Heuristik auf explanation_de (Risiko/Warnung) — Abgleich mit P&L im Diagnose-Skript.';
