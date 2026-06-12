"""
FactAgent 单元测试

测试 Fact Agent 的事实提取能力
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.fact_agent import FactAgent


@pytest.fixture
def fact_agent(mock_mcp_client):
    """创建 FactAgent 实例"""
    return FactAgent(mock_mcp_client)


class TestFactAgent:
    """FactAgent 测试类"""

    def test_init(self, fact_agent, mock_mcp_client):
        """测试初始化"""
        assert fact_agent.name == "FactAgent"
        assert fact_agent.version == "1.0.0"
        assert fact_agent.mcp_client == mock_mcp_client

    @pytest.mark.asyncio
    async def test_execute_success(self, fact_agent, mock_mcp_client):
        """测试执行成功"""
        # Mock 各工具返回 - 使用普通函数而不是 lambda
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": "OBMC-24951",
                    "key": "OBMC-24951",
                    "summary": "Test defect",
                    "severity": "Critical",
                    "priority": "High",
                    "created": "2025-03-15T10:30:00Z",
                    "assignee": "test@lenovo.com",
                    "reporter": "reporter@lenovo.com",
                    "components": ["BMC"],
                    "root_cause": "Network",
                    "evidence": {}
                },
                "reconstruct_timeline": {
                    "defect_id": "OBMC-24951",
                    "status_changes": [],
                    "created": "2025-03-15T10:30:00Z"
                },
                "calculate_tci": {
                    "tci": 0.65,
                    "actual_days": 20,
                    "expected_days": 14
                },
                "calculate_pfi": {
                    "pfi": 0.72,
                    "factors": {}
                },
                "detect_timeline_anomalies": {
                    "anomalies": [],
                    "anomaly_count": 0
                }
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        result = await fact_agent.execute("OBMC-24951")

        assert result["status"] == "success"
        assert result["data"]["defect_id"] == "OBMC-24951"
        assert result["metadata"]["defect_id"] == "OBMC-24951"

    @pytest.mark.asyncio
    async def test_execute_with_defect_id(self, fact_agent, mock_mcp_client):
        """测试使用 defect_id 执行"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "key": kwargs.get("defect_id", ""),
                    "summary": "Test",
                    "severity": "Medium",
                    "evidence": {}
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.5},
                "calculate_pfi": {"pfi": 0.5},
                "detect_timeline_anomalies": {"anomalies": []}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        result = await fact_agent.execute("OBMC-12345")

        assert result["status"] == "success"
        assert result["metadata"]["defect_id"] == "OBMC-12345"

    @pytest.mark.asyncio
    async def test_execute_exception(self, fact_agent, mock_mcp_client):
        """测试执行异常 - MCP 客户端异常被 _call_mcp_tool 捕获并转换为错误响应"""
        async def failing_call(*args, **kwargs):
            raise Exception("Connection error")

        mock_mcp_client.call_tool = failing_call

        result = await fact_agent.execute("OBMC-24951")

        # _call_mcp_tool catches exceptions and returns error dict, not raises
        # Then asyncio.gather with return_exceptions=True also catches them
        # The final result is "success" with partial data (some fields have error info)
        assert result["status"] == "success"
        # The data contains the fact_data which has an "error" field from the failed tool call
        data = result.get("data", {})
        assert "error" in data  # The extract_defect_facts returned error dict

    @pytest.mark.asyncio
    async def test_execute_with_similar_cases(self, fact_agent, mock_mcp_client):
        """测试获取相似案例"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": "OBMC-24951",
                    "root_cause": "Network",
                    "components": ["BMC"],
                    "platform": "ThinkSystem",
                    "evidence": {}
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.5},
                "calculate_pfi": {"pfi": 0.5},
                "detect_timeline_anomalies": {"anomalies": []},
                "retrieve_similar_cases": {
                    "cases": [
                        {"defect_id": "OBMC-24001", "similarity_score": 0.85}
                    ]
                }
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        result = await fact_agent.execute("OBMC-24951")

        assert result["status"] == "success"
        assert len(result["data"]["similar_cases"]) == 1

    def test_build_defect_fact(self, fact_agent):
        """测试构建 DefectFact"""
        fact_data = {
            "defect_id": "OBMC-24951",
            "severity": "Critical"
        }
        timeline = {"status_changes": []}
        tci_result = {"tci": 0.65, "actual_days": 20, "expected_days": 14}
        pfi_result = {"pfi": 0.72, "factors": {}}
        anomalies = {"anomalies": [], "anomaly_count": 0, "has_critical_anomaly": False}
        similar_cases = []

        result = fact_agent._build_defect_fact(
            fact_data, timeline, tci_result, pfi_result, anomalies, similar_cases
        )

        assert result["defect_id"] == "OBMC-24951"
        assert result["tci"] == 0.65
        assert result["pfi"] == 0.72
        assert result["anomaly_count"] == 0
        assert "retrieved_at" in result

    def test_calculate_overall_confidence_full(self, fact_agent):
        """测试综合置信度计算 - 完整数据"""
        fact_data = {
            "summary": "Test defect",
            "severity": "Critical",
            "priority": "High",
            "created": "2025-01-01T00:00:00Z",
            "assignee": "test@test.com",
            "reporter": "reporter@test.com",
            "evidence": {
                "customer_impact": {},
                "workaround_exists": {},
                "no_regression": {},
                "root_cause_analysis": {},
                "reproduction_steps": {},
                "test_coverage": {}
            },
            "timeline": {
                "status_changes": [
                    {}, {}, {}
                ]
            },
            "tci": 0.65,
            "pfi": 0.72
        }

        confidence = fact_agent._calculate_overall_confidence(fact_data)
        assert confidence >= 0.9

    def test_calculate_overall_confidence_partial(self, fact_agent):
        """测试综合置信度计算 - 部分数据"""
        fact_data = {
            "summary": "Test defect",
            "severity": "Critical",
            "evidence": {},
            "timeline": {"status_changes": [{}]},
            "tci": 0
        }

        confidence = fact_agent._calculate_overall_confidence(fact_data)
        assert 0 < confidence < 0.9

    def test_get_confidence_level_high(self, fact_agent):
        """测试高置信度等级"""
        assert fact_agent._get_confidence_level(0.95) == "high"
        assert fact_agent._get_confidence_level(0.90) == "high"

    def test_get_confidence_level_medium(self, fact_agent):
        """测试中等置信度等级"""
        assert fact_agent._get_confidence_level(0.89) == "medium"
        assert fact_agent._get_confidence_level(0.75) == "medium"

    def test_get_confidence_level_low(self, fact_agent):
        """测试低置信度等级"""
        assert fact_agent._get_confidence_level(0.74) == "low"
        assert fact_agent._get_confidence_level(0.50) == "low"

    def test_get_expected_days(self, fact_agent):
        """测试预期天数获取"""
        assert fact_agent.get_expected_days("Blocker") == 7
        assert fact_agent.get_expected_days("Critical") == 14
        assert fact_agent.get_expected_days("Major") == 30
        assert fact_agent.get_expected_days("Minor") == 60
        assert fact_agent.get_expected_days("Low") == 90
        assert fact_agent.get_expected_days("Unknown") == 30

    @pytest.mark.asyncio
    async def test_batch_execute(self, fact_agent, mock_mcp_client):
        """测试批量执行"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "evidence": {}
                },
                "reconstruct_timeline": {"status_changes": []},
                "calculate_tci": {"tci": 0.5},
                "calculate_pfi": {"pfi": 0.5},
                "detect_timeline_anomalies": {"anomalies": []}
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        defect_ids = ["OBMC-001", "OBMC-002", "OBMC-003"]
        results = await fact_agent.batch_execute(defect_ids, max_concurrent=2)

        assert len(results) == 3
        assert all(r.get("status") == "success" for r in results)

    @pytest.mark.asyncio
    async def test_batch_execute_with_errors(self, fact_agent, mock_mcp_client):
        """测试批量执行包含错误"""
        call_count = [0]

        async def mixed_call(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise Exception("Random error")
            return {
                "defect_id": kwargs.get("defect_id", ""),
                "evidence": {}
            }

        mock_mcp_client.call_tool = AsyncMock(side_effect=mixed_call)

        defect_ids = ["OBMC-001", "OBMC-002", "OBMC-003", "OBMC-004"]
        results = await fact_agent.batch_execute(defect_ids)

        assert len(results) == 4
        # 检查是否有成功的
        success_count = sum(1 for r in results if r.get("status") == "success")
        error_count = sum(1 for r in results if r.get("status") == "error")
        assert success_count + error_count == 4


class TestFactAgentMockData:
    """测试 Mock 数据处理"""

    @pytest.mark.asyncio
    async def test_mock_data_when_no_client(self):
        """测试无 MCP 客户端时返回 Mock 数据"""
        agent = FactAgent(None)

        # Mock extract_defect_facts
        result = await agent._call_mcp_tool(
            "extract_defect_facts",
            defect_id="MOCK-001"
        )

        assert result["defect_id"] == "MOCK-001"
        assert result["_mock"] is True
        assert result["summary"] is not None

    def test_mock_timeline_data(self):
        """测试 Mock 时间线数据"""
        agent = FactAgent(None)

        result = agent._get_mock_tool_result(
            "reconstruct_timeline",
            {"defect_id": "MOCK-001"}
        )

        assert result["defect_id"] == "MOCK-001"
        assert result["_mock"] is True

    def test_mock_tci_data(self):
        """测试 Mock TCI 数据"""
        agent = FactAgent(None)

        result = agent._get_mock_tool_result(
            "calculate_tci",
            {"defect_id": "MOCK-001"}
        )

        assert result["defect_id"] == "MOCK-001"
        assert result["tci"] > 0
        assert result["_mock"] is True

    def test_mock_pfi_data(self):
        """测试 Mock PFI 数据"""
        agent = FactAgent(None)

        result = agent._get_mock_tool_result(
            "calculate_pfi",
            {"defect_id": "MOCK-001"}
        )

        assert result["defect_id"] == "MOCK-001"
        assert result["pfi"] > 0
        assert result["_mock"] is True