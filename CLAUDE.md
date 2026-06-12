# Defect Lifecycle Intelligence - CLAUDE.md

**Project:** Defect Lifecycle Intelligence Agent  
**Architecture:** Multi-Agent + MCP + Skills  
**Design Principles:** Fact Before Interpretation, Rules Before Reasoning, Human Authority Supremacy

## Quick Start

```
/defect-analyze OBMC-9062
```

## Available Skills

| Command | Description |
|---------|-------------|
| `/defect-extract` | Extract defect facts |
| `/defect-review` | Review compliance |
| `/defect-advise` | Generate recommendations |
| `/defect-analyze` | Full pipeline (Fact → Review → Advisor) |
| `/defect-batch` | Batch analyze multiple defects |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ Extract │  │ Review  │  │ Advise  │  │ Analyze │       │
│  │ Skill   │  │ Skill   │  │ Skill   │  │ Skill   │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
│       │             │             │             │          │
│       ▼             ▼             ▼             ▼          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ Fact    │  │ Review  │  │ Advisor │  │Orchestr.│       │
│  │ Agent   │  │ Agent   │  │ Agent   │  │ Agent   │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
│       │             │             │             │          │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server Layer                          │
│  defect_fact_tool  timeline_tool  tci_pfi_tool  knowledge  │
└─────────────────────────────────────────────────────────────┘
```

## Agent Definitions

- [fact-agent.md](.claude/agents/fact-agent.md) - Fact extraction
- [review-agent.md](.claude/agents/review-agent.md) - Compliance review
- [advisor-agent.md](.claude/agents/advisor-agent.md) - Recommendations
- [orchestrator-agent.md](.claude/agents/orchestrator-agent.md) - Pipeline

## Skills

- [defect-extract.md](.claude/skills/defect-extract.md)
- [defect-review.md](.claude/skills/defect-review.md)
- [defect-advise.md](.claude/skills/defect-advise.md)
- [defect-analyze.md](.claude/skills/defect-analyze.md)
- [defect-batch.md](.claude/skills/defect-batch.md)

## Design Principles

### 1. Fact Before Interpretation
- Always extract facts before judgment
- Facts are objective, interpretations are subjective
- Agent cannot make decisions without facts

### 2. Rules Before Reasoning
- Compliance decisions come from rule engine
- Rules defined in `mcp-server/config/rules.json`
- LLM only for explanation, not decision

### 3. Human Authority Supremacy
- Human reviewer is final authority
- AI recommendations can be overridden
- Override events feed back to improve rules

## MCP Tools

| Tool | Description |
|------|-------------|
| `jira_extract_defect_facts` | Extract basic defect info |
| `jira_reconstruct_timeline` | Reconstruct timeline |
| `jira_calculate_tci` | Calculate Time-to-Close Index |
| `jira_calculate_pfi` | Calculate Priority Factor Index |
| `jira_detect_timeline_anomalies` | Detect timeline anomalies |
| `jira_retrieve_similar_cases` | Retrieve similar cases |

## Output Formats

### DefectFact (from Fact Agent)
```json
{
  "defect_id": "OBMC-9062",
  "severity": "Critical",
  "tci": 0.42,
  "pfi": 0.68,
  "anomalies": [...],
  "evidence": {...}
}
```

### ReviewDecision (from Review Agent)
```json
{
  "decision_type": "TEMP_LIMITATION_ELIGIBLE",
  "confidence": 0.87,
  "triggered_rules": ["LIM-002"]
}
```

### AdvisorOutput (from Advisor Agent)
```json
{
  "preferred_path": {...},
  "alternative_path": {...},
  "escalation_path": {...}
}
```

## Decision Types

| Decision | Description |
|----------|-------------|
| MUST_FIX_BLOCKER | Critical + > 4 weeks → must fix |
| TEMP_LIMITATION_ELIGIBLE | Eligible for 90-day limitation |
| PERM_LIMITATION_ELIGIBLE | Eligible for permanent limitation |
| CRITICAL_SSRB_REVIEW | Requires SSR B review |
| INVALID_CLOSURE_REQUEST | Invalid closure request |
| INSUFFICIENT_EVIDENCE | Missing required evidence |
| PASS | Compliant |

## Configuration

- Rules: `mcp-server/config/rules.json`
- Knowledge Store: `knowledge_store/`
- MCP Server: `mcp-server/server.py`

## Testing

```bash
pytest tests/agents/ -v
pytest tests/agents/test_fact_agent.py -v
pytest tests/agents/test_review_agent.py -v
pytest tests/agents/test_advisor_agent.py -v
```