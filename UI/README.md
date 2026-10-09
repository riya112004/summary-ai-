# AI Analysis

FastAPI + MongoDB Atlas app — auth, dashboard, profile, and per-user document uploads.

## Run

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Open http://127.0.0.1:8000 → `/login`

## Config (`.env`)

| Key | Purpose |
|---|---|
| `MONGO_URI` | MongoDB Atlas connection string |
| `DB_NAME` | `Analysis-AI` |
| `SECRET_KEY` | JWT signing key — **change before deploying** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Session length (default 7 days) |

## Pages

- `/login` — Sign In / Sign Up tabs (name, email, phone, new password, confirm password)
- `/dashboard` — single-page shell with four views:
  - **Dashboard** — Total Documents, Storage Used, Last 7 Days, File Types + 7-day activity bars, type breakdown, 5 recent docs
  - **Upload** — optional title + drag-and-drop / click-to-browse, 25 MB cap
  - **Documents** — searchable table, download, delete
  - **Profile** (avatar menu) — edit name and phone, change password; **email is locked**

## API

| Method | Route | Notes |
|---|---|---|
| POST | `/api/signup` | Sets httpOnly JWT cookie |
| POST | `/api/login` | Sets httpOnly JWT cookie |
| POST | `/api/logout` | Clears cookie |
| GET | `/api/me` | Current user |
| PUT | `/api/me` | Update name / phone / password (email immutable) |
| GET | `/api/stats` | Dashboard counters, scoped to caller |
| POST | `/api/upload` | multipart `file` + `title` |
| GET | `/api/documents?q=&limit=` | Caller's documents only |
| GET | `/api/documents/{id}` | Caller-owned document metadata and extracted raw text |
| POST | `/api/documents/{id}/extract-text` | Retry extraction from the caller's stored GridFS file |
| GET | `/api/documents/{id}/download` | Streams from GridFS |
| DELETE | `/api/documents/{id}` | Removes metadata + GridFS blob |

Uploads store `extracted_text` and `extraction_status` (`pending`, `completed`,
`no_text`, `unsupported`, or `failed`) in the document record. Upload now saves
the original to GridFS and creates the MongoDB document record before starting
text extraction in a background task, so slow OCR does not hold the upload
response open. OCR failures are reported in `extraction_error`; they no longer
silently appear as successful empty extraction.
PDF pages without embedded text and supported image uploads use PaddleOCR. Image
OCR disables PaddleOCR's optional document-orientation, unwarping, and text-line
orientation stages and runs on CPU with OneDNN disabled. OpenCV masks detected
QR/barcode regions and creates one denoised, contrast-enhanced image variant;
PaddleOCR uses PP-OCRv5 mobile detection and recognition models with a
960-pixel detection limit to reduce CPU inference time. OCR detections retain
their confidence and bounding boxes. Row grouping uses adaptive box heights
and vertical-center distances, then orders detections top-to-bottom and
left-to-right; detections without coordinates are retained after positioned
text instead of disabling ordering. Duplicate overlapping detections and
symbol-only noise are removed, and small camera-watermark text at the image
edge is filtered without rewriting recognized letters or digits. Extraction
is limited to 90 seconds and timed-out jobs are marked failed.
PaddleOCR runs in a dedicated single-worker thread rather than a process,
avoiding native Paddle runtime crashes in spawned worker processes while
keeping requests off the event loop. Pending jobs are retried when the server
starts. Set `OCR_LOG_TEXT=true` before starting the server to log raw OCR,
coordinate-ordered text, and cleaned output for comparison; these logs may
include personal information present in uploaded documents.

## Data model (`Analysis-AI`)

- **`users`** — `name`, `email` (unique index), `phone`, `password_hash` (bcrypt), `created_at`
- **`documents`** — `user_id` (ObjectId ref), `title`, `filename`, `content_type`, `size`, `gridfs_id`, `extracted_text`, `extraction_status`, `extraction_error`, `uploaded_at`; index `(user_id, uploaded_at desc)`
- **`user_files.files` / `user_files.chunks`** — GridFS bucket holding the bytes

## Per-user isolation

Every document query carries `user_id` as part of the filter itself — read, download and delete all go through
`find_one({"_id": oid, "user_id": user["_id"]})`, so another account's document id simply returns 404 rather than
leaking existence. Verified end-to-end: a second user sees an empty list, and gets 404 on both download and delete
of the first user's document.
