# SAFEAI Backend

SAFEAI Backend is a Django + Django REST Framework service that exposes a unified API for interacting with a Gemini model from multiple channels:

- Chat over HTTP (web frontend)
- File-based chat (PDF / Word / text upload)
- Telegram bot
- External API clients via API keys

It also provides a Swagger/OpenAPI UI for exploring and testing the API.

---

## Tech Stack

- **Language**: Python 3.11+
- **Web Framework**: Django 5
- **API Framework**: Django REST Framework
- **Database**: PostgreSQL
- **Docs / Schema**: drf-spectacular (OpenAPI + Swagger UI)
- **CORS**: django-cors-headers
- **LLM**: Google Gemini via HTTP API

---

## Project layout

At the root of this backend repo:

- `manage.py` – Django management script
- `requirements.txt` – Python dependencies
- `safeAi/` – Django project + app package
  - `safeAi/safeAi/` – project settings and URLs
  - `safeAi/chat/` – main app with models, views, serializers, and integrations
- `.env` – environment variables (not tracked in git)
- `build.sh` – optional build/deploy helper script

---

## Setup

### 1. Create and activate a virtualenv

From the backend root (this directory):

```bash
python -m venv venv
venv\Scripts\activate  # on Windows
# or on macOS/Linux: source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the backend root (if it does not exist yet). The project already loads it from `BASE_DIR.parent / ".env"`.

Typical variables:

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=true
ALLOWED_HOSTS=*

# Database (PostgreSQL)
DB_NAME=your_db_name
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Gemini / Google Generative Language
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_NAME=gemini-2.5-flash
GEMINI_API_BASE=https://generativelanguage.googleapis.com/v1beta

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# (Optional) WhatsApp/Twilio (not wired yet, but reserved for future use)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+123456789
```

Adjust values according to your environment.

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Run the development server

From the `safeAi` project directory or repo root:

```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/` by default.

---

## Core concepts

### Models

Defined in `safeAi/chat/models.py`:

- **ChatUser** – anonymous web chat user tracked by Django session ID.
- **TelegramUser** – Telegram users identified by their Telegram chat ID.
- **APIUser** – external clients that use an API key to call the `/api/message/` endpoint.
- **MessageLog** – centralized log of all requests and responses across channels:
  - `source`: `"chat"`, `"telegram"`, or `"api"`
  - `chat_user` / `telegram_user` / `api_user`: optional foreign keys to the source user
  - `request_text`: text sent to Gemini
  - `response_text`: text returned from Gemini or error messages
  - `created_at`: timestamp

These logs are exposed via the `api/all-data/` endpoint.

---

## API Endpoints

All endpoints are defined under `safeAi/chat/views.py` and routed from `safeAi/chat/urls.py`.

### 1. Chat over HTTP

**POST `/chat/`**

JSON-based chat endpoint.

- Request body (JSON):

```json
{
  "message": "Hello, world"
}
```

- Success response (HTTP 200):

```json
{
  "response": "<Gemini reply text>"
}
```

- Validation errors (HTTP 400):

```json
{
  "message": ["This field is required."]
}
```

- Gemini errors (HTTP 502):

```json
{
  "detail": "Gemini API request timed out"
}
```

Each call is logged to `MessageLog` with `source="chat"`.

---

### 2. Chat with file upload (PDF / Word / text)

**POST `/chat/upload/`**

Multipart endpoint that accepts an optional message and a file. The backend extracts text from the file and sends the combined text to Gemini.

- Content-Type: `multipart/form-data`
- Fields:
  - `message` (optional, string)
  - `file` (required, file – `.pdf`, `.doc`, `.docx`, or text)

Example (conceptual curl):

```bash
curl -X POST http://127.0.0.1:8000/chat/upload/ \
  -F "message=Summarize this" \
  -F "file=@/path/to/file.pdf"
```

Behavior:

1. Extracts text from the uploaded file:
   - PDF via **PyPDF2**
   - DOC / DOCX via **python-docx**
   - Fallback: treats other files as UTF-8 text
2. Combines `message` (if present) and extracted text into a single prompt.
3. Calls `generate_gemini_response()`.
4. Logs the interaction in `MessageLog` with `source="chat"`.

- Success response (HTTP 200):

```json
{
  "response": "<Gemini reply based on combined text>"
}
```

- File/validation errors (HTTP 400):

```json
{
  "file": ["This field is required."]
}
```

- Gemini errors (HTTP 502):

```json
{
  "detail": "Gemini API request timed out"
}
```

---

### 3. Telegram webhook

**POST `/telegram/webhook/`**

Endpoint for Telegram Bot API updates. It expects the standard Telegram update payload for text messages.

- Extracts:
  - Chat ID and username
  - Incoming text message
- Calls Gemini and logs to `MessageLog` with `source="telegram"`.
- Sends the reply back to the user using `TELEGRAM_BOT_TOKEN`.

To use it:

1. Set your bot webhook in Telegram:

   ```bash
   curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -d "url=https://your-domain.com/telegram/webhook/"
   ```

2. Ensure your server is reachable from the internet.

---

### 4. API key management and API chat

These endpoints allow external systems to call Gemini using an API key.

#### 4.1 Generate API key

**POST `/api/generate-key/`**

- Request body (JSON):

```json
{
  "company_name": "Acme Corp"
}
```

- Response (HTTP 200):

```json
{
  "api_key": "<generated-uuid>"
}
```

An `APIUser` is created and associated with the generated `api_key`.

#### 4.2 Send message using API key

**POST `/api/message/`**

- Request body (JSON):

```json
{
  "api_key": "<your-api-key>",
  "message": "Question from external system"
}
```

- Success response (HTTP 200):

```json
{
  "response": "<Gemini reply>",
  "api_user_id": 1
}
```

- Invalid API key (HTTP 401):

```json
{
  "detail": "Invalid API key"
}
```

- Gemini errors (HTTP 502):

```json
{
  "detail": "Gemini API request timed out"
}
```

All API interactions are logged to `MessageLog` with `source="api"`.

---

### 5. All data (for debugging/analytics)

**GET `/api/all-data/`**

Returns serialized data for all users and message logs:

```json
{
  "chat_users": [...],
  "telegram_users": [...],
  "api_users": [...],
  "message_logs": [...]
}
```

Intended mainly for debugging, admin views, and analytics.

---

## OpenAPI / Swagger documentation

Swagger UI and OpenAPI schema are provided by **drf-spectacular**.

- **OpenAPI schema (JSON)**: `GET /api/schema/`
- **Swagger UI**: `GET /api/docs/`

After running the dev server, open:

- `http://127.0.0.1:8000/api/docs/` in a browser to explore and test endpoints interactively.

---

## Gemini integration

Located in `safeAi/chat/gemini_service.py`.

- Reads API configuration from environment variables:
  - `GEMINI_API_KEY`
  - `GEMINI_MODEL_NAME`
  - `GEMINI_API_BASE`
- Uses `requests` to call Google7s Generative Language API.
- Wraps HTTP and response format issues in a custom `GeminiClientError`, which views translate into clean JSON error responses.

Error handling:

- Network issues / timeouts:

  ```text
  GeminiClientError("Gemini API request timed out")
  GeminiClientError("Gemini API request failed: ...")
  ```

- Non-200 responses:

  ```text
  GeminiClientError("Gemini API error <status>: <body excerpt>")
  ```

- Unexpected JSON shape:

  ```text
  GeminiClientError("Unexpected Gemini response format: ...")
  ```

Views catch `GeminiClientError` and respond with `HTTP 502` + `{ "detail": "..." }` while also logging the error to `MessageLog`.

---

## Logging and observability

- Every user interaction (chat, upload, Telegram, API) is logged into `MessageLog`.
- The `/api/all-data/` endpoint exposes these logs for inspection.
- You can extend this with additional analytics or admin pages as needed.

---

## Notes and future improvements

- **WhatsApp integration**: can be added later using Twilio or the Meta WhatsApp Cloud API by following the same pattern as `telegram_webhook_view` (new model for WhatsApp users, a webhook endpoint, and a small client wrapper).
- **Authentication/permissions**: current endpoints are open except for API key auth on `/api/message/`. For production, you may want to restrict access further (e.g., admin-only views for `/api/all-data/`).
- **Rate limiting**: should be added in front of Gemini calls for cost and abuse control.
- **File size limits**: Django settings and your reverse proxy should enforce reasonable upload limits for `/chat/upload/`.
