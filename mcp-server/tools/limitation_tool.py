"""
Limitation Tool - 限制数据提取工具

用于提取和管理缺陷的 limitation（限制）相关信息。
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .constants import load_env
from .schemas import LimitationInfo, ConfidenceLevel

load_env()


class LimitationTool:
    """
    Limitation 数据提取工具

    提取 limitation 相关字段：
    - Limitation 类型（临时/永久）
    - Limitation 开始/结束日期
    - 审批状态
    - 限制原因
    """

    def __init__(self):
        self.jira_url = os.getenv("JIRA_URL", "")
        self.jira_pat = os.getenv("JIRA_PAT", "")
        self._client = None

    def _get_client(self):
        """获取 JIRA 客户端（懒加载）"""
        if self._client is None:
            if not self.jira_url or not self.jira_pat:
                return None
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                from jira import JIRA
                self._client = JIRA(
                    server=self.jira_url,
                    token_auth=self.jira_pat,
                    options={'verify': False}
                )
            except Exception:
                return None
        return self._client

    def extract_limitation_info(self, defect_id: str) -> Dict[str, Any]:
        """
        提取缺陷的 limitation 信息

        Args:
            defect_id: JIRA Issue Key

        Returns:
            LimitationInfo 字典
        """
        client = self._get_client()
        if not client:
            return self._get_mock_limitation(defect_id)

        try:
            issue = client.issue(defect_id)
            return self._extract_from_issue(issue)
        except Exception:
            return self._get_mock_limitation(defect_id)

    def _extract_from_issue(self, issue) -> Dict[str, Any]:
        """从 JIRA Issue 提取 limitation 信息"""
        f = issue.fields

        # 判断当前状态是否为 Limitation
        current_status = f.status.name if f.status else ""
        is_in_limitation = current_status in [
            "Limitation", "Temporary Limitation",
            "Permanent Limitation", "Limitation - Approved"
        ]

        # 提取 Limitation 类型
        limitation_type = self._extract_limitation_type(issue)

        # 提取 Limitation 开始日期
        limitation_start = self._extract_limitation_start(issue, current_status)

        # 提取 Limitation 结束日期（临时限制）
        limitation_end = self._extract_limitation_end(issue)

        # 提取 Limitation 原因
        limitation_reason = self._extract_limitation_reason(issue)

        # 提取审批状态
        approval_status = self._extract_approval_status(issue)

        # 提取 SSR B 审批信息
        ssrb_approval = self._extract_ssrb_approval(issue)

        # 提取 Board 审批信息
        board_approval = self._extract_board_approval(issue)

        # 计算剩余天数（临时限制）
        remaining_days = None
        if limitation_end and limitation_start:
            end_date = self._parse_datetime(limitation_end)
            if end_date:
                now = datetime.now(timezone.utc)
                remaining = (end_date - now).total_seconds() / 86400
                remaining_days = max(0, round(remaining, 1))

        return {
            "defect_id": issue.key,
            "is_in_limitation": is_in_limitation,
            "limitation_type": limitation_type,
            "limitation_start": limitation_start,
            "limitation_end": limitation_end,
            "limitation_reason": limitation_reason,
            "approval_status": approval_status,
            "ssrb_approval": ssrb_approval,
            "board_approval": board_approval,
            "remaining_days": remaining_days,
            "retrieved_at": datetime.now(timezone.utc).isoformat()
        }

    def _extract_limitation_type(self, issue) -> Optional[str]:
        """提取 Limitation 类型"""
        f = issue.fields

        # 方法1: 从 status 判断
        status = f.status.name if f.status else ""
        if "Temporary" in status:
            return "Temporary"
        if "Permanent" in status:
            return "Permanent"
        if status == "Limitation":
            # 默认临时限制
            return "Temporary"

        # 方法2: 从 labels 检测
        labels = [l.lower() for l in (f.labels or [])]
        if "limitation_permanent" in labels:
            return "Permanent"
        if "limitation_temporary" in labels:
            return "Temporary"
        if "limitation" in labels:
            return "Temporary"

        # 方法3: 从 summary 检测
        summary = f.summary or ""
        if "permanent limitation" in summary.lower():
            return "Permanent"
        if "temporary limitation" in summary.lower():
            return "Temporary"

        return None

    def _extract_limitation_start(self, issue, current_status: str) -> Optional[str]:
        """提取 Limitation 开始日期"""
        f = issue.fields

        # 检查是否有自定义开始日期字段
        if hasattr(f, 'customfield_limitation_start'):
            start = getattr(f, 'customfield_limitation_start', None)
            if start:
                return self._parse_datetime(start).isoformat() if isinstance(start, datetime) else str(start)

        # 从 status change history 推断
        if hasattr(issue, 'changelog') and issue.changelog:
            for history in issue.changelog.histories:
                for item in history.items:
                    if item.field == 'status':
                        to_status = item.toString or ""
                        if to_status in ["Limitation", "Temporary Limitation", "Permanent Limitation"]:
                            return self._parse_datetime(history.created).isoformat() if history.created else None

        return None

    def _extract_limitation_end(self, issue) -> Optional[str]:
        """提取 Limitation 结束日期"""
        f = issue.fields

        # 检查是否有自定义结束日期字段
        if hasattr(f, 'customfield_limitation_end'):
            end = getattr(f, 'customfield_limitation_end', None)
            if end:
                return self._parse_datetime(end).isoformat() if isinstance(end, datetime) else str(end)

        # 从 labels 提取期限（如 "limitation_90d" 表示 90 天）
        labels = f.labels or []
        for label in labels:
            if 'limitation_' in label.lower() and 'd' in label.lower():
                # 格式: limitation_90d
                try:
                    days = int(''.join(filter(str.isdigit, label)))
                    start = self._extract_limitation_start(issue, "")
                    if start:
                        start_dt = self._parse_datetime(start)
                        if start_dt:
                            end_dt = start_dt + timedelta(days=days)
                            return end_dt.isoformat()
                except ValueError:
                    pass

        return None

    def _extract_limitation_reason(self, issue) -> Optional[str]:
        """提取 Limitation 原因"""
        f = issue.fields

        # 从 description 提取
        desc = f.description or ""
        if "limitation reason:" in desc.lower():
            lines = desc.split('\n')
            for i, line in enumerate(lines):
                if "limitation reason:" in line.lower():
                    if i + 1 < len(lines):
                        return lines[i + 1].strip()

        # 从 labels 提取
        labels = [l.lower() for l in (f.labels or [])]
        for label in labels:
            if label.startswith("limreason_"):
                return label.replace("limreason_", "").replace("_", " ")

        return None

    def _extract_approval_status(self, issue) -> str:
        """提取审批状态"""
        f = issue.fields

        status = f.status.name if f.status else ""

        if status == "Limitation - Approved":
            return "Approved"
        if status == "Limitation - Pending Approval":
            return "Pending"
        if status == "Limitation":
            return "Pending"

        # 从 labels 检测
        labels = [l.lower() for l in (f.labels or [])]
        if "limitation_approved" in labels:
            return "Approved"
        if "limitation_pending" in labels:
            return "Pending"

        return "Unknown"

    def _extract_ssrb_approval(self, issue) -> Optional[Dict[str, Any]]:
        """提取 SSR B 审批信息"""
        f = issue.fields

        # 从 labels 检测
        labels = [l.lower() for l in (f.labels or [])]

        ssrb_approved = "ssrb_approved" in labels
        ssrb_rejected = "ssrb_rejected" in labels
        ssrb_pending = "ssrb_pending" in labels

        if ssrb_approved or ssrb_rejected or ssrb_pending:
            return {
                "approved": ssrb_approved,
                "rejected": ssrb_rejected,
                "pending": ssrb_pending,
                "approver": None,  # 需要从 comments 提取
                "approval_date": None
            }

        return None

    def _extract_board_approval(self, issue) -> Optional[Dict[str, Any]]:
        """提取 Board 审批信息"""
        f = issue.fields

        # 从 labels 检测
        labels = [l.lower() for l in (f.labels or [])]

        board_approved = "board_approved" in labels
        board_rejected = "board_rejected" in labels
        board_pending = "board_pending" in labels

        if board_approved or board_rejected or board_pending:
            return {
                "approved": board_approved,
                "rejected": board_rejected,
                "pending": board_pending,
                "approver": None,
                "approval_date": None
            }

        return None

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """解析 ISO 格式日期时间"""
        if not dt_str:
            return None
        try:
            if isinstance(dt_str, datetime):
                return dt_str
            dt_str = str(dt_str)
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00")[:26])
        except (ValueError, TypeError):
            return None

    def _get_mock_limitation(self, defect_id: str) -> Dict[str, Any]:
        """返回模拟 limitation 数据"""
        return {
            "defect_id": defect_id,
            "is_in_limitation": False,
            "limitation_type": None,
            "limitation_start": None,
            "limitation_end": None,
            "limitation_reason": None,
            "approval_status": "Unknown",
            "ssrb_approval": None,
            "board_approval": None,
            "remaining_days": None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "_mock": True
        }

    def validate_limitation_eligibility(self, defect_id: str) -> Dict[str, Any]:
        """
        验证缺陷是否符合 limitation 条件

        Args:
            defect_id: JIRA Issue Key

        Returns:
            验证结果字典
        """
        limitation_info = self.extract_limitation_info(defect_id)
        fact_tool_data = self._get_fact_data(defect_id)

        # 检查基本条件
        eligible = True
        reasons = []

        # 条件1: 不能是 Critical/Blocker severity
        severity = fact_tool_data.get("severity", "")
        if severity in ["Blocker", "Critical", "Highest", "High"]:
            eligible = False
            reasons.append(f"High severity ({severity}) not eligible for limitation")

        # 条件2: 必须有 workaround
        evidence = fact_tool_data.get("evidence", {})
        if not evidence.get("workaround_exists"):
            eligible = False
            reasons.append("No workaround exists")

        # 条件3: 活跃时间要求
        timeline = fact_tool_data.get("timeline", {})
        active_days = timeline.get("active_duration_days", 0)
        if active_days < 30:  # 至少活跃 30 天
            eligible = False
            reasons.append(f"Active duration ({active_days} days) too short")

        return {
            "defect_id": defect_id,
            "eligible": eligible,
            "limitation_type": limitation_info.get("limitation_type"),
            "reasons": reasons,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

    def _get_fact_data(self, defect_id: str) -> Dict[str, Any]:
        """获取缺陷事实数据"""
        from .defect_fact_tool import DefectFactTool
        tool = DefectFactTool()
        return tool.extract_defect_facts(defect_id)
