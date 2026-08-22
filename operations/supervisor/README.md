# AI-Lab Supervisor

Small host-level control plane for the local Docker Compose stack.

Endpoints:

- `GET /health` - local liveness
- `GET /status` - administrator JWT required
- `POST /start` - administrator JWT required
- `POST /restart` - administrator JWT required
- `POST /stop` - administrator JWT required
- `GET /vision/health` - private Vision bridge health
- `POST /vision/jobs` - enqueue one bounded manifest
- `GET /vision/jobs/{job_id}` - get private job state
- `POST /vision/jobs/{job_id}/cancel` - cancel a job
- `POST /vision/resume` - resume after manual ChatGPT authentication/UI review
- `GET /analysis/health` - private advanced-analysis bridge health
- `POST /analysis/jobs` - enqueue one sanitized, hash-bound analysis package
- `GET /analysis/jobs/{job_id}` - get private analysis job state
- `POST /analysis/jobs/{job_id}/cancel` - cancel an analysis job
- `POST /analysis/resume` - resume after manual authentication/UI review

The supervisor binds to `127.0.0.1:8787` and runs outside Docker so it can
start the stack when the backend is stopped.

It reads the existing project `.env` for `SECRET_KEY` and validates HS256
access JWTs independently from FastAPI.

Vision endpoints use a private HMAC-derived bridge header shared only by the
backend and supervisor. They accept neither arbitrary paths/URLs nor commands.
Vision jobs are serialized (one visible Temporary Chat at a time), use only
the `data/vision-spool` tree, and expire terminal working directories after
72 hours.

For advanced analysis, `request_key` is the local input fingerprint used for
diagnostics and duplicate hints; it is not sufficient job ownership. Durable
external identity is the immutable `(analysis_id, package_sha256,
analysis_type)` binding stored in the job manifest. Repeating that exact
binding returns the same queued/running/paused/terminal job. The same
`analysis_id` with a different package or request key fails closed, while a
different `analysis_id` creates a distinct job even when its input fingerprint
matches an older terminal analysis.

The production host starts this process through the existing limited-user
Windows Scheduled Task `NEXT Stabil - Supervisor`. It is not installed as a
Windows service. Task creation and host startup remain operationally gated.
