# Deploying WithCare to Google Cloud

**Architecture:** Backend (FastAPI) → **Cloud Run**, with the SQLite DB on a mounted
**Cloud Storage** volume. Frontend (Vite) → **Firebase Hosting**. Gemini runs on
**Vertex AI** and data on **Firestore**, both via the Cloud Run service account (no key files).

```
Firebase Hosting  ──VITE_API_URL──▶  Cloud Run (backend)
                                        ├─ Vertex AI (Gemini)      [IAM: aiplatform.user]
                                        ├─ Firestore (facilities)  [IAM: datastore.user]
                                        ├─ GCS bucket → /mnt/db     [SQLite lives here]
                                        ├─ Maps API key             [env var]
                                        └─ token.json (Calendar)    [Secret Manager]
```

---

## 0. Prerequisites (one-time)

```bash
# Install the CLIs if you don't have them:
#   gcloud  → https://cloud.google.com/sdk/docs/install
#   firebase → npm install -g firebase-tools

gcloud auth login
firebase login

# Pick your values once — reused throughout:
export PROJECT_ID="withcare-prod"          # your GCP project id
export REGION="asia-south1"                 # Mumbai (closest to India users)
export BUCKET="${PROJECT_ID}-db"            # bucket that holds the SQLite file
export SERVICE="withcare-backend"

gcloud config set project "$PROJECT_ID"
```

---

## 1. Enable the APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  maps-backend.googleapis.com \
  geocoding-backend.googleapis.com \
  places-backend.googleapis.com \
  distance-matrix-backend.googleapis.com
```

If you haven't created the Firestore database yet:

```bash
gcloud firestore databases create --location="$REGION" --type=firestore-native
```

---

## 2. Create the GCS bucket for the SQLite DB

```bash
gcloud storage buckets create "gs://${BUCKET}" --location="$REGION" --uniform-bucket-level-access
```

> The DB file is created automatically on first write at `/mnt/db/withcare.db`.

---

## 3. Store the Calendar token as a secret

`token.json` is the shared Google account used for Calendar/Drive/Gmail. Generate it
locally first (if you haven't): `python scripts/setup_calendar_auth.py`, then:

```bash
gcloud secrets create withcare-token --replication-policy=automatic
gcloud secrets versions add withcare-token --data-file="withcare-backend/token.json"
```

---

## 4. Grant the Cloud Run service account its roles

```bash
# Default compute service account (or create a dedicated one)
export SA="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

for ROLE in \
  roles/aiplatform.user \
  roles/datastore.user \
  roles/secretmanager.secretAccessor ; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA}" --role="$ROLE" --condition=None
done

# Read/write the SQLite bucket
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${SA}" --role="roles/storage.objectAdmin"
```

---

## 5. Deploy the backend to Cloud Run

Run from the repo root. `--source` builds the image from `withcare-backend/Dockerfile`.

```bash
export MAPS_KEY="YOUR_GOOGLE_MAPS_API_KEY"
export OAUTH_CLIENT_ID="YOUR_WEB_OAUTH_CLIENT_ID.apps.googleusercontent.com"

gcloud run deploy "$SERVICE" \
  --source=withcare-backend \
  --region="$REGION" \
  --allow-unauthenticated \
  --execution-environment=gen2 \
  --max-instances=1 \
  --memory=1Gi \
  --add-volume=name=db,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount=volume=db,mount-path=/mnt/db \
  --set-secrets=/secrets/token.json=withcare-token:latest \
  --set-env-vars=^@^WITHCARE_DB_PATH=/mnt/db/withcare.db@WITHCARE_TOKEN_PATH=/secrets/token.json@GCP_PROJECT_ID=$PROJECT_ID@GEMINI_LOCATION=us-central1@GOOGLE_MAPS_API_KEY=$MAPS_KEY@GOOGLE_OAUTH_CLIENT_ID=$OAUTH_CLIENT_ID@ENVIRONMENT=production
```

> **Why `--max-instances=1`:** SQLite is a single-writer file. One instance avoids
> concurrent writers corrupting the DB on the GCS volume. Fine for a demo; if you ever
> need to scale out, that's the moment to move to the Firestore migration.
>
> **Why the `^@^` prefix:** it changes the env-var delimiter to `@` so values (like the
> Vertex location) can contain commas safely.

Grab the URL it prints:

```bash
export BACKEND_URL="$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')"
echo "$BACKEND_URL"
curl -s "$BACKEND_URL/health"   # → {"status":"ok",...}
```

---

## 6. Deploy the frontend to Firebase Hosting

```bash
cd withcare-frontend

# Point the build at the deployed backend
echo "VITE_API_URL=$BACKEND_URL" > .env.production

npm ci
npm run build

firebase use "$PROJECT_ID"       # or: firebase init hosting (first time — choose 'dist', SPA = yes)
firebase deploy --only hosting
```

Firebase prints your live URL, e.g. `https://withcare-prod.web.app`.

---

## 7. Post-deploy wiring (required for Google sign-in + Maps)

1. **OAuth origins** — Google Cloud Console → *APIs & Services → Credentials* → your
   **Web OAuth client** → add to **Authorized JavaScript origins**:
   - `https://<PROJECT_ID>.web.app`
   - `https://<PROJECT_ID>.firebaseapp.com`

   (Google sign-in and per-connector consent are blocked from any origin not listed.)

2. **Maps API key** — restrict it by **API** (Geocoding, Places, Distance Matrix), **not**
   by HTTP referrer. The backend calls Maps server-side from Cloud Run, so a referrer
   restriction would block it.

3. **CORS (optional hardening)** — the backend currently allows all origins. To lock it
   down, set `allow_origins` in `withcare-backend/app/main.py` to your Firebase URL and redeploy.

---

## 8. Redeploying after changes

```bash
# Backend
gcloud run deploy "$SERVICE" --source=withcare-backend --region="$REGION"

# Frontend
cd withcare-frontend && npm run build && firebase deploy --only hosting
```

---

## Notes / caveats

- **Single Google account for Calendar/Drive/Gmail.** All bookings use the one `token.json`
  identity. True per-user calendar OAuth is future work (frontend already does per-connector
  consent, but the backend still executes via the shared token).
- **Firestore facility/scheme data.** If your prod project's Firestore is empty, facility
  search falls back to live Google Maps results. Seed Firestore if you want the curated set.
- **Cost.** Cloud Run scales to zero (pay per request); GCS + Secret Manager + Firestore stay
  within free tiers for demo traffic; Vertex Gemini is the main variable cost.
