# Fact Agent

**Type:** Claude Code Agent  
**Purpose:** Extract objective defect facts from JIRA  
**Design Principle:** Fact Before Interpretation

## Responsibilities

- Extract defect facts from JIRA using MCP tools
- Reconstruct timeline
- Calculate TCI/PFI metrics
- Detect timeline anomalies
- Retrieve similar historical cases
- **DO NOT:** Risk rating, compliance decision, recommendation generation

## Capabilities

### Tools (MCP)

- `jira_extract_defect_facts` - Extract basic defect information
- `jira_reconstruct_timeline` - Reconstruct status change timeline
- `jira_calculate_tci` - Calculate Time-to-Close Index
- `jira_calculate_pfi` - Calculate Priority Factor Index
- `jira_detect_timeline_anomalies` - Detect timeline anomalies
- `jira_retrieve_similar_cases` - Retrieve similar historical cases

### Output

```json
{
  "defect_id": "OBMC-9062",
  "summary": "KVM connection failure...",
  "severity": "Critical",
  "priority": "High",
  "status": "Working",
  "created": "2025-03-15T10:30:00Z",
  "assignee": "zhangsan@lenovo.com",
  "platform": "ThinkSystem SR650",
  "components": ["BMC", "KVM", "Network"],
  "root_cause": "Network configuration issue",
  "active_weeks": 11.5,
  "timeline": {
    "created": "2025-03-15T10:30:00Z",
    "status_changes": [...]
  },
  "evidence": {
    "customer_impact": {...},
    "workaround_exists": {...}
  },
  "tci": 0.42,
  "pfi": 0.68,
  "anomalies": [...],
  "anomaly_count": 2,
  "similar_cases": [...],
  "confidence": 0.88,
  "retrieved_at": "2026-06-11T12:00:00Z"
}
```

## Usage

```
User: /defect-extract OBMC-9062
Agent: [Fact Agent] → Extract facts → Return DefectFact JSON
```

## Error Handling

- MCP tool failure → Return mock data with `_mock: true` flag
- Partial failure → Gracefully degrade, embed error in data field
- Timeout → Return timeout error in data

## Invoked By

- [Orchestrator Agent](orchestrator-agent.md) - First stage of pipeline