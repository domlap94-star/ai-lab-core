# Checkpoint — priorytet CRM po R04

UTC: `2026-09-19T19:30:25Z`

## Wynik

- Utworzono decyzję D-22 bez zmiany D-21 ani bieżącego zakresu R04/P4-B.
- Wiążąca kolejność po zakończeniu i właścicielskim odbiorze R04:
  `ARKUSZE -> KOREKTA I WALIDACJA KLIENTÓW -> TYLKO NIEPRZYPISANE MAILE`.
- Historyczne pola klientów wolno korygować wyłącznie na podstawie
  zatwierdzonych Excel/Google Sheets. Wcześniejszy wariant arkusze + maile jest
  zastąpiony; mail, wątek, załącznik i mailowa notatka nie są źródłem wartości.
- Etap pocztowy rozpoczyna się po walidacji klientów, obejmuje zamknięty zbiór
  wyłącznie nieprzypisanych wiadomości i zmienia tylko dozwolone powiązanie oraz
  metadane decyzji. Już przypisane wiadomości pozostają nietknięte.
- Poprawne, ręczne, potwierdzone i świadomie puste pola są chronione per pole.
- Pozostałe pilne poprawki CRM zachowano w istniejących kartach R12/R16/R20/R22;
  nie utworzono nowego pakietu ani roadmapy.

## Granice wykonania

To była wyłącznie aktualizacja dokumentacji. Audyt produkcji, Gmail/Sheets/n8n,
SQL, modele, import, naprawa danych, merge/delete, deploy oraz testy produktu są
`NOT_RUN`. Nie odnowiono zgody na live preflight, UAC, instalację lub rollback.
R04/P4-B zachowuje wcześniejszy stan
`PREFLIGHT_EVIDENCE_PARTIAL / TASK_INFO_MAPPING_ERROR_NO_REREAD / NO_UAC /
NOT_INSTALLED`, a jego następny bezpieczny krok i STOP pozostają bez zmian.

## Walidacja i wznowienie

Przed publikacją należy sprawdzić CSV/JSON, 108/36/61/16/25, 22 decyzje,
33 pozycje D-21, referencje, sekrety, `git diff --check` i jawną allowlistę.
Następny krok operacyjny pozostaje w R04; D-22 zaczyna wykonanie dopiero po jego
zakończeniu i odbiorze właścicielskim oraz po właściwych osobnych zgodach na
audyt i mutacje danych.
