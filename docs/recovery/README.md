# Załączniki wspólnej roadmapy NEXT Stabil

Kanoniczny plik: [NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md](../../NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md).
Gałąź do odczytu/zapisu po R00: `recovery/next-stabil-repair-completion`.
Nie zakładaj, że dokument jest już w `main`.

## Źródło statusu i dowody

Aktualny pakiet i następny krok są w §0.1 roadmapy; statusy R00–R24 w §0.2.
PACKAGE_REGISTER.csv i PACKAGE_DETAILS.json są tylko pochodnym indeksem.
REQUIREMENT_PACKAGE_MAP.csv, FINDING_PACKAGE_MAP.csv i RETIREMENT_EXECUTION_MAP.csv
zachowują historyczne pola audytu oraz dodatkowe mapowanie do pakietów.
Oryginalne `evidence_refs` odnoszą się do materiału wejściowego audytu poza repo,
nie do obietnicy, że wszystkie dawne raw pliki znajdują się w tym katalogu.
Nowe dowody opisujemy w bezpiecznych checkpointach z datą/SHA/zakresem testu.

SCOPE_DETAIL_CHECKLIST.csv doprecyzowuje szerokie wymagania. OWNER_DECISIONS.csv
odróżnia historyczne decyzje od nowych, niekonsumowanych zgód operacyjnych.
AUDIT_RECONCILIATION.md zachowuje wcześniejsze korekty audytu; zmiany sterowania
v1.1 są w GOVERNANCE_CHANGE_V1_1.md. Nic z tego nie tworzy drugiej roadmapy.

## Integralność materiału wejściowego

Oryginalny `NEXT_STABIL_FULL_AUDIT_20260907.zip` ma hash
B38CF3DA7CB2699C97891DBC64FE03B4770D1E86F7C90A5280D9A72AC15CF2F9.
Zachowujemy go poza repo. SOURCE_ARCHIVE_MEMBER_HASHES.csv to pomiar otrzymanych
bajtów, nie brakujący oryginalny manifest Codexa.
VALIDATION.json opisuje walidację dostarczonego planu v1.1; nie jest bieżącym
pipeline PASS. Jeżeli zmieniasz uzgodniony zakres/mapowania, wykonaj nową
walidację i zapisz kiedy/na jakim SHA ją wykonano.

## Checkpointy

`checkpoints/` powstaje w R00. Każdy plik zawiera niewielki, zanonimizowany stan
przekazania (UTC, pakiet, source SHA, testy, wyniki, zgody, pozostała praca),
nie raw logi, sekrety, dane firmy albo backup. Nie twórz kopii całej roadmapy
w checkpointach. §0 wskazuje najnowszy; historyczne są dowodem, nie poleceniem.

Prompty instalowane przez R00: `prompts/R00_BASELINE.md` i `prompts/RESUME.md`.
`R00_BASELINE.md` jest po akceptacji R00 historycznym materiałem wejściowym,
nie aktywną instrukcją ponownego bootstrapu. `RESUME.md` prowadzi wyłącznie do
§0 roadmapy. Żaden z nich nie rozszerza zgód na następny pakiet.
