# D-23 — ANTI_EXCESSIVE_WORK policy recorded

UTC: 2026-09-20T18:07:14Z

Baseline read before the documentation change:
`efc951bbc8a60cb9579538b8dba26255cc6b3c55` on
`recovery/next-stabil-repair-completion`, with local/tracking/remote equal and
no pre-existing WIP.

## Result

- Added the canonical `ANTI_EXCESSIVE_WORK` section near roadmap §0.
- Added owner decision D-23; decisions are now expected to total 23, with one
  D-21, one D-22 and one D-23.
- Added short mandatory references in `AGENTS.md` and
  `AI_LAB_FOLLOWUP_PLAN.md`; the roadmap remains the sole full policy source.
- Defined K0/K1/K2/K3, frozen acceptance contracts, collective first review,
  diff-focused second review, the `2/2` loop stop, preservation of unchanged
  accepted evidence, the ChatGPT reread obligation and the mandatory report
  footer.
- Applied the policy to the existing R04/P4-B contract without a new product
  audit or a new acceptance decision.

## Preserved state

This was documentation only. No product source, tests, host, Docker, Task
Scheduler, UAC, runtime, data, import, backup, retry or rollback operation was
performed. Current P4/B operational approvals remain unchanged and consumed as
previously recorded. Host22/run01 status is unchanged. D-22 remains unchanged
and `NOT_RUN`.

Status:
`ANTI_EXCESSIVE_WORK_POLICY_RECORDED / DOCUMENTATION_ONLY /
CURRENT_OPERATIONAL_APPROVALS_UNCHANGED`.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną tej zwrotki i kolejnym promptem przeczytaj
`NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md`: §0, `ANTI_EXCESSIVE_WORK` oraz
aktywną kartę/checkpoint. Pełny SHA publikacji i przypięty link znajdują się w
końcowej odpowiedzi; baseline tego dokumentu to
`efc951bbc8a60cb9579538b8dba26255cc6b3c55`.

Nie wracaj do odebranych etapów i nie dodawaj K2/K3 do warunków odbioru.
K0/K1 blokujące ten dokumentacyjny krok: `BRAK`.
Efekt użytkowy i pozostałe kryterium: polityka jest zapisana; R04 wraca do
jednego review już przygotowanego narrow-update package.
Cykl `naprawa -> review`: `0/2` dla tego zapisu dokumentacyjnego; następny krok:
niezależny review dokładnego pakietu P4/B, bez operacji hosta.
