"""
Agent 基类 - Defect Lifecycle Intelligence Agent

提供所有 Agent 通用能力：
- MCP 工具调用
- 输入验证
- 响应构建
- 错误处理
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """
    Agent 基类

    所有 Agent 必须继承此类并实现 execute 方法。
    设计原则：Fact Before Interpretation - 事实提取优先于推理。
    """

    def __init__(self, mcp_client=None):
        """
        初始化 Agent

        Args:
            mcp_client: MCP 客户端（可选，用于调用 MCP 工具）
        """
        self.mcp_client = mcp_client
        self.name = self.__class__.__name__
        self.version = "1.0.0"
        self._tool_cache = {}

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        执行 Agent 逻辑

        子类必须实现此方法。
        返回标准化响应字典。

        Returns:
            包含 agent_name, status, data, metadata 的字典
        """
        raise NotImplementedError(f"{self.name} must implement execute()")

    async def _call_mcp_tool(
        self,
        tool_name: str,
        timeout: int = 30,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用 MCP 工具

        Args:
            tool_name: 工具名称
            timeout: 超时时间（秒）
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        if self.mcp_client is None:
            # 返回 mock 数据
            return self._get_mock_tool_result(tool_name, kwargs)

        try:
            # 调用 MCP 工具
            result = await asyncio.wait_for(
                self.mcp_client.call_tool(tool_name, kwargs),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return {
                "error": f"Tool {tool_name} timeout after {timeout}s",
                "tool": tool_name,
                "status": "timeout"
            }
        except Exception as e:
            return {
                "error": str(e),
                "tool": tool_name,
                "status": "error"
            }

    def _get_mock_tool_result(self, tool_name: str, kwargs: Dict) -> Dict[str, Any]:
        """
        返回 Mock 工具结果（当 MCP 客户端不可用时）

        Args:
            tool_name: 工具名称
            kwargs: 工具参数

        Returns:
            Mock 数据
        """
        mock_results = {
            "extract_defect_facts": {
                "defect_id": kwargs.get("defect_id", "MOCK-001"),
                "key": kwargs.get("defect_id", "MOCK-001"),
                "summary": "[Mock] Sample defect for testing",
                "severity": "Medium",
                "priority": "Medium",
                "status": "Working",
                "timeline": {
                    "defect_id": kwargs.get("defect_id", "MOCK-001"),
                    "created": datetime.now().isoformat(),
                    "status_changes": [],
                    "resolved": None,
                    "closed": None
                },
                "clone_info": {
                    "defect_id": kwargs.get("defect_id", "MOCK-001"),
                    "is_clone": False,
                    "parent_id": None,
                    "child_ids": [],
                    "clone_chain": [],
                    "clone_depth": 0
                },
                "evidence": {
                    "defect_id": kwargs.get("defect_id", "MOCK-001"),
                    "customer_impact": {"source": "mock", "verified": True},
                    "workaround_exists": None,
                    "no_regression": None,
                    "root_cause_analysis": None,
                    "reproduction_steps": None,
                    "test_coverage": None,
                    "customer_visibility": None
                },
                "confidence": 0.75,
                "retrieved_at": datetime.now().isoformat(),
                "_mock": True
            },
            "reconstruct_timeline": {
                "defect_id": kwargs.get("defect_id", "MOCK-001"),
                "created": datetime.now().isoformat(),
                "status_changes": [],
                "resolved": None,
                "closed": None,
                "_mock": True
            },
            "calculate_tci": {
                "defect_id": kwargs.get("defect_id", "MOCK-001"),
                "tci": 0.65,
                "actual_days": 30,
                "expected_days": 14,
                "_mock": True
            },
            "calculate_pfi": {
                "defect_id": kwargs.get("defect_id", "MOCK-001"),
                "pfi": 0.72,
                "factors": {
                    "root_cause_score": 0.8,
                    "fix_location_score": 0.7,
                    "component_score": 0.65
                },
                "_mock": True
            },
            "detect_timeline_anomalies": {
                "defect_id": kwargs.get("defect_id", "MOCK-001"),
                "anomaly_count": 0,
                "anomalies": [],
                "_mock": True
            },
            "retrieve_similar_cases": {
                "total_matches": 0,
                "cases": [],
                "_mock": True
            }
        }

        return mock_results.get(tool_name, {"_mock": True, "tool": tool_name})

    def _validate_input(
        self,
        input_data: Dict[str, Any],
        required_fields: List[str]
    ) -> tuple[bool, Optional[str]]:
        """
        验证输入数据

        Args:
            input_data: 输入数据字典
            required_fields: 必需字段列表

        Returns:
            (是否有效, 错误消息)
        """
        for field in required_fields:
            if field not in input_data:
                return False, f"Missing required field: {field}"
            if input_data[field] is None:
                return False, f"Field cannot be None: {field}"
        return True, None

    def _build_response(
        self,
        status: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        构建标准化响应

        Args:
            status: 状态 (success, error, partial)
            data: 响应数据
            metadata: 元数据（可选）

        Returns:
            标准化响应字典
        """
        response = {
            "agent_name": self.name,
            "status": status,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

        if metadata:
            response["metadata"] = metadata

        return response

    def _build_error_response(
        self,
        error_message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        构建错误响应

        Args:
            error_message: 错误消息
            error_code: 错误代码（可选）
            details: 错误详情（可选）

        Returns:
            错误响应字典
        """
        error_response = {
            "agent_name": self.name,
            "status": "error",
            "error": {
                "message": error_message,
                "timestamp": datetime.now().isoformat()
            }
        }

        if error_code:
            error_response["error"]["code"] = error_code

        if details:
            error_response["error"]["details"] = details

        return error_response

    def _generate_fingerprint(self) -> str:
        """
        生成 Pipeline 指纹

        用于追踪和审计。

        Returns:
            指纹字符串
        """
        import hashlib
        timestamp = datetime.now().isoformat()
        content = f"{self.name}:{self.version}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(version={self.version})"