# DOC-04 versioned Windows metadata-repair runtime

> **THE WINDOWS REPAIR RUNTIME USES OFFICIAL CPYTHON 3.12.10 AS AN
> EXPLICIT SAME-MINOR COMPATIBILITY VARIANCE FROM THE 3.12.13 BACKEND.**
>
> **DOC-04B DOES NOT AUTHORIZE PRODUCTION PREFLIGHT OR PRODUCTION REPAIR.**

This directory defines a native Windows amd64, portable, one-shot runtime for
the already accepted DOC-04A metadata repair. It provides synthetic readiness;
it does not repair data, deploy source, alter a database, or replace the Linux
backend runtime.

## Trust model

- The Python payload is the official `python-3.12.10-embed-amd64.zip` release.
- Every Python and PyPI artifact is named, sized, and SHA-256 pinned in
  `runtime-lock.json`; online builds independently recheck wheel identity using
  the corresponding official PyPI JSON endpoint.
- `python.exe` and `python312.dll` must have a valid Python Software Foundation
  Authenticode signature and product version 3.12.10.
- Archive extraction is bounded direct PowerShell/.NET ZIP/GZip processing.
  Python `zipfile` and `tarfile`, blind archive expansion, package resolution,
  and wheel scripts or `.pth` payloads are not used. The sole source-only
  artifact, official `odfpy` 1.4.1, is qualification-only: it is hash-pinned
  and its pure `odf/` package is selected by a bounded fail-closed TAR reader;
  no build script executes. No source distribution enters Production.
- The runtime contains dependencies only. Application source is imported
  directly from an exact Git worktree after HEAD and Git-cleaned blob checks.
- Final invocation is offline, isolated (`-I -B -X utf8`), and never falls back
  to an installed interpreter.
- Every supported Windows invocation goes through `invoke-repair.ps1`. The
  wrapper creates a fresh synthetic environment directory outside the source,
  data, and backup roots, launches with `System.Diagnostics.ProcessStartInfo`,
  sets `UseShellExecute=false`, assigns an explicit `WorkingDirectory`, clears
  the inherited environment, and supplies only a bounded allowlist.
- Runtime and cache paths must be strict descendants of the lock-pinned
  `C:\ai-lab-core-staging\doc04b-runtime` and
  `C:\ai-lab-core-staging\doc04b-cache` parents. The repository, data root,
  `C:\ai-lab-core-backups`, E:, F:, system, Program Files, ProgramData, and
  startup roots are forbidden. Complete parent chains and runtime contents are
  rejected on any reparse point; runtime/cache overlap is forbidden.
- `runtime-entrypoint.py` has standard-library-only top-level imports. It
  validates the environment policy, installs a permanent Python audit hook
  that rejects non-authorized `.env` opens, changes to the approved directory,
  verifies the exact Git source, and only then exposes the backend on
  `sys.path` or imports an `app.*` module.
- Supported network boundaries are none for smoke/parity, a disposable
  loopback PostgreSQL port for isolated tests, and only a separately approved
  forced loopback PostgreSQL endpoint for future production use.

Lock V3 has two non-interchangeable profiles. **Production** contains only the
11-distribution executable import closure for the fixed repair: SQLAlchemy,
greenlet, typing extensions, psycopg plus its Windows binary implementation,
and the Pydantic settings stack. It excludes web servers, FastAPI, Qdrant,
OCR/render/document parsers, Office libraries, NumPy, gRPC, test packages, and
all source distributions. **Qualification** contains the wider 65-package
closure needed by isolated migration and regression suites. `odfpy` 1.4.1 has
no PyPI wheel and is the sole qualification-only source exception. A runtime
profile marker participates in the frozen tree hash; production modes reject a
Qualification tree and isolated tests reject a Production tree.

## Patch variance and security delta

Python 3.12.13 is source-only and has no official Windows embeddable package;
3.12.10 is the final official Python 3.12 Windows binary release. The lock
therefore records an explicit same-minor variance and the official security
changes in 3.12.11, 3.12.12, and 3.12.13.

The runtime architecture eliminates reachability of the affected parsing
surfaces. Repair code uses lexical JSON escape handling rather than non-strict
Unicode codecs. Runtime archives are hash-locked and extracted by bounded .NET
code. XML, HTML, mail, HTTP-server, property-list, data-URL, and tar parsers do
not receive customer metadata. HTTP/TLS packages may import `ssl`, but no HTTP
or TLS call occurs in a supported repair mode. Compatibility vectors must be
byte-identical under Windows 3.12.10 and the immutable Linux backend image's
Python 3.12.13 before the runtime is ready.

## Build and deterministic offline rebuild

Use a clean, exact audit worktree and staging/cache roots outside the
repository, its data directory, system locations, startup locations, and all
backup volumes.

1. Invoke `build-runtime.ps1` with an explicit `-Profile Production` or
   `-Profile Qualification`; there is no default.
2. Build online and offline trees for both profiles. The builder may obtain
   only lock-listed HTTPS artifacts from the three allowlisted hosts.
3. Require each profile's online/offline hash and count to match its separate
   frozen identity.
4. Successful complete readiness retains only the Production online runtime,
   its adjacent manifest, and the final report. Qualification, offline, scratch,
   temporary Git, synthetic roots, and disposable containers are removed.
   A verified cache remains only when the harness explicitly requests it.

The tree identity is SHA-256 over records sorted by relative path. Each record
is `relative-path NUL byte-count NUL file-sha256 LF`. The adjacent safe runtime
manifest is deliberately outside the runtime tree to avoid recursion.

## Synthetic readiness

`test-runtime.ps1` is the only complete readiness harness. It verifies supply
chain, online/offline determinism, signatures, negative archive and source
identity cases, the fixed compatibility vectors, and DOC-04A matrices in the
portable interpreter against an isolated disposable PostgreSQL container.
The container uses temporary storage, a random loopback port other than 5432,
no production network or volume, and is removed in a `finally` block.

`invoke-repair.ps1 -Readiness` requires an explicit staging `SyntheticRoot` and
performs only the bounded smoke import. The wrapper—not caller location—selects
the child's fresh working directory. It does not read `.env`, storage, backups,
or production data and does not connect to a database. The same wrapper owns
the fixed repair-help, compatibility-vector, isolated-test, and isolated-
Alembic modes; diagnostics never invoke the backend repair module directly.

Readiness also runs the L01–L20 isolation matrix and M01–M30 closure matrix:
bounded backend result relay, exact refusal propagation, profile minimality and
separation, staging/backup-root policy, reparse rejection, builder environment
preservation, owned partial cleanup, parent controls, and success cleanup.
The fixed relay captures backend Python stdout/stderr in bounded memory,
validates exactly one JSON object, emits only the validated object through the
preserved result descriptor, and retains the backend exit code. Thus a valid
`DOCUMENT_METADATA_REPAIR_*` refusal is not collapsed into a generic wrapper
failure. The remaining isolation checks cover hostile caller directories,
a synthetic poison dotenv positive control, inherited application/Python
environment scrubbing, explicit child-CWD proof, synthetic-root rejection,
production-shaped dotenv allowlist proof entirely under temporary staging,
output redaction, and caller-location independence. Backend parity resolves
only the immutable `.Image` field of `ai-lab-backend`; an optional expected ID
can only constrain that value and can never substitute another image. The
disposable parity container has no network and is removed. None of those tests
names, opens, stats, or probes a production dotenv file.

## Production gates are intentionally dormant

The launcher defines separate `ProductionPreflight` and `ExecuteProduction`
parameter sets for a future owner-approved operation. There is no implicit
production mode. Both require exact main/Git identity, an explicit environment
root and data root, the complete frozen repair contract, a non-empty approval
identifier, and the existing repair executable's production guards. Execute
also requires the exact write-awareness switch and a runtime-supplied fixed
confirmation phrase.

No production command with filled values is documented here. A future run must
receive separate authorization, fresh backup and concurrency evidence, and
fresh exact guard values. The wrapper never creates a backup or infers a guard.
For either dormant production parameter set the process environment is still
rebuilt from an empty collection, the working directory is exactly the explicit
environment root, PostgreSQL is forced to loopback `ai_lab`, and the audit hook
permits only that environment root's exact regular, non-reparse `.env`. Its
resolved identity must match the explicit audit allowlist, and the full existing
parent chains of EnvironmentRoot and DataRoot must be non-reparse. Those parameter sets are not
part of synthetic readiness and must not be exercised without a later owner
gate.

## Cleanup

After independent review, remove only the explicitly identified disposable
comparison/PostgreSQL containers and any specifically named staging runtime or
cache that the owner authorizes removing. Never recursively remove an unknown
directory. Cleanup is not part of normal invocation, and no service, task,
registry entry, global interpreter, or system PATH change is created.
