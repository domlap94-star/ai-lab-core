# R26 krok 1 — READY FOR OWNER SMOKE

**Czas:** 2026-09-27T19:55:41Z

**Branch:** `recovery/next-stabil-repair-completion`

**Pakiet:** `R26 — Bezpośrednie udostępnianie klienta`

## Wynik użytkowy

Przycisk `Udostępnij klienta` działa na liście klientów i w szczegółach.
Rozwija aktualną listę External bez aktywnego grantu, wybór otwiera dialog bez
mutacji, `Anuluj` wykonuje zero POST, a `Udostępnij` wykonuje dokładnie jeden
istniejący POST grantu. Po sukcesie użytkownik znika z dostępnych opcji i
pozostaje bieżący ekran.

## Source i release

- feature source: `d34bb805...`;
- version correction `1.0.2+42`: `b1ff82b8...`;
- transactional deployment source: `5492009d...`;
- final Windows startup binding: `ccfd4846...`;
- backend/schema/migracje: bez zmian;
- Flutter focused: `11/11` i `16/16` PASS;
- Flutter full: `374/374` PASS;
- Flutter analyze: PASS.

Artefakty:

- Web main: `44A53C0BF821D31279294D017D4D12673A822AAFFBAAF301B8C90900E4A115EE`;
- Windows installer: `1F920C494704F7FA2E91ADC1049DB4002A3B210A4F15948013D5237BC8AB013E`;
- installed Windows executable:
  `C0DE8E94FF2BF4280ACDC2C1FA0B65701CB3A19D3269226F6C2BDB664C134CD5`;
- Android APK: `10A1193AB6FE50F567549F6F42AA40AE829896B23BA8986EA8E8BE25927BE027`;
- stable manifest: `F65CC51573D583C408413CCAAAA62BBED84C9862FA8BB2109F223C48461135E5`;
- startup manifest: `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`.

## Deployment i platform smoke

Operation `R26-DIRECT-SHARE-20260927-B1FF82B824D8` ma `PASS`,
`APPROVED_FOR_START` i `pending_mutation=false`. Web health/version są `200`,
a publiczne `/control*` pozostaje `404`. Android `1.0.2+42` na jedynym
emulatorze przeszedł podpis v2, launch, login screen, pause/resume,
close/reopen i crash count 0. Windows `1.0.2+42` przeszedł exact-root/hash oraz
sekwencyjne launch/close/reopen.

## Syntetyczny live smoke i cleanup

Za zgodą właściciela utworzono wyłącznie fixture R26S1: User, External Alpha,
External Beta, Klient testowy A i pre-grant Beta -> A. Live UI/API potwierdził:

- Alpha dostępny, Beta wykluczony przez aktywny grant;
- wybór i anulowanie: zero mutacji;
- potwierdzenie: dokładnie jeden `POST /api/v1/client-access/grants` z `201`;
- po sukcesie Alpha i Beta wykluczeni z listy;
- External Alpha: dokładnie jeden udostępniony klient A;
- revoke obu grantów istniejącym endpointem;
- dokładny cleanup fixture w jednej transakcji;
- końcowe residue: `users=0`, `clients=0`, `grants=0`.

Nie zapisano do Git screenshotów, poświadczeń, tokenów, danych firmy ani raw
logów. Historyczna pierwsza próba deploymentu zachowuje własny fail-safe
rollback po mismatch hasha narzędzia; nie pozostawiła pending mutation.

## Stan i następny krok

- `R25_ACCEPTED`;
- R26 krok 1: `IMPLEMENTED / DEPLOYED / READY_FOR_OWNER_SMOKE`;
- R26 krok 2: `DEFERRED / NOT_AUTHORIZED / NOT_STARTED`;
- techniczne K0/K1 kroku 1: `BRAK`;
- R04: wstrzymane;
- D-22: `NOT_RUN`;
- następny krok: wyłącznie praktyczny odbiór nowego przycisku przez
  właściciela; agent nie nadaje `R26_ACCEPTED`.

Status kanoniczny:

`R25_ACCEPTED / R26_STEP1_READY_FOR_OWNER_SMOKE / R26_NOT_ACCEPTED`
