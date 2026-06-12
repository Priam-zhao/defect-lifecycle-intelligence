# Defect Batch Analyze Skill

Batch analyze multiple defects using the complete pipeline.

## Usage

```
/defect-batch <defect_id_1> <defect_id_2> ...
/defect-batch <defect_id_1> <defect_id_2> --parallel
```

## Examples

```
/defect-batch OBMC-9062 OBMC-9063 OBMC-9064
/defect-batch OBMC-9062 OBMC-24951 --parallel
/defect-batch OBMC-9062 OBMC-9063 OBMC-9064 OBMC-9065 OBMC-9066 --parallel
```

## What It Does

1. Runs complete pipeline for each defect:
   - Fact Agent → Review Agent → Advisor Agent
2. Parallel execution (when `--parallel` flag used)
3. Returns summary table + detailed results

## Output Format

```json
{
  "summary": {
    "total": 3,
    "success": 3,
    "failed": 0,
    "analyzed_at": "2026-06-11T12:20:00Z"
  },
  "results": [
    {
      "defect_id": "OBMC-9062",
      "status": "success",
      "severity": "Critical",
      "decision_type": "TEMP_LIMITATION_ELIGIBLE",
      "confidence": 0.87
    },
    ...
  ]
}
```

## Flags

| Flag | Description |
|------|-------------|
| `--parallel` | Run in parallel (faster for many defects) |
| `--json` | Output raw JSON format |
| `--csv` | Output CSV format |
| `--summary` | Summary table only |

## Notes

- Use `--parallel` for > 5 defects
- Results cached for 5 minutes
- Check `_mock: true` to identify mock data