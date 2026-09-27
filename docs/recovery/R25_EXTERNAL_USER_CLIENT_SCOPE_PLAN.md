# R25 — External user / client-scoped access

Status: `IN_PROGRESS / CORE_BACKEND_AND_WEB_DEPLOYED / WINDOWS_APPLICATION_CONTROL_BLOCKED / ANDROID_SIGNATURE_OWNER_DECISION_REQUIRED / NOT_ACCEPTED`.

Ten dokument pozostaje kanonicznym kontraktem R25. Właściciel później zatwierdził implementację i kontrolowany deployment. Source `16e8fcb5d311a20b703a74b1a9c966292b3499a8` jest opublikowany; addytywna migracja `r25_external_scope_20260927`, exact 36 plików backendu, backend-only replacement, pochodny startup manifest i Web zostały wdrożone. R25 nie jest jeszcze gotowy do odbioru: Application Control zablokował exact instalator Windows przed startem także przez jedyny dopuszczony kanał UAC, a standardowy Android update zakończył się `INSTALL_FAILED_UPDATE_INCOMPATIBLE`; zgodnie z bieżącą granicą nie wykonano uninstallu. Szczegóły zawiera checkpoint `20260927T124457Z-R25-FORWARD-RECOVERY-CONSOLIDATED-K1.md`. Wyłącznie właściciel może nadać `R25_ACCEPTED`.

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
