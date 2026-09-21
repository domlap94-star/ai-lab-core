# R04 / D-21 / P4-B — odbiór SHA-256 i preflight VerifyOnly

UTC: `2026-09-21T21:16:33.7075929Z`
Zakres: `SOURCE / LOCAL FILE READ / dokładnie jeden VerifyOnly warunkowany integralnością wejść`

## Odbiór source

Właściciel przyjął dokładny diff `Get-P4BSha256` oraz jego bezpośrednie testy
jako `P4B_PS51_SELF_CONTAINED_FILE_SHA256_SOURCE_AND_OFFLINE_ACCEPTED /
NOT_DEPLOYED`:

- recepta `65080` B / `CA6A5DCC4CD472332D32178FD3AEB659A9828FE9A746B02E3FCD188893387157`;
- package index `10006` B / `C2F6A77CC09869E26473BA85B1E21F4A1784E359D423A79A08C6E3086D12B8AA`;
- review index `19946` B / `A4D2A5DB4BAD4A9DAF93ED76DC36D5902AF799DB24986E9D3FF5A6DC6B1732DE`.

D-23 pozostaje `REVIEW_2_OF_2_COMPLETED`; wcześniejsze odbiory Host identity,
Stage-A normalization, Host22 i NUP-01/02/03 pozostają zachowane.

## Preflight jednej autoryzowanej próby

Przed pierwszą granicą systemową sprawdzono dokładny LOCAL_ONLY root
`C:\Users\domai\AppData\Local\Temp\P4B-SHA-01` samowystarczalnym .NET
SHA-256. Recepta, package index i review index mają przypięte rozmiary i
hashe. Wszystkie `8/8` niepustych payload bindings wskazane przez indeks mają
zgodne path/size/SHA-256. Operation ID pozostaje
`R04-D21-P4B-HOST22-NUP-20260920T200422Z`.

Wymagany czwarty artefakt
`R04-D21-P4B-PS51-SHA256-REVIEW-20260921T192345Z.zip`, oczekiwany jako
`223585` B / `0DE0E072A6030F00159CAFD32CEE73636AC2033B7AFE73F42BD4838BB73414F8`,
nie istnieje ani w przypiętym katalogu, ani pod dokładną nazwą w sprawdzonych
rootach TEMP i `C:\ai-lab-core-staging\recovery`. Zachowany roundtrip nie został
przepakowany ani użyty jako zamiennik exact ZIP.

`vfy1` oraz `vfy1\out` nie istniały. Nie utworzono sentinela, stdout/stderr,
metadata ani procesu recepty, ponieważ integralność czterech wymaganych wejść
nie przeszła. Wykonania VerifyOnly: `0`; Task Scheduler reads/writes/starts,
Docker/WSL/CIM/TCP/HTTP/SQL, UAC/RunAs, journal, mutation, warm i rollback:
`0`.

Status: `P4B_VERIFYONLY_NOT_RUN /
BLOCKED_LOCAL_PREREQUISITE_REVIEW_ZIP_MISSING / NO_TASK_READS / NO_MUTATION`.
Brak wykonania nie jest PASS ani zgodą na Stage B. Nie wykonano retry i nie
rekonstruowano archiwum.

## Następny krok i STOP

Jedna decyzja właściciela powinna wskazać przywrócenie dokładnych, wcześniej
sprawdzonych bajtów ZIP albo inny jawny sposób ponownego związania transportu;
dopiero po zgodnym preflightcie może zostać rozważone jedno nowe VerifyOnly.
Nie ma automatycznej kontynuacji tej autoryzacji na zmienionym punkcie wejścia.

Installed run01, Host disabled/no-trigger, warm `0/2`, Private `0`, Supervisor
`INTENTIONALLY_STOPPED`, HTTP i fresh six-container preflight pozostają bez
świeżej obserwacji i bez zmian. Stage B jest `BLOCKED / NOT_AUTHORIZED`.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną przeczytaj §0, `ANTI_EXCESSIVE_WORK`, aktywną kartę R04 i ten
checkpoint na pełnym opublikowanym SHA. K0: `BRAK`. K1: exact transport ZIP
wymagany przez bieżące przypięcie jest nieobecny; dowód to lokalny exact-name
lookup przy zgodnych pozostałych `3/4` top-level artefaktach i `8/8` bindingach.
Nie naprawiać przez rekonstrukcję na zapas. D-23 pozostaje `2/2`; bez K2/K3,
bez Task reads i bez operacji hosta.
