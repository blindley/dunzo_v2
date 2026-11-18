# dunzo

Spaced-repetition flashcards

## Setup

```bash
uv sync
cp .env.example .env   # skip if .env already exists; edit PORT etc. as needed
```

## Run

```bash
uv run dunzo            # start the server
uv run dunzo --reload   # start with hot reload (development)
```

The port comes from `PORT` in `.env`. Visit `http://127.0.0.1:<PORT>/docs` for the API docs.

## Configuration (`.env`)

| Variable   | Required | Default     | Purpose                                              |
|------------|----------|-------------|------------------------------------------------------|
| `PORT`     | yes      |             | Port the server listens on                           |
| `HOST`     | no       | `127.0.0.1` | Interface to bind                                    |
| `DATA_DIR` | no       | `data`      | Where application data is stored (relative paths are relative to the project root) |
| `MAX_MEDIA_BYTES` | no | `20971520` | Largest media upload, in bytes |
| `TIMEZONE` | no       | system      | IANA time zone used to compute study days            |

## Layout

- `src/dunzo/` – application code: `main.py` CLI entry point, `config.py` settings, and one directory per component (see `ARCHITECTURE.md`)
- tests live inside each component directory (`src/dunzo/<component>/tests/`); run them with `uv run pytest`
- `.hierarchy/` – project-hierarchy documents (briefs, contracts, reports)
- `data/` – application data (gitignored)
- `scratch/` – throwaway experiments (gitignored)
