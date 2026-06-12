"""
Fact Agent - 缺陷事实提取 Agent

职责：
- 从 JIRA 提取缺陷的客观事实
- 重建时间线
- 计算 TCI/PFI 指标
- 检测时间线异常
- 检索相似历史案例

输出：DefectFact JSON

设计原则：Fact Before Interpretation
- 只提取事实，不做解释
- 不执行风险评级、合规判断、建议生成
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

from .base import BaseAgent


class FactAgent(BaseAgent):
    """
    Fact Agent - 事实提取 Agent

    从 JIRA 提取缺陷的客观事实，为后续 Agent 提供数据基础。
    """

    name = "FactAgent"
    version = "1.0.0"

    # 严重程度对应的预期关闭天数
    SEVERITY_EXPECTED_DAYS = {
        "Blocker": 7,
        "Critical": 14,
        "Major": 30,
        "Minor": 60,
        "Low": 90
    }

    async def execute(self, defect_id: str) -> Dict[str, Any]:
        """
        执行事实提取

        调用多个 MCP 工具获取完整的缺陷事实数据。

        Args:
            defect_id: JIRA Issue Key (如 "OBMC-24951")

        Returns:
            包含所有客观事实的字典 (DefectFact)
        """
        try:
            # 1. 调用 extract_defect_facts
            fact_data = await self._call_mcp_tool(
                "extract_defect_facts",
                defect_id=defect_id
            )

            # 2. 并行获取补充数据
            timeline_task = self._call_mcp_tool(
                "reconstruct_timeline",
                defect_id=defect_id
            )
            tci_task = self._call_mcp_tool(
                "calculate_tci",
                defect_id=defect_id
            )
            pfi_task = self._call_mcp_tool(
                "calculate_pfi",
                defect_id=defect_id
            )
            anomalies_task = self._call_mcp_tool(
                "detect_timeline_anomalies",
                defect_id=defect_id
            )

            # 并行执行
            timeline, tci_result, pfi_result, anomalies = await asyncio.gather(
                timeline_task,
                tci_task,
                pfi_task,
                anomalies_task,
                return_exceptions=True
            )

            # 处理异常结果
            if isinstance(timeline, Exception):
                timeline = {"error": str(timeline)}
            if isinstance(tci_result, Exception):
                tci_result = {"tci": 0.0, "error": str(tci_result)}
            if isinstance(pfi_result, Exception):
                pfi_result = {"pfi": 0.0, "error": str(pfi_result)}
            if isinstance(anomalies, Exception):
                anomalies = {"anomalies": [], "error": str(anomalies)}

            # 3. 提取相似案例（基于技术域和组件）
            similar_cases = await self._retrieve_similar_cases(fact_data)

            # 4. 构建完整 DefectFact
            defect_fact = self._build_defect_fact(
                fact_data=fact_data,
                timeline=timeline,
                tci_result=tci_result,
                pfi_result=pfi_result,
                anomalies=anomalies,
                similar_cases=similar_cases
            )

            # 5. 计算综合置信度
            confidence = self._calculate_overall_confidence(defect_fact)
            defect_fact["confidence"] = confidence
            defect_fact["confidence_level"] = self._get_confidence_level(confidence)

            return self._build_response(
                status="success",
                data=defect_fact,
                metadata={
                    "defect_id": defect_id,
                    "tools_used": [
                        "extract_defect_facts",
                        "reconstruct_timeline",
                        "calculate_tci",
                        "calculate_pfi",
                        "detect_timeline_anomalies"
                    ],
                    "pipeline_fingerprint": self._generate_fingerprint()
                }
            )

        except Exception as e:
            return self._build_error_response(
                error_message=f"Fact extraction failed: {str(e)}",
                error_code="FACT_EXTRACTION_ERROR",
                details={"defect_id": defect_id}
            )

    async def _retrieve_similar_cases(
        self,
        fact_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        检索相似历史案例

        Args:
            fact_data: 缺陷事实数据

        Returns:
            相似案例列表
        """
        # 从 fact_data 中提取检索条件
        technical_domain = fact_data.get("root_cause")
        affected_components = fact_data.get("components", [])
        platform = fact_data.get("platform")

        # 如果有足够的检索条件，调用知识库
        if technical_domain or affected_components or platform:
            result = await self._call_mcp_tool(
                "retrieve_similar_cases",
                technical_domain=technical_domain,
                affected_components=affected_components,
                platform_family=platform,
                similarity_threshold=0.7
            )
            return result.get("cases", [])

        return []

    def _build_defect_fact(
        self,
        fact_data: Dict[str, Any],
        timeline: Dict[str, Any],
        tci_result: Dict[str, Any],
        pfi_result: Dict[str, Any],
        anomalies: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        构建完整的 DefectFact

        Args:
            fact_data: 缺陷事实数据
            timeline: 时间线数据
            tci_result: TCI 计算结果
            pfi_result: PFI 计算结果
            anomalies: 异常检测结果
            similar_cases: 相似案例列表

        Returns:
            完整的 DefectFact 字典
        """
        # 合并时间线数据
        if "timeline" not in fact_data and isinstance(timeline, dict):
            fact_data["timeline"] = timeline

        # 添加 TCI/PFI
        fact_data["tci"] = tci_result.get("tci", 0.0)
        fact_data["tci_details"] = {
            "actual_days": tci_result.get("actual_days"),
            "expected_days": tci_result.get("expected_days"),
            "method": tci_result.get("method", "standard")
        }

        fact_data["pfi"] = pfi_result.get("pfi", 0.0)
        fact_data["pfi_details"] = pfi_result.get("factors", {})

        # 添加异常检测结果
        fact_data["anomalies"] = anomalies.get("anomalies", [])
        fact_data["anomaly_count"] = anomalies.get("anomaly_count", 0)
        fact_data["has_critical_anomaly"] = anomalies.get("has_critical_anomaly", False)

        # 添加相似案例
        fact_data["similar_cases"] = similar_cases
        fact_data["similar_case_count"] = len(similar_cases)

        # 添加检索时间戳
        fact_data["retrieved_at"] = datetime.now().isoformat()

        return fact_data

    def _calculate_overall_confidence(self, fact_data: Dict[str, Any]) -> float:
        """
        计算综合置信度

        基于以下因素：
        - 数据完整性（基础字段）
        - 证据完整性
        - 时间线完整性
        - 相似案例数量

        Args:
            fact_data: 缺陷事实数据

        Returns:
            综合置信度 (0.0 - 1.0)
        """
        score = 0.0
        max_score = 10.0

        # 1. 基本数据完整性 (0-3 分)
        if fact_data.get("summary"):
            score += 0.5
        if fact_data.get("severity"):
            score += 0.5
        if fact_data.get("priority"):
            score += 0.5
        if fact_data.get("created"):
            score += 0.5
        if fact_data.get("assignee"):
            score += 0.5
        if fact_data.get("reporter"):
            score += 0.5

        # 2. 证据完整性 (0-3 分)
        evidence = fact_data.get("evidence", {})
        evidence_types = [
            "customer_impact",
            "workaround_exists",
            "no_regression",
            "root_cause_analysis",
            "reproduction_steps",
            "test_coverage"
        ]
        evidence_count = sum(
            1 for e in evidence_types
            if evidence.get(e) is not None
        )
        score += (evidence_count / len(evidence_types)) * 3.0

        # 3. 时间线完整性 (0-2 分)
        timeline = fact_data.get("timeline", {})
        status_changes = timeline.get("status_changes", [])
        if len(status_changes) >= 3:
            score += 2.0
        elif len(status_changes) >= 1:
            score += 1.0

        # 4. 指标完整性 (0-2 分)
        if fact_data.get("tci", 0) > 0:
            score += 1.0
        if fact_data.get("pfi", 0) > 0:
            score += 1.0

        return min(score / max_score, 1.0)

    def _get_confidence_level(self, confidence: float) -> str:
        """
        根据置信度值获取置信度等级

        Args:
            confidence: 置信度值 (0.0 - 1.0)

        Returns:
            置信度等级字符串
        """
        if confidence >= 0.90:
            return "high"
        elif confidence >= 0.75:
            return "medium"
        else:
            return "low"

    def get_expected_days(self, severity: str) -> int:
        """
        根据严重程度获取预期关闭天数

        Args:
            severity: 严重程度

        Returns:
            预期天数
        """
        return self.SEVERITY_EXPECTED_DAYS.get(severity, 30)

    async def batch_execute(
        self,
        defect_ids: List[str],
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        批量执行事实提取

        Args:
            defect_ids: 缺陷 ID 列表
            max_concurrent: 最大并发数

        Returns:
            批量执行结果列表
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_with_semaphore(defect_id: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.execute(defect_id)

        # 并发执行
        tasks = [extract_with_semaphore(did) for did in defect_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "defect_id": defect_ids[i],
                    "status": "error",
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        return processed_results