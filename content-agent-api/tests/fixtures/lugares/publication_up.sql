-- Prepared release prerequisite, NEVER automatically applied by the API/importer.
-- B1 forbids every cc_lugares publication, including approved revisions.
-- Replace the blanket lock and allow approved draft -> published.
-- Submitted text, review decisions, identities and all geometry remain immutable.
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '60s';
LOCK TABLE design.content_items IN ACCESS EXCLUSIVE MODE;
CREATE FUNCTION design.cc_lugares_publication_evidence_valid(meta jsonb, sources jsonb)
RETURNS boolean LANGUAGE sql IMMUTABLE SET search_path = pg_catalog, design AS $function$
  SELECT (
    COALESCE(meta #>> '{a3_record,editorial_review,outcome}', '') <> 'blocked'
    AND COALESCE(meta #> '{a3_record,verification,notes}', 'null'::jsonb) = '[]'::jsonb
    AND COALESCE(meta->'review_exceptions', '[]'::jsonb) = '[]'::jsonb
    AND jsonb_typeof(sources) = 'array' AND jsonb_array_length(sources) > 0
    AND NOT EXISTS (
      SELECT FROM jsonb_array_elements(sources) s
      WHERE s->>'http_status' IS DISTINCT FROM '200'
        OR s->'error' IS DISTINCT FROM 'null'::jsonb
        OR s->>'checked_at' IS NULL
        OR s->>'evidence_scope' = 'historical_snapshot_only_current_url_failed'
    )
  ) IS TRUE
$function$;
ALTER TABLE design.content_items
  DROP CONSTRAINT cc_lugares_unpublished,
  ADD CONSTRAINT cc_lugares_publication_guard CHECK (
    module <> 'cc_lugares' OR publication_status = 'draft' OR (
      publication_status = 'published' AND cc_review_status = 'approved'
      AND cc_verification_status = 'verified' AND cc_style_approved IS TRUE
      AND length(btrim(cc_reviewed_by)) > 0 AND cc_reviewed_at IS NOT NULL
      AND body IS NOT NULL AND btrim(body) <> ''
      AND design.cc_lugares_publication_evidence_valid(metadata, cc_sources)
    )
  );
COMMENT ON CONSTRAINT cc_lugares_publication_guard ON design.content_items IS
  'Publication is a separate authorized write; imports remain drafts. Blocked evidence cannot be published. B1 revision immutability remains enforced.';
CREATE OR REPLACE FUNCTION design.cc_lugares_revision_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, design AS $function$
DECLARE
  state text; merged_into uuid;
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.module = 'cc_lugares' THEN
    IF OLD.cc_review_status <> 'draft' AND (
      to_jsonb(NEW) - ARRAY['updated_at', 'publication_status', 'cc_review_status', 'cc_reviewed_by',
        'cc_reviewed_at', 'cc_style_approved']
      IS DISTINCT FROM
      to_jsonb(OLD) - ARRAY['updated_at', 'publication_status', 'cc_review_status', 'cc_reviewed_by',
        'cc_reviewed_at', 'cc_style_approved']
    ) THEN RAISE EXCEPTION 'Submitted text is immutable; insert a new revision'; END IF;
    IF NEW.publication_status IS DISTINCT FROM OLD.publication_status AND NOT (
      OLD.publication_status = 'draft' AND NEW.publication_status = 'published'
      AND NEW.cc_review_status = 'approved'
    ) THEN RAISE EXCEPTION 'Only approved draft to published is permitted'; END IF;
    IF OLD.cc_review_status IN ('approved', 'rejected') AND (
      ROW(NEW.cc_review_status, NEW.cc_reviewed_by, NEW.cc_reviewed_at, NEW.cc_style_approved)
      IS DISTINCT FROM
      ROW(OLD.cc_review_status, OLD.cc_reviewed_by, OLD.cc_reviewed_at, OLD.cc_style_approved)
    ) THEN RAISE EXCEPTION 'Review decision is immutable; insert a new revision'; END IF;
    IF OLD.cc_review_status = 'pending_review' AND NEW.cc_review_status = 'draft' THEN
      RAISE EXCEPTION 'Submitted text cannot return to draft; insert a new revision';
    END IF;
  END IF;
  IF NEW.module = 'cc_lugares' THEN
    -- Explicit aliases from A2.2 / frontend 01f9e4e; never infer by name.
    IF NEW.entity_id = ANY (ARRAY[
      'b4498814-e6a1-5ef5-82d3-a332efc28cf1',
      '14c3aaf2-c1a3-5e0f-a17c-30fefdba64eb',
      '92b7e86b-dfb5-5248-bc12-454957b73802',
      '8a233434-d330-5929-9942-5e6a4e02adb5',
      'ed877996-98ec-5a22-80f7-7cbfa465ca5b',
      'c848c50c-58bb-5cba-8fcb-e1335c35366b',
      'ea635ef2-4917-5dc4-b93f-c27777fc8a92',
      '10eb6a1a-8419-570f-8c91-d90b3e8e690b',
      '13889400-929f-5dfe-ba41-76b07e0b6a6c',
      'b67200ad-9bde-5083-adfc-657ac922ce10',
      'ee5b70e5-8c45-58f5-8935-ed7a145c3c0a',
      '14f49575-f9a8-5f54-9cdc-46f0f4f4e7fb',
      '7b220930-d693-52e2-81e6-5afa56d77b6e',
      'e526a766-86ae-5991-b257-da31a5775cc8',
      '8266d91a-04ad-5db2-bd3c-d3f74005e0a1',
      'b5c441ea-d903-5b50-b83d-ea567f62e4ee',
      'ac058770-3348-55a1-be4c-0c7bc6fc26a9',
      'e16bb7ed-fc5a-5e72-bf25-7546c1eb6443',
      '7801ef63-bf3a-5231-a050-159f8c8fe21d',
      'bd4e017a-7e4c-51e8-b0ce-58584e7fb3ff',
      '0b02a4bc-d05c-5ffe-a5b9-ee6a06ee0592',
      'f9a04da2-df0b-50a2-8e28-b88a9718ed54',
      '83f543ac-8b6f-518a-ab7b-1bf123caf599',
      'cae309a9-c59d-5d49-b3fc-561967c46f6e'
    ]::uuid[]) THEN
      RAISE EXCEPTION 'Known A2.2 alias; resolve canonical_id explicitly before import';
    END IF;
    SELECT e.lifecycle_status, e.merged_into_entity_id INTO state, merged_into
      FROM design.entities e WHERE e.id = NEW.entity_id FOR SHARE;
    IF FOUND AND (state = 'merged' OR merged_into IS NOT NULL) THEN
      RAISE EXCEPTION 'Merged identity cannot receive a Lugares revision';
    END IF;
    -- A missing identity is rejected by the existing FK, never created here.
  END IF;
  RETURN NEW;
END $function$;

COMMIT;
