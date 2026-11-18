### `dunzo.app` (contract v1; owner: agent `l`)
```python
def create_app(settings: Settings | None = None) -> FastAPI   # no I/O at construction; startup work happens in the lifespan
app: FastAPI                                                  # = create_app(); this is what `dunzo.main` serves ("dunzo.app:app")
```
Lifespan: open the database, `migrate(conn, [content.MIGRATIONS, progress.MIGRATIONS])` (content first), run `Content.collect_garbage` once at startup and then daily in a background task. Mounts `manage.router` and `review.router`. Provides the middleware, error handling and routes listed in the web conventions (CSRF token in `request.state.csrf_token`, Host-header check, error pages, `/`, `/healthz`).
