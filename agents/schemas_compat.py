"""
Schema 兼容层

处理 schemas 模块的动态导入，避免包名问题。
"""

import sys
import os

# 获取项目根目录
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_mcp_tools_path = os.path.join(_project_root, 'mcp-server', 'tools')

# 动态加载 schemas
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "schemas",
    os.path.join(_mcp_tools_path, "schemas.py")
)
_schemas_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schemas_module)

# 导出需要的类
ReviewDecision = _schemas_module.ReviewDecision
DecisionType = _schemas_module.DecisionType
ConfidenceLevel = _schemas_module.ConfidenceLevel
EvidenceType = _schemas_module.EvidenceType
StatusChange = _schemas_module.StatusChange
Timeline = _schemas_module.Timeline
CloneInfo = _schemas_module.CloneInfo
Evidence = _schemas_module.Evidence
DefectFact = _schemas_module.DefectFact
Recommendation = _schemas_module.Recommendation
RecommendationTrack = _schemas_module.RecommendationTrack
AdvisorOutput = _schemas_module.AdvisorOutput
OverrideEvent = _schemas_module.OverrideEvent
CorrectionPattern = _schemas_module.CorrectionPattern

__all__ = [
    "ReviewDecision",
    "DecisionType",
    "ConfidenceLevel",
    "EvidenceType",
    "StatusChange",
    "Timeline",
    "CloneInfo",
    "Evidence",
    "DefectFact",
    "Recommendation",
    "RecommendationTrack",
    "AdvisorOutput",
    "OverrideEvent",
    "CorrectionPattern",
]