# Project identity and renaming an existing checkout

The public name is **Raster Processes API**; the repository and local directory
name is **`raster-processes`**. The subtitle is:

> An OGC API – Processes service for raster operations, powered by pygeoapi and rasterio/GDAL.

Python imports remain `geo_processes`, the Python distribution remains
`geo-processes`, and process IDs and `GEO_*` environment settings are unchanged.
Docker images are `raster-processes:0.1.0` and `raster-processes-dev:0.1.0`.
MIT notices and the original project's attribution are preserved.

## Rename on GitHub

1. Open the existing repository's **Settings → General**.
2. Change **Repository name** from `terrio-processes` to `raster-processes`
   and click **Rename**. Rename the existing repository; do not create a new one.
3. On its main page, edit **About** using the gear icon and set the description
   to the subtitle above.
4. After the rename succeeds, update this checkout's remote:

```bash
git remote set-url origin https://github.com/Gouwe-Gozer/raster-processes.git
git remote -v
```

GitHub preserves repository information and redirects ordinary old repository
URLs and Git operations. See [GitHub's rename instructions](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).
Service-defined error responses now link to the new repository's
[exception catalogue](errors.md).

## Rename the local directory

Close the IDE workspace, then use a separate terminal:

```bash
cd ~/projects
mv -- terrio-processes raster-processes
cd raster-processes
uv venv --clear .venv
uv sync --locked --all-groups
```

The virtual environment is regenerated because installed scripts can contain
the old absolute directory path. Reopen `~/projects/raster-processes` in the
IDE and update saved workspace paths or terminal bookmarks. Source files, Git
history and uncommitted work move with the directory.
If using the pre-commit hook, reinstall it with `uv run pre-commit install` so
it uses the recreated environment.

## Docker after renaming

The existing test installation uses Compose project `terrio-processes`.
Stop it before starting the renamed stack on the same port. From the renamed
checkout:

```bash
docker compose --project-name terrio-processes --file compose.release.yml down
docker compose --project-name raster-processes --file compose.release.yml up --build --detach
```

This starts with a new `raster-processes_results` volume; the old test volume
is left in place. Keep public URL, port and other desired environment overrides;
remove or update any old `COMPOSE_PROJECT_NAME` in your local `.env`.
When the directory is named `raster-processes`, that is also the default Compose
project name, so subsequent commands can omit `--project-name`.

If you want to keep using the old test results, use
`--project-name terrio-processes` for the new image instead. Do not add
`--volumes` to `down` when retaining those results.

The repository rename, remote update and local directory move are operator
steps; editing the project's branding does not perform them automatically.
