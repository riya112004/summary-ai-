# AI Analysis Backend

API-only FastAPI + MongoDB Atlas backend for authentication, tasks, activity,
document uploads, OCR, and summaries. A responsive HTML/CSS sign-in and
registration page is served by FastAPI; application APIs and the generated
OpenAPI documentation are also available.

## Run

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.
Open `http://127.0.0.1:8000/` for the sign-in and registration page.

## Config (`.env`)

| Key | Purpose |
|---|---|
| `MONGO_URI` | MongoDB Atlas connection string |
| `DB_NAME` | `Analysis-AI` |
| `SECRET_KEY` | JWT signing key — **change before deploying** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Session length (default 7 days) |
| `OLLAMA_URL` | Local Ollama URL (default `http://127.0.0.1:11434`) |
| `OLLAMA_MODEL` | Self-hosted summary model (default `qwen3:0.6b`) |
| `OLLAMA_TIMEOUT_SECONDS` | Local summary request timeout (default 180 seconds) |

## Web UI

The root path (`/`) and `/login` serve the responsive authentication page;
`/signup` opens the same page with registration selected. The page submits to
the existing `/api/login` and `/api/signup` endpoints and uses their httpOnly
session cookie. Successful authentication opens `/dashboard`, which uses the
provided daily-summary HTML and loads the authenticated user's tasks, today's
meetings, and upcoming document-expiry alerts from `GET /api/dashboard-data`.
Task checkboxes save status through the existing `PATCH /api/tasks/{id}`
endpoint. Unauthenticated dashboard access redirects to `/login`.

## API

| Method | Route | Notes |
|---|---|---|
| POST | `/api/signup` | Sets httpOnly JWT cookie |
| POST | `/api/login` | Sets httpOnly JWT cookie |
| POST | `/api/logout` | Clears cookie |
| GET | `/api/me` | Current user |
| PUT | `/api/me` | Update name / phone / password (email immutable) |
| GET | `/api/activity` | Paginated activity history for the authenticated user |
| GET | `/api/dashboard-overview` | Caller-owned document counts and the five latest uploads |
| GET | `/api/dashboard-data` | Aggregated current-user tasks, today's meetings, and document expiry alerts for the dashboard |
| GET | `/api/dashboard-plan` | Daily, weekly, monthly, and quarterly highlights from the user's active plan; includes today's entries for date-based CSV schedules |
| GET | `/api/tasks` | User-owned tasks, completion progress, weekly totals, and overdue indicators |
| POST | `/api/tasks` | Create a manual task with a due date today or later |
| PATCH | `/api/tasks/{id}` | Update task status; carried-forward tasks require a new future due date |
| POST | `/api/upload` | multipart `file` + `title` |
| GET | `/api/documents?q=&limit=&skip=` | Paged caller-owned documents with the matching total count |
| GET | `/api/documents/{id}` | Caller-owned document metadata and extracted raw text |
| POST | `/api/documents/{id}/summarize` | Retry local summary generation from saved extracted text |
| POST | `/api/documents/{id}/extract-text` | Retry extraction from the caller's stored GridFS file |
| GET | `/api/documents/{id}/download` | Streams from GridFS |
| DELETE | `/api/documents/{id}` | Removes metadata + GridFS blob |

Uploads store `extracted_text` and `extraction_status` (`pending`, `completed`,
`no_text`, `unsupported`, or `failed`) in the document record. Upload now saves
the original to GridFS and creates the MongoDB document record before starting
text extraction in a background task, so slow OCR does not hold the upload
response open. OCR failures are reported in `extraction_error`; they no longer
silently appear as successful empty extraction.
Plain-text `.txt` and `.csv` uploads are decoded as UTF-8 or BOM-marked
UTF-16/UTF-32, with invalid byte sequences reported as extraction failures
instead of corrupted text. CSV rows are extracted as readable text with cells
separated by ` | `; quoted commas and identifier strings (including leading
zeroes) are preserved.
PDF pages without embedded text and supported image uploads use PaddleOCR. Image
OCR enables PaddleOCR's document-orientation classifier, disables document
unwarping and text-line orientation, and runs on CPU with OneDNN disabled.
OpenCV masks detected QR/barcode regions, corrects small image skew, trims safe
blank margins, and creates one denoised, contrast-enhanced image variant;
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

## Local summaries and expiry alerts

After extraction succeeds, the application reads the saved `extracted_text`
from that document record and asks the local Ollama service for a concise,
extractive summary. The default model is `qwen3:0.6b`; no hosted AI service is
used. A single-concurrency background worker queues new extractions and scans
all existing records with saved text on startup, so missing, failed, and stale
summaries are processed without a user action. MongoDB atomically claims each
job to avoid duplicate workers; summaries and deterministic source-derived
fields are saved on the existing document record with a source/prompt-version
hash. Temporary Ollama errors are retried with bounded backoff, failed jobs
are eligible for automatic recovery after application restart, and stale
processing jobs are re-queued after their lease expires. Unreadable OCR or
unverifiable model output does not become a fabricated summary: the application
renders a readable, document-specific summary from source-verified fields and
labels OCR-sensitive identifiers for verification. It does not display noisy
raw OCR lines as a summary. When the local model is unavailable, the same
structured summary is generated directly from saved text. Poor-quality OCR
with no reliable details is marked `needs_review`. A prompt-version change
marks older cached summaries stale so the startup worker can regenerate them.
The dashboard overview API returns a personal overview of the authenticated
user's uploaded plans and documents, including total uploads, completed text
extraction, current processing count, and the five latest uploads. Structured plans with an explicit
`Period:` date range and `YEAR n / QUARTER n` and `YEAR n / MONTH n` sections
also show today's weekday focus and routine, this week's activities and due
dates, the current plan month's focus and review date, and the current quarter's
focus and review milestone. Summaries are derived from that user's saved
extracted text; older `.txt` uploads that were saved before text extraction was
supported can be re-extracted with `POST /api/documents/{id}/extract-text`. CSV
schedule uploads with date, activity, and optional time/category columns are
also parsed into dated dashboard agenda entries; today's activities appear in
the agenda, every valid CSV row is synchronized as a task with saved checkbox
status, and meeting-category rows populate the meetings panel. Plans outside
their date range are identified as inactive rather than shown as today's
schedule. Task tracking generates tasks only from explicit weekday
themes and monthly/quarterly goals and reviews; it does not infer additional
deliverables. Generated tasks are synchronized idempotently for the selected
plan, and users can add manual tasks. Tasks support Pending, In Progress,
Completed, Blocked, Carried Forward, and Skipped statuses. The tracker shows
completion progress, this week's completion, and overdue tasks; carried-forward
tasks require a new due date after today. Paginated activity history is
available through `GET /api/activity`.
The documents API returns saved documents and their source-backed summaries.
Deterministically extracted names,
identifiers, dates, contact details, insurance values, and marks/result lines
are derived from saved text; expiry countdowns are calculated by the backend.
Documents whose text or summary is still processing show their current status
and refresh until generation finishes. Documents without common known type
labels are shown as generic documents rather than being mislabeled “Not
available”; their source-verified summaries still use the saved text.

Expiry dates are not generated by the model. The backend only recognizes
dates adjacent to explicit labels such as “Expiry Date” or “Valid Until” and
calculates the status using the server's local date. Ambiguous numeric dates
(for example `03/04/2027`) are marked “Verification Required”; missing expiry
dates remain “Expiry Date Unavailable” and never create a false expired alert.
The assistant timeline includes expiry status and remaining days alongside
each document whenever an explicit expiry date can be parsed. A document detail
popup shows derived fields, summary, and original extracted text for verification.
These features use optional fields on the existing MongoDB document records;
no separate records or collection migration is needed.

## Data model (`Analysis-AI`)

- **`users`** — `name`, `email` (unique index), `phone`, `password_hash` (bcrypt), `created_at`
- **`documents`** — `user_id` (ObjectId ref), `title`, `filename`, `content_type`, `size`, `gridfs_id`, `extracted_text`, `extraction_status`, `extraction_error`, `uploaded_at`; optional summary cache/status fields are stored on the same record; index `(user_id, uploaded_at desc)`
- **`tasks`** — `user_id`, plan/source identifiers for generated tasks or manual task metadata, `title`, `description`, `task_date`, `due_date`, `expiry_date`, `status`, and timestamps; indexes support per-user generated-task uniqueness and due-date lookup
- **`user_files.files` / `user_files.chunks`** — GridFS bucket holding the bytes

## Per-user isolation

Every document query carries `user_id` as part of the filter itself — read, download and delete all go through
`find_one({"_id": oid, "user_id": user["_id"]})`, so another account's document id simply returns 404 rather than
leaking existence. Verified end-to-end: a second user sees an empty list, and gets 404 on both download and delete
of the first user's document.
