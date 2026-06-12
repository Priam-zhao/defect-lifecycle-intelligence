"""
常量定义 - Defect Lifecycle Intelligence Agent
"""

import os


def load_env():
    """加载环境变量"""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        load_dotenv(env_path)
    except ImportError:
        pass


# ==================== JIRA 状态定义 ====================

# Active 状态
ACTIVE_STATUSES = [
    "Open",
    "Investigate",
    "Working",
    "Need Info",
    "Assigned",
    "In Progress",
    "Open - Review"
]

# Rejected 状态
REJECTED_STATUSES = [
    "Rejected",
    "Duplicate",
    "Cannot Reproduce",
    "Not a Bug",
    "Won't Fix"
]

# Verify 状态
VERIFY_STATUSES = [
    "Fixed",
    "Verify",
    "Fixed - Pending Verification"
]

# Limitation 状态
LIMITATION_STATUSES = [
    "Limitation",
    "Temporary Limitation",
    "Permanent Limitation",
    "Limitation - Approved",
    "Limitation - Pending Approval"
]

# Closed 状态
CLOSED_STATUSES = [
    "Closed",
    "Verified Closed",
    "Resolved and Closed"
]

# Resolved 状态（用于计算解决时间）
RESOLVED_STATUSES = [
    "Fixed",
    "Closed",
    "Limitation",
    "Temporary Limitation",
    "Permanent Limitation"
]


# ==================== 优先级和严重程度 ====================

CRITICAL_SEVERITIES = ["Blocker", "Critical", "Highest", "High"]
HIGH_PRIORITIES = ["Blocker", "Critical", "Highest", "High"]
MEDIUM_PRIORITIES = ["Medium", "Major"]
LOW_PRIORITIES = ["Low", "Lowest", "Minor"]


# ==================== 置信度阈值 ====================

CONFIDENCE_HIGH_THRESHOLD = 0.90
CONFIDENCE_MEDIUM_THRESHOLD = 0.75
CONFIDENCE_LOW_THRESHOLD = 0.75


# ==================== 相似度阈值 ====================

SIMILARITY_STRONG = 0.90  # Strong Match
SIMILARITY_RELATED = 0.70  # Related Match
SIMILARITY_REFERENCE = 0.50  # Reference Match


# ==================== 时间阈值 ====================

DEFECT_LONG_STANDING_WEEKS = 6  # 长期未解决缺陷的周数阈值
DEFECT_AGING_WARNING_WEEKS = 4  # 老化预警周数
TEMP_LIMITATION_MAX_DAYS = 90  # 临时限制最大天数


# ==================== 证据要求 ====================

# Limitation 决策所需的证据类型
EVIDENCE_REQUIREMENTS = {
    "TEMP_LIMITATION_ELIGIBLE": [
        "customer_impact",
        "workaround_exists",
        "no_regression"
    ],
    "PERM_LIMITATION_ELIGIBLE": [
        "customer_impact",
        "root_cause_analysis",
        "test_coverage"
    ],
    "MUST_FIX_BLOCKER": [
        "customer_visibility",
        "root_cause_analysis"
    ],
    "CRITICAL_SSRB_REVIEW": [
        "customer_impact",
        "reproduction_steps"
    ]
}


# ==================== 规则引擎常量 ====================

RULE_ENGINE_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config",
    "rules.json"
)


# ==================== 知识库路径 ====================

KNOWLEDGE_STORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "knowledge_store"
)


# ==================== JIRA 自定义字段 ====================

# Release Found 字段 ID（需要根据实际 JIRA 配置）
JIRA_RELEASE_FOUND_FIELD = "customfield_13725"

# Severity 字段 ID
JIRA_SEVERITY_FIELD = "customfield_10690"

# Platform 字段 ID
JIRA_PLATFORM_FIELD = "customfield_xxxxx"

# Root Cause 字段 ID
JIRA_ROOT_CAUSE_FIELD = "customfield_xxxxx"


# ==================== 架构继承权重 ====================

INHERITANCE_WEIGHT_THRESHOLD = 0.60  # 知识转移的最小继承权重
SHARED_COMPONENT_SIMILARITY_THRESHOLD = 0.70  # 共享组件相似度阈值


load_env()