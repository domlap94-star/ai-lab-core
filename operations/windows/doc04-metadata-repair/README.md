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
  directly from an exact Git worktree after a protected-scope cleanliness
  check, exact `backend/app` Git-tree identity, and path-aware Git blob
  verification of every tracked file. The critical-file list remains an
  additional contract; dirty files outside the protected scope remain allowed.
- Final invocation is offline, isolated (`-I -B --check-hash-based-pycs always
  -X utf8 -X pycache_prefix=<fresh invocation path>`), and never falls back to
  an installed interpreter. `TEMP`, `TMP`, Git HOME/config, and bytecode cache
  all live in a fresh invocation-owned staging directory that is removed after
  the child exits. Source-tree bytecode is rejected and is never imported.
- Every supported Windows invocation goes through `invoke-repair.ps1`. The
  wrapper creates a fresh synthetic environment directory outside the source,
  data, and backup roots, launches with `System.Diagnostics.ProcessStartInfo`,
  sets `UseShellExecute=false`, assigns an explicit `WorkingDirectory`, clears
  the inherited environment, and supplies only a bounded allowlist.
- Lock V5 closes the physical source set in addition to Git identity. Every
  physical file and directory below `backend/app` must correspond exactly to a
  tracked Git entry, and the runtime-tooling directory must contain exactly its
  six locked files. Ignored bytecode/native payloads, import shadows, namespace
  directories, missing or case-mismatched entries, and reparse objects fail
  closed. The pinned `.gitattributes`, requirements blob, and compose blob are
  verified with system/global Git config and attributes disabled; non-empty
  `.git/info/attributes` and protected-path filter, ident, or
  `working-tree-encoding` attributes are rejected.
- Lock V5 separates runtime/cache, non-production working, and production
  configuration path policies. Runtime and cache paths must be strict descendants of the lock-pinned
  `C:\ai-lab-core-staging\doc04b-runtime` and
  `C:\ai-lab-core-staging\doc04b-cache` parents. The repository, data root,
  `C:\ai-lab-core-backups`, E:, F:, system, Program Files, ProgramData, and
  startup roots are forbidden. Non-production working roots stay in staging
  and cannot overlap a runtime payload. A production `EnvironmentRoot` may be
  the explicit application/repository root, but never a data, backup, E:/F:,
  runtime/cache, system, startup, drive-root, or reparse path. Complete parent chains and runtime contents are
  rejected on any reparse point; runtime/cache overlap is forbidden.
- `runtime-entrypoint.py` has standard-library-only top-level imports. It
  validates the environment policy, installs a permanent Python audit hook
  that rejects non-authorized `.env` opens, changes to the approved directory,
  verifies the exact Git source, and only then exposes the backend on
  `sys.path` or imports an `app.*` module.
- A second permanent audit hook measures and enforces Python-observable socket,
  hostname-resolution, urllib, and HTTP activity. Supported network boundaries are none for smoke/parity, a disposable
  loopback PostgreSQL port for isolated tests, and only a separately approved
  forced loopback PostgreSQL endpoint for future production use. The sole
  non-DB exception is CPython's private `_fallback_socketpair` self-connection
  used to wake a Windows asyncio event loop; exact stdlib source/function
  identity bounds it, and it cannot select an external endpoint. Native
  `psycopg-binary`/libpq networking is not visible to Python audit hooks, so
  database host, port, name, and isolation remain separately enforced.

Lock V5 has two non-interchangeable profiles. **Production** contains only the
12-distribution executable import closure for the fixed repair: SQLAlchemy,
greenlet, typing extensions, psycopg plus its Windows binary implementation,
the Pydantic settings stack, and locked IANA timezone data required for silent
PostgreSQL timezone adaptation. It excludes web servers, FastAPI, Qdrant,
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
not receive customer metadata. The fixed `production-source-security-trace`
records the repository-relative `app.*` import closure, its SHA-256, selected
stdlib-module presence, and the distribution closure on Windows 3.12.10 and
backend 3.12.13. Transitive imports such as `email`, `urllib.request`,
`http.client`, `zipfile`, `ipaddress`, and `ssl` are recorded truthfully but
remain unreachable from customer-controlled parser or network input.
`tzdata` is exercised by the real PostgreSQL preflight rather than the
connection-free import trace, so the trace has 11 imported distributions while
the fixed Production runtime contains 12 locked distributions.
Compatibility vectors must remain byte-identical across both patch versions.

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

Readiness also runs the L01–L20 isolation matrix, M01–M30 closure matrix, and
N01–N28 production-path/source-closure matrix, plus O01–O32 executable
source-authority matrix:
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
harness performs exactly one `docker inspect --format '{{.Image}}'
ai-lab-backend` per campaign and reuses the resulting immutable ID. The
disposable parity container has no network and is removed. None of those tests
names, opens, stats, or probes a production dotenv file.

The O matrix exercises ignored `.pyc`/`.pyd` and import-shadow rejection,
exact physical file/directory closure, reparse and case rejection, isolated
bytecode/TEMP cleanup, pinned Git attributes and clean-filter bypass resistance,
the requirements/compose pins, single backend image authority lookup, canonical
`EnvironmentRoot\data`, and the complete Python-observable network event deny
set. `socket.sendto`, `socket.sendmsg`, reverse lookup, service lookup, and
arbitrary bind are always rejected. Bind is allowed only for CPython's narrowly
identified internal fallback socketpair. The allowed database endpoint remains
numeric `127.0.0.1` at the one approved port. `psycopg-binary`/libpq native
networking remains separately pinned by database host, port, name, and live
PostgreSQL identity.

The N matrix runs the actual repair `main()` through the Production runtime and
normal bounded relay against disposable PostgreSQL. Qualification alone
migrates and seeds synthetic Document 8903, managed-backup evidence, and
temporary files. Production runs `--preflight-production`; Qualification then
proves the row, metadata, relations, storage, and backup fixtures unchanged. A
wrong-before-hash control must relay the exact backend refusal. The same test
uses a clean temporary clone whose `EnvironmentRoot` equals its `RepoRoot`.
Fixture timestamps are relayed as invariant ISO-8601 arguments even when the
host PowerShell deserializer materializes JSON timestamps as `DateTime` values.

## Production gates are intentionally dormant

The launcher defines separate `ProductionPreflight` and `ExecuteProduction`
parameter sets for a future owner-approved operation. There is no implicit
production mode. Both require exact main/Git identity, an explicit environment
root and canonical data root exactly equal to `EnvironmentRoot\data`, the
expected lowercase SHA-256 of the exact `.env`, the complete frozen repair contract, a non-empty approval
identifier, and the existing repair executable's production guards. Execute
also requires the exact write-awareness switch and a runtime-supplied fixed
confirmation phrase.

No production command with filled values is documented here. A future run must
receive separate authorization, fresh backup and concurrency evidence, and
fresh exact guard values. The wrapper never creates a backup or infers a guard.
For either dormant production parameter set the process environment is still
rebuilt from an empty collection, the working directory is exactly the explicit
environment root, PostgreSQL is forced to loopback `ai_lab`, and the audit hook
permits only that environment root's exact regular, non-reparse `.env`. The
launcher opens it read-only with reader-only sharing, verifies its hash, holds
the handle for the complete child lifetime, and verifies the hash again before
closing. Its resolved identity must match the audit allowlist, and the full
existing parent chains of EnvironmentRoot and DataRoot must be non-reparse.
The compose source is blob-pinned and must retain the exact `../../data:/data`
mapping. Alternate byte-identical copies, backup volumes, runtime/cache roots,
system locations, and reparse paths are not valid data authority. The synthetic Production-profile proof still does not authorize a real
production preflight or repair. Those parameter sets are not
part of synthetic readiness and must not be exercised without a later owner
gate.

## Cleanup

After independent review, remove only the explicitly identified disposable
comparison/PostgreSQL containers and any specifically named staging runtime or
cache that the owner authorizes removing. Never recursively remove an unknown
directory. Cleanup is not part of normal invocation, and no service, task,
registry entry, global interpreter, or system PATH change is created.
