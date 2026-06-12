"""
Knowledge Tool - 知识库操作工具

提供知识存储和检索能力，包括：
- 规范缺陷存储
- 相似案例检索
- 覆盖事件记录
- 纠正模式生成
"""

import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from .constants import (
    KNOWLEDGE_STORE_PATH, SIMILARITY_STRONG, SIMILARITY_RELATED,
    SIMILARITY_REFERENCE, load_env
)
from .schemas import (
    OverrideEvent, CorrectionPattern, CaseRetrievalResult
)

load_env()


class KnowledgeTool:
    """
    知识库操作工具

    提供以下能力：
    - store_canonical_defect: 存储规范缺陷
    - retrieve_similar_cases: 检索相似案例
    - record_override_event: 记录覆盖事件
    - generate_correction_pattern: 生成纠正模式
    """

    def __init__(self):
        self.store_path = KNOWLEDGE_STORE_PATH
        self._ensure_store_exists()

    def _ensure_store_exists(self):
        """确保知识库目录存在"""
        if not os.path.exists(self.store_path):
            os.makedirs(self.store_path, exist_ok=True)

    # ========== 规范缺陷存储 ==========

    def store_canonical_defect(self, defect_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        存储规范缺陷数据

        Args:
            defect_data: 包含以下字段的字典：
                - defect_id: 缺陷 ID
                - technical_domain: 技术域
                - affected_components: 受影响组件列表
                - failure_signature: 失败签名
                - root_cause_category: 根因类别
                - resolution_days: 解决天数
                - tci_range: TCI 范围
                - patterns: 已知模式

        Returns:
            存储结果
        """
        defect_id = defect_data.get("defect_id", "unknown")
        canonical_id = f"canonical_{defect_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        canonical_defect = {
            "canonical_id": canonical_id,
            "defect_id": defect_id,
            "technical_domain": defect_data.get("technical_domain", ""),
            "affected_components": defect_data.get("affected_components", []),
            "failure_signature": defect_data.get("failure_signature", ""),
            "root_cause_category": defect_data.get("root_cause_category", ""),
            "platform_family": defect_data.get("platform_family", ""),
            "resolution_days": defect_data.get("resolution_days", 0),
            "tci_range": defect_data.get("tci_range", (0, 1)),
            "known_patterns": defect_data.get("known_patterns", []),
            "stored_at": datetime.now().isoformat()
        }

        # 保存到文件
        filepath = os.path.join(self.store_path, f"{canonical_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(canonical_defect, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "canonical_id": canonical_id,
            "filepath": filepath
        }

    def retrieve_similar_cases(
        self,
        technical_domain: Optional[str] = None,
        affected_components: Optional[List[str]] = None,
        failure_signature: Optional[str] = None,
        root_cause_category: Optional[str] = None,
        platform_family: Optional[str] = None,
        similarity_threshold: float = SIMILARITY_RELATED
    ) -> CaseRetrievalResult:
        """
        检索相似案例

        Args:
            technical_domain: 技术域
            affected_components: 受影响组件列表
            failure_signature: 失败签名
            root_cause_category: 根因类别
            platform_family: 平台系列
            similarity_threshold: 相似度阈值

        Returns:
            CaseRetrievalResult 对象
        """
        query_criteria = {
            "technical_domain": technical_domain,
            "affected_components": affected_components,
            "failure_signature": failure_signature,
            "root_cause_category": root_cause_category,
            "platform_family": platform_family,
            "similarity_threshold": similarity_threshold
        }

        # 读取所有规范缺陷
        canonical_files = self._list_canonical_files()
        cases = []

        for filepath in canonical_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    canonical = json.load(f)

                # 计算相似度
                similarity = self._calculate_similarity(canonical, query_criteria)

                if similarity >= similarity_threshold:
                    case = {
                        "canonical_id": canonical.get("canonical_id"),
                        "defect_id": canonical.get("defect_id"),
                        "technical_domain": canonical.get("technical_domain"),
                        "affected_components": canonical.get("affected_components"),
                        "root_cause_category": canonical.get("root_cause_category"),
                        "platform_family": canonical.get("platform_family"),
                        "resolution_days": canonical.get("resolution_days"),
                        "similarity_score": round(similarity, 3),
                        "stored_at": canonical.get("stored_at")
                    }
                    cases.append(case)

            except Exception:
                continue

        # 按相似度排序
        cases.sort(key=lambda x: x["similarity_score"], reverse=True)

        return CaseRetrievalResult(
            query_criteria=query_criteria,
            total_matches=len(cases),
            cases=cases[:20]  # 限制返回数量
        )

    def _calculate_similarity(
        self,
        canonical: Dict[str, Any],
        criteria: Dict[str, Any]
    ) -> float:
        """
        计算相似度分数

        相似度计算逻辑：
        1. 技术域匹配: +0.3
        2. 组件匹配: +0.3 * (匹配组件数 / 总查询组件数)
        3. 根因匹配: +0.2
        4. 平台匹配: +0.2
        """
        score = 0.0

        # 技术域匹配
        if criteria.get("technical_domain") and canonical.get("technical_domain"):
            if criteria["technical_domain"].lower() == canonical["technical_domain"].lower():
                score += 0.3

        # 组件匹配
        query_components = criteria.get("affected_components") or []
        canonical_components = canonical.get("affected_components") or []
        if query_components and canonical_components:
            matches = sum(
                1 for c in query_components
                if c in canonical_components
            )
            component_score = (matches / len(query_components)) * 0.3
            score += component_score

        # 根因匹配
        if criteria.get("root_cause_category") and canonical.get("root_cause_category"):
            if criteria["root_cause_category"].lower() == canonical["root_cause_category"].lower():
                score += 0.2

        # 平台匹配
        if criteria.get("platform_family") and canonical.get("platform_family"):
            if criteria["platform_family"].lower() == canonical["platform_family"].lower():
                score += 0.2

        return min(score, 1.0)

    def _list_canonical_files(self) -> List[str]:
        """列出知识库中的所有规范缺陷文件"""
        files = []
        if os.path.exists(self.store_path):
            for filename in os.listdir(self.store_path):
                if filename.startswith("canonical_") and filename.endswith(".json"):
                    files.append(os.path.join(self.store_path, filename))
        return files

    # ========== 覆盖事件记录 ==========

    def record_override_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        记录覆盖事件

        Args:
            event_data: 包含以下字段的字典：
                - defect_id: 缺陷 ID
                - system_decision: 系统决策
                - human_decision: 人类决策
                - reason: 原因
                - reviewer: 审查者

        Returns:
            记录结果
        """
        event = OverrideEvent(
            defect_id=event_data["defect_id"],
            system_decision=event_data["system_decision"],
            human_decision=event_data["human_decision"],
            reason=event_data.get("reason", ""),
            reviewer=event_data.get("reviewer", "unknown"),
            timestamp=datetime.now()
        )

        # 保存到覆盖事件日志
        events_file = os.path.join(self.store_path, "override_events.jsonl")
        with open(events_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + '\n')

        return {
            "success": True,
            "event_id": f"override_{event.timestamp.strftime('%Y%m%d%H%M%S')}",
            "recorded_at": event.timestamp.isoformat()
        }

    def get_override_events(
        self,
        defect_id: Optional[str] = None,
        reviewer: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取覆盖事件记录

        Args:
            defect_id: 缺陷 ID 过滤
            reviewer: 审查者过滤
            limit: 返回数量限制

        Returns:
            覆盖事件列表
        """
        events_file = os.path.join(self.store_path, "override_events.jsonl")
        events = []

        if os.path.exists(events_file):
            with open(events_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        if defect_id and event.get("defect_id") != defect_id:
                            continue
                        if reviewer and event.get("reviewer") != reviewer:
                            continue
                        events.append(event)
                    except Exception:
                        continue

        return events[-limit:]

    # ========== 纠正模式生成 ==========

    def generate_correction_pattern(
        self,
        pattern_description: str,
        related_events: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        生成纠正模式

        基于多个覆盖事件生成纠正模式

        Args:
            pattern_description: 模式描述
            related_events: 相关覆盖事件 ID 列表

        Returns:
            纠正模式
        """
        pattern_id = f"pattern_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 分析相关事件的统计信息
        events = []
        if related_events:
            for event_id in related_events:
                events_file = os.path.join(self.store_path, "override_events.jsonl")
                if os.path.exists(events_file):
                    with open(events_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                event = json.loads(line.strip())
                                if f"override_{event.get('timestamp', '')}" == event_id:
                                    events.append(event)
                            except Exception:
                                continue

        # 计算历史结果统计
        total = len(events)
        if total > 0:
            human_decisions = [e.get("human_decision") for e in events]
            most_common = max(set(human_decisions), key=human_decisions.count) if human_decisions else "unknown"
            historical_outcome = f"{round(total / max(1, total) * 100, 0)}% escalated to {most_common}"
        else:
            historical_outcome = "Insufficient data"
            total = 1

        pattern = CorrectionPattern(
            pattern_id=pattern_id,
            pattern_description=pattern_description,
            historical_outcome=historical_outcome,
            confidence=min(0.9, 0.5 + (total * 0.1)),  # 基于事件数量的置信度
            related_override_events=related_events or [],
            created_at=datetime.now()
        )

        # 保存到纠正模式文件
        patterns_file = os.path.join(self.store_path, "correction_patterns.jsonl")
        with open(patterns_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(pattern.to_dict(), ensure_ascii=False) + '\n')

        return {
            "success": True,
            "pattern": pattern.to_dict()
        }

    def get_correction_patterns(
        self,
        pattern_id: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        获取纠正模式

        Args:
            pattern_id: 模式 ID 过滤
            min_confidence: 最低置信度

        Returns:
            纠正模式列表
        """
        patterns_file = os.path.join(self.store_path, "correction_patterns.jsonl")
        patterns = []

        if os.path.exists(patterns_file):
            with open(patterns_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        pattern = json.loads(line.strip())
                        if pattern_id and pattern.get("pattern_id") != pattern_id:
                            continue
                        if pattern.get("confidence", 0) < min_confidence:
                            continue
                        patterns.append(pattern)
                    except Exception:
                        continue

        return patterns

    # ========== 统计信息 ==========

    def get_knowledge_stats(self) -> Dict[str, Any]:
        """
        获取知识库统计信息
        """
        canonical_files = self._list_canonical_files()
        events_file = os.path.join(self.store_path, "override_events.jsonl")
        patterns_file = os.path.join(self.store_path, "correction_patterns.jsonl")

        # 统计事件数量
        event_count = 0
        if os.path.exists(events_file):
            with open(events_file, 'r', encoding='utf-8') as f:
                event_count = sum(1 for _ in f)

        # 统计模式数量
        pattern_count = 0
        if os.path.exists(patterns_file):
            with open(patterns_file, 'r', encoding='utf-8') as f:
                pattern_count = sum(1 for _ in f)

        return {
            "canonical_defects": len(canonical_files),
            "override_events": event_count,
            "correction_patterns": pattern_count,
            "store_path": self.store_path,
            "stats_generated_at": datetime.now().isoformat()
        }