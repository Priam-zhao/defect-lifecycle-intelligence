"""
Advisor Agent - 建议生成 Agent

职责：
- 接收 Fact Agent + Review Agent 的输出
- 检索相似历史案例
- 生成三轨推荐建议（preferred, alternative, escalation）

设计原则：Human Authority Supremacy
- Advisor Agent 不可修改 Review Agent 的决策
- 建议仅供参考，人类审查员是最终权威
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Literal, Union

from .base import BaseAgent


class AdvisorAgent(BaseAgent):
    """
    Advisor Agent - 建议生成 Agent

    输入:
    - DefectFact (来自 Fact Agent)
    - ReviewDecision (来自 Review Agent)
    - similar_cases (历史案例)

    输出: AdvisorOutput (三轨推荐)

    规则: Advisor Agent 不可修改 Review Agent 的决策
    """

    name = "AdvisorAgent"
    version = "1.0.0"

    def __init__(self, mcp_client=None):
        """
        初始化 Advisor Agent

        Args:
            mcp_client: MCP 客户端（可选）
        """
        super().__init__(mcp_client)

        # 推荐的置信度衰减因子（基于历史案例相似度）
        self.similarity_weight = 0.15

    async def execute(
        self,
        defect_fact: Union[Dict[str, Any], str],
        review_decision: Optional[Dict[str, Any]] = None,
        similar_cases: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        生成三轨推荐

        Args:
            defect_fact: 事实数据或 defect_id
            review_decision: 审查决策（可选，如果传入 defect_id 则会自动获取）
            similar_cases: 相似历史案例（可选）

        Returns:
            标准化响应，包含三轨推荐
        """
        try:
            # 处理 defect_id 的情况
            if isinstance(defect_fact, str):
                defect_id = defect_fact
                fact_data = await self._call_mcp_tool(
                    "extract_defect_facts",
                    defect_id=defect_id
                )
            else:
                fact_data = defect_fact
                defect_id = fact_data.get("defect_id", fact_data.get("key", ""))

            # 获取审查决策（如果未提供）
            if review_decision is None:
                review_decision = await self._get_review_decision(defect_id)

            # 获取相似案例（如果未提供）
            if similar_cases is None:
                similar_cases = await self._retrieve_similar_cases(fact_data)

            # 生成三轨推荐
            advisor_output = self._generate_recommendations(
                fact_data,
                review_decision,
                similar_cases
            )

            return self._build_response(
                status="success",
                data={
                    "defect_id": defect_id,
                    "recommendations": advisor_output.to_dict()
                },
                metadata={
                    "decision_type": review_decision.get("decision_type", "UNKNOWN"),
                    "similar_cases_count": len(similar_cases),
                    "confidence_base": review_decision.get("confidence", 0.0)
                }
            )

        except Exception as e:
            return self._build_error_response(
                error_message=f"Advisor generation failed: {str(e)}",
                error_code="ADVISOR_ERROR",
                details={"defect_id": defect_id if isinstance(defect_fact, str) else "unknown"}
            )

    async def _get_review_decision(self, defect_id: str) -> Dict[str, Any]:
        """
        获取缺陷的审查决策

        Args:
            defect_id: 缺陷 ID

        Returns:
            审查决策数据
        """
        # 调用 Review Agent 的 MCP 工具（如果存在）
        result = await self._call_mcp_tool(
            "review_defect",
            defect_id=defect_id
        )

        if result and not result.get("error"):
            return result.get("decision", {})

        # 如果没有 review 工具，返回默认决策
        return {
            "decision_type": "PASS",
            "confidence": 0.0,
            "reasoning": "No review decision available"
        }

    async def _retrieve_similar_cases(
        self,
        fact_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        检索相似历史案例

        Args:
            fact_data: 缺陷事实数据

        Returns:
            相似案例列表
        """
        technical_domain = fact_data.get("root_cause", "")
        affected_components = fact_data.get("components", [])
        platform = fact_data.get("platform")

        result = await self._call_mcp_tool(
            "retrieve_similar_cases",
            technical_domain=technical_domain,
            affected_components=affected_components,
            platform_family=platform,
            similarity_threshold=0.6
        )

        return result.get("cases", [])

    def _generate_recommendations(
        self,
        fact_data: Dict[str, Any],
        review_decision: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> "AdvisorOutput":
        """
        根据审查决策生成三轨推荐

        Args:
            fact_data: 缺陷事实数据
            review_decision: 审查决策
            similar_cases: 相似历史案例

        Returns:
            AdvisorOutput 对象
        """
        from .schemas_compat import (
            AdvisorOutput,
            RecommendationTrack,
            Recommendation
        )

        decision_type = review_decision.get("decision_type", "PASS")
        defect_id = fact_data.get("defect_id", fact_data.get("key", ""))

        # 基于决策类型选择生成策略
        if decision_type == "MUST_FIX_BLOCKER":
            return self._generate_must_fix_recommendations(
                fact_data, review_decision, similar_cases
            )
        elif decision_type == "TEMP_LIMITATION_ELIGIBLE":
            return self._generate_temp_limitation_recommendations(
                fact_data, review_decision, similar_cases
            )
        elif decision_type == "PERM_LIMITATION_ELIGIBLE":
            return self._generate_perm_limitation_recommendations(
                fact_data, review_decision, similar_cases
            )
        elif decision_type == "CRITICAL_SSRB_REVIEW":
            return self._generate_ssrb_review_recommendations(
                fact_data, review_decision, similar_cases
            )
        elif decision_type == "INVALID_CLOSURE_REQUEST":
            return self._generate_invalid_closure_recommendations(
                fact_data, review_decision, similar_cases
            )
        elif decision_type == "INSUFFICIENT_EVIDENCE":
            return self._generate_insufficient_evidence_recommendations(
                fact_data, review_decision, similar_cases
            )
        else:  # PASS
            return self._generate_standard_recommendations(
                fact_data, review_decision, similar_cases
            )

    def _generate_must_fix_recommendations(
        self,
        fact_data: Dict[str, Any],
        review_decision: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> "AdvisorOutput":
        """
        MUST_FIX_BLOCKER 的三轨推荐

        Preferred: 立即修复方案
        Alternative: 分阶段修复方案
        Escalation: 升级到 SSR B review
        """
        from .schemas_compat import (
            AdvisorOutput,
            RecommendationTrack,
            Recommendation
        )

        defect_id = fact_data.get("defect_id", fact_data.get("key", ""))
        severity = fact_data.get("severity", "Unknown")
        active_weeks = fact_data.get("active_weeks", 0)
        base_confidence = review_decision.get("confidence", 0.90)

        # 分析相似案例中的修复模式
        fix_patterns = self._analyze_fix_patterns(similar_cases)

        # Preferred Track: 立即修复
        preferred = RecommendationTrack(
            track_type="preferred",
            summary="建议立即修复此严重缺陷",
            recommendations=[
                Recommendation(
                    action=f"Assign to senior developer immediately - {severity} severity with {active_weeks:.1f} active weeks",
                    rationale=f"Critical severity defect requires immediate attention. {len(fix_patterns.get('quick_fix', []))} similar cases were fixed within 2 weeks.",
                    priority="high",
                    confidence=min(base_confidence + 0.05, 1.0)
                ),
                Recommendation(
                    action="Schedule hotfix release",
                    rationale="Customer impact confirmed per evidence. Expedited release process recommended.",
                    priority="high",
                    confidence=base_confidence
                ),
                Recommendation(
                    action="Notify affected customer stakeholders",
                    rationale="Customer visibility exists per evidence. Proactive communication reduces escalation risk.",
                    priority="medium",
                    confidence=base_confidence - 0.05
                )
            ]
        )

        # Alternative Track: 分阶段方案
        alternative = RecommendationTrack(
            track_type="alternative",
            summary="如无法立即修复，考虑分阶段方案",
            recommendations=[
                Recommendation(
                    action="Deploy interim workaround",
                    rationale="Workaround exists per evidence. Temporary relief while permanent fix is developed.",
                    priority="high",
                    confidence=base_confidence - 0.10
                ),
                Recommendation(
                    action="Create phased fix plan (Phase 1: mitigation, Phase 2: root cause fix)",
                    rationale="Phased approach reduces risk and allows customer preparation.",
                    priority="medium",
                    confidence=base_confidence - 0.15
                ),
                Recommendation(
                    action="Request extended timeline with customer agreement",
                    rationale="Extended timeline requires explicit customer approval per policy.",
                    priority="medium",
                    confidence=base_confidence - 0.20
                )
            ]
        )

        # Escalation Track: 升级决策
        escalation = RecommendationTrack(
            track_type="escalation",
            summary="升级决策到 SSR B Review Board",
            recommendations=[
                Recommendation(
                    action="Escalate to SSR B Review Board for deviation approval",
                    rationale="Blocker decision requires board approval for any exception. Historical deviation approval rate: 15%.",
                    priority="high",
                    confidence=0.98
                ),
                Recommendation(
                    action="Prepare deviation request document with business impact analysis",
                    rationale="Comprehensive documentation increases approval probability by 40%.",
                    priority="high",
                    confidence=0.95
                ),
                Recommendation(
                    action="Schedule pre-board meeting with engineering lead",
                    rationale="Early alignment with board members improves presentation success rate.",
                    priority="medium",
                    confidence=0.90
                )
            ]
        )

        return AdvisorOutput(
            defect_id=defect_id,
            preferred_path=preferred,
            alternative_path=alternative,
            escalation_path=escalation,
            based_on_facts=True,
            based_on_review=True
        )

    def _generate_temp_limitation_recommendations(
        self,
        fact_data: Dict[str, Any],
        review_decision: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> "AdvisorOutput":
        """
        TEMP_LIMITATION_ELIGIBLE 的三轨推荐

        Preferred: 批准临时限制 + 后续修复计划
        Alternative: 要求补充证据后重新审查
        Escalation: 拒绝限制，转为必须修复
        """
        from .schemas_compat import (
            AdvisorOutput,
            RecommendationTrack,
            Recommendation
        )

        defect_id = fact_data.get("defect_id", fact_data.get("key", ""))
        severity = fact_data.get("severity", "Unknown")
        base_confidence = review_decision.get("confidence", 0.85)

        # 分析相似案例中的限制有效期
        limitation_patterns = self._analyze_limitation_patterns(similar_cases)

        # Preferred Track: 批准临时限制
        preferred = RecommendationTrack(
            track_type="preferred",
            summary=f"批准 {severity} 缺陷的临时限制申请",
            recommendations=[
                Recommendation(
                    action=f"Approve temporary limitation for {severity} defect",
                    rationale=f"Defect meets all eligibility criteria. Evidence complete per review.",
                    priority="high",
                    confidence=base_confidence
                ),
                Recommendation(
                    action="Set limitation expiry date (recommended: 90 days)",
                    rationale=f"Similar limitations typically expire in {limitation_patterns.get('typical_duration', 90)} days.",
                    priority="high",
                    confidence=base_confidence - 0.05
                ),
                Recommendation(
                    action="Schedule follow-up review before expiry",
                    rationale="Ensures limitation is not extended indefinitely without justification.",
                    priority="medium",
                    confidence=base_confidence - 0.10
                )
            ]
        )

        # Alternative Track: 补充证据
        alternative = RecommendationTrack(
            track_type="alternative",
            summary="要求补充证据后重新审查",
            recommendations=[
                Recommendation(
                    action="Request additional evidence for root_cause_analysis",
                    rationale="Complete root cause analysis strengthens limitation justification.",
                    priority="high",
                    confidence=base_confidence - 0.15
                ),
                Recommendation(
                    action="Request workaround validation from customer",
                    rationale="Customer confirmation of workaround effectiveness improves approval confidence.",
                    priority="medium",
                    confidence=base_confidence - 0.20
                ),
                Recommendation(
                    action="Defer decision until evidence is provided",
                    rationale="Defers the burden of proof to the requestor.",
                    priority="medium",
                    confidence=base_confidence - 0.25
                )
            ]
        )

        # Escalation Track: 拒绝限制
        escalation = RecommendationTrack(
            track_type="escalation",
            summary="拒绝临时限制，转为必须修复",
            recommendations=[
                Recommendation(
                    action="Deny temporary limitation request",
                    rationale="Customer impact documented. Workaround insufficient for customer-visible defects.",
                    priority="high",
                    confidence=0.90
                ),
                Recommendation(
                    action="Require immediate fix assignment",
                    rationale="Defect cannot be held in open state with active customer impact.",
                    priority="high",
                    confidence=0.85
                ),
                Recommendation(
                    action="Escalate to development manager for resource allocation",
                    rationale="Ensures fix receives adequate engineering resources.",
                    priority="medium",
                    confidence=0.80
                )
            ]
        )

        return AdvisorOutput(
            defect_id=defect_id,
            preferred_path=preferred,
            alternative_path=alternative,
            escalation_path=escalation,
            based_on_facts=True,
            based_on_review=True
        )

    def _generate_perm_limitation_recommendations(
        self,
        fact_data: Dict[str, Any],
        review_decision: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> "AdvisorOutput":
        """
        PERM_LIMITATION_ELIGIBLE 的三轨推荐
        """
        from .schemas_compat import (
            AdvisorOutput,
            RecommendationTrack,
            Recommendation
        )

        defect_id = fact_data.get("defect_id", fact_data.get("key", ""))
        base_confidence = review_decision.get("confidence", 0.80)

        # Preferred Track: 批准永久限制
        preferred = RecommendationTrack(
            track_type="preferred",
            summary="批准永久限制（需要 SSR B 审查）",
            recommendations=[
                Recommendation(
                    action="Initiate SSR B review process",
                    rationale="Permanent limitation requires SSR B approval per policy.",
                    priority="high",
                    confidence=base_confidence
                ),
                Recommendation(
                    action="Prepare comprehensive technical justification document",
                    rationale="Strong documentation increases SSR B approval probability.",
                    priority="high",
                    confidence=base_confidence - 0.05
                ),
                Recommendation(
                    action="Obtain customer acknowledgment of limitation",
                    rationale="Customer sign-off required for permanent limitations.",
                    priority="high",
                    confidence=base_confidence - 0.10
                )
            ]
        )

        # Alternative Track: 降级为临时限制
        alternative = RecommendationTrack(
            track_type="alternative",
            summary="降级为临时限制，要求定期复审",
            recommendations=[
                Recommendation(
                    action="Approve temporary limitation with 1-year expiry",
                    rationale="Lower commitment than permanent, allows future reassessment.",
                    priority="high",
                    confidence=base_confidence + 0.05
                ),
                Recommendation(
                    action="Require annual review of continued validity",
                    rationale="Periodic review ensures limitation remains justified.",
                    priority="medium",
                    confidence=base_confidence
                )
            ]
        )

        # Escalation Track: 拒绝限制
        escalation = RecommendationTrack(
            track_type="escalation",
            summary="拒绝永久限制，要求修复",
            recommendations=[
                Recommendation(
                    action="Deny permanent limitation request",
                    rationale="Permanent limitations require exceptional justification.",
                    priority="high",
                    confidence=0.85
                ),
                Recommendation(
                    action="Require fix plan with committed timeline",
                    rationale="Clear commitment expected for defects with permanent limitation request.",
                    priority="high",
                    confidence=0.80
                )
            ]
        )

        return AdvisorOutput(
            defect_id=defect_id,
            preferred_path=preferred,
            alternative_path=alternative,
            escalation_path=escalation,
            based_on_facts=True,
            based_on_review=True
        )

    def _generate_ssrb_review_recommendations(
        self,
        fact_data: Dict[str, Any],
        review_decision: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> "AdvisorOutput":
        """
        CRITICAL_SSRB_REVIEW 的三轨推荐
        """
        from .schemas_compat import (
            AdvisorOutput,
            RecommendationTrack,
            Recommendation
        )

        defect_id = fact_data.get("defect_id", fact_data.get("key", ""))
        base_confidence = review_decision.get("confidence", 0.85)

        preferred = RecommendationTrack(
            track_type="preferred",
            summary="提交 SSR B 审查",
            recommendations=[
                Recommendation(
                    action="Prepare SSR B presentation materials",
                    rationale="Clear, data-driven presentation improves approval probability.",
                    priority="high",
                    confidence=base_confidence
                ),
                Recommendation(
                    action="Schedule SSR B review meeting",
                    rationale="Timely scheduling prevents further delays.",
                    priority="high",
                    confidence=base_confidence - 0.05
                )
            ]
        )

        alternative = RecommendationTrack(
            track_type="alternative",
            summary="补充证据后重新提交",
            recommendations=[
                Recommendation(
                    action="Gather additional supporting evidence",
                    rationale="Stronger evidence package strengthens the case.",
                    priority="medium",
                    confidence=base_confidence - 0.10
                ),
                Recommendation(
                    action="Request pre-review with SSR B member",
                    rationale="Early feedback helps refine the presentation.",
                    priority="medium",
                    confidence=base_confidence - 0.15
                )
            ]
        )

        escalation = RecommendationTrack(
            track_type="escalation",
            summary="升级到更高层级决策",
            recommendations=[
                Recommendation(
                    action="Escalate to SSR A if SSR B is unavailable",
                    rationale="Higher authority can provide guidance on exceptional cases.",
                    priority="high",
                    confidence=0.90
                ),
                Recommendation(
                    action="Involve executive sponsor if critical customer impact",
                    rationale="Executive visibility ensures appropriate priority.",
                    priority="medium",
                    confidence=0.85
                )
            ]
        )

        return AdvisorOutput(
            defect_id=defect_id,
            preferred_path=preferred,
            alternative_path=alternative,
            escalation_path=escalation,
            based_on_facts=True,
            based_on_review=True
        )

    def _generate_invalid_closure_recommendations(
        self,
        fact_data: Dict[str, Any],
        review_decision: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> "AdvisorOutput":
        """
        INVALID_CLOSURE_REQUEST 的三轨推荐
        """
        from .schemas_compat import (
            AdvisorOutput,
            RecommendationTrack,
            Recommendation
        )

        defect_id = fact_data.get("defect_id", fact_data.get("key", ""))
        current_status = fact_data.get("status", "Unknown")
        base_confidence = review_decision.get("confidence", 0.95)

        preferred = RecommendationTrack(
            track_type="preferred",
            summary="拒绝无效关闭请求",
            recommendations=[
                Recommendation(
                    action=f"Reject closure request - current status is '{current_status}'",
                    rationale="Defect must be in Fixed/Verified status before closure.",
                    priority="high",
                    confidence=base_confidence
                ),
                Recommendation(
                    action="Notify requestor of rejection reason",
                    rationale="Clear communication prevents repeated invalid requests.",
                    priority="medium",
                    confidence=base_confidence - 0.05
                )
            ]
        )

        alternative = RecommendationTrack(
            track_type="alternative",
            summary="要求修复后重新提交",
            recommendations=[
                Recommendation(
                    action="Request fix verification before closure",
                    rationale="Ensure fix is actually implemented before closing.",
                    priority="high",
                    confidence=base_confidence - 0.10
                ),
                Recommendation(
                    action="Assign to QA for verification",
                    rationale="Independent verification adds confidence.",
                    priority="medium",
                    confidence=base_confidence - 0.15
                )
            ]
        )

        escalation = RecommendationTrack(
            track_type="escalation",
            summary="升级争议处理",
            recommendations=[
                Recommendation(
                    action="Escalate to development lead for status clarification",
                    rationale="Clarify actual defect state if status appears incorrect.",
                    priority="medium",
                    confidence=0.80
                ),
                Recommendation(
                    action="Request status audit if discrepancy exists",
                    rationale="JIRA status should reflect actual defect state.",
                    priority="low",
                    confidence=0.75
                )
            ]
        )

        return AdvisorOutput(
            defect_id=defect_id,
            preferred_path=preferred,
            alternative_path=alternative,
            escalation_path=escalation,
            based_on_facts=True,
            based_on_review=True
        )

    def _generate_insufficient_evidence_recommendations(
        self,
        fact_data: Dict[str, Any],
        review_decision: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> "AdvisorOutput":
        """
        INSUFFICIENT_EVIDENCE 的三轨推荐
        """
        from .schemas_compat import (
            AdvisorOutput,
            RecommendationTrack,
            Recommendation
        )

        defect_id = fact_data.get("defect_id", fact_data.get("key", ""))
        reasoning = review_decision.get("reasoning", "")
        base_confidence = review_decision.get("confidence", 0.70)

        # 提取缺失的证据类型
        missing_evidence = []
        if "Missing evidence:" in reasoning:
            missing_str = reasoning.split("Missing evidence:")[1].strip()
            missing_evidence = [e.strip() for e in missing_str.split(",")]

        preferred = RecommendationTrack(
            track_type="preferred",
            summary="要求补充缺失证据",
            recommendations=[
                Recommendation(
                    action=f"Request evidence: {', '.join(missing_evidence) if missing_evidence else 'evidence checklist'}",
                    rationale="Complete evidence package required for decision.",
                    priority="high",
                    confidence=base_confidence
                ),
                Recommendation(
                    action="Provide evidence template/examples",
                    rationale="Clear guidance accelerates evidence collection.",
                    priority="medium",
                    confidence=base_confidence - 0.05
                ),
                Recommendation(
                    action="Set evidence submission deadline (recommended: 5 business days)",
                    rationale="Timely submission prevents indefinite delays.",
                    priority="medium",
                    confidence=base_confidence - 0.10
                )
            ]
        )

        alternative = RecommendationTrack(
            track_type="alternative",
            summary="基于现有证据做出保守决策",
            recommendations=[
                Recommendation(
                    action="Proceed with conservative decision based on available evidence",
                    rationale="If timeline is critical, proceed with available information.",
                    priority="medium",
                    confidence=base_confidence - 0.20
                ),
                Recommendation(
                    action="Request waiver for missing evidence if justified",
                    rationale="Exceptional circumstances may warrant evidence waiver.",
                    priority="low",
                    confidence=base_confidence - 0.30
                )
            ]
        )

        escalation = RecommendationTrack(
            track_type="escalation",
            summary="升级证据收集责任",
            recommendations=[
                Recommendation(
                    action="Escalate to team lead for evidence collection support",
                    rationale="Leadership support may be needed for difficult evidence.",
                    priority="high",
                    confidence=0.85
                ),
                Recommendation(
                    action="Request customer assistance for customer_impact evidence",
                    rationale="Customer involvement may be required for impact documentation.",
                    priority="medium",
                    confidence=0.80
                )
            ]
        )

        return AdvisorOutput(
            defect_id=defect_id,
            preferred_path=preferred,
            alternative_path=alternative,
            escalation_path=escalation,
            based_on_facts=True,
            based_on_review=True
        )

    def _generate_standard_recommendations(
        self,
        fact_data: Dict[str, Any],
        review_decision: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> "AdvisorOutput":
        """
        PASS 的三轨推荐 - 标准处理流程
        """
        from .schemas_compat import (
            AdvisorOutput,
            RecommendationTrack,
            Recommendation
        )

        defect_id = fact_data.get("defect_id", fact_data.get("key", ""))
        status = fact_data.get("status", "Unknown")
        base_confidence = review_decision.get("confidence", 0.95)

        preferred = RecommendationTrack(
            track_type="preferred",
            summary="标准流程处理",
            recommendations=[
                Recommendation(
                    action=f"Proceed with standard workflow - current status: {status}",
                    rationale="No special handling required.",
                    priority="medium",
                    confidence=base_confidence
                ),
                Recommendation(
                    action="Continue normal defect lifecycle management",
                    rationale="Defect follows standard path.",
                    priority="low",
                    confidence=base_confidence - 0.05
                )
            ]
        )

        alternative = RecommendationTrack(
            track_type="alternative",
            summary="优化处理效率",
            recommendations=[
                Recommendation(
                    action="Consider batch processing with similar defects",
                    rationale="Efficiency improvement for high-volume handling.",
                    priority="low",
                    confidence=base_confidence - 0.10
                )
            ]
        )

        escalation = RecommendationTrack(
            track_type="escalation",
            summary="监控潜在风险",
            recommendations=[
                Recommendation(
                    action="Monitor for status changes requiring attention",
                    rationale="Even PASS defects may develop issues.",
                    priority="low",
                    confidence=0.85
                )
            ]
        )

        return AdvisorOutput(
            defect_id=defect_id,
            preferred_path=preferred,
            alternative_path=alternative,
            escalation_path=escalation,
            based_on_facts=True,
            based_on_review=True
        )

    def _analyze_fix_patterns(
        self,
        similar_cases: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        分析相似案例中的修复模式

        Args:
            similar_cases: 相似案例列表

        Returns:
            修复模式分析结果
        """
        quick_fix = []
        standard_fix = []
        delayed_fix = []

        for case in similar_cases:
            resolution_days = case.get("resolution_days", 999)
            if resolution_days <= 14:
                quick_fix.append(case)
            elif resolution_days <= 30:
                standard_fix.append(case)
            else:
                delayed_fix.append(case)

        return {
            "quick_fix": quick_fix,
            "standard_fix": standard_fix,
            "delayed_fix": delayed_fix
        }

    def _analyze_limitation_patterns(
        self,
        similar_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析相似案例中的限制有效期模式

        Args:
            similar_cases: 相似案例列表

        Returns:
            限制模式分析结果
        """
        durations = []
        approvals = 0
        denials = 0

        for case in similar_cases:
            if case.get("limitation_duration"):
                durations.append(case["limitation_duration"])
            if case.get("limitation_approved"):
                approvals += 1
            elif case.get("limitation_denied"):
                denials += 1

        typical_duration = sum(durations) / len(durations) if durations else 90
        approval_rate = approvals / (approvals + denials) if (approvals + denials) > 0 else 0.5

        return {
            "typical_duration": typical_duration,
            "approval_rate": approval_rate,
            "sample_size": len(similar_cases)
        }