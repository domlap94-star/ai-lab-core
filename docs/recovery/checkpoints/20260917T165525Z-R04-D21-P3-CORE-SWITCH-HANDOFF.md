# Checkpoint R04 / D-21 / P3 — core backend source switch handoff

- UTC: `2026-09-17T16:55:25Z`
- parent local/tracking/remote: `78bcf70edc7ed787b377e38461e84c1b4149a29f`
- OP_ID: `R04-D21-P3-CORE-SWITCH-20260917T141404Z`
- selected source: `0ee0ea50943578e6e552aae23ce1688595ddc262`
- payload aggregate: `7A65EDFC8E18B4B1B592A5DDEB1EBFA5C2CA85762260299157E7132AEE48B055`
- override SHA-256: `F99BABA92A72DFA366367470181AB1BF9DEC19D71ADBD2CBF1632F0B74DE4E86`
- operation plan SHA-256: `8F5691A5504FE01213C97502D20B2517FF172A641092629413FD08F64FE31E78`
- result: `CORE_BACKEND_SOURCE_SWITCH_READY_FOR_REVIEW / LIMITED_RUNTIME_VERIFIED`

## Wykonana operacja

Po zatwierdzeniu dokładnego okna właściciela wykonano jedną operację backend-only:

1. stary backend `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`
   został raz zatrzymany w sposób kontrolowany;
2. dotychczasowy `C:\ai-lab-core\backend` został przeniesiony do dokładnego
   katalogu rollback, a zweryfikowany payload `592` plików / `5 061 238` B
   został zainstalowany pod kanoniczną ścieżką;
3. zainstalowano dokładny zatwierdzony override i wykonano jeden
   `compose up` tylko usługi backend z `--no-deps --no-build --pull never
   --force-recreate`;
4. nowy backend ma pełne ID
   `686ac37663ad369f253eb91da4364aa2bd6c16c77b1205cc41d61c68d4d9c854`,
   ten sam image
   `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`,
   `/app=C:/ai-lab-core/backend:ro` i niezmienione
   `/data=C:/ai-lab-core/data:rw`;
5. rollback nie był potrzebny i nie został wykonany.

Wrapper odnotował dwa błędy formatowania pustego stdout/stderr już po
skutecznym zakończeniu natywnych poleceń. Operacji nie powtórzono. Pierwszy
agregat runtime różnił się wyłącznie kolejnością wpisów; rozstrzygające
porównanie per-file potwierdziło `592/592`, `missing=0`, `mismatch=0`,
`extra=0`.

## Wynik ograniczonej weryfikacji runtime

- backend i Public Gateway odpowiadają `200`; publiczne `/control*` pozostaje
  `404`; unauthenticated auth/clients/documents pozostają `401`;
- `/version` raportuje source `0ee0ea50943578e6e552aae23ce1688595ddc262`
  oraz schema `followup_assistant_chat_history_20260829`; pełna tożsamość
  pozostaje `UNVERIFIED / runtime_configuration=REVIEW_REQUIRED`, ponieważ
  globalny manifest nie został zatwierdzony;
- zainstalowany override ma zatwierdzony hash, lecz lokalny pakiet dowodowy nie
  zachował niezależnego runtime readbacku wartości flag; ich efektywny stan
  pozostaje `NOT_VERIFIED`, a deklaracja override nie jest obserwacją runtime;
- końcowy odczyt PostgreSQL był read-only: schema i Administrator `1/1`
  zgodne, DB `743 888 563` B, brak restore/import, pending nadal `18/16/1`;
- pięć pozostałych kontenerów zachowało pełne ID i czas startu;
- Supervisor i Private Gateway pozostały nieuruchomione, Public Gateway działa;
- junction `C:\ai-lab-core\data -> D:\ai-lab-data`, dane, harmonogramy,
  kolejki i mount `/data` nie zostały zmienione.

Końcowe zasoby: Windows available `7 694 639 104` B, commit reserve
`39 732 572 160` B, Docker/WSL available `15 885 901 824` B, swap used `0` B,
D: free `917 942 157 312` B.

## Zachowanie pracy i dowodów

Manifest R00 ma nadal kompletne `203/203` wpisy: `116` ma identyczne hashe na
oryginalnych ścieżkach, a `87` wpisów backendowych ma identyczne hashe w
kontrolowanym katalogu rollback. Brak missing i mismatch. Oryginalny worktree
pozostaje na `main@72950657ac79b50d0afe72753632ba4cde810b95`; jego bieżący status
odzwierciedla świadomie zainstalowany backend i nie jest przywracany/resetowany.

Lokalny indeks obejmuje `32` pliki / `180 781` B, SHA-256
`6D6354AC5D458919149ABC5DBD44C409CF67E7917A98ED57BD18DDEEE7F62085`.
Podsumowanie operacji ma SHA-256
`D4DDDC8702903419BA16FEBA7A6AD342E49727AB9B75BC36DE0F2208235C26B6`.
Surowe logi pozostają `LOCAL_ONLY`; do Git trafia wyłącznie ten zanonimizowany
checkpoint i zaktualizowane istniejące rejestry.

## Granice i następny krok

`DELTA_NOT_FULLY_OBSERVED`, ograniczenia punktu rollbacku i proceduralne
odstępstwa wcześniejszego drillu pozostają zapisane. Nie wykonano migracji,
restore danych, relokacji, task install, startu Supervisora, modeli, eksportu,
P4/P5 ani cleanupu. R04 pozostaje `IN_PROGRESS`, a globalny manifest
`NOT_APPROVED_FOR_START`.

Następny krok to review tego ograniczonego backend switch i jego dowodów.
Bez osobnej zgody nie wolno kontynuować do P4/P5 ani wykonywać kolejnej
mutacji runtime.
