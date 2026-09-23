# Contributing guidelines

Thank you for your interest in this project. Bug reports and changes that fit
the [roadmap](ROADMAP.md) are welcome.

## Installation

The repo includes a demo Wagtail site for working on the package. Requirements:
[`uv`](https://github.com/astral-sh/uv), [`just`](https://github.com/casey/just),
[`prek`](https://prek.j178.dev/).

```sh
git clone git+https://github.com/org-name-or-username/wagtail-mcp
cd wagtail-mcp
just install
just demo
```

`just help` lists the other recipes. Run `just lint` and `just test` before
considering work complete.

## Further reading

- [Tasks](docs/contributing/tasks.md) — tests, adding a tool, agent-behavior evals, review.
- [Architecture](docs/contributing/architecture.md) — dispatch, transport, the admin agent.
- [Maintenance](docs/contributing/maintenance.md) — CI and releases.
- [API feedback](docs/contributing/api-feedback.md) — notes for the Wagtail v3 API.
