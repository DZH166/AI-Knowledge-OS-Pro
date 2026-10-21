# Docker Deployment

Docker Compose is currently used for local supporting services, not a full production application deployment.

## Implemented Services

The current Compose file supports:

- Redis for RQ background tasks.
- Qdrant for vector search.

Validate configuration:

```powershell
docker compose config --quiet
```

Start services:

```powershell
docker compose up -d redis qdrant
```

Stop services:

```powershell
docker compose down
```

## Application Runtime

Current recommended demo runtime:

- Run Redis and Qdrant in Docker.
- Run FastAPI locally.
- Run Next.js locally.

## Planned V4.0 Improvements

- Optional full-stack Compose profile.
- Worker service documentation.
- Volume and backup notes.
- Healthcheck notes.

## Limitations

- Do not present the current Compose setup as full production deployment.
- Provider secrets must still be injected through environment variables, not committed files.
