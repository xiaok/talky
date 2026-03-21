# Talky Cloud Server

FastAPI service that provides remote ASR (Whisper) + LLM (Ollama) processing for Talky clients.

Deploy on a Mac Mini (Apple Silicon) with sufficient memory for both models.

## Requirements

- macOS Apple Silicon (M1/M2/M4)
- Python 3.11+
- Ollama installed with a model pulled (e.g. `ollama pull qwen3.5:4b`)
- Whisper model is auto-downloaded from HuggingFace on first request

## Setup

```bash
cd talky
pip install -r talky-server/requirements.txt
```

Create `talky-server/api_keys.json` (copy from the example and replace keys):

```bash
cp talky-server/api_keys.example.json talky-server/api_keys.json
# edit api_keys.json with your own secret keys
```

```json
{
    "sean": "sk-talky-your-secret-key-001",
    "friend1": "sk-talky-your-secret-key-002"
}
```

## Run

```bash
cd talky
python talky-server/main.py
```

Server starts on `http://0.0.0.0:8000`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TALKY_WHISPER_MODEL` | `mlx-community/whisper-large-v3-mlx` | Whisper model (HF repo or local path) |
| `TALKY_OLLAMA_MODEL` | (auto-detect) | Ollama model name |
| `TALKY_LANGUAGE` | `zh` | Default ASR language |
| `TALKY_PORT` | `8000` | Server port |

## API

### `GET /api/health`

Returns server status and model info.

### `POST /api/process`

Full pipeline: audio → ASR → LLM → cleaned text.

**Headers:**
- `X-API-Key`: required

**Body (multipart/form-data):**
- `audio`: WAV file
- `dictionary`: JSON array of dictionary terms (optional)
- `language`: ASR language code (optional, default `zh`)

**Response:**
```json
{
    "text": "cleaned text",
    "raw": "raw ASR output",
    "asr_ms": 3200,
    "llm_ms": 800,
    "user": "sean"
}
```

## Expose to Internet (Cloudflare Tunnel)

```bash
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create talky-api
cloudflared tunnel route dns talky-api api.talky.yourdomain.com
cloudflared tunnel run --url http://localhost:8000 talky-api
```

## Test

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/process \
  -H "X-API-Key: sk-talky-your-secret-key-001" \
  -F "audio=@test.wav" \
  -F 'dictionary=["词典词条"]' \
  -F "language=zh"
```
