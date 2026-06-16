"""
Defect Fact Tool - 缺陷事实提取工具

Fact Agent 的核心工具，负责从 JIRA 提取客观事实数据。
遵循原则：Fact Before Interpretation - 只提取事实，不做解释。
"""

import os
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .constants import (
    ACTIVE_STATUSES, REJECTED_STATUSES, VERIFY_STATUSES,
    LIMITATION_STATUSES, CLOSED_STATUSES, load_env
)
from .schemas import (
    DefectFact, Timeline, CloneInfo, Evidence, StatusChange,
    ConfidenceLevel, BatchExtractionResult
)
from .limitation_tool import LimitationTool

load_env()


class DefectFactTool:
    """
    缺陷事实提取工具

    从 JIRA 提取缺陷的客观事实，包括：
    - 基本信息（key, summary, severity, priority）
    - 时间线（created, status changes, resolution）
    - 克隆信息（is clone, parent, children）
    - 证据（从 comments/labels 提取）
    - TCI/PFI 指标（后续计算）
    """

    def __init__(self):
        self.jira_url = os.getenv("JIRA_URL", "")
        self.jira_pat = os.getenv("JIRA_PAT", "")
        self._client = None
        self._limitation_tool = None

    def _get_limitation_tool(self):
        """获取 LimitationTool 实例（懒加载）"""
        if self._limitation_tool is None:
            self._limitation_tool = LimitationTool()
        return self._limitation_tool

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

    def extract_defect_facts(self, defect_id: str) -> Dict[str, Any]:
        """
        提取单个缺陷的事实数据

        Args:
            defect_id: JIRA Issue Key (如 "OBMC-24951")

        Returns:
            包含缺陷事实的字典
        """
        client = self._get_client()
        if not client:
            return self._get_mock_fact(defect_id)

        try:
            issue = client.issue(defect_id)
            return self._extract_from_issue(issue)
        except Exception as e:
            # 返回 mock 数据作为降级方案
            return self._get_mock_fact(defect_id)

    def batch_extract_facts(
        self,
        project_id: str,
        max_results: int = 500
    ) -> BatchExtractionResult:
        """
        批量提取项目缺陷的事实数据

        Args:
            project_id: 项目 ID（如 "OBMC" 或 "9508"）
            max_results: 最大返回数量

        Returns:
            BatchExtractionResult 对象
        """
        client = self._get_client()
        result = BatchExtractionResult(
            project_id=project_id,
            total_defects=0,
            successful=0,
            failed=0
        )

        if not client:
            return self._get_mock_batch_result(project_id)

        try:
            # 判断 project_id 是项目 key 还是 release found ID
            if project_id.isdigit():
                jql = f'issuetype = Defect AND cf[13725] = "{project_id}"'
            else:
                jql = f'issuetype = Defect AND project = "{project_id}"'

            issues = client.search_issues(jql, maxResults=max_results)
            result.total_defects = len(issues)

            for issue in issues:
                try:
                    fact_dict = self._extract_from_issue(issue)
                    fact = DefectFact(
                        defect_id=fact_dict["defect_id"],
                        key=fact_dict["key"],
                        summary=fact_dict["summary"],
                        severity=fact_dict["severity"],
                        priority=fact_dict["priority"],
                        timeline=Timeline(**fact_dict["timeline"]),
                        clone_info=CloneInfo(**fact_dict["clone_info"]),
                        evidence=Evidence(**fact_dict["evidence"]),
                        limitation=fact_dict.get("limitation"),
                        tci=fact_dict.get("tci", 0.0),
                        pfi=fact_dict.get("pfi", 0.0),
                        confidence=fact_dict.get("confidence", 0.0),
                        source="jira"
                    )
                    result.facts.append(fact)
                    result.successful += 1
                except Exception as e:
                    result.failed += 1
                    result.errors.append({
                        "defect_id": issue.key,
                        "error": str(e)
                    })

            return result

        except Exception as e:
            result.errors.append({"error": str(e)})
            return result

    def _extract_from_issue(self, issue) -> Dict[str, Any]:
        """从 JIRA Issue 对象提取事实数据"""
        f = issue.fields

        # 提取 Severity
        severity_value = self._extract_field_value(f, "customfield_10690")

        # 提取 Platform Found (customfield_17100)
        platform_value = self._extract_field_value(f, "customfield_17100")

        # 提取 Project Found / Iteration Project (customfield_13725)
        project_value = self._extract_field_value(f, "customfield_13725")

        # 提取 Root Cause (from custom field)
        root_cause_value = self._extract_field_value(f, "customfield_11106")

        # 提取 Resolution
        resolution_value = f.resolution.name if hasattr(f, 'resolution') and f.resolution else None

        # 提取 Solution Explanation (customfield_11107)
        solution_explanation = self._extract_field_value(f, "customfield_11107")

        # 提取 Build Fixed (customfield_11112 - Build 版本号，如 IHX431T)
        build_fixed = self._extract_field_value(f, "customfield_11112")

        # 构建时间线
        timeline = self._build_timeline(issue)

        # 构建克隆信息
        clone_info = self._build_clone_info(issue)

        # 构建证据
        evidence = self._build_evidence(issue)

        # 提取 limitation 信息
        limitation_info = self._extract_limitation_info(issue)

        # 计算置信度（基于数据完整性）
        confidence = self._calculate_confidence(issue, evidence)

        return {
            "defect_id": issue.key,
            "key": issue.key,
            "summary": f.summary or "",
            "severity": severity_value,
            "platform_found": platform_value,
            "project_found": project_value,
            "priority": f.priority.name if f.priority else "Unknown",
            "status": f.status.name if f.status else "Unknown",
            "resolution": resolution_value,
            "solution_explanation": solution_explanation,
            "build_fixed": build_fixed,
            "root_cause": root_cause_value,
            "assignee": f.assignee.displayName if f.assignee else None,
            "reporter": f.reporter.displayName if f.reporter else None,
            "created": str(f.created) if f.created else None,
            "updated": str(f.updated) if f.updated else None,
            "resolved": str(f.resolutiondate) if hasattr(f, 'resolutiondate') and f.resolutiondate else None,
            "labels": f.labels or [],
            "components": [c.name for c in (f.components or [])],
            "timeline": timeline,
            "clone_info": clone_info,
            "evidence": evidence,
            "limitation": limitation_info,
            "confidence": confidence,
            "retrieved_at": datetime.now().isoformat()
        }

    def _extract_field_value(self, fields, field_id: str) -> str:
        """安全提取字段值（支持 JSON 数组格式 {"label": "...", "value": "..."}）"""
        import json

        if not hasattr(fields, field_id):
            return ""

        value = getattr(fields, field_id, None)
        if not value:
            return ""

        if isinstance(value, str):
            # 处理 JSON 格式 {"label": "...", "value": "..."}
            if value.startswith('{') and value.endswith('}'):
                try:
                    data = json.loads(value)
                    if 'label' in data:
                        return data['label']
                    elif 'value' in data:
                        return data['value']
                    return value
                except json.JSONDecodeError:
                    return value

            # 处理 JSON 数组格式 [{"label": "...", "value": "..."}]
            if value.startswith('[') and value.endswith(']'):
                try:
                    arr = json.loads(value)
                    if isinstance(arr, list) and len(arr) > 0:
                        item = arr[0]
                        if isinstance(item, dict):
                            if 'label' in item:
                                return item['label']
                            elif 'value' in item:
                                return item['value']
                        return str(item)
                except json.JSONDecodeError:
                    return value

            return value
        elif hasattr(value, 'value'):
            return value.value
        elif isinstance(value, dict):
            return value.get('label', '')
        else:
            return str(value)

    def _build_timeline(self, issue) -> Dict[str, Any]:
        """构建缺陷时间线"""
        f = issue.fields
        created = self._parse_datetime(f.created)

        status_changes = []
        # 从 changelog 中提取状态变更
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

        # 计算活跃天数
        duration_days = None
        if created:
            end_date = resolved if resolved else datetime.now(timezone.utc)
            duration_days = (end_date - created).total_seconds() / 86400
            duration_days = round(duration_days, 1)

        return {
            "defect_id": issue.key,
            "created": created.isoformat() if created else None,
            "status_changes": status_changes,
            "resolved": resolved.isoformat() if resolved else None,
            "closed": closed.isoformat() if closed else None,
            "duration_days": duration_days
        }

    def _build_clone_info(self, issue) -> Dict[str, Any]:
        """构建克隆信息"""
        f = issue.fields

        # 检查是否是克隆
        # 方法1: 从 labels 检测
        labels = f.labels or []
        is_clone = "clone" in [l.lower() for l in labels]

        # 方法2: 从 summary 检测 "Cloned from XXX"
        summary = f.summary or ""
        parent_match = re.search(r'[Cc]loned from[:\s]+([A-Z]+-\d+)', summary)
        parent_id = parent_match.group(1) if parent_match else None
        if parent_id:
            is_clone = True

        # 方法3: 从 links 检测
        if hasattr(f, 'issuelinks'):
            for link in f.issuelinks:
                if hasattr(link, 'type') and link.type.name in ('Clone', 'Cloners'):
                    if hasattr(link, 'outwardIssue'):
                        parent_id = link.outwardIssue.key
                        is_clone = True
                    elif hasattr(link, 'inwardIssue'):
                        parent_id = link.inwardIssue.key
                        is_clone = True

        # 查找子克隆（反向查找）
        child_ids = []
        try:
            client = self._get_client()
            if client:
                links = client.remote_links(issue)
                for link in links:
                    if link.type.name == 'Clone':
                        child_ids.append(link.targetIssue.key)
        except Exception:
            pass

        return {
            "defect_id": issue.key,
            "is_clone": is_clone,
            "parent_id": parent_id,
            "child_ids": child_ids,
            "clone_chain": [parent_id] if parent_id else [],
            "clone_depth": 1 if is_clone else 0
        }

    def _build_evidence(self, issue) -> Dict[str, Any]:
        """从 comments 和 labels 提取证据"""
        f = issue.fields

        evidence = {
            "defect_id": issue.key,
            "customer_impact": None,
            "workaround_exists": None,
            "no_regression": None,
            "root_cause_analysis": None,
            "reproduction_steps": None,
            "test_coverage": None,
            "customer_visibility": None
        }

        # 从 labels 提取证据标记
        labels = [l.lower() for l in (f.labels or [])]

        # 检测 customer_impact 证据
        if any(l in labels for l in ['customer-impact', 'ci', 'customer_visible']):
            evidence["customer_impact"] = {"source": "label", "verified": True}

        # 检测 workaround 证据
        if any(l in labels for l in ['workaround', 'has-workaround']):
            evidence["workaround_exists"] = {"source": "label", "verified": True}

        # 检测 no_regression 证据
        if any(l in labels for l in ['no-regression', 'regression-free']):
            evidence["no_regression"] = {"source": "label", "verified": True}

        # 从 comments 提取详细证据
        try:
            if hasattr(issue, 'fields') and hasattr(f, 'comment'):
                comments = issue.fields.comment.comments if hasattr(f.comment, 'comments') else []
                for comment in comments:
                    body = comment.body.lower() if hasattr(comment, 'body') else ""

                    # 提取 customer impact 详情
                    if not evidence["customer_impact"] and any(k in body for k in ['customer', 'user impact', 'visible']):
                        evidence["customer_impact"] = {
                            "source": "comment",
                            "comment_id": comment.id,
                            "verified": True
                        }

                    # 提取 workaround 详情
                    if not evidence["workaround_exists"] and any(k in body for k in ['workaround', 'temporary fix', 'bypass']):
                        evidence["workaround_exists"] = {
                            "source": "comment",
                            "comment_id": comment.id,
                            "verified": True
                        }

                    # 提取 reproduction steps
                    if not evidence["reproduction_steps"] and any(k in body for k in ['steps to reproduce', 'reproduce', 'repro']):
                        evidence["reproduction_steps"] = {
                            "source": "comment",
                            "comment_id": comment.id,
                            "verified": True
                        }

                    # 提取 root cause analysis
                    if not evidence["root_cause_analysis"] and any(k in body for k in ['root cause', 'rc:', 'analysis']):
                        evidence["root_cause_analysis"] = {
                            "source": "comment",
                            "comment_id": comment.id,
                            "verified": True
                        }
        except Exception:
            pass

        return evidence

    def _extract_limitation_info(self, issue) -> Dict[str, Any]:
        """提取 limitation 信息"""
        limitation_tool = self._get_limitation_tool()
        return limitation_tool.extract_limitation_info(issue.key)

    def _calculate_confidence(self, issue, evidence: Dict[str, Any]) -> float:
        """
        计算数据置信度

        基于数据完整性评分
        """
        score = 0.0
        max_score = 10.0

        # 基本字段
        if issue.fields.summary:
            score += 1.0
        if issue.fields.priority:
            score += 1.0
        if hasattr(issue.fields, 'resolutiondate') and issue.fields.resolutiondate:
            score += 1.0
        if issue.fields.assignee:
            score += 1.0

        # 证据完整性
        evidence_count = sum(1 for v in evidence.values() if v is not None and v != "defect_id")
        score += evidence_count * 1.0

        # changelog 可用性
        if hasattr(issue, 'changelog') and issue.changelog:
            score += 2.0

        return min(score / max_score, 1.0)

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

    def _get_mock_fact(self, defect_id: str) -> Dict[str, Any]:
        """返回模拟缺陷事实数据"""
        return {
            "defect_id": defect_id,
            "key": defect_id,
            "summary": f"[Mock] Sample defect {defect_id} for testing",
            "severity": "Medium",
            "priority": "Medium",
            "status": "Working",
            "assignee": "Test User",
            "reporter": "Test Reporter",
            "created": datetime.now(timezone.utc).isoformat(),
            "updated": datetime.now(timezone.utc).isoformat(),
            "resolved": None,
            "labels": ["mock-data"],
            "components": ["Component A"],
            "platform": "GNR",
            "root_cause": None,
            "timeline": {
                "defect_id": defect_id,
                "created": datetime.now().isoformat(),
                "status_changes": [
                    {
                        "from_status": "",
                        "to_status": "Open",
                        "changed_at": datetime.now().isoformat(),
                        "changed_by": "System",
                        "comment": None
                    },
                    {
                        "from_status": "Open",
                        "to_status": "Working",
                        "changed_at": datetime.now().isoformat(),
                        "changed_by": "Test User",
                        "comment": None
                    }
                ],
                "resolved": None,
                "closed": None
            },
            "clone_info": {
                "defect_id": defect_id,
                "is_clone": False,
                "parent_id": None,
                "child_ids": [],
                "clone_chain": [],
                "clone_depth": 0
            },
            "evidence": {
                "defect_id": defect_id,
                "customer_impact": None,
                "workaround_exists": {"source": "mock", "verified": True},
                "no_regression": None,
                "root_cause_analysis": None,
                "reproduction_steps": None,
                "test_coverage": None,
                "customer_visibility": None
            },
            "limitation": {
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
                "retrieved_at": datetime.now(timezone.utc).isoformat()
            },
            "confidence": 0.75,
            "retrieved_at": datetime.now().isoformat(),
            "_mock": True
        }

    def _get_mock_batch_result(self, project_id: str) -> BatchExtractionResult:
        """返回模拟批量结果"""
        result = BatchExtractionResult(
            project_id=project_id,
            total_defects=5,
            successful=5,
            failed=0
        )

        for i in range(5):
            defect_id = f"{project_id}-{100 + i}"
            fact_dict = self._get_mock_fact(defect_id)
            fact = DefectFact(
                defect_id=defect_id,
                key=fact_dict["key"],
                summary=fact_dict["summary"],
                severity=fact_dict["severity"],
                priority=fact_dict["priority"],
                timeline=Timeline(**fact_dict["timeline"]),
                clone_info=CloneInfo(**fact_dict["clone_info"]),
                evidence=Evidence(**fact_dict["evidence"]),
                limitation=fact_dict.get("limitation"),
                confidence=fact_dict["confidence"],
                source="mock"
            )
            result.facts.append(fact)

        return result