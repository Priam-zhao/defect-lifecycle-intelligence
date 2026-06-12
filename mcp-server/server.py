"""
Defect Lifecycle Intelligence Agent - MCP Server

基于 JIRA Defect Lifecycle Intelligence Platform v4.0 设计
提供 Fact Agent、Review Agent、Advisor Agent 所需的数据获取能力
"""

import asyncio
import json
import os
from datetime import datetime
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(env_path)
except ImportError:
    pass

from tools.defect_fact_tool import DefectFactTool
from tools.timeline_tool import TimelineTool
from tools.tci_pfi_tool import TciPfiTool
from tools.knowledge_tool import KnowledgeTool


app = Server("defect-lifecycle-intelligence-agent")

# 初始化工具
defect_fact_tool = DefectFactTool()
timeline_tool = TimelineTool()
tci_pfi_tool = TciPfiTool()
knowledge_tool = KnowledgeTool()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用的 MCP Tools"""
    return [
        # ========== Defect Fact Tools ==========
        Tool(
            name="extract_defect_facts",
            description="从 JIRA 提取单个缺陷的事实数据（Fact Agent 核心工具）",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "JIRA Issue Key（如 OBMC-24951）"}
                },
                "required": ["defect_id"]
            }
        ),
        Tool(
            name="batch_extract_defect_facts",
            description="批量提取项目缺陷的事实数据",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID（如 OBMC 或 9508）"},
                    "max_results": {"type": "integer", "description": "最大返回数量", "default": 500}
                },
                "required": ["project_id"]
            }
        ),

        # ========== Timeline Tools ==========
        Tool(
            name="reconstruct_timeline",
            description="重建缺陷的状态变更时间线",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "JIRA Issue Key"}
                },
                "required": ["defect_id"]
            }
        ),
        Tool(
            name="calculate_duration",
            description="计算缺陷在特定状态间的持续时间",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "JIRA Issue Key"},
                    "from_status": {"type": "string", "description": "起始状态（可选）"},
                    "to_status": {"type": "string", "description": "结束状态（可选）"}
                },
                "required": ["defect_id"]
            }
        ),
        Tool(
            name="detect_timeline_anomalies",
            description="检测时间线异常（长期未处理、状态回退等）",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "JIRA Issue Key"}
                },
                "required": ["defect_id"]
            }
        ),
        Tool(
            name="analyze_time_patterns",
            description="分析多个缺陷的时间模式",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_ids": {"type": "array", "items": {"type": "string"}, "description": "缺陷 ID 列表"}
                },
                "required": ["defect_ids"]
            }
        ),

        # ========== TCI/PFI Tools ==========
        Tool(
            name="calculate_tci",
            description="计算 Time-to-Close Index（缺陷关闭效率指数）",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "JIRA Issue Key"},
                    "expected_days": {"type": "number", "description": "预期关闭天数（可选）"},
                    "severity": {"type": "string", "description": "严重程度（用于计算默认预期天数）"}
                },
                "required": ["defect_id"]
            }
        ),
        Tool(
            name="calculate_pfi",
            description="计算 Platform-First Index（平台优先指数）",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "JIRA Issue Key"},
                    "platform_field": {"type": "string", "description": "平台字段值（可选）"},
                    "root_cause_field": {"type": "string", "description": "根本原因字段值（可选）"}
                },
                "required": ["defect_id"]
            }
        ),
        Tool(
            name="batch_calculate_tci_pfi",
            description="批量计算多个缺陷的 TCI 和 PFI",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_ids": {"type": "array", "items": {"type": "string"}, "description": "缺陷 ID 列表"}
                },
                "required": ["defect_ids"]
            }
        ),
        Tool(
            name="get_tci_pfi_trend",
            description="获取项目的 TCI/PFI 趋势数据",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID"},
                    "time_range": {"type": "string", "description": "时间范围: week, month, quarter", "default": "month"}
                },
                "required": ["project_id"]
            }
        ),

        # ========== Knowledge Tools ==========
        Tool(
            name="store_canonical_defect",
            description="存储规范缺陷数据到知识库",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "缺陷 ID"},
                    "technical_domain": {"type": "string", "description": "技术域"},
                    "affected_components": {"type": "array", "items": {"type": "string"}, "description": "受影响组件"},
                    "failure_signature": {"type": "string", "description": "失败签名"},
                    "root_cause_category": {"type": "string", "description": "根因类别"},
                    "platform_family": {"type": "string", "description": "平台系列"},
                    "resolution_days": {"type": "number", "description": "解决天数"},
                    "tci_range": {"type": "array", "items": {"type": "number"}, "description": "TCI 范围 [min, max]"},
                    "known_patterns": {"type": "array", "items": {"type": "string"}, "description": "已知模式"}
                },
                "required": ["defect_id"]
            }
        ),
        Tool(
            name="retrieve_similar_cases",
            description="检索相似案例",
            inputSchema={
                "type": "object",
                "properties": {
                    "technical_domain": {"type": "string", "description": "技术域"},
                    "affected_components": {"type": "array", "items": {"type": "string"}, "description": "受影响组件"},
                    "failure_signature": {"type": "string", "description": "失败签名"},
                    "root_cause_category": {"type": "string", "description": "根因类别"},
                    "platform_family": {"type": "string", "description": "平台系列"},
                    "similarity_threshold": {"type": "number", "description": "相似度阈值", "default": 0.7}
                },
                "required": []
            }
        ),
        Tool(
            name="record_override_event",
            description="记录 Human Override 事件（Human Feedback Flywheel）",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "缺陷 ID"},
                    "system_decision": {"type": "string", "description": "系统决策"},
                    "human_decision": {"type": "string", "description": "人类决策"},
                    "reason": {"type": "string", "description": "原因"},
                    "reviewer": {"type": "string", "description": "审查者"}
                },
                "required": ["defect_id", "system_decision", "human_decision"]
            }
        ),
        Tool(
            name="get_override_events",
            description="获取覆盖事件记录",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "缺陷 ID 过滤"},
                    "reviewer": {"type": "string", "description": "审查者过滤"},
                    "limit": {"type": "integer", "description": "返回数量限制", "default": 100}
                },
                "required": []
            }
        ),
        Tool(
            name="generate_correction_pattern",
            description="生成纠正模式",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern_description": {"type": "string", "description": "模式描述"},
                    "related_events": {"type": "array", "items": {"type": "string"}, "description": "相关覆盖事件 ID"}
                },
                "required": ["pattern_description"]
            }
        ),
        Tool(
            name="get_correction_patterns",
            description="获取纠正模式列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern_id": {"type": "string", "description": "模式 ID 过滤"},
                    "min_confidence": {"type": "number", "description": "最低置信度", "default": 0}
                },
                "required": []
            }
        ),
        Tool(
            name="get_knowledge_stats",
            description="获取知识库统计信息",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # ========== Rule Engine Tools ==========
        Tool(
            name="read_rules_config",
            description="读取规则引擎配置",
            inputSchema={
                "type": "object",
                "properties": {
                    "config_type": {"type": "string", "description": "配置类型: limitation_rules, closure_rules, evidence_requirements"}
                },
                "required": ["config_type"]
            }
        ),
        Tool(
            name="evaluate_limitation_eligibility",
            description="评估缺陷的限制资格（Review Agent 核心）",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "JIRA Issue Key"},
                    "limitation_type": {"type": "string", "description": "限制类型: TEMP_LIMITATION_ELIGIBLE, PERM_LIMITATION_ELIGIBLE"}
                },
                "required": ["defect_id"]
            }
        ),

        # ========== Aggregation Tools ==========
        Tool(
            name="get_complete_defect_analysis",
            description="获取完整缺陷分析报告（一次调用返回事实、时间线、TCI/PFI、异常检测）",
            inputSchema={
                "type": "object",
                "properties": {
                    "defect_id": {"type": "string", "description": "JIRA Issue Key"}
                },
                "required": ["defect_id"]
            }
        ),
        Tool(
            name="get_project_facts_summary",
            description="获取项目缺陷事实摘要",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID"}
                },
                "required": ["project_id"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """执行 Tool 调用"""
    try:
        # ========== Defect Fact Tools ==========
        if name == "extract_defect_facts":
            result = defect_fact_tool.extract_defect_facts(
                defect_id=arguments["defect_id"]
            )

        elif name == "batch_extract_defect_facts":
            result = defect_fact_tool.batch_extract_facts(
                project_id=arguments["project_id"],
                max_results=arguments.get("max_results", 500)
            ).to_dict()

        # ========== Timeline Tools ==========
        elif name == "reconstruct_timeline":
            result = timeline_tool.reconstruct_timeline(
                defect_id=arguments["defect_id"]
            )

        elif name == "calculate_duration":
            result = timeline_tool.calculate_duration(
                defect_id=arguments["defect_id"],
                from_status=arguments.get("from_status"),
                to_status=arguments.get("to_status")
            )

        elif name == "detect_timeline_anomalies":
            result = timeline_tool.detect_anomalies(
                defect_id=arguments["defect_id"]
            )

        elif name == "analyze_time_patterns":
            result = timeline_tool.analyze_time_patterns(
                defect_ids=arguments["defect_ids"]
            )

        # ========== TCI/PFI Tools ==========
        elif name == "calculate_tci":
            result = tci_pfi_tool.calculate_tci(
                defect_id=arguments["defect_id"],
                expected_days=arguments.get("expected_days"),
                severity=arguments.get("severity")
            )

        elif name == "calculate_pfi":
            result = tci_pfi_tool.calculate_pfi(
                defect_id=arguments["defect_id"],
                platform_field=arguments.get("platform_field"),
                root_cause_field=arguments.get("root_cause_field")
            )

        elif name == "batch_calculate_tci_pfi":
            result = tci_pfi_tool.batch_calculate_tci_pfi(
                defect_ids=arguments["defect_ids"]
            )

        elif name == "get_tci_pfi_trend":
            result = tci_pfi_tool.get_tci_pfi_trend(
                project_id=arguments["project_id"],
                time_range=arguments.get("time_range", "month")
            )

        # ========== Knowledge Tools ==========
        elif name == "store_canonical_defect":
            result = knowledge_tool.store_canonical_defect(
                defect_data=arguments
            )

        elif name == "retrieve_similar_cases":
            result = knowledge_tool.retrieve_similar_cases(
                technical_domain=arguments.get("technical_domain"),
                affected_components=arguments.get("affected_components"),
                failure_signature=arguments.get("failure_signature"),
                root_cause_category=arguments.get("root_cause_category"),
                platform_family=arguments.get("platform_family"),
                similarity_threshold=arguments.get("similarity_threshold", 0.7)
            ).to_dict()

        elif name == "record_override_event":
            result = knowledge_tool.record_override_event(
                event_data=arguments
            )

        elif name == "get_override_events":
            result = knowledge_tool.get_override_events(
                defect_id=arguments.get("defect_id"),
                reviewer=arguments.get("reviewer"),
                limit=arguments.get("limit", 100)
            )

        elif name == "generate_correction_pattern":
            result = knowledge_tool.generate_correction_pattern(
                pattern_description=arguments["pattern_description"],
                related_events=arguments.get("related_events")
            )

        elif name == "get_correction_patterns":
            result = knowledge_tool.get_correction_patterns(
                pattern_id=arguments.get("pattern_id"),
                min_confidence=arguments.get("min_confidence", 0)
            )

        elif name == "get_knowledge_stats":
            result = knowledge_tool.get_knowledge_stats()

        # ========== Rule Engine Tools ==========
        elif name == "read_rules_config":
            config_type = arguments["config_type"]
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "rules.json"
            )
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                result = config.get(config_type, {})
            except Exception as e:
                result = {"error": str(e)}

        elif name == "evaluate_limitation_eligibility":
            defect_id = arguments["defect_id"]
            limitation_type = arguments.get("limitation_type", "TEMP_LIMITATION_ELIGIBLE")

            # 获取缺陷事实
            fact = defect_fact_tool.extract_defect_facts(defect_id)

            # 读取规则配置
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "rules.json"
            )
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 简单规则评估
            evidence = fact.get("evidence", {})
            evidence_required = config.get("evidence_requirements", {}).get(limitation_type, [])

            # 检查证据完整性
            missing_evidence = []
            for req in evidence_required:
                evidence_type = req.get("type") if isinstance(req, dict) else req
                if not evidence.get(evidence_type):
                    missing_evidence.append(evidence_type)

            # 检查严重程度
            severity = fact.get("severity", "")
            if severity in ["Blocker", "Critical"]:
                result = {
                    "defect_id": defect_id,
                    "decision": "MUST_FIX_BLOCKER",
                    "eligible": False,
                    "reason": "Blocker/Critical severity cannot be limited",
                    "confidence": 0.95
                }
            elif len(missing_evidence) == 0:
                result = {
                    "defect_id": defect_id,
                    "decision": limitation_type,
                    "eligible": True,
                    "reason": "All required evidence provided",
                    "confidence": 0.85
                }
            else:
                result = {
                    "defect_id": defect_id,
                    "decision": "INSUFFICIENT_EVIDENCE",
                    "eligible": False,
                    "missing_evidence": missing_evidence,
                    "confidence": 0.80
                }

        # ========== Aggregation Tools ==========
        elif name == "get_complete_defect_analysis":
            defect_id = arguments["defect_id"]

            # 并行获取多个数据
            fact = defect_fact_tool.extract_defect_facts(defect_id)
            timeline = timeline_tool.reconstruct_timeline(defect_id)
            tci = tci_pfi_tool.calculate_tci(defect_id)
            pfi = tci_pfi_tool.calculate_pfi(defect_id)
            anomalies = timeline_tool.detect_anomalies(defect_id)

            result = {
                "defect_id": defect_id,
                "facts": fact,
                "timeline": timeline,
                "tci": tci,
                "pfi": pfi,
                "anomalies": anomalies,
                "generated_at": datetime.now().isoformat()
            }

        elif name == "get_project_facts_summary":
            project_id = arguments["project_id"]
            batch_result = defect_fact_tool.batch_extract_facts(project_id)

            # 统计分析
            tci_values = []
            pfi_values = []
            severities = {}

            for fact in batch_result.facts:
                # 计算 TCI
                tci_result = tci_pfi_tool.calculate_tci(fact.key)
                tci_values.append(tci_result.get("tci", 0))

                # 计算 PFI
                pfi_result = tci_pfi_tool.calculate_pfi(fact.key)
                pfi_values.append(pfi_result.get("pfi", 0))

                # 统计严重程度
                sev = fact.severity
                severities[sev] = severities.get(sev, 0) + 1

            result = {
                "project_id": project_id,
                "total_defects": batch_result.total_defects,
                "successful": batch_result.successful,
                "failed": batch_result.failed,
                "avg_tci": round(sum(tci_values) / len(tci_values), 3) if tci_values else 0,
                "avg_pfi": round(sum(pfi_values) / len(pfi_values), 3) if pfi_values else 0,
                "severity_distribution": severities,
                "generated_at": datetime.now().isoformat()
            }

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2, default=str))]

    except Exception as e:
        import traceback
        return [TextContent(type="text", text=json.dumps({"error": str(e), "traceback": traceback.format_exc()}, ensure_ascii=False))]


async def main():
    """启动 MCP Server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())