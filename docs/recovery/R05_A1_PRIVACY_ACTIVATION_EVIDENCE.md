# R05-A1 — aktywacja Visual V2 i dopuszczenie dokładnych bajtów

## Wynik

Status podetapu: `SOURCE_PARTIAL / NOT_DEPLOYED`.

Właściciel zaakceptował R04-A3 w zakresie źródeł
`41d2b844a7b120a79001ad5cfbe6304b30580dfc` i dowodów
`457a4321db835421c0d06847e2132d9623d735ae`. Zestaw
`R04-A3-20260911T091750Z-41d2b844` pozostaje `TEST_ONLY`.
Odbiór zachowuje dwa ograniczenia: brak zachowanego stdout/exit wrappera
kompilacji Web oraz `test_followup_chunk13_api_auth.py = NOT_RUN`.

Nowa kontrola Visual V2 została zaimplementowana jako WIP i przeszła testy
pozytywne/negatywne, ale repo nadal zawiera aktywną ścieżkę Vision V1, która
może wysłać materiał do Supervisora bez tego samego dopuszczenia dokładnych
bajtów. Nie wolno więc deklarować pełnej ochrony granicy eksportu ani
commitować tego WIP jako `SOURCE_PASS`.

## Mapa badanego przepływu

1. Assistant/preparation wywołuje `VisualV2Service.ensure()` i zapisuje
   `AnalysisJob` / `AnalysisJobSource`.
2. `advance()` wybiera źródła i przygotowuje finalny raster w lokalnym stagingu.
3. Dopuszczenie operatora wiąże sprawę/źródło, wersję i checksum oryginału,
   hash finalnego rastra, hash pakietu, kanał oraz wersję polityki.
4. Bezpośrednio przed `create_job()` finalne bajty, źródła i pakiet są ponownie
   sprawdzane. Do fake Supervisora trafia tylko zatwierdzony zestaw.
5. Niezależna starsza ścieżka
   `documents/router.py` / `technical_ai_service.py` →
   `vision_dispatcher.py` → `VisionProcessingService.advance()` nadal może
   utworzyć job Supervisora bez tej kontroli. Produkcyjna konfiguracja ma
   historycznie `VISION_AUTOMATION_ENABLED=true`; nie uruchamiano jej w tej
   sesji.

## Zaimplementowany WIP Visual V2

- `VISUAL_V2_ENABLED` ma bezpieczny domyślny stan `false`; brak/false nie
  uruchamia pętli Visual V2.
- `ensure()` i bezpośredni `advance()` odmawiają nowej pracy, gdy funkcja jest
  wyłączona. Zaakceptowany lokalny wynik historyczny może nadal zostać użyty
  bez eksportu.
- Dopuszczenie jest zapisem serwerowym w istniejącym ledgerze
  `AnalysisJob.quality_signals`; nie jest zaufanym polem requestu i nie wymaga
  migracji. Utworzyć je może tylko aktywny administrator.
- Polityka `visual-export-v1` dopuszcza `public_safe` albo
  `locally_redacted`, dokładny kanał `temporary_chat_visual`, scope i czas
  ważności. `restricted_never_external` zawsze blokuje.
- Oryginał pozostaje niezmieniony. Staging korzysta z wyłącznego utworzenia
  pliku i ponownie sprawdza hash bajtów przed handoffem. Zmiana źródła,
  ścieżki/symlinku, rastra, pakietu, polityki, wygaśnięcie albo cofnięcie zgody
  kończą się odmową.
- Metadata eksportu nie zawierają nazw klientów, oryginalnych nazw plików,
  ścieżek ani EXIF.
- Niepewny wynik handoffu nie jest automatycznie wysyłany drugi raz.

Zmodyfikowane, niezatwierdzone pliki WIP:

- `backend/app/core/config.py`;
- `backend/app/main.py`;
- `backend/app/services/visual_v2_service.py`;
- `backend/test/test_visual_v2_service.py`.

WIP pozostaje `LOCAL_ONLY` jako patch:
`C:\ai-lab-core-staging\recovery\R05_A1_WIP_20260911T133256Z\r05-a1-source-wip.patch`,
44 444 B, SHA-256
`357AF58A42C94ADC09C88DFB2F15D5C36538C6035275ECC72B79E4409C65D958`.

## Fail-before i pass-after

Pierwsza poprawna konfiguracja odtworzenia luki, w przypiętym obrazie R02,
`--network none`, read-only source i syntetycznym `DATA_DIR`, zakończyła się:

- `test_r05_a1_disabled_visual_dispatcher_does_not_start`: FAIL,
  `R05_A1_ACTIVATION_FLAG_MISSING`;
- `test_r05_a1_unapproved_pixels_do_not_reach_supervisor`: FAIL, ponieważ
  niezatwierdzone piksele doszły do fake Supervisora;
- razem `2 failed`, exit `1`.

Po WIP wykonano:

```powershell
docker run --rm --network none --read-only --tmpfs /tmp `
  --mount type=bind,source=C:\ai-lab-core-recovery\backend,target=/workspace/backend,readonly `
  -w /workspace/backend <R02_IMAGE_ID> -m pytest -q -p no:cacheprovider `
  test/test_visual_v2_service.py test/test_assistant_visual_branch.py
```

Wynik: `68 passed`, exit `0`. Użyty image ID:
`sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`.
Świeży log: `LOCAL_ONLY` pod katalogiem WIP, 1 765 B, SHA-256
`BDEE7C1C9E9DF64099A413592AB1F7A2606A1E6EE7CFF37572B3BF579FB29782`.

Testy obejmują: wyłączenie startupu, bezpośredni `advance`, wcześniejszy queued
job, niezaufany payload, sztuczne PII w pikselach, positive exact-byte handoff,
minimalne metadata, actor bez uprawnień, obcy scope, cofnięcie/wygaśnięcie,
restricted, zmianę bajtu źródła i rastra, symlink/obcą ścieżkę, zmianę pakietu,
lokalny reuse oraz niepewny handoff bez duplikatu.

W osobnej syntetycznej bazie PostgreSQL, na nowej sieci `internal`, bez host
ports i produkcyjnych mountów, wykonano istniejące migracje do
`followup_assistant_chat_history_20260829` i testy ingestion/chat:
`18 passed`, exit `0`. Kontener i sieć o prefiksie
`next-stabil-r05-a1-test-20260911t132905z` usunięto po kontroli ownera i ID.
Pierwsza próba zestawu DB została odrzucona przez guard z powodu niedozwolonej
nazwy bazy; testów wtedy nie wykonano. Następna użyła
`ai_lab_isolated_r05_a1_132905`.

`test_followup_chunk13_api_auth.py` pozostaje `NOT_RUN`: jego `TestClient(app)`
uruchamia pełny lifespan, którego ta zgoda zabrania. Nie zastąpiono tego
stałym adminem ani pozornym auth PASS.

## Pozostała bramka

Pełne domknięcie wymaga osobnej, jawnej zgody na kompatybilne objęcie albo
bezpieczne wycofanie alternatywnej granicy Vision V1, co najmniej w:

- `backend/app/services/vision_dispatcher.py`;
- `backend/app/api/documents/router.py`;
- `backend/app/services/technical_ai_service.py`;
- odpowiadających testach kontraktu i auth.

Próba rozszerzenia obecnego diffu na tę publiczną/runtime ścieżkę została
zatrzymana przez bramkę bezpieczeństwa jako szersza zmiana migracyjna. Nie
obchodzono jej i nie zmieniono tych plików. Do czasu decyzji: `REAL_EXPORT` i
`END_TO_END` pozostają `NOT_VERIFIED`, R05 `IN_PROGRESS`, a źródła WIP są
`NOT_DEPLOYED`.

## Skutki

Nie uruchomiono aplikacji, lifespan, prawdziwych dispatcherów, Supervisora,
Temporary Chat, Qwena, embeddingu, Qdrant, Gmaila ani produkcyjnych kolejek.
Nie było produkcyjnych zapisów, migracji, deployu, builda frontendowego ani
zmian main/rescue. Utworzono wyłącznie syntetyczne rekordy/pliki i jeden
efemeryczny PostgreSQL; zasoby kontenerowe tej sesji usunięto, a patch i log
pozostają chronione `LOCAL_ONLY`.
