# Session: Multi-Agent Architecture Design

**Date**: 2026-06-11
**Session**: Design Document Review

## Summary
Reviewed the multi-agent system design document (JIRA Defect Lifecycle Intelligence Platform v4.0) and updated project definition accordingly.

## Key Insights from Design Document

### Architecture Overview
- 4-layer architecture: Raw Sources → Infrastructure Layer → Agent Layer → Knowledge Governance
- 3 specialized agents: Fact Agent, Review Agent, Advisor Agent
- Strict principle hierarchy: Fact → Rules → Human Authority

### Agent Responsibilities
1. **Fact Agent**: Pure fact extraction, no interpretation
2. **Review Agent**: Rule Engine-driven compliance verification
3. **Advisor Agent**: Three-track recommendations, cannot override Review

### Key Innovations
- **Ontology Shadow**: Draft nodes for failed canonicalization
- **Human Feedback Flywheel**: Override events → Correction Patterns
- **Architecture Inheritance**: Cross-platform knowledge transfer
- **Confidence Escalation**: 3-tier confidence with escalation rules

### Design Principles (Critical)
1. Fact Before Interpretation
2. Rules Before Reasoning
3. Human Authority Supremacy
4. Knowledge Must Evolve
5. Ontology Is the Single Source of Truth

## Next Steps
1. Set up MCP server infrastructure
2. Implement each agent sequentially:
   - Fact Agent (foundation layer)
   - Review Agent (rule-based)
   - Advisor Agent (generative layer)
3. Build Knowledge Store
4. Implement Governance workflows

## Open Questions
- Integration with actual JIRA instance?
- Specific TCI/PFI calculation formulas?
- Rule Engine implementation approach?