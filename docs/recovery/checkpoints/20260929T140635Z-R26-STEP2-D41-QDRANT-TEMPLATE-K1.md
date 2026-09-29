# R26 krok 2 — D-41 diagnostyka helpera PASS, Qdrant template K1

## Wynik użytkowy

- decision: `D-41`;
- operation ID: `R26-STEP2-D41-20260929T140500Z`;
- OutputRoot:
  `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-D41-20260929T140500Z`;
- jeden UAC: `ACCEPTED / CONSUMED`;
- runner i helper: `PASS / INSTALLED / PRESERVED`;
- bezpośredni Qdrant proof: `FAILED / PRE_INVENTORY`;
- pełny RecoveryPointV2 i produkt R26 krok 2: `NOT_RUN`;
- `pending_mutation=false`;
- status: `R26_STEP2_IN_PROGRESS / FINAL_CONSOLIDATED_K1 /
  D41_QDRANT_GO_TEMPLATE_QUOTE_LOSS_PRE_INVENTORY`.

## Minimalna naprawa source i testy

Granica runner -> helper została zmieniona tak, aby helper zawsze zapisywał
strukturalny wynik zawierający co najmniej `stage`, `code`, `message`,
`exit_code`, bounded `stdout`/`stderr`, stan głównego Qdrant, helpera,
stagingu i cleanupu. Runner zachowuje ten wynik także po niepowodzeniu childa.
Helper rozdziela błąd pierwotny od błędu cleanupu i nie nadpisuje pierwszej
przyczyny.

Source opublikowano jako:
`735003a56dba979df4bd6755b24c89e0efde20f1`.

Końcowe pliki source:

- `backup-production.ps1`: `54827` B /
  `6CFFA1EC2CE8242EFD541B931B3E68790FD0FD36F3EC9F4871721356D6A542B6`;
- `invoke-qdrant-backup-helper.ps1`: `24049` B /
  `60203C42C6971F518B9260A581C40F0A09CECD1C38E089ECEF4E64FB9B37A704`.

Testy Windows PowerShell 5.1 i Node:

- parsery: PASS;
- kontrakt diagnostyczny helpera: `67` asercji PASS;
- transport PostgreSQL: `24` asercje PASS;
- selection: `7/7` PASS;
- helper contract: PASS;
- `git diff --check`, secret scan i business-content scan: PASS.

## Operator, ValidateOnly i preflight

- operator LOCAL_ONLY:
  `C:\Users\domai\AppData\Local\Temp\R26-STEP2-D41-20260929T140000Z-operator.ps1`;
- bytes: `42606`;
- SHA-256:
  `D429BA36AC3A7B39701CD3FCCBFDCA7D8165D2900F6E5F6924241CD32F5A7036`;
- parser PS5.1: PASS;
- alias audit: `18` funkcji, `57` jawnych poleceń, `0` kolizji;
- ValidateOnly: PASS (`67/24/7` i helper contract);
- produkcyjne/Docker/DB/backup/UAC writes w ValidateOnly: `0`.

Bounded preflight potwierdził local/tracking/remote `735003a...`, worktree
clean, sześć wymaganych kontenerów running, DB
`r25_external_scope_20260927` bez `scheduled_date`, active backup `0`,
fixture `0`, Supervisor `0/0`, tylko emulator `emulator-5554` oraz około
`490 GB` wolnego miejsca na F:.

## Instalacja toolsetu

Jedyny UAC uruchomił elevated PID `12388`, który zakończył się kodem `1` po
kontrolowanym K1. Zainstalowane i zachowane zostały wyłącznie pliki fazy
toolsetu:

- runner: `6CFFA1EC2CE8242EFD541B931B3E68790FD0FD36F3EC9F4871721356D6A542B6`;
- helper: `60203C42C6971F518B9260A581C40F0A09CECD1C38E089ECEF4E64FB9B37A704`.

Nie rozpoczęto fazy pełnego backupu ani mutacji produktu.

## Materialny K1 Qdrant

Bezpośredni proof helpera utworzył poprawny strukturalny wynik, więc D-41
usunęła wcześniejszą lukę diagnostyczną. Wynik wskazuje dokładnie:

- `status=FAIL`;
- `stage=PRE_INVENTORY`;
- `code=template`;
- `exit_code=0`;
- bounded stderr/message:
  `template parsing error: template: :1: unexpected "/" in operand`;
- `primary_stopped=false`;
- `helper_created=false`;
- `helper_removed=true`;
- `staging_residue_count=0`;
- `helper_container_residue_count=0`;
- `cleanup_error` pusty.

Przyczyną jest utrata wewnętrznych cudzysłowów w argumencie Go-template
Docker podczas natywnego wywołania przez Windows PowerShell 5.1. Wyrażenie
porównujące `Mounts[].Destination` do `/qdrant/storage` dociera do Docker bez
cytowanego literału i parser zatrzymuje się jeszcze w `PRE_INVENTORY`.

Zgodnie z bramką D-41 nie poprawiano tej nowej przyczyny w tej samej operacji,
nie wykonano retry ani drugiego UAC.

## Końcowy readback i skutki

- główny Qdrant ID:
  `daa3b0b86b748aa3a52052dac08bfde499cf19ad61600a1325e09061a5451fae`;
- Qdrant: running, restart count `0`, `/readyz=200`;
- `ai_lab_document_chunks`: `57` punktów, indexed `0`, aliasy `0`;
- `ai_lab_knowledge_base_chunks`: `157` punktów, indexed `0`, aliasy `0`;
- helper containers: `0`;
- staging residue: `0`;
- proof artifact residue: `0`;
- active backup: `0`;
- DB nadal `r25_external_scope_20260927`, `scheduled_date` absent;
- backend ID nadal
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest nadal
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- Web nadal `44A53C0BF821D31279294D017D4D12673A822AAFFBAAF301B8C90900E4A115EE`;
- Windows nadal
  `C0DE8E94FF2BF4280ACDC2C1FA0B65701CB3A19D3269226F6C2BDB664C134CD5`;
- Android nadal `1.0.2+42`;
- finalny checkpoint backupu: absent;
- migracja/backend/Web/Windows/Android `+43`: `NOT_RUN`;
- live smoke: `NOT_RUN`;
- Supervisor process/listener: `0/0`;
- `pending_mutation=false`.

## Bramka

Do kolejnego proofu potrzebna jest minimalna poprawka przekazania argumentu
Go-template tak, aby cytowany literał `/qdrant/storage` docierał do
`docker inspect` niezmieniony pod Windows PowerShell 5.1, bez zmiany
bezpiecznej semantyki helpera. Skonsumowanego UAC D-41 nie wolno ponawiać.

---
R25: `ACCEPTED` · R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` · R26 krok 2:
`IN_PROGRESS / FINAL_CONSOLIDATED_K1` · R04: `IN_PROGRESS / WSTRZYMANE` ·
D-22: `NOT_RUN`
