# R04 / D-21 / P4-A — four-service identity reconciliation

Checkpoint ID: `R04-20260918T012154Z-D21-P4A-FOUR-SERVICE-IDENTITY`

## Zakres i wynik

- Parent: `54a0fffa341ff875d660667f09ac6c3117ef4fe9`.
- Branch: `recovery/next-stabil-repair-completion`.
- Pakiet: `R04-D21-P4A-STARTUP-ACTIVATION-20260917T210051Z`.
- Source launchera pozostaje bez zmian:
  `8756314f51a76091a483cfc9b677a05c7f67f315`.
- Okno bieżących odczytów:
  `2026-09-18T01:15:44.2376952Z`–`2026-09-18T01:18:24.0096364Z`.
- Wynik: `P4A FOUR_SERVICE_IDENTITY_RECONCILED /
  CURRENT_READ_ONLY_EVIDENCE / INACTIVE_STARTUP_PACKAGE_READY_FOR_REVIEW /
  NOT_INSTALLED`.
- Globalny manifest pozostaje `NOT_APPROVED_FOR_START`; P4-B jest
  `NOT_AUTHORIZED / NOT_INSTALLED / NOT_RUN`.

## Proweniencja i klasyfikacja

Commit `daf0931cff28944e5df528f63cd95b4d99dd041a` wprowadził cztery wtórne
pełne container/image ID. Zachowany pierwotny
`E:\ai-lab-backup\20260917T082022Z\artifacts\runtime-inventory.json`, captured
`2026-09-17T08:21:56.3539611Z`, 11 349 B, SHA-256
`D3DE5C85E73F9B6771A5480D9A7E90A923CE0079BB2850702D5081E884D0EBC0`,
zawiera inne pełne wartości. Draft zachował tylko zgodne skróty/prefiksy.

Jedna lista `ai-lab-core` znalazła dokładnie jednego kandydata dla każdej roli.
Bieżące pełne ID, image ID i RepoDigests czterech kontenerów są identyczne z
pierwotnym runtime inventory. Dla wszystkich czterech wynik to
`DRAFT_TRANSCRIPTION_ERROR_PROVEN / HIGH`; nie wykazano recreate, zmiany
obrazu, sprawcy ani utraty danych.

| Usługa | Bieżący pełny container ID | Bieżący image ID | Stan |
| --- | --- | --- | --- |
| qdrant | `daa3b0b86b748aa3a52052dac08bfde499cf19ad61600a1325e09061a5451fae` | `sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286` | running, restart 0 |
| n8n | `a44e719ecfecf72a199b4f8b3ec9d7503548d2098601e767d5e9e6503d37081c` | `sha256:3c07c723326dd72e46a6969181c66a75260b7a204b9b77ba1ece6d594489c684` | running, restart 0 |
| open-webui | `9575ca068b8cc17d0b2ac72e0062867c5c74650c12619bf6ecc6b48d1ec54c39` | `sha256:a26effeb220e132482bf7e0560b3404843e7bc40d23051144e062960df8df6b0` | running, restart 0 |
| ollama | `7ff1c45ea12cb9a26df1540cdeb5993c30fe12ac1d9c199ea7ce776847aac083` | `sha256:ec24bcaa2a810eb74171ce7c517813ef4821ed678988845e8d76cf62467036d4` | running, restart 0 |

Mounty, loopback ports, network `ai-lab-network`, project/service labels i
policy `unless-stopped` są zgodne. Qdrant physical backing poza nazwanym volume
pozostaje `UNKNOWN`; wynik nie oznacza `ALL_DATA_ON_D_PASS`.

## Kolektor i dowody LOCAL_ONLY

Root:

`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\p4-startup-activation-20260917T210051Z\identity-reconciliation-20260918T011139Z`

- test początkowy: `16/16`, Windows PowerShell `5.1.26100.8894`, exit 0;
- po potwierdzonym błędzie opcjonalnego `Mount.Name`: `17/17`, exit 0;
- lista + Qdrant safe projection: 21 717 B, SHA-256
  `7FB247C58E9B1675D35572356C485219C14332771B48DF636F6CDFF75CA0B184`;
- skorygowana projekcja n8n/Open WebUI/Ollama: 16 859 B, SHA-256
  `9F4980132ACCF73F4790742849862963E5629386C12E4F225676899DB7EE3B66`;
- finalna walidacja draftu przez rzeczywiste czyste funkcje: `61` asercji,
  exit 0; stdout 186 B, SHA-256
  `1F1044762F985D37F241983ACAE22A97AE9E09E7D9D47F867D28AB39FC5BEB74`;
- cztery końcowe CSV odczytane przez `@oai/artifact-tool`: PASS, exit 0;
  stdout 785 B, SHA-256
  `FC83DDF37117FBD08DB319B058A0A9B8F9F7CDF2E54CE41B96862B6E7721312F`;
- pierwszy nieudany formatter został zachowany; nie wykonano drugiej listy
  projektu ani ponownego odczytu Qdrant;
- nowy indeks 18 plików: 5 545 B, SHA-256
  `3FCF1938111C9746FB9F4B5D57F1F98C5085099503B1385B862B0F68776303A9`.

Draft ma 15 469 B, SHA-256
`E17DDCA39D4D3BC7BBAD6F0688738DAA1B7C28B5810BB611C83A940234A28403`,
wiąże 6/6 exact identity, ale nadal ma `approval.status=NOT_APPROVED`.
Historyczne indeksy i partial readback pozostają dowodami historycznymi.

## Skutki i STOP

Wykonano wyłącznie odczyty Engine i zapis dokumentacji/stagingu. Nie wykonano
startu, stopu, restartu, create/recreate, `compose up`, pull/build/tag, exec,
instalacji, zmian tasków/triggerów/skrótów, danych, mountów, sieci, wolumenów,
junctionu, SQL, backupu/restore ani cleanupu. Supervisor pozostaje
`INTENTIONALLY_STOPPED`.

Następny krok: review skorygowanego exact pakietu i osobna decyzja właściciela
o P4-B, z jawnym rozstrzygnięciem Qdrant/VHD oraz zakresu instalacji i
aktywacji. STOP przed P4-B/P5/R06.
