"""
数据模型定义 - Defect Lifecycle Intelligence Agent

定义 Agent 层之间传递的标准数据结构，确保数据一致性。
遵循设计文档 v4.0 的核心原则：Fact Before Interpretation
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


# ==================== 枚举定义 ====================

class ConfidenceLevel(Enum):
    """置信度等级"""
    HIGH = "high"      # 0.90-1.00
    MEDIUM = "medium"  # 0.75-0.89
    LOW = "low"        # <0.75


class DecisionType(Enum):
    """审查决策类型"""
    MUST_FIX_BLOCKER = "MUST_FIX_BLOCKER"
    TEMP_LIMITATION_ELIGIBLE = "TEMP_LIMITATION_ELIGIBLE"
    PERM_LIMITATION_ELIGIBLE = "PERM_LIMITATION_ELIGIBLE"
    CRITICAL_SSRB_REVIEW = "CRITICAL_SSRB_REVIEW"
    INVALID_CLOSURE_REQUEST = "INVALID_CLOSURE_REQUEST"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PASS = "PASS"


class EvidenceType(Enum):
    """证据类型"""
    CUSTOMER_IMPACT = "customer_impact"
    WORKAROUND_EXISTS = "workaround_exists"
    NO_REGRESSION = "no_regression"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    REPRODUCTION_STEPS = "reproduction_steps"
    TEST_COVERAGE = "test_coverage"
    CUSTOMER_VISIBILITY = "customer_visibility"


# ==================== 时间线数据结构 ====================

@dataclass
class StatusChange:
    """状态变更记录"""
    from_status: str
    to_status: str
    changed_at: datetime
    changed_by: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class Timeline:
    """缺陷时间线"""
    defect_id: str
    created: datetime
    status_changes: List[StatusChange] = field(default_factory=list)
    resolved: Optional[datetime] = None
    closed: Optional[datetime] = None

    # 计算属性（基于 created/resolved/closed 计算）
    @property
    def total_duration_days(self) -> float:
        """总持续时间（天）"""
        if not self.closed:
            end = datetime.now()
        else:
            end = self.closed
        return (end - self.created).total_seconds() / 86400

    @property
    def active_duration_days(self) -> float:
        """活跃持续时间（天）- 排除 Closed 状态"""
        if not self.resolved:
            end = datetime.now()
        else:
            end = self.resolved
        return (end - self.created).total_seconds() / 86400

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（不含计算属性，避免反序列化失败）"""
        return {
            "defect_id": self.defect_id,
            "created": self.created.isoformat(),
            "status_changes": [
                {
                    "from_status": sc.from_status,
                    "to_status": sc.to_status,
                    "changed_at": sc.changed_at.isoformat(),
                    "changed_by": sc.changed_by,
                    "comment": sc.comment
                }
                for sc in self.status_changes
            ],
            "resolved": self.resolved.isoformat() if self.resolved else None,
            "closed": self.closed.isoformat() if self.closed else None
        }


# ==================== 克隆关系数据结构 ====================

@dataclass
class CloneInfo:
    """克隆信息"""
    defect_id: str
    is_clone: bool = False
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    clone_chain: List[str] = field(default_factory=list)
    clone_depth: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "is_clone": self.is_clone,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "clone_chain": self.clone_chain,
            "clone_depth": self.clone_depth
        }


# ==================== 证据数据结构 ====================

@dataclass
class Evidence:
    """证据数据"""
    defect_id: str
    customer_impact: Optional[Dict[str, Any]] = None
    workaround_exists: Optional[Dict[str, Any]] = None
    no_regression: Optional[Dict[str, Any]] = None
    root_cause_analysis: Optional[Dict[str, Any]] = None
    reproduction_steps: Optional[Dict[str, Any]] = None
    test_coverage: Optional[Dict[str, Any]] = None
    customer_visibility: Optional[Dict[str, Any]] = None

    @property
    def completeness_score(self) -> float:
        """证据完整性评分"""
        fields = [
            self.customer_impact,
            self.workaround_exists,
            self.no_regression,
            self.root_cause_analysis,
            self.reproduction_steps,
            self.test_coverage
        ]
        return sum(1 for f in fields if f is not None) / len(fields)

    def get_missing_evidence(self) -> List[str]:
        """获取缺失的证据类型"""
        missing = []
        if not self.customer_impact:
            missing.append("customer_impact")
        if not self.workaround_exists:
            missing.append("workaround_exists")
        if not self.no_regression:
            missing.append("no_regression")
        if not self.root_cause_analysis:
            missing.append("root_cause_analysis")
        if not self.reproduction_steps:
            missing.append("reproduction_steps")
        if not self.test_coverage:
            missing.append("test_coverage")
        return missing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "completeness_score": round(self.completeness_score, 2),
            "customer_impact": self.customer_impact,
            "workaround_exists": self.workaround_exists,
            "no_regression": self.no_regression,
            "root_cause_analysis": self.root_cause_analysis,
            "reproduction_steps": self.reproduction_steps,
            "test_coverage": self.test_coverage,
            "customer_visibility": self.customer_visibility,
            "missing_evidence": self.get_missing_evidence()
        }


# ==================== Limitation 数据结构 ====================

@dataclass
class LimitationInfo:
    """限制信息"""
    defect_id: str
    is_in_limitation: bool = False
    limitation_type: Optional[str] = None  # "Temporary" / "Permanent"
    limitation_start: Optional[str] = None  # ISO format datetime
    limitation_end: Optional[str] = None  # ISO format datetime
    limitation_reason: Optional[str] = None
    approval_status: str = "Unknown"  # "Pending" / "Approved" / "Rejected"
    ssrb_approval: Optional[Dict[str, Any]] = None
    board_approval: Optional[Dict[str, Any]] = None
    remaining_days: Optional[float] = None
    retrieved_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "is_in_limitation": self.is_in_limitation,
            "limitation_type": self.limitation_type,
            "limitation_start": self.limitation_start,
            "limitation_end": self.limitation_end,
            "limitation_reason": self.limitation_reason,
            "approval_status": self.approval_status,
            "ssrb_approval": self.ssrb_approval,
            "board_approval": self.board_approval,
            "remaining_days": self.remaining_days,
            "retrieved_at": self.retrieved_at
        }


# ==================== 核心缺陷事实 ====================

@dataclass
class DefectFact:
    """
    缺陷事实数据 - Fact Agent 输出

    遵循原则：Fact Before Interpretation
    - 只包含客观事实，无解释
    - 所有时间戳精确记录
    - 证据直接引用，无推断
    """
    # 基本信息
    defect_id: str
    key: str  # Jira Issue Key
    summary: str
    severity: str
    priority: str

    # 时间线
    timeline: Timeline

    # 克隆信息
    clone_info: CloneInfo

    # 证据
    evidence: Evidence

    # 限制信息
    limitation: Optional[Dict[str, Any]] = None

    # 指标
    tci: float = 0.0  # Time-to-Close Index
    pfi: float = 0.0  # Platform-First Index

    # 置信度
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM

    # 元数据
    retrieved_at: datetime = field(default_factory=datetime.now)
    source: str = "jira"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "key": self.key,
            "summary": self.summary,
            "severity": self.severity,
            "priority": self.priority,
            "timeline": self.timeline.to_dict(),
            "clone_info": self.clone_info.to_dict(),
            "evidence": self.evidence.to_dict(),
            "limitation": self.limitation,
            "tci": round(self.tci, 3),
            "pfi": round(self.pfi, 3),
            "confidence": round(self.confidence, 3),
            "confidence_level": self.confidence_level.value,
            "retrieved_at": self.retrieved_at.isoformat(),
            "source": self.source
        }


# ==================== 审查决策 ====================

@dataclass
class ReviewDecision:
    """
    审查决策 - Review Agent 输出

    由规则引擎生成，不可被 LLM 修改
    """
    decision_type: DecisionType
    defect_id: str
    confidence: float
    confidence_level: ConfidenceLevel
    evidence_links: List[str] = field(default_factory=list)
    reasoning: str = ""
    triggered_rules: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_type": self.decision_type.value,
            "defect_id": self.defect_id,
            "confidence": round(self.confidence, 3),
            "confidence_level": self.confidence_level.value,
            "evidence_links": self.evidence_links,
            "reasoning": self.reasoning,
            "triggered_rules": self.triggered_rules,
            "created_at": self.created_at.isoformat()
        }


# ==================== 推荐建议 ====================

@dataclass
class Recommendation:
    """单一推荐"""
    action: str
    rationale: str
    priority: Literal["high", "medium", "low"]
    confidence: float


@dataclass
class RecommendationTrack:
    """推荐轨道"""
    track_type: Literal["preferred", "alternative", "escalation"]
    recommendations: List[Recommendation] = field(default_factory=list)
    summary: str = ""


@dataclass
class AdvisorOutput:
    """
    Advisor Agent 输出

    基于 Fact JSON 和 Review JSON 生成三轨推荐
    """
    defect_id: str
    preferred_path: RecommendationTrack
    alternative_path: RecommendationTrack
    escalation_path: RecommendationTrack

    # 审计信息
    based_on_facts: bool = True
    based_on_review: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "preferred_path": {
                "track_type": self.preferred_path.track_type,
                "summary": self.preferred_path.summary,
                "recommendations": [
                    {
                        "action": r.action,
                        "rationale": r.rationale,
                        "priority": r.priority,
                        "confidence": round(r.confidence, 3)
                    }
                    for r in self.preferred_path.recommendations
                ]
            },
            "alternative_path": {
                "track_type": self.alternative_path.track_type,
                "summary": self.alternative_path.summary,
                "recommendations": [
                    {
                        "action": r.action,
                        "rationale": r.rationale,
                        "priority": r.priority,
                        "confidence": round(r.confidence, 3)
                    }
                    for r in self.alternative_path.recommendations
                ]
            },
            "escalation_path": {
                "track_type": self.escalation_path.track_type,
                "summary": self.escalation_path.summary,
                "recommendations": [
                    {
                        "action": r.action,
                        "rationale": r.rationale,
                        "priority": r.priority,
                        "confidence": round(r.confidence, 3)
                    }
                    for r in self.escalation_path.recommendations
                ]
            },
            "based_on_facts": self.based_on_facts,
            "based_on_review": self.based_on_review,
            "created_at": self.created_at.isoformat()
        }


# ==================== 本体数据结构 ====================

@dataclass
class OntologyNode:
    """本体节点"""
    node_id: str
    name: str
    node_type: str  # technical_domain, component, failure_signature, etc.
    status: Literal["canonical", "draft", "pending_review"] = "canonical"
    confidence: float = 1.0
    related_cases: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type,
            "status": self.status,
            "confidence": round(self.confidence, 3),
            "related_cases": self.related_cases,
            "attributes": self.attributes
        }


@dataclass
class CanonicalDefectModel:
    """规范缺陷模型"""
    model_id: str
    technical_domain: str
    root_cause_category: str = ""
    platform_family: str = ""
    affected_components: List[str] = field(default_factory=list)
    failure_signatures: List[str] = field(default_factory=list)

    typical_resolution_days: float = 0.0
    typical_tci_range: tuple = (0.0, 1.0)
    known_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "technical_domain": self.technical_domain,
            "affected_components": self.affected_components,
            "failure_signatures": self.failure_signatures,
            "root_cause_category": self.root_cause_category,
            "platform_family": self.platform_family,
            "typical_resolution_days": round(self.typical_resolution_days, 2),
            "typical_tci_range": self.typical_tci_range,
            "known_patterns": self.known_patterns
        }


# ==================== 覆盖事件 ====================

@dataclass
class OverrideEvent:
    """覆盖事件 - Human Feedback Flywheel 数据"""
    defect_id: str
    system_decision: DecisionType
    human_decision: DecisionType
    reason: str
    reviewer: str
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """自动转换字符串到枚举类型"""
        if isinstance(self.system_decision, str):
            self.system_decision = DecisionType(self.system_decision)
        if isinstance(self.human_decision, str):
            self.human_decision = DecisionType(self.human_decision)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "system_decision": self.system_decision.value,
            "human_decision": self.human_decision.value,
            "reason": self.reason,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class CorrectionPattern:
    """纠正模式"""
    pattern_id: str
    pattern_description: str
    historical_outcome: str  # e.g., "82% escalated to Must Fix"
    confidence: float
    related_override_events: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_description": self.pattern_description,
            "historical_outcome": self.historical_outcome,
            "confidence": round(self.confidence, 3),
            "related_override_events": self.related_override_events,
            "created_at": self.created_at.isoformat()
        }


# ==================== 批量处理结果 ====================

@dataclass
class BatchExtractionResult:
    """批量提取结果"""
    project_id: str
    total_defects: int
    successful: int
    failed: int
    facts: List[DefectFact] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successful / self.total_defects if self.total_defects > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "total_defects": self.total_defects,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 3),
            "errors": self.errors
        }


# ==================== 案例检索 ====================

@dataclass
class CaseRetrievalResult:
    """案例检索结果"""
    query_criteria: Dict[str, Any]
    total_matches: int
    cases: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def similarity_distribution(self) -> Dict[str, int]:
        """按相似度分类统计"""
        dist = {"strong": 0, "related": 0, "reference": 0, "discarded": 0}
        for case in self.cases:
            similarity = case.get("similarity_score", 0)
            if similarity > 0.90:
                dist["strong"] += 1
            elif similarity > 0.70:
                dist["related"] += 1
            elif similarity > 0.50:
                dist["reference"] += 1
            else:
                dist["discarded"] += 1
        return dist

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_criteria": self.query_criteria,
            "total_matches": self.total_matches,
            "similarity_distribution": self.similarity_distribution,
            "cases": self.cases
        }