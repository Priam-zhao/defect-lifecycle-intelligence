"""
AdvisorAgent 单元测试

测试 Advisor Agent 的建议生成能力
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.advisor_agent import AdvisorAgent
from agents.schemas_compat import AdvisorOutput, Recommendation


@pytest.fixture
def advisor_agent(mock_mcp_client):
    """创建 AdvisorAgent 实例"""
    return AdvisorAgent(mock_mcp_client)


class TestAdvisorAgent:
    """AdvisorAgent 测试类"""

    def test_init(self, advisor_agent):
        """测试初始化"""
        assert advisor_agent.name == "AdvisorAgent"
        assert advisor_agent.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_execute_with_defect_id(self, advisor_agent, mock_mcp_client):
        """测试使用 defect_id 执行"""
        async def mock_tool(name, kwargs):
            return {
                "extract_defect_facts": {
                    "defect_id": kwargs.get("defect_id", ""),
                    "key": kwargs.get("defect_id", ""),
                    "severity": "Critical",
                    "active_weeks": 8,
                    "evidence": {}
                },
                "review_defect": {
                    "decision_type": "PASS",
                    "confidence": 0.95
                },
                "retrieve_similar_cases": {
                    "cases": []
                }
            }.get(name, {})

        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_tool)

        result = await advisor_agent.execute("OBMC-24951")

        assert result["status"] == "success"
        assert result["data"]["defect_id"] == "OBMC-24951"

    @pytest.mark.asyncio
    async def test_execute_with_fact_and_review(self, advisor_agent, sample_defect_fact, sample_review_decision, mock_mcp_client):
        """测试使用事实和审查数据执行"""
        # Mock retrieve_similar_cases
        mock_mcp_client.call_tool = AsyncMock(return_value={"cases": []})

        result = await advisor_agent.execute(
            sample_defect_fact,
            sample_review_decision
        )

        assert result["status"] == "success"
        assert "recommendations" in result["data"]

    @pytest.mark.asyncio
    async def test_generate_must_fix_recommendations(self, advisor_agent, sample_defect_fact):
        """测试 MUST_FIX_BLOCKER 建议生成"""
        review_decision = {
            "decision_type": "MUST_FIX_BLOCKER",
            "confidence": 0.90,
            "reasoning": "Critical severity requires immediate fix"
        }

        output = advisor_agent._generate_recommendations(
            sample_defect_fact,
            review_decision,
            []
        )

        assert isinstance(output, AdvisorOutput)
        assert output.preferred_path.track_type == "preferred"
        assert output.alternative_path.track_type == "alternative"
        assert output.escalation_path.track_type == "escalation"

    @pytest.mark.asyncio
    async def test_generate_temp_limitation_recommendations(self, advisor_agent, sample_defect_fact):
        """测试 TEMP_LIMITATION_ELIGIBLE 建议生成"""
        review_decision = {
            "decision_type": "TEMP_LIMITATION_ELIGIBLE",
            "confidence": 0.85
        }

        output = advisor_agent._generate_recommendations(
            sample_defect_fact,
            review_decision,
            []
        )

        assert output.preferred_path.track_type == "preferred"
        assert len(output.preferred_path.recommendations) > 0

    @pytest.mark.asyncio
    async def test_generate_perm_limitation_recommendations(self, advisor_agent, sample_defect_fact):
        """测试 PERM_LIMITATION_ELIGIBLE 建议生成"""
        review_decision = {
            "decision_type": "PERM_LIMITATION_ELIGIBLE",
            "confidence": 0.80
        }

        output = advisor_agent._generate_recommendations(
            sample_defect_fact,
            review_decision,
            []
        )

        assert output.preferred_path.track_type == "preferred"
        # 应该提到 SSR B 审查
        summary_lower = output.preferred_path.summary.lower()
        assert "ssr" in summary_lower or "b" in summary_lower

    @pytest.mark.asyncio
    async def test_generate_ssrb_review_recommendations(self, advisor_agent, sample_defect_fact):
        """测试 CRITICAL_SSRB_REVIEW 建议生成"""
        review_decision = {
            "decision_type": "CRITICAL_SSRB_REVIEW",
            "confidence": 0.85
        }

        output = advisor_agent._generate_recommendations(
            sample_defect_fact,
            review_decision,
            []
        )

        assert output.preferred_path.track_type == "preferred"

    @pytest.mark.asyncio
    async def test_generate_invalid_closure_recommendations(self, advisor_agent, sample_defect_fact):
        """测试 INVALID_CLOSURE_REQUEST 建议生成"""
        review_decision = {
            "decision_type": "INVALID_CLOSURE_REQUEST",
            "confidence": 0.95
        }

        output = advisor_agent._generate_recommendations(
            sample_defect_fact,
            review_decision,
            []
        )

        assert output.preferred_path.track_type == "preferred"

    @pytest.mark.asyncio
    async def test_generate_insufficient_evidence_recommendations(self, advisor_agent, sample_defect_fact):
        """测试 INSUFFICIENT_EVIDENCE 建议生成"""
        review_decision = {
            "decision_type": "INSUFFICIENT_EVIDENCE",
            "confidence": 0.70,
            "reasoning": "Missing evidence: customer_impact, workaround_exists"
        }

        output = advisor_agent._generate_recommendations(
            sample_defect_fact,
            review_decision,
            []
        )

        assert output.preferred_path.track_type == "preferred"
        # 应该提到证据请求
        actions = [r.action for r in output.preferred_path.recommendations]
        assert any("evidence" in a.lower() for a in actions)

    @pytest.mark.asyncio
    async def test_generate_standard_recommendations(self, advisor_agent, sample_defect_fact):
        """测试 PASS 建议生成"""
        review_decision = {
            "decision_type": "PASS",
            "confidence": 0.95
        }

        output = advisor_agent._generate_recommendations(
            sample_defect_fact,
            review_decision,
            []
        )

        assert output.preferred_path.track_type == "preferred"
        assert output.preferred_path.summary == "标准流程处理"

    def test_analyze_fix_patterns(self, advisor_agent):
        """测试修复模式分析"""
        similar_cases = [
            {"defect_id": "OBMC-001", "resolution_days": 10},
            {"defect_id": "OBMC-002", "resolution_days": 15},
            {"defect_id": "OBMC-003", "resolution_days": 25},
            {"defect_id": "OBMC-004", "resolution_days": 45}
        ]

        patterns = advisor_agent._analyze_fix_patterns(similar_cases)

        assert len(patterns["quick_fix"]) == 1  # 10 days <= 14
        assert len(patterns["standard_fix"]) == 2  # 15 and 25 days between 15-30
        assert len(patterns["delayed_fix"]) == 1  # 45 days > 30

    def test_analyze_limitation_patterns(self, advisor_agent):
        """测试限制模式分析"""
        similar_cases = [
            {"defect_id": "OBMC-001", "limitation_duration": 90, "limitation_approved": True},
            {"defect_id": "OBMC-002", "limitation_duration": 90, "limitation_approved": True},
            {"defect_id": "OBMC-003", "limitation_duration": 90, "limitation_denied": True}
        ]

        patterns = advisor_agent._analyze_limitation_patterns(similar_cases)

        assert patterns["typical_duration"] == 90
        assert patterns["approval_rate"] == 2/3
        assert patterns["sample_size"] == 3

    @pytest.mark.asyncio
    async def test_retrieve_similar_cases(self, advisor_agent, sample_defect_fact, mock_mcp_client):
        """测试相似案例检索"""
        mock_mcp_client.call_tool = AsyncMock(return_value={
            "cases": [
                {"defect_id": "OBMC-24001", "similarity_score": 0.85}
            ]
        })

        cases = await advisor_agent._retrieve_similar_cases(sample_defect_fact)

        assert len(cases) == 1
        assert cases[0]["defect_id"] == "OBMC-24001"

    @pytest.mark.asyncio
    async def test_execute_with_similar_cases_included(self, advisor_agent, sample_defect_fact, sample_review_decision, mock_mcp_client):
        """测试包含相似案例的执行"""
        similar_cases = [
            {"defect_id": "OBMC-24001", "resolution_days": 12}
        ]

        result = await advisor_agent.execute(
            sample_defect_fact,
            sample_review_decision,
            similar_cases
        )

        assert result["status"] == "success"
        assert result["metadata"]["similar_cases_count"] == 1

    @pytest.mark.asyncio
    async def test_recommendation_confidence_bounded(self, advisor_agent, sample_defect_fact):
        """测试建议置信度边界"""
        review_decision = {
            "decision_type": "MUST_FIX_BLOCKER",
            "confidence": 0.98
        }

        output = advisor_agent._generate_recommendations(
            sample_defect_fact,
            review_decision,
            []
        )

        for recommendation in output.preferred_path.recommendations:
            assert 0 <= recommendation.confidence <= 1.0


class TestAdvisorAgentErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_execute_exception(self, advisor_agent):
        """测试执行异常"""
        # 传入无效数据触发异常
        result = await advisor_agent.execute(None)

        assert result["status"] == "error"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_with_failing_mcp_call(self, advisor_agent, mock_mcp_client):
        """测试 MCP 调用失败 - advisor 会优雅降级到默认 PASS 决策"""
        async def failing_call(*args, **kwargs):
            raise Exception("MCP connection error")

        mock_mcp_client.call_tool = failing_call

        result = await advisor_agent.execute("OBMC-24951")

        # Advisor gracefully handles MCP failures by falling back to default PASS decision
        assert result["status"] == "success"
        assert "recommendations" in result["data"]


class TestAdvisorAgentIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_advisor_flow(self, mock_mcp_client, sample_defect_fact, sample_review_decision):
        """测试完整建议生成流程"""
        mock_mcp_client.call_tool = AsyncMock(return_value={
            "cases": [
                {"defect_id": "OBMC-24001", "resolution_days": 12}
            ]
        })

        agent = AdvisorAgent(mock_mcp_client)
        result = await agent.execute(sample_defect_fact, sample_review_decision)

        assert result["status"] == "success"
        assert "recommendations" in result["data"]

        recommendations = result["data"]["recommendations"]
        assert "preferred_path" in recommendations
        assert "alternative_path" in recommendations
        assert "escalation_path" in recommendations

    @pytest.mark.asyncio
    async def test_all_decision_types(self, mock_mcp_client, sample_defect_fact):
        """测试所有决策类型的建议生成"""
        decision_types = [
            "MUST_FIX_BLOCKER",
            "TEMP_LIMITATION_ELIGIBLE",
            "PERM_LIMITATION_ELIGIBLE",
            "CRITICAL_SSRB_REVIEW",
            "INVALID_CLOSURE_REQUEST",
            "INSUFFICIENT_EVIDENCE",
            "PASS"
        ]

        mock_mcp_client.call_tool = AsyncMock(return_value={"cases": []})

        agent = AdvisorAgent(mock_mcp_client)

        for decision_type in decision_types:
            review_decision = {
                "decision_type": decision_type,
                "confidence": 0.85,
                "reasoning": f"Test for {decision_type}"
            }

            output = agent._generate_recommendations(
                sample_defect_fact,
                review_decision,
                []
            )

            assert output is not None
            assert output.defect_id == sample_defect_fact["defect_id"]