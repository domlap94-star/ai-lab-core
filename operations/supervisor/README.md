# AI-Lab Supervisor

Small host-level control plane for the local Docker Compose stack.

Endpoints:

- `GET /health` - local liveness
- `GET /status` - administrator JWT required
- `POST /start` - administrator JWT required
- `POST /restart` - administrator JWT required
- `POST /stop` - administrator JWT required

The supervisor binds to `127.0.0.1:8787` and runs outside Docker so it can
start the stack when the backend is stopped.

It reads the existing project `.env` for `SECRET_KEY` and validates HS256
access JWTs independently from FastAPI.

This phase does not install a Windows service or scheduled task.