# Memory Index

## Project Files
- [project-definition.md](project-definition.md) — Complete multi-agent architecture design (v4.0)
- [user-context.md](user-context.md) — User information and preferences
- [agent-skill-architecture.md](agent-skill-architecture.md) — Agent vs Skill 架构理解

## Session History
- [2026-06-11-initialization.md](sessions/2026-06-11-initialization.md) — GitHub repository setup
- [2026-06-11-design-review.md](sessions/2026-06-11-design-review.md) — Design document review and architecture understanding
- [2026-06-11-mcp-implementation.md](sessions/2026-06-11-mcp-implementation.md) — MCP layer implementation

## Architecture Reference
- **Design Document**: `JIRA Defect Lifecycle Intelligence Platform.pdf`
- **Version**: 4.0 (Knowledge Governance)
- [limitation-data-integration.md](limitation-data-integration.md) — Limitation data extraction integration
- [limitation-management-principles.md](limitation-management-principles.md) — Limitation tracking rules

## Claude Code Agent + Skill + MCP Architecture

New architecture using Claude Code native Agent + Skill + MCP:

- [.claude/agents/](.claude/agents/) — Agent definitions
  - `fact-agent.md` — Fact extraction agent
  - `review-agent.md` — Compliance review agent
  - `advisor-agent.md` — Recommendation agent
  - `orchestrator-agent.md` — Pipeline orchestrator
- [.claude/skills/](.claude/skills/) — Skill definitions
  - `defect-extract.md` — /defect-extract skill
  - `defect-review.md` — /defect-review skill
  - `defect-advise.md` — /defect-advise skill
  - `defect-analyze.md` — /defect-analyze skill
  - `defect-batch.md` — /defect-batch skill
- [.claude/mcp/](.claude/mcp/) — MCP configuration
- [CLAUDE.md](../CLAUDE.md) — Root configuration file