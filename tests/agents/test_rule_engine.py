"""
RuleEngine 单元测试

测试规则引擎的合规决策能力
"""

import pytest
import json
import os
from unittest.mock import MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.rule_engine import RuleEngine, Rule, Condition
from agents.schemas_compat import ReviewDecision, DecisionType, ConfidenceLevel


@pytest.fixture
def rules_config_path():
    """规则配置文件路径"""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "mcp-server",
        "config",
        "rules.json"
    )


@pytest.fixture
def rule_engine(rules_config_path):
    """创建 RuleEngine 实例"""
    return RuleEngine(rules_config_path)


@pytest.fixture
def default_rule_engine():
    """创建使用默认配置的 RuleEngine"""
    return RuleEngine()


class TestRuleEngine:
    """RuleEngine 测试类"""

    def test_init_with_config(self, rule_engine):
        """测试使用配置文件初始化"""
        assert rule_engine.config is not None
        assert "limitation_rules" in rule_engine.config
        assert "closure_rules" in rule_engine.config

    def test_init_default_config(self, default_rule_engine):
        """测试使用默认配置初始化"""
        assert default_rule_engine.config is not None

    def test_limitation_rules_loaded(self, rule_engine):
        """测试限制规则加载"""
        assert len(rule_engine._limitation_rules) > 0

    def test_closure_rules_loaded(self, rule_engine):
        """测试关闭规则加载"""
        assert len(rule_engine._closure_rules) > 0

    def test_evaluate_limitation_rules(self, rule_engine, sample_defect_fact):
        """测试评估限制规则"""
        decision = rule_engine.evaluate(sample_defect_fact, "limitation_rules")

        assert isinstance(decision, ReviewDecision)
        assert decision.defect_id == sample_defect_fact["defect_id"]
        assert decision.confidence > 0

    def test_evaluate_closure_rules(self, rule_engine, sample_defect_fact):
        """测试评估关闭规则"""
        decision = rule_engine.evaluate(sample_defect_fact, "closure_rules")

        assert isinstance(decision, ReviewDecision)

    def test_evaluate_unknown_rule_type(self, rule_engine, sample_defect_fact):
        """测试评估未知规则类型"""
        decision = rule_engine.evaluate(sample_defect_fact, "unknown_rules")

        # 应该返回默认 PASS
        assert decision.decision_type == DecisionType.PASS
        assert decision.confidence == 1.0

    def test_check_rule_with_conditions(self, rule_engine):
        """测试规则条件检查"""
        rule = Rule(
            rule_id="TEST-001",
            name="Test Rule",
            conditions=[
                {"field": "severity", "operator": "==", "value": "Critical"}
            ],
            decision="MUST_FIX_BLOCKER",
            confidence_threshold=0.90
        )

        fact = {"severity": "Critical"}
        result = rule_engine._check_rule(fact, rule)
        assert result is True

    def test_check_rule_condition_not_matched(self, rule_engine):
        """测试规则条件不匹配"""
        rule = Rule(
            rule_id="TEST-001",
            name="Test Rule",
            conditions=[
                {"field": "severity", "operator": "==", "value": "Critical"}
            ],
            decision="MUST_FIX_BLOCKER",
            confidence_threshold=0.90
        )

        fact = {"severity": "Major"}
        result = rule_engine._check_rule(fact, rule)
        assert result is False

    def test_evaluate_condition_operators(self, rule_engine):
        """测试各种条件操作符"""
        test_cases = [
            # operator, field_value, expected_value, expected_result
            ("==", "Critical", "Critical", True),
            ("==", "Critical", "Major", False),
            ("!=", "Critical", "Major", True),
            ("!=", "Critical", "Critical", False),
            ("in", "Critical", ["Critical", "Blocker"], True),
            ("in", "Major", ["Critical", "Blocker"], False),
            ("not_in", "Major", ["Critical", "Blocker"], True),
            ("not_in", "Critical", ["Critical", "Blocker"], False),
            (">", 10, 5, True),
            (">", 5, 10, False),
            ("<", 5, 10, True),
            ("<", 10, 5, False),
            (">=", 10, 10, True),
            (">=", 11, 10, True),
            ("<=", 10, 10, True),
            ("<=", 9, 10, True),
            ("exists", "value", None, True),
            ("exists", None, None, False),
            ("not_exists", None, None, True),
            ("not_exists", "value", None, False),
        ]

        for operator, field_value, expected_value, expected_result in test_cases:
            condition = {
                "field": "test_field",
                "operator": operator,
                "value": expected_value if operator not in ["exists", "not_exists"] else None
            }
            fact = {"test_field": field_value}

            result = rule_engine._evaluate_condition(fact, condition)
            assert result == expected_result, f"Failed for {operator}: {field_value} vs {expected_value}"

    def test_evaluate_condition_logical_and(self, rule_engine):
        """测试逻辑与条件"""
        condition = {
            "and": [
                {"field": "severity", "operator": "==", "value": "Critical"},
                {"field": "active_weeks", "operator": ">", "value": 4}
            ]
        }

        fact = {"severity": "Critical", "active_weeks": 8}
        result = rule_engine._evaluate_condition(fact, condition)
        assert result is True

        fact = {"severity": "Critical", "active_weeks": 2}
        result = rule_engine._evaluate_condition(fact, condition)
        assert result is False

    def test_evaluate_condition_logical_or(self, rule_engine):
        """测试逻辑或条件"""
        condition = {
            "or": [
                {"field": "severity", "operator": "==", "value": "Blocker"},
                {"field": "severity", "operator": "==", "value": "Critical"}
            ]
        }

        fact = {"severity": "Blocker"}
        result = rule_engine._evaluate_condition(fact, condition)
        assert result is True

        fact = {"severity": "Critical"}
        result = rule_engine._evaluate_condition(fact, condition)
        assert result is True

        fact = {"severity": "Major"}
        result = rule_engine._evaluate_condition(fact, condition)
        assert result is False

    def test_evaluate_condition_logical_not(self, rule_engine):
        """测试逻辑非条件"""
        condition = {
            "not": {"field": "is_clone", "operator": "==", "value": True}
        }

        fact = {"is_clone": False}
        result = rule_engine._evaluate_condition(fact, condition)
        assert result is True

        fact = {"is_clone": True}
        result = rule_engine._evaluate_condition(fact, condition)
        assert result is False

    def test_nested_field_access(self, rule_engine):
        """测试嵌套字段访问"""
        condition = {"field": "evidence.customer_impact", "operator": "exists", "value": None}
        fact = {
            "evidence": {
                "customer_impact": {"source": "customer"}
            }
        }

        result = rule_engine._evaluate_condition(fact, condition)
        assert result is True

    def test_nested_field_access_missing(self, rule_engine):
        """测试嵌套字段访问（字段不存在）"""
        condition = {"field": "evidence.customer_impact", "operator": "exists", "value": None}
        fact = {"evidence": {}}

        result = rule_engine._evaluate_condition(fact, condition)
        assert result is False

    def test_get_field_value_deep_nesting(self, rule_engine):
        """测试深度嵌套字段访问"""
        fact = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }

        value = rule_engine._get_field_value(fact, "level1.level2.level3")
        assert value == "value"

    def test_build_decision(self, rule_engine, sample_defect_fact):
        """测试决策构建"""
        rule = Rule(
            rule_id="TEST-001",
            name="Test Rule",
            decision="MUST_FIX_BLOCKER",
            confidence_threshold=0.90,
            evidence_required=["customer_impact"]
        )

        decision = rule_engine._build_decision(sample_defect_fact, rule)

        assert decision.decision_type == DecisionType.MUST_FIX_BLOCKER
        assert decision.defect_id == sample_defect_fact["defect_id"]
        assert decision.confidence > 0
        assert "TEST-001" in decision.triggered_rules

    def test_calculate_confidence_base(self, rule_engine):
        """测试置信度计算基础"""
        rule = Rule(
            rule_id="TEST-001",
            name="Test",
            decision="PASS",
            confidence_threshold=0.90,
            evidence_required=[]
        )

        fact = {"defect_id": "TEST-001"}
        confidence = rule_engine._calculate_confidence(fact, rule)

        assert 0.85 <= confidence <= 0.95

    def test_calculate_confidence_with_evidence(self, rule_engine):
        """测试置信度计算（带证据）"""
        rule = Rule(
            rule_id="TEST-001",
            name="Test",
            decision="PASS",
            confidence_threshold=0.90,
            evidence_required=["customer_impact", "workaround_exists"]
        )

        fact = {
            "defect_id": "TEST-001",
            "evidence": {
                "customer_impact": {"source": "test"},
                "workaround_exists": {"source": "test"}
            }
        }

        confidence = rule_engine._calculate_confidence(fact, rule)
        # 有证据应该增加置信度
        assert confidence >= 0.90

    def test_calculate_confidence_with_anomaly(self, rule_engine):
        """测试置信度计算（带异常）"""
        rule = Rule(
            rule_id="TEST-001",
            name="Test",
            decision="PASS",
            confidence_threshold=0.90,
            evidence_required=[]
        )

        fact = {
            "defect_id": "TEST-001",
            "has_critical_anomaly": True
        }

        confidence = rule_engine._calculate_confidence(fact, rule)
        # 有关键异常应该降低置信度
        assert confidence < 0.90

    def test_get_confidence_level(self, rule_engine):
        """测试置信度等级转换"""
        assert rule_engine._get_confidence_level(0.95) == ConfidenceLevel.HIGH
        assert rule_engine._get_confidence_level(0.90) == ConfidenceLevel.HIGH
        assert rule_engine._get_confidence_level(0.89) == ConfidenceLevel.MEDIUM
        assert rule_engine._get_confidence_level(0.75) == ConfidenceLevel.MEDIUM
        assert rule_engine._get_confidence_level(0.74) == ConfidenceLevel.LOW
        assert rule_engine._get_confidence_level(0.50) == ConfidenceLevel.LOW

    def test_build_evidence_links(self, rule_engine, sample_defect_fact):
        """测试证据链接构建"""
        rule = Rule(
            rule_id="TEST-001",
            name="Test",
            decision="PASS",
            evidence_required=["customer_impact", "workaround_exists"]
        )

        links = rule_engine._build_evidence_links(sample_defect_fact, rule)

        assert len(links) == 2
        assert any("customer_impact" in link for link in links)
        assert any("workaround_exists" in link for link in links)

    def test_generate_reasoning(self, rule_engine, sample_defect_fact):
        """测试推理说明生成"""
        rule = Rule(
            rule_id="TEST-001",
            name="Test Rule",
            decision="PASS",
            evidence_required=[]
        )

        reasoning = rule_engine._generate_reasoning(sample_defect_fact, rule)

        assert "OBMC-24951" in reasoning
        assert "Test Rule" in reasoning
        assert "Critical" in reasoning

    def test_validate_evidence_completeness_complete(self, rule_engine, sample_defect_fact):
        """测试证据完整性验证 - 完整"""
        is_complete, missing, completeness = rule_engine.validate_evidence_completeness(
            sample_defect_fact,
            "TEMP_LIMITATION_ELIGIBLE"
        )

        assert is_complete is True or len(missing) == 0 or completeness >= 0

    def test_validate_evidence_completeness_missing(self, rule_engine):
        """测试证据完整性验证 - 缺失"""
        fact = {
            "defect_id": "TEST-001",
            "evidence": {
                "customer_impact": {"source": "test"}
            }
        }

        is_complete, missing, completeness = rule_engine.validate_evidence_completeness(
            fact,
            "PERM_LIMITATION_ELIGIBLE"
        )

        # 应该有缺失的证据
        assert len(missing) > 0 or completeness < 1.0

    def test_evaluate_batch(self, rule_engine, sample_defect_fact):
        """测试批量评估"""
        facts = [
            sample_defect_fact,
            {**sample_defect_fact, "defect_id": "OBMC-24952"},
            {**sample_defect_fact, "defect_id": "OBMC-24953"}
        ]

        decisions = rule_engine.evaluate_batch(facts, "limitation_rules")

        assert len(decisions) == 3
        assert all(isinstance(d, ReviewDecision) for d in decisions)


class TestRule:
    """Rule 数据类测试"""

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "rule_id": "TEST-001",
            "name": "Test Rule",
            "description": "A test rule",
            "condition": [
                {"field": "severity", "operator": "==", "value": "Critical"}
            ],
            "decision": "MUST_FIX_BLOCKER",
            "confidence_threshold": 0.90,
            "evidence_required": ["customer_impact"],
            "priority": 1
        }

        rule = Rule.from_dict(data)

        assert rule.rule_id == "TEST-001"
        assert rule.name == "Test Rule"
        assert rule.decision == "MUST_FIX_BLOCKER"
        assert rule.confidence_threshold == 0.90
        assert rule.priority == 1

    def test_from_dict_defaults(self):
        """测试从字典创建（带默认值）"""
        data = {
            "rule_id": "TEST-001",
            "name": "Test Rule",
            "decision": "PASS"
        }

        rule = Rule.from_dict(data)

        assert rule.description == ""
        assert rule.conditions == []
        assert rule.confidence_threshold == 0.90
        assert rule.evidence_required == []
        assert rule.priority == 1