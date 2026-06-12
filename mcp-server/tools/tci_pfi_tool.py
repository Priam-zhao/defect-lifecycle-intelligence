"""
TCI/PFI Tool - 时间效率指标计算工具

TCI (Time-to-Close Index): 缺陷关闭效率指数
PFI (Platform-First Index): 平台优先指数

注意: TCI/PFI 的具体计算公式需要在实际使用中根据业务需求调整
"""

import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .constants import (
    CLOSED_STATUSES, RESOLVED_STATUSES, load_env
)
from .schemas import ConfidenceLevel

load_env()


class TciPfiTool:
    """
    TCI/PFI 指标计算工具

    TCI (Time-to-Close Index):
    - 衡量缺陷从创建到关闭的时间效率
    - 公式: TCI = 1 - (actual_days / expected_days)
    - 范围: 0-1, 越高表示效率越高

    PFI (Platform-First Index):
    - 衡量缺陷是否优先在平台侧解决
    - 考虑因素: 根本原因位置、修复位置、涉及组件
    - 范围: 0-1, 越高表示越符合平台优先策略
    """

    # 默认预期关闭时间（天）- 按严重程度
    DEFAULT_EXPECTED_DAYS = {
        "Blocker": 3,
        "Critical": 7,
        "Highest": 10,
        "High": 14,
        "Major": 21,
        "Medium": 30,
        "Low": 60,
        "Lowest": 90
    }

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

    def calculate_tci(
        self,
        defect_id: str,
        expected_days: Optional[float] = None,
        severity: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        计算 TCI (Time-to-Close Index)

        Args:
            defect_id: JIRA Issue Key
            expected_days: 预期关闭天数（可选，默认根据严重程度）
            severity: 严重程度（用于计算默认预期天数）

        Returns:
            TCI 计算结果
        """
        client = self._get_client()
        if not client:
            return self._get_mock_tci(defect_id)

        try:
            issue = client.issue(defect_id)
            f = issue.fields

            # 解析日期
            created = self._parse_datetime(f.created)
            resolved = self._parse_datetime(f.resolutiondate) if hasattr(f, 'resolutiondate') and f.resolutiondate else None

            if not created:
                return self._get_mock_tci(defect_id)

            # 计算实际天数
            end_time = resolved or datetime.now(timezone.utc)
            actual_days = (end_time - created).total_seconds() / 86400

            # 获取预期天数
            if not expected_days:
                if severity:
                    expected_days = self.DEFAULT_EXPECTED_DAYS.get(severity, 30)
                elif f.priority and f.priority.name:
                    expected_days = self.DEFAULT_EXPECTED_DAYS.get(f.priority.name, 30)
                else:
                    expected_days = 30

            # 计算 TCI
            # TCI = 1 - (actual_days / expected_days)
            # 范围: [0, 1], 负值截断为 0
            tci = 1 - (actual_days / expected_days)
            tci = max(0.0, min(1.0, tci))  # 限制在 0-1 范围

            # 计算置信度（基于数据完整性）
            confidence = self._calculate_confidence(issue, resolved)

            return {
                "defect_id": defect_id,
                "tci": round(tci, 3),
                "actual_days": round(actual_days, 2),
                "expected_days": expected_days,
                "severity": f.priority.name if f.priority else None,
                "confidence": round(confidence, 3),
                "confidence_level": self._get_confidence_level(confidence),
                "is_closed": f.status.name in CLOSED_STATUSES if f.status else False,
                "calculated_at": datetime.now().isoformat()
            }

        except Exception:
            return self._get_mock_tci(defect_id)

    def calculate_pfi(
        self,
        defect_id: str,
        platform_field: Optional[str] = None,
        root_cause_field: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        计算 PFI (Platform-First Index)

        PFI 评估缺陷是否应该优先在平台侧解决：
        - 因素 1: 根本原因是否在平台层 (权重 40%)
        - 因素 2: 修复是否应该在平台层 (权重 30%)
        - 因素 3: 涉及组件是否属于平台 (权重 30%)

        Args:
            defect_id: JIRA Issue Key
            platform_field: 平台字段值（可选）
            root_cause_field: 根本原因字段值（可选）

        Returns:
            PFI 计算结果
        """
        client = self._get_client()
        if not client:
            return self._get_mock_pfi(defect_id)

        try:
            issue = client.issue(defect_id)
            f = issue.fields

            # 提取关键信息
            components = [c.name for c in (f.components or [])]
            labels = f.labels or []

            # 因素 1: 根本原因位置
            root_cause_score = self._evaluate_root_cause(
                root_cause_field or "",
                labels
            )

            # 因素 2: 修复位置
            fix_location_score = self._evaluate_fix_location(
                platform_field or "",
                labels,
                f.summary or ""
            )

            # 因素 3: 涉及组件
            component_score = self._evaluate_components(components)

            # 加权计算 PFI
            pfi = (
                root_cause_score * 0.40 +
                fix_location_score * 0.30 +
                component_score * 0.30
            )

            # 置信度
            confidence = self._calculate_pfi_confidence(
                root_cause_field,
                platform_field,
                components
            )

            return {
                "defect_id": defect_id,
                "pfi": round(pfi, 3),
                "factors": {
                    "root_cause_score": round(root_cause_score, 3),
                    "fix_location_score": round(fix_location_score, 3),
                    "component_score": round(component_score, 3)
                },
                "components": components,
                "root_cause_field": root_cause_field,
                "platform_field": platform_field,
                "confidence": round(confidence, 3),
                "confidence_level": self._get_confidence_level(confidence),
                "calculated_at": datetime.now().isoformat()
            }

        except Exception:
            return self._get_mock_pfi(defect_id)

    def batch_calculate_tci_pfi(
        self,
        defect_ids: List[str]
    ) -> Dict[str, Any]:
        """
        批量计算多个缺陷的 TCI 和 PFI

        Args:
            defect_ids: 缺陷 ID 列表

        Returns:
            批量计算结果
        """
        tci_results = []
        pfi_results = []

        for defect_id in defect_ids:
            tci_result = self.calculate_tci(defect_id)
            pfi_result = self.calculate_pfi(defect_id)

            tci_results.append(tci_result)
            pfi_results.append(pfi_result)

        # 统计分析
        tci_values = [r["tci"] for r in tci_results if r.get("tci") is not None]
        pfi_values = [r["pfi"] for r in pfi_results if r.get("pfi") is not None]

        return {
            "total_defects": len(defect_ids),
            "tci": {
                "count": len(tci_values),
                "average": round(sum(tci_values) / len(tci_values), 3) if tci_values else 0,
                "min": round(min(tci_values), 3) if tci_values else 0,
                "max": round(max(tci_values), 3) if tci_values else 0,
                "distribution": self._get_tci_distribution(tci_values)
            },
            "pfi": {
                "count": len(pfi_values),
                "average": round(sum(pfi_values) / len(pfi_values), 3) if pfi_values else 0,
                "min": round(min(pfi_values), 3) if pfi_values else 0,
                "max": round(max(pfi_values), 3) if pfi_values else 0,
                "distribution": self._get_pfi_distribution(pfi_values)
            },
            "results": tci_results,
            "calculated_at": datetime.now().isoformat()
        }

    def get_tci_pfi_trend(
        self,
        project_id: str,
        time_range: str = "month"
    ) -> Dict[str, Any]:
        """
        获取项目的 TCI/PFI 趋势数据

        Args:
            project_id: 项目 ID
            time_range: 时间范围 ("week", "month", "quarter")

        Returns:
            趋势数据
        """
        # 获取项目的所有缺陷
        client = self._get_client()
        if not client:
            return self._get_mock_trend(project_id)

        try:
            # 根据 project_id 类型构建 JQL
            if project_id.isdigit():
                jql = f'issuetype = Defect AND cf[13725] = "{project_id}"'
            else:
                jql = f'issuetype = Defect AND project = "{project_id}"'

            issues = client.search_issues(jql, maxResults=500)
            defect_ids = [issue.key for issue in issues]

            # 计算每个缺陷的 TCI/PFI
            trend_data = []
            for defect_id in defect_ids:
                tci = self.calculate_tci(defect_id)
                pfi = self.calculate_pfi(defect_id)

                created = self._parse_datetime(issues[[i.key for i in issues].index(defect_id)].fields.created)
                week = created.strftime("%Y-W%W") if created else "unknown"

                trend_data.append({
                    "defect_id": defect_id,
                    "week": week,
                    "tci": tci["tci"],
                    "pfi": pfi["pfi"]
                })

            # 按周聚合
            week_data = {}
            for item in trend_data:
                week = item["week"]
                if week not in week_data:
                    week_data[week] = {"tci_sum": 0, "pfi_sum": 0, "count": 0}
                week_data[week]["tci_sum"] += item["tci"]
                week_data[week]["pfi_sum"] += item["pfi"]
                week_data[week]["count"] += 1

            # 计算每周平均值
            weekly_trend = []
            for week in sorted(week_data.keys()):
                data = week_data[week]
                weekly_trend.append({
                    "week": week,
                    "avg_tci": round(data["tci_sum"] / data["count"], 3),
                    "avg_pfi": round(data["pfi_sum"] / data["count"], 3),
                    "defect_count": data["count"]
                })

            return {
                "project_id": project_id,
                "time_range": time_range,
                "weekly_trend": weekly_trend,
                "total_weeks": len(weekly_trend),
                "generated_at": datetime.now().isoformat()
            }

        except Exception:
            return self._get_mock_trend(project_id)

    # ========== 辅助方法 ==========

    def _evaluate_root_cause(self, root_cause: str, labels: List[str]) -> float:
        """
        评估根本原因是否在平台层

        平台层关键词: platform, firmware, bios, driver, hardware, infrastructure
        """
        if not root_cause and not labels:
            return 0.5  # 无数据，默认中等

        platform_keywords = [
            "platform", "firmware", "bios", "driver", "hardware",
            "infrastructure", "kernel", "os", "system"
        ]

        combined_text = (root_cause + " " + " ".join(labels)).lower()
        matches = sum(1 for kw in platform_keywords if kw in combined_text)

        if matches >= 3:
            return 0.9
        elif matches >= 2:
            return 0.7
        elif matches >= 1:
            return 0.5
        else:
            return 0.3

    def _evaluate_fix_location(self, platform_field: str, labels: List[str], summary: str) -> float:
        """
        评估修复是否应该在平台层
        """
        if not platform_field and not labels and not summary:
            return 0.5

        fix_location_keywords = [
            "platform fix", "fw fix", "fw change", "driver update",
            "bios update", "kernel patch"
        ]

        combined_text = (platform_field + " " + summary + " " + " ".join(labels)).lower()
        matches = sum(1 for kw in fix_location_keywords if kw in combined_text)

        if matches >= 2:
            return 0.8
        elif matches >= 1:
            return 0.6
        else:
            return 0.4

    def _evaluate_components(self, components: List[str]) -> float:
        """
        评估涉及组件是否属于平台
        """
        if not components:
            return 0.5

        platform_components = [
            "platform", "fw", "firmware", "driver", "bios",
            "kernel", "system", "infrastructure"
        ]

        platform_count = sum(
            1 for c in components
            if any(pc in c.lower() for pc in platform_components)
        )

        return min(1.0, platform_count / max(1, len(components)))

    def _calculate_confidence(self, issue, resolved) -> float:
        """计算 TCI 计算置信度"""
        score = 0.0

        if issue.fields.created:
            score += 0.3
        if resolved:
            score += 0.3
        if issue.fields.priority:
            score += 0.2
        if issue.fields.status:
            score += 0.2

        return score

    def _calculate_pfi_confidence(
        self,
        root_cause: Optional[str],
        platform: Optional[str],
        components: List[str]
    ) -> float:
        """计算 PFI 计算置信度"""
        score = 0.0

        if root_cause:
            score += 0.4
        if platform:
            score += 0.3
        if components:
            score += 0.3

        return score

    def _get_confidence_level(self, confidence: float) -> str:
        """获取置信度等级"""
        if confidence >= 0.90:
            return "high"
        elif confidence >= 0.75:
            return "medium"
        else:
            return "low"

    def _get_tci_distribution(self, values: List[float]) -> Dict[str, int]:
        """获取 TCI 分布"""
        return {
            "excellent": sum(1 for v in values if v >= 0.8),  # TCI >= 0.8
            "good": sum(1 for v in values if 0.5 <= v < 0.8),   # 0.5 <= TCI < 0.8
            "fair": sum(1 for v in values if 0.2 <= v < 0.5),  # 0.2 <= TCI < 0.5
            "poor": sum(1 for v in values if v < 0.2)          # TCI < 0.2
        }

    def _get_pfi_distribution(self, values: List[float]) -> Dict[str, int]:
        """获取 PFI 分布"""
        return {
            "high_priority": sum(1 for v in values if v >= 0.7),   # PFI >= 0.7
            "medium_priority": sum(1 for v in values if 0.4 <= v < 0.7),  # 0.4 <= PFI < 0.7
            "low_priority": sum(1 for v in values if v < 0.4)     # PFI < 0.4
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

    def _get_mock_tci(self, defect_id: str) -> Dict[str, Any]:
        """返回模拟 TCI 数据"""
        return {
            "defect_id": defect_id,
            "tci": 0.75,
            "actual_days": 7.5,
            "expected_days": 30,
            "severity": "Medium",
            "confidence": 0.85,
            "confidence_level": "high",
            "is_closed": True,
            "calculated_at": datetime.now().isoformat(),
            "_mock": True
        }

    def _get_mock_pfi(self, defect_id: str) -> Dict[str, Any]:
        """返回模拟 PFI 数据"""
        return {
            "defect_id": defect_id,
            "pfi": 0.65,
            "factors": {
                "root_cause_score": 0.7,
                "fix_location_score": 0.6,
                "component_score": 0.6
            },
            "components": ["Platform", "Driver"],
            "root_cause_field": "platform",
            "platform_field": "GNR",
            "confidence": 0.8,
            "confidence_level": "high",
            "calculated_at": datetime.now().isoformat(),
            "_mock": True
        }

    def _get_mock_trend(self, project_id: str) -> Dict[str, Any]:
        """返回模拟趋势数据"""
        return {
            "project_id": project_id,
            "time_range": "month",
            "weekly_trend": [
                {"week": "2026-W22", "avg_tci": 0.72, "avg_pfi": 0.60, "defect_count": 5},
                {"week": "2026-W23", "avg_tci": 0.75, "avg_pfi": 0.65, "defect_count": 8},
                {"week": "2026-W24", "avg_tci": 0.78, "avg_pfi": 0.68, "defect_count": 6},
            ],
            "total_weeks": 3,
            "generated_at": datetime.now().isoformat(),
            "_mock": True
        }