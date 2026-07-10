# gtm-sales-agent

## Hosting

This app has two deployable parts:

- `backend/`: FastAPI API
- `frontend/`: Vite React app

### Backend on Render

Create a new Render Web Service from this GitHub repo.

Settings:

- Root directory: leave blank, or use repo root
- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`

Environment variables:

- `ANTHROPIC_API_KEY`: your Anthropic API key
- `ALLOWED_ORIGINS`: your frontend URL, for example `https://your-app.vercel.app`

After deploy, test:

```bash
curl https://your-backend.onrender.com/health
```

### Frontend on Vercel

Create a new Vercel project from this GitHub repo.

Settings:

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`

Environment variables:

- `VITE_API_BASE_URL`: your backend URL, for example `https://your-backend.onrender.com`

Redeploy the frontend after setting `VITE_API_BASE_URL`.

### Local development

Backend:

```bash
uvicorn backend.app:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```
