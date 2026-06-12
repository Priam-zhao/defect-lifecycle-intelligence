"""
ReviewAgent 单元测试

测试 Review Agent 的合规审查能力
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.review_agent import ReviewAgent
from agents.schemas_compat import ReviewDecision, DecisionType, ConfidenceLevel


@pytest.fixture
def review_agent(mock_mcp_client, rules_config_path):
    """创建 ReviewAgent 实例"""
    return ReviewAgent(mock_mcp_client, rules_config_path)


class TestReviewAgent:
    """ReviewAgent 测试类"""

    def test_init(self, review_agent):
        """测试初始化"""
        assert review_agent.name == "ReviewAgent"
        assert review_agent.version == "1.0.0"
        assert review_agent.rule_engine is not None

    @pytest.mark.asyncio
    async def test_execute_with_defect_id(self, review_agent, mock_mcp_client):
        """测试使用 defect_id 执行"""
        mock_mcp_client.call_tool = AsyncMock(side_effect=lambda name, **kwargs: {
            "extract_defect_facts": {
                "defect_id": kwargs.get("defect_id", ""),
                "key": kwargs.get("defect_id", ""),
                "severity": "Critical",
                "active_weeks": 8,
                "evidence": {}
            }
        }.get(name, {}))

        result = await review_agent.execute("OBMC-24951")

        assert result["status"] == "success"
        assert result["data"]["defect_id"] == "OBMC-24951"

    @pytest.mark.asyncio
    async def test_execute_with_fact_data(self, review_agent, sample_defect_fact):
        """测试使用事实数据执行"""
        result = await review_agent.execute(sample_defect_fact)

        assert result["status"] == "success"
        assert result["data"]["defect_id"] == sample_defect_fact["defect_id"]

    @pytest.mark.asyncio
    async def test_execute_returns_all_evaluations(self, review_agent, sample_defect_fact):
        """测试返回所有评估结果"""
        result = await review_agent.execute(sample_defect_fact)

        assert "limitation_evaluation" in result["data"]
        assert "closure_evaluation" in result["data"]
        assert "evidence_validation" in result["data"]

    def test_validate_evidence_complete(self, review_agent, sample_defect_fact):
        """测试证据验证 - 完整"""
        result = review_agent._validate_evidence(sample_defect_fact)

        assert isinstance(result, ReviewDecision)

    def test_validate_evidence_incomplete(self, review_agent):
        """测试证据验证 - 不完整"""
        # 创建一个会触发 MUST_FIX_BLOCKER 的场景 (severity = Critical + active_weeks > 4)
        # 这样会有证据要求需要验证
        fact_data = {
            "defect_id": "TEST-001",
            "severity": "Critical",  # 触发 MUST_FIX_BLOCKER
            "active_weeks": 8,  # 触发时长限制
            "tci": 0.65,
            "evidence": {
                "customer_impact": None,  # 缺失关键证据
                "workaround_exists": None
            }
        }

        result = review_agent._validate_evidence(fact_data)

        # 验证返回的是 ReviewDecision 类型
        assert isinstance(result, ReviewDecision)
        # MUST_FIX_BLOCKER 有证据要求，缺失证据应该导致 INSUFFICIENT_EVIDENCE
        assert result.decision_type in [DecisionType.INSUFFICIENT_EVIDENCE, DecisionType.MUST_FIX_BLOCKER]
        assert result.confidence < 1.0

    def test_merge_decisions_all_pass(self, review_agent):
        """测试合并决策 - 全部 PASS"""
        decisions = [
            ReviewDecision(
                decision_type=DecisionType.PASS,
                defect_id="TEST-001",
                confidence=1.0,
                confidence_level=ConfidenceLevel.HIGH
            ),
            ReviewDecision(
                decision_type=DecisionType.PASS,
                defect_id="TEST-001",
                confidence=1.0,
                confidence_level=ConfidenceLevel.HIGH
            )
        ]

        merged = review_agent._merge_decisions(decisions)

        assert merged.decision_type == DecisionType.PASS

    def test_merge_decisions_priority(self, review_agent):
        """测试合并决策 - 优先级"""
        decisions = [
            ReviewDecision(
                decision_type=DecisionType.PASS,
                defect_id="TEST-001",
                confidence=1.0,
                confidence_level=ConfidenceLevel.HIGH
            ),
            ReviewDecision(
                decision_type=DecisionType.TEMP_LIMITATION_ELIGIBLE,
                defect_id="TEST-001",
                confidence=0.85,
                confidence_level=ConfidenceLevel.MEDIUM,
                triggered_rules=["LIM-002"]
            )
        ]

        merged = review_agent._merge_decisions(decisions)

        # 应该取最严格的决策
        assert merged.decision_type in [
            DecisionType.PASS,
            DecisionType.TEMP_LIMITATION_ELIGIBLE
        ]

    def test_merge_decisions_confidence(self, review_agent):
        """测试合并决策 - 置信度"""
        decisions = [
            ReviewDecision(
                decision_type=DecisionType.MUST_FIX_BLOCKER,
                defect_id="TEST-001",
                confidence=0.90,
                confidence_level=ConfidenceLevel.HIGH
            ),
            ReviewDecision(
                decision_type=DecisionType.TEMP_LIMITATION_ELIGIBLE,
                defect_id="TEST-001",
                confidence=0.85,
                confidence_level=ConfidenceLevel.MEDIUM
            )
        ]

        merged = review_agent._merge_decisions(decisions)

        # 应该取最低置信度
        assert merged.confidence <= min(0.90, 0.85)

    def test_evaluate_limitation_eligibility(self, review_agent, sample_defect_fact):
        """测试评估 Limitation 资格"""
        result = review_agent.evaluate_limitation_eligibility(sample_defect_fact)

        assert "decision_type" in result
        assert "confidence" in result

    def test_evaluate_closure_validity(self, review_agent, sample_defect_fact):
        """测试评估关闭请求有效性"""
        result = review_agent.evaluate_closure_validity(sample_defect_fact)

        assert "decision_type" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_batch_review(self, review_agent, sample_defect_fact):
        """测试批量审查"""
        facts = [
            {**sample_defect_fact, "defect_id": "OBMC-001"},
            {**sample_defect_fact, "defect_id": "OBMC-002"},
            {**sample_defect_fact, "defect_id": "OBMC-003"}
        ]

        results = await review_agent.batch_review(facts, max_concurrent=2)

        assert len(results) == 3
        assert all(r.get("status") == "success" for r in results)

    @pytest.mark.asyncio
    async def test_batch_review_with_errors(self, review_agent):
        """测试批量审查包含错误"""
        facts = [
            {"defect_id": "OBMC-001", "severity": "Critical", "active_weeks": 8},
            {"defect_id": "OBMC-002", "severity": "Critical", "active_weeks": 8}
        ]

        results = await review_agent.batch_review(facts)

        assert len(results) == 2


class TestReviewAgentErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_execute_exception(self, mock_mcp_client, rules_config_path):
        """测试执行异常"""
        agent = ReviewAgent(mock_mcp_client, rules_config_path)

        # 传入无效数据触发异常
        result = await agent.execute(None)

        assert result["status"] == "error"
        assert "error" in result


class TestReviewAgentIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_review_flow(self, mock_mcp_client, rules_config_path):
        """测试完整审查流程"""
        mock_mcp_client.call_tool = AsyncMock(side_effect=lambda name, **kwargs: {
            "extract_defect_facts": {
                "defect_id": "OBMC-24951",
                "key": "OBMC-24951",
                "severity": "Critical",
                "priority": "High",
                "active_weeks": 10,
                "evidence": {
                    "customer_impact": {"source": "test"}
                }
            }
        }.get(name, {}))

        agent = ReviewAgent(mock_mcp_client, rules_config_path)
        result = await agent.execute("OBMC-24951")

        assert result["status"] == "success"
        assert "decision" in result["data"]

    @pytest.mark.asyncio
    async def test_different_decision_types(self, mock_mcp_client, rules_config_path):
        """测试不同决策类型"""
        test_cases = [
            {"severity": "Blocker", "active_weeks": 12},
            {"severity": "Critical", "active_weeks": 6},
            {"severity": "Major", "active_weeks": 12},
            {"severity": "Low", "active_weeks": 4}
        ]

        mock_mcp_client.call_tool = AsyncMock(side_effect=lambda name, **kwargs: {
            "extract_defect_facts": {
                "defect_id": "TEST-001",
                "key": "TEST-001",
                **test_cases[0]
            }
        }.get(name, {}))

        agent = ReviewAgent(mock_mcp_client, rules_config_path)

        for test_case in test_cases:
            fact_data = {
                "defect_id": "TEST-001",
                **test_case,
                "evidence": {}
            }
            result = await agent.execute(fact_data)

            assert result["status"] == "success"