# AI Lab — Database Design

> Historical target-design draft, not an as-built schema reference. The live
> database at the final audit is Alembic head `chunk16audit_20260819`; several
> entities below (including `Case`) remain conceptual and are not deployed.
> Use migrations/models plus `FINAL_SYSTEM_AUDIT.md` for current evidence.

## 1. Purpose

This document defines the target relational database structure for AI Lab.

The central business entity is:

```text
Case
```

A Case represents a real business project, inquiry, offer, inspection, realization, complaint, or another business matter.

Documents, emails, contacts, notes, AI extractions, and search data are connected to Cases.

---

# 2. General design rules

## 2.1 Database

Primary relational database:

```text
PostgreSQL
```

Vector database:

```text
Qdrant
```

PostgreSQL stores:

- business entities,
- relationships,
- structured metadata,
- processing status,
- audit information,
- Qdrant point identifiers.

Qdrant stores:

- embeddings,
- vector indexes,
- searchable chunk vectors.

---

## 2.2 Primary keys

All main relational tables use:

```text
id: BIGINT
```

Initially the application may use SQLAlchemy `Integer`, but business-domain tables should preferably use `BigInteger`.

Dictionary tables may use regular integer identifiers.

---

## 2.3 Timestamps

Business tables should normally contain:

```text
created_at
updated_at
```

Both timestamps use timezone-aware values:

```text
TIMESTAMP WITH TIME ZONE
```

The database generates `created_at`.

The application or database updates `updated_at`.

---

## 2.4 Soft deletion

Important business records should not normally be physically deleted.

Tables that support soft deletion contain:

```text
deleted_at
```

A non-null `deleted_at` means the record has been archived or deleted logically.

Soft deletion is planned for:

- clients,
- contacts,
- cases,
- documents,
- notes,
- tasks.

Imported technical records may use physical deletion when safe.

---

## 2.5 AI write rule

AI never writes directly to final business fields.

AI writes proposals to:

```text
ai_extractions
```

The proposals must then be:

- automatically accepted under explicit rules, or
- reviewed by a user.

Only application services update business tables.

---

# 3. Domain overview

```text
User
  │
  ├── creates and reviews
  │
  ▼
Client
  │
  ├── Contact
  │
  └── Case
        │
        ├── Case Contact
        ├── Document
        │     ├── Document Chunk
        │     └── AI Extraction
        │
        ├── Email
        │     └── Email Attachment
        │
        ├── Note
        ├── Task
        └── Calendar Event
```

---

# 4. Existing system tables

The following tables already exist:

- users
- roles
- conversations
- messages
- documents
- document_chunks

The current `documents` and `document_chunks` tables will be extended rather than immediately replaced.

The exact migration strategy will be implemented incrementally.

---

# 5. Core business tables

# 5.1 clients

Represents a business customer, organization, public institution, sole proprietor, or private individual.

A Client is the commercial or legal entity connected with one or more Cases.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| client_type | VARCHAR(30) | no | `company`, `person`, `institution`, `other` |
| name | VARCHAR(255) | no | Display name |
| legal_name | VARCHAR(255) | yes | Registered legal name |
| tax_id | VARCHAR(32) | yes | NIP or another tax identifier |
| registration_number | VARCHAR(64) | yes | KRS, REGON, or another registration number |
| industry_id | INTEGER | yes | Reference to industries |
| website | VARCHAR(500) | yes | Website URL |
| primary_email | VARCHAR(255) | yes | General client email |
| primary_phone | VARCHAR(50) | yes | General client phone |
| street | VARCHAR(255) | yes | Address street |
| building_number | VARCHAR(50) | yes | Building number |
| unit_number | VARCHAR(50) | yes | Unit number |
| postal_code | VARCHAR(20) | yes | Postal code |
| city | VARCHAR(150) | yes | City |
| country_code | VARCHAR(2) | no | ISO country code, default `PL` |
| notes | TEXT | yes | General internal description |
| created_at | TIMESTAMPTZ | no | Creation timestamp |
| updated_at | TIMESTAMPTZ | no | Last update |
| deleted_at | TIMESTAMPTZ | yes | Soft deletion |

## Constraints

```text
CHECK client_type IN (
    'company',
    'person',
    'institution',
    'other'
)
```

`name` must not be empty.

`country_code` must contain exactly two characters.

## Indexes

```text
INDEX clients_name_idx
INDEX clients_tax_id_idx
INDEX clients_primary_email_idx
INDEX clients_city_idx
INDEX clients_deleted_at_idx
```

`tax_id` is not globally required to be unique because imported historical data may contain duplicates or incomplete values.

Duplicate detection belongs to the service layer.

---

# 5.2 contacts

Represents a person associated with a Client.

A single Client may have many Contacts.

Examples:

- owner,
- project manager,
- engineer,
- accountant,
- purchasing specialist,
- private property owner.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| client_id | BIGINT | no | Parent client |
| first_name | VARCHAR(100) | yes | First name |
| last_name | VARCHAR(150) | yes | Last name |
| display_name | VARCHAR(255) | no | Full display name |
| job_title | VARCHAR(150) | yes | Position or role |
| department | VARCHAR(150) | yes | Department |
| email | VARCHAR(255) | yes | Contact email |
| phone | VARCHAR(50) | yes | Primary phone |
| secondary_phone | VARCHAR(50) | yes | Secondary phone |
| is_primary | BOOLEAN | no | Primary contact for the Client |
| notes | TEXT | yes | Internal notes |
| created_at | TIMESTAMPTZ | no | Creation timestamp |
| updated_at | TIMESTAMPTZ | no | Last update |
| deleted_at | TIMESTAMPTZ | yes | Soft deletion |

## Relationships

```text
clients 1:N contacts
```

## Foreign key

```text
contacts.client_id
    → clients.id
    ON DELETE RESTRICT
```

A Client cannot be physically deleted while Contacts exist.

Soft deletion should normally be used.

## Indexes

```text
INDEX contacts_client_id_idx
INDEX contacts_email_idx
INDEX contacts_phone_idx
INDEX contacts_display_name_idx
```

Only one active primary Contact per Client should be enforced in the service layer initially.

A partial database index may be introduced later.

---

# 5.3 cases

Represents the central business matter.

A Case may represent:

- inquiry,
- offer,
- inspection,
- project,
- realization,
- complaint,
- service job,
- internal analysis.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| client_id | BIGINT | yes | Related Client |
| case_number | VARCHAR(100) | no | Internal unique identifier |
| title | VARCHAR(255) | no | Human-readable title |
| description | TEXT | yes | Case description |
| status_id | INTEGER | no | Current case status |
| object_type_id | INTEGER | yes | Type of object |
| problem_type_id | INTEGER | yes | Main problem category |
| technology_type_id | INTEGER | yes | Main technology |
| industry_id | INTEGER | yes | Industry copied or selected for Case |
| location_id | BIGINT | yes | Structured project location |
| offer_number | VARCHAR(100) | yes | Offer identifier |
| project_number | VARCHAR(100) | yes | Project identifier |
| external_reference | VARCHAR(255) | yes | External system reference |
| inquiry_date | DATE | yes | Initial inquiry date |
| offer_date | DATE | yes | Offer issue date |
| realization_date | DATE | yes | Actual realization date |
| completion_date | DATE | yes | Completion date |
| estimated_value | NUMERIC(14,2) | yes | Estimated case value |
| final_value | NUMERIC(14,2) | yes | Final case value |
| currency | VARCHAR(3) | no | ISO currency, default `PLN` |
| created_by_id | BIGINT | yes | User who created the Case |
| assigned_to_id | BIGINT | yes | Responsible user |
| created_at | TIMESTAMPTZ | no | Creation timestamp |
| updated_at | TIMESTAMPTZ | no | Last update |
| deleted_at | TIMESTAMPTZ | yes | Soft deletion |

## Relationships

```text
clients 1:N cases
case_statuses 1:N cases
object_types 1:N cases
problem_types 1:N cases
technology_types 1:N cases
industries 1:N cases
locations 1:N cases
users 1:N cases as creator
users 1:N cases as assignee
```

## Foreign keys

```text
cases.client_id
    → clients.id
    ON DELETE SET NULL
```

A Case must remain available even if a Client is later anonymized or removed.

```text
cases.status_id
    → case_statuses.id
    ON DELETE RESTRICT
```

```text
cases.location_id
    → locations.id
    ON DELETE SET NULL
```

```text
cases.created_by_id
    → users.id
    ON DELETE SET NULL
```

```text
cases.assigned_to_id
    → users.id
    ON DELETE SET NULL
```

## Constraints

```text
UNIQUE case_number
```

```text
CHECK estimated_value >= 0
CHECK final_value >= 0
```

```text
CHECK length(currency) = 3
```

## Indexes

```text
UNIQUE INDEX cases_case_number_uq
INDEX cases_client_id_idx
INDEX cases_status_id_idx
INDEX cases_object_type_id_idx
INDEX cases_problem_type_id_idx
INDEX cases_technology_type_id_idx
INDEX cases_industry_id_idx
INDEX cases_location_id_idx
INDEX cases_realization_date_idx
INDEX cases_offer_number_idx
INDEX cases_project_number_idx
INDEX cases_assigned_to_id_idx
INDEX cases_deleted_at_idx
```

The default interpretation of date-based business searches is:

```text
realization_date
```

Example:

```text
"Show projects from 2025"
```

means:

```text
cases.realization_date between 2025-01-01 and 2025-12-31
```

unless the user explicitly requests another date.

---

# 5.4 case_contacts

Connects Contacts to Cases.

A Contact may participate in multiple Cases.

A Case may have multiple Contacts.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| case_id | BIGINT | no | Related Case |
| contact_id | BIGINT | no | Related Contact |
| role | VARCHAR(100) | yes | Role in this Case |
| is_primary | BOOLEAN | no | Primary contact for this Case |
| created_at | TIMESTAMPTZ | no | Creation timestamp |

## Foreign keys

```text
case_contacts.case_id
    → cases.id
    ON DELETE CASCADE
```

```text
case_contacts.contact_id
    → contacts.id
    ON DELETE RESTRICT
```

## Constraints

```text
UNIQUE (case_id, contact_id)
```

## Indexes

```text
INDEX case_contacts_case_id_idx
INDEX case_contacts_contact_id_idx
```

---

# 5.5 locations

Stores reusable structured locations.

Locations may represent:

- project address,
- construction site,
- client office,
- parcel,
- geographic coordinates.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| name | VARCHAR(255) | yes | Location label |
| street | VARCHAR(255) | yes | Street |
| building_number | VARCHAR(50) | yes | Building number |
| unit_number | VARCHAR(50) | yes | Unit number |
| postal_code | VARCHAR(20) | yes | Postal code |
| city | VARCHAR(150) | yes | City |
| municipality | VARCHAR(150) | yes | Municipality |
| county | VARCHAR(150) | yes | County |
| region | VARCHAR(150) | yes | Region or voivodeship |
| country_code | VARCHAR(2) | no | Default `PL` |
| parcel_number | VARCHAR(100) | yes | Cadastral parcel number |
| latitude | NUMERIC(10,7) | yes | Latitude |
| longitude | NUMERIC(10,7) | yes | Longitude |
| created_at | TIMESTAMPTZ | no | Creation timestamp |
| updated_at | TIMESTAMPTZ | no | Last update |

## Constraints

```text
CHECK latitude BETWEEN -90 AND 90
CHECK longitude BETWEEN -180 AND 180
CHECK length(country_code) = 2
```

## Indexes

```text
INDEX locations_city_idx
INDEX locations_postal_code_idx
INDEX locations_parcel_number_idx
INDEX locations_coordinates_idx
```

Locations are not automatically deduplicated solely by address text.

AI may propose matching locations, but the service layer decides whether to reuse or create a location.

---

# 6. Document and communication tables

# 6.1 documents

Represents every imported or uploaded file or text-based business document.

Examples:

- PDF,
- DOCX,
- XLSX,
- photograph,
- scanned document,
- email body represented as a document,
- technical report,
- offer,
- invoice,
- project file.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| case_id | BIGINT | yes | Assigned Case |
| client_id | BIGINT | yes | Optional directly identified Client |
| document_type_id | INTEGER | yes | Document classification |
| source_type | VARCHAR(50) | no | Import source |
| source_identifier | VARCHAR(500) | yes | External source ID |
| filename | VARCHAR(255) | no | Original filename |
| original_path | TEXT | yes | Original source path |
| storage_path | TEXT | yes | Internal storage path |
| content_type | VARCHAR(150) | no | MIME type |
| file_size | BIGINT | no | Size in bytes |
| checksum_sha256 | VARCHAR(64) | yes | File checksum |
| title | VARCHAR(500) | yes | Extracted or assigned title |
| language | VARCHAR(10) | yes | Detected language |
| page_count | INTEGER | yes | Page count |
| raw_text | TEXT | yes | Extracted source text |
| processing_status | VARCHAR(50) | no | Pipeline status |
| processing_error | TEXT | yes | Last processing error |
| imported_at | TIMESTAMPTZ | no | Import timestamp |
| processed_at | TIMESTAMPTZ | yes | Processing completion |
| created_at | TIMESTAMPTZ | no | Creation timestamp |
| updated_at | TIMESTAMPTZ | no | Last update |
| deleted_at | TIMESTAMPTZ | yes | Soft deletion |

## Source types

Initial values:

```text
upload
gmail
local_folder
onedrive
google_drive
nas
api
generated
```

## Processing statuses

Initial values:

```text
imported
text_extraction_pending
text_extracted
ai_extraction_pending
ai_extracted
review_pending
assigned
chunking_pending
chunked
embedding_pending
indexed
failed
```

## Foreign keys

```text
documents.case_id
    → cases.id
    ON DELETE SET NULL
```

```text
documents.client_id
    → clients.id
    ON DELETE SET NULL
```

```text
documents.document_type_id
    → document_types.id
    ON DELETE SET NULL
```

## Constraints

```text
CHECK file_size >= 0
CHECK page_count IS NULL OR page_count >= 0
```

Possible duplicate protection:

```text
UNIQUE (source_type, source_identifier)
```

This constraint should be introduced only when every importer provides a stable source identifier.

## Indexes

```text
INDEX documents_case_id_idx
INDEX documents_client_id_idx
INDEX documents_document_type_id_idx
INDEX documents_source_type_idx
INDEX documents_source_identifier_idx
INDEX documents_checksum_sha256_idx
INDEX documents_processing_status_idx
INDEX documents_imported_at_idx
INDEX documents_deleted_at_idx
```

A Document may temporarily exist without a Case.

This is required because Case matching happens after import and AI extraction.

Chunking should normally happen after Case assignment.

---

# 6.2 document_chunks

Stores searchable text fragments created from Documents.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| document_id | BIGINT | no | Parent Document |
| chunk_index | INTEGER | no | Position in Document |
| content | TEXT | no | Chunk content |
| token_count | INTEGER | no | Approximate token count |
| page_start | INTEGER | yes | First source page |
| page_end | INTEGER | yes | Last source page |
| section_title | VARCHAR(500) | yes | Section heading |
| content_hash | VARCHAR(64) | yes | Chunk content hash |
| qdrant_point_id | UUID | yes | Qdrant vector point ID |
| embedding_model | VARCHAR(150) | yes | Model used for embedding |
| embedded_at | TIMESTAMPTZ | yes | Embedding creation timestamp |
| created_at | TIMESTAMPTZ | no | Creation timestamp |

## Foreign key

```text
document_chunks.document_id
    → documents.id
    ON DELETE CASCADE
```

## Constraints

```text
UNIQUE (document_id, chunk_index)
CHECK chunk_index >= 0
CHECK token_count >= 0
CHECK page_start IS NULL OR page_start >= 1
CHECK page_end IS NULL OR page_end >= page_start
```

## Indexes

```text
INDEX document_chunks_document_id_idx
INDEX document_chunks_qdrant_point_id_idx
INDEX document_chunks_content_hash_idx
```

The vector itself is stored in Qdrant.

PostgreSQL stores the relationship between:

```text
Document Chunk
↔
Qdrant Point
```

---

# 6.3 emails

Stores individual email messages.

Emails remain separate records even when they belong to the same thread.

AI reasons over complete communication history, but raw messages remain unchanged.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| case_id | BIGINT | yes | Assigned Case |
| client_id | BIGINT | yes | Identified Client |
| contact_id | BIGINT | yes | Identified Contact |
| document_id | BIGINT | yes | Document representing searchable email content |
| provider | VARCHAR(50) | no | Example: `gmail` |
| external_message_id | VARCHAR(500) | no | Provider message ID |
| external_thread_id | VARCHAR(500) | yes | Provider thread ID |
| internet_message_id | VARCHAR(500) | yes | RFC Message-ID |
| subject | VARCHAR(1000) | yes | Email subject |
| sender_name | VARCHAR(255) | yes | Sender display name |
| sender_email | VARCHAR(255) | no | Sender email |
| recipients_to | JSONB | no | To recipients |
| recipients_cc | JSONB | no | CC recipients |
| recipients_bcc | JSONB | no | BCC recipients |
| sent_at | TIMESTAMPTZ | yes | Message send time |
| received_at | TIMESTAMPTZ | yes | Message receive time |
| body_text | TEXT | yes | Plain text body |
| body_html | TEXT | yes | HTML body |
| direction | VARCHAR(20) | no | `incoming`, `outgoing`, `internal` |
| has_attachments | BOOLEAN | no | Attachment indicator |
| imported_at | TIMESTAMPTZ | no | Import timestamp |
| created_at | TIMESTAMPTZ | no | Creation timestamp |

## Foreign keys

```text
emails.case_id
    → cases.id
    ON DELETE SET NULL
```

```text
emails.client_id
    → clients.id
    ON DELETE SET NULL
```

```text
emails.contact_id
    → contacts.id
    ON DELETE SET NULL
```

```text
emails.document_id
    → documents.id
    ON DELETE SET NULL
```

## Constraints

```text
UNIQUE (provider, external_message_id)
```

```text
CHECK direction IN (
    'incoming',
    'outgoing',
    'internal'
)
```

## Indexes

```text
INDEX emails_case_id_idx
INDEX emails_client_id_idx
INDEX emails_contact_id_idx
INDEX emails_external_thread_id_idx
INDEX emails_sender_email_idx
INDEX emails_sent_at_idx
INDEX emails_received_at_idx
```

Emails must not be assigned to a Case only because they share the same sender.

Case matching uses multiple signals.

---

# 6.4 email_attachments

Connects email messages to imported Documents.

Every attachment becomes a Document.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| email_id | BIGINT | no | Parent email |
| document_id | BIGINT | no | Imported attachment document |
| external_attachment_id | VARCHAR(500) | yes | Provider attachment ID |
| filename | VARCHAR(255) | no | Original filename |
| content_type | VARCHAR(150) | yes | MIME type |
| file_size | BIGINT | yes | Size in bytes |
| is_inline | BOOLEAN | no | Inline content flag |
| content_id | VARCHAR(500) | yes | Email Content-ID |
| created_at | TIMESTAMPTZ | no | Creation timestamp |

## Foreign keys

```text
email_attachments.email_id
    → emails.id
    ON DELETE CASCADE
```

```text
email_attachments.document_id
    → documents.id
    ON DELETE CASCADE
```

## Constraints

```text
UNIQUE (email_id, document_id)
CHECK file_size IS NULL OR file_size >= 0
```

## Indexes

```text
INDEX email_attachments_email_id_idx
INDEX email_attachments_document_id_idx
```

---

# 7. AI processing tables

# 7.1 ai_jobs

Represents asynchronous AI or processing tasks.

Examples:

- OCR,
- text extraction,
- classification,
- entity extraction,
- case matching,
- chunking,
- embedding,
- summarization.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| job_type | VARCHAR(100) | no | Processing type |
| status | VARCHAR(50) | no | Job status |
| document_id | BIGINT | yes | Related Document |
| case_id | BIGINT | yes | Related Case |
| input_data | JSONB | yes | Job input |
| output_data | JSONB | yes | Job output |
| error_message | TEXT | yes | Error details |
| retry_count | INTEGER | no | Retry number |
| max_retries | INTEGER | no | Maximum retries |
| priority | INTEGER | no | Queue priority |
| started_at | TIMESTAMPTZ | yes | Start time |
| completed_at | TIMESTAMPTZ | yes | Completion time |
| created_at | TIMESTAMPTZ | no | Creation timestamp |
| updated_at | TIMESTAMPTZ | no | Last update |

## Status values

```text
pending
running
completed
failed
cancelled
```

## Foreign keys

```text
ai_jobs.document_id
    → documents.id
    ON DELETE CASCADE
```

```text
ai_jobs.case_id
    → cases.id
    ON DELETE CASCADE
```

## Constraints

```text
CHECK retry_count >= 0
CHECK max_retries >= 0
```

## Indexes

```text
INDEX ai_jobs_status_priority_idx
INDEX ai_jobs_document_id_idx
INDEX ai_jobs_case_id_idx
INDEX ai_jobs_job_type_idx
INDEX ai_jobs_created_at_idx
```

---

# 7.2 ai_extractions

Stores structured proposals extracted by AI.

This is a staging and review table.

It is not the final source of business truth.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| document_id | BIGINT | no | Source Document |
| extraction_type | VARCHAR(100) | no | Extracted entity or field type |
| field_name | VARCHAR(150) | no | Proposed business field |
| raw_value | TEXT | yes | Original extracted text |
| normalized_value | JSONB | yes | Normalized structured value |
| confidence | NUMERIC(5,4) | no | Confidence from 0 to 1 |
| source_text | TEXT | yes | Supporting text |
| source_page | INTEGER | yes | Source page |
| status | VARCHAR(50) | no | Review status |
| reviewed_by_id | BIGINT | yes | Reviewing user |
| reviewed_at | TIMESTAMPTZ | yes | Review time |
| rejection_reason | TEXT | yes | Rejection explanation |
| model_name | VARCHAR(150) | yes | AI model |
| prompt_version | VARCHAR(100) | yes | Extraction prompt version |
| created_at | TIMESTAMPTZ | no | Creation timestamp |

## Status values

```text
proposed
accepted
rejected
superseded
```

## Foreign keys

```text
ai_extractions.document_id
    → documents.id
    ON DELETE CASCADE
```

```text
ai_extractions.reviewed_by_id
    → users.id
    ON DELETE SET NULL
```

## Constraints

```text
CHECK confidence >= 0
CHECK confidence <= 1
```

## Indexes

```text
INDEX ai_extractions_document_id_idx
INDEX ai_extractions_field_name_idx
INDEX ai_extractions_status_idx
INDEX ai_extractions_confidence_idx
```

Examples of `field_name`:

```text
client.name
client.email
client.phone
case.offer_number
case.project_number
case.realization_date
case.object_type
case.problem_type
case.technology_type
location.address
location.parcel_number
```

---

# 7.3 case_match_proposals

Stores AI-generated proposals assigning Documents or Emails to Cases.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| document_id | BIGINT | no | Document being matched |
| candidate_case_id | BIGINT | yes | Existing candidate Case |
| proposed_new_case | BOOLEAN | no | AI proposes creating a new Case |
| confidence | NUMERIC(5,4) | no | Overall confidence |
| signal_scores | JSONB | no | Scores for individual signals |
| explanation | TEXT | yes | Human-readable explanation |
| status | VARCHAR(50) | no | Proposal status |
| reviewed_by_id | BIGINT | yes | Reviewing user |
| reviewed_at | TIMESTAMPTZ | yes | Review timestamp |
| created_at | TIMESTAMPTZ | no | Creation timestamp |

## Signal examples

```json
{
  "address": 0.98,
  "client_email": 0.95,
  "offer_number": 1.0,
  "project_number": 1.0,
  "semantic_similarity": 0.84,
  "contact": 0.91
}
```

## Foreign keys

```text
case_match_proposals.document_id
    → documents.id
    ON DELETE CASCADE
```

```text
case_match_proposals.candidate_case_id
    → cases.id
    ON DELETE CASCADE
```

```text
case_match_proposals.reviewed_by_id
    → users.id
    ON DELETE SET NULL
```

## Constraints

```text
CHECK confidence >= 0
CHECK confidence <= 1
```

```text
CHECK (
    candidate_case_id IS NOT NULL
    OR proposed_new_case = TRUE
)
```

## Status values

```text
proposed
accepted
rejected
expired
```

## Initial decision thresholds

```text
confidence >= 0.95
    automatic assignment may be allowed

confidence >= 0.80 and confidence < 0.95
    assignment proposal requiring review

confidence < 0.80
    manual review required
```

Automatic assignment must require more than one matching signal.

A semantic similarity score alone must never automatically assign a Document to a Case.

---

# 8. Operational business tables

# 8.1 notes

Stores internal notes connected to Cases.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| case_id | BIGINT | no | Parent Case |
| author_id | BIGINT | yes | Author |
| content | TEXT | no | Note content |
| note_type | VARCHAR(50) | no | Note category |
| is_pinned | BOOLEAN | no | Pin flag |
| created_at | TIMESTAMPTZ | no | Creation timestamp |
| updated_at | TIMESTAMPTZ | no | Last update |
| deleted_at | TIMESTAMPTZ | yes | Soft deletion |

## Foreign keys

```text
notes.case_id
    → cases.id
    ON DELETE CASCADE
```

```text
notes.author_id
    → users.id
    ON DELETE SET NULL
```

## Indexes

```text
INDEX notes_case_id_idx
INDEX notes_author_id_idx
INDEX notes_created_at_idx
```

---

# 8.2 tasks

Stores work items associated with Cases.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| case_id | BIGINT | yes | Related Case |
| title | VARCHAR(255) | no | Task title |
| description | TEXT | yes | Task description |
| status | VARCHAR(50) | no | Task status |
| priority | VARCHAR(30) | no | Task priority |
| assigned_to_id | BIGINT | yes | Responsible user |
| created_by_id | BIGINT | yes | Creator |
| due_at | TIMESTAMPTZ | yes | Due date |
| completed_at | TIMESTAMPTZ | yes | Completion date |
| created_at | TIMESTAMPTZ | no | Creation timestamp |
| updated_at | TIMESTAMPTZ | no | Last update |
| deleted_at | TIMESTAMPTZ | yes | Soft deletion |

## Status values

```text
open
in_progress
blocked
completed
cancelled
```

## Priority values

```text
low
normal
high
urgent
```

## Foreign keys

```text
tasks.case_id
    → cases.id
    ON DELETE CASCADE
```

```text
tasks.assigned_to_id
    → users.id
    ON DELETE SET NULL
```

```text
tasks.created_by_id
    → users.id
    ON DELETE SET NULL
```

## Indexes

```text
INDEX tasks_case_id_idx
INDEX tasks_assigned_to_id_idx
INDEX tasks_status_idx
INDEX tasks_due_at_idx
```

---

# 8.3 calendar_events

Stores events related to Cases.

It may later be synchronized with external calendars.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| case_id | BIGINT | yes | Related Case |
| title | VARCHAR(255) | no | Event title |
| description | TEXT | yes | Event description |
| starts_at | TIMESTAMPTZ | no | Start |
| ends_at | TIMESTAMPTZ | no | End |
| all_day | BOOLEAN | no | All-day flag |
| location_text | VARCHAR(500) | yes | Event location |
| external_provider | VARCHAR(50) | yes | Calendar provider |
| external_event_id | VARCHAR(500) | yes | Provider event ID |
| created_by_id | BIGINT | yes | Creator |
| created_at | TIMESTAMPTZ | no | Creation timestamp |
| updated_at | TIMESTAMPTZ | no | Last update |

## Constraints

```text
CHECK ends_at >= starts_at
```

## Foreign keys

```text
calendar_events.case_id
    → cases.id
    ON DELETE CASCADE
```

```text
calendar_events.created_by_id
    → users.id
    ON DELETE SET NULL
```

## Indexes

```text
INDEX calendar_events_case_id_idx
INDEX calendar_events_starts_at_idx
INDEX calendar_events_external_event_id_idx
```

---

# 9. Dictionary tables

Dictionary tables provide structured filtering while allowing administrators to extend business categories.

# 9.1 case_statuses

## Columns

```text
id
code
name
description
sort_order
is_active
```

## Initial values

```text
new
qualification
inspection
offer_preparation
offer_sent
negotiation
accepted
scheduled
in_progress
completed
cancelled
archived
```

`code` is unique and stable.

`name` is display text.

---

# 9.2 object_types

Examples:

```text
house
apartment_building
warehouse
production_hall
office
commercial_building
bridge
road
airport
parking
industrial_floor
other
```

## Columns

```text
id
code
name
description
is_active
```

---

# 9.3 problem_types

Examples:

```text
floor_settlement
foundation_settlement
voids_under_slab
soil_instability
soil_stabilization
water_infiltration
cracks
uneven_floor
other
```

## Columns

```text
id
code
name
description
is_active
```

---

# 9.4 technology_types

Examples:

```text
geopolymer_injection
slab_lifting
foundation_lifting
soil_stabilization
void_filling
traditional_underpinning
other
```

## Columns

```text
id
code
name
description
is_active
```

---

# 9.5 document_types

Examples:

```text
email
offer
contract
invoice
photo
drawing
technical_report
soil_test
inspection_report
protocol
correspondence
spreadsheet
other
```

## Columns

```text
id
code
name
description
is_active
```

---

# 9.6 industries

Examples:

```text
food
logistics
manufacturing
construction
retail
public_sector
residential
agriculture
automotive
other
```

## Columns

```text
id
code
name
description
is_active
```

---

# 10. Audit table

# 10.1 audit_logs

Stores important changes to business entities.

## Columns

| Column | Type | Nullable | Description |
|---|---|---:|---|
| id | BIGINT | no | Primary key |
| user_id | BIGINT | yes | Acting user |
| entity_type | VARCHAR(100) | no | Entity type |
| entity_id | BIGINT | no | Entity identifier |
| action | VARCHAR(50) | no | Action type |
| old_values | JSONB | yes | Previous values |
| new_values | JSONB | yes | New values |
| metadata | JSONB | yes | Additional context |
| ip_address | VARCHAR(64) | yes | Source IP |
| created_at | TIMESTAMPTZ | no | Creation timestamp |

## Action examples

```text
create
update
delete
restore
assign
unassign
approve
reject
login
```

## Foreign key

```text
audit_logs.user_id
    → users.id
    ON DELETE SET NULL
```

## Indexes

```text
INDEX audit_logs_entity_idx
INDEX audit_logs_user_id_idx
INDEX audit_logs_created_at_idx
```

Audit logs should not be deleted automatically when a business entity is deleted.

---

# 11. Search architecture

Business search uses three layers.

## 11.1 Structured filters

PostgreSQL filters:

```text
realization date
object type
problem type
technology
industry
client
location
case status
assigned user
```

## 11.2 Semantic search

Qdrant searches Document Chunk embeddings.

Each Qdrant point should contain payload metadata such as:

```json
{
  "chunk_id": 123,
  "document_id": 45,
  "case_id": 12,
  "client_id": 7,
  "document_type": "technical_report",
  "object_type": "production_hall",
  "problem_type": "floor_settlement",
  "technology_type": "geopolymer_injection",
  "realization_year": 2025
}
```

PostgreSQL remains the source of truth.

Qdrant payload is a searchable projection.

## 11.3 AI reasoning

AI combines:

```text
structured query results
+
semantic search results
+
case relationships
+
conversation context
```

AI must provide source references for business answers.

---

# 12. Knowledge graph readiness

A separate graph database is not required initially.

The relational schema supports future graph projection through explicit relationships:

```text
Client
→ Contact

Client
→ Case

Case
→ Location

Case
→ Object Type

Case
→ Problem Type

Case
→ Technology

Case
→ Document

Document
→ Chunk

Document
→ AI Extraction

Email
→ Contact

Email
→ Case
```

A future Neo4j integration may project these entities and relationships without redesigning the PostgreSQL database.

---

# 13. Deletion strategy summary

| Parent | Child | Strategy |
|---|---|---|
| Client | Contact | RESTRICT |
| Client | Case | SET NULL |
| Client | Document | SET NULL |
| Case | Case Contact | CASCADE |
| Case | Document | SET NULL |
| Case | Email | SET NULL |
| Case | Note | CASCADE |
| Case | Task | CASCADE |
| Case | Calendar Event | CASCADE |
| Document | Chunk | CASCADE |
| Document | AI Extraction | CASCADE |
| Document | AI Job | CASCADE |
| Email | Email Attachment | CASCADE |
| User | Assigned business records | SET NULL |
| Dictionary value | Business record | RESTRICT or SET NULL depending on field |

Important business entities should normally use soft deletion instead of physical deletion.

---

# 14. Implementation order

The schema will not be introduced in one migration.

Implementation will be incremental.

## Phase 1 — Client domain

```text
industries
clients
contacts
```

## Phase 2 — Case domain

```text
case_statuses
object_types
problem_types
technology_types
locations
cases
case_contacts
```

## Phase 3 — Document domain

```text
document_types
extend documents
extend document_chunks
```

## Phase 4 — Communication

```text
emails
email_attachments
```

## Phase 5 — AI processing

```text
ai_jobs
ai_extractions
case_match_proposals
```

## Phase 6 — Operations

```text
notes
tasks
calendar_events
audit_logs
```

Every phase must include:

1. SQLAlchemy models
2. Alembic migration
3. Pydantic schemas
4. Repository
5. Service
6. Router
7. Automated or manual tests
8. Git commit

---

# 15. First implementation scope

The first implemented domain will include:

```text
Industry
Client
Contact
```

The first Client API should support:

```text
POST   /api/v1/clients
GET    /api/v1/clients
GET    /api/v1/clients/{client_id}
PATCH  /api/v1/clients/{client_id}
DELETE /api/v1/clients/{client_id}
```

Contact endpoints will be added after the Client CRUD is stable.

The existing `schemas/case.py` file is legacy code and must not be used as the foundation for the new Case domain.

It will be replaced when the Case module is implemented.
