# Defect Extract Skill

Extract objective defect facts from JIRA using the Fact Agent pipeline.

## Usage

```
/defect-extract <defect_id>
```

## Examples

```
/defect-extract OBMC-9062
/defect-extract OBMC-24951
/defect-extract OBMC-17994
```

## What It Does

1. Invokes Fact Agent
2. Extracts defect facts using MCP tools:
   - `jira_extract_defect_facts` - Basic defect info
   - `jira_reconstruct_timeline` - Status timeline
   - `jira_calculate_tci` - Time-to-Close Index
   - `jira_calculate_pfi` - Priority Factor Index
   - `jira_detect_timeline_anomalies` - Anomaly detection
   - `jira_retrieve_similar_cases` - Similar cases
3. Returns structured DefectFact JSON

## Output

```json
{
  "defect_id": "OBMC-9062",
  "summary": "...",
  "severity": "Critical",
  "priority": "High",
  "tci": 0.42,
  "pfi": 0.68,
  "anomalies": [...],
  "similar_cases": [...],
  "confidence": 0.88
}
```

## Notes

- Only extracts facts, no interpretation
- MCP tools may return mock data if JIRA unavailable
- Check `_mock: true` flag to identify mock data