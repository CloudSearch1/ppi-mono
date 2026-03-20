# PPI-Mono

Python reimplementation workspace for pi-mono.

## Project Structure

```
ppi-mono/
├── .github/
│   └── workflows/
│       └── ci.yml          # CI pipeline configuration
├── docs/
│   └── pi-mono-rewrite/    # Design documents and specifications
├── python/
│   ├── src/
│   │   ├── ppi_ai/              # Provider and message protocol layer
│   │   ├── ppi_agent_core/      # Agent loop and tool orchestration
│   │   ├── ppi_coding_agent/    # Session, settings, resources, CLI modes
│   │   ├── ppi_tui/             # Terminal UI primitives
│   │   ├── ppi_web/             # Browser/runtime data layer
│   │   ├── ppi_mom/             # Slack workspace automation
│   │   └── ppi_pods/            # GPU pod and vLLM orchestration
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
└── .gitignore
```

## Packages

| Package | Description |
|---------|-------------|
| `ppi_ai` | AI provider adapters, message protocols, and streaming |
| `ppi_agent_core` | Agent loop, tool orchestration, and event handling |
| `ppi_coding_agent` | Coding agent runtime, sessions, settings, and CLI |
| `ppi_tui` | Terminal UI components and rendering |
| `ppi_web` | Web interface and data persistence |
| `ppi_mom` | Slack workspace automation and scheduling |
| `ppi_pods` | GPU pod management and vLLM orchestration |

## Quick Start

```bash
# Install the package
pip install -e python

# Run the CLI
pimono

# Install with all extras
pip install -e "python[dev,tui,web,mom,pods]"
```

## Development

```bash
# Install dev dependencies
pip install -e "python[dev]"

# Run linting
ruff check python/
ruff format python/

# Run type checking
mypy python/src/

# Run tests
pytest python/tests/
```

## Documentation

Design documents and specifications are available in [`docs/pi-mono-rewrite/`](docs/pi-mono-rewrite/).

## License

MIT