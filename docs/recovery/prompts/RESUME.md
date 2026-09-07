# NEXT_STABIL — wznowienie z Git, bez nowego planu

Wznów według wspólnego stanu projektu:
- repo `domlap94-star/ai-lab-core`;
- gałąź `recovery/next-stabil-repair-completion`;
- plik `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md`, najpierw §0;
- lokalny worktree ustal z Git; proponowany `C:\ai-lab-core-recovery` nie jest
  dowodem, że istnieje albo że jest właściwym katalogiem.

Przed wykonaniem czegokolwiek porównaj lokalny i zdalny SHA, stan drzewa oraz
aktywne sesje; nie pull/reset/stash/rebase/checkout w ciemno. Jeżeli wspólna
gałąź nie istnieje, nie twórz planu od nowa: R00 publikacji nie jest potwierdzone.

Przeczytaj AGENTS, masterplan, followup, kartę aktywnego pakietu i ostatnią
notatkę przekazania. Sprawdź zmiany od checkpointu, dostępność lokalnej kopii
WIP oraz rzeczywisty wynik ostatniej operacji. Nagły crash nie dowodzi ani
zakończenia, ani braku skutków. Nie powtarzaj migracji, wysyłki czy apply w ciemno.

Wykonaj tylko wskazany pozostały podetap w zakresie uprzednio udokumentowanej
zgody. Samo „wznów” nie zatwierdza nowego pakietu, usunięcia roadmap, migracji,
deploy, zmian danych, secrets/escrow, modeli ani live testów. Przy
WAITING_APPROVAL/BLOCKED lub nieweryfikowalnej zgodzie podaj konkretną bramkę
i zatrzymaj wykonanie tej operacji, bez kolejnego pełnego audytu.

Zachowaj Qwen 9B, KB i Temporary Chat. Nie twórz nowej roadmapy. Po znaczącym
podetapie i przed końcem sesji zaktualizuj istniejący checkpoint oraz pochodne
statusy; zabezpiecz niezacommitowaną pracę. Bezpieczny doc commit/push na
wskazaną gałąź jest elementem bieżącego przekazania, source tylko według
zgody pakietu. Sprawdź remote i podaj ROADMAP_SYNCED@SHA albo LOCAL_ONLY,
aktualny etap, wynik, blokadę i jeden następny krok. Nie oznaczaj sam ACCEPTED.
