# AI Lab - Data Flow

## General Rule

Every source is processed by the same pipeline.

The source never decides where data goes.

Only AI decides.

---

# Sources

- Gmail
- Manual Upload
- Local Folder
- OneDrive
- Google Drive
- NAS
- API

↓

Importer

↓

Raw Document

↓

OCR (if required)

↓

Text Extraction

↓

AI Extraction

↓

Entity Recognition

↓

Similarity Search

↓

Case Matching

↓

Human Review (optional)

↓

Case Update

↓

Chunking

↓

Embeddings

↓

Qdrant

---

# AI Extraction

AI extracts structured information.

Example:

Client

Address

Object Type

Problem Type

Technology

Project Number

Offer Number

Phone

Email

Dates

Keywords

Confidence

---

# Case Matching

The system compares:

existing Case

↓

new document

↓

confidence score

↓

Decision

---

# Confidence Levels

95-100%

Automatic assignment

80-95%

Assignment proposal

Below 80%

Needs human review

---

# Chunking

Only after the document belongs to a Case.

---

# Embeddings

Created only for processed chunks.

---

# Search

Hybrid

↓

Metadata filters

+

Semantic Search

+

AI reasoning

---

# Final Goal

The AI should answer business questions.

Not document questions.