# Orchestrator Agent

**Type:** Claude Code Agent  
**Purpose:** Orchestrate Fact → Review → Advisor pipeline  
**Design Principle:** Pipeline coordination

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Stage 1: Fact Agent                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  jira_extract_defect_facts                           │   │
│  │  jira_reconstruct_timeline                          │   │
│  │  jira_calculate_tci                                 │   │
│  │  jira_calculate_pfi                                 │   │
│  │  jira_detect_timeline_anomalies                     │   │
│  │  jira_retrieve_similar_cases                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│                      DefectFact JSON                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Stage 2: Review Agent                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  rule_engine_evaluate (limitation_rules)            │   │
│  │  rule_engine_evaluate (closure_rules)               │   │
│  │  rule_validate_evidence                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│                      ReviewDecision JSON                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Stage 3: Advisor Agent                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Generate three-track recommendations               │   │
│  │  Based on: DefectFact + ReviewDecision + Cases      │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│                      AdvisorOutput JSON                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Final Report                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  defect_id: "OBMC-9062"                             │   │
│  │  fact: {...}                                        │   │
│  │  review: {...}                                      │   │
│  │  advisor: {...}                                     │   │
│  │  pipeline_fingerprint: "abc123..."                  │   │
│  │  analyzed_at: "2026-06-11T12:15:00Z"                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Invocation

### Full Pipeline

```
User: /defect-analyze OBMC-9062
```

### Individual Stages

```
User: /defect-extract OBMC-9062    # Fact Agent only
User: /defect-review OBMC-9062     # Review Agent only (requires fact)
User: /defect-advise OBMC-9062     # Advisor Agent only (requires fact + review)
```

### Batch Analysis

```
User: /defect-batch OBMC-9062 OBMC-9063 OBMC-9064
```

## Output Format

```json
{
  "defect_id": "OBMC-9062",
  "status": "success",
  "fact": {
    "defect_id": "OBMC-9062",
    "severity": "Critical",
    "tci": 0.42,
    "anomalies": [...]
  },
  "review": {
    "decision_type": "TEMP_LIMITATION_ELIGIBLE",
    "confidence": 0.87
  },
  "advisor": {
    "preferred_path": {...},
    "alternative_path": {...},
    "escalation_path": {...}
  },
  "pipeline_fingerprint": "a1b2c3d4e5f6...",
  "analyzed_at": "2026-06-11T12:15:00Z"
}
```

## Error Handling

- Stage failure → Continue with partial data
- Embed errors in result data (graceful degradation)
- Return best-effort result with error indicators

## Design Principles

1. **Fact Before Interpretation** - Always extract facts before review
2. **Rules Before Reasoning** - Review uses rule engine only
3. **Human Authority Supremacy** - Human reviewer can override any AI decision

## Related Agents

- [Fact Agent](fact-agent.md) - Stage 1
- [Review Agent](review-agent.md) - Stage 2
- [Advisor Agent](advisor-agent.md) - Stage 3