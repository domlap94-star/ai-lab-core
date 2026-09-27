# R26 krok 2 — source/build PASS, UAC anulowany, brak mutacji

## Stan kanoniczny

- pakiet: `R26`, krok 2;
- source SHA: `67b867ee279fe0bf7617c05b7d61fff0b337cab3`;
- branch: `recovery/next-stabil-repair-completion`;
- krok 1: `R26_STEP1_ACCEPTED / OWNER_CONFIRMED`;
- krok 2: `R26_STEP2_IN_PROGRESS / CONSOLIDATED_K1 /
  DEPLOYMENT_NOT_RUN_UAC_CANCELLED`;
- R04: `IN_PROGRESS / ORGANIZACYJNIE_WSTRZYMANE`;
- D-22: `NOT_RUN`.

## Wykonany zakres

Source kroku 2 realizuje:

- query-level active-only i historię po jawnym przełączniku;
- wybór wielu aktywnych grantów i jeden atomowy bulk revoke;
- zachowanie historii, wspólny `revoked_at`, conflict bez częściowego wyniku;
- addytywną `scheduled_date` z backfillem Europe/Warsaw;
- jedną obowiązkową date-only wybieraną z kalendarza, bez pola
  `Rozpoczęto` w UI;
- wersję `1.0.2+43` dla Web, Windows i Android.

Wyniki przed wdrożeniem:

- focused backend migration/date/bulk: `PASS`;
- direct R25 regressions: `PASS`;
- Python compile: `PASS`;
- Flutter analyze: `PASS`;
- focused Flutter: `29/29 PASS`;
- pełny Flutter: `379/379 PASS`;
- Web/Windows/Android release build: `PASS`;
- repo hygiene i source secret/business scan: `PASS`.

Artefakty:

| Target | SHA-256 |
|---|---|
| Web `main.dart.js` | `F7013E8E5DE072B679703DE07989B34415D4D94BD383C06ACFFBC2B0CAC3D0CB` |
| Windows installer | `562DBE2E41838D4960459958442CE314D1EE5E5299D869F446923666F6841A89` |
| Windows expected installed `frontend.exe` | `7CBC3CF72C86AD51F8571CEDDB373704B1681DBF6443D1D1E3C9C411051AE020` |
| Android APK | `52D8AD6E259691F52CC80245A884DF322FEB3C02F374BB0CD6A26D98E445AFCF` |

## UAC i skutki

Operation ID: `R26-STEP2-20260927T225049Z`.

Windows anulował RunAs przed uruchomieniem procesu. Operation OutputRoot nie
powstał. Zgodnie z decyzją właściciela nie wykonano automatycznego retry,
drugiego kanału ani częściowego deploymentu.

Exact readback po anulowaniu:

- DB head: `r25_external_scope_20260927`;
- backend container ID:
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest:
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- stable manifest:
  `F65CC51573D583C408413CCAAAA62BBED84C9862FA8BB2109F223C48461135E5`;
- version override:
  `4F55994D8258090BC92120A46C48E053877971307297C5CF06F4EF4FC29F0D82`;
- live Web main:
  `44A53C0BF821D31279294D017D4D12673A822AAFFBAAF301B8C90900E4A115EE`;
- installed Windows executable:
  `C0DE8E94FF2BF4280ACDC2C1FA0B65701CB3A19D3269226F6C2BDB664C134CD5`;
- stable artefakty `+43`: nieobecne;
- PostgreSQL: healthy;
- pozostałe kontenery: tożsamości zachowane;
- Supervisor process/listener: `0/0`;
- active backup: `0`;
- pending mutation: brak;
- fixture R26S2: nie utworzono, więc residue `0` przez brak rozpoczęcia.

## Pozostały materialny K1

`DEPLOYMENT_NOT_RUN_UAC_CANCELLED`:

- migracja `r26_step2_20260928`: `NOT_RUN`;
- backend/Web/Windows/Android deployment: `NOT_RUN`;
- syntetyczny live smoke i exact cleanup: `NOT_RUN`;
- runtime acceptance: `NOT_RUN`.

Nie wolno nadać `R26_STEP2_READY_FOR_OWNER_REVIEW` ani `R26_STEP2_ACCEPTED`.
Kolejne wykonanie hosta wymaga nowej, bieżącej zgody; ten checkpoint nie jest
taką zgodą.

---
R25: `ACCEPTED` · R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` · R26 krok 2:
`IN_PROGRESS / CONSOLIDATED_K1` · R04: `IN_PROGRESS / WSTRZYMANE` · D-22:
`NOT_RUN`
