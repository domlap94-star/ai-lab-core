# R25 — External user / client-scoped access

Status: `R25_READY_FOR_OWNER_REVIEW / NOT_ACCEPTED`.

Ten dokument pozostaje kanonicznym kontraktem R25. Source `34834c96443da619d051b66ea4ef37f055a6549b`, addytywna migracja `r25_external_scope_20260927`, backend, startup manifest, Web, Android `1.0.2+29` i pełny authenticated A/B no-leak E2E pozostają wdrożone i zweryfikowane. Exact Windows `1.0.2+29` został zainstalowany na tej właścicielsko zarządzanej maszynie i przeszedł `SAC_OFF_OWNER_MANAGED_HOST / EXACT_HASH_INSTALLED_ROOT_ACCEPTANCE` oraz syntetyczny UI smoke z exact cleanupem. Otwartych technicznych K0/K1 brak; wynik jest gotowy do odbioru właściciela. Szczegóły zawiera checkpoint `20260927T164120Z-R25-WINDOWS-OWNER-INSTALL-PASS.md`. Wyłącznie właściciel może nadać `R25_ACCEPTED`.

## 1. Efekt użytkowy i zasada nadrzędna

Handlowiec zalogowany jako `External` (`Zewnętrzny`) korzysta z pełnych funkcji biznesowych istniejącej roli `User`, ale tylko w obrębie klientów z aktywnym, ręcznie nadanym grantem. Poza tym zakresem obowiązuje:

`FULL USER FUNCTIONALITY WITHIN ACTIVE CLIENT GRANTS, DEFAULT DENY OUTSIDE CLIENT SCOPE`.

Klient nieudostępniony i wszystkie jego zasoby są niewidoczne oraz niedostępne również przez bezpośrednie ID, URL, download, wyszukiwanie, agregaty, kolejki i AI. R25 nie zmienia praw Administratora/Usera, nie przyznaje External praw administracyjnych i nie opiera zabezpieczenia na ukryciu UI.

## 2. Role i uprawnienia

| Rola | Widoczność klientów | Funkcje biznesowe | Użytkownicy | Grant/revoke |
|---|---|---|---|---|
| Administrator | wszyscy zgodnie z obecnym kontraktem | bez zmian | obecne zarządzanie kontami | grant, revoke, lista i historia |
| User | wszyscy zgodnie z obecnym kontraktem | bez zmian | bez nowych praw administracyjnych | grant, revoke, lista i historia |
| External / Zewnętrzny | wyłącznie aktywne granty | jak User w obrębie klienta | brak zarządzania | brak grant/revoke/delegowania |

External nie otrzymuje dostępu przez autorstwo, przypisanie, odbiorcę maila, wykonawcę zadania ani claim JWT. Jedynym źródłem dostępu jest bieżący aktywny grant. Revoke, deactivation i zmiana roli działają od następnego requestu.

## 3. Model danych i migracja addytywna

Przyszła migracja Alembic musi:

1. Dodać rolę `External`, bez zmiany nazw `Administrator` i `User`.
2. Dodać audytowalny `client_access_grants`: `id`, `client_id`, `external_user_id`, `granted_by_user_id`, `granted_at`, `revoked_by_user_id`, `revoked_at`.
3. Zapewnić FK do klienta/użytkowników, indeksy po `(external_user_id, revoked_at, client_id)` i `(client_id, revoked_at, external_user_id)` oraz unikalność jednego aktywnego grantu pary. Mechanizm PostgreSQL może użyć partial unique index `WHERE revoked_at IS NULL`.
4. Walidować, że odbiorca ma rolę External, aktor jest aktywnym Administrator/User, a klient jest aktywny i nieusunięty.
5. Zachować historię: revoke aktualizuje aktywny rekord; regrant tworzy nowy rekord historyczny; rekordów nie usuwać.
6. Filtrować w SQL, nie po pobraniu tabel do pamięci; zapewnić poprawne scoped count/pagination/sort.

Zmiana `User -> External` natychmiast przełącza na grant scope; `External -> User` przywraca normalny zakres User i zachowuje historię. Dezaktywowany External lub nieaktywny/usunięty klient nigdy nie przechodzi guarda.

Rollback kodu może wyłączyć działanie/logowanie External, ale nie usuwa tabeli ani historii grantów bez osobnej destrukcyjnej zgody.

## 4. Centralna polityka backendu

Implementacja ma wprowadzić jeden moduł polityki, używany przez routery, serwisy, repozytoria, downloady i joby, z odpowiednikami:

- `scope_client_query(current_user, query)`;
- `can_access_client(current_user, client_id)`;
- `require_client_access(current_user, client_id)`;
- `resolve_resource_client_scope(resource)`.

Administrator/User zachowują obecny zakres. Dla External listy są filtrowane aktywnymi grantami; read/create/update/link/move/download wymagają bieżącego scope. Przeniesienie zasobu do nieudostępnionego klienta jest zabronione. Brak lub niejednoznaczny owner client oznacza `DEFAULT DENY`.

Dla niedostępnego rekordu zwracać 404, gdy 403 ujawniałoby istnienie. Odpowiedź nie może ujawnić ID/nazwy klienta, liczników, nazw plików, maili, fragmentów ani różnicy pozwalającej enumerować rekordy.

JWT nadal identyfikuje użytkownika/rolę i `auth_version`, ale nie przechowuje trwałej listy `client_id`. Każdy request odczytuje aktualny grant lub krótki cache z jednoznaczną invalidacją na grant/revoke/deactivation/role change.

## 5. Rozwiązywanie klienta nadrzędnego

| Zasób | Kanoniczny owner client |
|---|---|
| Client, ContactPerson, adres, telefon | bezpośredni `client_id` |
| Project/Realization | `project.client_id` |
| Inspection/SiteVisit | jawny client albo client projektu; konflikt = deny |
| Document/page/asset/attachment | document client albo jednoznaczny project/inspection client |
| Email/thread/attachment | aktualne przypisanie do Client |
| Task/WorkItem | client albo jednoznaczny project/inspection client |
| Timeline/activity/note/comment | owner client encji nadrzędnej |
| AI request/material/job/result | jawny client zapisany przy enqueue |
| Export/report | przecięcie wszystkich rekordów ze scoped client IDs |

Nieprzypisany, wieloklientowy albo nierozstrzygalny zasób jest niedostępny External. Scope podąża za aktualnym powiązaniem A/B. Grant klienta obejmuje przyszłe zasoby tego klienta; nie powstają granty per zasób.

## 6. Macierz pełnego pokrycia

| Obszar | Ustalenie klienta | List filter | Object guard | Create/update | Download/file | Test braku przecieku |
|---|---|---:|---:|---:|---:|---|
| Klienci, kontakty, adresy, telefony, status/historia | bezpośredni klient | tak | tak | tak | jeśli występuje | A widoczny, B 404 |
| Projekty/realizacje, aktywności i dokumenty | `project.client_id` | tak | tak | tak | tak | `project_id` B 404 |
| Wizje/oględziny, terminarz, formularze, zdjęcia, pomiary | inspection/project/client | tak | tak | tak | tak | `inspection_id` i media B 404 |
| Dokumenty, wersje, preview, thumbnail, raw | document/project/inspection client | tak | tak | tak | obowiązkowo | `document_id`/`attachment_id` B 404 |
| Maile/wątki/załączniki/send/reply | przypisany klient | tak | tak | kontekst i odbiorcy klienta | obowiązkowo | email/thread/attachment B 404; brak unassigned |
| Zadania/kalendarz | client/project/inspection | tak | tak | wymagany grant | jeśli występuje | global/bez klienta hidden |
| Timeline/notes/comments | owner client | tak | tak | tak | jeśli występuje | ID B 404 |
| Search/autocomplete/recent | owner każdego wyniku | tak, przed limit | tak | n/d | wynikowy guard | zero wyników/liczników B |
| Dashboard/count/alerts/summary | scoped SQL aggregates | tak | n/d | n/d | n/d | count tylko A |
| Powiadomienia | target owner client | tak | tak przy otwarciu | enqueue scope | target guard | revoke blokuje cel |
| Eksport/report | dozwolone client IDs | tak | tak | tworzenie scoped | artefakt scoped | brak global export |
| AI/Assistant/retrieval/vector | obowiązkowy jawny klient | tak przed retrieval/limit | tak | enqueue actor+scope | result guard | brak cross-client RAG |
| Asynchroniczne joby | zapisany actor/client | kolejka scoped | worker revaliduje | bez rozszerzenia | result scoped | revoke/role change fail closed |

## 7. Maile

External widzi tylko przypisane maile, wątki, załączniki i wysłane wiadomości udostępnionego klienta. Nie widzi globalnej ani nieprzypisanej skrzynki, kandydatów, wyników globalnego mail search ani istnienia innych wiadomości. Send/reply wymaga jawnego klienta; odbiorca należy do klienta/kontaktu, chyba że istniejący bezpieczny kontrakt sprawy dopuszcza dodatkowego odbiorcę. Nowa wiadomość jest związana z tym klientem; External nie może przepisać jej do innego.

## 8. Globalne obszary niedostępne

External ma backendowy deny dla: zarządzania użytkownikami/rolami/grantami, panelu systemowego, backup/restore, security settings, globalnego kosza, unassigned mail i kandydatów, globalnej KB, globalnych statystyk, admin tools, globalnych eksportów i każdego obszaru bez jednoznacznego client scope.

## 9. API grantów

Zgodnie z istniejącą konwencją backend ma zapewnić:

- shared clients bieżącego External;
- aktywne i historyczne granty dla Administrator/User;
- filtry po kliencie i External;
- idempotentny grant;
- idempotentny revoke;
- audit read.

Zarządzać mogą wyłącznie Administrator/User; External otrzymuje deny. Odpowiedzi zawierają wyłącznie `client_id`, `external_user_id`, actor/time revoke/grant i `active`, bez sekretów. Atomiczny grant/revoke blokuje duplikaty i race conditions.

## 10. Flutter — „Udostępnieni klienci”

Wspólna implementacja Windows/Android/Web dodaje `/shared-clients`.

- Administrator/User: klienci, External z dostępem, Udostępnij/Cofnij, filtry, historia, potwierdzenie revoke, empty/error states.
- External: wyłącznie własne shared clients, brak kontrolek, wejście do pełnego workspace klienta, brak globalnej liczby.
- Po login External trafia na `/shared-clients`; nie widzi globalnej zakładki Klienci.
- Menu External może zawierać tylko backendowo scoped: shared clients, zadania, realizacje, wizje, dokumenty, maile i Assistant z klientem.

UI jest ergonomią, nie granicą bezpieczeństwa.

## 11. Statyczny inventory obecnego kodu

| Obszar i obecny stan | Rzeczywiste ścieżki | Wpływ R25 | Guardy/testy |
|---|---|---|---|
| Role/User istnieją; Administrator/User są walidowane jawnie | `backend/app/models/role.py`, `user.py`, `api/auth.py`, `api/admin_users.py`, `services/user_lifecycle_service.py`, `database/seed_admin.py` | External role, grant model, role-change invalidation; tworzenie kont pozostaje admin-only | migration/auth/lifecycle/negative role tests |
| Klienci i kontakty mają repo/service/router | `api/clients/router.py`, `services/client_service.py`, `contact_person_service.py`, `repositories/client_repository.py`, modele `client*.py` | list SQL scope i object/create/update guards | A/B list/direct/edit/contact tests |
| Projekty | `api/projects/router.py`, `services/project_service.py`, `repositories/project_repository.py`, `models/project.py` | scope po `client_id` | list/object/write/document tests |
| Inspections | `api/inspections/router.py`, `services/inspection_service.py`, `repositories/inspection_repository.py`, `models/inspection.py` | resolver project/client i media guard | direct ID/file/calendar tests |
| Dokumenty/downloady | `api/documents/router.py`, `services/document_service.py`, `document_read_service.py`, `document_thumbnail_service.py`, `repositories/document*.py`, modele `document*.py` | wszystkie list/preview/raw/upload/download/version paths | document/asset/attachment B 404 |
| Mail | `api/mail.py`, `services/global_mail_service.py`, `client_email_service.py`, `mail_send_service.py`, `repositories/global_mail_repository.py`, `client_email_repository.py` | wyłączyć unassigned/global; scope list, direct, attachment, send/reply | A positive, B/unassigned negative |
| Zadania/kalendarz | `api/work_items.py`, `api/calendar.py`, `services/work_item_service.py`, modele `work_item*.py`, `absence_request.py` | owner resolver; hide global/absence for External | list/direct/create/move/calendar tests |
| Search/dashboard/activity | `api/search/router.py`, `services/global_search_service.py`, `recent_activity_service.py`, `client_activity_service.py`, `api/activity.py` | SQL scope przed limit/count | no count/recent/autocomplete leaks |
| AI/retrieval/jobs | `api/ai.py`, `services/unified_assistant_service.py`, `assistant_run_*`, `client_knowledge_service.py`, `semantic_search_service.py`, `qdrant_vector_store.py`, `ai/services/rag_service.py` | obowiązkowy client context, scoped retrieval, actor/client persisted and revalidated | A/B RAG/vector/job/result tests |
| Admin-only global APIs | `api/admin_*.py`, `api/client_candidates/router.py`, `api/imports/router.py` | deny External; nie rozszerzać User admin rights | authorization regressions |
| Flutter routing/menu/auth | `frontend/lib/core/router/app_router.dart`, `core/widgets/app_shell.dart`, `features/auth/**`, `domain/current_user.dart` | parse External, redirect/menu, shared-clients feature | router/widget/auth-role tests |
| Flutter klientowe features | `features/clients`, `projects`, `inspections`, `documents`, `mail`, `tasks`, `global_search`, `dashboard`, `ai` | scoped params/views and 404-safe UX | widget/API adapter and cross-target smoke |
| Obecne testy | `backend/test/test_admin_user_lifecycle_e2e.py`, `test_client_list_contract_e2e.py`, `test_client_email_*`, `test_chunk10*`, `test_chunk11_global_search.py`, `test_chunk12_client_ai_*`, `test_followup_chunk13_api_auth.py`, `frontend/test/**` | dodać focused R25 suite, zachować bezpośrednie regresje | bez blanketowego R23 |

Inventory jest checklistą pokrycia, nie zgodą na modyfikację tych plików.

## 12. Testy bezpieczeństwa i E2E

Fixture: Administrator, User, External bez grantów, External z A, klient A i B oraz reprezentatywne zasoby każdego typu.

Scenariusz: admin tworzy aktywnego External; login; przed grantem zero klientowych danych; Admin/User nadaje A; pełny dozwolony workflow A; B jest niewidoczny; revoke A odbiera dostęp od następnego requestu.

Negatywy B obejmują listę, client/project/inspection/document/attachment/email/thread/task/activity ID, wpisany URL, search, autocomplete, recent, counts, notification, export, AI retrieval i raw download. Wynik: brak danych i potwierdzenia istnienia, 404 gdzie potrzebne.

Pozytywy A obejmują read/create/edit, upload/download, mail reply/send, task, inspection, timeline/note, AI context oraz automatyczny scope nowych zasobów. Testy zmian: A->B znika, B->A pojawia się, revoke/deactivation/role changes natychmiastowe, historia zachowana.

Regresje: Administrator/User nadal widzą obecny zakres, admin-only pozostaje admin-only, login/JWT i istniejące workflow nie ulegają regresji.

## 13. Wydajność i wymagane bramki

- query-level filtering i indeksy; scoped pagination/count/sort/filter;
- brak N+1 dla shared clients;
- wspólna policy zamiast ad-hoc warunków;
- atomic grant/revoke z audytem aktora/czasu;
- fail closed przy błędzie owner resolution;
- test migracji, backend focused/direct regressions, Flutter source/widget, integration oraz pełny A/B no-leak E2E;
- Web build/smoke, Windows build/smoke, Android build/smoke, jeśli Android jest wspieranym targetem wydania;
- bez blanketowego R23.

## 14. Jeden przyszły chunk wykonawczy

1. Alembic + External seed/role handling.
2. Central policy i resolver owner client.
3. Query/object/write/download coverage wszystkich obszarów.
4. Grant/revoke/audit API.
5. Flutter route, menu, shared-clients i scoped views.
6. Security, migration, backend, Flutter i A/B E2E tests.
7. Tylko dotknięte buildy.
8. Controlled deployment po osobnej bieżącej zgodzie.
9. Post-deploy no-leak workflow.
10. `R25_READY_FOR_OWNER_REVIEW`, następnie wyłącznie właścicielski `R25_ACCEPTED`.

Nie zatrzymywać przyszłego wykonania osobno po migracji, backendzie, UI, testach ani package-ready. Operacyjne UAC/restart/deployment wymagają nowej zgody.

## 15. Rollback przyszłego deploymentu

Zachować exact preimages kodu/config/buildów i addytywną migrację. Rollback przywraca kod/build/config oraz może wyłączyć External, ale nie usuwa danych grantów ani tabeli. Po rollbacku Admin/User zachowują wcześniejsze zachowanie; External fail-closed. Restore danych produkcyjnych wymaga odrębnej zgody.

## 16. Poza zakresem

Automatyczny assignment, territory/team/group, publiczne linki, delegowanie przez External, field-level permissions, granty per zasób, redesign RBAC/multi-tenant, Gmail/Sheets/D-22, dalsze R04, niezwiązane R05–R24, cleanup i R23 audit.

## 17. Definition of Done

Rola External istnieje; ręczne grant/revoke i historia działają; backend centralnie wymusza cały client scope; UI ma „Udostępnieni klienci”; direct IDs/files/search/count/AI nie przeciekają; revoke jest natychmiastowy; Administrator/User zachowują zachowanie; pełny A/B security E2E przechodzi; wynik jest wdrożony i gotowy do odbioru właściciela.

Powiązane istniejące wymagania: `M-006`, `M-007`, `M-015`, `M-016`, `M-017`, `M-038`, `M-039`, `M-043`, `M-047`, `M-064`, `M-069`, `M-071`, `M-072`, `M-073`, `F-005`, `F-009`, `F-013`, `F-020`, `F-022`, `F-035`. Nowe wymagania bezpieczeństwa wynikają bezpośrednio z decyzji właściciela D-24; nie utworzono fikcyjnych identyfikatorów M/F.

## 18. Wynik okna Android / live E2E / Windows trust — 2026-09-27

Preflight zachował anchor source/runtime: HEAD `fa2d2919f59c7cf600dcafe145a33c766e8ba37d`, source produktu `16e8fcb5d311a20b703a74b1a9c966292b3499a8`, backend `021c33255883c37933dd68c8efc302f0c22348a5804199b39caf76f7e00d46f5`, schema `r25_external_scope_20260927`, startup manifest `7014D583910AAFBCCFF4CF3673ACC2DC647CE5AEF97194D42CC3B60FF69D429D`, exact backend `36/36`, Web `A6D708B2BF72664676F5232CD1208B3FB656FB275A65BCB927FEBC9AFDDCE80A`, Supervisor `0/0` i `pending_mutation=false`.

Android Branch B został rozliczony na jedynym emulatorze `emulator-5554` (`Pixel_8`), bez fizycznych urządzeń. Installed preimage `1.0.0+1` miał debug signer `7A4397BF69CF0B21A6D028510C13FE84FAD7D3892B62F1C524B78D0B05CBE0F4`; exact APK R25 `F24A250B5A32FDBF9DD9EAA15E62AAE378C06C766795E2D7179B856510B83E47` miał historycznie kanoniczny signer `5E223DA2DA7C893D089D7333E99AAEEE8D98C9CDF72BE80609020967368FE018` i v2. Autoryzowany uninstall dotyczył wyłącznie `pl.ailab.app`; jedna instalacja exact APK zakończyła się sukcesem. Readback potwierdził `1.0.2+29`, ten sam kanoniczny signer, v2, zgodność installed/source APK i normalny ekran logowania. Pulled APK i lokalne sekrety operacyjne usunięto.

Live authenticated run `R25_E2E_20260927T131429Z_2bc8101b` użył wyłącznie operation-owned syntetycznych fixture i rzeczywistych login/JWT. PASS przed pierwszym defektem: auth/role, grant management, clients, projects, inspections, documents/files, bounded tasks i timeline, w tym pozytyw A oraz bezpieczne negatywy B/direct ID. Pierwszy materialny defekt wystąpił dla roli External w `GET /api/v1/search?q=<synthetic-prefix>`: oczekiwano `200` z A i bez B, otrzymano `500`. Minimalny traceback wskazuje `app/services/global_search_service.py::_documents` i SQLAlchemy `InvalidRequestError` dotyczący automatycznej korelacji zapytania bez FROM. Nie zaobserwowano ujawnienia B; jest to funkcjonalny K1 uniemożliwiający ukończenie search i kolejnych domen macierzy. Zgodnie z granicą operacji nie wykonano source patchu, restartu backendu ani dalszego E2E. Cleanup potwierdził aktywne testowe granty `0`, aktywnych testowych użytkowników `0`, widoczne testowe klienty `0`, pozostałe pliki `0` i brak pending mutation.

Windows otrzymał klasyfikację `B. NO_TRUSTED_CODESIGNING_IDENTITY_AVAILABLE`. Exact installer `EA69C1FF1DA1CB2E608FF49CABEB6ABBAEA763AB679B73B2FDBB55DF5EFA3CE9` jest `NotSigned`; Code Integrity 3033/3077 wiąże jego exact path/hash z aktywną polityką `VerifiedAndReputableDesktop`, GUID `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`, hash `2668895A5B233A80432D00D67251D7B7F52686A3FB13780F4B242C5A1F937A01`, signing level requested `2`, validated `1` i status `0xc0e90002`, przed utworzeniem procesu instalatora. `CurrentUser\My` i `LocalMachine\My` nie zawierają dostępnej tożsamości spełniającej jednocześnie Code Signing EKU, RSA, ważność/chain i dostępny private key. Wszystkie osiem dystrybucyjnych PE w payloadzie (`frontend.exe`, `flutter_windows.dll` oraz sześć plug-in DLL) są niepodpisane; tylko `permission_handler_windows_plugin.dll` i `geolocator_windows_plugin.dll` są objęte istniejącym native hash pinningiem. Pipeline nie ma post-build signing step ani NSIS installer/uninstaller signing hooks. Przyszły, osobno zatwierdzony plan musi podpisać dystrybucyjne EXE/DLL, wygenerowany uninstaller i finalny installer z zaufanej tożsamości, ponownie obliczyć hashe signed bytes oraz oddzielić deterministyczny unsigned payload manifest od timestampowanego, niedeterministycznego signed distribution manifestu; dopiero potem dozwolone są install i installed-root acceptance.

Bieżący historyczny status tego okna został zastąpiony wynikiem sekcji 19. External search i Android są zamknięte technicznie; jedynym pozostałym K1 jest zaufany signed Windows build/install/acceptance. R04 pozostaje wstrzymane; D-22 pozostaje `NOT_RUN`.

## 19. Wynik poprawki External search i pełnego post-deploy E2E — 2026-09-27

Fail-before na izolowanym PostgreSQL potwierdził, że `_documents` łączył zewnętrznie `Project` i `Inspection`, a `_document_allowed()` ponownie używał tych samych mapped classes w `EXISTS`; SQLAlchemy automatycznie skorelował wszystkie lokalne FROM i podniósł `InvalidRequestError`. Minimalna poprawka używa osobnych `aliased(Project)` i `aliased(Inspection)` oraz jawnej korelacji wyłącznie do `Document`. Focused suite `test_r25_external_search_scope.py` przeszła `5/5`; bezpośrednie regresje external scope, global search i 60-klientowego list contract również przeszły. Source opublikowano jako `34834c96443da619d051b66ea4ef37f055a6549b`.

Pierwsza próba deploymentu prawidłowo wdrożyła source i uruchomiła zdrowy backend, ale lokalny harness błędnie odczytał `release_id` oraz `runtime_configuration` o jeden poziom za głęboko i zgłosił fałszywy timeout. Operation-owned rollback przywrócił source/override, a ograniczony readback i reconciliation związały manifest z rzeczywistym ID odtworzonego backendu; `pending_mutation=false`. Po poprawieniu wyłącznie projekcji harnessu powtórzono dotknięty deployment bez drugiego UAC. Wynik końcowy: backend `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`, ten sam image digest `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`, release `NEXT-STABIL-R25-searchfix-34834c96443da619`, source `34834c96443da619d051b66ea4ef37f055a6549b`, schema `r25_external_scope_20260927`, source-file SHA-256 `CF1AB70B44D283A34C5138D7AC28EC9BBD83B8D1A88026EC4EF7FC40199D90B3`, override `87C940B3B7C767C4DCF67EAA19D62E7978A0164DE96AC8E9905B763807E9B8B3` i startup manifest `F9C33CB404589309ED3CDE1D8956C96882DBB194654DA21DB0139B350E6BCCCA`. Manifest jest `APPROVED_FOR_START`, set/approval IDs są zgodne, pięć pozostałych pinned container IDs nie zmieniło się, `/health=200`, `/control*=404`, Supervisor `0/0`.

Świeży run `R25_E2E_20260927T150637Z_7b275f03` przeszedł rzeczywiste HTTP/JWT dla: auth i roli; brak grantów; idempotentny grant/regrant/revoke i historię; clients/contacts/address/phone; projects; inspections; dokumenty z wersją, preview, thumbnail, raw i download; mail/thread/attachment oraz walidację send bez transportu; tasks/calendar; timeline/notes; lexical i semantic search; scoped aggregates; calendar-alert surface; scoped download; klientowe AI direct retrieval bez zewnętrznego modelu; deactivation; zmiany External↔User; deleted-client deny; Admin/User regressions; nieenumerowalne B/mixed/unknown direct IDs oraz brak cross-client leak. Fixture używał wyłącznie syntetycznych danych i nie uruchamiał Gmail, n8n, real mail ani zewnętrznego AI.

Web smoke potwierdził login External, dokładnie Client A bez B, szczegóły A, manager grant/revoke UI oraz pustą listę od następnego requestu po revoke. Na jedynym emulatorze `emulator-5554`, bez urządzenia fizycznego, istniejąca aplikacja `1.0.2+29` potwierdziła analogicznie listę A, szczegóły A, natychmiastowy revoke, pustą listę i close/reopen bez crasha; nie wykonywano reinstall, uninstall ani clear-data. Cleanup zwrócił zera dla aktywnych grantów, użytkowników, widocznych klientów, dokumentów, work items, mail sources, plików i punktów Qdrant oraz `pending_mutation=false`; syntetyczne poświadczenia, harness i screenshots usunięto.

Windows pozostał bez mutacji: dokładnie jeden proces z `%LOCALAPPDATA%\Programs\NEXT Stabil\frontend.exe`, SHA-256 `5BD959A30CE176D5E484D41EF1B5BF51D0D9FD38F5F99F7219AA07446BDB0865`. Nie wykonano retry instalatora ani obejścia ochrony. Jedynym otwartym materialnym K1 jest `WINDOWS_TRUSTED_SIGNING_REQUIRED`: osobno zatwierdzony zaufany RSA Code Signing build, podpisanie dystrybucyjnych PE i NSIS, zgodna instalacja oraz installed-root acceptance.

Status końcowy tego okna: `R25_IN_PROGRESS / FULL_POST_DEPLOY_E2E_PASS / ANDROID_PASS / WINDOWS_TRUSTED_SIGNING_REQUIRED / NOT_ACCEPTED`. Nie nadano `R25_READY_FOR_OWNER_REVIEW` ani `R25_ACCEPTED`; R04 pozostaje wstrzymane, D-22 pozostaje `NOT_RUN`.

## 20. Windows owner-managed local installation — 2026-09-27

Historyczny wynik `SAC_ON_INSTALLER_TRUSTED` i raport WDAC pozostają prawidłowe dla podpisanego kanału. Właściciel osobno zdecydował, że ta jedna lokalna maszyna NEXT Stabil używa trybu `SAC_OFF_OWNER_MANAGED_HOST`; nie jest to deklaracja zaufania do publicznej dystrybucji na obce komputery. Smart App Control przełączono przez oficjalny interfejs Windows Security z `On` na `Off`, bez edycji rejestru, usuwania polityk, `Unblock-File` ani restartu. Bitdefender pozostał aktywny (`productState=266240`), wszystkie trzy profile firewalla pozostały aktywne, a UAC `EnableLUA=1`.

Source kontraktu acceptance opublikowano jako `a92a4238d118f7ea4a7698bea7e84ae2cb1ac1af`. Historyczny tryb nadal wymaga Managed Installer evidence; nowy tryb wymaga SAC Off, aktywnych Bitdefendera/firewalla/UAC, kanonicznego registered rootu, exact manifestu i hashy wszystkich plików, jawnie dozwolonych generated files, poprawnego uninstall/shortcuts, braku reparse/path escape i braku szeroko zapisywalnych katalogów wykonywalnych. Focused PowerShell 5.1 testy obu trybów przeszły, historyczny preimage przeszedł historyczny gate, a fail-before starego rootu w nowym trybie prawidłowo wykrył nieoczekiwany plik.

Exact installer `EA69C1FF1DA1CB2E608FF49CABEB6ABBAEA763AB679B73B2FDBB55DF5EFA3CE9` (`NotSigned`, `1.0.2.29`) zakończył się exit `0`. Stary, potrójnie związany z preimage plik `dartjni.dll` nie należał do exact R25 manifestu i został usunięty przy zachowanej operation-owned kopii rollback. Finalny gate potwierdził 20 payload files plus jawnie dozwolony `Uninstall.exe`, installed `frontend.exe` `DF4683C67423276AA18BFD107F5238F3EFD5E27FD7FDA86EED23A0B7F9CBED51`, uninstall metadata, oba skróty, ACL/reparse/path boundaries i brak staging/recovery/Temp dependency. Jeden responsywny proces ładował natywne moduły wyłącznie z kanonicznego rootu; po początku okna nie było nowych nieoczekiwanych Code Integrity 3033/3077.

Windows UI smoke użył wyłącznie efemerycznych danych syntetycznych. External bez grantów zobaczył pusty stan; po grancie User widział wyłącznie A, otworzył szczegóły A i dozwolone ekrany zadań, realizacji, wizji, dokumentów i maili; B pozostał nieenumerowalny. Revoke odebrał A od następnego requestu, a close/reopen pokazał pustą listę i dokładnie jeden proces bez crasha. Po wylogowaniu usunięto użytkowników, klientów A/B, grant i poświadczenia; wszystkie liczniki residue są `0`, `pending_mutation=false`.

Wynik końcowy: `R25_READY_FOR_OWNER_REVIEW / NOT_ACCEPTED`. Backend, schema, startup manifest, Web, Android i wcześniejszy pełny A/B E2E pozostają bez zmian i PASS. Technicznych K0/K1 brak. R04 pozostaje wstrzymane; D-22 pozostaje `NOT_RUN`.
