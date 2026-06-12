"""
Review Agent - 合规审查 Agent

职责：
- 接收 Fact Agent 输出的 DefectFact
- 使用规则引擎进行合规验证
- 评估 Limitation 资格
- 验证证据完整性

设计原则：Rules Before Reasoning
- 规则引擎决定合规性，LLM 不可修改
- 只做合规判断，不做建议生成
"""

import asyncio
from typing import Dict, Any, List, Optional, Union

from .base import BaseAgent
from .rule_engine import RuleEngine


class ReviewAgent(BaseAgent):
    """
    Review Agent - 合规审查 Agent

    输入: DefectFact (来自 Fact Agent)
    输出: ReviewDecision (规则引擎生成)

    规则: Review Agent 仅通过规则引擎决策，LLM 不可修改决策
    """

    name = "ReviewAgent"
    version = "1.0.0"

    def __init__(self, mcp_client=None, rules_config_path: Optional[str] = None):
        """
        初始化 Review Agent

        Args:
            mcp_client: MCP 客户端（可选）
            rules_config_path: 规则配置文件路径（可选）
        """
        super().__init__(mcp_client)

        # 初始化规则引擎
        if rules_config_path is None:
            import os
            base_dir = os.path.dirname(os.path.dirname(__file__))
            rules_config_path = os.path.join(base_dir, "mcp-server", "config", "rules.json")

        self.rule_engine = RuleEngine(rules_config_path)

    async def execute(self, defect_fact: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """
        执行合规审查

        Args:
            defect_fact: Fact Agent 输出的事实数据（Dict）或 defect_id (str)

        Returns:
            标准化响应，包含 ReviewDecision
        """
        try:
            # 如果传入的是 defect_id，需要先获取 fact 数据
            if isinstance(defect_fact, str):
                defect_id = defect_fact
                fact_data = await self._call_mcp_tool(
                    "extract_defect_facts",
                    defect_id=defect_id
                )
            else:
                fact_data = defect_fact
                defect_id = fact_data.get("defect_id", fact_data.get("key", ""))

            # 1. 评估 Limitation 资格
            limitation_decision = self.rule_engine.evaluate(
                fact_data,
                "limitation_rules"
            )

            # 2. 评估关闭请求有效性
            closure_decision = self.rule_engine.evaluate(
                fact_data,
                "closure_rules"
            )

            # 3. 验证证据完整性
            evidence_validation = self._validate_evidence(fact_data)

            # 4. 综合决策（取最严格的决策）
            final_decision = self._merge_decisions([
                limitation_decision,
                closure_decision,
                evidence_validation
            ])

            return self._build_response(
                status="success",
                data={
                    "defect_id": defect_id,
                    "decision": final_decision.to_dict(),
                    "limitation_evaluation": limitation_decision.to_dict(),
                    "closure_evaluation": closure_decision.to_dict(),
                    "evidence_validation": evidence_validation.to_dict()
                },
                metadata={
                    "rule_engine_version": self.rule_engine.config.get("version", "1.0.0"),
                    "rules_applied": list(set(
                        limitation_decision.triggered_rules +
                        closure_decision.triggered_rules +
                        evidence_validation.triggered_rules
                    ))
                }
            )

        except Exception as e:
            return self._build_error_response(
                error_message=f"Review failed: {str(e)}",
                error_code="REVIEW_ERROR",
                details={"defect_id": defect_id if isinstance(defect_fact, str) else "unknown"}
            )

    def _validate_evidence(self, fact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证证据完整性

        根据规则引擎的 evidence_requirements 验证所需证据是否齐全

        Args:
            fact_data: 缺陷事实数据

        Returns:
            证据验证结果
        """
        from .schemas_compat import ReviewDecision, DecisionType, ConfidenceLevel

        # 尝试获取决策类型
        limitation_decision = self.rule_engine.evaluate(fact_data, "limitation_rules")
        decision_type = limitation_decision.decision_type.value

        # 验证证据完整性
        is_complete, missing_evidence, completeness = self.rule_engine.validate_evidence_completeness(
            fact_data,
            decision_type
        )

        if is_complete:
            return ReviewDecision(
                decision_type=DecisionType.PASS,
                defect_id=fact_data.get("defect_id", fact_data.get("key", "")),
                confidence=1.0,
                confidence_level=ConfidenceLevel.HIGH,
                evidence_links=[],
                reasoning=f"All required evidence present for {decision_type}",
                triggered_rules=[]
            )
        else:
            # 证据不完整，降低置信度
            confidence = max(0.5, completeness)
            return ReviewDecision(
                decision_type=DecisionType.INSUFFICIENT_EVIDENCE,
                defect_id=fact_data.get("defect_id", fact_data.get("key", "")),
                confidence=confidence,
                confidence_level=ConfidenceLevel.MEDIUM if confidence >= 0.75 else ConfidenceLevel.LOW,
                evidence_links=[],
                reasoning=f"Missing evidence: {', '.join(missing_evidence)}",
                triggered_rules=["evidence_validation"]
            )

    def _merge_decisions(
        self,
        decisions: List[Any]
    ) -> Any:
        """
        综合多个决策，取最严格的决策

        决策优先级（从高到低）：
        1. MUST_FIX_BLOCKER - 必须修复
        2. CRITICAL_SSRB_REVIEW - 需要 SSR B 审查
        3. INVALID_CLOSURE_REQUEST - 无效关闭请求
        4. INSUFFICIENT_EVIDENCE - 证据不足
        5. PERM_LIMITATION_ELIGIBLE - 永久限制
        6. TEMP_LIMITATION_ELIGIBLE - 临时限制
        7. PASS - 通过

        Args:
            decisions: ReviewDecision 列表

        Returns:
            最终决策
        """
        from .schemas_compat import ReviewDecision, DecisionType, ConfidenceLevel

        # 决策优先级映射
        priority_map = {
            DecisionType.MUST_FIX_BLOCKER: 1,
            DecisionType.CRITICAL_SSRB_REVIEW: 2,
            DecisionType.INVALID_CLOSURE_REQUEST: 3,
            DecisionType.INSUFFICIENT_EVIDENCE: 4,
            DecisionType.PERM_LIMITATION_ELIGIBLE: 5,
            DecisionType.TEMP_LIMITATION_ELIGIBLE: 6,
            DecisionType.PASS: 7
        }

        # 过滤掉 PASS（除非所有决策都是 PASS）
        non_pass_decisions = [d for d in decisions if d.decision_type != DecisionType.PASS]

        if not non_pass_decisions:
            # 所有决策都是 PASS
            return decisions[0]

        # 按优先级排序，取最严格的
        sorted_decisions = sorted(
            non_pass_decisions,
            key=lambda d: priority_map.get(d.decision_type, 99)
        )

        final_decision = sorted_decisions[0]

        # 综合置信度（取最低）
        min_confidence = min(d.confidence for d in decisions)

        # 收集所有触发的规则
        all_rules = []
        for d in decisions:
            all_rules.extend(d.triggered_rules)

        # 构建综合决策
        return ReviewDecision(
            decision_type=final_decision.decision_type,
            defect_id=final_decision.defect_id,
            confidence=min_confidence,
            confidence_level=final_decision.confidence_level,
            evidence_links=final_decision.evidence_links,
            reasoning=f"Multi-rule evaluation: {final_decision.reasoning}",
            triggered_rules=list(set(all_rules))
        )

    async def batch_review(
        self,
        defect_facts: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        批量执行合规审查

        Args:
            defect_facts: 缺陷事实列表
            max_concurrent: 最大并发数

        Returns:
            批量审查结果列表
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def review_with_semaphore(fact: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self.execute(fact)

        # 并发执行
        tasks = [review_with_semaphore(fact) for fact in defect_facts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "defect_id": defect_facts[i].get("defect_id", "unknown"),
                    "status": "error",
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        return processed_results

    def evaluate_limitation_eligibility(
        self,
        defect_fact: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        专门评估 Limitation 资格

        用于快速判断缺陷是否符合 Limitation 条件

        Args:
            defect_fact: 缺陷事实数据

        Returns:
            评估结果
        """
        decision = self.rule_engine.evaluate(defect_fact, "limitation_rules")
        return decision.to_dict()

    def evaluate_closure_validity(
        self,
        defect_fact: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        专门评估关闭请求有效性

        用于快速判断关闭请求是否有效

        Args:
            defect_fact: 缺陷事实数据

        Returns:
            评估结果
        """
        decision = self.rule_engine.evaluate(defect_fact, "closure_rules")
        return decision.to_dict()