# P0 KB synthesis and Client document discovery

Date: 2026-08-26

Source baseline: `272de1081311054d11cf756377bda2b3b4b37366`

Stable: `NEXT Stabil 1.0.2+29`

Decision: `P0_KB_SYNTHESIS_DOCUMENT_DISCOVERY_RESOLVED_PHYSICAL_RETEST_REQUIRED`

## Owner evidence and root causes

Android +38 proved exact Knowledge Base resolution and provenance for the
current `fundamentowanie` item, but the answer was a concatenation of extracted
page fragments. The fast path in `UnifiedAssistantService` copied the first two
retrieved excerpts directly into FACT claims and joined them as the answer.
The title query also ranked title/bibliographic pages 1, 2 and 3 ahead of
technical content. This was an extractive source preview, not a product answer.

The descriptive Client-document resolver compared query tokens only with the
filename and required two overlaps. A bounded production control for the
physical defect class found three active documents in one Client scope. The
target's old filename overlap was `0`; its persisted content had six relevant
technical concept hits. The old resolver therefore returned `NOT_FOUND`
before content access. The exact owner-selected document ID was not durably
recorded in request logs, so the report does not guess it or include any Client
identity, filename, address or document content.

The Flutter answer widget rendered every non-pending response. An empty
terminal `review_required` result therefore received the same empty-source
caption as an accepted general-knowledge answer, even though no model answer
existed.

## Knowledge Base synthesis

Exact-item resolution, current-only filtering, page provenance, privacy and
the canonical KB collection remain unchanged. For overview requests, the
service now reads at most 400 pages of the already selected current item,
scores bounded sentences for technical substance, penalizes title/header,
authorship, copyright, table-of-contents and high-digit noise, deduplicates the
result and selects at most five page excerpts.

The selected original pages are mapped into a deterministic technical concept
overview. Each human-readable insight is generated from a bounded concept
classification and cites only pages on which its supporting terms occur. The
answer is a short list of material technical areas rather than copied text.
Original pages remain the truth; the accepted local analysis artifact is only
an optional aid when it is both accepted, page-compatible and sufficiently
rich. The live artifact was structurally accepted but contained only one
technical value and no definitions, constraints, standards, applicability,
exceptions, examples or formulas, so it was correctly excluded.

A compact Qwen synthesis remains a local-only fallback for materials that do
not yield at least two safe concepts. It retains the existing one-correction
limit and KB external privacy block. A direct Qwen variant on the production
item hit the 105-second local deadline and returned the controlled timeout at
106.65 seconds, so it was not selected as the primary overview path.

The usefulness gate rejects fewer than two material claims, a short/empty
overview, header/bibliographic domination and near-verbatim claim copying. For
the live item, substantive ranking selected pages 22, 24, 44, 45 and 48 instead
of the title-heavy 1, 2 and 3. Ten exact read-only repetitions produced 10/10
`accepted_local`, five claims, no model, no external work and no errors; p50
was 0.039 seconds and bounded p95 0.349 seconds. Post-reload live smoke returned
five claims and three actually used page Sources in 0.488 seconds. No KB text
is included in this report.

## Client-scoped semantic document discovery

Discovery now has two deterministic stages inside the SQL allowlist of active
documents belonging to the selected Client:

1. weighted filename/metadata matching, with a local-only Client-address
   signal and a uniqueness margin;
2. if metadata is insufficient, read-only content relevance over at most 12
   likely same-Client documents through `UnifiedDocumentContentService`.

The second stage reuses persisted extraction/OCR or the checksum-gated
ephemeral native reader. It uses a bounded technical vocabulary expansion and
does not load Qwen. It returns `UNIQUE_MATCH`, `AMBIGUOUS`, `NOT_FOUND` or the
specific content-unavailable state. Up to four same-Client filenames are
included in an ambiguous response so the operator can choose; no global
repository widening occurs. Client address tokens are used only for local
selection and never enter reasoning evidence.

The production read-only control described above now returned `UNIQUE_MATCH`
for the exact target in a three-document Client scope, based on six content
hits despite zero filename hits. The resolved ID matched the preselected
control row. IDs were hashed in diagnostic output and no content was printed.
Global customer Qdrant search was deliberately not used because historical
point ownership is not sufficiently reliable; no vector backfill or write was
performed.

After resolution, the existing read-only document content service supplies
actual evidence. Relevant technical questions can still add current KB
reference evidence, while case facts and general reference rules remain
separate and claim-bound.

## Sources UX

Flutter now renders an answer and Sources inspector only for a non-empty
`accepted_local` or `accepted_advanced` result. `NOT_FOUND`, `AMBIGUOUS`,
unavailable, timeout and cancellation states show their bounded error without
claiming a general-knowledge answer. An accepted source-free general answer is
labelled simply as general knowledge; it no longer says that Client sources
were absent when the active domain is KB or when no answer was produced.

## Verification

- focused Unified/KB/document backend after expanded quality matrix: 163/163 PASS;
- broader Unified/KB/document/contract/Advanced/Temp Chat: 171/171 PASS;
- exact live KB repeatability: 10/10 PASS, wrong source 0, raw-noise failure 0;
- live descriptive same-Client control: `UNIQUE_MATCH`, correct target PASS;
- Flutter focused Assistant: 5/5 PASS;
- Flutter analyze: PASS, zero issues;
- full Flutter: 306/306 PASS;
- saved immutable F0 local replay: 35 local cases accepted, overall 88.00,
  factual/evidence 100.00%, technical documentation 97.37, cross-domain 88.00,
  wrong sources 0, privacy failures 0 and hard failures 0. The unchanged
  qualified saved external artifacts remain historical proof for the 15
  Advanced cases; no new external request was sent.

Backend was actually restarted and its mounted-source SHA-256 matched the host
source. Backend health and the guarded public ingress passed; `/control`
remains unavailable publicly. Supervisor source did not change and was not
restarted.

## Android and safety

Flutter changed, so +38 is consumed and superseded. The new non-stable owner
candidate is:

- `C:\ai-lab-core\staging\android\NEXT-Stabil-1.0.2+39-kb-synthesis-document-discovery-candidate.apk`;
- version `1.0.2+39`, application ID `pl.ailab.app`;
- SHA-256 `CC54559EEE3C1648058B099BD11CA4CDB3D883090E7B15ADB199BA4482B33DB9`;
- signer SHA-256 `5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`;
- release non-debuggable, cleartext disabled, canonical public API supplied;
- published: no.

DB migrations, business/Client/Document/KB writes, Qdrant writes/deletes,
external proprietary KB jobs, Gmail, n8n, model pulls/deletes, backup deletion,
Tailscale changes and publication are all zero.

Status: `SOURCE/RUNTIME PASS / OWNER PHYSICAL RETEST REQUIRED`. PRE-CHUNK23
remains physical acceptance required. CHUNK23 remains blocked/not started.
Release F Ignore Mail address/domain reminder remains unchanged.
