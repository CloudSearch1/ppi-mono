# Python Reimplementation Workspace

This directory contains the Python skeleton for the `pi-mono` rewrite.

The layout mirrors the design documents in `docs/pi-mono-rewrite/` and keeps the
core boundary explicit:

- `ppi_ai`: provider and message protocol layer
- `ppi_agent_core`: agent loop and tool orchestration
- `ppi_coding_agent`: session, settings, resources, extensions, CLI modes
- `ppi_tui`: terminal UI primitives
- `ppi_web`: browser/runtime data layer
- `ppi_mom`: Slack workspace automation
- `ppi_pods`: GPU pod and vLLM orchestration

This is a minimal, interface-first scaffold. The modules intentionally expose
types and protocols before implementation details.

## Install

```bash
pip install -e python
```

## Next Steps

1. Fill in provider adapters in `ppi_ai`
2. Implement the agent loop in `ppi_agent_core`
3. Wire the coding-agent runtime and session tree in `ppi_coding_agent`

## Package Bootstrap Draft

The first executable skeleton is intentionally small:

```text
python/
├── pyproject.toml
├── README.md
└── src/
    ├── ppi_ai/
    ├── ppi_agent_core/
    ├── ppi_coding_agent/
    ├── ppi_mom/
    ├── ppi_pods/
    ├── ppi_tui/
    └── ppi_web/
```

Current bootstrap rules:

- `pimono` is the only wired console script for now, and it points to `ppi_coding_agent.cli.main:main`
- top-level packages are split by product boundary instead of by technical layer
- protocol types live in `ppi_ai`, while orchestration lives in `ppi_agent_core`
- `ppi_coding_agent` owns the rewrite entry path, session tree, settings, resources, and extension runtime

This keeps the first installable artifact simple while leaving room for later CLI subcommands and runtime entry points.
