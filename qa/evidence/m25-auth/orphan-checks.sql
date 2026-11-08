select
    (
        select count(*)
        from question_attempts qa
        left join practice_sessions ps on ps.id=qa.session_id
        where ps.id is null
    ) as orphan_attempts,
    (
        select count(*)
        from mistake_items mi
        left join question_banks qb on qb.id=mi.bank_id
        where qb.id is null
    ) as orphan_mistake_banks,
    (
        select count(*)
        from mistake_items mi
        left join passages p
          on p.bank_id=mi.bank_id
         and p.passage_group_id=mi.passage_id
        where p.id is null
    ) as orphan_mistake_passages,
    (
        select count(*)
        from question_attempts qa
        left join questions q
          on q.bank_id=qa.bank_id
         and q.id=qa.question_id
        where q.id is null
    ) as orphan_attempt_questions;
