\pset pager off

-- 1. Confirm the database instance and current active bank.
select
    inet_server_port() as server_port,
    current_database() as database_name,
    (select count(*) from practice_sessions) as session_count;

select
    b.id,
    b.name,
    count(q.id) filter (where q.status='published') as published_questions
from question_banks b
join bank_active_state s
  on s.active_bank_id=b.id
 and s.singleton=TRUE
left join questions q
  on q.bank_id=b.id
group by b.id, b.name;

-- 2. Inspect the stored passage; the numbered blanks contain answer words.
select passage_group_id, type, content
from passages
where bank_id=(select active_bank_id from bank_active_state where singleton)
  and passage_group_id='M2-FULL-CLOZE-04';

-- 3. Compare each cloze answer with the word stored immediately after its marker.
with target_questions as (
    select
        id,
        answer#>>'{}' as answer_text,
        substring(id from '([0-9]+)$')::integer as question_no
    from questions
    where bank_id=(select active_bank_id from bank_active_state where singleton)
      and passage_group_id='M2-FULL-CLOZE-04'
    order by id
)
select
    q.id,
    q.answer_text,
    (
        regexp_match(
            p.content,
            '\(' || q.question_no || '\)\s*([^[:space:],.;:!?()]+)'
        )
    )[1] as stored_slot_token
from target_questions q
join passages p
  on p.bank_id=(select active_bank_id from bank_active_state where singleton)
 and p.passage_group_id='M2-FULL-CLOZE-04'
order by q.id;
