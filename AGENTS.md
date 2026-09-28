# Superwhisper docs

Public Mintlify docs for Superwhisper. Pages are MDX; navigation and redirects live in `docs.json`.

## Rules

- **Images.** Any file added or changed under `images/` must pass `python3 scripts/optimize-images.py --check` before commit. Load `skills/docs-images/SKILL.md` before touching images. CI enforces this on pull requests.
- **Removed or renamed pages** get a redirect in `docs.json`.
- **No raw screenshots.** Captures with real names, paths, or dictations never enter this repo. Re-shoot with demo data.

## Skills

- `skills/docs-images` — adding and optimising images.
- `skills/superwhisper-optimize` — user-facing skill shipped from the docs; not for editing this repo.
