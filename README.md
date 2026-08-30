# Hate Speech Blur

Hate Speech Blur is a Chrome extension that detects potentially toxic or hateful text on web pages and blurs matching text. Once enabled, it scans pages automatically and continues watching for dynamically added content.

The project has two parts:

- A Chrome Manifest V3 extension that continuously scans the current page and replaces toxic text nodes with blurred `<span>` elements.
- A local Flask API that vectorizes text and classifies it with the bundled TensorFlow/Keras model.

## How it works

```text
Web page text ──> content.js ──POST /detect──> Flask/TensorFlow API
                                             │
                                             └── {"toxic": true/false}
                                                      │
                                                      └── blur toxic text

Popup action ──> request a page rescan
```

When the extension content script loads, it recursively walks the page body, batches text nodes, and asks the background service worker to classify them through `http://127.0.0.1:5050/detect-batch`. If a response is toxic, the node is replaced with blurred text. A mutation observer handles content added after the initial page load.

## Repository layout

| Path | Purpose |
| --- | --- |
| `manifest.json` | Chrome extension metadata, permissions, popup, and content-script configuration |
| `content.js` | Scans page text and blurs text classified as toxic |
| `popup.html` / `popup.js` | Extension popup and manual page-scan trigger |
| `background.js` | Extension service worker; currently logs installation |
| `backend/app.py` | Flask API, preprocessing, vectorization, and inference |
| `backend/vocabulary.json` | Persisted `TextVectorization` vocabulary used during inference |
| `backend/toxicity.h5` | Pre-trained TensorFlow/Keras toxicity model |

## Requirements

- Google Chrome or another Chromium-based browser with Manifest V3 support
- Python 3.9 or newer
- A TensorFlow installation compatible with your operating system and Python version
- TensorFlow 2.16.1 (the version used by the Docker image for compatibility with the bundled model)

Install the backend dependencies from the included `requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The repository includes the persisted `vocabulary.json` required for inference. Keep it paired with the model that was trained using it.

## Run the backend

### Docker (recommended)

Docker packages the existing model and vocabulary directly:

```bash
docker compose up --build -d
```

Verify the API is healthy:

```bash
curl http://127.0.0.1:5050/health
```

Stop the container with:

```bash
docker compose down
```

The Chrome extension still runs on the host and continues to use `http://127.0.0.1:5050`. The initial Docker build downloads TensorFlow and may take several minutes. The runtime image contains the model and persisted vocabulary.

### Local Python

Start the API from the `backend` directory:

```bash
cd backend
python app.py
```

The server listens on `http://localhost:5050` (and all interfaces) by default. Docker runs it with Gunicorn; local `python app.py` remains convenient for development. On startup it loads the persisted vocabulary and model, avoiding the previous CSV adaptation step.

### Configuration

The backend supports these environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` / `PORT` | `0.0.0.0` / `5050` | Local development server binding |
| `MODEL_PATH` | `backend/toxicity.h5` | Model file location |
| `VOCABULARY_PATH` | `backend/vocabulary.json` | Persisted vocabulary location |
| `TOXICITY_THRESHOLD` | `0.5` | Positive classification threshold |
| `MAX_TEXT_LENGTH` | `10000` | Maximum characters per input |
| `MAX_BATCH_SIZE` | `100` | Maximum texts per batch |
| `CORS_ORIGINS` | disabled | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Backend log level |

The API emits JSON-formatted request logs and returns request duration in the `X-Request-Duration-Ms` response header.

### API endpoints

#### `POST /detect`

Classifies text, splitting it into sentences first. A request looks like:

```bash
curl -X POST http://127.0.0.1:5050/detect \
  -H 'Content-Type: application/json' \
  -d '{"text":"Text to classify"}'
```

Response:

```json
{"toxic": false}
```

#### `POST /detect-batch`

Classifies up to 100 text strings in one request. The extension uses this endpoint to reduce network round trips while scanning a page:

```bash
curl -X POST http://127.0.0.1:5050/detect-batch \
  -H 'Content-Type: application/json' \
  -d '{"texts":["First text","Second text"]}'
```

Response:

```json
{"toxic":[false,true]}
```

The backend also exposes `GET /health`, which returns `{"status":"ok"}` when the service is running.

To verify that the model itself is loaded and able to perform inference, open [`http://127.0.0.1:5050/test`](http://127.0.0.1:5050/test) in a browser or run:

```bash
curl 'http://127.0.0.1:5050/test?text=This%20is%20a%20test%20message'
```

Response:

```json
{"status":"ok","text":"This is a test message","toxic":false,"score":0.01}
```

The `score` is the highest sentence score and the current decision threshold is `0.5`.

You can also send custom JSON with `POST /test` using the same `{"text":"..."}` format as `/detect`.

The model is considered positive when its output is greater than `0.5`.

The OpenAPI definition is available at [`/openapi.yaml`](http://127.0.0.1:5050/openapi.yaml).

## Testing

Run unit/API tests locally with the development dependencies:

```bash
pip install -r requirements-dev.txt
pytest tests/test_app.py -q
```

Run the integration test against the Docker Compose service:

```bash
docker compose up --build -d
pytest tests/integration_test.py -q
docker compose down
```

GitHub Actions runs linting, unit tests, a Docker build, and the Compose integration test on pushes and pull requests.

## Model evaluation

The model requires a separate labeled evaluation CSV with a text column and binary label column:

```bash
cd backend
python evaluate_model.py \
  --data /path/to/labeled_comments.csv \
  --text-column comment_text \
  --label-column toxic \
  --output-dir ../evaluation
```

The command writes `evaluation/metrics.json` containing precision, recall, F1, the confusion matrix, and a classification report. It also writes `evaluation/false_positives.csv` containing non-toxic examples incorrectly classified as toxic.

## Load the extension in Chrome

1. Start the backend and leave it running.
2. Open `chrome://extensions`.
3. Enable **Developer mode**.
4. Select **Load unpacked**.
5. Choose the project root, the directory containing `manifest.json`.
6. Open a page containing text. The extension scans automatically when enabled; opening the popup starts another scan of the active tab.

After changing extension files, return to `chrome://extensions` and click **Reload** for the extension. The browser may restrict content scripts on special pages such as Chrome Web Store pages, settings pages, and other browser-owned URLs.

## Important limitations

- Detection is performed locally through an unauthenticated Flask development server; this setup is intended for local experimentation, not production deployment.
- Large or highly dynamic pages may still be slow because their text must be classified locally. Requests are batched, and a mutation observer handles text added later by single-page applications.
- Blurring replaces the original text node with a span and may affect page styling or behavior.
- The extension currently treats any model score above `0.5` as toxic; there is no user-facing threshold or enable/disable setting.
- The bundled model and vocabulary are large assets and must remain paired.

## Privacy

The extension sends page text to the local service at `127.0.0.1:5050`. No remote service is configured by this project. The background service worker owns the backend request so HTTPS pages can be scanned without page-context mixed-content or CORS issues.

## Development notes

The backend enables permissive CORS with `CORS(app)` so the extension can call the local API. For a deployed or shared service, restrict allowed origins, validate request payloads, run behind a production WSGI server, and avoid binding to all interfaces unless required.

There are currently no automated tests, and dependency versions are not pinned.
