# Defect Analyze Skill

Run the complete Fact → Review → Advisor pipeline.

## Usage

```
/defect-analyze <defect_id>
/defect-analyze <defect_id> --full
```

## Examples

```
/defect-analyze OBMC-9062
/defect-analyze OBMC-9062 --full
/defect-analyze OBMC-24951 OBMC-23850 OBMC-17994
```

## What It Does

Runs the complete three-stage pipeline:

### Stage 1: Fact Agent
- Extract defect facts from JIRA
- Calculate TCI/PFI metrics
- Detect anomalies
- Retrieve similar cases

### Stage 2: Review Agent
- Evaluate against rules.json
- Determine limitation eligibility
- Validate evidence completeness

### Stage 3: Advisor Agent
- Generate three-track recommendations
- Based on facts + review decision

## Output

```json
{
  "defect_id": "OBMC-9062",
  "status": "success",
  "fact": {
    "defect_id": "OBMC-9062",
    "severity": "Critical",
    "active_weeks": 11.5,
    "tci": 0.42,
    "pfi": 0.68,
    "anomalies": [...],
    "evidence": {...}
  },
  "review": {
    "decision_type": "TEMP_LIMITATION_ELIGIBLE",
    "confidence": 0.87,
    "triggered_rules": ["LIM-002"]
  },
  "advisor": {
    "preferred_path": {
      "track_type": "preferred",
      "summary": "建议申请临时限制...",
      "recommendations": [...]
    },
    "alternative_path": {...},
    "escalation_path": {...}
  },
  "pipeline_fingerprint": "a1b2c3d4...",
  "analyzed_at": "2026-06-11T12:15:00Z"
}
```

## Flags

| Flag | Description |
|------|-------------|
| `--full` | Include full detail for all stages |
| `--json` | Output raw JSON format |
| `--brief` | Summary only, no recommendations |

## Notes

- Run with `--full` for detailed analysis
- Check pipeline_fingerprint for audit trail
- Human reviewer can override any AI decision