# Checkpoint — D-22 CRM automation policy

Checkpoint UTC: `2026-09-19T22:00:56Z`

Entry HEAD: `30e4dbf2352c765376e56829f15dab44f832686a`

Branch: `recovery/next-stabil-repair-completion`

## Zakres

Właściciel rozszerzył istniejącą D-22 bez tworzenia nowej decyzji, pakietu ani
roadmapy. Poprzednia publikacja D-22 na
`6cb706741d3e35afb2d790bf399a91e93a2d3202` pozostaje jej pochodzeniem, a nie
punktem cofnięcia bieżącego HEAD. Kolejność po zakończeniu i właścicielskim
odbiorze R04 pozostaje:

`ARKUSZE -> KOREKTA I WALIDACJA KLIENTÓW -> TYLKO NIEPRZYPISANE MAILE`.

Utrwalona polityka przyszłej implementacji:

| Zdarzenie | Wymagany skutek |
|---|---|
| Poprawny nowy wpis arkusza | Jeden klient utworzony lub powiązany bez kandydata arkuszowego i bez akceptacji per wiersz |
| Zmiana powiązanego wpisu | Nowa informacja/wersja przy tym samym kliencie oraz zachowana poprzednia wartość i provenance |
| Wyczyszczenie lub usunięcie w Sheets | Zdarzenie źródłowe bez usunięcia klienta, kontaktów, dokumentów, relacji lub historii |
| Mail jednoznacznie dopasowany | Powiązanie z istniejącym klientem bez nowego kandydata |
| Mail niedopasowany | Jeden właściwy kandydat mailowy; awaria techniczna nie jest `no-match` |
| Późniejszy klient lub kontakt | Automatyczne rozwiązanie jednoznacznego kandydata po e-mailu **LUB** telefonie, bez zmiany pól klienta z maila |
| n8n co 15 minut | Przyrostowe nowe kwalifikujące się maile oraz nowe i zmienione rekordy Sheets, ze stabilnymi checkpointami i bez drugiego schedulera |

Historyczne pola klientów nadal wolno naprawiać wyłącznie z zatwierdzonych
arkuszy. Poprawne, ręczne, potwierdzone, główne i świadomie puste wartości są
chronione. Poczta nie jest źródłem tych pól, a już przypisanych wiadomości nie
wolno ponownie analizować ani przepinać w kampanii historycznej.

## Stan wykonania

`DOCUMENTATION_ONLY / CURRENT_R04_SCOPE_UNCHANGED /
NO_PRODUCT_OR_DATA_OPERATIONS`.

Nie wykonano audytu danych, Sheets/Gmail/n8n, modeli, SQL, importu, tworzenia
klientów, merge/delete, deploymentu, runtime, UAC ani testów produktu. Historia
zmian, automatyczne tworzenie/powiązanie i harmonogram 15 minut pozostają
wymaganiami `NOT_RUN`, a nie dowodem działania.

Aktywnym checkpointem operacyjnym pozostaje
`20260919T212059Z-R04-D21-P4B-RUN01-PARTIAL.md`; R04/P4-B nadal jest
`PARTIAL_AFTER_FAILURE / HOST_TASK_FAILED_22`, a jego zgody i warunki STOP nie
zostały zmienione. D-21 pozostaje nienaruszone.

## Walidacja i następny krok

Zachowano jedną D-22, 22 decyzje, 25 pakietów i mapowania 108/36/61/16.
Lokalna walidacja potwierdziła poprawny JSON/CSV, pojedyncze lustra R12/R16/
R20/R22 ze statusem `PLANNED`, 33 pozycje mapy D-21, wymagane referencje,
secret scan `0` i `git diff --check` PASS. Jawna allowlista stage obejmuje
wyłącznie siedem dozwolonych plików dokumentacyjnych. Remote readback jest
czynnością po commit/push; checkpoint nie wpisuje przyszłego SHA.

Następny krok operacyjny nie zmienia się: owner review faktycznego wyniku R04
P4/B i osobna decyzja o ewentualnej diagnostyce kodu Host `22`. D-22 zaczyna się
dopiero po zakończeniu i odbiorze R04.
