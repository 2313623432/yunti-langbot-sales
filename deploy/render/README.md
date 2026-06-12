# Render deployment

This project runs as a Docker web service on Render.

## Data

The app stores its built-in SQLite database, Chroma vector database, uploads, media, and logs under `data/`.
Render must mount a persistent disk at `/app/data` so this data survives redeploys and restarts.

Do not commit `data/` to GitHub. It can contain real user messages, uploaded media, and provider keys.

## Optional seed data

The Docker image includes the committed local `data/` directory as first-boot seed data.
The startup script copies that seed into the Render disk only when `/app/data/langbot.db` does not exist.

If you do not want to commit future data changes but a new Render disk still needs a different local database on first boot, create a private zip from the local `data` contents:

```powershell
Compress-Archive -Path data\* -DestinationPath langbot-render-data.zip -Force
```

Upload that zip to private storage and set `LANGBOT_SEED_DATA_URL` in Render to the private download URL.
The startup script imports this zip only when `/app/data/langbot.db` does not already exist, so existing Render data is not overwritten.

The zip may contain either the contents of `data/` directly or a top-level `data/` folder.

## Render settings

Use the repository Blueprint in `render.yaml`.

Required settings:

- Runtime: Docker
- Disk mount path: `/app/data`
- Health check path: `/api/v1/system/info`
- Branch: choose the branch you want Render to deploy

After deploy, set `API__WEBHOOK_PREFIX` to the public Render URL if your bot adapters need an externally reachable webhook URL.
