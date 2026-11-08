select
    (
        select count(*)
        from practice_sessions ps
        left join question_banks qb on qb.id=ps.bank_id
        where qb.id is null
    ) as orphan_sessions,
    (
        select count(*)
        from practice_reports pr
        left join question_banks qb on qb.id=pr.bank_id
        where qb.id is null
    ) as orphan_reports;
