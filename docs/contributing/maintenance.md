# Maintenance

## Checks

`just help` lists every recipe. The gates before calling work done are `just lint` and `just test`. Coverage is `just coverage`.

## Continuous integration

GitHub Actions runs on every push and pull request:

- Linters (Ruff, prek, Prettier).
- Tests with coverage.
- Tests against the lowest supported dependency versions.
- Tests against the latest dependency versions.
- Tests against a matrix of Python, Django, and Wagtail versions.

A nightly job tests against Wagtail's development version.

## Releases

On `main`:

1. Update the version in `pyproject.toml`.
2. Update the [changelog](../../CHANGELOG.md) and the [roadmap](../../ROADMAP.md).
3. Commit, tag, and push the tag. For version `0.1.1`:

   ```sh
   git commit -m "Release v0.1.1"
   git tag -a v0.1.1 -m "Release v0.1.1"
   git push --tags
   ```

4. Create a GitHub release from the tag. CI builds the package and publishes it to PyPI.

Version numbers follow [Semantic Versioning](https://semver.org/). Changelog entries follow [Keep a Changelog](https://keepachangelog.com/).
