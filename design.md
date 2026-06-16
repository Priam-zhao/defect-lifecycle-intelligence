# Defect Lifecycle Intelligence - 项目设计

## 架构

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

## 设计原则

- **Fact Before Interpretation**: 事实提取优先于合规判断
- **Rules Before Reasoning**: 规则引擎决定合规性
- **Human Authority Supremacy**: 人类审查员是最终权威

## 4个 Agent

| Agent | 职责 | 输出 |
|-------|------|------|
| Orchestrator Agent | 编排任务、协调Agent、总结分析、格式化输出 | 完整分析报告 |
| Fact Agent | 从 JIRA 提取客观事实 | DefectFact JSON |
| Review Agent | 基于规则引擎进行合规验证 | ReviewDecision |
| Advisor Agent | 生成三轨推荐建议 | AdvisorOutput |

## 实施状态

### Agent Layer ✅
- [x] base.py - Agent 基类
- [x] fact_agent.py - Fact Agent
- [x] review_agent.py - Review Agent
- [x] advisor_agent.py - Advisor Agent
- [x] orchestrator_agent.py - Orchestrator Agent
- [x] rule_engine.py - 规则引擎

### Skill Layer ✅
- [x] defect-extract - 缺陷事实提取
- [x] defect-review - 合规审查
- [x] defect-advise - 推荐建议
- [x] defect-analyze - 完整分析
- [x] defect-batch - 批量分析

### MCP Layer ✅
- [x] defect_fact_tool - 缺陷事实提取
- [x] timeline_tool - 时间线重建
- [x] tci_pfi_tool - TCI/PFI 计算
- [x] limitation_tool - Limitation 数据提取
- [x] knowledge_tool - 知识库
- [x] rules.json - 规则配置

### 集成测试 ⏳
- [ ] 完整流程测试 (Skill → Agent → MCP)
- [ ] Mock 测试
- [ ] 边界测试

## 调用链路

```
User → Skill → Orchestrator Agent → [Fact/Review/Advisor] Agent → MCP Tools → JIRA
```

## 输出格式

### Basic Info (当前实现)
```json
{
  "defect_id": "XCC-83683",
  "summary": "SR655 V3 XCC/BMC change history contains garbled characters",
  "severity": "Low",
  "platform_found": "Kahoolawe",
  "project_found": "[9483] FW Agile Release 25-4",
  "priority": "Medium",
  "status": "Closed",
  "root_cause": "-",
  "resolution": "Done",
  "solution_explanation": "Documentation issue resolved.",
  "build_fixed": "N/A"
}
```

### Timeline (当前实现)
```json
{
  "created": "2026-06-05T05:38:49",
  "resolved": "2026-06-10T23:07:27",
  "duration_days": 5.7
}
```

### Limitation History (当前实现)
```json
{
  "original_defect_id": "UEFIRM-70862",
  "total_limitation_records": 1,
  "limitation_records": [
    {
      "key": "UEFIRM-71232",
      "link_type": "Resolves",
      "jira_project": "UEFIRM",
      "iteration_project": "[9483] FW Agile Release 25-4",
      "created": "2025-07-16T...",
      "status": "Closed"
    }
  ]
}
```