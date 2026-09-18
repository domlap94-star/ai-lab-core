# R04 / D-21 / P4-A — current identity readback partial

Checkpoint ID: `R04-20260918T000227Z-D21-P4A-IDENTITY-READBACK-PARTIAL`

## Zakres i wynik

- Parent/evidence preimage: `93a7126ed1f93f298725a9f9e929712d23e4c03c`.
- Branch: `recovery/next-stabil-repair-completion`.
- Pakiet: `R04-D21-P4A-STARTUP-ACTIVATION-20260917T210051Z`.
- Okno odczytu: `2026-09-18T00:02:24.5802192Z`–
  `2026-09-18T00:02:27.4592777Z`.
- Wynik: `CURRENT_IDENTITY_READBACK_2_OF_6_PARTIAL / BLOCKING_P4B`.
- Globalny manifest: `NOT_APPROVED_FOR_START`; P4-B pozostaje
  `NOT_AUTHORIZED / NOT_INSTALLED / NOT_RUN`.

Przed kontaktem z Engine kolektor przeszedł parser oraz 20/20 syntetycznych
asercji w Windows PowerShell `5.1.26100.8894`. Sprawdzono puste, pojedyncze i
wielokrotne `RepoDigests`, jawne `null`, brak pola, pusty stdout, niepoprawny
JSON, niezerowy exit, timeout, niezgodny pełny ID, brak opcjonalnych mount/health
oraz trwałość sześciu rekordów po późniejszym błędzie formattera.

Pierwsze uruchomienie wrappera zakończyło się przed pierwszym poleceniem Docker,
ponieważ historyczna ścieżka CLI nie istniała. Po odczytaniu faktycznej ścieżki
już zainstalowanego CLI wykonano jedną kampanię. Każdy obiekt miał własny limit
20 s; wykonywano wyłącznie `container inspect` lub `image inspect` przez
`desktop-linux`, z formatem ograniczającym stdout do dozwolonej projekcji.

## Bieżące ustalenia

- `backend`: pełny container ID, image ID, projekt `ai-lab-core`, service
  `backend` i runtime name `/ai-lab-backend` są zgodne; obraz zwrócił dwa
  RepoDigests.
- `postgres`: pełny container ID, image ID, projekt `ai-lab-core`, service
  `postgres` i runtime name `/postgres` są zgodne; obraz zwrócił jeden
  RepoDigest.
- `qdrant`, `n8n`, `open-webui`, `ollama`: każde przypięte pełne ID kontenera
  zwróciło `No such container`, a każde przypięte image ID `No such image`.

Nie wykonano listowania wszystkich kontenerów/obrazów, automatycznego
wyszukiwania po nazwie, zmiany draftu, startu, stopu, restartu, create,
recreate, pull, build, tag ani `docker exec`. Nie odczytano pełnego inspect,
Env, mounts, health, komend ani danych firmy. Draft i historyczny indeks 18
plików są niezmienione, ponieważ kompletność tożsamości wynosi `2/6`.

## Dowody LOCAL_ONLY

Chroniony podkatalog:

`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\p4-startup-activation-20260917T210051Z\readback-20260917T235659Z`

- safe projection: 11 181 B, SHA-256
  `D82FC6FD1E3141EAF9EFB4BEDFC1051E5DC13F50BCA474D0D9B0253443F1116C`;
- final synthetic stdout: 65 B, SHA-256
  `8C77CC35DD6D718CE0293BFFAF157FBBFA264D81187D40EC28202102D8110858`;
- final synthetic stderr: 0 B, SHA-256
  `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.

## Następny krok

Potrzebna jest osobna decyzja właściciela o ograniczonym rozliczeniu aktualnych
tożsamości czterech nieobecnych przypiętych zasobów. Bez niej nie wolno szukać
zamienników po nazwie, adoptować nowych ID, zmieniać składu draftu ani uruchamiać
zasobów. Supervisor pozostaje `INTENTIONALLY_STOPPED`; P4-B/P5/R06 pozostają
poza zakresem.
