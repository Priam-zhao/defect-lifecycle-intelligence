"""
Pytest 配置和共享 Fixtures

提供测试所需的共享 fixtures 和配置
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 添加 mcp-server 目录到 path（用于导入 schemas 等）
mcp_server_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mcp-server"
)
if os.path.exists(mcp_server_path):
    sys.path.insert(0, os.path.dirname(mcp_server_path))


@pytest.fixture
def mock_mcp_client():
    """Mock MCP 客户端"""
    client = MagicMock()
    client.call_tool = AsyncMock()
    return client


@pytest.fixture
def sample_defect_fact():
    """示例缺陷事实数据"""
    return {
        "defect_id": "OBMC-24951",
        "key": "OBMC-24951",
        "summary": "KVM connection failure during remote management",
        "severity": "Critical",
        "priority": "High",
        "status": "Working",
        "created": "2025-03-15T10:30:00Z",
        "assignee": "zhangsan@lenovo.com",
        "reporter": "lisi@lenovo.com",
        "platform": "ThinkSystem",
        "components": ["BMC", "KVM"],
        "root_cause": "Network configuration",
        "active_weeks": 8.5,
        "tci": 0.42,
        "pfi": 0.68,
        "confidence": 0.88,
        "confidence_level": "high",
        "timeline": {
            "created": "2025-03-15T10:30:00Z",
            "status_changes": [
                {"from_status": "New", "to_status": "Assigned", "changed_at": "2025-03-15T11:00:00Z"},
                {"from_status": "Assigned", "to_status": "Working", "changed_at": "2025-03-16T09:00:00Z"}
            ],
            "resolved": None,
            "closed": None
        },
        "clone_info": {
            "is_clone": False,
            "parent_id": None,
            "child_ids": [],
            "clone_chain": [],
            "clone_depth": 0
        },
        "evidence": {
            "customer_impact": {
                "source": "customer_report",
                "verified": True,
                "impact_level": "high"
            },
            "workaround_exists": {
                "source": "internal",
                "verified": True,
                "description": "Use local console instead"
            },
            "no_regression": None,
            "root_cause_analysis": None,
            "reproduction_steps": None,
            "test_coverage": None,
            "customer_visibility": True
        },
        "anomalies": [
            {
                "type": "long_resolution_time",
                "severity": "warning",
                "description": "Resolution time exceeds typical for severity"
            }
        ],
        "anomaly_count": 1,
        "has_critical_anomaly": False,
        "similar_cases": [
            {
                "defect_id": "OBMC-24001",
                "similarity_score": 0.85,
                "resolution_days": 12
            }
        ],
        "similar_case_count": 1,
        "retrieved_at": datetime.now().isoformat()
    }


@pytest.fixture
def sample_review_decision():
    """示例审查决策"""
    return {
        "decision_type": "TEMP_LIMITATION_ELIGIBLE",
        "defect_id": "OBMC-24951",
        "confidence": 0.87,
        "confidence_level": "medium",
        "evidence_links": [
            "customer_impact (customer_report, ID: 12345)",
            "workaround_exists (internal, ID: 12346)"
        ],
        "reasoning": "Defect meets criteria for temporary limitation",
        "triggered_rules": ["LIM-002", "LIM-003"]
    }


@pytest.fixture
def rules_config_path():
    """规则配置文件路径"""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "mcp-server",
        "config",
        "rules.json"
    )


@pytest.fixture
def temp_knowledge_store(tmp_path):
    """临时知识库目录"""
    return str(tmp_path / "knowledge_store")