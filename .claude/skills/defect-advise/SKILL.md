# Defect Advise Skill

Generate three-track recommendation advice. Requires fact + review data.

## Usage

```
/defect-advise <defect_id>
```

## Prerequisites

Run `/defect-extract` and `/defect-review` first, or run `/defect-analyze` to get all data.

## Examples

```
/defect-advise OBMC-9062
/defect-advise OBMC-24951
/defect-advise OBMC-17994
```

## What It Does

1. Receives DefectFact + ReviewDecision
2. Retrieves similar historical cases
3. Generates three-track recommendations:
   - **Preferred Path**: Primary action recommendation
   - **Alternative Path**: Secondary option
   - **Escalation Path**: SSR B review / Board escalation

## Output

```json
{
  "defect_id": "OBMC-9062",
  "preferred_path": {
    "track_type": "preferred",
    "summary": "建议申请临时限制",
    "recommendations": [
      {
        "action": "申请90天临时限制",
        "rationale": "Critical severity with customer impact verified",
        "priority": "high",
        "confidence": 0.95
      }
    ]
  },
  "alternative_path": {...},
  "escalation_path": {...}
}
```

## Recommendation Matrix

| Review Decision | Preferred | Alternative | Escalation |
|----------------|-----------|-------------|------------|
| MUST_FIX_BLOCKER | Immediate fix | Workaround | SSR B review |
| TEMP_LIMITATION_ELIGIBLE | Apply limitation | Prepare fix | SSR B approval |
| PERM_LIMITATION_ELIGIBLE | SSR B review | Permanent fix | Board approval |
| PASS | Standard closure | - | - |
| INSUFFICIENT_EVIDENCE | Request evidence | - | - |

## Notes

- Cannot modify Review Agent decisions
- Always shows three tracks, even for PASS
- Recommendations reference specific facts