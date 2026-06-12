# Defect Review Skill

Review defect compliance using the rule engine. Requires fact data from `/defect-extract`.

## Usage

```
/defect-review <defect_id>
```

## Prerequisites

Run `/defect-extract` first to get fact data.

## Examples

```
/defect-review OBMC-9062
/defect-review OBMC-24951
/defect-review OBMC-17994
```

## What It Does

1. Receives DefectFact from Fact Agent (or fetches it)
2. Evaluates against rules.json:
   - `limitation_rules` - Limitation eligibility
   - `closure_rules` - Closure validity
   - Evidence validation
3. Returns ReviewDecision JSON

## Output

```json
{
  "defect_id": "OBMC-9062",
  "decision_type": "TEMP_LIMITATION_ELIGIBLE",
  "confidence": 0.87,
  "confidence_level": "medium",
  "reasoning": "Defect meets criteria for temporary limitation",
  "triggered_rules": ["LIM-002"]
}
```

## Decision Types

| Decision | Meaning |
|----------|---------|
| MUST_FIX_BLOCKER | Critical + >4 weeks → must fix |
| TEMP_LIMITATION_ELIGIBLE | Eligible for 90-day limitation |
| PERM_LIMITATION_ELIGIBLE | Eligible for permanent limitation |
| CRITICAL_SSRB_REVIEW | Requires SSR B review |
| INVALID_CLOSURE_REQUEST | Cannot close in current status |
| INSUFFICIENT_EVIDENCE | Missing required evidence |
| PASS | Compliant, no issues |

## Notes

- Uses rule engine only, no LLM judgment
- Human reviewer can override any decision