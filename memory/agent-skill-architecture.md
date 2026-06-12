---
name: agent-vs-skill-architecture
description: Agent 和 Skill 的架构区别
metadata:
  type: reference
---

# Agent vs Skill 架构理解

## 正确架构
```
用户 → Skill（命令入口）→ Agent（执行者）→ MCP（数据源）
```

## 层级职责

| 层级 | 组件 | 职责 |
|------|------|------|
| 接口层 | Skill | 封装 Agent 能力，提供命令入口 `/defect-extract` |
| 执行层 | Agent | 调用 MCP 工具，执行逻辑 |
| 数据层 | MCP | 连接 JIRA，获取数据 |

## 3 个 Agent

- **Fact Agent**: 提取客观事实（不解释、不决策）
- **Review Agent**: 基于规则引擎进行合规验证
- **Advisor Agent**: 生成三轨推荐建议

## Skill 是对外接口

- Skill 封装 Agent 的能力
- 用户通过 `/命令` 调用 Skill
- Skill 调用对应 Agent 执行

**Why:** 保持架构清晰，分层职责明确
**How to apply:** 创建 Skill 时，描述其调用的 Agent，而不是直接实现逻辑