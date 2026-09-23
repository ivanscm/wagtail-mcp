# Agents

Important context for AI coding agents working on this project.

## Project overview

Wagtail MCP is a Django/Wagtail package. The source code is in `src/wagtail_mcp/`, with tests in `tests/` and a demo Wagtail site in `demo/`.

This project was created from the [cookiecutter-wagtail-package](https://github.com/wagtail/cookiecutter-wagtail-package) template and follows the [Wagtail package maintenance guidelines](https://wagtail.org/package-guidelines/).

## Key commands

```sh
just help        # View all commands
just install     # Install Python and Node.js dependencies
just demo        # Run the demo Wagtail site (migrate + load data + runserver)
just test        # Run tests with pytest
just lint        # Run all linters (Ruff, prek, Prettier, Stylelint)
just format      # Run all formatters (Ruff, Prettier)
just coverage    # Run tests with coverage report
```

## Quality assurance

- Python: Ruff for linting and formatting (`ruff.toml`), prek hooks (`prek.toml`).
- JavaScript/CSS/JSON/YAML: Prettier for formatting (`prettier.config.js`).
- CSS: Stylelint with `@wagtail/stylelint-config-wagtail` (`stylelint.config.mjs`).
- Tests: pytest with pytest-django. Test settings are in `src/wagtail_mcp/test/settings.py`.
- CI: GitHub Actions in `.github/workflows/`.

Always run `just lint` and `just test` before considering work complete.

## Project layout

```
src/wagtail_mcp/           # Package source code
src/wagtail_mcp/test/      # Django test app with settings, URLs
tests/                     # Test modules (pytest)
demo/                      # Demo Wagtail site for development
docs/                      # User guides and reference
docs/contributing/         # Architecture, maintenance, tasks
.github/workflows/         # CI: linting, tests, nightly builds, publishing
```

## Guidelines

- Follow [Semantic Versioning](https://semver.org/) for releases.
- Use [Keep a Changelog](https://keepachangelog.com/) format for CHANGELOG.md.
- CSS should follow the Wagtail stylelint config conventions.
- Refer to [CONTRIBUTING.md](CONTRIBUTING.md). Design notes live in [docs/contributing/architecture.md](docs/contributing/architecture.md).
