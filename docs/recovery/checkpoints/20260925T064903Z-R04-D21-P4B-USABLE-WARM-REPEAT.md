# R04 / D-21 / P4-B — USABLE-WARM repeat, logon i CRM/Web

## Wynik

- Status wykonawczy przed decyzją: `USABLE_WARM_READY_FOR_OWNER_REVIEW`.
- Odbiór właściciela: `USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` na
  opublikowanym `e35ec2c9f74d598ae0ee6d48573e8c7b11e2caaa`.
- Warm runs: `2/2` na dwóch różnych recorder attempts.
- Pierwszy zaakceptowany attempt: `20260924T200607127Z-09f89fd4`, Private
  `START_ONCE=1`.
- Drugi attempt: `20260925T063227046Z-3e1e1246`, child exit `0`, nowe starty
  usług/kontenerów `0`, duplikaty `0`.
- Host: `Ready`, enabled, idle, jeden trigger logon, LastResult `0`.
- CRM/Web: właściciel potwierdził ręczne read-only otwarcie listy klientów i
  szczegółów jednego klienta.
- Supervisor: `INTENTIONALLY_STOPPED`; sześć kontenerów i cztery pliki produktu
  zachowane.

Nie jest to `R04_ACCEPTED`, cold-start/logoff/reboot PASS ani odbiór backupów,
relokacji danych, HKCU Run, Docker/WSL pool lub swap.

Historyczne parent/logon `PARTIAL/PENDING_UNKNOWN` oraz późniejsze dowody ich
rozliczenia pozostają bez zmian; starych journalów nie przepisano.

## Dokładne wejścia LOCAL_ONLY

| Artefakt | Rozmiar | SHA-256 |
|---|---:|---|
| `review/invoke-p4b-usable-warm-continuation.repeat.ps1` | 43652 B | `2498FC31736D754FFD5C8F05612DC8C80EE9D0B68E38D5BB4344298E55899953` |
| `continuation-index.repeat.json` | 8525 B | `494536D6787D7E70890475FF90A7310638272C6BA3E39FC238E83FF8A98705EE` |
| `tests/test-usable-warm-continuation.repeat.ps1` | 44256 B | `E5DF942C1C52FF6A9020CAD3FF34B186C0B1C6805C8422ABFBACFDFFAC45251C` |
| offline result | 864 B | `E1EB86C73862ECD4FD40660ED18F2FCA91D4C5577BDA6171E6EE59FA79C28C4D` |

Offline PS5.1: `14` scenariuszy / `72` asercje, produkcyjne granice `0`.
Pochodna nie zmienia czterech zainstalowanych plików ani manifestu.

## Bieżący preflight i jedno wykonanie

Read-only preflight potwierdził cztery pliki exact, Host on-demand exact/idle,
sześć kontenerów running, PostgreSQL healthy, Public i Private present,
Supervisor absent oraz HTTP `200/200/200/404`. Docker/WSL pool i swap pozostały
`UNKNOWN_ACCEPTED_FOR_THIS_WINDOW`, nie PASS.

Jeden UAC uruchomił PID `33600` w oknie
`R04-D21-P4B-USABLE-WARM-REPEAT-20260924T230413Z`. Parent exit `22` i jego
`result.json` pozostają historycznie `PARTIAL_PENDING_OPERATION_UNKNOWN`; nie
zostały przepisane. Journal rozlicza własny `START_TASK`, a późniejszy recorder
tego samego startu daje:

| Dowód | Rozmiar | SHA-256 |
|---|---:|---|
| marker | 364 B | `2A4FD8AC721568E252C335F5B832C342A4E87AD788323D38E0EAD68B846D45B1` |
| result | 5961 B | `D19E17A2EE74C4DAC72CA366597BAC49CAFDBB75BB8CBAF52F5D9659CB58669E` |
| stdout | 3054 B | `525FEF67AD239AAFE5629A5803E2FF75CD10DE33C876780D071DBAD9AF565913` |
| stderr | 0 B | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |

Recorder potwierdza `BASE_READY_LIMITED_CAPTURED`, rozliczone dziecko PID
`59948`, exit `0`, zachowanie sześciu kontenerów/Public/Private oraz brak
`START_ONCE` i `START_EXISTING`. Drugi run nie utworzył duplikatu.

## Logon i UI

Po rozliczeniu drugiego runu wykonano jedną rejestrację wariantu logon. Journal
`B71520E3D59D97786E4E5F91938E0BF00695173EDAA9A25977A184645AE35964`
zachowuje `PENDING_UNKNOWN / TASK_POSTCHECK_NOT_CONFIRMED`. Nie wykonano retry.
Późniejszy exact readback potwierdził jeden trigger, Host `Ready`/idle, poprawną
akcję, CWD, InteractiveToken, LeastPrivilege, PT15M i IgnoreNew. Eksportowana
nazwa `DOMAI\domai` została rozstrzygnięta do przypiętego SID. Formalnego wyniku
nie przepisano na sukces; logoff/reboot nie wykonano.

Zachowany skrót uruchomił klienta. Automatyczna próba ustawienia fokusu została
zablokowana przez ochronę i nie była ponawiana. Właściciel potwierdził w rozmowie
ręczne, read-only otwarcie CRM/Web, listy klientów i szczegółów jednego klienta.
Nie wykonano edycji danych, importu, analizy ani eksportu.

## Skutki i następny krok

- UAC `1`, drugi Host start `1`, zapis logon `1`.
- Nowe starty usług/kontenerów w drugim runie `0`.
- Retry `0`, SAFE_INACTIVE `0`, drugi UAC `0`.
- Cztery pliki produktu, sześć kontenerów, dependency tasks, helper, dane,
  junction i dziewięć flag bez zmian.
- Następny istniejący zakres: `R04-ONE-ENTRY-COLD`, po odrębnej zgodzie. Ta
  decyzja nie zezwala na jego wykonanie i nie otwiera ponownie USABLE-WARM.
