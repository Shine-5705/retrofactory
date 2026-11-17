# Dossier — Stage 2

Self-contained HTTP service. It listens on `0.0.0.0:$PORT` (default `8080`).

## Build

```sh
docker build -t dossier-stage-2 .
```

## Run

```sh
docker run --rm -e PORT=8080 -p 8080:8080 dossier-stage-2
```

The deployment's environment supplies `NIMBLE_API_KEY` and `NIMBLE_BASE_URL`
(and optionally `TAVILY_API_KEY`, `TAVILY_BASE_URL`). Pass them with `-e` or an
env file; never bake credentials into the image.

```sh
docker run --rm -e PORT=8080 -p 8080:8080 \
  -e NIMBLE_API_KEY -e NIMBLE_BASE_URL dossier-stage-2
```

Verify:

```sh
curl -s http://localhost:8080/health
# {"status":"ok"}
```

## Local run without Docker

Requires Python 3.12+.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
PORT=8080 python server.py
```

## Tests / checks

The supplied harness is run from the kickoff checkout, not from this folder:

```sh
cd /workspace/band/ref/sf-buildathon-2026 && . .venv/bin/activate && \
python -m harness run --track dossier --repo <result-repo> --stage 2 --out <fresh-out-dir>
```
