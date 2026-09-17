# R04 / D-21 / P4-A — identity and cold-start handoff

Checkpoint ID: `R04-20260917T225125Z-D21-P4A-IDENTITY-COLD-START`

## Stan

- Parent: `daf0931cff28944e5df528f63cd95b4d99dd041a`.
- Source commit: `8756314f51a76091a483cfc9b677a05c7f67f315`.
- Pakiet: `R04-D21-P4A-STARTUP-ACTIVATION-20260917T210051Z`.
- Wynik source/offline: `READY_FOR_REVIEW / NOT_INSTALLED`.
- Runtime identity readback: `PARTIAL / NOT_VERIFIED / BLOCKING_P4B`.
- Globalny manifest: `NOT_APPROVED_FOR_START`.
- P3 backend switch pozostaje `ACCEPTED / LIMITED_RUNTIME_SCOPE`; nie był
  ponawiany ani cofany.
- Supervisor pozostaje polityką `INTENTIONALLY_STOPPED`; nie był sondowany,
  uruchamiany ani zmieniany przez tę kontynuację.

## Odtworzone braki i poprawka

Na preimage rzeczywisty walidator akceptował obserwację z innym pełnym ID przy
zgodnych pozostałych polach. Faza kontenerowa przetwarzała kolejność draftu
`backend, postgres, ...`, więc syntetyczny zimny start uruchamiał backend przed
PostgreSQL i nie obserwował Docker health. Log fail-before:

- `fail-before-review-findings.json`, 1 072 B,
  SHA-256 `F287EEA275B7DAF2D80E3F1FB68287EBE0E8FFDA1762D00021D5F176570FB754`.

Source `8756314...` dodaje:

- `NEXT_STABIL_STARTUP_PACKAGE_V1` i trzy brakujące role plików;
- niezależne bindingi service label, runtime name i pełnego container ID;
- normalny RepoDigest oraz jawny backend-only
  `LOCAL_IMAGE_ID_CONFIRMED_NO_REPO_DIGEST`, bez fallbacku na timeout/błąd;
- unikalny `startup_order`, wymaganie `HEALTHY` PostgreSQL i zależność backendu;
- bounded wait bez drugiego startu, create/up/recreate/build/pull;
- SHA-256 przez standardową bibliotekę .NET, aby działać w faktycznym
  PowerShell 5.1 `-NoProfile -NonInteractive`.

## Testy offline

Pierwsza końcowa kampania ujawniła niedostępne `Get-FileHash` i zakończyła
pierwszy skrypt exit `1`; zachowany log ma 1 139 B i SHA-256
`3E438E694E7D354AFAE357A60FCCFDB73E19E1C8B62A2E1966C585325DB9EABC`.
Nie jest PASS.

Pass-after na tych samych granicach, Windows PowerShell 5.1, exit `0`:

- `test-start-host-services.ps1`: 53 asercje;
- `test-startup-real-adapters.ps1`: 51 asercji;
- `test-startup-data-junction.ps1`: 44 asercje;
- `test-p4-startup-package.ps1`: 14 asercji.

Log pass-after ma 1 344 B i SHA-256
`75C2BBA85D9EE590D567511B1C07186F857B879878AE3EA6C8821B4F94E281EB`.
Testy korzystały wyłącznie z kompletnych dolnych atrap i własnego syntetycznego
junctionu. Nie uruchamiały realnego Dockera, HTTP, Task Schedulera ani usług.

## Odczyt metadanych

Engine odpowiadał na ograniczone polecenia natywne, lecz bezpieczna projekcja
nie została utrwalona. Trzy kolejne formatowania zatrzymały się przed zapisem:

1. opcjonalne `Mount.Name`;
2. opcjonalne `Healthcheck.StartPeriod`;
3. skalarne `RepoDigests.Count`.

Po trzecim błędzie odczyty przerwano; nie wykonano retry-do-skutku. Bieżąca
`.Name`, pełna nowa projekcja mountów i `RepoDigests` są `NOT_VERIFIED` w tej
kontynuacji. Historyczne dowody P3/P4 zachowują własne daty. Draft używa
`ai-lab-backend` z deklaracji zainstalowanego override P3, nie przedstawia jej
jako nowej obserwacji runtime. Nie wybrano backend-only local-image mode.

## Artefakty i skutki

- Stary indeks 16 plików `DC76525E...ACB72` pozostaje historycznym preimage.
- Indeks efektywnego zestawu kontynuacji obejmuje 18 plików, ma 4 222 B i
  SHA-256 `78966E33376D4A6E118B79AFE2A844403AFEF1B0E56BB8A972B438FB55428482`.
- Jedyny podkatalog kontynuacji znajduje się pod istniejącym chronionym
  stagingiem P4/A; zawiera fail-before, oba logi końcowe, nowy payload i
  wyłączony draft taska z finite `PT15M`.
- Nie zmieniono `C:\ai-lab-core`, kontenerów, tasków, Startup, skrótów,
  dziewięciu flag, junctionu, danych, backupów ani harmonogramów.
- Nie wykonano start/stop/restart/recreate/up/build/pull, SQL, backupu, restore,
  relokacji ani cleanupu.

## Następny krok

Jeden osobno zatwierdzony, poprawnie rejestrowany readback dokładnej nazwy,
pełnych ID i `RepoDigests` sześciu przypiętych zasobów. Dopiero po jego
utrwaleniu można zbudować kompletny draft do review P4/B. Instalacja, task
registration i live startup pozostają `NOT_RUN / NOT_AUTHORIZED`.
