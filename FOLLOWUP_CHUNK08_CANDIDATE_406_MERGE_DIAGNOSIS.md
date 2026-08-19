# FOLLOW-UP CHUNK 08 — Candidate accept conflict and merge diagnosis

Date: 2026-08-19

Source HEAD: `90d55f11f9764caf31b80199e328e2b5da69e443`

Release: NEXT Stabil 1.0.2+21

Database: `followup_clientdate_20260819`

## Decision

The current source and available runtime logs do not contain a Candidate accept
path that emits HTTP 406. Since the Candidate review endpoint was introduced in
commit `c93c09a`, an exact duplicate has been represented as HTTP 409 with
`detail.code = candidate_matches_existing_client`. The reported 406 is therefore
not reproducible against the current contract and cannot truthfully be assigned
to the current duplicate exception.

The current 409 response is still incomplete for the requested workflow. It
returns one Client ID and one reason, while a safe merge needs all deterministic
matches, bounded evidence, a preview, explicit confirmation, idempotency and a
persistent actor audit. The existing audit tables do not provide that merge
audit. Implementation must stop at:

`FOLLOWUP_CANDIDATE_MERGE_AUDIT_MIGRATION_APPROVAL_REQUIRED`

No production Candidate or Client was changed during this diagnosis.

## Current flow

1. `POST /api/v1/client-candidates/{candidate_id}/accept`
2. `ClientCandidateReviewService.accept_candidate`
3. `ClientCandidatePromotionService.promote`
4. Candidate row lock and validation (`pending`, unmatched, usable identity)
5. deterministic duplicate lookup
6. create Client when no duplicate exists
7. copy bounded Candidate fields and forward validated contacts
8. set Candidate to `accepted` and `matched_client_id`
9. relink Candidate Documents to the new Client
10. flush and commit in the review service; rollback on any exception

The duplicate exception is `CandidateDuplicateClientError`. The route maps it
to HTTP 409. Other promotion state/validation failures are also HTTP 409, but
currently use untyped string details. There is no current HTTP 406 branch.

## Current duplicate rules

The matcher stops at the first matching category in this order:

1. exact normalized `tax_id`;
2. exact normalized primary/contact email;
3. exact normalized primary/contact phone.

Name, name plus city and source/thread identity are not used. This prevents a
name-only automatic merge, but it also means ambiguous evidence is not surfaced.
When different identifiers match different Clients, the first category wins and
the conflict is hidden. Multiple matches within one category are reduced by an
unordered `.first()` query.

Normalization is also fragmented. A future matcher should reuse
`ClientIdentityNameQualityService.normalize_email`, `normalize_phone` and
`normalize_tax_id`. NIP must be digits-only and exact; it must never be fuzzy.

## Controlled characterization

`backend/test/test_followup_chunk08_candidate_diagnosis.py` runs entirely in an
outer transaction that is rolled back after every test. It covers 12 cases:

1. unique Candidate promotion;
2. normalized email duplicate;
3. normalized phone duplicate;
4. normalized NIP duplicate;
5. same name only;
6. same name and city;
7. source identity omission;
8. multiple deterministic matches collapsed by priority;
9. repeated promotion request;
10. conflicting NIP and email evidence;
11. contact union/deduplication;
12. Document relation preservation during unique promotion.

Result: `12/12 PASS` as a characterization of the current behavior. The tests
also prove two gaps: repeated promotion returns a state conflict rather than an
idempotent prior result, and multi-Client evidence is not represented.

## Additive compatible conflict contract

Keep HTTP 409 and the existing fields for deployed +21 consumers. Extend the
body additively:

```json
{
  "code": "candidate_matches_existing_client",
  "message": "Candidate matches an existing client.",
  "matched_client_id": 123,
  "matched_by": "email",
  "matches": [
    {
      "client_id": 123,
      "confidence": "certain",
      "reasons": ["exact_email"]
    }
  ]
}
```

`certain` is limited to exact normalized identifiers or a verified source
identity. `high` and `ambiguous` may be displayed for review but must not apply
a merge. Name-only and name/city evidence remain `ambiguous` at most. When more
than one Client matches, every bounded match is returned and no target is picked
automatically.

## Merge design after approval

The safe flow is:

1. duplicate conflict;
2. read-only preview for a user-selected target Client;
3. display identity, contacts, addresses, provenance and bounded linked-record
   counts without email/document bodies;
4. explicit field policy (`keep_existing`, `take_candidate`, `add`, or
   `manual_conflict`);
5. confirmation with an operation UUID and optimistic Candidate version check;
6. one DB transaction for link changes, Candidate terminal state and audit;
7. idempotent replay returns the already completed target and performs no writes.

Contacts and addresses use normalized union/deduplication. Different names or
legal names require an explicit choice. A conflicting exact NIP blocks apply
until manually resolved. Existing Documents/emails are relinked, never copied;
their original source identity and provenance remain intact. Candidate becomes
`merged` with `matched_client_id` set and is not deleted.

The UI may then show “Znaleziono istniejącego klienta”, all matching reasons and
the actions “Otwórz klienta”, “Połącz” and “Anuluj”. Opening or rendering the
dialog has no write side effect. A second confirmation screen is mandatory.

## Required persistent audit migration

Existing `AgentExecution`, `UserLifecycleEvent` and
`DocumentClientLinkEvent` tables are scoped to other domains and cannot record a
Candidate merge without losing required semantics. Reusing them would create a
misleading audit trail.

Proposed minimal additive table: `candidate_merge_events`.

- `id` — bigint primary key;
- `operation_id` — backend-generated UUID-compatible string, unique and not
  derived from customer content;
- `actor_user_id` — FK to `users`, `ON DELETE RESTRICT`;
- `candidate_id` — FK to `client_candidates`, `ON DELETE RESTRICT`;
- `target_client_id` — FK to `clients`, `ON DELETE RESTRICT`;
- `action` — bounded value `candidate_merged`;
- `changed_fields` — bounded JSON array of field names only;
- `relation_counts` — bounded JSON counts only (contacts, addresses, documents,
  emails and sources), with no content;
- `created_at` — timezone-aware server timestamp.

Indexes: unique `operation_id`, plus `(candidate_id, created_at)` and
`(target_client_id, created_at)`. Upgrade creates only the table, constraints and
indexes. There is no backfill and no business-row rewrite. Downgrade drops only
the new table. Isolated upgrade/downgrade/re-upgrade and row-preservation tests
are required before production apply.

After migration approval, implementation must add a read-only preview and an
explicit confirm/apply endpoint, preserve the existing 409 fields, add bounded
multi-match evidence, implement idempotency, add responsive Flutter confirmation
UX, and run the full 12-case apply/rollback matrix. A production merge remains a
separate human-approved operation; acceptance uses synthetic rollback fixtures.

## Data safety

- production Clients changed: 0;
- production Candidates changed: 0;
- durable synthetic writes: 0;
- migrations: 0;
- Qdrant writes: 0;
- n8n changes: 0;
- Vision jobs: 0;
- emails sent: 0;
- cleanup: 0;
- release: not performed.
