# JIRA MCP Server Configuration

Model Context Protocol (MCP) server for JIRA integration.

## Connection

```json
{
  "mcpServers": {
    "jira": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-jira"]
    }
  }
}
```

## Available Tools

### defect_fact_tool.py

| Tool | Description |
|------|-------------|
| `jira_extract_defect_facts` | Extract basic defect information |
| `jira_reconstruct_timeline` | Reconstruct status change timeline |
| `jira_retrieve_similar_cases` | Retrieve similar historical cases |

### timeline_tool.py

| Tool | Description |
|------|-------------|
| `jira_detect_timeline_anomalies` | Detect timeline anomalies |

### tci_pfi_tool.py

| Tool | Description |
|------|-------------|
| `jira_calculate_tci` | Calculate Time-to-Close Index |
| `jira_calculate_pfi` | Calculate Priority Factor Index |

### knowledge_tool.py

| Tool | Description |
|------|-------------|
| `jira_search_defects` | Search defects in knowledge base |
| `jira_get_canonical_case` | Get canonical case for defect type |

## Local MCP Server

For development, use the local MCP server:

```json
{
  "mcpServers": {
    "defect-lifecycle": {
      "command": "python",
      "args": ["mcp-server/server.py"],
      "cwd": "E:\\OneDrive - Lenovo\\Defect Lifecycle Intelligence"
    }
  }
}
```

## Environment Variables

```bash
JIRA_URL=https://lenovo.atlassian.net
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=your_api_token
```

## Usage

1. Configure MCP in Claude Code settings
2. Use `/defect-extract <defect_id>` to extract facts
3. Use `/defect-review <defect_id>` to review compliance
4. Use `/defect-advise <defect_id>` to get recommendations
5. Use `/defect-analyze <defect_id>` for full pipeline