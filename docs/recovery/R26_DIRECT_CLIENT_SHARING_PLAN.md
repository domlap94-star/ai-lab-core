# R26 — Bezpośrednie udostępnianie klienta

## 1. Cel i granice

R26 krok 1 dodaje bezpośrednią akcję `Udostępnij klienta` na liście klientów
oraz w szczegółach klienta. Akcja korzysta wyłącznie z istniejącego kontraktu
R25 i nie przechodzi do `/shared-clients`.

Przepływ użytkownika:

1. kliknięcie `Icons.share_outlined` otwiera przy ikonie aktualną listę
   użytkowników External;
2. aktywny grant dla wybranego klienta wyklucza użytkownika z listy, a grant
   cofnięty nie blokuje ponownego nadania;
3. wybór użytkownika otwiera dialog, ale nie wykonuje mutacji;
4. dopiero przycisk `Udostępnij` wykonuje dokładnie jeden
   `POST /api/v1/client-access/grants`;
5. sukces odświeża historię i opcje oraz pokazuje komunikat bez zmiany trasy.

Krok 2 został później osobno autoryzowany. Jego source/test/build jest
opublikowany, lecz deployment nie rozpoczął się, ponieważ jedyny UAC anulowano
przed `CreateProcess`. Nie zmienia to odbioru kroku 1 ani polityki scope R25.

## 2. Implementacja współdzielona

- `frontend/lib/features/shared_clients/data/client_access_repository.dart` —
  jeden klient istniejących endpointów shared-clients, grants i
  manager-options;
- `frontend/lib/features/shared_clients/application/client_access_providers.dart`
  — wspólne providery, polityka widoczności dla `User`, `Admin` i
  `Administrator`, wykluczanie aktywnych grantów i sortowanie;
- `frontend/lib/features/shared_clients/presentation/client_share_action.dart`
  — jeden komponent używany na liście i w szczegółach klienta;
- `clients_page.dart` i `client_details_page.dart` — wyłącznie osadzenie
  wspólnego komponentu we właściwej kolejności UI;
- `shared_clients_page.dart` — zachowany istniejący ekran historii i revoke,
  korzystający ze wspólnej warstwy dostępu.

Dialog ma tytuł `Udostępnić klienta?` i treść:

> Udostępnić klienta „<NAZWA KLIENTA>” użytkownikowi
> „<NAZWA UŻYTKOWNIKA>”?
> Użytkownik uzyska dostęp do klienta oraz jego zasobów zgodnie z zakresem
> uprawnień R25.

Sukces pokazuje:

> Udostępniono klienta użytkownikowi <NAZWA>.

## 3. Bezpieczeństwo i kompatybilność

- backend pozostaje ostateczną warstwą autoryzacji;
- External, rola pusta, nieznana i brak sesji nie otrzymują przycisku;
- otwarcie listy, wybór użytkownika i `Anuluj` wykonują zero POST/DELETE;
- przycisk potwierdzający jest blokowany na czas requestu;
- błędy są ograniczonymi komunikatami bez wyjątków, tokenów i ścieżek;
- karta klienta nadal otwiera szczegóły, a akcja udostępniania nie propaguje
  tapnięcia;
- `/shared-clients` i pojedynczy revoke zachowują dotychczasowy kontrakt;
- nie dodano zmian backendu, Alembic ani schematu.

## 4. Testy i artefakty

Source i release używają wersji `1.0.2+42` — pierwszego wolnego,
monotonicznego numeru build po zajętych wartościach.

- focused share action: `11/11 PASS`;
- focused clients hotfix/regression: `16/16 PASS`;
- pełny aktualny zestaw Flutter: `374/374 PASS`;
- `flutter analyze`: `PASS`;
- Web main SHA-256:
  `44A53C0BF821D31279294D017D4D12673A822AAFFBAAF301B8C90900E4A115EE`;
- Windows installer SHA-256:
  `1F920C494704F7FA2E91ADC1049DB4002A3B210A4F15948013D5237BC8AB013E`;
- Windows installed `frontend.exe` SHA-256:
  `C0DE8E94FF2BF4280ACDC2C1FA0B65701CB3A19D3269226F6C2BDB664C134CD5`;
- Android APK SHA-256:
  `10A1193AB6FE50F567549F6F42AA40AE829896B23BA8986EA8E8BE25927BE027`;
- stable manifest SHA-256:
  `F65CC51573D583C408413CCAAAA62BBED84C9862FA8BB2109F223C48461135E5`;
- startup manifest SHA-256:
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`.

## 5. Deployment i live smoke

Transakcyjny deployment `R26-DIRECT-SHARE-20260927-B1FF82B824D8` zakończył
się `PASS`, manifest ma `APPROVED_FOR_START`, a `pending_mutation=false`.
Web odpowiada na kanonicznym publicznym adresie, publiczne `/control*`
pozostaje `404`.

Android `1.0.2+42` przeszedł instalację i smoke wyłącznie na
`emulator-5554`: Signature Scheme v2, właściwa wersja, ekran logowania,
pause/resume, close/reopen i brak crasha. Windows `1.0.2+42` przeszedł exact
hash/root, launch, close i reopen.

Live smoke użył wyłącznie czterech jawnie zatwierdzonych fixture R26S1 oraz
jednego pre-grantu `External Beta -> Klient testowy A`. Potwierdzono:

- lista zawiera Alpha i wyklucza Beta;
- anulowanie tworzy zero nowych grantów;
- potwierdzenie tworzy dokładnie jeden grant Alpha;
- po sukcesie Alpha i Beta są wykluczeni z dostępnych opcji;
- External Alpha otrzymuje dokładnie jednego udostępnionego klienta A;
- oba syntetyczne granty cofnięto istniejącym endpointem;
- usunięto dokładnie fixture R26S1;
- końcowe residue: `users=0`, `clients=0`, `grants=0`.

Nie zachowano w repo screenów, poświadczeń, tokenów, danych klientów ani
lokalnych logów biznesowych.

## 6. Stan

- `R25_ACCEPTED` pozostaje bez zmian;
- R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` dla wyniku opublikowanego w
  `182183c618a2545b79eaea97702a8bbc3a1525ac`;
- właściciel praktycznie potwierdził działanie na liście i w szczegółach,
  anulowanie bez grantu oraz dokładnie jeden właściwy grant po potwierdzeniu;
- R26 krok 2: `IN_PROGRESS / CONSOLIDATED_K1 /
  DEPLOYMENT_NOT_RUN_UAC_CANCELLED`;
- otwarte techniczne K0/K1 w zakresie kroku 1: `BRAK`;
- R04 pozostaje wstrzymane; D-22 pozostaje `NOT_RUN`.

## 7. Krok 2 — wykonany zakres source/test/build

Opublikowany source `67b867ee279fe0bf7617c05b7d61fff0b337cab3` zawiera:

- domyślną listę active-only i jawny przełącznik `Pokaż cofnięte`;
- zaznaczanie wielu aktywnych grantów oraz jeden atomowy
  `POST /api/v1/client-access/grants/bulk-revoke`;
- zachowanie historii grantów, wspólny `revoked_at`, konflikt bez częściowego
  skutku oraz niezmieniony flow kroku 1;
- addytywną migrację `r26_step2_20260928` z nullable DATE `scheduled_date`,
  deterministycznym backfillem Europe/Warsaw i historycznymi kolumnami bez
  usuwania;
- obowiązkowy date-only picker `Termin wizji *`, bez pola `Rozpoczęto` i bez
  drugiego źródła prawdy dla nowych operacji;
- wersję `1.0.2+43`.

Dowody przed deploymentem:

- focused backend migration/date/bulk oraz regresje R25: `PASS`;
- Python compile: `PASS`;
- Flutter analyze: `PASS`;
- focused Flutter: `29/29 PASS`;
- pełny Flutter: `379/379 PASS`;
- Web/Windows/Android release build: `PASS`;
- Web main SHA-256:
  `F7013E8E5DE072B679703DE07989B34415D4D94BD383C06ACFFBC2B0CAC3D0CB`;
- Windows installer SHA-256:
  `562DBE2E41838D4960459958442CE314D1EE5E5299D869F446923666F6841A89`;
- oczekiwany installed Windows `frontend.exe` SHA-256:
  `7CBC3CF72C86AD51F8571CEDDB373704B1681DBF6443D1D1E3C9C411051AE020`;
- Android APK SHA-256:
  `52D8AD6E259691F52CC80245A884DF322FEB3C02F374BB0CD6A26D98E445AFCF`.

## 8. UAC anulowany — rozliczenie skutków

Operacja `R26-STEP2-20260927T225049Z` nie weszła do skryptu: Windows zwrócił
`Operacja została anulowana przez użytkownika`, katalog OutputRoot nie powstał,
a kolejnego monitu ani alternatywnego kanału nie użyto.

Exact readback potwierdził:

- DB nadal `r25_external_scope_20260927`;
- backend container ID nadal
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest nadal
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- Web nadal `44A53C0B...A115EE`, stable manifest `F65CC515...35E5`, version
  override `4F55994D...F0D82` i Windows executable `C0DE8E94...34CD5`;
- artefakty stable `+43` są nieobecne;
- wszystkie istniejące kontenery zachowały tożsamości, PostgreSQL jest healthy;
- Supervisor i aktywny backup pozostają `0`.

Nie utworzono fixture, więc cleanup residue wynosi zero przez brak rozpoczęcia.
Migracja, deployment Web/backend/Windows/Android oraz synthetic live smoke są
`NOT_RUN`. Był to historyczny K1 `DEPLOYMENT_NOT_RUN_UAC_CANCELLED`,
zastąpiony bieżącym wynikiem opisanym w sekcji 10.

## 9. Bieżący status

- R25: `ACCEPTED`;
- R26 krok 1: `ACCEPTED / OWNER_CONFIRMED`;
- R26 krok 2: `R26_STEP2_IN_PROGRESS / CONSOLIDATED_K1 /
  CHANGES_REQUIRED`;
- source/test/build: `PASS / PUBLIC`;
- deployment/live smoke: `NOT_RUN`;
- R04: `IN_PROGRESS / ORGANIZACYJNIE_WSTRZYMANE`;
- D-22: `NOT_RUN`.

## 10. Świeża próba deploymentu — backup preflight K1

Operacja `R26-STEP2-LIVE-20260928T142708Z` otrzymała UAC i przeszła exact
preflight, lecz zatrzymała się przed mutacją. Standardowy database backup do
`F:\dump` nie utworzył checkpointu, ponieważ Windows PowerShell 5.1 rozwinął
jedną wartość `$selectedCollections` do skalarnego `String`, po czym StrictMode
odrzucił odczyt `.Count` w `backup-production.ps1`.

Read-only reprodukcja potwierdziła `PropertyNotFoundStrict`; nie jest to wada
R26 ani buildów `+43`. `mutation_started=false`, `pending_mutation=false`,
backup/migracja/deployment/smoke są `NOT_RUN`, a produkcja pozostała dokładnie
na preimage `+42`. Drugi UAC nie był dozwolony, ponieważ deployment nie
rozpoczął się. Bieżący K1:
`BACKUP_PREFLIGHT_PS51_SCALAR_COUNT`.

## 11. Minimalny hotfix PS5.1 opublikowany; UAC anulowany bez mutacji

Fail-before na rzeczywistym kodzie runnera odtworzył
`PropertyNotFoundStrict`. Minimalny fix wymusza jednowymiarowe `string[]` oraz
używa jawnego `selectedCollectionCount`; kontrakty nazw, duplikatów, LegacyV1,
RecoveryPointV2, proof mode i destination pozostały bez zmian. Windows
PowerShell 5.1 przeszedł parser oraz 7-przypadkową macierz. Publiczny source
hotfixu: `7dff894b09facc9e8763296a2bf7ea5e03117535`.

Binding audit sklasyfikował bieżący startup manifest jako brak aktywnego
bindingu runnera, historyczne kandydaty jako `HISTORICAL_EVIDENCE`, a recovery
tool manifest 1.2.0 jako `INDEPENDENT_PINNED_TOOL_VERSION`; żadnego z nich nie
zmieniono.

Operacja `R26-STEP2-HOTFIX-20260928T163858Z` nie weszła do skryptu. UAC został
anulowany przed `CreateProcess`, OutputRoot nie powstał i nie użyto retry ani
alternatywnego kanału. Readback potwierdził:

- produkcyjny runner nadal `36724` B / `25BD1F12B237A603D2C19323C175E3220ECFA2E8B97FAB48B05D3DE3CCEB4DDE`;
- DB revision `r25_external_scope_20260927`, `scheduled_date=absent`;
- backend ID `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- active backup `0`, nowy checkpoint nie istnieje;
- migracja/deployment/live smoke/fixture nadal `NOT_RUN`.

Bounded preflight wykazał także brak aktywnego
`C:\ai-lab-core\operations\hardening\invoke-qdrant-backup-helper.ps1`, przy
obecnym validatorze. Pełny RecoveryPointV2 nie może wejść w etap Qdrant bez
tego helpera. Bieżąca zgoda zezwalała w fazie A na instalację wyłącznie
`backup-production.ps1`, więc helpera nie skopiowano.

Bieżący status: `R26_STEP2_IN_PROGRESS / CONSOLIDATED_K1 /
UAC_CANCELLED_NO_MUTATION / QDRANT_HELPER_NOT_INSTALLED`. R26 krok 2 nie jest
`READY_FOR_OWNER_REVIEW` ani `ACCEPTED`.
