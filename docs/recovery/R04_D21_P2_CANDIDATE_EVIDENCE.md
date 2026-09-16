# R04 / D-21 / P2 — preservation and pinned candidate evidence

Status: `PRESERVATION_AND_CANDIDATE_ACCEPTED / NOT_DEPLOYED` oraz
`ACTIVE_DATA_TOPOLOGY_AND_DESTINATION_SOURCE_ACCEPTED / OFFLINE_TEST_ONLY /
NOT_DEPLOYED`; P3: `PREPARATION_PARTIAL / NO_CUTOVER`

## Zakres i tożsamość

- Parent/evidence HEAD wejścia: `7687cc15bb31175d19485b10a6e13dfc5945bfc2`.
- Odebrany source P1: `2e69622bc6a0b4888427f8ae5be119377aed26d9` jako
  `SOURCE_AND_OFFLINE_TESTS_ACCEPTED / NOT_DEPLOYED`.
- Odebrany source A4: `04ab5e58cf86896ffd946cabffde13367d343f53`;
  evidence `8620871711321a42e62291e52865b5a668a4955d`.
- Wybrany source set P2: pełne drzewo commita
  `2e69622bc6a0b4888427f8ae5be119377aed26d9`, tree
  `4ee8f9ca77cc315dce428b689264d5125f0a23f5`.
- Poprawka źródłowa DATA_ONLY: commit
  `e4f298a46efa2ad29921fcf7cce0ca6a04f3d0fd`, tree
  `873d199ed43c5d6719a34f2158b0537f7e07a73b`. Backend/frontend z P2 nie
  zmieniły bajtów; zmiana obejmuje walidator, przykład, README i test junctionu.
- Domknięcie celu mountu `RV-D21-DATA-01`: commit
  `cb6e22506a0fecc440400566293524536847b9b0`, tree
  `c349a1d6ebfeb6077bc62181667f7f3c8f9d42cc`. Zmiana obejmuje wyłącznie
  walidator, jego test junctionu i README; bajty aplikacji i Web nie zmieniły się.
- Jeden chroniony root P2:
  `C:\ai-lab-core-staging\recovery\R04_D21_SINGLE_ROOT_20260915T033112Z\p2-20260915T212340Z`.
- Kandydat jest `NOT_DEPLOYED / NOT_APPROVED_FOR_START`. P2 nie zmieniło
  produkcyjnych ścieżek, tasków, mountów, flag, kolejek ani danych.

Preflight potwierdził właściwy branch i tracking ref, czyste recovery, brak
drugiego autora, brak konsumenta dokładnego rootu P2, 572.34 GiB wolnego miejsca
na C: oraz odziedziczone ograniczone ACL. Nie zmieniano ACL. Nazwę rootu
ustalono przed pierwszym zapisem i nie tworzono drugiego środowiska P2.

## Wybór jednego kandydata

Porównanie A4 source → P1 source nie wykazało zmian w `backend/app`,
`frontend/lib`, `backend/alembic`, `frontend/pubspec.yaml` ani
`frontend/pubspec.lock` (`git diff --quiet`, exit `0`). Oznacza to, że zaakceptowane
bajty aplikacyjne A4 przetrwały, a dalsze różnice P1 dotyczą kontrolowanego
launchera/operations i dokumentacji. Kandydat jest pełnym drzewem jednego
commita, nie ręcznie złożoną mieszaniną katalogów.

Snapshot Git ma 1,198 plików / 13,886,448 B. Archiwum ma 6,207,605 B i
SHA-256 `318A41F24F5B2949A06A24B38BB5D2B599E300734E67F1E91E0F5C59879CC6C3`.
Manifest plików ma SHA-256
`72A8B6ACA13208F296F513D5DFCC6D9FE6ECD7411DBB895F3776539CE29DE417`.
Bezpieczna ekstrakcja do własnego katalogu walidacyjnego oraz pełne porównanie
1,198 hashy dały mismatch `0`. Z odtworzonego drzewa nie uruchamiano produktu.

Szczegółowy wybór komponentów, targetów i bramek znajduje się w
`R04_D21_P2_SOURCE_SELECTION.csv`. Źródła, artefakty i runtime pozostają trzema
odrębnymi klasami dowodu.

## Preservation unikalnej pracy

### Oryginalny worktree

Ponownie użyto istniejącego, kompletnego preservation R00 zamiast tworzyć
drugą kopię. Aktualny odczyt potwierdził:

- HEAD `72950657ac79b50d0afe72753632ba4cde810b95`;
- 203/203 pozycje obecne, mismatch hash `0`, mismatch rozmiaru `0`;
- 6 tracked modified + 197 untracked, staged `0`;
- `R00_WORKTREE_MANIFEST.csv` SHA-256
  `994A17D7BCD7BA8120F73BC462AC6A2313A47F04D91F6639D2863A98A3FD6999`;
- `R00_SOURCE_PRESERVATION_MANIFEST.csv` SHA-256
  `0442A171B031A30A7FC835CF39E1D864BCA0BFBAA987E82FE761D8A6B75A9A50`;
- binary-capable tracked patch SHA-256
  `0CA24C4255CE43F7753E53F322324A9D042707319D17F7BED30B537910A1DF63`.

Nie zmieniono brancha, HEAD, indeksu ani plików oryginalnego worktree.

### Visual V2 audit

Audit worktree pozostaje na
`c2e931c8b72a55f4260b546e9eba84d67040e1f4`, merge base z main
`4cc7446f9ad311c63c72727a969a55f319258669`, 13 commitów w jego historii ponad
bazą i 5 wpisów stanu lokalnego. Porównanie patch identity z wybranym kandydatem
dało 4 commity równoważne patchowo i 9 commitów unikalnych do dalszego review.
Nie wykonano ich adopcji.

- bundle: 506,522,548 B, SHA-256
  `6010890462798DD24C59F2158E7662C1691FF4F7B657F5C0B98BFAC837C8ECD8`;
- `git bundle verify`: PASS; fetch do osobnego bare validation repo odtworzył
  dokładnie HEAD audytu;
- dirty binary patch: 94,134 B, SHA-256
  `6242BD7B22D95EA8CFEBF105509BD130913A606218E7EC110FFAF929E1C3CFF2`;
- reverse-apply check: PASS;
- dirty manifest: 5 pozycji, cztery exact-byte copies zgodne i jedno usunięcie
  zapisane jawnie.

Pierwsza próba wygenerowania patcha przez pipeline PowerShell zmieniła
kodowanie/newline i była nieważna. Zachowano ją lokalnie jako
`visual-v2-audit-dirty.invalid-pipeline-encoding.patch` z etykietą INVALID;
nie jest dowodem odtwarzalności i nie zastępuje poprawnego patcha.

### Zewnętrzny worker

Z `C:\ChatGPT-Vision-Worker\worker` skopiowano jako opaque bytes wyłącznie siedem
jawnie dozwolonych plików źródłowych. 7/7 kopii ma zgodne rozmiary i SHA-256.
Względem kandydata: 0 identycznych, 3 różne, 4 nieobecne. Zewnętrzny
`vision-job.js` ma SHA-256
`54CCA6E992BD00F2A239288E18199B7D4CAE097AE7B49773639B094851434BEE`, a
kandydat
`D61B9BDDB6AC9AA9314B48079BA89B8BE15E98697FF41A6DD030BDE6F0F74C1D`.
Klasyfikacja pozostaje `HOLD / REVIEW`; niczego nie zaimportowano.

Nie czytano ani nie kopiowano profilu przeglądarki, cookies, sesji, kluczy,
inputs, outputs, logów lub runtime state. Clean promotion worktrees z mapy D-21
nie zostały ponownie zarchiwizowane: ich czystość i ancestry/ref są wystarczającym
dowodem P2. Nierozstrzygnięte katalogi pozostają `HOLD/UNKNOWN`.

## Web TEST_ONLY

Starszy build A3 pochodził z innego źródła i nie został przemianowany na
aktualny. Po bramce zasobów wykonano dokładnie jeden lokalny build Web z kopii
frontendu kandydata:

```text
C:\FlutterSDK-New\flutter\bin\flutter.bat build web --debug --no-pub
  --no-web-resources-cdn
  --dart-define=API_BASE_URL=http://127.0.0.1:18004
  --dart-define=SUPERVISOR_BASE_URL=http://127.0.0.1:18006
```

Wcześniej `flutter pub get --offline` zakończył się exit `0`; lockfile pozostał
niezmieniony. Flutter Git HEAD
`058e0af2c2b57e369d905a03ac9748b0ebf543c6` (3.44.8), Dart 3.12.2.
Build trwał od `2026-09-15T21:39:10.8417243Z` do
`2026-09-15T21:40:00.7895372Z`, exit `0`; pełne stdout/stderr zachowano od
początku. Błąd pierwszej recepty pakowania (`Compress-Archive -LiteralPath` z
wildcardem) poprawiono bez ponownego builda.

- ZIP: 20,044,226 B; SHA-256
  `A99FB9E30FD66F815509434BD594050D82F4D5D1B6E45A36DB6DDECC085A4C41`;
- zawartość: 40 plików / 62,936,454 B; manifest SHA-256
  `A5BA823B0F41A3288CF20F2B7C6A898105994652AF4CF25814C85D762D713B44`;
- `main.dart.js`: 18,159,271 B; SHA-256
  `77201F480D899224E50AE6355D20C34B58933AABD6AFB09ED0BF6C413DE83B4F`;
- skan zawartości potwierdził testowy API `127.0.0.1:18004`; nie wykrył
  produkcyjnych 8789/8788; Supervisor URL nie występuje w wygenerowanych
  bajtach, bo nie jest używany przez klienta;
- serwer, przeglądarka i UI: `NOT_RUN`; publikacja: `NOT_RUN`.

Bramki przed/po buildzie przeszły. Przed buildem Windows available 7.887 GiB,
commit reserve 37.983 GiB, właściwa pula WSL/Docker available 15.032 GiB, swap
used 0. Po buildzie odpowiednio 7.692 / 37.913 / 15.028 GiB, swap used 0.

## DATA_ONLY — zmiana polityki i testy offline

Preimage zaakceptowanego P1 odrzucił poprawny syntetyczny junction przez
`CONTAINER_BIND_REPARSE_POINT:backend` (exit `1`). Jest to oczekiwany
fail-before dla nowej decyzji właściciela, nie wada wcześniej odebranego P1.
Źródło `e4f298a46efa2ad29921fcf7cce0ca6a04f3d0fd` dodaje wersjonowany kontrakt
`NEXT_STABIL_DATA_TOPOLOGY_V1` i pozwala wyłącznie na dokładny directory
junction danych z powiązaniem service/role/source/destination. Kod, manifest,
script_ref, executable, CWD, `/app`, obcy/nested reparse, data2 i traversal
pozostają fail-closed.

Windows PowerShell `5.1.26100.8894`:

- data junction: `20/20`, exit `0`, stdout SHA-256
  `D59D16D3B5EF1F46E4C896B875B411706DC8366E2B38F0D7B255469F16346A91`;
- host plan regression: `53/53`, exit `0`, stdout SHA-256
  `6B15018D1A1C7EFA831F7B3C6A6DCDBFFE2D4922A0C97B36925134DBAE55DD15`;
- real-adapter mapping regression: `48/48`, exit `0`, stdout SHA-256
  `6112F31AFB76A2D7F192C0DFB8149226CD06D45C22038E7ADDB67C9F53A8881D`;
- parser pięciu właściwych `.ps1`: błędy `0`; JSON przykładu: PASS.

Test utworzył i usunął tylko własny, dokładnie nazwany syntetyczny junction i
target. Wszystkie granice Docker/HTTP/CIM/TCP/Task Scheduler/startu pozostały
atrapami. Nie zmieniono rzeczywistego junctionu, D:, backupów ani runtime.

### RV-D21-DATA-01 — dokładny kontrakt celu mountu

Wynik: `REPRODUCED`. Na rzeczywistym walidatorze z preimage
`e4f298a46efa2ad29921fcf7cce0ca6a04f3d0fd` dwa wewnętrznie spójne, lecz
nieuprawnione manifesty doszły do planu:

- `backend / APPLICATION_DATA / /app/app` powtórzone w `data_topology.bindings`
  i `containers[].mounts` — fail-before exit `1`;
- `postgres / N8N_DATA / /home/node/.n8n` powtórzone w obu sekcjach —
  fail-before exit `1`.

Nie był to Docker ani incydent runtime. Test użył wyłącznie własnego junctionu,
pełnych atrap adapterów i kodu preimage. Source
`cb6e22506a0fecc440400566293524536847b9b0` wiąże teraz dokładną, czułą na
wielkość liter trójkę `service + role + destination` z pięcioma istniejącymi
wariantami: backend `/data`, PostgreSQL `/var/lib/postgresql/data`, n8n
`/home/node/.n8n`, Open WebUI `/app/backend/data` i Ollama `/root/.ollama`.
Nieznane role i zgodne wewnętrznie, ale obce pary są odrzucane przed adapterami.

Końcowa kampania Windows PowerShell `5.1.26100.8894`:

- data junction/destination guard: `44/44`, exit `0`, log 43 B, SHA-256
  `F70CD54EBC0229CACDBA371CD41A5EF61BBCC729CF57F210C46A74E6C56D6EE0`;
- host plan regression: `53/53`, exit `0`, log 32 B, SHA-256
  `6B15018D1A1C7EFA831F7B3C6A6DCDBFFE2D4922A0C97B36925134DBAE55DD15`;
- real-adapter mapping: `48/48`, exit `0`, log 44 B, SHA-256
  `6112F31AFB76A2D7F192C0DFB8149226CD06D45C22038E7ADDB67C9F53A8881D`;
- parser pięciu `.ps1` i JSON przykładu: błędy `0`, exit `0`, log 35 B,
  SHA-256 `90A343C8D862E69FE28B8BB6E90AA24B5CA3D553D57A2DF56C21519A9D63AB7A`.

Hash wynikowego `operations/runtime/startup-runtime.ps1`:
`DC4E5EB638B93470BFF252D23864BBB1FC2F75D001B2D1E9FC20C0B849C0A103`.
Surowe dowody pozostają LOCAL_ONLY w
`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\active-data-junction-20260916T055951Z\destination-guard-20260916T082046Z`.

## Draft manifest i celowa odmowa

`R04_D21_P2_CANDIDATE_SET.json` korzysta z kontraktu P1
`NEXT_STABIL_STARTUP_SET_V1` i pozostaje `DRAFT_NOT_APPROVED_FOR_START` z
`approval.status=NOT_APPROVED`. Nie został skopiowany do rootu kanonicznego.

Statyczna walidacja przez Windows PowerShell `5.1.26100.8894` zakończyła się
exit `0` dla oczekiwanego testu odmowy: `valid=false`, błąd
`START_NOT_APPROVED` obecny, adaptery wywołane `0`. Pozostałe błędy opisują
faktyczny brak instalacji plików kandydata pod `C:\ai-lab-core` oraz
nierozstrzygnięte ID/image/digest P3. Nie podstawiono expected jako observed i
nie osłabiono walidatora.

Pierwszy wrapper uruchomił PowerShell 7.6.5; jego zgodny wynik odmowy zachowano,
ale nie użyto jako wymaganego dowodu PS 5.1. Następnie poprawiono wyłącznie
receptę uruchomienia i zapisano właściwy wynik 5.1.

Po aktualizacji kandydata wykonano osobną kontrolę spójności danych: JSON PASS,
`approval=NOT_APPROVED`, dokładny logical/target/type/purpose, pięć jawnych
bindingów, source/tree `cb6e225.../c349a1d...`, host-runtime SHA-256
`DC4E5EB638B93470BFF252D23864BBB1FC2F75D001B2D1E9FC20C0B849C0A103` oraz
niezmienione pochodzenie Web z `2e69622...`. Negatywny przypadek planu
`START_NOT_APPROVED` i zero adapterów jest częścią bieżącego testu junctionu;
samego kandydata nie uruchamiano.

## Startup policy i skutki późniejszego P3

Statyczny odczyt kandydata potwierdził domyślne `false` dla: Vision V1,
Visual V2, Advanced, KB processing, KB vector writes, Document Preparation i
Assistant pipeline V2. Odpowiadające dispatchery są bramkowane tymi flagami.
Nie oznacza to jeszcze bezpiecznego startupu całego backendu:

- `init_database()` jest wywoływane bezwarunkowo w lifespan;
- `start_backup_plan_reconciler()` bezwarunkowo uruchamia pętlę, która może
  wywołać `reconcile_pending()`;
- efektywna konfiguracja P3 nie została zainstalowana ani odczytana z sekretów;
- Supervisor pozostaje `INTENTIONALLY_STOPPED` i launcher nie może go uruchomić.

Przed P3 wymagane są więc: zatwierdzona allowlista efektywnych flag,
kontrola side effects `init_database` i backup reconciler, dokładne ID
kontenerów/image/mountów, decyzja schema, przegląd zewnętrznego workera/profile,
potwierdzenie fizycznych miejsc zapisów nieobjętych dowodem D:, okno operacyjne,
aktualny rollback oraz osobna zgoda właściciela. Wybór
`C:\ai-lab-core\data -> D:\ai-lab-data` jest już rozstrzygnięty i ma status
`OWNER_APPROVED_ACTIVE_DATA_JUNCTION`; P2 nie zmienia flag i nie uruchamia
lifespan.

## Current observed vs candidate vs target

Ograniczony read-only odczyt Engine z `2026-09-15T21:43:27.3024961Z`
potwierdził, że aktualny backend nadal działa z:

- container ID
  `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`;
- image ID
  `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`;
- `/app` z `C:/ai-lab-core/build/deploy-main-483f9bf8/backend`;
- `/data` z `C:/ai-lab-core/data`;
- restart policy `unless-stopped`.

Odrębny odczyt metadanych ścieżki wykazał, że
`C:\ai-lab-core\data` jest junctionem do `D:\ai-lab-data`. Backend source root
nie jest reparse pointem. Właściciel zatwierdził ten dokładny junction jako
`ACTIVE_DATA_ONLY`: jeden root instalacji oznacza jedno źródło kodu/startu, a
nie jeden fizyczny dysk kodu i danych. Link i dane nie zostały zmienione.

## Fizyczne miejsca zapisów

Poniższa tabela rozdziela deklaracje źródłowe od historycznej obserwacji runtime
z `2026-09-15T21:43:27.3024961Z`. `CONFIRMED_D` oznacza potwierdzony łańcuch
mount → logiczne `C:\ai-lab-core\data` → junction D:, a nie bieżący test
end-to-end każdego zapisu aplikacji.

| Kategoria / zapisujący | Ścieżka usługi → host | Dowód | Stan | Brakujące P3 |
|---|---|---|---|---|
| PostgreSQL: cluster, indeksy i WAL wewnątrz PGDATA | `/var/lib/postgresql/data` → `C:\ai-lab-core\data\postgres` → `D:\ai-lab-data\postgres` | Compose + historyczny live bind + metadata junction | `CONFIRMED_D` | Odczyt-only: wykluczyć zewnętrzne tablespaces/WAL. |
| PostgreSQL: zewnętrzne tablespaces/WAL | nieustalone | brak odczytu konfiguracji DB | `UNKNOWN` | Rozliczyć konkretne lokalizacje bez SQL zapisu/migracji. |
| Backend: dokumenty, poczta/CRM attachments, KB originals/extracted/chunks, OCR/rendery, analysis/vision spool | `/data/...` → `C:\ai-lab-core\data\...` → D: | `settings.data_dir=/data`, mapy ścieżek w kodzie, historyczny live `/data` bind i junction | `CONFIRMED_D` | Potwierdzić efektywne flagi i wszystkie dodatkowe cache/tmp/log paths. |
| Qdrant: kolekcje/indeksy | `/qdrant/storage` → managed volume `qdrant_storage` | deklaracja Compose; brak backing metadata | `UNKNOWN` | Ustalić fizyczny backing/VHD; managed volume nie dowodzi D:. |
| n8n | `/home/node/.n8n` → `C:\ai-lab-core\data\n8n` → D: | Compose + historyczny live bind + junction | `CONFIRMED_D` | `KEEP`; tylko potwierdzić exact mount w oknie P3. |
| Ollama models/state | `/root/.ollama` → `C:\ai-lab-core\data\ollama` → D: | Compose + historyczny live bind + junction | `CONFIRMED_D` | `KEEP`; nie pobierać/przenosić modeli w P3. |
| Open WebUI state | `/app/backend/data` → `C:\ai-lab-core\data\openwebui` → D: | Compose + historyczny live bind + junction | `CONFIRMED_D` | `KEEP`; potwierdzić exact mount. |
| Worker/AI spool i wyniki repozytoryjne | `/data/analysis-spool`, `/data/vision-spool` → D: | kod + backend live bind | `CONFIRMED_D` | Potwierdzić wyłącznie efektywne consumers/flags. |
| Zewnętrzny Vision profile/session/state | `C:\ChatGPT-Vision-Worker` | mapa D-21; brak relokacji/odczytu profilu | `CURRENT_C_REQUIRES_RELOCATION` | Osobna zgoda i session-safe plan; bez cookies/secrets. |
| Docker/WSL VHD, image layers, writable layers i container logs | instalacja zarządzana przez Docker/WSL | fizyczne położenie nieodczytane | `UNKNOWN` | Odczyt-only backing metadata i wpływ; bez move/restart. |
| Duże cache/tmp/logi poza `/data` | zależne od procesu | częściowe deklaracje, brak kompletnego runtime proof | `UNKNOWN` | Zamknąć allowlistę trwałych ścieżek; małe logi kontrolne pozostają wyjątkiem. |
| Backup schedules | oddzielne taski/wrappers i dotychczasowe cele | D21-031 + istniejące dowody R03 | `NOT_APPLICABLE` dla zwykłego startu | Zachować mechanizm, harmonogram, retencję i cele bez zmian; nie uruchamiać backupu. |

W sesji źródłowej DATA_ONLY nie wykonano nowego odczytu Engine, SQL,
`docker exec`, skanu danych ani zapisu kontrolnego do firmy. Późniejszy,
ograniczony odczyt P3 preparation jest opisany oddzielnie poniżej. Wniosek nie
ma statusu `ALL_LIVE_WRITES_ON_D_PASS`.

Nie ma mountu recovery ani P2, a kandydat nie jest załadowany. Aktywny deploy
repo pozostaje clean na `483f9bf8b1a591ded8a42df5da87663c664ed5d4`, a dokładny override D21-016 ma
SHA-256 `36355C9392BA1A9A060B036D7B64B42E0CBD4EF65579335BB7C95DDA807436E8`.
To rollback kodu/konfiguracji, nie dowód odzyskania aktualnych danych firmy.

Docker Desktop po aktualizacji znajduje się pod profilem użytkownika; pierwsza
recepta odczytu wskazywała nieistniejącą starą ścieżkę i nie uruchomiła CLI.
Po ustaleniu faktycznej ścieżki wykonano jedną ograniczoną obserwację
read-only. Nie startowano, nie zatrzymywano i nie restartowano kontenerów.

## R03 i rollback danych

Istniejący punkt R03 pozostaje historycznym dowodem odtworzenia wskazanego
manifestu, nie kopią dzisiejszego stanu. R03 nadal ma status
`WAITING_APPROVAL / WAITING_ESCROW_DECISION`. P2 nie wykonało nowego backupu,
snapshotu, restore ani rehashu wielkich artefaktów. Brak aktualnej bramki
operacyjnej blokuje P3, ale nie unieważnia preservation źródeł P2.

## Rzeczywiste skutki i ograniczenia

Rzeczywiste zapisy tej sesji to jeden root P2, kopie/archiwa źródeł objętych
zgodą, rozpakowane katalogi walidacyjne, jeden build Web TEST_ONLY, jego cache i
logi oraz dokumentacja Git. Nie było produkcyjnych zapisów danych, migracji,
startu aplikacji/launchera/Supervisora/workera/modeli, zmiany tasków, mountów,
flag, kolejek, harmonogramów, backupu, restore, escrow, deploymentu, release ani
cleanup. Wszystkie oryginalne roots i profile pozostają na miejscu.

P2 ani poprawka DATA_ONLY nie dowodzą działania aplikacji, Web runtime, zgodności Windows/Android,
realnego eksportu, aktualności danych recovery ani poprawnego cutoveru.
`PRODUCTION_START_MANIFEST_NOT_APPROVED`; operacyjne P3–P5 są `NOT_RUN`.

## Odtworzenie i rollback

1. Źródła kandydata odtwarza się wyłącznie z archiwum i sprawdza względem
   `source-file-manifest.csv`; nie uruchamia się ich z P2 stagingu.
2. Audit Git odtwarza się z bundle do nowego repo i dopiero potem stosuje
   poprawny dirty patch/exact bytes; invalid patch jest wykluczony.
3. Zewnętrzne źródła workera pozostają osobnym HOLD; profil/state pozostają in
   place i nie są rekonstruowane z repo.
4. Aktywny rollback kodu pozostaje przy main `483f9bf8...`, jego obrazie,
   mountach i D21-016. Żadne przełączenie nie zostało wykonane.
5. Powrót danych wymaga osobnej decyzji R03/escrow i aktualności punktu; P2 nie
   zastępuje backupu.

## P3 preparation — bieżący odczyt i wynik

Właściciel odebrał destination guard na source `cb6e225...` i evidence
`e9c17933...`. Dnia 2026-09-16 wykonano dopuszczoną serię read-only:

- dokładny junction `C:\ai-lab-core\data -> D:\ai-lab-data` potwierdzono
  bieżąco; D: jest NTFS i target istnieje;
- Public Gateway działa na `127.0.0.1:8789`; `/gateway-health=200`, a
  publiczne `/control=404`;
- Engine odpowiedział na version/info, lecz bounded `docker ps -a` i potem
  jeden celowany inspect sześciu znanych nazw przekroczyły po 20 s. Własne
  CLI zakończono; bieżące container/image/mount/volume/log facts pozostają
  `CURRENT_UNKNOWN` zamiast kopiowania obserwacji historycznej;
- current Docker data VHD znajduje się na C: i ma 46,937,407,488 B;
- host nie ma `psql`, więc po utracie obserwowalności Engine nie wykonano
  dozwolonej sesji SQL ani `docker exec`; schema/WAL/tablespaces i zagregowane
  stany DB pozostają `UNKNOWN`;
- Task Scheduler potwierdził niezmienione taski. Backup 2 i 3 mają ostatni
  result `1`, a najnowszy znaleziony lokalny manifest pochodzi z 2026-08-29;
- profil/state `C:\ChatGPT-Vision-Worker` ma 7,328 plików / 890,094,670 B na
  C:. Nie odczytywano cookies, tokenów ani zawartości profilu.

Source review wykazał też, że `init_database()` bezwarunkowo wykonuje
`seed_admin()`, a backup plan reconciler jest uruchamiany bezwarunkowo i może
zapisywać sync events oraz kontaktować Supervisor. Jednocześnie bieżące pliki
Compose deklarują kilka producerów jako `true`; historyczny override wyłącza
tylko document preparation. Effective env nie został odczytany z kontenera.

Pełna tabela i plan znajdują się w
`R04_D21_P3_PREPARATION.md` i `R04_D21_P3_CHANGESET.csv`. Wynik to
`PREPARATION_PARTIAL`: blokują go bieżąca obserwowalność Engine, brak SQL,
brak bezpiecznego guardu reconcilera dla pierwszego base-only startu oraz
nierozstrzygnięta aktualność rollbacku danych. Kandydat nadal ma
`approval.status=NOT_APPROVED`; P3 nie został wykonany.

Następny krok: po rzeczywistej zmianie stanu Engine dokończyć jedną bounded
projekcję container/image/mount/volume i jedną READ ONLY sesję SQL, a następnie
przedstawić właścicielowi osobną decyzję dla nazwanego
`P3 CORE BACKEND SOURCE SWITCH`. Bez automatycznego cutoveru.
