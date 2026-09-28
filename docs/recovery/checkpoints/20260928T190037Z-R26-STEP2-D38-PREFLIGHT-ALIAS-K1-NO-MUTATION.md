# R26 krok 2 — D-38 zatrzymane przed mutacją przez kolizję aliasu PS5.1

## Wynik

- decision: `D-38`;
- operation ID: `R26-STEP2-D38-20260928T185418Z`;
- OutputRoot:
  `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-D38-20260928T185418Z`;
- jeden UAC: `ACCEPTED / CONSUMED`;
- proces podniesiony: exit `1`;
- `mutation_started=false`;
- `pending_mutation=false`;
- backup/migracja/deployment/live smoke: `NOT_RUN`;
- status: `R26_STEP2_IN_PROGRESS / FINAL_CONSOLIDATED_K1 /
  D38_PS51_ALIAS_COLLISION_BEFORE_MUTATION`.

## Preflight

- local/tracking/remote przed operatorem:
  `4a672e6323fa4b48c2f7115ce15441f7758e357e`;
- worktree przed lokalnym operatorem: clean;
- runner source, helper source, parser PS5.1, test 7/7 i helper contract: PASS;
- artefakty Web/Windows/Android `1.0.2+43`: exact hashes PASS;
- startup manifest, sześć kontenerów, DB R25, brak `scheduled_date`, active
  backup `0`, Supervisor `0/0`, fixture `0`, emulator i `F:\dump`: bounded
  preflight PASS;
- operator po korekcie rozliczania `pending_mutation` ponownie przeszedł parser
  PS5.1.

## Konkretny fail-before

Podniesiony proces utworzył wyłącznie OutputRoot, pusty katalog `preimages` i
`journal.json`. Pierwsza kontrola źródła zakończyła się przed kopiowaniem
preimages i przed ustawieniem `mutation_started`:

`Cannot bind parameter 'Id'. Cannot convert value
"C:\ai-lab-core-recovery\operations\hardening\backup-production.ps1" to type
"System.Int64".`

Przyczyna jest jednoznaczna: operator deklarował jednoliterową funkcję skrótu
hashującego `H`, lecz Windows PowerShell 5.1 ma wbudowany alias
`h -> Get-History`. Alias ma pierwszeństwo w rozwiązywaniu polecenia, dlatego
wywołanie `H $path` trafiło do parametru `Get-History -Id`. Lokalny parser nie
wykrywa kolizji nazw poleceń i poprawnie zwrócił PASS.

Próba ścieżki rollback zgłosiła brak preimage, ponieważ fail nastąpił przed
jego utworzeniem. Nie jest to nierozliczona mutacja: journal zachował
`mutation_started=false`, a bezpośredni readback celów potwierdził stan
wejściowy.

## Końcowy readback

- runner: `36724` B,
  `25BD1F12B237A603D2C19323C175E3220ECFA2E8B97FAB48B05D3DE3CCEB4DDE`;
- helper: `ABSENT`;
- startup manifest:
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- Web main: `44A53C0BF821D31279294D017D4D12673A822AAFFBAAF301B8C90900E4A115EE`;
- Windows executable:
  `C0DE8E94FF2BF4280ACDC2C1FA0B65701CB3A19D3269226F6C2BDB664C134CD5`;
- Android emulator: `versionName=1.0.2`, `versionCode=42`;
- checkpoint `F:\dump\20260928T185718Z`: absent;
- operation-owned hardening staging residue: `0`;
- fixture utworzone przez D-38: `0` przez brak wejścia do tej fazy.

Po UAC odczyt Docker/CIM z niepodniesionego procesu nie miał uprawnień, dlatego
nie jest przedstawiany jako nowy runtime proof. Nie wpływa to na wynik
mutacji: operator zakończył się na pierwszej kontroli pliku przed jakimkolwiek
wywołaniem Docker, backupu lub produktu.

## Bramka

D-38 zezwalała na dokładnie jeden UAC i zabraniała automatycznego ponowienia.
Nie wykonano drugiego UAC, retry ani alternatywnego kanału. Usunięto wyłącznie
nieśledzony lokalny operator. Do osiągnięcia
`R26_STEP2_READY_FOR_OWNER_REVIEW` nadal wymagane są instalacja toolsetu,
RecoveryPointV2, migracja/deployment oraz live smoke w nowej jawnie
autoryzowanej operacji z helperami o niekolidujących nazwach.

---
R25: `ACCEPTED` · R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` · R26 krok 2:
`IN_PROGRESS / FINAL_CONSOLIDATED_K1` · R04: `IN_PROGRESS / WSTRZYMANE` ·
D-22: `NOT_RUN`
