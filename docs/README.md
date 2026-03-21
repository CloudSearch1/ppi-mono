# PPI-Mono Documentation

## Design Documents

All design documents for the Python rewrite are located in [`pi-mono-rewrite/`](pi-mono-rewrite/).

### Document Categories

| Category | Number Range | Description |
|----------|--------------|-------------|
| Architecture Design | 01-09 | Core architecture and design analysis |
| Core Flow & Protocols | 10-16 | Call flows, protocols, and data classes |
| Module Design | 17-25 | Individual module designs and interfaces |
| Extensions & Persistence | 26-29 | Providers, templates, and schemas |
| Detailed Design | 30-36 | In-depth design specifications |

### Quick Links

**Getting Started:**
- [Design Document Index](pi-mono-rewrite/README.md) - Complete categorized list of all design documents
- [AI Agent Design](pi-mono-rewrite/01-ai-agent-design.md) - Core AI agent architecture
- [Python Rewrite Plan](pi-mono-rewrite/03-python-rewrite-plan.md) - Rewrite strategy

**Architecture:**
- [Coding Agent Architecture](pi-mono-rewrite/02-coding-agent-architecture.md)
- [Agent & Coding Agent Design](pi-mono-rewrite/06-agent-coding-agent-design.md)
- [Package Layout](pi-mono-rewrite/34-python-package-layout.md)

**Implementation:**
- [Interface Spec & Migration](pi-mono-rewrite/33-interface-spec-and-migration.md)
- [Python Package Structure](pi-mono-rewrite/09-python-package-structure.md)
- [Implementation Task Breakdown](pi-mono-rewrite/16-python-implementation-task-breakdown.md)

**Module-Specific:**
- [mom/pods Design](pi-mono-rewrite/36-mom-pods-design.md)
- [Web UI Design](pi-mono-rewrite/32-mom-pods-web-ui-design.md)
- [JSON Schemas](pi-mono-rewrite/29-coding-agent-jsonschema.md)

## Directory Structure

```
docs/
├── README.md                  # This file
└── pi-mono-rewrite/
    ├── README.md              # Design document index
    ├── examples/              # Example configurations
    │   └── provider-registry.json
    └── *.md                   # Design documents (36 total)
```

## Document Naming Convention

Documents are numbered sequentially by category:
- `01-09`: Architecture and planning
- `10-16`: Core implementation details
- `17-25`: Module designs
- `26-29`: Extensions and persistence
- `30-36`: Detailed specifications

## Contributing

When adding new documents:
1. Use the next available number in the appropriate category
2. Follow the naming pattern: `NN-descriptive-name.md`
3. Update the index in `pi-mono-rewrite/README.md`
4. Add cross-references to related documents where appropriate