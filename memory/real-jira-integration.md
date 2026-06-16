---
name: real-jira-integration-success
description: Direct tool call integration enables real JIRA data in agents
metadata:
  type: project
---

# Real JIRA Data Integration Success

## Summary

Successfully integrated real JIRA data into the Agent pipeline by adding direct tool calls to `BaseAgent._call_direct_tool()`.

## Problem

- `AgentOrchestrator` was initialized with `mcp_client=None`
- This caused all agents to return mock data instead of real JIRA data
- The MCP server uses stdio communication which isn't accessible from Python

## Solution

Added `_call_direct_tool()` method to `BaseAgent` that directly imports and calls tool classes:

```python
# agents/base.py - _call_direct_tool method
def _call_direct_tool(self, tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
    # Add mcp-server to sys.path
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mcp_server_dir = os.path.join(current_dir, "mcp-server")
    sys.path.insert(0, mcp_server_dir)
    
    from tools.defect_fact_tool import DefectFactTool
    from tools.timeline_tool import TimelineTool
    from tools.tci_pfi_tool import TciPfiTool
    from tools.knowledge_tool import KnowledgeTool
    
    # Call appropriate tool based on tool_name
```

## Test Results (UEFIRM-70862)

### Fact Agent ✅
- Summary: "ACPI errors" in system logs with SR250V2& ST250V2
- Severity: Medium
- Status: Closed
- Platform: Trenton
- Project: [9562] FW On-Demand Release 25C
- TCI: 0.541, PFI: 0.32
- Anomalies: 3 (status regressions)
- Data Source: Real JIRA ✅

### Review Agent ✅
- Decision: PASS (no rules matched - default pass)
- Limitation evaluation: PASS
- Closure evaluation: PASS

### Advisor Agent ✅
- Preferred: Standard workflow
- Alternative: Batch processing
- Escalation: Monitor risks

## Files Changed

- [agents/base.py](agents/base.py) - Added `_call_direct_tool()` method

## Test Scripts Created

- [test_direct_analysis.py](test_direct_analysis.py) - Direct tool test
- [test_orchestrator.py](test_orchestrator.py) - Orchestrator test
- `test_result_UEFIRM_70862.json` - Full output

## Next Steps

- Add integration tests to `tests/agents/`
- Verify with multiple defect IDs
- Consider caching for performance