# Release Process (Maintainers Only)

## 1. Generate Changelog

Run the following command locally to generate the changelog for the new version (e.g. `0.1.0`):

```bash
uv run git-cliff --tag 0.1.0 --output CHANGELOG.md
```

## 2. Bump Version

Update the `__version__` string in `src/legend/__init__.py`.

## 3. Commit & Push

Commit `CHANGELOG.md` and `src/legend/__init__.py`, then push to main:

```bash
git commit -am "chore: prepare v0.1.0"
git push origin main
```

## 4. Trigger Release

1. Go to the **Actions** tab on GitHub.
2. Select **Release to PyPI**.
3. Click **Run workflow** and enter the version number (e.g. `0.1.0`).
