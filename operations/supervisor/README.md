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

The supervisor binds to `127.0.0.1:8787` and runs outside Docker so it can
start the stack when the backend is stopped.

It reads the existing project `.env` for `SECRET_KEY` and validates HS256
access JWTs independently from FastAPI.

Vision endpoints use a private HMAC-derived bridge header shared only by the
backend and supervisor. They accept neither arbitrary paths/URLs nor commands.
Vision jobs are serialized (one visible Temporary Chat at a time), use only
the `data/vision-spool` tree, and expire terminal working directories after
72 hours.

This phase does not install a Windows service or scheduled task.
