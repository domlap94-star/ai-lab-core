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

Krok 2 pozostaje `DEFERRED / NOT_AUTHORIZED / NOT_STARTED`. R26 krok 1 nie
obejmuje filtrowania historii `/shared-clients`, bulk grant/revoke, nowego
endpointu, zmian backendu, migracji, DB/schema, polityki scope R25, R04 ani
D-22.

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
- R26 krok 1: `IMPLEMENTED / DEPLOYED / READY_FOR_OWNER_SMOKE`;
- R26 krok 2: `DEFERRED / NOT_AUTHORIZED / NOT_STARTED`;
- `R26_NOT_ACCEPTED` — odbiór praktyczny należy do właściciela;
- otwarte techniczne K0/K1 w zakresie kroku 1: `BRAK`;
- R04 pozostaje wstrzymane; D-22 pozostaje `NOT_RUN`.
