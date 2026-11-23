-- B1: schema only. Manual approval and a staging rehearsal precede production use.
-- Reuse content_items; never update provider text, entities, catalogues or geometry.
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '60s';
LOCK TABLE design.content_items IN ACCESS EXCLUSIVE MODE;
DO $preflight$
BEGIN
  IF EXISTS (SELECT FROM design.content_items WHERE module = 'cc_lugares') THEN
    RAISE EXCEPTION 'B1 namespace already occupied; inspect before migrating';
  END IF;
  IF NOT EXISTS (
    SELECT FROM pg_constraint c
    WHERE c.conrelid = 'design.content_items'::regclass AND c.contype = 'f'
      AND c.confrelid = 'design.entities'::regclass AND c.confdeltype IN ('a', 'r')
      AND c.conkey = ARRAY[(SELECT attnum FROM pg_attribute
        WHERE attrelid = c.conrelid AND attname = 'entity_id')]::smallint[]
      AND c.confkey = ARRAY[(SELECT attnum FROM pg_attribute
        WHERE attrelid = c.confrelid AND attname = 'id')]::smallint[]
  ) THEN RAISE EXCEPTION 'Expected canonical entity FK is missing'; END IF;
END $preflight$;

ALTER TABLE design.content_items
  ADD COLUMN cc_revision integer,
  ADD COLUMN cc_official_url text,
  ADD COLUMN cc_sources jsonb,
  ADD COLUMN cc_review_status text,
  ADD COLUMN cc_verification_status text,
  ADD COLUMN cc_last_verified_at timestamptz,
  ADD COLUMN cc_availability_status text,
  ADD COLUMN cc_style_approved boolean,
  ADD COLUMN cc_reviewed_by text,
  ADD COLUMN cc_reviewed_at timestamptz;

CREATE FUNCTION design.cc_lugares_sources_valid(value jsonb) RETURNS boolean
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $function$
  SELECT jsonb_typeof(value) = 'array' AND NOT EXISTS (
    SELECT FROM jsonb_array_elements(
      CASE WHEN jsonb_typeof(value) = 'array' THEN value ELSE '[]'::jsonb END
    ) AS source
    WHERE (jsonb_typeof(source) = 'object'
      AND jsonb_typeof(source->'url') = 'string'
      AND source->>'url' ~ '^https?://[^[:space:]/?#@]+([/?#][^[:space:]]*)?$') IS NOT TRUE
  );
$function$;

ALTER TABLE design.content_items
  ADD CONSTRAINT cc_lugares_fields CHECK ((CASE WHEN module = 'cc_lugares' THEN
    section = 'descriptions' AND language = 'es' AND entity_id IS NOT NULL
    AND cc_revision > 0
    AND content_key = 'cc_lugares:' || entity_id::text || ':es:r' || cc_revision::text
    AND char_length(short_description) BETWEEN 1 AND 220
    AND short_description = btrim(short_description)
    AND short_description !~ '^[[:space:]]*$'
    AND (body IS NULL OR body !~ '^[[:space:]]*$')
    AND (cc_official_url IS NULL
      OR cc_official_url ~ '^https?://[^[:space:]/?#@]+([/?#][^[:space:]]*)?$')
    AND design.cc_lugares_sources_valid(cc_sources)
    AND cc_review_status IN ('draft', 'pending_review', 'approved', 'rejected')
    AND cc_verification_status IN ('unchecked', 'needs_review', 'verified')
    AND cc_availability_status IN (
      'unknown', 'open', 'temporarily_closed', 'permanently_closed', 'restricted')
    AND cc_style_approved IS NOT NULL
    AND (cc_verification_status <> 'verified'
      OR (cc_last_verified_at IS NOT NULL AND jsonb_array_length(cc_sources) > 0))
    AND (cc_review_status <> 'approved' OR (
      cc_verification_status = 'verified' AND cc_style_approved
      AND length(btrim(cc_reviewed_by)) > 0 AND cc_reviewed_at IS NOT NULL))
  ELSE
    cc_revision IS NULL AND cc_official_url IS NULL AND cc_sources IS NULL
    AND cc_review_status IS NULL AND cc_verification_status IS NULL
    AND cc_last_verified_at IS NULL AND cc_availability_status IS NULL
    AND cc_style_approved IS NULL AND cc_reviewed_by IS NULL AND cc_reviewed_at IS NULL
  END) IS TRUE),
  -- Approval is not publication. A future B3 must explicitly replace this lock.
  ADD CONSTRAINT cc_lugares_unpublished
    CHECK (module <> 'cc_lugares' OR publication_status = 'draft');

CREATE UNIQUE INDEX cc_lugares_entity_revision_uq
  ON design.content_items (entity_id, language, cc_revision) WHERE module = 'cc_lugares';
CREATE INDEX cc_lugares_review_queue_idx
  ON design.content_items (cc_review_status, updated_at) WHERE module = 'cc_lugares';

CREATE FUNCTION design.cc_lugares_revision_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, design AS $function$
DECLARE
  state text; merged_into uuid;
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.module = 'cc_lugares' THEN
    IF OLD.cc_review_status <> 'draft' AND (
      to_jsonb(NEW) - ARRAY['updated_at', 'cc_review_status', 'cc_reviewed_by',
        'cc_reviewed_at', 'cc_style_approved']
      IS DISTINCT FROM
      to_jsonb(OLD) - ARRAY['updated_at', 'cc_review_status', 'cc_reviewed_by',
        'cc_reviewed_at', 'cc_style_approved']
    ) THEN RAISE EXCEPTION 'Submitted text is immutable; insert a new revision'; END IF;
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
CREATE TRIGGER cc_lugares_revision_guard
  BEFORE INSERT OR UPDATE ON design.content_items
  FOR EACH ROW EXECUTE FUNCTION design.cc_lugares_revision_guard();
COMMENT ON COLUMN design.content_items.cc_sources IS
  'CC evidence URLs, source roles and fact IDs. Own text lives in short_description/body, not JSON.';
COMMENT ON COLUMN design.content_items.cc_availability_status IS
  'Unknown unless explicitly verified; HTTP success is not proof that a place is open.';
COMMIT;
