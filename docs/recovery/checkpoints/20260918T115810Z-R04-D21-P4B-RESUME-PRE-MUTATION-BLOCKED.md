# R04 / D-21 / P4-B — resume blocked before mutation

UTC evidence window: `2026-09-18T11:58:08.5630580Z–2026-09-18T11:58:10.5820968Z`

Resume ID: `R04-D21-P4B-RESUME-20260918T112015Z`

Parent OP_ID: `R04-D21-P4B-WINDOW-20260918T084652Z`

Entry HEAD: `79e4bf1b802664851b6499f566d302e868841d67`

## Result

The owner supplied the exact single-use resume authorization and was present
for one Windows UAC prompt. The final local binding confirmed clean recovery,
matching tracking ref and the exact recipe/input/index hashes. One `RunAs` was
issued, the UAC was accepted and elevated installer PID `79808` started at
`2026-09-18T11:58:08.5630580Z`.

The installer passed its elevated-token, owner-SID and exact input-index gate.
Its first Docker container guard then failed before the mutation boundary.
Windows PowerShell 5.1 split the space-containing `docker inspect` Go-template
passed through `Start-Process -ArgumentList`; Docker reported
`unknown shorthand flag: '}' in -}}{{range`. This is a native argument
transport defect in the one-time LOCAL_ONLY recipe, not an observed container
identity mismatch.

The installer event records `mutation_started=false`. The code sets the flag
only after all task/file/container/host pre-mutation guards; therefore none of
the task registration, payload installation, Host activation or warm-run code
was reached. The single UAC was not retried. The permitted SAFE_INACTIVE
rollback was not needed and was not attempted.

## Exact state retained

- Startup wrapper remains absent from Startup; exact rollback copy SHA-256 is
  `C843C05CB023CE187D7C6829DB904E2FDB58B893C8072CBC33E476D7307C06D4`.
- Launcher, runtime and global startup manifest remain absent.
- Existing helper remains SHA-256
  `445AFFC04CF916602A30FDC9BBE0C8557E31AC670E8C5D389636BAB11E6DECC5`.
- The prior Host state remains disabled/no-trigger/never-run; five existing
  tasks remain on their preimages because the resume reached no mutation code.
- Warm runs remain `0/2`; no Host/Private/Supervisor start was requested by the
  resume.
- Repository/global manifest remains `NOT_APPROVED_FOR_START`.
- Supervisor remains `INTENTIONALLY_STOPPED` according to the immediately prior
  bounded preflight; the failed recipe did not reach any service action.

The statement above is scoped to effects of this resume. It does not claim
global zero I/O for independently running host services.

## Local-only evidence

Protected resume root:
`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\p4-startup-activation-20260917T210051Z\p4b-window-20260918T084652Z\r04-d21-p4b-resume-20260918t112015z`

- recipe SHA-256:
  `D8E2868F51F04D179C3749CA6E0691C307BA8B7ABEB668CC9987E60D4A350F61`;
- input index SHA-256:
  `ED8826F7CFAB1A33B84C5FCF3BDA1E57FB48E9598100B3826C0CDDDCC3131CDA`;
- recipe index SHA-256:
  `9DD6A85B14B307DA698513849EC0DF9E81ED7EBDF278B1064329AA64234B6E7E`;
- installer events: 731 B, SHA-256
  `618B31443F27C22E0C745AB54D407FE4FED4C0177A85B5B1B5331D851E0C6339`;
- Docker stderr: 171 B, SHA-256
  `37965294C541CC98E4D13C3EBB63DE7C24BCC71EFC2ECAE89DB3BD02D9523CBD`;
- Docker stdout: 0 B, SHA-256
  `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.

Raw logs, task XML and payload remain LOCAL_ONLY. No secret, business data,
full inspect or runtime payload is committed.

## Handoff

Status: `P4B PARTIAL_SAFE_INACTIVE /
RESUME_PRE_MUTATION_NATIVE_ARGUMENT_TRANSPORT_FAILED / NOT_INSTALLED`.

Both the original Phase-B authorization and this resume authorization are
consumed. The next permissible step is preparation and review of a corrected
closed-scope recipe that preserves the Go-template as one native argument,
followed by a new exact owner decision and one fresh bounded drift check. This
checkpoint does not authorize another UAC, installation, rollback, warm run,
logon/reboot test, Supervisor, backup/restore, relocation, P5 or R06.
