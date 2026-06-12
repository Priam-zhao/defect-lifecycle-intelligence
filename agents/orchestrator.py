"""
Agent Orchestrator - Agent 编排器

职责：
- 协调 Fact Agent、Review Agent、Advisor Agent 的执行
- 提供完整缺陷分析流程
- 支持批量处理和错误恢复
- 生成 Pipeline 指纹用于追踪和审计
"""

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from .base import BaseAgent
from .fact_agent import FactAgent
from .review_agent import ReviewAgent
from .advisor_agent import AdvisorAgent


class AgentOrchestrator:
    """
    Agent 编排器 - 协调三个 Agent 的执行

    执行流程:
    1. 调用 Fact Agent 提取事实
    2. 调用 Review Agent 进行合规审查
    3. 调用 Advisor Agent 生成建议
    4. 返回完整分析报告

    设计原则：Pipeline Architecture
    - 流水线式处理，确保数据一致性
    - 每个阶段的结果传递给下一个阶段
    - 支持断点续传和错误恢复
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        mcp_client=None,
        rules_config_path: Optional[str] = None
    ):
        """
        初始化 Agent Orchestrator

        Args:
            mcp_client: MCP 客户端（可选）
            rules_config_path: 规则配置文件路径（可选）
        """
        # 初始化三个 Agent
        self.fact_agent = FactAgent(mcp_client)
        self.review_agent = ReviewAgent(mcp_client, rules_config_path)
        self.advisor_agent = AdvisorAgent(mcp_client)

        self.mcp_client = mcp_client
        self.rules_config_path = rules_config_path

    async def analyze_defect(
        self,
        defect_id: str,
        include_facts: bool = True,
        include_review: bool = True,
        include_advisor: bool = True
    ) -> Dict[str, Any]:
        """
        完整缺陷分析流程

        Args:
            defect_id: JIRA Issue Key
            include_facts: 是否包含事实数据
            include_review: 是否包含审查决策
            include_advisor: 是否包含建议

        Returns:
            包含 Fact + Review + Advisor 输出的完整报告
        """
        pipeline_fingerprint = self._generate_pipeline_fingerprint()
        started_at = datetime.now()

        result = {
            "defect_id": defect_id,
            "pipeline_fingerprint": pipeline_fingerprint,
            "pipeline_version": self.VERSION,
            "started_at": started_at.isoformat(),
            "status": "in_progress"
        }

        try:
            # 阶段 1: Fact Agent
            if include_facts:
                fact_result = await self.fact_agent.execute(defect_id)
                if fact_result.get("status") == "success":
                    result["fact"] = fact_result.get("data", {})
                    result["fact_status"] = "success"
                else:
                    result["fact"] = fact_result
                    result["fact_status"] = "failed"
            else:
                result["fact_status"] = "skipped"

            # 阶段 2: Review Agent
            if include_review and result.get("fact_status") == "success":
                # Review Agent 需要 fact 数据作为输入
                fact_data = result.get("fact", {})
                review_result = await self.review_agent.execute(fact_data)
                if review_result.get("status") == "success":
                    result["review"] = review_result.get("data", {})
                    result["review_status"] = "success"
                else:
                    result["review"] = review_result
                    result["review_status"] = "failed"
            else:
                result["review_status"] = "skipped"

            # 阶段 3: Advisor Agent
            if include_advisor:
                if result.get("fact_status") == "success":
                    fact_data = result.get("fact", {})
                    review_data = result.get("review", {})
                    similar_cases = fact_data.get("similar_cases", [])

                    advisor_result = await self.advisor_agent.execute(
                        fact_data,
                        review_data,
                        similar_cases
                    )
                    if advisor_result.get("status") == "success":
                        result["advisor"] = advisor_result.get("data", {})
                        result["advisor_status"] = "success"
                    else:
                        result["advisor"] = advisor_result
                        result["advisor_status"] = "failed"
                else:
                    result["advisor_status"] = "skipped"
            else:
                result["advisor_status"] = "skipped"

            # 计算总体状态
            statuses = [
                result.get("fact_status"),
                result.get("review_status"),
                result.get("advisor_status")
            ]
            if all(s == "success" for s in statuses if s):
                result["status"] = "success"
            elif any(s == "failed" for s in statuses):
                result["status"] = "partial"
            else:
                result["status"] = "failed"

        except Exception as e:
            result["status"] = "error"
            result["error"] = {
                "message": str(e),
                "type": type(e).__name__
            }

        finally:
            result["completed_at"] = datetime.now().isoformat()
            result["duration_ms"] = int(
                (datetime.now() - started_at).total_seconds() * 1000
            )

        return result

    async def analyze_defect_fast(
        self,
        defect_id: str
    ) -> Dict[str, Any]:
        """
        快速分析缺陷（仅获取关键结果）

        适用于需要快速响应的场景

        Args:
            defect_id: JIRA Issue Key

        Returns:
            精简的分析结果
        """
        # 并行执行 Fact 和 Review
        fact_task = self.fact_agent.execute(defect_id)
        review_task = self.review_agent.execute(defect_id)

        fact_result, review_result = await asyncio.gather(
            fact_task,
            review_task,
            return_exceptions=True
        )

        # 处理异常
        if isinstance(fact_result, Exception):
            return {
                "defect_id": defect_id,
                "status": "error",
                "error": f"Fact extraction failed: {str(fact_result)}"
            }

        if isinstance(review_result, Exception):
            return {
                "defect_id": defect_id,
                "status": "error",
                "error": f"Review failed: {str(review_result)}"
            }

        # 提取关键信息
        fact_data = fact_result.get("data", {})
        review_data = review_result.get("data", {})

        return {
            "defect_id": defect_id,
            "status": "success",
            "severity": fact_data.get("severity"),
            "decision_type": review_data.get("decision", {}).get("decision_type"),
            "confidence": review_data.get("decision", {}).get("confidence"),
            "active_weeks": fact_data.get("active_weeks"),
            "tci": fact_data.get("tci"),
            "summary": fact_data.get("summary", "")[:100]
        }

    async def batch_analyze(
        self,
        defect_ids: List[str],
        max_concurrent: int = 3,
        stop_on_error: bool = False,
        callback=None
    ) -> Dict[str, Any]:
        """
        批量分析多个缺陷

        Args:
            defect_ids: 缺陷 ID 列表
            max_concurrent: 最大并发数
            stop_on_error: 遇到错误是否停止
            callback: 进度回调函数

        Returns:
            批量分析结果
        """
        started_at = datetime.now()
        results = []
        errors = []
        success_count = 0
        failed_count = 0

        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(defect_id: str, index: int) -> Dict[str, Any]:
            async with semaphore:
                if callback:
                    callback(index, len(defect_ids), defect_id)

                try:
                    result = await self.analyze_defect(defect_id)
                    return result
                except Exception as e:
                    return {
                        "defect_id": defect_id,
                        "status": "error",
                        "error": str(e)
                    }

        # 创建任务列表
        tasks = [
            analyze_with_semaphore(did, i)
            for i, did in enumerate(defect_ids)
        ]

        # 并发执行
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for result in task_results:
            if isinstance(result, Exception):
                errors.append({
                    "defect_id": "unknown",
                    "error": str(result)
                })
                failed_count += 1
            elif result.get("status") == "success":
                results.append(result)
                success_count += 1
            else:
                errors.append({
                    "defect_id": result.get("defect_id", "unknown"),
                    "error": result.get("error", {}).get("message", "Unknown error")
                })
                failed_count += 1

                if stop_on_error:
                    # 取消剩余任务
                    pass

        completed_at = datetime.now()

        return {
            "total": len(defect_ids),
            "successful": success_count,
            "failed": failed_count,
            "success_rate": success_count / len(defect_ids) if defect_ids else 0,
            "results": results,
            "errors": errors,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": (completed_at - started_at).total_seconds()
        }

    async def get_defect_summary(
        self,
        defect_id: str
    ) -> Dict[str, Any]:
        """
        获取缺陷摘要（最简化版本）

        适用于列表展示等场景

        Args:
            defect_id: JIRA Issue Key

        Returns:
            缺陷摘要
        """
        fact_result = await self.fact_agent.execute(defect_id)

        if fact_result.get("status") != "success":
            return {
                "defect_id": defect_id,
                "error": "Failed to retrieve defect facts"
            }

        fact_data = fact_result.get("data", {})

        return {
            "defect_id": defect_id,
            "summary": fact_data.get("summary", "")[:80],
            "severity": fact_data.get("severity"),
            "status": fact_data.get("status"),
            "assignee": fact_data.get("assignee"),
            "active_weeks": fact_data.get("active_weeks", 0),
            "tci": fact_data.get("tci", 0),
            "pfi": fact_data.get("pfi", 0),
            "confidence": fact_data.get("confidence", 0),
            "has_anomalies": fact_data.get("anomaly_count", 0) > 0
        }

    def _generate_pipeline_fingerprint(self) -> str:
        """
        生成 Pipeline 指纹

        用于追踪和审计

        Returns:
            指纹字符串
        """
        timestamp = datetime.now().isoformat()
        content = f"orchestrator:{self.VERSION}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_pipeline_info(self) -> Dict[str, Any]:
        """
        获取 Pipeline 信息

        Returns:
            Pipeline 信息字典
        """
        return {
            "version": self.VERSION,
            "agents": {
                "fact": {
                    "name": self.fact_agent.name,
                    "version": self.fact_agent.version
                },
                "review": {
                    "name": self.review_agent.name,
                    "version": self.review_agent.version,
                    "rule_engine_version": self.review_agent.rule_engine.config.get("version", "1.0.0")
                },
                "advisor": {
                    "name": self.advisor_agent.name,
                    "version": self.advisor_agent.version
                }
            },
            "features": [
                "fact_extraction",
                "compliance_review",
                "recommendation_generation",
                "batch_processing",
                "error_recovery"
            ]
        }


class HumanFeedbackFlywheel:
    """
    Human Feedback Flywheel - 人类反馈循环

    职责：
    - 记录人类覆盖事件
    - 检测纠正模式
    - 生成模式建议

    设计原则：Human Authority Supremacy
    - 人类审查员是最终权威
    - 系统从人类反馈中学习
    """

    VERSION = "1.0.0"

    def __init__(self, knowledge_store_path: Optional[str] = None):
        """
        初始化 Human Feedback Flywheel

        Args:
            knowledge_store_path: 知识库路径（可选）
        """
        if knowledge_store_path is None:
            import os
            base_dir = os.path.dirname(os.path.dirname(__file__))
            knowledge_store_path = os.path.join(base_dir, "knowledge_store")

        self.knowledge_store_path = knowledge_store_path
        self._ensure_knowledge_store()

    def _ensure_knowledge_store(self):
        """确保知识库目录存在"""
        import os
        os.makedirs(self.knowledge_store_path, exist_ok=True)

    def record_override(
        self,
        defect_id: str,
        system_decision: str,
        human_decision: str,
        reason: str,
        reviewer: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        记录人类覆盖事件

        Args:
            defect_id: 缺陷 ID
            system_decision: 系统决策类型
            human_decision: 人类决策类型
            reason: 覆盖原因
            reviewer: 审查员
            metadata: 额外元数据

        Returns:
            覆盖事件记录
        """
        from .schemas_compat import OverrideEvent

        event = OverrideEvent(
            defect_id=defect_id,
            system_decision=system_decision,
            human_decision=human_decision,
            reason=reason,
            reviewer=reviewer
        )

        # 保存到知识库
        event_data = event.to_dict()
        self._save_override_event(event_data)

        # 检查是否需要生成纠正模式
        pattern = self._check_and_generate_pattern(event_data)

        return {
            "event": event_data,
            "pattern_detected": pattern is not None,
            "pattern": pattern.to_dict() if pattern else None
        }

    def _save_override_event(self, event_data: Dict[str, Any]):
        """保存覆盖事件到知识库"""
        import os
        import json

        events_dir = os.path.join(self.knowledge_store_path, "override_events")
        os.makedirs(events_dir, exist_ok=True)

        # 使用时间戳作为文件名
        timestamp = event_data.get("timestamp", datetime.now().isoformat())
        filename = f"override_{timestamp.replace(':', '-').replace('.', '-')}.json"

        filepath = os.path.join(events_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(event_data, f, indent=2, ensure_ascii=False)

    def _check_and_generate_pattern(
        self,
        event_data: Dict[str, Any]
    ) -> Optional[Any]:
        """
        检查并生成纠正模式

        当同一模式出现 >= 3 次时生成纠正模式

        Args:
            event_data: 覆盖事件数据

        Returns:
            纠正模式（如果有）
        """
        from .schemas_compat import CorrectionPattern

        # 查找相似的覆盖事件
        similar_events = self._find_similar_override_events(event_data)

        if len(similar_events) >= 3:
            # 生成纠正模式
            pattern = self._generate_correction_pattern(similar_events)
            self._save_correction_pattern(pattern)
            return pattern

        return None

    def _find_similar_override_events(
        self,
        event_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        查找相似的覆盖事件

        Args:
            event_data: 覆盖事件数据

        Returns:
            相似事件列表
        """
        import os
        import json
        import glob

        events_dir = os.path.join(self.knowledge_store_path, "override_events")
        if not os.path.exists(events_dir):
            return []

        # 获取最近的事件（30天内）
        recent_events = []
        pattern = os.path.join(events_dir, "override_*.json")
        cutoff_time = datetime.now().timestamp() - 30 * 24 * 3600

        for filepath in glob.glob(pattern):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    event = json.load(f)
                    event_time = datetime.fromisoformat(
                        event.get("timestamp", "1970-01-01")
                    ).timestamp()
                    if event_time >= cutoff_time:
                        recent_events.append(event)
            except Exception:
                continue

        # 筛选相似事件
        similar = []
        for event in recent_events:
            if (event.get("system_decision") == event_data.get("system_decision") and
                event.get("human_decision") == event_data.get("human_decision")):
                similar.append(event)

        return similar

    def _generate_correction_pattern(
        self,
        events: List[Dict[str, Any]]
    ) -> "CorrectionPattern":
        """
        生成纠正模式

        Args:
            events: 相似事件列表

        Returns:
            纠正模式
        """
        from .schemas_compat import CorrectionPattern

        # 统计人类决策分布
        human_decisions = {}
        for event in events:
            hd = event.get("human_decision")
            human_decisions[hd] = human_decisions.get(hd, 0) + 1

        # 最常见的人类决策
        most_common_hd = max(human_decisions, key=human_decisions.get)
        percentage = human_decisions[most_common_hd] / len(events) * 100

        # 生成模式描述
        system_decision = events[0].get("system_decision", "UNKNOWN")
        pattern_description = f"When system decides '{system_decision}', human overrides to '{most_common_hd}' in {percentage:.0f}% of cases"

        pattern = CorrectionPattern(
            pattern_id=f"PATTERN-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            pattern_description=pattern_description,
            historical_outcome=f"{percentage:.0f}% escalated to {most_common_hd}",
            confidence=min(0.5 + len(events) * 0.1, 0.99),
            related_override_events=[e.get("defect_id") for e in events]
        )

        return pattern

    def _save_correction_pattern(self, pattern: "CorrectionPattern"):
        """保存纠正模式到知识库"""
        import os
        import json

        patterns_dir = os.path.join(self.knowledge_store_path, "correction_patterns")
        os.makedirs(patterns_dir, exist_ok=True)

        filename = f"{pattern.pattern_id}.json"
        filepath = os.path.join(patterns_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(pattern.to_dict(), f, indent=2, ensure_ascii=False)

    def get_recent_patterns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的纠正模式

        Args:
            limit: 返回数量限制

        Returns:
            纠正模式列表
        """
        import os
        import json
        import glob

        patterns_dir = os.path.join(self.knowledge_store_path, "correction_patterns")
        if not os.path.exists(patterns_dir):
            return []

        patterns = []
        for filepath in sorted(
            glob.glob(os.path.join(patterns_dir, "*.json")),
            key=os.path.getmtime,
            reverse=True
        )[:limit]:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    patterns.append(json.load(f))
            except Exception:
                continue

        return patterns