# Deployment

This project is currently designed for local development, portfolio demonstration and reproducible review. Do not claim production deployment unless you have actually deployed and verified it.

## Implemented

- Local backend and frontend startup.
- Docker Compose services for Redis and Qdrant.
- SQLite local persistence.
- Release archive generation and safety checks.
- GitHub Actions CI for source validation.

## Local Deployment

Use the local quickstart:

- [Quickstart](quickstart.md)
- [Local Development](local_development.md)

## Docker-Based Services

Docker Compose currently starts supporting services:

```powershell
docker compose up -d redis qdrant
```

The API and frontend are usually run directly on the host for easier debugging.

## Optional Cloud Direction

The following are documentation directions, not completed deployments:

- Frontend: Vercel or static-compatible Next.js hosting if API URL is configured.
- Backend: Render, Railway, Fly.io or VPS.
- Worker: separate process with Redis access.
- Qdrant: managed Qdrant or self-hosted container.
- File storage: local storage for demo; object storage would be needed for production.

## Security Notes

- Never commit provider keys.
- Use environment variables or secret managers.
- Keep upload storage outside Git.
- Review release archive manifest before publishing.

## Current Limitations

- No production deployment has been verified in this repository.
- No Docker image for the full API/frontend application is currently provided.
- SQLite is suitable for local demo, not multi-user production.
