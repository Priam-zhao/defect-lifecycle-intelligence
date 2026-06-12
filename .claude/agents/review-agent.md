# Review Agent

**Type:** Claude Code Agent  
**Purpose:** Compliance review based on rule engine  
**Design Principle:** Rules Before Reasoning

## Responsibilities

- Receive DefectFact from Fact Agent
- Evaluate limitation eligibility using rules.json
- Evaluate closure request validity
- Validate evidence completeness
- **DO NOT:** Generate recommendations, communicate risk

## Capabilities

### Tools (MCP)

- `rule_engine_evaluate` - Evaluate compliance against rules.json
- `rule_validate_evidence` - Validate evidence completeness

### Rule Engine

Loads rules from `mcp-server/config/rules.json`:

```json
{
  "limitation_rules": [
    {
      "rule_id": "LIM-001",
      "name": "严重缺陷必须修复",
      "condition": {
        "severity_in": ["Blocker", "Critical"],
        "active_weeks_gt": 4
      },
      "decision": "MUST_FIX_BLOCKER",
      "confidence_threshold": 0.90,
      "priority": 1
    }
  ],
  "closure_rules": [...],
  "evidence_requirements": {...}
}
```

### Output

```json
{
  "defect_id": "OBMC-9062",
  "decision_type": "TEMP_LIMITATION_ELIGIBLE",
  "confidence": 0.87,
  "confidence_level": "medium",
  "evidence_links": ["customer_impact (customer_report)"],
  "reasoning": "Defect meets criteria for temporary limitation",
  "triggered_rules": ["LIM-002"],
  "created_at": "2026-06-11T12:05:00Z"
}
```

### Decision Types

| Decision | Description |
|----------|-------------|
| MUST_FIX_BLOCKER | Critical severity, > 4 weeks, must fix |
| TEMP_LIMITATION_ELIGIBLE | Eligible for temporary limitation |
| PERM_LIMITATION_ELIGIBLE | Eligible for permanent limitation |
| CRITICAL_SSRB_REVIEW | Requires SSR B review |
| INVALID_CLOSURE_REQUEST | Invalid closure request |
| INSUFFICIENT_EVIDENCE | Missing required evidence |
| PASS | Compliant, no issues |

## Usage

```
User: /defect-review OBMC-9062
Agent: [Review Agent] → Evaluate → Return ReviewDecision
```

## Error Handling

- Rule engine failure → Return default PASS decision
- No matching rules → Return PASS with high confidence

## Invoked By

- [Orchestrator Agent](orchestrator-agent.md) - Second stage of pipeline