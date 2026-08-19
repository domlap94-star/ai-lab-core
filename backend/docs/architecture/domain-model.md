# AI Lab - Domain Model

> Historical target-design draft. It is not the canonical description of the
> current production schema. Production is Client/Document/Inspection-centric;
> Projects are retained as legacy/read-only and no `Case` table is deployed.
> See `AI_LAB_MASTER_PLAN.txt`, `CODEX_MASTER_EXECUTION.md` and
> `FINAL_SYSTEM_AUDIT.md` for the reconciled current state.

## Główna zasada

Centralnym elementem systemu jest **Case**.

Każdy dokument, e-mail, zdjęcie, oferta, badanie gruntu lub notatka
należy do jednej sprawy (Case).

Klient może posiadać wiele spraw.

---

# Encje

User

↓

Client

↓

Case

↓

Documents

↓

DocumentChunks

↓

Embeddings (Qdrant)

---

# Źródła danych

- Gmail
- Upload
- Folder lokalny
- OneDrive
- Google Drive
- NAS
- Zdjęcia
- PDF
- DOCX
- XLSX

---

# Import

Każdy importer działa identycznie.

Importer

↓

Document

↓

AI Extraction

↓

Case Matching

↓

Chunking

↓

Embeddings

↓

Qdrant

---

# AI Extraction

AI wyodrębnia:

- klient
- adres
- telefon
- email
- numer oferty
- numer projektu
- numer działki
- rodzaj obiektu
- rodzaj problemu
- technologię
- słowa kluczowe
- daty

---

# Domyślna data

Jeżeli użytkownik nie poda rodzaju daty,
system interpretuje ją jako

realization_date

---

# Typy obiektów

- dom jednorodzinny
- blok
- kamienica
- hala produkcyjna
- hala magazynowa
- magazyn
- biurowiec
- most
- droga
- parking
- lotnisko
- obiekt przemysłowy

Lista będzie rozszerzana.

---

# Problemy

- osiadanie posadzki
- osiadanie fundamentów
- pustki pod płytą
- stabilizacja gruntu
- nierównomierne osiadanie
- zapadnięcie

---

# Technologie

- iniekcja geopolimerowa
- podnoszenie posadzki
- podnoszenie fundamentów
- stabilizacja gruntu

---

# Wyszukiwanie

System obsługuje:

- wyszukiwanie strukturalne
- wyszukiwanie semantyczne
- wyszukiwanie hybrydowe

---

# Cel

System ma odpowiadać na pytania typu:

"Pokaż wszystkie hale produkcyjne zrealizowane w latach 2023-2025."

"Pokaż wszystkie realizacje dotyczące pustek pod posadzką."

"Znajdź realizacje podobne do Lipowa 14."

"Pokaż wszystkie realizacje dla klienta XYZ."

"Pokaż wszystkie realizacje wykonane technologią iniekcji geopolimerowej."

