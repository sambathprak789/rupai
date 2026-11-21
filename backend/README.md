# RupAI backend

FastAPI app that runs image jobs on a local ComfyUI (Colab) or a mock engine (no GPU).

## Run locally (mock, no GPU)

Needs Python 3.11 or newer.

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:MOCK = "1"; $env:RUPAI_KEY = "devkey"; $env:OUTPUT_DIR = ".\outputs"
uvicorn app.main:create_app --factory --port 8000
```

If `Activate.ps1` is blocked, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

macOS / Linux:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
MOCK=1 RUPAI_KEY=devkey OUTPUT_DIR=./outputs uvicorn app.main:create_app --factory --port 8000
```

## Test and lint

```bash
python -m pytest -q
ruff check .
ruff format --check .
```

## Environment variables

| Name | Default | Use |
|---|---|---|
| `RUPAI_KEY` | random (printed nowhere) | Access key. The notebook always sets it. |
| `COMFY_URL` | `http://127.0.0.1:8188` | Local ComfyUI |
| `OUTPUT_DIR` | `/content/outputs` | Where images are stored |
| `MOCK` | `0` | `1` = placeholder images, no GPU |
| `MODEL_QUANT` | `Q5_K_M` | Picks `qwen-image-2.1-step90000-<quant>.gguf` |
| `TEXT_ENCODER_FILE` | `qwen3vl_8b_int8_convrot.safetensors` | Text encoder file in ComfyUI |
| `STATIC_DIR` | unset | Built frontend to serve at `/` |
| `COOKIE_SECURE` | `1` | Set `0` only for plain-http testing with curl |
| `WARMUP` | `0` | `1` = load the models with a hidden 1-step job at startup (the notebook sets it) |

## API

All routes except `POST /api/auth` need the session cookie or `Authorization: Bearer <key>`.

| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth` | `{ "key": "..." }` -> 204 + `rupai_session` cookie; 401 wrong key; 429 after 10 wrong keys/min |
| GET | `/api/health` | ComfyUI status, VRAM, RAM, `busy` |
| POST | `/api/jobs` | 201 Job; 409 busy; 422 invalid; 404 unknown `sourceImageId` |
| GET | `/api/jobs` | Newest first |
| GET | `/api/jobs/{id}` | One job with its images |
| POST | `/api/jobs/{id}/cancel` | Stops the running job, keeps finished images; 409 if not running |
| GET | `/images/{filename}` | PNG |
| WS | `/api/ws` | Events: `status` (warm-up), `job` (state + countdown), `preview` (JPEG data URL after each step). Closes with 4401 / 4429 on bad auth |
