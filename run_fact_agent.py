"""
运行 Fact Agent 提取 OBMC-9062 的数据

Usage: python run_fact_agent.py [defect_id]
"""

import asyncio
import sys
import os
import io
from unittest.mock import AsyncMock, MagicMock

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def create_mock_mcp_client():
    """创建 Mock MCP 客户端，返回与 OBMC-9062 相关的模拟数据"""
    client = MagicMock()

    async def mock_call_tool(tool_name: str, **kwargs):
        defect_id = kwargs.get("defect_id", "OBMC-9062")

        if tool_name == "extract_defect_facts":
            return {
                "defect_id": defect_id,
                "key": defect_id,
                "summary": "KVM connection failure during remote management session",
                "severity": "Critical",
                "priority": "High",
                "status": "Working",
                "created": "2025-03-15T10:30:00Z",
                "updated": "2025-06-01T14:22:00Z",
                "assignee": "zhangsan@lenovo.com",
                "reporter": "lisi@lenovo.com",
                "platform": "ThinkSystem SR650",
                "components": ["BMC", "KVM", "Network"],
                "root_cause": "Network configuration issue",
                "active_weeks": 11.5,
                "evidence": {
                    "customer_impact": {
                        "source": "customer_report",
                        "verified": True,
                        "impact_level": "high",
                        "comment_id": "CMT-12345"
                    },
                    "workaround_exists": {
                        "source": "internal",
                        "verified": True,
                        "description": "Use local console as workaround",
                        "comment_id": "CMT-12346"
                    },
                    "no_regression": None,
                    "root_cause_analysis": {
                        "source": "internal",
                        "verified": True,
                        "description": "Root cause identified as network timeout configuration",
                        "comment_id": "CMT-12347"
                    },
                    "reproduction_steps": None,
                    "test_coverage": None
                }
            }

        elif tool_name == "reconstruct_timeline":
            return {
                "defect_id": defect_id,
                "created": "2025-03-15T10:30:00Z",
                "status_changes": [
                    {"from_status": "New", "to_status": "Assigned", "changed_at": "2025-03-15T11:00:00Z", "changed_by": "system"},
                    {"from_status": "Assigned", "to_status": "Working", "changed_at": "2025-03-16T09:00:00Z", "changed_by": "zhangsan@lenovo.com"},
                    {"from_status": "Working", "to_status": "Review", "changed_at": "2025-04-20T16:00:00Z", "changed_by": "zhangsan@lenovo.com"},
                    {"from_status": "Review", "to_status": "Working", "changed_at": "2025-05-10T10:00:00Z", "changed_by": "wangwu@lenovo.com"}
                ],
                "resolved": None,
                "closed": None
            }

        elif tool_name == "calculate_tci":
            return {
                "defect_id": defect_id,
                "tci": 0.42,
                "actual_days": 80,
                "expected_days": 14,
                "method": "standard",
                "factors": {
                    "severity_weight": 0.3,
                    "duration_weight": 0.4,
                    "complexity_weight": 0.3
                }
            }

        elif tool_name == "calculate_pfi":
            return {
                "defect_id": defect_id,
                "pfi": 0.68,
                "factors": {
                    "customer_impact_score": 0.8,
                    "business_impact_score": 0.6,
                    "technical_complexity": 0.7
                }
            }

        elif tool_name == "detect_timeline_anomalies":
            return {
                "defect_id": defect_id,
                "anomalies": [
                    {
                        "type": "long_resolution_time",
                        "severity": "warning",
                        "description": "Resolution time (80 days) significantly exceeds expected (14 days) for Critical severity"
                    },
                    {
                        "type": "status_fluctuation",
                        "severity": "info",
                        "description": "Status changed from Review back to Working"
                    }
                ],
                "anomaly_count": 2,
                "has_critical_anomaly": False
            }

        elif tool_name == "retrieve_similar_cases":
            return {
                "cases": [
                    {
                        "defect_id": "OBMC-24001",
                        "similarity_score": 0.85,
                        "summary": "Similar KVM connection issue",
                        "resolution_days": 12,
                        "limitation_used": False
                    },
                    {
                        "defect_id": "OBMC-23850",
                        "similarity_score": 0.72,
                        "summary": "BMC network timeout problem",
                        "resolution_days": 18,
                        "limitation_used": True
                    }
                ]
            }

        return {}

    client.call_tool = mock_call_tool
    return client


async def main():
    from agents.fact_agent import FactAgent

    # 获取缺陷 ID（默认 OBMC-9062）
    defect_id = sys.argv[1] if len(sys.argv) > 1 else "OBMC-9062"

    print(f"\n{'='*60}")
    print(f"Fact Agent - Defect Data Extraction")
    print(f"Defect ID: {defect_id}")
    print(f"{'='*60}\n")

    # 创建 Mock MCP 客户端
    mock_client = create_mock_mcp_client()

    # 创建 FactAgent 并执行
    fact_agent = FactAgent(mock_client)
    result = await fact_agent.execute(defect_id)

    # 输出结果
    if result["status"] == "success":
        data = result["data"]
        print("\n[SUCCESS] Extract completed!\n")
        print("Defect Summary:")
        print(f"   Defect ID: {data['defect_id']}")
        print(f"   Summary: {data['summary']}")
        print(f"   Severity: {data['severity']}")
        print(f"   Priority: {data['priority']}")
        print(f"   Status: {data['status']}")
        print(f"   Active Weeks: {data['active_weeks']:.1f} weeks")

        print(f"\nMetrics:")
        print(f"   TCI (Time-to-Close Index): {data['tci']:.2f}")
        print(f"   PFI (Priority-Factor Index): {data['pfi']:.2f}")
        print(f"   Overall Confidence: {data['confidence']:.2f} ({data['confidence_level']})")

        print(f"\nAnomaly Detection:")
        print(f"   Anomaly Count: {data['anomaly_count']}")
        if data['anomalies']:
            for anomaly in data['anomalies']:
                print(f"   - [{anomaly['severity'].upper()}] {anomaly['description']}")

        print(f"\nEvidence:")
        evidence = data.get('evidence', {})
        for key, value in evidence.items():
            status = "[PROVIDED]" if value else "[MISSING]"
            print(f"   {key}: {status}")

        print(f"\nSimilar Cases:")
        similar_cases = data.get('similar_cases', [])
        print(f"   Found {len(similar_cases)} similar cases")
        for case in similar_cases:
            print(f"   - {case['defect_id']} (similarity: {case['similarity_score']:.0%}, resolution days: {case['resolution_days']})")

        print(f"\nTimeline:")
        timeline = data.get('timeline', {})
        print(f"   Created: {timeline.get('created', 'N/A')}")
        print(f"   Status Change Count: {len(timeline.get('status_changes', []))}")

        print(f"\n{'='*60}")
        print(f"Tools Used: {', '.join(result['metadata']['tools_used'])}")
        print(f"Pipeline Fingerprint: {result['metadata']['pipeline_fingerprint']}")
        print(f"{'='*60}\n")

    else:
        print(f"\n[ERROR] Extract failed: {result.get('error', 'Unknown error')}")

    return result


if __name__ == "__main__":
    asyncio.run(main())