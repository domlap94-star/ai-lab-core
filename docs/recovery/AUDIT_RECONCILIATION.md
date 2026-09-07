# Uzgodnienie audytu Codexa z materiałem źródłowym

Data: 2026-09-07. Charakter: **przegląd dowodów i korekty planowania; nie kolejna roadmapa i nie nowy audyt runtime**.

## 1. Co niezależnie sprawdzono

Otrzymany `NEXT_STABIL_FULL_AUDIT_20260907.zip` ma SHA-256:

`B38CF3DA7CB2699C97891DBC64FE03B4770D1E86F7C90A5280D9A72AC15CF2F9`

Hash jest identyczny z podanym przez Codexa. Archiwum ma 15 wpisów, kontrola CRC wszystkich wpisów przechodzi. Wypakowanie nie wymagało uruchamiania kodu z archiwum. Wczytano wszystkie rejestry CSV/JSON i tekstowe raporty. Liczby potwierdzone parserem: 108 wymagań (73 M + 35 F), 36 ustaleń, 1274 rekordy inwentarza i 61 kandydatów. Początkowy i końcowy manifest zawierają te same 203 ścieżki oraz identyczne wartości wszystkich pól po parsowaniu; różnica bajtów pliku CSV nie jest różnicą danych. `WORKTREE_DRIFT.csv` ma 0 wierszy danych.

1274 to liczba rekordów inwentarza, nie liczba niezależnych fizycznych plików: 6 zmienionych tracked ścieżek występuje również w części dirty. Nie wyliczano procentu gotowości.

Odczyt GitHub podczas tej analizy potwierdził `main=483f9bf8b1a591ded8a42df5da87663c664ed5d4` i `rescue=5cd8f86e63e1ab829692ca2601096fd0c0d9d53a`. To odczyt Git, nie dzisiejszy pomiar zainstalowanej produkcji. Przeczytano właściwe sekcje kanonicznego masterplanu/followup oraz sporny fragment kodu rescue. Nie wykonywano lokalnych testów NEXT Stabil, model calls, zmian Git ani wdrożeń.

## 2. Korekty i ograniczenia dowodowe

### C-001 — brak historycznego manifestu wewnątrz ZIP

`ARTIFACT_MANIFEST_SHA256.csv` jest wymieniany w raportach i odpowiedzi Codexa, ale **nie znajduje się w otrzymanym archiwum**. ZIP zawiera dokładnie pozostałe 15 wpisów. Nie jest to dowód uszkodzenia ZIP: całościowy hash jest zgodny. Nie można jednak niezależnie porównać hashy składników z deklarowanym manifestem historycznym. Wygenerowano `SOURCE_ARCHIVE_MEMBER_HASHES.csv` z otrzymanych bajtów, jawnie jako nowy pomiar. R00 ma odszukać pierwotny manifest w katalogu audytu; brak manifestu nie wymaga powtarzania całego audytu.

### C-002 — opisy testów są szersze niż przekazane reprodukcje

`TEST_EVIDENCE.md` zawiera komendy/oczekiwania/wyniki, natomiast w ZIP nie ma pełnych surowych logów ani trwałych skryptów reprodukujących REP-001–004. `reproductions/README.md` wyraźnie opisuje ich wykonanie bez zachowanych plików; dołączony kod to fixture Android JSON. Nie nazywam wyników fałszywymi, ale nie przedstawiam ich jako niezależnie powtórzonych. R02 zapisze testy rzeczywistych modułów i logi dla zmienianych granic; nie uruchamia całej produkcji na ślepo.

### C-003 — błędne powiązania ID w REPAIR_INPUT

Część propozycji ma niewłaściwe identyfikatory wymagań. Przykłady: FIX-01/COMPLETE-01 wskazują F-016, które w macierzy oznacza Admin Backup UI, nie Visual. FIX-02 kieruje do M-026…M-032 (m.in. strony/assets/OCR/pipeline), choć błędy routingu/retrieval należą bezpośrednio do M-039/M-040/M-041/M-042/M-046/M-054/M-055. Nie skopiowano tych odwołań. Nowe mapowanie powstało z opisów wymagań, rejestru FND i źródeł kanonicznych. Oryginał pozostaje niezmieniony w `evidence/`.

### C-004 — wynik main nie obala problemu supplemental Visual w rescue

Raport obala twierdzenie absolutne „Visual zawsze wypiera KB” na main. Wcześniejszy konkretny zarzut dotyczy innej ścieżki, dostępnej na rescue. W `unified_assistant_service.py` na `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a` limit wynosi 8, po dodaniu KB znajduje się osobny blok:

```python
bounded = self.supplemental_sources[:MAX_SOURCES]
sources = sources[: max(0, MAX_SOURCES - len(bounded))]
```

Dla osiągniętej listy 5 źródeł sprawy + 3 KB i czterech supplemental Visual odcięcie zostawia pierwsze 4 bez KB. To **CODE_SUPPORTED_NOT_REPRODUCED w bieżącej analizie**: nie jest nowym zaobserwowanym incydentem produkcyjnym. R08 wymaga testu rzeczywistego `_collect()` z dokładnym układem oraz kontroli actual prompt. Nie tworzę nowego 37. potwierdzonego FND, lecz powiązane sprawdzenie M-042/M-060.

### C-005 — ContactPerson B jest już zatwierdzony w followup

F-029 i komentarze do M-008 sugerują nierozstrzygnięty model osób kontaktowych. Jednak pinned followup, sekcja CHUNK26 (około linii 2067–2114), dokumentuje **wybór opcji B, zgodę na migrację, jej zastosowanie i odbiór z 22.08.2026**. Historyczny wynik nie potwierdza automatycznie dzisiejszego runtime, ale dowodzi, że nie należy ponownie pytać o A/B ani implementować tej samej encji. R20 ma zweryfikować istniejące zachowanie. Oryginalne `OWNER_DECISION` w macierzy jest zachowane, a korekta znajduje się w oddzielnej kolumnie i rejestrze D-10.

### C-006 — zalecenie włączenia flagi dla 15 jobów jest zbyt szerokie na pierwszy smoke

REPAIR_INPUT/VERIFY-01 proponuje włączenie istniejącej flagi i obserwację 15 bieżących jobów. Są to produkcyjne zadania, nie automatycznie syntetyczny test. Zmieniono kolejność na: izolowany E2E → dokładnie allowlisted mały canary po zgodzie → ewentualna osobna zgoda na większą kolejkę. Jeżeli dispatcher nie ogranicza wyboru do zadanych ID, globalnej flagi nie wolno włączyć pod pozorem testu jednej pozycji.

### C-007 — 108 pozycji jest użytecznym indeksem, nie dowodem atomowości każdego checkboxa

M-055 zbiera wiele metod obliczeniowych, M-056 zakres Internetu/norm, M-063 narzędzia agenta, a M-071 cały proces biznesowy. Masterplan zawiera też szczegółowe upload/field UX/porównania/image embeddings. Dodano 16 grup podkryteriów w `SCOPE_DETAIL_CHECKLIST.csv`, powiązanych z istniejącymi ID — bez tworzenia nowych wymagań ze starych roadmap. Nie wolno zamknąć szerokiego rodzica jednym testem szczęśliwej ścieżki.

### C-008 — brak dedykowanych tabel Visual V2 nie dowodzi konieczności migracji

Manifest odnotowuje nieobecność takich tabel; obecny rescue deklaruje wykorzystanie istniejących mechanizmów. R02/R04 sprawdzają faktyczne modele, migracje i zależności kandydata. Nie dodawać tabel tylko z powodu nazwy funkcji ani z góry zabraniać uzasadnionej migracji dla ofert/umów/obliczeń.

## 3. Co przyjęto bez zmiany treści audytu

Zachowano wszystkie 108 ID i cztery osie statusów, 36 FND i ich stopień dowodu oraz 61 dyspozycji plikowych. P0 prywatności dotyczy niepromowanego eksportu Visual, nie zaobserwowanego wycieku obecnego main. FND-024 pozostaje hipotezą; nie uzasadnia automatycznie nowego schedulera. Nie wyłączamy KB, Temporary Chat ani 9B, aby poprawić wyniki. Dane/queue/model counts są snapshotem audytu, nie stanem „teraz”.

## 4. Konsekwencja

Audyt jest wystarczającą podstawą planowania po wskazanych korektach. **Nie potrzebujemy kolejnego pełnego audytu przed R00/R01/R02.** Niewiadome trafiają do konkretnego pakietu i rozstrzygającego testu. Pierwszy realny odbiór operacyjny K1 następuje po krytycznym CRM+AI, przed dokończeniem ofert/umów, zaś pełny uzgodniony workflow ma osobny K2.

## Źródła

- Otrzymane archiwum: `evidence/NEXT_STABIL_FULL_AUDIT_20260907.zip` — oryginalne pliki AUDIT_REPORT, REQUIREMENTS_MATRIX, FINDINGS_REGISTER, REPAIR_INPUT, TEST_EVIDENCE, COVERAGE_AND_UNKNOWNS, RUNTIME_MANIFEST i manifesty worktree.
- Masterplan (wymagania i kryteria): https://github.com/domlap94-star/ai-lab-core/blob/483f9bf8b1a591ded8a42df5da87663c664ed5d4/AI_LAB_MASTER_PLAN.txt — szczególnie §7–8, §12, §23–33, §35–38, §42–47.
- Followup (reguły, privacy, scope, historia ContactPerson/CHUNK23): https://github.com/domlap94-star/ai-lab-core/blob/483f9bf8b1a591ded8a42df5da87663c664ed5d4/AI_LAB_FOLLOWUP_PLAN.md — global execution rules oraz CHUNK23–32.
- Rescue context collector: https://github.com/domlap94-star/ai-lab-core/blob/5cd8f86e63e1ab829692ca2601096fd0c0d9d53a/backend/app/services/unified_assistant_service.py — MAX_SOURCES, `_collect`, `supplemental_sources`.
