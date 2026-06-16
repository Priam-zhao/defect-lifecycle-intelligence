# Defect Lifecycle Intelligence - CLAUDE.md

**Project:** Defect Lifecycle Intelligence Agent  
**Architecture:** Multi-Agent + Skills + MCP  
**Design Principles:** Fact Before Interpretation, Rules Before Reasoning, Human Authority Supremacy

## Quick Start

```
/defect-analyze OBMC-9062
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agent Layer                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Orchestrator Agent                        │   │
│  │  - 编排任务，协调其他 Agent                           │   │
│  │  - 总结分析结果                                       │   │
│  │  - 格式化输出                                        │   │
│  └─────────────────────────────────────────────────────┘   │
│       │                  │                  │              │
│       ▼                  ▼                  ▼              │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐           │
│  │  Fact   │      │ Review  │      │ Advisor │           │
│  │  Agent  │      │  Agent  │      │  Agent  │           │
│  └────┬────┘      └────┬────┘      └────┬────┘           │
└───────┼────────────────┼────────────────┼─────────────────┘
        │                │                │
        ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                     Skill Layer                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Extract  │  │  Review  │  │  Advise  │  │ Analyze  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼─────────┘
        │                │                │             │
        ▼                ▼                ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                      MCP Layer                              │
│  defect_fact_tool  review_tool  advisor_tool  orchestrator │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        JIRA                                  │
└─────────────────────────────────────────────────────────────┘
```

## Agent Definitions

### Orchestrator Agent
- **职责**: 编排任务、协调其他 Agent、总结分析、格式化输出
- **调用**: Fact Agent, Review Agent, Advisor Agent

### Fact Agent
- **职责**: 从 JIRA 提取客观事实
- **输出**: DefectFact JSON

### Review Agent
- **职责**: 基于规则引擎进行合规验证
- **输出**: ReviewDecision

### Advisor Agent
- **职责**: 生成三轨推荐建议
- **输出**: AdvisorOutput

## Skills

| Command | Description |
|---------|-------------|
| `/defect-extract` | Extract defect facts (Skill → Fact Agent → MCP) |
| `/defect-review` | Review compliance (Skill → Review Agent → MCP) |
| `/defect-advise` | Generate recommendations (Skill → Advisor Agent → MCP) |
| `/defect-analyze` | Full pipeline (Skill → Orchestrator → All Agents) |
| `/defect-batch` | Batch analyze multiple defects |

## Design Principles

### 1. Fact Before Interpretation
- Always extract facts before judgment
- Facts are objective, interpretations are subjective
- Agent cannot make decisions without facts

### 2. Rules Before Reasoning
- Compliance decisions come from rule engine
- Rules defined in `mcp-server/config/rules.json`
- LLM only for explanation, not decision

### 3. Human Authority Supremacy
- Human reviewer is final authority
- AI recommendations can be overridden
- Override events feed back to improve rules

## MCP Tools

| Tool | Description |
|------|-------------|
| `jira_extract_defect_facts` | Extract basic defect info |
| `jira_reconstruct_timeline` | Reconstruct timeline |
| `jira_calculate_tci` | Calculate Time-to-Close Index |
| `jira_calculate_pfi` | Calculate Priority Factor Index |
| `jira_detect_timeline_anomalies` | Detect timeline anomalies |
| `jira_retrieve_similar_cases` | Retrieve similar cases |

## Output Formats

### DefectFact (from Fact Agent)
```json
{
  "defect_id": "OBMC-9062",
  "severity": "Critical",
  "tci": 0.42,
  "pfi": 0.68,
  "anomalies": [...],
  "evidence": {...}
}
```

### ReviewDecision (from Review Agent)
```json
{
  "decision_type": "TEMP_LIMITATION_ELIGIBLE",
  "confidence": 0.87,
  "triggered_rules": ["LIM-002"]
}
```

### AdvisorOutput (from Advisor Agent)
```json
{
  "preferred_path": {...},
  "alternative_path": {...},
  "escalation_path": {...}
}
```

## Decision Types

| Decision | Description |
|----------|-------------|
| MUST_FIX_BLOCKER | Critical + > 4 weeks → must fix |
| TEMP_LIMITATION_ELIGIBLE | Eligible for 90-day limitation |
| PERM_LIMITATION_ELIGIBLE | Eligible for permanent limitation |
| CRITICAL_SSRB_REVIEW | Requires SSR B review |
| INVALID_CLOSURE_REQUEST | Invalid closure request |
| INSUFFICIENT_EVIDENCE | Missing required evidence |
| PASS | Compliant |

## Configuration

- Rules: `mcp-server/config/rules.json`
- Knowledge Store: `knowledge_store/`
- MCP Server: `mcp-server/server.py`

## Project Structure

```
defect-lifecycle-intelligence/
├── agents/                    # Agent Layer
│   ├── __init__.py
│   ├── base.py               # Agent 基类
│   ├── orchestrator_agent.py # 编排器 Agent
│   ├── fact_agent.py         # Fact Agent
│   ├── review_agent.py       # Review Agent
│   ├── advisor_agent.py      # Advisor Agent
│   └── rule_engine.py        # 规则引擎
├── .claude/
│   ├── skills/               # Skill Layer
│   │   ├── defect-extract/
│   │   ├── defect-review/
│   │   ├── defect-advise/
│   │   ├── defect-analyze/
│   │   └── defect-batch/
│   └── agents/               # Agent 定义文档
│       ├── fact-agent.md
│       ├── review-agent.md
│       ├── advisor-agent.md
│       └── orchestrator-agent.md
├── mcp-server/               # MCP Layer
│   ├── tools/
│   │   ├── defect_fact_tool.py
│   │   ├── timeline_tool.py
│   │   ├── tci_pfi_tool.py
│   │   ├── limitation_tool.py
│   │   └── knowledge_tool.py
│   ├── config/
│   │   └── rules.json
│   └── server.py
└── tests/
    └── agents/
```

## Testing

```bash
pytest tests/agents/ -v
pytest tests/agents/test_fact_agent.py -v
pytest tests/agents/test_review_agent.py -v
pytest tests/agents/test_advisor_agent.py -v
```