"""
Test script for Agent Orchestrator with real JIRA data

Tests the complete pipeline: Fact Agent -> Review Agent -> Advisor Agent
"""
import asyncio
import sys
import os

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Set working directory
os.chdir(current_dir)

# 导入 Agent 编排器
from agents.orchestrator import AgentOrchestrator


async def test_orchestrator(defect_id: str):
    """测试 Orchestrator"""
    print(f"\n{'='*60}")
    print(f"Testing Agent Orchestrator with: {defect_id}")
    print(f"{'='*60}\n")

    # 初始化 Orchestrator（不提供 MCP client，使用直接工具调用）
    orchestrator = AgentOrchestrator(mcp_client=None)

    # 运行完整分析
    result = await orchestrator.analyze_defect(defect_id)

    return result


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Agent Orchestrator Test")
    parser.add_argument("defect_id", nargs="?", default="UEFIRM-70862", help="JIRA Issue Key")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    result = await test_orchestrator(args.defect_id)

    print(f"\n{'='*60}")
    print(f"Test complete - Status: {result.get('status')}")
    print(f"{'='*60}")

    if args.json:
        import json
        output_file = f"test_result_{args.defect_id.replace('-', '_')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        print(f"Result saved to: {output_file}")
    else:
        # Display summary
        print(f"""
Defect ID: {result.get('defect_id')}
Status: {result.get('status')}
Pipeline: {result.get('pipeline_fingerprint')}
Duration: {result.get('duration_ms', 'N/A')}ms

Fact Status: {result.get('fact_status', 'N/A')}
Review Status: {result.get('review_status', 'N/A')}
Advisor Status: {result.get('advisor_status', 'N/A')}
        """)

        # Show fact data if available
        fact = result.get("fact", {})
        if fact:
            print(f"Fact Summary: {fact.get('summary', 'N/A')[:80]}")
            print(f"Fact Severity: {fact.get('severity', 'N/A')}")
            print(f"Fact Is Mock: {fact.get('_mock', 'N/A')}")
            print(f"Fact TCI: {fact.get('tci', 'N/A')}")

        # Show review data if available
        review = result.get("review", {})
        if review:
            print(f"Review Decision: {review.get('decision', {}).get('decision_type', 'N/A')}")

        # Show advisor data if available
        advisor = result.get("advisor", {})
        if advisor:
            print(f"Advisor: Generated recommendations")

    return result


if __name__ == "__main__":
    asyncio.run(main())