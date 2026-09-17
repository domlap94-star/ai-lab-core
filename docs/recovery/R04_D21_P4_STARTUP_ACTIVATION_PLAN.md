# R04 / D-21 / P4-A — pakiet aktywacji jednego startu

Status: `STARTUP_ACTIVATION_PACKAGE_READY_FOR_REVIEW / NOT_INSTALLED / GLOBAL_START_MANIFEST_NOT_APPROVED`

Pakiet: `R04-D21-P4A-STARTUP-ACTIVATION-20260917T210051Z`
Decyzja: `D-21`
Podstawa: P1 launcher source `2e69622bc6a0b4888427f8ae5be119377aed26d9`,
DATA_ONLY source `cb6e22506a0fecc440400566293524536847b9b0`, P3 backend
source `0ee0ea50943578e6e552aae23ce1688595ddc262`.

## 1. Granica i przyjęty stan P3

Właściciel przyjął `P3 CORE_BACKEND_SOURCE_SWITCH_ACCEPTED /
LIMITED_RUNTIME_SCOPE` dla OP_ID
`R04-D21-P3-CORE-SWITCH-20260917T141404Z`. Odbiór obejmuje wykonane
przełączenie backendu, 592/592 bajtów payloadu, zachowaną DB/schema i pending
`18/16/1`, preservation `116 + 87 = 203/203` oraz późniejszy readback dwóch
warstw środowiska `11/11 MATCH`, w tym `9/9` przełączników `false`.

Odbiór nie oznacza pełnego P3/R04, odczytu obiektu `Settings` w pamięci,
historii wszystkich dispatcherów, globalnego braku zapisów ani zgody na
launcher, relokację, P4-B/P5 lub nowe funkcje. Globalny manifest pozostaje
`NOT_APPROVED_FOR_START`.

## 2. Wynik P4-A

P4-A przygotowuje wyłącznie nieaktywny zestaw do osobnego review:

- dokładny minimalny payload przyjętego launchera P1 i helpera istniejących
  kontenerów;
- draft manifestu oparty na bieżących tożsamościach sześciu kontenerów;
- rollbackowe kopie pięciu definicji tasków i dwóch obecnych wejść użytkownika;
- wyłączony draft taska `NEXT Stabil - Host`, 1 535 B, SHA-256
  `66810B9DABE86518C28A3D7A9709B8D1DC50688F4B6B2BFC7A69B514D87629CB`;
- changeset triggerów i kolejność instalacji uniemożliwiającą przypadkową
  aktywację.

Lokalny pakiet jest w chronionym stagingu:

`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\p4-startup-activation-20260917T210051Z`

Indeks pakietu ma SHA-256
`DC76525E49B77C7CA791B9724D38F9E26C2FC7FDA8513A2403B7D167481ACB72`.
Jest `LOCAL_ONLY / NOT_INSTALLED / NOT_APPROVED`.

## 3. Minimalny payload

| Rola | Źródło | Docelowa ścieżka po osobnej zgodzie | Bajty | SHA-256 | Stan dziś |
| --- | --- | --- | ---: | --- | --- |
| Launcher | `operations/runtime/start-host-services.ps1` z P1 | `C:\ai-lab-core\operations\runtime\start-host-services.ps1` | 62 651 | `12B978E97DFE5766945238EF92C591AC3DC6896E71279EA3B3D792A9EFD73108` | Brak w instalacji |
| Runtime validator | `operations/runtime/startup-runtime.ps1` z DATA_ONLY | `C:\ai-lab-core\operations\runtime\startup-runtime.ps1` | 59 253 | `DC4E5EB638B93470BFF252D23864BBB1FC2F75D001B2D1E9FC20C0B849C0A103` | Brak w instalacji |
| Existing-only helper | `operations/windows/start-compose-after-docker.ps1` z P1 | `C:\ai-lab-core\operations\windows\start-compose-after-docker.ps1` | 880 | `91C763F5D0FF6CC7184E0B238EA6A6047CBB3FB13F88917777F4E0696E9667EC` | Do zastąpienia starego helpera `445AFFC0...EDECC5` |
| P3 override | już zainstalowany plik | `C:\ai-lab-core\operations\runtime\approved-compose\R04-D21-P3-core.override.yml` | 1 174 | `F99BABA92A72DFA366367470181AB1BF9DEC19D71ADBD2CBF1632F0B74DE4E86` | KEEP |

Nie kopiuje się całego `operations` z recovery. Zainstalowane gatewaye i
Supervisor pozostają w swoich obecnych bajtach; draft manifestu wiąże właśnie
te bajty, nie ich recoveryowe odpowiedniki.

## 4. Bieżący zestaw runtime użyty do draftu

Odczyt metadanych `desktop-linux` z 2026-09-17T20:54:22Z pokazał sześć
istniejących, działających kontenerów projektu `ai-lab-core`, wszystkie z
`RestartCount=0`, restart policy `unless-stopped` i siecią `ai-lab-network`:

| Usługa | Pełny ID | Image ID | Dane | Port hosta |
| --- | --- | --- | --- | --- |
| backend | `686ac37663ad369f253eb91da4364aa2bd6c16c77b1205cc41d61c68d4d9c854` | `sha256:6342b36f...d63702` | `/app=C:/ai-lab-core/backend:ro`; `/data=C:/ai-lab-core/data:rw` | `127.0.0.1:8000` |
| postgres | `240343ebff4fb299b239db2817efea1910ab59c29ed3ec9df3a8abde04e81226` | `sha256:a426e44b...d8508d` | `C:/ai-lab-core/data/postgres:/var/lib/postgresql/data:rw` | `127.0.0.1:5432` |
| qdrant | `daa3b0b86b74d4a156522034406f8bd685848181e2467df85d55c37067551fae` | `sha256:0bd98fa7...d5286` | volume `qdrant_storage:/qdrant/storage:rw` | `127.0.0.1:6333/6334` |
| n8n | `a44e719ecfecbd46e982589199706746539217196ccdc1014b8493a23737081c` | `sha256:3c07c723...9c684` | `C:/ai-lab-core/data/n8n:/home/node/.n8n:rw` | `127.0.0.1:5678` |
| open-webui | `9575ca068b8c547c189071f3f950be8b74c7651dc830918ad6979a2e6a654c39` | `sha256:a26effeb...f6b0` | `C:/ai-lab-core/data/openwebui:/app/backend/data:rw` | `127.0.0.1:3000` |
| ollama | `7ff1c45ea12c2d1639471d68a5704b82e262fc422160b6374be36733229ac083` | `sha256:ec24bcaa...036d4` | `C:/ai-lab-core/data/ollama:/root/.ollama:rw` | `127.0.0.1:11434` |

RepoDigests nie zostały utrwalone: projekcja metadanych obrazu utraciła wynik i
nie była ponawiana. Fizyczny backing `qdrant_storage` i Docker/WSL VHD pozostają
`UNKNOWN`; nie wolno zamieniać tego w `ALL_DATA_ON_D_PASS`.

Aktualny odczyt HTTP z 2026-09-17T21:00:51Z dał backend health `200`, public
gateway health `200` i publiczne `/control` `404`. Projekcja pól `/version`
utraciła szczegóły; P3 readback pozostaje właściwym dowodem source/schema.

## 5. Zainstalowane skrypty i narzędzia

| Element | Bieżąca ścieżka | SHA-256 / wersja | Decyzja P4-A |
| --- | --- | --- | --- |
| Public Gateway | `C:\ai-lab-core\operations\gateway\public_web_server.cjs` | `59B21389A25EAD7F73384F3267AD0238F4563B85589D823161A5853ECE41B37A` | KEEP, task jako executor |
| Private Gateway | `C:\ai-lab-core\operations\gateway\web_server.cjs` | `AD9D05F35A86AEDAF2F1522EE330788AD9312040525E5B65AF389EC07DFC06ED` | KEEP, task jako executor |
| Supervisor | `C:\ai-lab-core\operations\supervisor\server.js` | `4CFB7F9E3D97521D8D0F6D588BB119AB34C9D52FAD498AA520368CD13B170701` | KEEP, `INTENTIONALLY_STOPPED` |
| Docker CLI | instalacja Docker Desktop | `46D8A5BD7523C575FB276A75296AB19ABB9BF277D334169C665E521E46DBC2A4`; 29.8.0 | external tool |
| Docker Desktop | instalacja użytkownika | `F508DE4FA1F4A9E2EB8A2DDDE64A10D0CD45414E88CC11E9CD4120247E217799`; 4.91.0.239619 | external tool |
| Node | `C:\Program Files\nodejs\node.exe` | `9A4EB5F1C29C6A2E93852EAD46B999E284A6A5CA8BAB4D4E241D587D025A52DE`; 24.18.0 | external tool |

## 6. Konsolidacja wejść

| Wejście | Stan obserwowany | Rola docelowa | Zmiana dopiero w P4-B |
| --- | --- | --- | --- |
| `NEXT Stabil - Docker Desktop` | enabled, logon trigger | `REPLACE_TRIGGER` | usunąć niezależny logon trigger po zainstalowaniu kompletnego host taska; nie zmieniać instalacji Dockera |
| `NEXT Stabil - Docker Compose` | enabled, logon trigger, stary helper | `DISABLE_DUPLICATE_TRIGGER` | wyłączyć stary automatyczny start; launcher nie wykonuje `compose up` |
| `NEXT Stabil - Public Gateway` | enabled/running, logon trigger | `REUSE_EXECUTOR` | zachować task enabled/on-demand, usunąć jego niezależny trigger |
| `NEXT Stabil - Private Gateway` | enabled/ready, logon trigger | `REUSE_EXECUTOR` | zachować task enabled/on-demand, usunąć jego niezależny trigger |
| `NEXT Stabil - Supervisor` | enabled/ready, logon trigger | `REUSE_EXECUTOR` + `INTENTIONALLY_STOPPED` | zachować executor, usunąć trigger; launcher nie startuje go |
| `NEXT-Stabil-Host.cmd` w Startup | aktywny wrapper wskazujący brakujący launcher | `DISABLE_DUPLICATE_TRIGGER` | wyłączyć/przenieść przed instalacją launchera |
| `NEXT Stabil.lnk` | bezpośrednio otwiera istniejący klient Windows | `HOLD_WITH_REASON` | zachować do implementacji i odbioru `OPEN_AFTER_BASE_READY` |
| Backup 1/2/3, legacy Daily Backup, Trash Purge | odrębne harmonogramy | `KEEP_SEPARATE_SCHEDULE` | bez zmian w P4-B |

Task nie jest tym samym co trigger. Gatewaye i Supervisor pozostają potrzebnymi
wykonawcami on-demand; plan nie usuwa ich całych tasków.

Staging zawiera też pięć nieaktywnych draftów `after`: taski Docker Desktop i
Docker Compose bez triggerów i z `Enabled=false`; taski Public/Private/Supervisor
bez triggerów, nadal `Enabled=true`. Żaden XML nie został zaimportowany.

## 7. Sekwencja P4-B — NOT_EXECUTED / REQUIRES_SEPARATE_APPROVAL

1. Zweryfikować brak driftu pełnych identyfikatorów i zachować rollback XML,
   wrappera i skrótu. Efekt: wyłącznie punkt cofnięcia. Rollback: nie dotyczy.
2. Wyłączyć lub bezpiecznie przenieść `NEXT-Stabil-Host.cmd` ze Startup.
   To musi nastąpić **przed** pojawieniem się launchera pod jego docelową
   ścieżką. Rollback: przywrócić dokładne bajty tylko po przywróceniu poprzedniej
   semantyki startu.
3. Zarejestrować `NEXT Stabil - Host` jako `Enabled=false`, principal `domai`,
   `InteractiveToken`, `LeastPrivilege`, `IgnoreNew`, limit `PT6M`. Nie uruchamiać.
   Rollback: usunąć tylko dokładnie nowy task po potwierdzeniu identity.
4. Usunąć wyłącznie automatyczne triggery z tasków Public/Private/Supervisor,
   pozostawiając executory enabled/on-demand. Wyłączyć legacy Docker Desktop i
   Docker Compose jako konkurujące wejścia dopiero po kontroli definicji.
   Rollback: import dokładnych zachowanych XML; nie startować tasków.
5. Zainstalować trzy pliki payloadu przez atomową kopię i zweryfikować hash.
   Nie kopiować recovery jako rootu. Rollback: przywrócić stary helper i usunąć
   wyłącznie dwa wcześniej nieistniejące pliki.
6. Zainstalować osobno zatwierdzony manifest z `APPROVED` dopiero po uzupełnieniu
   RepoDigest/identity i review właściciela. Obecny draft pozostaje
   `NOT_APPROVED`; jego instalacja nie uprawnia do startu.
7. Włączyć jeden trigger host taska dopiero po fail-closed walidacji całego
   zestawu. Bez `pull/build/create/recreate/up`, migracji i naprawy mountów.
8. W osobnym oknie odbiorowym wykonać kolejno: normalny start, drugi start bez
   duplikatów, Docker ready/not-ready, intentional stop Supervisora, port
   conflict, image/mount mismatch, `/control` boundary, logon/reboot i rollback.

Każdy krok jest `NOT_EXECUTED / REQUIRES_SEPARATE_APPROVAL`. Nieaktywne XML w
stagingu nie zostało zaimportowane.

## 8. Rollback i ryzyka

- Rollback triggerów przywraca definicje, ale nie może automatycznie uruchomić
  Supervisora ani starego compose-up. Każdy start po rollbacku wymaga osobnej
  kontroli skutków.
- Timeout po przekazaniu startu jest `UNKNOWN`, nie dowodem braku startu i nie
  pozwala na retry.
- Zmiana taska lub wrappera może pozbawić użytkownika startu albo go zdublować;
  dlatego host task pozostaje disabled aż do kompletnego zestawu.
- Manualny skrót UI nie może być przełączony na launcher bez funkcji
  `OPEN_AFTER_BASE_READY`; w P4-A pozostaje bez zmian.
- Supervisor jest `INTENTIONALLY_STOPPED`. Jego task pozostaje wykonawcą, ale
  bez automatycznego triggera i bez startu przez launcher.

## 9. Backupy i dane D:

Backup 1/2/3 używają `run-backup-schedule.ps1`, który korzysta z Docker/backend,
ale nie z Supervisora. Legacy backup również nie wymaga Supervisora. Ostatnie
wyniki tasków `267014/1/1` nie są dowodem udanej pracy harmonogramu, dlatego
stan pozostaje `SCHEDULED_BACKUP_OPERATION_NOT_YET_VERIFIED /
REPAIR_PENDING`. Manualny punkt z 17 września nie zmienia tej oceny.

Junction `C:\ai-lab-core\data -> D:\ai-lab-data` i pięć przyjętych bindingów
DATA_ONLY pozostają bez zmian. Qdrant volume, Docker/WSL VHD, profile i inne
ciężkie lokalizacje nie są rozliczone jako D:. P4-A nie wykonuje relokacji i nie
usuwa tej bramki D-21.

## 10. Bramy przed P4-B

- właścicielski review tego exact pakietu i changesetu;
- bezpieczne uzupełnienie brakujących RepoDigests albo świadoma, osobno
  zaakceptowana polityka identity bez ich fabrykowania;
- rozliczenie fizycznego backingu Qdrant/VHD oraz decyzja, czy ograniczony start
  może poprzedzić relokację;
- decyzja o minimalnej funkcji `OPEN_AFTER_BASE_READY` albo jawne utrzymanie
  oddzielnego skrótu UI;
- dokładne, bieżące definicje triggerów bez driftu;
- osobny plan odbioru harmonogramu backupu;
- zatwierdzony manifest startowy; obecny draft nie jest nim.

Następny krok: właścicielski review pakietu P4-A i osobna zgoda na **jeden**
P4-B obejmujący najpierw wyłączenie starego Startup wrappera, instalację
wyłączonego host taska i payloadu, następnie kontrolowaną aktywację dopiero po
zatwierdzeniu kompletnego manifestu. Bez tej zgody nie wolno wykonać żadnego z
powyższych kroków.
