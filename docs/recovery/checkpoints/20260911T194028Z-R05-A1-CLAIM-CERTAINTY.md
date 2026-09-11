# R05-20260911T194028Z-A1-CLAIM-CERTAINTY

- UTC: `2026-09-11T19:40:28Z`.
- Pakiet/podetap: `R05 / A1 — trwałe rozróżnienie lokalnej odmowy i rozpoczętego handoffu`.
- Branch/worktree: `recovery/next-stabil-repair-completion` / `C:\ai-lab-core-recovery`.
- Parent: `0f73eb8d5d9b88df1df33abbbdb77c7c30d876a2`.
- Poprzedni source R05-A1: `3a36d5b3866e277b9186028b1926debfe92209e6`.
- Source po poprawce: `d31e105427acd40733e91c4d4b46f0412b0f95ad`.
- Status: `R05 A1 CLAIM_CERTAINTY_FIX_READY_FOR_REVIEW / NOT_DEPLOYED`;
  cały R05 pozostaje `IN_PROGRESS`.

## Wykonane

- Odtworzono RV05-01A: expiry po realnym claimie, przed kontaktem, było błędnie
  klasyfikowane jako niepewny handoff w V2 i V1.
- Odtworzono RV05-01B na świeżych sesjach PostgreSQL: kontrolowane przerwanie po
  fake `create_job`, lecz przed zapisem external ID pozwalało na revoke,
  reapprove i drugi fake handoff (`2` zamiast `1`).
- Dodano wersjonowany stan `claimed_no_contact`, `contact_may_have_started`,
  `external_id_recorded`, `local_denied` w istniejącym ledgerze JSON. Nie dodano
  modelu, tabeli ani migracji.
- Lokalny błąd przed kontaktem zwalnia wyłącznie własny pre-contact claim i
  zachowuje reason; możliwy kontakt oraz historyczny attempt bez markera są
  fail-closed. V1 używa tej samej klasyfikacji.

## Dowód

| Kontrola | Wynik |
|---|---|
| fail-before A | `2 failed, 1 passed`, exit `1`; SHA-256 `8CC35FC74BDA859979D5FFB33DA753F6DA91F430F8E0BABB7B2443B4DDB14CE9` |
| fail-before B | `1 failed`, exit `1`; drugi fake handoff; SHA-256 `F5183080B43D40A18ABE15C89F637C4CCB5F33D3EC1ABAC6DD97C646754DE9D3` |
| skupiony pass-after | `20 passed`, exit `0`; SHA-256 `BB98BEDB336CBEA4546227289F22326BA1184C9C89F5FAFB58B9DBDEF517A541` |
| zapisany external ID / walidacja wyniku | `5 passed`, exit `0`; SHA-256 `374841A72F2D8AB4B8F817807885A9B320780D34C6418AF116C9635E57FC40AC` |
| crash/revoke PostgreSQL | `1 passed`, exit `0`; SHA-256 `BB8241340428B17FC820999476F0AE4FB992D435DA00A16272AEDD4F5FA56805` |
| regresja bez DB | `316 passed`, exit `0`; SHA-256 `09801011BC2FDF1FE48394EB192B5A10650AD55A81D795FF371429EDC6B3FE4B` |
| regresja PostgreSQL | `59 passed`, exit `0`; SHA-256 `10C92F4EE53351EBCC8E7704D119EFDCB22BF26C7CACFAECC74CDA9D85E517AF` |
| auth/lifespan | `8 × 401`, product lifespan `0`, exit `0`; SHA-256 `47E12F02641D28E0375F6AF49F105500AB9A03EE7D74B18A534C30C8DA0CE63F` |
| compileall | exit `0`; SHA-256 `81ADC3EA1A5BA1FE66C8A22A28017E28ED79B7BB4E77C002CD6C45E8048AB9AF` |

Logi są `LOCAL_ONLY` w
`C:\ai-lab-core-staging\recovery\R05_A1_CLAIM_CERTAINTY_20260911T191840Z`.
Przypięty obraz testowy: `sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`.
Testy bez DB miały network none; PostgreSQL używał własnej internal network,
host ports `0`, syntetycznych danych i fake Supervisora.

## Skutki i stan

- Utworzono i po testach usunięto wyłącznie własny kontener PostgreSQL
  `next-stabil-r05-a1-certainty-20260911t192258z-postgres`, named volume
  `next-stabil-r05-a1-certainty-20260911t192258z-postgres-data` oraz sieć
  `next-stabil-r05-a1-certainty-20260911t192258z-network`; pełne ID/owner/run
  sprawdzono przed cleanupem, a później potwierdzono zero tych nazw.
- Aplikacja, normalny lifespan, dispatchery, realny Supervisor, modele,
  Temporary Chat, Qdrant, Gmail, n8n i realny eksport: `NOT_RUN`.
- Produkcyjna DB/storage/config/runtime, main, rescue oraz oryginalny dirty
  worktree: bez zmian tej sesji.
- R03 pozostaje `WAITING_APPROVAL / WAITING_ESCROW_DECISION`; R04 i R05
  pozostają `IN_PROGRESS`; R06–R24 nieuruchomione.
- Rzeczywisty uploader/UI/export/end-to-end: `NOT_VERIFIED`.

Następny bezpieczny krok i STOP: właściciel przegląda source
`d31e105427acd40733e91c4d4b46f0412b0f95ad` oraz ten dowód i osobno decyduje o
odbiorze poprawki. Bez realnego eksportu, wdrożenia i bez R06.

Poprzedni checkpoint:
`docs/recovery/checkpoints/20260911T180210Z-R05-A1-HANDOFF-SCOPE.md`.
