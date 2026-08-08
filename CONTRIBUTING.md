# Contributing

## Getting started

```bash
make setup     # uv sync, including dev tools
make check     # lint + tests, the same thing CI runs
```

## Ground rules

- **Tests never hit the network.** Source modules take an `httpx.Client`, so tests inject an
  `httpx.MockTransport` with a recorded payload. If you add a data source, follow that shape.
- **Open data only.** Nothing in this repo may require an API key or an account. If a dataset
  needs one, look for the PDOK equivalent first.
- **Millimetres for hand measurements, metres for coordinates.** Control files are in
  millimetres because that is how a laser distance meter reads. Geodata is in RD metres.
  Conversions live at the edges, never in the middle.
- **The control measurement outranks the cloud.** Any feature that quietly reverses that is a
  bug, however convenient it looks.
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

## Adding a data source

1. New module under `src/scan2bim/sources/`, taking an `httpx.Client` as a keyword argument.
2. Raise `SourceError` for anything the service returns that you cannot use, including the
   fun case of an error page served with HTTP 200.
3. Add a fixture with a real recorded payload in `tests/conftest.py`.
4. Document the endpoint, its quirks and its licence in `docs/data-sources.md`.
