# Checkpoint R03-20260908T093202Z-PREFLIGHT-APPROVAL

- UTC: `2026-09-08T09:32:02Z`
- Pakiet / podetap: `R03 / PREFLIGHT FOR OPERATIONAL APPROVAL`
- Branch / worktree: `recovery/next-stabil-repair-completion` / `C:\ai-lab-core-recovery`
- Parent dokumentacji: `883987f8ba422986db6893aa993da730fa9405a2`
- Source main: `483f9bf8b1a591ded8a42df5da87663c664ed5d4`
- Source rescue: `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a`, nieadoptowane
- Poprzedni checkpoint: [`R02-20260908T065945Z-HANDOFF-C3`](20260908T065945Z-R02-HANDOFF-C3.md)
- Status: `PREFLIGHT_COMPLETE / WAITING_APPROVAL`

## Decyzja właściciela i wykonany zakres

Właściciel zaakceptował R02 na
`883987f8ba422986db6893aa993da730fa9405a2`. Historyczne i nowe wyniki R02
pozostają rozdzielone; FND-019 i REP-001–004 pozostają otwarte we właściwych
późniejszych pakietach. W R03 wykonano wyłącznie ograniczone odczyty metadanych
i przygotowano zakres do osobnych decyzji. Nie uruchomiono backupu, restore,
escrow, odczytu sekretów ani zasobów wykonawczych.

## Istniejący punkt i jego granice

Najlepszy istniejący spójny checkpoint to
`E:\ai-lab-backup\20260906T010005Z` (`Full`, run `35`, schedule `1`, UTC
`2026-09-06T01:07:36Z`). Manifest `NEXT_STABIL_BACKUP_V1` ma SHA-256
`71D8434C7D5EFCFA1DD6574421F23C89F1C9CC82012472303393E558328C46C0`,
DB revision `followup_assistant_chat_history_20260829`, source
`72950657ac79b50d0afe72753632ba4cde810b95`, release `1.0.2+29` i 7/7
istniejących artefaktów zgodnych rozmiarem i SHA-256. Historyczny proof
odtworzył 57 punktów, 1024/Cosine, bez montowania wolumenu produkcyjnego.
Checkpoint nie zawiera sekretów.

Nie wolno łączyć go w jeden punkt czasu z późniejszymi, niezależnymi kopiami
DB/n8n z `2026-09-07`. Bieżący odczyt wykazał 39/39 BackupRuns
`completed+verified`, 0 aktywnych, 0 RestoreRuns, 49/49 ManagedBackups
verified i 0 deletion events; trzy włączone harmonogramy są zsynchronizowane,
a oba cele dostępne. Wolne miejsce: C około 597 GiB, E około 738 GiB, F około
458 GiB.

Istniejący Full checkpoint nie zamyka R03:

1. zawiera tylko `ai_lab_document_chunks`; bieżący Qdrant ma dodatkowo
   `ai_lab_knowledge_base_chunks` (57 i 157 punktów, obie kolekcje green);
2. `backup-production.ps1` i format V1 opisują jedną kolekcję/snapshot, a
   walidator offline jest ograniczony do kolekcji dokumentów;
3. source checkpointu i archiwum release nie odtwarzają jednoznacznie
   bieżącego mixed runtime oraz zewnętrznych workerów wykazanych w R00;
4. `restore-checkpoint.ps1 -ProofOnly` tworzy bazę `ai_lab_restore_test_*`
   wewnątrz czynnego kontenera `postgres`, więc nie spełnia wymagania osobnego
   serwera; walidator Qdrant publikuje losowy port loopback;
5. nie potwierdzono zatwierdzonego vault/nośnika, ACL/opiekuna ani odrębnego
   miejsca recovery key. Checklist jest wymaganiem, nie dowodem escrow.

Narzędzia recovery są identyczne z `origin/main`; 4/4 hashe manifestu zgadzają
się po kanonicznym LF (roboczy checkout ma CRLF). Obecne obrazy odczytane bez
environment: backend
`sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`,
PostgreSQL
`sha256:a426e44bac0b759c95894d68e1a0ac03ecc20b619f498a91aae373bf06d8508d`,
Qdrant
`sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286`
i n8n
`sha256:3c07c723326dd72e46a6969181c66a75260b7a204b9b77ba1ece6d594489c684`.
Obraz R02
`sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`
i jego logi/snapshoty nadal istnieją `LOCAL_ONLY`, ale nie są kopią
produkcyjnego punktu odzyskania.

Wszystkie 5 znanych ścieżek Supervisor/gateway/worker z R00 nadal istnieje.
Cztery pełne hashe są zgodne z zapisanymi prefiksami. Przy
`operations/vision-worker/analysis-job.js` R00 zapisał prefiks `2D9E4B9`, a
bieżący pełny SHA-256 to
`2D9E4B0B639D052611F57C5A17AF7DAD415E5D7BAA78349C420BF3E13B2C971C`.
Nie jest to drift pliku: working tree jest clean dla tej ścieżki, a identyczny
Git blob `b05a6c3dd36939f3f1808d1f84f1d83921840f04` występuje w original HEAD,
`origin/main` i recovery. To korekta niespójności dowodu R00, nie nowa zmiana
runtime.

## Dokładny przyszły cel izolowany — jeszcze nie utworzony

| Element | Proponowana wartość / kontrola |
|---|---|
| Root | `C:\ai-lab-core-staging\recovery\R03_DRILL_20260908_A1` — obecnie nie istnieje |
| Compose project | `next-stabil-r03-drill-20260908-a1` |
| PostgreSQL container / volume | `next-stabil-r03-postgres-20260908-a1` / `next-stabil-r03-pgdata-20260908-a1` |
| Qdrant container / volume | `next-stabil-r03-qdrant-20260908-a1` / `next-stabil-r03-qdrantdata-20260908-a1` |
| Network | `next-stabil-r03-internal-20260908-a1`, `internal: true`, bez portów hosta |
| Storage target | `<root>\restored-document-storage`, zapis tylko w tym nowym celu |
| Capacity gate | co najmniej 40 GiB wolnego miejsca przed startem; to bufor operacyjny, nie RTO/RPO |
| External isolation | brak trasy do Gmail, Temporary Chat, Ollamy, n8n, produkcyjnych Supervisorów i sieci; brak produkcyjnych mountów |
| Startup containment | nie uruchamiać odtworzonej aplikacji ani schedulerów; walidatory offline dopiero po restore DB/files/obu kolekcji |
| Evidence | czas każdego etapu, wiek checkpointu, manifest/hashy, bounded counts, FK/invariants, page/chunk scope i generation; reprezentatywna sprawa raportowana wyłącznie jako zanonimizowany digest |
| Cleanup | po osobnej zgodzie usunąć wyłącznie powyższy project, dwa kontenery, dwa volumes, jedną network i root; nigdy źródłowy checkpoint |

## Wiersze do osobnej decyzji właściciela

| Operacja | Dlaczego / dokładny zakres | Skutki i bramka |
|---|---|---|
| Nowy spójny punkt | Wymagany do pełnego R03 przed najbliższą ryzykowną zmianą: DB, document storage, config/n8n encrypted export, **obie** kolekcje Qdrant oraz hashowany inventory efektywnego runtime/workerów w jednym kontrolowanym oknie. Najpierw potrzebna mała, osobno zatwierdzona korekta narzędzia/formatu wielokolekcyjnego. | Nowy dokładnie nazwany katalog backupu i normalne snapshoty źródłowe; bez queue/modeli. Osobna zgoda na utworzenie oraz na minimalną zmianę narzędzia. |
| Izolowany restore drill | Po powstaniu spójnego punktu odtworzyć go wyłącznie do celu `R03_DRILL_20260908_A1`; istniejący proof tool musi najpierw dostać jawny osobny PostgreSQL target i tryb Qdrant bez publikacji portu. | Zapisy tylko w nowych celach izolowanych. Historyczny checkpoint `20260906T010005Z` może dać jedynie częściowy drill (bez KB/current runtime/secrets), więc sam nie zamknie R03. |
| Escrow | Właściciel wskazuje zatwierdzony zaszyfrowany vault/nośnik poza hostem/Git, operatora i recovery administratora, ACL, osobne miejsce recovery key oraz zakres kontrolowanego testu odczytu bez wypisywania wartości. | Niezależna zgoda; bez rotacji. Osobno zatwierdzić wcześniejszy termin wobec historycznej sekwencji CHUNK23. Brak decyzji blokuje odpowiednie ryzykowne wdrożenia, nie lokalne poprawki. |
| Cleanup po drill | Usunąć wyłącznie exact-name zasoby celu wymienione wyżej po zachowaniu zanonimizowanych dowodów. | Osobna zgoda po drill; bez retencji/usuwania źródłowych backupów. |

RTO/RPO pozostają `NOT_MEASURED`: przyszły drill ma mierzyć start/koniec etapów,
łączny czas oraz wiek i wzajemną spójność odzyskanego punktu. Samo istnienie
kopii nie ustala SLA. Punkt traci aktualność po pierwszej zmianie DB/storage,
obu kolekcji, konfiguracji lub efektywnego runtime po jego cut-off.

## Kontrole, skutki i STOP

- Production DB: jeden krótki `BEGIN READ ONLY` z timeoutem; zapisów `0`.
- Backup/Qdrant/filesystem: wyłącznie odczyty metadanych i hashy; nowych
  snapshotów, kopii, archiwów, baz, kontenerów, volumes i networks `0`.
- Wartości `.env`, credentials, cookies, tokenów i kluczy: nieodczytane.
- Restore, escrow, testy aplikacyjne, modele, Temporary Chat, kolejki i
  produkcyjne restarty: `NOT_RUN` / `0`.
- Oryginalny worktree: 203/203 wpisy preservation manifest, mismatch `0`,
  staged `0`; niezmieniony przez tę sesję.
- R02: `ACCEPTED`. R03: `WAITING_APPROVAL`, nie `READY_FOR_REVIEW` ani
  `ACCEPTED`. R04–R24: bez zmian.

**Jeden następny bezpieczny krok:** właściciel wybiera i osobno zatwierdza
konkretne wiersze powyżej; rekomendowana kolejność to minimalna korekta
izolacji/wielokolekcyjnego punktu, utworzenie spójnego punktu, izolowany drill,
a escrow jako odrębna decyzja.

**STOP: nie wykonywać żadnej z opisanych operacji i nie rozpoczynać R04.**
