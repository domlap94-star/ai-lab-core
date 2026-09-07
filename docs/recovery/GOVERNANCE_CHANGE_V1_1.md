# Zmiana v1.0 → v1.1 — wspólny stan wykonania

2026-09-07, cel zgłoszony przez właściciela: roadmapa w lokalnym repo i GitHub,
aktualizowana do przerwania/wznowienia. To rozszerzenie sterowania pracą, nie
kolejny plan produktu. Plik kanoniczny zachowuje nazwę.

Zmiany: §0 roadmapy (wspólny checkpoint i jeden rejestr statusów), reguły
checkpoint commit/push, R00 (ograniczony bootstrap dokumentacji), R01 (nie
publikuje ponownie roadmapy), ścieżki załączników docs/recovery oraz prompt
wznowienia. R02–R24 zachowują cel, zakres i warunki odbioru v1.0; status kart
wskazuje teraz jeden rejestr. Decyzja D-01 oddziela rejestrację od operacyjnych
zgód. Pozostałe wymagania, findings i kandydatury zachowane.

Nie wykonano publikacji w Git, żadnego pakietu, testu systemu, wdrożenia ani
usuwania plików. READY_FOR_R00_REGISTRATION to stan materiału wejściowego.
Dopiero rzeczywisty Codex preflight/push/odbiór mogą zmienić checkpoint i statusy.

Dokumenty wzorcowe do instalacji są w jawnej liście promptu; README paczki i
input_only nie mogą nadpisać README repo ani trafić w całości do Git. Raw logi,
sekrety, artefakty binarne i kopie pracy pozostają poza repo.
