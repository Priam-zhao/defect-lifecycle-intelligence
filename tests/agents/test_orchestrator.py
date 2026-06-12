"""
Orchestrator 单元测试

测试 Agent Orchestrator 和 Human Feedback Flywheel
"""

import pytest
import asyncio
import os
import json
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.orchestrator import AgentOrchestrator, HumanFeedbackFlywheel


@pytest.fixture
def orchestrator(mock_mcp_client, rules_config_path):
    """创建 AgentOrchestrator 实例"""
    return AgentOrchestrator(mock_mcp_client, rules_config_path)


@pytest.fixture
def flywheel(temp_knowledge_store):
    """创建 HumanFeedbackFlywheel 实例"""
    return HumanFeedbackFlywheel(temp_knowledge_store)


class TestAgentOrchestrator:
    """AgentOrchestrator 测试类"""

    def test_init(self, orchestrator):
        """测试初始化"""
        assert orchestrator.fact_agent is not None
        assert orchestrator.review_agent is not None
        assert orchestrator.advisor_agent is not None
        assert orchestrator.VERSION == "1.0.0"

    @pytest.mark.asyncio
    async def test_analyze_defect_full(self, orchestrator, mock_mcp_client):
        """测试完整缺陷分析"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "key": kwargs.get("defect_id", ""),
                    "summary": "Test defect",
                    "severity": "Critical",
                    "priority": "High",
                    "status": "Working",
                    "assignee": "test@lenovo.com",
                    "reporter": "reporter@lenovo.com",
                    "platform": "ThinkSystem",
                    "components": ["BMC"],
                    "root_cause": "Network",
                    "active_weeks": 8,
                    "tci": 0.65,
                    "pfi": 0.72,
                    "confidence": 0.88,
                    "evidence": {
                        "customer_impact": {"source": "test"}
                    },
                    "timeline": {"status_changes": []},
                    "anomalies": [],
                    "anomaly_count": 0,
                    "similar_cases": []
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.65},
                "calculate_pfi": {"pfi": 0.72},
                "detect_timeline_anomalies": {"anomalies": []}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        result = await orchestrator.analyze_defect("OBMC-24951")

        assert result["defect_id"] == "OBMC-24951"
        assert "pipeline_fingerprint" in result
        assert result["fact_status"] == "success"
        assert result["review_status"] == "success"
        assert result["advisor_status"] == "success"
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_analyze_defect_partial(self, orchestrator, mock_mcp_client):
        """测试部分分析（跳过某些阶段）"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "severity": "Critical",
                    "evidence": {}
                }
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        result = await orchestrator.analyze_defect(
            "OBMC-24951",
            include_facts=True,
            include_review=False,
            include_advisor=False
        )

        assert result["fact_status"] == "success"
        assert result["review_status"] == "skipped"
        assert result["advisor_status"] == "skipped"

    @pytest.mark.asyncio
    async def test_analyze_defect_fast(self, orchestrator, mock_mcp_client):
        """测试快速分析"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "summary": "Test defect",
                    "severity": "Critical",
                    "active_weeks": 8,
                    "tci": 0.65,
                    "evidence": {}
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.65},
                "calculate_pfi": {"pfi": 0.72},
                "detect_timeline_anomalies": {"anomalies": []}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        result = await orchestrator.analyze_defect_fast("OBMC-24951")

        assert result["defect_id"] == "OBMC-24951"
        assert "decision_type" in result

    @pytest.mark.asyncio
    async def test_batch_analyze(self, orchestrator, mock_mcp_client):
        """测试批量分析"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "severity": "Critical",
                    "evidence": {},
                    "root_cause": "Network",
                    "components": []
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.5},
                "calculate_pfi": {"pfi": 0.5},
                "detect_timeline_anomalies": {"anomalies": []}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        defect_ids = ["OBMC-001", "OBMC-002", "OBMC-003"]
        result = await orchestrator.batch_analyze(defect_ids, max_concurrent=2)

        assert result["total"] == 3
        assert result["successful"] + result["failed"] == 3
        assert len(result["results"]) == result["successful"]

    @pytest.mark.asyncio
    async def test_batch_analyze_callback(self, orchestrator, mock_mcp_client):
        """测试批量分析带回调"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "severity": "Critical",
                    "evidence": {}
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.5},
                "calculate_pfi": {"pfi": 0.5},
                "detect_timeline_anomalies": {"anomalies": []}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        callback_calls = []

        def callback(index, total, defect_id):
            callback_calls.append((index, total, defect_id))

        defect_ids = ["OBMC-001", "OBMC-002"]
        await orchestrator.batch_analyze(defect_ids, callback=callback)

        assert len(callback_calls) == 2

    @pytest.mark.asyncio
    async def test_get_defect_summary(self, orchestrator, mock_mcp_client):
        """测试获取缺陷摘要"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "summary": "Test defect summary",
                    "severity": "Critical",
                    "status": "Working",
                    "assignee": "test@lenovo.com",
                    "active_weeks": 8,
                    "tci": 0.65,
                    "pfi": 0.72,
                    "confidence": 0.88,
                    "anomaly_count": 1,
                    "evidence": {}
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.65},
                "calculate_pfi": {"pfi": 0.72},
                "detect_timeline_anomalies": {"anomalies": ["test anomaly"], "anomaly_count": 1}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        summary = await orchestrator.get_defect_summary("OBMC-24951")

        assert summary["defect_id"] == "OBMC-24951"
        assert summary["severity"] == "Critical"
        assert summary["has_anomalies"] is True

    def test_generate_pipeline_fingerprint(self, orchestrator):
        """测试 Pipeline 指纹生成"""
        fp1 = orchestrator._generate_pipeline_fingerprint()
        fp2 = orchestrator._generate_pipeline_fingerprint()

        assert len(fp1) == 16
        assert len(fp2) == 16
        # 由于时间戳不同，应该不同
        assert fp1 != fp2

    def test_get_pipeline_info(self, orchestrator):
        """测试获取 Pipeline 信息"""
        info = orchestrator.get_pipeline_info()

        assert info["version"] == "1.0.0"
        assert "agents" in info
        assert "fact" in info["agents"]
        assert "review" in info["agents"]
        assert "advisor" in info["agents"]
        assert "features" in info


class TestHumanFeedbackFlywheel:
    """HumanFeedbackFlywheel 测试类"""

    def test_init(self, flywheel):
        """测试初始化"""
        assert flywheel.VERSION == "1.0.0"
        assert flywheel.knowledge_store_path is not None

    def test_record_override(self, flywheel):
        """测试记录覆盖事件"""
        result = flywheel.record_override(
            defect_id="OBMC-24951",
            system_decision="TEMP_LIMITATION_ELIGIBLE",
            human_decision="MUST_FIX_BLOCKER",
            reason="Customer impact too severe for limitation",
            reviewer="admin@lenovo.com"
        )

        assert "event" in result
        assert result["event"]["defect_id"] == "OBMC-24951"
        assert result["event"]["system_decision"] == "TEMP_LIMITATION_ELIGIBLE"
        assert result["event"]["human_decision"] == "MUST_FIX_BLOCKER"

    def test_record_override_with_metadata(self, flywheel):
        """测试记录带元数据的覆盖事件"""
        result = flywheel.record_override(
            defect_id="OBMC-24951",
            system_decision="PASS",
            human_decision="TEMP_LIMITATION_ELIGIBLE",
            reason="Per customer request",
            reviewer="manager@lenovo.com",
            metadata={"customer_name": "Test Customer", "priority": "high"}
        )

        assert "event" in result

    def test_find_similar_override_events(self, flywheel):
        """测试查找相似覆盖事件"""
        # 记录多个相似事件
        for i in range(3):
            flywheel.record_override(
                defect_id=f"OBMC-{1000+i}",
                system_decision="TEMP_LIMITATION_ELIGIBLE",
                human_decision="MUST_FIX_BLOCKER",
                reason=f"Test reason {i}",
                reviewer="test@lenovo.com"
            )

        # 查找相似事件
        event_data = {
            "system_decision": "TEMP_LIMITATION_ELIGIBLE",
            "human_decision": "MUST_FIX_BLOCKER"
        }

        similar = flywheel._find_similar_override_events(event_data)

        assert len(similar) >= 3

    def test_generate_correction_pattern(self, flywheel):
        """测试生成纠正模式"""
        events = [
            {
                "defect_id": "OBMC-001",
                "system_decision": "TEMP_LIMITATION_ELIGIBLE",
                "human_decision": "MUST_FIX_BLOCKER",
                "reason": "Test",
                "reviewer": "test@lenovo.com",
                "timestamp": datetime.now().isoformat()
            },
            {
                "defect_id": "OBMC-002",
                "system_decision": "TEMP_LIMITATION_ELIGIBLE",
                "human_decision": "MUST_FIX_BLOCKER",
                "reason": "Test",
                "reviewer": "test@lenovo.com",
                "timestamp": datetime.now().isoformat()
            },
            {
                "defect_id": "OBMC-003",
                "system_decision": "TEMP_LIMITATION_ELIGIBLE",
                "human_decision": "MUST_FIX_BLOCKER",
                "reason": "Test",
                "reviewer": "test@lenovo.com",
                "timestamp": datetime.now().isoformat()
            }
        ]

        pattern = flywheel._generate_correction_pattern(events)

        assert pattern is not None
        assert "TEMP_LIMITATION_ELIGIBLE" in pattern.pattern_description
        assert "MUST_FIX_BLOCKER" in pattern.pattern_description
        assert pattern.pattern_id.startswith("PATTERN-")

    def test_get_recent_patterns(self, flywheel):
        """测试获取最近纠正模式"""
        patterns = flywheel.get_recent_patterns(limit=5)

        # 应该有模式（如果之前记录过事件）
        # 这个测试主要是验证方法不报错
        assert isinstance(patterns, list)


class TestOrchestratorErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_analyze_defect_error_recovery(self, mock_mcp_client, rules_config_path):
        """测试错误恢复 - MCP 工具失败时错误嵌入在数据中"""
        async def failing_call(*args, **kwargs):
            raise Exception("Tool failure")

        mock_mcp_client.call_tool = failing_call

        orchestrator = AgentOrchestrator(mock_mcp_client, rules_config_path)

        result = await orchestrator.analyze_defect("OBMC-001")

        # 验证返回了结果
        assert result["defect_id"] == "OBMC-001"

        # fact 数据中包含错误（来自失败的 MCP 调用）
        fact = result.get("fact", {})

        # 验证错误被嵌入到 fact 数据中
        assert "error" in fact, "Error should be embedded in fact when MCP tool fails"
        assert fact.get("status") == "error"

        # review 和 advisor 应该降级处理
        assert result["review_status"] in ["error", "partial", "skipped", "success"]
        assert result["advisor_status"] in ["error", "partial", "skipped", "success"]

    @pytest.mark.asyncio
    async def test_batch_analyze_stop_on_error(self, mock_mcp_client, rules_config_path):
        """测试批量分析错误停止"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "severity": "Critical",
                    "evidence": {}
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.5},
                "calculate_pfi": {"pfi": 0.5},
                "detect_timeline_anomalies": {"anomalies": []}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        orchestrator = AgentOrchestrator(mock_mcp_client, rules_config_path)

        defect_ids = ["OBMC-001", "OBMC-002", "OBMC-003"]
        result = await orchestrator.batch_analyze(
            defect_ids,
            stop_on_error=False  # 不停止，继续处理
        )

        assert result["total"] == 3


class TestOrchestratorIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_pipeline_flow(self, mock_mcp_client, rules_config_path):
        """测试完整 Pipeline 流程"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "key": kwargs.get("defect_id", ""),
                    "summary": "Test defect for integration",
                    "severity": "Critical",
                    "priority": "High",
                    "status": "Working",
                    "assignee": "test@lenovo.com",
                    "reporter": "reporter@lenovo.com",
                    "platform": "ThinkSystem",
                    "components": ["BMC", "KVM"],
                    "root_cause": "Network configuration",
                    "active_weeks": 8,
                    "tci": 0.65,
                    "pfi": 0.72,
                    "confidence": 0.88,
                    "evidence": {
                        "customer_impact": {"source": "customer_report"},
                        "workaround_exists": {"source": "internal"}
                    },
                    "timeline": {
                        "status_changes": [
                            {"from_status": "New", "to_status": "Assigned"},
                            {"from_status": "Assigned", "to_status": "Working"}
                        ]
                    },
                    "anomalies": [],
                    "anomaly_count": 0,
                    "similar_cases": []
                },
                "reconstruct_timeline": {
                    "status_changes": [
                        {"from_status": "New", "to_status": "Assigned"},
                        {"from_status": "Assigned", "to_status": "Working"}
                    ]
                },
                "calculate_tci": {"tci": 0.65, "actual_days": 20, "expected_days": 14},
                "calculate_pfi": {"pfi": 0.72, "factors": {}},
                "detect_timeline_anomalies": {"anomalies": [], "anomaly_count": 0}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        orchestrator = AgentOrchestrator(mock_mcp_client, rules_config_path)
        result = await orchestrator.analyze_defect("OBMC-24951")

        # 验证完整流程
        assert result["defect_id"] == "OBMC-24951"
        assert result["status"] == "success"

        # 验证各阶段结果
        assert "fact" in result
        assert "review" in result
        assert "advisor" in result

        # 验证 Pipeline 元数据
        assert result["pipeline_fingerprint"] is not None
        assert result["pipeline_version"] == "1.0.0"
        assert "started_at" in result
        assert "completed_at" in result
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_multiple_defects_batch_processing(self, mock_mcp_client, rules_config_path):
        """测试多缺陷批量处理"""
        async def mock_tool(name, kwargs):
            defect_id = kwargs.get("defect_id", "")
            severities = ["Critical", "Major", "Minor"]
            severity_index = hash(defect_id) % 3 if defect_id else 0
            return {
                "extract_defect_facts": {
                    "defect_id": defect_id,
                    "key": defect_id,
                    "summary": f"Batch test defect {defect_id}",
                    "severity": severities[severity_index],
                    "evidence": {}
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.5},
                "calculate_pfi": {"pfi": 0.5},
                "detect_timeline_anomalies": {"anomalies": []}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        orchestrator = AgentOrchestrator(mock_mcp_client, rules_config_path)
        defect_ids = [f"OBMC-{1000+i}" for i in range(5)]
        result = await orchestrator.batch_analyze(defect_ids, max_concurrent=3)

        assert result["total"] == 5
        assert result["successful"] + result["failed"] == 5
        assert result["success_rate"] >= 0