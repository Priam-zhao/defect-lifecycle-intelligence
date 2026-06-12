"""
BaseAgent 单元测试

测试 Agent 基类的通用能力
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    """Concrete 实现用于测试"""

    async def execute(self, input_data):
        return self._build_response(
            status="success",
            data={"result": "test"},
            metadata={"input": input_data}
        )


@pytest.fixture
def agent(mock_mcp_client):
    """创建测试 Agent 实例"""
    return ConcreteAgent(mock_mcp_client)


class TestBaseAgent:
    """BaseAgent 测试类"""

    def test_init(self, agent):
        """测试初始化"""
        assert agent.name == "ConcreteAgent"
        assert agent.version == "1.0.0"
        assert agent.mcp_client is not None

    def test_validate_input_success(self, agent):
        """测试输入验证成功"""
        input_data = {"field1": "value1", "field2": "value2"}
        required_fields = ["field1", "field2"]
        is_valid, error = agent._validate_input(input_data, required_fields)
        assert is_valid is True
        assert error is None

    def test_validate_input_missing_field(self, agent):
        """测试输入验证缺失字段"""
        input_data = {"field1": "value1"}
        required_fields = ["field1", "field2"]
        is_valid, error = agent._validate_input(input_data, required_fields)
        assert is_valid is False
        assert "field2" in error

    def test_validate_input_none_value(self, agent):
        """测试输入验证 None 值"""
        input_data = {"field1": "value1", "field2": None}
        required_fields = ["field1", "field2"]
        is_valid, error = agent._validate_input(input_data, required_fields)
        assert is_valid is False
        assert "None" in error

    def test_build_response(self, agent):
        """测试响应构建"""
        response = agent._build_response(
            status="success",
            data={"key": "value"},
            metadata={"version": "1.0"}
        )

        assert response["status"] == "success"
        assert response["data"] == {"key": "value"}
        assert response["metadata"] == {"version": "1.0"}
        assert response["agent_name"] == "ConcreteAgent"
        assert "timestamp" in response

    def test_build_error_response(self, agent):
        """测试错误响应构建"""
        response = agent._build_error_response(
            error_message="Test error",
            error_code="TEST_ERROR",
            details={"field": "value"}
        )

        assert response["status"] == "error"
        assert response["error"]["message"] == "Test error"
        assert response["error"]["code"] == "TEST_ERROR"
        assert response["error"]["details"] == {"field": "value"}
        assert "timestamp" in response["error"]

    def test_generate_fingerprint(self, agent):
        """测试指纹生成"""
        fp1 = agent._generate_fingerprint()
        fp2 = agent._generate_fingerprint()

        # 指纹应该是 16 字符的十六进制字符串
        assert len(fp1) == 16
        assert len(fp2) == 16
        # 由于时间戳不同，两次生成应该不同
        assert fp1 != fp2

    def test_repr(self, agent):
        """测试 __repr__ 方法"""
        repr_str = repr(agent)
        assert "ConcreteAgent" in repr_str
        assert "1.0.0" in repr_str

    @pytest.mark.asyncio
    async def test_execute(self, agent):
        """测试 execute 方法"""
        result = await agent.execute({"test": "data"})
        assert result["status"] == "success"
        assert result["data"]["result"] == "test"

    @pytest.mark.asyncio
    async def test_call_mcp_tool_success(self, agent):
        """测试 MCP 工具调用成功"""
        agent.mcp_client.call_tool = AsyncMock(return_value={"result": "ok"})

        result = await agent._call_mcp_tool(
            "test_tool",
            defect_id="TEST-001"
        )

        assert result["result"] == "ok"
        agent.mcp_client.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_mcp_tool_timeout(self, agent):
        """测试 MCP 工具调用超时"""
        async def slow_call(*args):
            await asyncio.sleep(1)
            return {"result": "ok"}

        agent.mcp_client.call_tool = slow_call

        result = await agent._call_mcp_tool(
            "slow_tool",
            timeout=0.1
        )

        assert result["status"] == "timeout"
        assert "timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_call_mcp_tool_exception(self, agent):
        """测试 MCP 工具调用异常"""
        async def failing_call(*args):
            raise Exception("Tool error")

        agent.mcp_client.call_tool = failing_call

        result = await agent._call_mcp_tool("failing_tool")

        assert result["status"] == "error"
        assert "Tool error" in result["error"]

    @pytest.mark.asyncio
    async def test_call_mcp_tool_no_client(self):
        """测试 MCP 客户端不可用时返回 Mock 数据"""
        agent = ConcreteAgent(None)

        result = await agent._call_mcp_tool(
            "extract_defect_facts",
            defect_id="TEST-001"
        )

        assert result["defect_id"] == "TEST-001"
        assert result["_mock"] is True

    def test_get_mock_tool_result(self, agent):
        """测试 Mock 工具结果"""
        result = agent._get_mock_tool_result(
            "extract_defect_facts",
            {"defect_id": "MOCK-001"}
        )

        assert result["defect_id"] == "MOCK-001"
        assert result["_mock"] is True

    def test_get_mock_tool_result_unknown_tool(self, agent):
        """测试未知工具的 Mock 结果"""
        result = agent._get_mock_tool_result(
            "unknown_tool",
            {}
        )

        assert result["_mock"] is True
        assert result["tool"] == "unknown_tool"