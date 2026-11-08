BEGIN;

UPDATE question_banks
SET name='Demo Bank（30题·旧版演示）',
    status='archived',
    coverage_snapshot=COALESCE(coverage_snapshot, '{}'::jsonb)
        || '{"switchable": false, "purpose": "legacy_demo_30"}'::jsonb,
    finished_at=COALESCE(finished_at, now())
WHERE id='00000000-0000-4000-8000-000000000001';

UPDATE question_banks
SET name='Demo Bank（80题·归档）'
WHERE id='00000000-0000-4000-8000-000000000002';

COMMIT;
