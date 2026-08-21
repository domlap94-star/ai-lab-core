# NEXT Stabil — Recovery

Minimalne, niezależne od backendu narzędzie Windows do walidacji i kontrolowanego
odtwarzania checkpointów `NEXT_STABIL_BACKUP_V1`.

## Build

Host nie ma SDK ani targeting packa `dotnet`. Projekt celowo używa wbudowanego
w Windows .NET Framework 4.8 oraz kompilatora Roslyn dostarczonego z Visual
Studio 2022. Build odwołuje się bezpośrednio do lokalnych assemblies runtime,
bez NuGet i bez instalowania dodatkowego frameworka:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Wynik trafia do nieśledzonego `recovery-dist\`:

```text
recovery-dist\
  NEXT-Stabil-Recovery.exe
  recovery-tool-manifest.json
  helpers\
```

`build.ps1` kopiuje wyłącznie allowlistę zaufanych helperów i zapisuje ich
SHA-256. Aplikacja weryfikuje manifest helperów przed uruchomieniem restore.

## Tryb diagnostyczny

Walidację bez UI można wykonać poleceniem:

```powershell
.\dist\NEXT-Stabil-Recovery.exe --validate C:\backup\checkpoint --json
```

Nie jest potrzebny backend, JWT ani baza historii backupów. Folder wskazuje
operator, a źródłem prawdy jest manifest i zawartość checkpointu.

## Brama produkcyjna

Build/test nie wykonują restore produkcji. W tym repozytorium silnik kończy
każde wywołanie bez `-ProofOnly` kodem
`production_restore_approval_required`, zanim zatrzyma usługę lub zmieni dane.
Reviewed host-specific cutover module może zostać dołączony dopiero po osobnym
`FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED`; sama zmienna środowiskowa nie
odblokowuje destrukcyjnego działania. Proof mode zawsze używa izolowanych celów
`ai_lab_restore_test_*` oraz tymczasowych kontenerów/wolumenów.

## Zaufanie do pliku wykonywalnego

Na chronionym hoście Bitdefender klasyfikuje niepodpisany plik wykonywalny jako
`Gen:Variant.MSILHeracles.239070` już podczas zapisu i przenosi go do
kwarantanny przed uruchomieniem. Nie należy wyłączać ochrony ani dodawać
szerokiego wykluczenia. Finalny artefakt i smoke UI pozostają zablokowane do
czasu zatwierdzenia wąskiej polityki zaufania/podpisu kodu:
`RECOVERY_APP_TRUST_POLICY_APPROVAL_REQUIRED`.
