# Deploying WithCare to Render (+ optional Vercel)

The repo has two config files:

- **`render.yaml`**: a Render Blueprint that deploys the **backend** (FastAPI, Docker) and the **frontend** (Vite static site).
- **`withcare-frontend/vercel.json`**: use this if you'd rather host the **frontend on Vercel**. The backend still goes on Render.

```
Browser ──▶ Frontend (Render static site  or  Vercel)
               │  VITE_API_URL
               ▼
            Backend (Render, Docker)  ──▶ Vertex AI Gemini, Firestore   (service-account.json)
                                      ──▶ Calendar / Drive / Gmail      (token.json)
                                      ──▶ Google Maps                   (API key)
                                      ──▶ SQLite file                   (local disk)
```

The backend still runs on your **Google Cloud project** (Vertex AI + Firestore). Render can't
use Cloud Run's built-in identity, so it authenticates with a **service account key file**.

---

## 1. Create a service account key (one-time, in Google Cloud)

```bash
export PROJECT_ID="your-gcp-project-id"
gcloud iam service-accounts create withcare-render --project "$PROJECT_ID"
export SA="withcare-render@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in roles/aiplatform.user roles/datastore.user; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" --role="$ROLE" --condition=None
done

gcloud iam service-accounts keys create service-account.json --iam-account="$SA"
```

(Or do it in Console → IAM → Service Accounts → *Keys → Add key → JSON*.)
**Never commit `service-account.json`.** `.gitignore` already excludes it.

You also need `withcare-backend/token.json` (Calendar/Drive/Gmail). Generate it with
`python scripts/setup_calendar_auth.py` if you don't have it.

---

## 2. Deploy on Render

1. Push this repo to GitHub.
2. Render dashboard → **New → Blueprint** → select the `WithCare` repo. Render reads `render.yaml`.
3. It asks for the `sync: false` values:
   | Service | Key | Value |
   |---|---|---|
   | backend | `GCP_PROJECT_ID` | your GCP project id |
   | backend | `GOOGLE_MAPS_API_KEY` | Maps key (restrict by API, **not** by HTTP referrer) |
   | backend | `GOOGLE_OAUTH_CLIENT_ID` | `xxxx.apps.googleusercontent.com` |
   | frontend | `VITE_API_URL` | `https://withcare-backend.onrender.com` (see step 5) |
   | frontend | `VITE_GOOGLE_CLIENT_ID` | same OAuth client id |
4. **Secret files.** Open `withcare-backend` → *Environment* → **Secret Files** and add:
   - `service-account.json` with the key from step 1
   - `token.json` with the contents of `withcare-backend/token.json`

   Render mounts them at `/etc/secrets/…`, where the env vars in `render.yaml` already point.
5. Copy the backend's public URL (e.g. `https://withcare-backend-abcd.onrender.com`).
   If it differs from what you entered, update `VITE_API_URL` on the frontend and click
   **Manual Deploy → Clear build cache & deploy**. Vite bakes env vars in at build time.
6. Check that it works: `curl https://<backend-url>/health` should return `{"status":"ok",...}`.

---

## 3. (Optional) Frontend on Vercel instead

1. Vercel → **Add New → Project** → import the repo.
2. **Root Directory:** `withcare-frontend`. Everything else comes from `vercel.json`.
3. Environment variables: `VITE_API_URL` = your Render backend URL, `VITE_GOOGLE_CLIENT_ID` = OAuth client id.
4. Deploy. Then delete the `withcare-frontend` service from `render.yaml` (or from the Render
   dashboard) so you aren't running two copies.

---

## 4. Post-deploy: Google sign-in

Google Cloud Console → *APIs & Services → Credentials* → your **Web OAuth client** →
**Authorized JavaScript origins**: add your frontend URL, for example
`https://withcare-frontend.onrender.com` or `https://withcare.vercel.app`.
Sign-in fails from any origin that isn't listed.

---

## Caveats

- **SQLite data on the free plan doesn't survive restarts.** The free plan has no persistent disk, and it
  sleeps after ~15 min idle, so users and history reset on every restart or deploy. To keep the data,
  set the backend to `plan: starter`, uncomment the `disk:` block in `render.yaml`, and set
  `WITHCARE_DB_PATH=/var/data/withcare.db`.
- **Cold starts.** A sleeping free service takes ~30–60 s to answer its first request.
- **Memory.** The free plan has 512 MB. If the backend gets OOM-killed, move it to `starter`.
- **CORS** allows all origins (`app/main.py`). To lock it down, set it to your frontend URL.
