# R04 / D-21 / P4-B — Host identity continuity

UTC: `2026-09-21T16:19:18Z`

Status: `P4B_STAGEA_HOST_IDENTITY_CONTINUITY_SOURCE_READY_FOR_REVIEW /
OFFLINE_TESTS_PASS / NOT_DEPLOYED`.

## Wynik K1

`REPRODUCED / FIXED_OFFLINE`.

Preflight Stage-A dopuszczał zachowany Host raw XML `85C4...` przez przypięty
comparable hash `7BBC...`, lecz świeże Register/Start/Rollback sprawdzały tylko
raw hash docelowego XML. Pełna orkiestracja na zachowanym preimage zatrzymała
się po czterech własnych zmianach fixture, przed leaf Register, z warm `0`.
Dowód fail-before: `876` B, SHA-256
`C7D0D1E95ED4A2F5158B998ACA269BF2DDBA1188DFDF53655B2630F1A590587F`.

Pochodna LOCAL_ONLY dopuszcza wyłącznie przypięty raw hash albo przypięty
comparable hash dla stanów preimage/disabled/on-demand/logon. Action,
principal, trigger, enabled, bezczynność, pending-operation i journal pozostają
niezależnymi obowiązkowymi guardami. Obcy raw+comparable, obca semantyka,
UNKNOWN lub aktywny Host nadal blokują zapis i destrukcyjny cleanup.

## Końcowe bajty i testy

- recepta: `64630` B, SHA-256
  `FD8DB2C5491E7A8835CC01734A8A902D67F606F29A4436A68A16096A44CBBCFE`;
- harness: `51735` B, SHA-256
  `75BDB800C58D54993C23970634FDE9B960BF5CDEB361524A6F26F752E09CAD79`;
- package index: `8923` B, SHA-256
  `0BC434D97847836CD54C2D847B23795614F684633013DFDCDA1F76AF7C966CDD`;
- final result: `824` B, SHA-256
  `9E51AB3B63B8DBC065F5B8B9300F4E517CAC25E96FEBC01B9D1C2BDB9E0954E2`;
- review index: `13034` B, SHA-256
  `7630D7A18FD59D93D7DC8B278C983124769B9B002879F73B25D4E0BFF6FB0D3A`;
- review ZIP: `184681` B, SHA-256
  `F0BE2DB31081458890873325DE8448C1D65F8ED57CF20C5D724F66A64FB88298`.

Końcowa kampania Windows PowerShell 5.1: `91` asercji / `26` scenariuszy,
Host starts `2`, Private `1 -> 0`, container/Supervisor/unapproved/
dependency-task writes `0`, własne procesy `1/1`, unsettled `0`, produkcyjne
granice `0`. Parser PS 5.1, bindingi payloadu `8/8`, JSON `18`, CSV `1` oraz
ZIP roundtrip/index `52/52` przeszły. ZIP nie zawiera capture raw XML.

Paczka:
`C:\Users\domai\AppData\Local\Temp\P4B-HOST-ID-01\R04-D21-P4B-STAGEA-HOST-IDENTITY-REVIEW-20260921T161823Z.zip`.

## Stan i STOP

Review D-23 pozostaje `2/2`; Host22 i NUP-01/02/03 zachowują odbiory. Nie
zmieniono run01, zainstalowanych plików, tasków, usług, kontenerów, danych ani
manifestu produkcyjnego. HTTP, live VerifyOnly, UAC, Stage B, InstallAndWarm,
Host retry i rollback hosta są `NOT_RUN / NOT_AUTHORIZED`. Warm pozostaje `0/2`,
Host historycznie disabled/no-trigger, Supervisor `INTENTIONALLY_STOPPED`.

Następny krok: niezależny review wyłącznie tego diffu i bezpośrednich regresji;
przy PASS rekomendować odbiór bez poszukiwania K2/K3.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną i kolejnym promptem przeczytaj §0, ANTI_EXCESSIVE_WORK, aktywną
kartę i ten checkpoint na SHA raportu. Zachowaj odbiory. Naprawiać tylko
wykazany istotny wpływ; K2/K3 nie ruszać, nie blokować nimi odbioru i nie
tworzyć automatycznych zadań naprawczych. K0/K1: K1 ciągłości Host — bez tej
zmiany semantycznie ten sam przypięty Host może przejść preflight, a następnie
zablokować Register/Start/Rollback; dowód fail-before `C7D0D1...0587F`.
Efekt: fresh operations uznają wyłącznie pinned raw albo pinned comparable i
zachowują pozostałe guardy. Cykl: review `2/2` zakończony i niezerowany.
Następny krok: weryfikacja wyłącznie tego uzupełnienia; brak zgody na operacje
hosta.
