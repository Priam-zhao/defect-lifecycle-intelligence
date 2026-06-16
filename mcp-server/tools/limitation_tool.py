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

# Limitation 相关状态
LIMITATION_STATUSES = [
    "Limitation",
    "Limitation - Pending Approval",
    "Limitation - Approved",
    "Temporary Limitation",
    "Permanent Limitation",
    "Limitation - Deferred",
]


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

    def get_limitation_records(self, defect_id: str) -> Dict[str, Any]:
        """
        获取缺陷的所有 limitation 记录（追溯 limitation 历史）

        原则1: 原 defect defer 到下一项目，当前项目生成 limitation defect 记录
        原则2: 通过 Issue Links 和 Summary 模式识别 limitation records
        原则3: limitation 先后顺序按 issue key 数字大小排序
        原则4: 按 link_type 和时间排序

        Args:
            defect_id: JIRA Issue Key (原始缺陷 ID)

        Returns:
            包含所有 limitation 记录的字典，按类型和时间排序
        """
        client = self._get_client()
        if not client:
            return self._get_mock_limitation_records(defect_id)

        try:
            # 方法1: 从 Issue Links 获取关联的 limitation defect
            linked_limitations = self._get_linked_limitation_defects(client, defect_id)

            # 方法2: 通过 JQL 搜索相同 summary pattern 的 limitation defect
            similar_limitations = self._get_similar_limitation_defects(client, defect_id)

            # 合并并按 key_number 排序
            all_records = self._merge_and_sort_records(linked_limitations, similar_limitations)

            # 计算每个 limitation 的时长
            for record in all_records:
                record["duration_days"] = self._calculate_duration(record)

            # 按 link_type 和 key_number 排序
            sorted_records = self._sort_by_link_type_and_time(all_records)

            # 按 link_type 分组
            grouped_by_type = self._group_by_link_type(sorted_records)

            return {
                "original_defect_id": defect_id,
                "total_limitation_records": len(sorted_records),
                "limitation_records": sorted_records,
                "grouped_by_link_type": grouped_by_type,
                "retrieved_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception:
            return self._get_mock_limitation_records(defect_id)

    def _get_linked_limitation_defects(self, client, defect_id: str) -> List[Dict[str, Any]]:
        """从 Issue Links 获取关联的 limitation defect"""
        records = []
        try:
            issue = client.issue(defect_id, expand='changelog')
            f = issue.fields

            # 检查 issuelinks
            if hasattr(f, 'issuelinks'):
                for link in f.issuelinks:
                    # 处理不同类型的 link
                    linked_key = None
                    link_type = None

                    if hasattr(link, 'outwardIssue'):
                        linked_key = link.outwardIssue.key
                        # 获取 outward link 类型 (如 "Resolves", "Relates", "Duplicate")
                        link_type = getattr(link, 'type', None)
                        if link_type and hasattr(link_type, 'name'):
                            link_type = link_type.name
                        elif link_type and isinstance(link_type, dict):
                            link_type = link_type.get('name')
                    elif hasattr(link, 'inwardIssue'):
                        linked_key = link.inwardIssue.key
                        # 获取 inward link 类型
                        link_type = getattr(link, 'type', None)
                        if link_type and hasattr(link_type, 'name'):
                            link_type = link_type.name
                        elif link_type and isinstance(link_type, dict):
                            link_type = link_type.get('name')
                        # Inward link 的 name 可能是 "Resolved by"，需要转换方向
                        if link_type == "Resolved by":
                            link_type = "Resolves"

                    if linked_key:
                        # 检查 linked issue 是否是 limitation defect
                        linked_issue = client.issue(linked_key)
                        if self._is_limitation_defect(linked_issue, defect_id):
                            record = self._extract_limitation_record(linked_issue, defect_id)
                            record["link_type"] = link_type
                            records.append(record)
        except Exception:
            pass

        return records

    def _get_similar_limitation_defects(self, client, defect_id: str) -> List[Dict[str, Any]]:
        """通过 JQL 搜索相同 description pattern 的 limitation defect"""
        records = []
        try:
            # 提取 defect_id 中的数字部分作为搜索基础
            import re
            match = re.match(r'([A-Z]+)-(\d+)', defect_id)
            if not match:
                return records

            project_prefix = match.group(1)
            defect_num = match.group(2)

            # 通过 description 搜索 temporary limitation record
            jql_temporary = f'project = "{project_prefix}" AND description ~ "temporary limitation record for {defect_id}" ORDER BY created ASC'
            issues_temporary = client.search_issues(jql_temporary, maxResults=100)

            # 通过 description 搜索 permanent limitation record
            jql_permanent = f'project = "{project_prefix}" AND description ~ "permanent limitation record for {defect_id}" ORDER BY created ASC'
            issues_permanent = client.search_issues(jql_permanent, maxResults=100)

            # 合并并去重
            all_issues = {issue.key: issue for issue in issues_temporary + issues_permanent}

            for issue in all_issues.values():
                if self._is_limitation_defect(issue, defect_id):
                    record = self._extract_limitation_record(issue, defect_id)
                    # JQL 搜索找到的记录，link_type 标记为通过 description 匹配找到
                    record["link_type"] = "Description Match"
                    records.append(record)
        except Exception:
            pass

        return records

    def _is_limitation_defect(self, issue, original_defect_id: str) -> bool:
        """判断 issue 是否是 original_defect_id 的 limitation defect"""
        f = issue.fields

        # 检查状态是否是 Limitation 相关
        if f.status.name not in LIMITATION_STATUSES:
            return False

        # 检查 description 是否包含原始 defect ID
        desc = (f.description or "").lower()
        if original_defect_id.lower() in desc:
            return True

        # 检查 summary 是否包含 "limitation" 关键词
        summary = (f.summary or "").lower()
        if "limitation" in summary and original_defect_id in f.summary:
            return True

        return False

    def _extract_limitation_record(self, issue, original_defect_id: str) -> Dict[str, Any]:
        """提取 limitation defect 的详细信息"""
        f = issue.fields

        # 计算 issue key 中的数字用于排序
        import re
        key_match = re.match(r'[A-Z]+-(\d+)', issue.key)
        key_number = int(key_match.group(1)) if key_match else 0

        # JIRA Project: 研发团队负责的项目 (如 OpenBMC)
        jira_project = None
        if hasattr(f, 'project') and f.project:
            if hasattr(f.project, 'name'):
                jira_project = f.project.name
            elif isinstance(f.project, dict):
                jira_project = f.project.get('name')

        # Iteration Project: 实际迭代版本 (customfield_13803)
        iteration_project = self._extract_project_found(f)

        return {
            "limitation_defect_id": issue.key,
            "key_number": key_number,
            "summary": f.summary,
            "status": f.status.name,
            "limitation_type": self._extract_limitation_type_from_status(f.status.name),
            "jira_project": jira_project,        # JIRA 项目（研发团队）
            "iteration_project": iteration_project,  # 迭代项目
            "created": str(f.created) if f.created else None,
            "updated": str(f.updated) if f.updated else None,
            "resolution_date": str(f.resolutiondate) if hasattr(f, 'resolutiondate') and f.resolutiondate else None,
            "original_defect_id": original_defect_id,
            "labels": f.labels or [],
            "description_snippet": (f.description or "")[:200] if f.description else None
        }

    def _extract_project_found(self, fields) -> Optional[str]:
        """提取 Project Found 字段 (customfield_13803)"""
        import json

        cf_13803 = getattr(fields, 'customfield_13803', None)
        if not cf_13803:
            return None

        try:
            # 解析 JSON 字符串 {"label": "...", "value": "..."}
            data = json.loads(cf_13803)
            return data.get('label')
        except (json.JSONDecodeError, TypeError):
            return str(cf_13803)

    def _extract_limitation_type_from_status(self, status: str) -> str:
        """从状态名称提取 limitation 类型"""
        status_lower = status.lower()
        if "temporary" in status_lower:
            return "Temporary"
        if "permanent" in status_lower:
            return "Permanent"
        if "approved" in status_lower:
            return "Approved"
        if "pending" in status_lower:
            return "Pending Approval"
        return "Limitation"

    def _merge_and_sort_records(
        self,
        linked_records: List[Dict[str, Any]],
        similar_records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """合并记录并按 key number 排序"""
        # 使用 dict 去重，以 key 为准
        records_dict = {}

        for record in linked_records + similar_records:
            key = record["limitation_defect_id"]
            if key not in records_dict:
                records_dict[key] = record

        # 按 key_number 排序（数字小的在前 = 较早的 limitation）
        sorted_records = sorted(records_dict.values(), key=lambda x: x["key_number"])

        return sorted_records

    def _sort_by_link_type_and_time(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按 link_type 和时间排序

        排序规则:
        1. Resolves (outward) > Description Match > Relates > Duplicate > 其他
        2. 同类型按 key_number 排序
        """
        # link_type 优先级 (数字越小优先级越高)
        link_type_priority = {
            "Resolves": 1,         # 主链路 defer 出去的 limitation
            "Description Match": 2, # JQL 搜索匹配到的 limitation
            "Relates": 3,          # 相关联
            "Duplicate": 4,         # 相同 root cause
            "Is duplicate of": 4,
            "Resolved by": 5,       # 被其他解决
        }

        def sort_key(record: Dict[str, Any]) -> tuple:
            link_type = record.get("link_type", "Unknown")
            priority = link_type_priority.get(link_type, 99)
            key_number = record.get("key_number", 0)
            return (priority, key_number)

        return sorted(records, key=sort_key)

    def _group_by_link_type(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按 link_type 分组"""
        grouped = {}
        for record in records:
            link_type = record.get("link_type", "Unknown")
            if link_type not in grouped:
                grouped[link_type] = []
            grouped[link_type].append(record)
        return grouped

    def _calculate_duration(self, record: Dict[str, Any]) -> Optional[float]:
        """计算 limitation 的持续天数"""
        created = self._parse_datetime(record.get("created"))
        resolved = self._parse_datetime(record.get("resolution_date"))

        if not created:
            return None

        end_date = resolved if resolved else datetime.now(timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        duration = (end_date - created).total_seconds() / 86400
        return round(duration, 1)

    def _get_mock_limitation_records(self, defect_id: str) -> Dict[str, Any]:
        """返回模拟 limitation 记录"""
        import re
        match = re.match(r'([A-Z]+)-(\d+)', defect_id)
        project = match.group(1) if match else "OBMC"

        records = [
            {
                "limitation_defect_id": f"{project}-25000",
                "key_number": 25000,
                "link_type": "Resolves",
                "summary": f"[PA_BHS_Santorini_GNR] This is the temporary limitation record for defect {defect_id}.",
                "status": "Temporary Limitation",
                "limitation_type": "Temporary",
                "jira_project": "OpenBMC",
                "iteration_project": "[9508] FW Agile Release 26-1",
                "created": "2025-04-15T10:00:00.000-0400",
                "updated": "2026-06-01T14:30:00.000-0400",
                "resolution_date": None,
                "original_defect_id": defect_id,
                "labels": ["limitation", "limitation_temporary"],
                "description_snippet": f"This is the temporary limitation record for defect {defect_id}...",
                "duration_days": 423.2
            },
            {
                "limitation_defect_id": f"{project}-26000",
                "key_number": 26000,
                "link_type": "Relates",
                "summary": f"[PA_BHS_Santorini_GNR] This is the permanent limitation record for defect {defect_id}.",
                "status": "Permanent Limitation",
                "limitation_type": "Permanent",
                "jira_project": "OpenBMC",
                "iteration_project": "[9508] FW Agile Release 26-2",
                "created": "2026-06-01T14:30:00.000-0400",
                "updated": "2026-06-10T09:00:00.000-0400",
                "resolution_date": None,
                "original_defect_id": defect_id,
                "labels": ["limitation", "limitation_permanent"],
                "description_snippet": f"This is the permanent limitation record for defect {defect_id}...",
                "duration_days": 11.8
            }
        ]

        grouped = self._group_by_link_type(records)

        return {
            "original_defect_id": defect_id,
            "total_limitation_records": len(records),
            "limitation_records": records,
            "grouped_by_link_type": grouped,
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
