# FOLLOW-UP CHUNK 26 — Contact Person decision audit

**Audit date:** 2026-08-22

**Source HEAD:** `3d7837c186388b0afe70a44e1ce3a0c1605800fa`

**Production DB head:** `followup_admin_knowledge_base_20260821`

**Decision status:** `AUDIT COMPLETE / OWNER DECISION REQUIRED`

**Recommendation:** `OPTION B`

**Owner gate:** `FOLLOWUP_CONTACT_PERSON_OPTION_B_APPROVAL_REQUIRED`

This is a read-only audit and product decision record. It does not create a
Contact Person model, migration, backfill or production data. A future schema
change remains separately gated by
`FOLLOWUP_CONTACT_PERSON_SCHEMA_MIGRATION_APPROVAL_REQUIRED`.

## Executive decision

The current model is a **multi-coordinate Client contact model**, not a
multi-person model. It safely stores multiple independent e-mail addresses and
phone numbers per Client, with one primary coordinate per kind and provenance
on each coordinate. It cannot represent that an e-mail and a phone belong to
the same human, nor can it persist that person's name, role, preference,
decision-maker status or person-specific notes.

Therefore Option A would preserve a simple and stable model, but would declare
several ordinary business cases permanently unrepresentable. **Option B is
recommended**, using an additive `ContactPerson` parent and retaining the
existing `ClientContactPoint` rows as the canonical phone/e-mail coordinates.
No historical coordinate should be linked to a person without explicit source
evidence.

## Current-state model

### Relational contract

Only one production table contains `contact` or `person` in its name:
`client_contact_points`.

Each `ClientContactPoint` contains:

- `client_id`, `kind = email|phone`, `value`, `normalized_value`,
- `is_primary` and `position`,
- `origin = manual|gmail|sheets|migration|other`,
- optional `source_type` and `source_id`,
- timestamps and `deleted_at` inherited from `BusinessBase`.

The database prevents the same normalized value from appearing twice for the
same Client and kind. The API independently validates the e-mail and phone
lists and permits at most one primary e-mail and one primary phone. If a
non-empty list has no primary coordinate, its first entry becomes primary.

The model has no field or relationship for:

- first name, last name or person display name,
- role, title or position held by a person,
- preferred person or decision maker,
- person-specific notes,
- grouping one or more phones and e-mails under one person.

`Client.notes` is Client-wide. It is not person-specific. The scalar
`Client.primary_email` and `Client.primary_phone` remain compatibility
projections and likewise do not identify a person.

### Lifecycle and history

Contact coordinates are Client children (`cascade="all, delete-orphan"`). The
current replace-list edit flow removes/recreates child rows rather than
offering a standalone Contact Trash workspace. Change History records
`client_contact` create/update/delete events with coordinate kind, value,
primary state and position. It does not retain a person identity because none
exists.

Client deletion is a separate Administrator-only Trash lifecycle. Client
contact editing uses the same authenticated Client update permission as other
Client fields; it is not Administrator-only.

## Production aggregate audit

All figures below are counts only. No contact value, name or other PII was
included in the audit output.

| Measure | Count |
|---|---:|
| Clients, all rows | 3,243 |
| Active/non-purged Clients | 3,236 |
| Active contact coordinates for active Clients | 5,052 |
| Active Clients with 0 coordinates | 15 |
| Active Clients with 1 coordinate | 1,396 |
| Active Clients with more than 1 coordinate | 1,825 |
| E-mail coordinates | 2,627 |
| Phone coordinates | 2,425 |
| Clients with both e-mail and phone | 1,825 |
| Clients with e-mail only | 799 |
| Clients with phone only | 597 |
| Clients with neither | 15 |
| Clients with more than one e-mail | 2 |
| Clients with more than one phone | 3 |

The active-client histogram is: 1,396 Clients with one coordinate, 1,822 with
two, and one Client each with three, four and five coordinates. This proves
multi-coordinate support but does **not** prove multi-person support.

No within-Client exact duplicate exists. Four normalized phone values occur
across more than one Client (18 rows in total; maximum 12 Clients for one
value). Cross-Client duplicates are permitted and may represent generic/shared
numbers; the audit does not infer identity from them. Every active
Client/kind group with coordinates has exactly one primary coordinate.

Production provenance is predominantly migrated historical data. Only six
coordinate rows have an exact `source_id` link. Provenance belongs to the
coordinate, not to an identified person.

## Current integrations

### Client Details and editing

The Polish Client Details `Kontakt` card lists e-mails and phones separately,
labels the primary item and displays coordinate origin. Its local `Edytuj`
action and the full `Edytuj klienta` dialog both use the same two independent
lists. An operator can add/remove multiple e-mails and phones and select one
primary item of each kind.

The UI cannot:

- create two named people under one company,
- assign an e-mail and two phones to one person,
- show role/title, preferred person or decision maker,
- save a note about one person rather than the whole Client.

### Client Search and Global Search

`ClientSearchMatchingService` searches the scalar compatibility fields and
active `ClientContactPoint.normalized_value`; phone digits are normalized.
Global Search reuses the same matcher, scores e-mail/phone matches and returns
a Client result. Neither service indexes a contact-person name or role because
those fields do not exist.

A future Contact Person implementation must extend these shared primitives,
not add a parallel search engine. Client results should remain backward
compatible, with optional person match context added additively.

### Mail matching and candidate merge

Candidate promotion matches normalized sender e-mail or phone to either the
Client scalar compatibility field or a `ClientContactPoint`. Gmail source rows
are ultimately associated with `ClientCandidate.matched_client_id`, and mail
history is projected at Client level. Production has 4,280 active Gmail source
rows, of which 4,130 are matched to a Client, but none can be canonically
attributed to a Contact Person.

Forward ingestion may extract a sender name for candidate identity and stores
verified e-mail/phone evidence in source payload metadata. Candidate merge
adds coordinate rows with provenance. It does not persist a person or bind
those coordinates to one.

There is a semantic projection capable of detecting candidate/source contact
names and roles for dry-run identity analysis. It is derived evidence, not a
canonical CRM Contact Person table and must not be treated as such.

### Activity, tasks, calendar and AI

Call activity can reference a phone `ClientContactPoint` ID, otherwise it
references the Client's legacy primary phone. There are currently no
production call events. Work items link to `client_id` and may hold a free-form
`party_name`; this is not a Contact Person relationship. No current canonical
Calendar attendee-to-contact relationship was found.

The Agent `get_client_contacts` tool returns only `type`, `value`, `primary`
and `origin`. A future AI contract would need to distinguish Client,
ContactPerson and coordinate, but that belongs to a later approved scope and
must not start Phase E here.

## Option A — keep coordinates only

### Benefits

- no schema, API, UI or migration work,
- complete compatibility with current search, mail and imports,
- no forced interpretation or backfill of historical values,
- low implementation and duplicate-concept risk.

### Limitations

- multiple coordinates cannot be grouped into identified people,
- person name/role/title, preferred person and decision maker are impossible,
- notes and provenance cannot describe a person independently of the Client or
  coordinate,
- mail/call attribution stops at Client or coordinate,
- two people under one company are awkward and ambiguous,
- future task/calendar/AI attribution has no stable person identity.

Option A is appropriate only if the product intentionally needs communication
coordinates and never needs human contacts. The present roadmap requirement
explicitly names person-level semantics, so the audit does not support marking
Contact Person obsolete.

## Option B — additive Contact Person domain

### Proposed ownership

Use one Contact Person per Client relationship:

```text
Client 1 ── * ContactPerson 1 ── * ClientContactPoint
                         ClientContactPoint.contact_person_id is nullable
```

One `ContactPerson` belongs to exactly one Client. Many-to-many ownership has
no demonstrated requirement and would add avoidable permission, history and
merge complexity.

Proposed `contact_persons` fields:

- `id`, `client_id`, required `display_name`, optional `role`,
- `is_preferred`, `is_decision_maker`, `notes`, `position`,
- `origin`, `source_type`, optional evidence/source reference,
- `created_at`, `updated_at`, `deleted_at`,
- actor metadata consistent with current auditable domains where required.

Retain `client_contact_points` and add nullable `contact_person_id` (Option
B1). Generic Client coordinates such as `office@company.pl` or a switchboard
number remain Client-owned with `contact_person_id = NULL`. Person-specific
e-mails/phones link to their person. This avoids duplicating normalization,
primary-coordinate, mail-matching and provenance logic in new child tables.

Database integrity should prevent a coordinate owned by Client A from linking
to a person owned by Client B, preferably with a composite `(id, client_id)`
key/FK contract. A partial unique index may allow at most one active preferred
person per Client. `is_decision_maker` should not be globally unique unless a
real business rule later proves that only one decision maker is permitted.

### Compatibility and migration

The safe migration is additive:

1. create `contact_persons`,
2. add nullable `client_contact_points.contact_person_id`,
3. add indexes/FKs and Change History allowlist support,
4. leave every historical link null.

There must be no automatic conversion from e-mail local parts, Client names,
coordinate order or primary flags into people. Initial person creation should
be manual or require explicit, reviewable source evidence.

Existing API response shapes remain intact. Person endpoints/projections and
optional coordinate ownership fields must be additive because deployed clients
remain API consumers. Existing primary e-mail/phone semantics continue to
mean primary coordinate; preferred person is a distinct concept.

### Audit and lifecycle

Use existing Change History conventions. Record `created`, `updated`,
`deleted/archived` and `restored`; preferred/decision-maker changes should be
field-level before/after values on an `updated` event unless the existing
action constraint is deliberately extended in the separately approved
migration.

Use a recoverable soft archive for Contact Persons inside the Client domain.
Do not create a parallel deletion system. The canonical Trash workspace does
not currently manage Client child contacts, so a standalone Trash extension is
not justified by this decision chunk.

Permissions should inherit current Client read/edit authorization. Do not add
an unrelated permission framework.

### Integration impact

- **Mail:** resolve a matched e-mail to optional Contact Person plus Client;
  generic coordinates remain Client-only. Keep old Client match fields
  additive/backward compatible.
- **Client/Global Search:** extend the shared Client matcher with active person
  display name/role and linked coordinates; preserve Client result routing.
- **Imports/merge:** preserve evidence but never synthesize or auto-link people
  without explicit source proof.
- **Client UI:** show people as compact cards with name/role, their coordinates,
  preferred/decision-maker badges and local edit; retain a separate generic
  Client coordinates area.
- **AI/Agent:** later expose explicit entity types and provenance. No AI work is
  part of CHUNK 26 or Phase D.
- **Tasks/calendar/activity:** a stable optional person ID would improve future
  attribution, but no cross-domain relation is implemented by this decision.

## Decision matrix

Scores are 1–5; higher is better. “Migration safety” scores lower risk higher.

| Criterion | Option A | Option B |
|---|---:|---:|
| Business usefulness | 2 | 5 |
| Data correctness | 2 | 5 |
| Existing-data compatibility | 5 | 4 |
| Schema simplicity | 5 | 2 |
| UX simplicity | 4 | 3 |
| Mail attribution | 2 | 5 |
| Search quality | 3 | 5 |
| Auditability | 3 | 5 |
| Future extensibility | 2 | 5 |
| Migration safety | 5 | 4 |
| Low duplicate-concept risk | 4 | 3 |
| **Total** | **37/55** | **46/55** |

Option B's duplicate-concept risk is controlled by keeping
`ClientContactPoint` as the sole coordinate model and making Contact Person an
identity/grouping parent, not another phone/e-mail store.

## Recommendation and gates

**RECOMMEND OPTION B.** The current model is robust for multiple phone/e-mail
coordinates but insufficient for multiple identified people. The smallest
correct extension is the additive B1 ownership model described above.

This recommendation is not owner approval. Exact next gate:

`FOLLOWUP_CONTACT_PERSON_OPTION_B_APPROVAL_REQUIRED`

If the owner chooses Option B, schema work additionally requires:

`FOLLOWUP_CONTACT_PERSON_SCHEMA_MIGRATION_APPROVAL_REQUIRED`

## Owner decision and source implementation checkpoint — 2026-08-22

The owner approved Option B through
`FOLLOWUP_CONTACT_PERSON_OPTION_B_APPROVAL_REQUIRED`. Source now implements the
audited B1 model: one Client owns many Contact Persons; existing
`ClientContactPoint` rows optionally reference a same-Client person through a
composite foreign key. Coordinates with a null person remain generic company
contacts. No parallel phone/e-mail tables were introduced.

The additive migration is `followup_contact_person_20260822`, directly after
`followup_admin_knowledge_base_20260821`. It performs no backfill. Isolated
upgrade/downgrade/re-upgrade proves that historical coordinate counts are
preserved and all historical ownership remains null. It also proves the
cross-Client ownership rejection, one-active-preferred rule, nullable generic
ownership and multiple-decision-maker rule.

Runtime source includes bounded CRUD and coordinate assignment, additive
Client/Global Search matching, exact canonical-coordinate mail attribution,
Change History and responsive Client Details cards. Archiving a person unlinks
their coordinates to generic Client ownership and soft-deletes only the person;
the e-mail/phone rows are retained. Full Flutter acceptance is `281/281`, with
Android/Web/Windows debug builds passing.

Production migration and production Contact Person creation were not
performed. Exact next gate:

`FOLLOWUP_CONTACT_PERSON_SCHEMA_MIGRATION_APPROVAL_REQUIRED`

## Phase boundary

The owner sequencing rule is mandatory:

```text
CHUNK 15 COMPLETE
→ CHUNK 16 COMPLETE
→ CHUNK 26 owner decision and any approved bounded completion COMPLETE
→ RELEASE D (separate prompt)
→ only then PHASE E
```

CHUNK 17/18/19 and all Phase E runtime work remain NOT STARTED. No Release D,
production write, migration, Qdrant mutation, Vision job or Temporary Chat job
occurred during this audit.
