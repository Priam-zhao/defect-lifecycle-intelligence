"""
Timeline Tool - 时间线重建工具

用于重建缺陷的状态变更时间线，计算各阶段持续时间，检测异常。
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .constants import (
    ACTIVE_STATUSES, CLOSED_STATUSES, RESOLVED_STATUSES,
    DEFECT_LONG_STANDING_WEEKS, DEFECT_AGING_WARNING_WEEKS, load_env
)
from .schemas import Timeline, StatusChange, ConfidenceLevel

load_env()


class TimelineTool:
    """
    时间线重建工具

    提供以下能力：
    - 重建缺陷状态变更时间线
    - 计算各阶段持续时间
    - 检测时间异常
    - 分析时间模式
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

    def reconstruct_timeline(self, defect_id: str) -> Dict[str, Any]:
        """
        重建缺陷的时间线

        Args:
            defect_id: JIRA Issue Key

        Returns:
            时间线数据字典
        """
        client = self._get_client()
        if not client:
            return self._get_mock_timeline(defect_id)

        try:
            issue = client.issue(defect_id, expand='changelog')
            return self._reconstruct_from_issue(issue)
        except Exception:
            return self._get_mock_timeline(defect_id)

    def calculate_duration(
        self,
        defect_id: str,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        计算缺陷在特定状态间的持续时间

        Args:
            defect_id: JIRA Issue Key
            from_status: 起始状态（默认从头）
            to_status: 结束状态（默认到当前）

        Returns:
            持续时间数据
        """
        timeline_data = self.reconstruct_timeline(defect_id)

        # 将字典转换为 StatusChange 对象列表
        status_changes = [
            StatusChange(
                from_status=sc["from_status"],
                to_status=sc["to_status"],
                changed_at=datetime.fromisoformat(sc["changed_at"].replace("Z", "+00:00")) if isinstance(sc["changed_at"], str) else sc["changed_at"],
                changed_by=sc.get("changed_by"),
                comment=sc.get("comment")
            )
            for sc in timeline_data["status_changes"]
        ]

        # 创建 Timeline 对象
        timeline = Timeline(
            defect_id=timeline_data["defect_id"],
            created=datetime.fromisoformat(timeline_data["created"].replace("Z", "+00:00")) if isinstance(timeline_data["created"], str) else timeline_data["created"],
            status_changes=status_changes,
            resolved=datetime.fromisoformat(timeline_data["resolved"].replace("Z", "+00:00")) if timeline_data["resolved"] and isinstance(timeline_data["resolved"], str) else timeline_data["resolved"],
            closed=datetime.fromisoformat(timeline_data["closed"].replace("Z", "+00:00")) if timeline_data["closed"] and isinstance(timeline_data["closed"], str) else timeline_data["closed"]
        )

        if from_status and to_status:
            # 计算特定状态间的持续时间
            from_time = None
            to_time = None

            for change in timeline.status_changes:
                if change.to_status == from_status:
                    from_time = change.changed_at
                if from_time and change.to_status == to_status:
                    to_time = change.changed_at
                    break

            if from_time and to_time:
                duration = (to_time - from_time).total_seconds() / 86400
            else:
                duration = 0.0
        else:
            # 计算总活跃时间
            duration = timeline.active_duration_days

        return {
            "defect_id": defect_id,
            "duration_days": round(duration, 2),
            "from_status": from_status,
            "to_status": to_status,
            "calculated_at": datetime.now().isoformat()
        }

    def detect_anomalies(self, defect_id: str) -> Dict[str, Any]:
        """
        检测时间线异常

        检测以下异常：
        - 长期未处理（超过阈值周数）
        - 状态回退
        - 长时间处于某状态
        - 异常快速关闭

        Args:
            defect_id: JIRA Issue Key

        Returns:
            异常检测结果
        """
        timeline_data = self.reconstruct_timeline(defect_id)

        # 将字典转换为 StatusChange 对象列表
        def parse_datetime(dt_str):
            """解析 ISO 格式时间字符串，统一为无时区信息的时间"""
            if not dt_str:
                return None
            dt_str = str(dt_str).replace("Z", "+00:00")
            dt = datetime.fromisoformat(dt_str)
            # 统一为无时区信息的时间
            if dt.tzinfo is not None:
                dt = dt.astimezone(None).replace(tzinfo=None)
            return dt

        status_changes = [
            StatusChange(
                from_status=sc["from_status"],
                to_status=sc["to_status"],
                changed_at=parse_datetime(sc.get("changed_at")),
                changed_by=sc.get("changed_by"),
                comment=sc.get("comment")
            )
            for sc in timeline_data["status_changes"]
        ]

        # 创建 Timeline 对象
        timeline = Timeline(
            defect_id=timeline_data["defect_id"],
            created=parse_datetime(timeline_data["created"]),
            status_changes=status_changes,
            resolved=parse_datetime(timeline_data["resolved"]) if timeline_data.get("resolved") else None,
            closed=parse_datetime(timeline_data["closed"]) if timeline_data.get("closed") else None
        )

        anomalies = []

        # 检查 1: 长期未处理
        active_days = timeline.active_duration_days
        if active_days > DEFECT_LONG_STANDING_WEEKS * 7:
            anomalies.append({
                "type": "long_standing",
                "severity": "high",
                "description": f"Defect has been active for {active_days:.1f} days",
                "threshold_days": DEFECT_LONG_STANDING_WEEKS * 7
            })
        elif active_days > DEFECT_AGING_WARNING_WEEKS * 7:
            anomalies.append({
                "type": "aging_warning",
                "severity": "medium",
                "description": f"Defect has been active for {active_days:.1f} days",
                "threshold_days": DEFECT_AGING_WARNING_WEEKS * 7
            })

        # 检查 2: 状态回退
        prev_status = None
        for change in timeline.status_changes:
            if prev_status:
                # 定义状态顺序（一般情况）
                status_order = {
                    "Open": 1, "Assigned": 2, "Working": 3, "Fixed": 4,
                    "Verify": 5, "Closed": 6
                }
                prev_order = status_order.get(prev_status, 0)
                curr_order = status_order.get(change.to_status, 0)

                # 如果状态回退（当前状态序号小于之前状态）
                if curr_order < prev_order and change.to_status not in ["Open", "Assigned"]:
                    anomalies.append({
                        "type": "status_regression",
                        "severity": "medium",
                        "description": f"Status regressed from {prev_status} to {change.to_status}",
                        "at": change.changed_at.isoformat()
                    })
            prev_status = change.to_status

        # 检查 3: 长时间处于某状态
        prev_time = timeline.created
        prev_status = "Created"
        for change in timeline.status_changes:
            duration = (change.changed_at - prev_time).total_seconds() / 86400
            if duration > 30:  # 超过 30 天处于某状态
                anomalies.append({
                    "type": "long_status_duration",
                    "severity": "medium",
                    "description": f"Stayed in '{prev_status}' for {duration:.1f} days",
                    "status": prev_status,
                    "duration_days": round(duration, 2)
                })
            prev_time = change.changed_at
            prev_status = change.to_status

        # 检查 4: 异常快速关闭（创建到关闭少于 1 天）
        if timeline.closed:
            total_duration = timeline.total_duration_days
            if total_duration < 1.0:
                anomalies.append({
                    "type": "rapid_closure",
                    "severity": "low",
                    "description": f"Defect closed in {total_duration:.2f} days (unusually fast)",
                    "duration_days": round(total_duration, 2)
                })

        return {
            "defect_id": defect_id,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "has_critical_anomaly": any(a["severity"] == "high" for a in anomalies),
            "analyzed_at": datetime.now().isoformat()
        }

    def analyze_time_patterns(self, defect_ids: List[str]) -> Dict[str, Any]:
        """
        分析多个缺陷的时间模式

        Args:
            defect_ids: 缺陷 ID 列表

        Returns:
            时间模式分析结果
        """
        timelines = []
        for defect_id in defect_ids:
            timeline_data = self.reconstruct_timeline(defect_id)
            timelines.append(timeline_data)

        if not timelines:
            return {"total_defects": 0, "patterns": {}}

        # 统计分析
        total_durations = []
        active_durations = []
        status_counts = {}

        for tl in timelines:
            total = tl.get("total_duration_days", 0)
            active = tl.get("active_duration_days", 0)
            if total > 0:
                total_durations.append(total)
            if active > 0:
                active_durations.append(active)

            for change in tl.get("status_changes", []):
                to_status = change["to_status"]
                status_counts[to_status] = status_counts.get(to_status, 0) + 1

        return {
            "total_defects": len(timelines),
            "avg_total_duration_days": round(sum(total_durations) / len(total_durations), 2) if total_durations else 0,
            "avg_active_duration_days": round(sum(active_durations) / len(active_durations), 2) if active_durations else 0,
            "median_total_duration_days": round(sorted(total_durations)[len(total_durations) // 2], 2) if total_durations else 0,
            "status_distribution": status_counts,
            "patterns": {
                "long_standing_count": sum(1 for d in active_durations if d > DEFECT_LONG_STANDING_WEEKS * 7),
                "quick_close_count": sum(1 for d in total_durations if d < 1.0),
            },
            "analyzed_at": datetime.now().isoformat()
        }

    def _reconstruct_from_issue(self, issue) -> Dict[str, Any]:
        """从 JIRA Issue 重建时间线"""
        f = issue.fields
        created = self._parse_datetime(f.created)

        status_changes = []
        if hasattr(issue, 'changelog') and issue.changelog:
            for history in issue.changelog.histories:
                for item in history.items:
                    if item.field == 'status':
                        status_changes.append({
                            "from_status": item.fromString or "",
                            "to_status": item.toString or "",
                            "changed_at": self._parse_datetime(history.created),
                            "changed_by": history.author.displayName if history.author else None,
                            "comment": None
                        })

        # 按时间排序
        status_changes.sort(key=lambda x: x["changed_at"])

        resolved = None
        closed = None
        if hasattr(f, 'resolutiondate') and f.resolutiondate:
            resolved = self._parse_datetime(f.resolutiondate)
            if f.status.name in CLOSED_STATUSES:
                closed = resolved

        total_duration = 0.0
        active_duration = 0.0
        if created:
            end_time = closed or resolved or datetime.now(timezone.utc)
            total_duration = (end_time - created).total_seconds() / 86400

            if resolved:
                active_duration = (resolved - created).total_seconds() / 86400
            else:
                active_duration = (datetime.now(timezone.utc) - created).total_seconds() / 86400

        return {
            "defect_id": issue.key,
            "created": created.isoformat() if created else None,
            "status_changes": status_changes,
            "resolved": resolved.isoformat() if resolved else None,
            "closed": closed.isoformat() if closed else None,
            "total_duration_days": round(total_duration, 2),
            "active_duration_days": round(active_duration, 2)
        }

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """解析 ISO 格式日期时间"""
        if not dt_str:
            return None
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00")[:26])
        except ValueError:
            return None

    def _get_mock_timeline(self, defect_id: str) -> Dict[str, Any]:
        """返回模拟时间线数据"""
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=30)

        return {
            "defect_id": defect_id,
            "created": created.isoformat(),
            "status_changes": [
                {
                    "from_status": "",
                    "to_status": "Open",
                    "changed_at": created.isoformat(),
                    "changed_by": "System",
                    "comment": None
                },
                {
                    "from_status": "Open",
                    "to_status": "Working",
                    "changed_at": (created + timedelta(days=2)).isoformat(),
                    "changed_by": "Developer",
                    "comment": None
                },
                {
                    "from_status": "Working",
                    "to_status": "Fixed",
                    "changed_at": (created + timedelta(days=10)).isoformat(),
                    "changed_by": "Developer",
                    "comment": None
                },
                {
                    "from_status": "Fixed",
                    "to_status": "Verify",
                    "changed_at": (created + timedelta(days=12)).isoformat(),
                    "changed_by": "QA",
                    "comment": None
                }
            ],
            "resolved": None,
            "closed": None,
            "total_duration_days": 30.0,
            "active_duration_days": 30.0,
            "_mock": True
        }