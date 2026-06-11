# ResearchGPT Deployment Guide

This project is ready to deploy as a FastAPI backend with PostgreSQL, persistent PDF storage, and persistent ChromaDB storage.

## Production Files

- `requirements.txt`: Python dependencies pinned from the tested local environment.
- `.env.example`: Safe template for production secrets and service configuration.
- `.gitignore`: Excludes local env files, virtualenvs, caches, ChromaDB data, uploaded papers, and editor files.
- `Dockerfile`: Python 3.11 production image running `uvicorn app:app`.
- `docker-compose.yml`: Backend plus PostgreSQL with persistent volumes, health checks, restart policies, and a private network.

## Environment Setup

1. Copy the template:

```bash
cp .env.example .env
```

2. Replace all placeholder secrets in `.env`.

3. Use a strong JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

4. For Docker Compose, keep `DATABASE_URL` pointed at the Compose database host:

```env
DATABASE_URL=postgresql://researchgpt_user:your-postgres-password@postgres:5432/researchgpt_db
```

5. If Ollama runs on your host machine, keep:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

For a cloud Ollama-compatible endpoint, replace it with that private service URL.

## Docker Commands

Build the image:

```bash
docker build -t researchgpt-backend:latest .
```

Run locally with Docker only:

```bash
docker run --env-file .env -p 8000:8000 -v researchgpt_chromadb:/app/chromadb -v researchgpt_papers:/app/papers researchgpt-backend:latest
```

Verify the container:

```bash
curl http://localhost:8000/api/health
```

## Docker Compose Commands

Start the full stack:

```bash
docker compose up -d --build
```

Stop containers:

```bash
docker compose down
```

Stop containers and keep data:

```bash
docker compose down
```

Stop containers and delete all persistent data:

```bash
docker compose down -v
```

Restart:

```bash
docker compose restart
```

View logs:

```bash
docker compose logs -f researchgpt-backend
docker compose logs -f postgres
```

Check service health:

```bash
docker compose ps
curl http://localhost:8000/api/health
```

Open API docs:

```bash
http://localhost:8000/docs
```

## PostgreSQL

The `postgres` service automatically creates the database from:

```env
POSTGRES_DB=researchgpt_db
POSTGRES_USER=researchgpt_user
POSTGRES_PASSWORD=your-postgres-password
```

Data persists in the `postgres_data` Docker volume.

The backend runs `python create_tables.py` before Uvicorn when started by Docker Compose, so tables are created and verified against the existing SQLAlchemy models.

## ChromaDB Persistence

ChromaDB data is written to:

```env
CHROMADB_PATH=/app/chromadb
```

Docker Compose mounts that path to the `chromadb_data` volume. Uploaded PDFs are mounted to `papers_data`. Both survive container restarts and image rebuilds.

## Render Deployment

1. Push the repository to GitHub.
2. Create a PostgreSQL database in Render.
3. Create a Web Service from the repository.
4. Use Docker as the runtime.
5. Add environment variables from `.env.example` in Render's dashboard.
6. Set `DATABASE_URL` to the Render PostgreSQL internal connection string.
7. Add persistent disk storage if you want uploaded PDFs and ChromaDB data to survive deploys:
   - Mount path: `/app/papers`
   - Mount path: `/app/chromadb`
8. Deploy and verify:

```bash
curl https://your-render-service.onrender.com/api/health
```

## Railway Deployment

1. Create a Railway project from GitHub.
2. Add a PostgreSQL service.
3. Add the backend service using the Dockerfile.
4. Set environment variables from `.env.example`.
5. Use Railway's PostgreSQL connection value for `DATABASE_URL`.
6. Add persistent volumes for `/app/papers` and `/app/chromadb` if available on your plan.
7. Deploy and open `/api/health`.

## PostgreSQL Cloud

Use any managed PostgreSQL provider such as Render PostgreSQL, Railway PostgreSQL, Supabase, Neon, Aiven, or AWS RDS.

Set:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
```

For hosted providers that require SSL, use:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

## HTTPS

Use HTTPS at the platform edge:

- Render and Railway provide HTTPS automatically.
- For a VPS, place Nginx or Caddy in front of the backend.
- Terminate TLS at the reverse proxy and forward traffic to `http://127.0.0.1:8000`.

Caddy example:

```caddyfile
api.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

## Custom Domain

1. Add the domain in your hosting provider.
2. Add the DNS record requested by that provider:
   - `CNAME` for subdomains such as `api.example.com`
   - `A` record for root domains if required
3. Enable HTTPS/TLS.
4. Verify:

```bash
curl https://api.example.com/api/health
```

## Frontend Deployment

The `frontend/` directory is a static HTML/CSS/JavaScript app. Deploy it as a static site on Render, Railway, Netlify, Vercel, GitHub Pages, or any static hosting provider.

If the frontend and API use different domains, configure the frontend API base before loading scripts:

```html
<script>
  window.RESEARCHGPT_API_BASE = "https://api.example.com";
</script>
```

Place that snippet before `frontend/js/auth.js` in each HTML page, or serve frontend and backend from the same origin.

## Portfolio Checklist

- Use managed PostgreSQL or a persistent Docker volume.
- Use persistent storage for `/app/papers` and `/app/chromadb`.
- Keep `.env` out of Git.
- Set long random secrets for `JWT_SECRET_KEY` and `SECRET_KEY`.
- Verify `/api/health`.
- Verify `/docs`.
- Register a demo user.
- Upload a small PDF.
- Ask a question and confirm chat/search history is saved.
