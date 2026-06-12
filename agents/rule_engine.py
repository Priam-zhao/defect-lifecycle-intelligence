"""
Rule Engine - 规则引擎

设计原则：Rules Before Reasoning
- 规则由配置文件定义
- LLM 仅用于解释，不可修改决策
- 所有合规决策由规则引擎生成

支持的条件操作符：
- ==: 相等
- !=: 不等
- in: 包含
- not_in: 不包含
- >: 大于
- <: 小于
- >=: 大于等于
- <=: 小于等于
- exists: 字段存在且非空
- not_exists: 字段不存在或为空
- and: 逻辑与
- or: 逻辑或
- not: 逻辑非
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field

# 导入 schemas 中的数据类型
from .schemas_compat import ReviewDecision, DecisionType, ConfidenceLevel


@dataclass
class Condition:
    """规则条件"""
    field: str
    operator: str
    value: Any = None


@dataclass
class Rule:
    """规则定义"""
    rule_id: str
    name: str
    decision: str = ""
    description: str = ""
    conditions: List[Union[Condition, Dict]] = field(default_factory=list)
    confidence_threshold: float = 0.90
    evidence_required: List[str] = field(default_factory=list)
    priority: int = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rule":
        """从字典创建 Rule"""
        return cls(
            rule_id=data.get("rule_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            conditions=data.get("condition", []),
            decision=data.get("decision", ""),
            confidence_threshold=data.get("confidence_threshold", 0.90),
            evidence_required=data.get("evidence_required", []),
            priority=data.get("priority", 1)
        )


class RuleEngine:
    """
    规则引擎 - Review Agent 的核心决策组件

    设计原则: Rules Before Reasoning
    - 规则由配置文件定义
    - LLM 仅用于解释，不可修改决策
    """

    def __init__(self, rules_config_path: Optional[str] = None):
        """
        初始化规则引擎

        Args:
            rules_config_path: 规则配置文件路径
        """
        if rules_config_path is None:
            # 默认路径
            base_dir = os.path.dirname(os.path.dirname(__file__))
            rules_config_path = os.path.join(base_dir, "mcp-server", "config", "rules.json")

        self.config_path = rules_config_path
        self.config = self._load_config()
        self._build_rule_index()

    def _load_config(self) -> Dict[str, Any]:
        """加载规则配置"""
        if not os.path.exists(self.config_path):
            return self._get_default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """返回默认配置（当配置文件不存在时）"""
        return {
            "limitation_rules": [],
            "closure_rules": [],
            "evidence_requirements": {},
            "confidence_thresholds": {
                "high": 0.90,
                "medium": 0.75,
                "low": 0.50
            }
        }

    def _build_rule_index(self):
        """构建规则索引以加快查询"""
        self._limitation_rules = [
            Rule.from_dict(r) for r in self.config.get("limitation_rules", [])
        ]
        self._limitation_rules.sort(key=lambda r: r.priority)

        self._closure_rules = [
            Rule.from_dict(r) for r in self.config.get("closure_rules", [])
        ]
        self._closure_rules.sort(key=lambda r: r.priority)

        self._evidence_requirements = self.config.get("evidence_requirements", {})
        self._confidence_thresholds = self.config.get("confidence_thresholds", {
            "high": 0.90,
            "medium": 0.75,
            "low": 0.50
        })

    def evaluate(
        self,
        defect_fact: Dict[str, Any],
        rule_type: str = "limitation_rules"
    ) -> ReviewDecision:
        """
        评估缺陷的合规性

        Args:
            defect_fact: DefectFact 数据
            rule_type: 规则类型 (limitation_rules, closure_rules)

        Returns:
            ReviewDecision 对象
        """
        # 选择规则集
        if rule_type == "limitation_rules":
            rules = self._limitation_rules
        elif rule_type == "closure_rules":
            rules = self._closure_rules
        else:
            rules = []

        # 按优先级执行规则
        for rule in rules:
            if self._check_rule(defect_fact, rule):
                return self._build_decision(defect_fact, rule)

        # 无匹配规则，返回默认 PASS
        return ReviewDecision(
            decision_type=DecisionType.PASS,
            defect_id=defect_fact.get("defect_id", defect_fact.get("key", "")),
            confidence=1.0,
            confidence_level=ConfidenceLevel.HIGH,
            evidence_links=[],
            reasoning="No rules matched - default pass",
            triggered_rules=[]
        )

    def _check_rule(self, fact: Dict[str, Any], rule: Rule) -> bool:
        """
        检查规则是否匹配

        Args:
            fact: 缺陷事实数据
            rule: 规则定义

        Returns:
            是否匹配
        """
        conditions = rule.conditions
        if not conditions:
            return False

        # 支持简单条件和复合条件
        if isinstance(conditions, dict):
            # 单个条件（可能是复合条件）
            return self._evaluate_condition(fact, conditions)
        elif isinstance(conditions, list):
            # 多个条件，需要全部满足
            return all(self._evaluate_condition(fact, c) for c in conditions)

        return False

    def _evaluate_condition(
        self,
        fact: Dict[str, Any],
        condition: Union[Dict, Condition]
    ) -> bool:
        """
        评估单个条件

        Args:
            fact: 缺陷事实数据
            condition: 条件定义

        Returns:
            条件是否满足
        """
        # 支持字典格式和 Condition 对象
        if isinstance(condition, Condition):
            cond = {"field": condition.field, "operator": condition.operator, "value": condition.value}
        else:
            cond = condition

        # 处理逻辑操作符
        if "and" in cond:
            return all(
                self._evaluate_condition(fact, c)
                for c in cond["and"]
            )

        if "or" in cond:
            return any(
                self._evaluate_condition(fact, c)
                for c in cond["or"]
            )

        if "not" in cond:
            return not self._evaluate_condition(fact, cond["not"])

        # 获取字段值
        field = cond.get("field", "")
        operator = cond.get("operator", "==")
        expected_value = cond.get("value")

        # 处理嵌套字段（如 evidence.customer_impact）
        field_value = self._get_field_value(fact, field)

        # 评估操作符
        if operator == "==":
            return field_value == expected_value
        elif operator == "!=":
            return field_value != expected_value
        elif operator == "in":
            return field_value in expected_value if expected_value else False
        elif operator == "not_in":
            return field_value not in expected_value if expected_value else True
        elif operator == ">":
            return field_value > expected_value if field_value is not None else False
        elif operator == "<":
            return field_value < expected_value if field_value is not None else False
        elif operator == ">=":
            return field_value >= expected_value if field_value is not None else False
        elif operator == "<=":
            return field_value <= expected_value if field_value is not None else False
        elif operator == "exists":
            return field_value is not None and field_value != ""
        elif operator == "not_exists":
            return field_value is None or field_value == ""

        return False

    def _get_field_value(self, fact: Dict[str, Any], field_path: str) -> Any:
        """
        获取嵌套字段值

        Args:
            fact: 缺陷事实数据
            field_path: 字段路径（如 evidence.customer_impact）

        Returns:
            字段值
        """
        parts = field_path.split(".")
        value = fact

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value

    def _build_decision(
        self,
        fact: Dict[str, Any],
        rule: Rule
    ) -> ReviewDecision:
        """
        构建审查决策

        Args:
            fact: 缺陷事实数据
            rule: 匹配的规则

        Returns:
            ReviewDecision 对象
        """
        defect_id = fact.get("defect_id", fact.get("key", ""))

        # 获取决策类型
        try:
            decision_type = DecisionType(rule.decision)
        except ValueError:
            decision_type = DecisionType.PASS

        # 计算置信度（基于证据完整性）
        confidence = self._calculate_confidence(fact, rule)

        # 获取置信度等级
        confidence_level = self._get_confidence_level(confidence)

        # 构建证据链接
        evidence_links = self._build_evidence_links(fact, rule)

        # 生成推理说明
        reasoning = self._generate_reasoning(fact, rule)

        return ReviewDecision(
            decision_type=decision_type,
            defect_id=defect_id,
            confidence=confidence,
            confidence_level=confidence_level,
            evidence_links=evidence_links,
            reasoning=reasoning,
            triggered_rules=[rule.rule_id]
        )

    def _calculate_confidence(
        self,
        fact: Dict[str, Any],
        rule: Rule
    ) -> float:
        """
        计算决策置信度

        基于：
        - 规则配置的阈值
        - 证据完整性
        - 异常检测结果

        Args:
            fact: 缺陷事实数据
            rule: 匹配的规则

        Returns:
            置信度 (0.0 - 1.0)
        """
        base_confidence = rule.confidence_threshold

        # 证据完整性调整
        evidence = fact.get("evidence", {})
        required_evidence = rule.evidence_required

        if required_evidence:
            evidence_count = sum(
                1 for e in required_evidence
                if evidence.get(e) is not None
            )
            evidence_ratio = evidence_count / len(required_evidence)
            evidence_bonus = evidence_ratio * 0.1  # 最多增加 0.1
        else:
            evidence_bonus = 0.0

        # 异常调整
        anomaly_penalty = 0.0
        if fact.get("has_critical_anomaly"):
            anomaly_penalty = 0.15
        elif fact.get("anomaly_count", 0) > 0:
            anomaly_penalty = min(fact["anomaly_count"] * 0.05, 0.10)

        confidence = base_confidence + evidence_bonus - anomaly_penalty
        return max(0.0, min(1.0, confidence))

    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """根据置信度值获取置信度等级"""
        if confidence >= self._confidence_thresholds.get("high", 0.90):
            return ConfidenceLevel.HIGH
        elif confidence >= self._confidence_thresholds.get("medium", 0.75):
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _build_evidence_links(
        self,
        fact: Dict[str, Any],
        rule: Rule
    ) -> List[str]:
        """
        构建证据链接

        Args:
            fact: 缺陷事实数据
            rule: 匹配的规则

        Returns:
            证据链接列表
        """
        evidence_links = []
        evidence = fact.get("evidence", {})

        for evidence_type in rule.evidence_required:
            evidence_item = evidence.get(evidence_type)
            if evidence_item:
                if isinstance(evidence_item, dict):
                    source = evidence_item.get("source", "unknown")
                    comment_id = evidence_item.get("comment_id", "")
                    evidence_links.append(f"{evidence_type} ({source}, ID: {comment_id})")
                else:
                    evidence_links.append(f"{evidence_type} (verified)")

        return evidence_links

    def _generate_reasoning(self, fact: Dict[str, Any], rule: Rule) -> str:
        """
        生成推理说明

        Args:
            fact: 缺陷事实数据
            rule: 匹配的规则

        Returns:
            推理说明字符串
        """
        defect_id = fact.get("defect_id", fact.get("key", ""))
        severity = fact.get("severity", "Unknown")
        active_weeks = fact.get("active_weeks", 0)

        reasoning_parts = [
            f"Defect {defect_id}",
            f"Rule: {rule.name}",
            f"Severity: {severity}",
            f"Active weeks: {active_weeks:.1f}"
        ]

        # 添加异常信息
        if fact.get("has_critical_anomaly"):
            reasoning_parts.append("Critical anomaly detected")

        return "; ".join(reasoning_parts)

    def validate_evidence_completeness(
        self,
        fact: Dict[str, Any],
        decision_type: str
    ) -> tuple[bool, List[str], float]:
        """
        验证证据完整性

        Args:
            fact: 缺陷事实数据
            decision_type: 决策类型

        Returns:
            (是否完整, 缺失证据列表, 完整性分数)
        """
        requirements = self._evidence_requirements.get(decision_type, [])

        if not requirements:
            return True, [], 1.0

        evidence = fact.get("evidence", {})
        missing = []
        present_count = 0

        for req in requirements:
            evidence_type = req.get("type") if isinstance(req, dict) else req
            if evidence.get(evidence_type) is None:
                missing.append(evidence_type)
            else:
                present_count += 1

        completeness = present_count / len(requirements) if requirements else 1.0
        return len(missing) == 0, missing, completeness

    def get_required_evidence(self, decision_type: str) -> List[Dict[str, Any]]:
        """
        获取决策类型所需的证据

        Args:
            decision_type: 决策类型

        Returns:
            证据要求列表
        """
        return self._evidence_requirements.get(decision_type, [])

    def evaluate_batch(
        self,
        defect_facts: List[Dict[str, Any]],
        rule_type: str = "limitation_rules"
    ) -> List[ReviewDecision]:
        """
        批量评估

        Args:
            defect_facts: 缺陷事实列表
            rule_type: 规则类型

        Returns:
            审查决策列表
        """
        return [self.evaluate(fact, rule_type) for fact in defect_facts]