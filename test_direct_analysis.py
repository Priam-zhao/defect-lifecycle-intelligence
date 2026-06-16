"""
Test script for Defect Lifecycle Intelligence Agent

Directly call MCP tools to verify the complete data retrieval flow
"""
import asyncio
import sys
import os
import json

# Add mcp-server directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
mcp_server_dir = os.path.join(current_dir, "mcp-server")
sys.path.insert(0, mcp_server_dir)

# Set working directory
os.chdir(current_dir)

# Import constants module to load .env
from tools import constants

# Import tools
from tools.defect_fact_tool import DefectFactTool
from tools.timeline_tool import TimelineTool
from tools.tci_pfi_tool import TciPfiTool
from tools.knowledge_tool import KnowledgeTool


class DirectToolClient:
    """
    Client for directly calling tools

    Bypass MCP server, directly call tool classes
    """

    def __init__(self):
        self.defect_fact_tool = DefectFactTool()
        self.timeline_tool = TimelineTool()
        self.tci_pfi_tool = TciPfiTool()
        self.knowledge_tool = KnowledgeTool()

    async def extract_defect_facts(self, defect_id: str) -> dict:
        """Extract defect facts"""
        return self.defect_fact_tool.extract_defect_facts(defect_id)

    async def reconstruct_timeline(self, defect_id: str) -> dict:
        """Reconstruct timeline"""
        return self.timeline_tool.reconstruct_timeline(defect_id)

    async def calculate_tci(self, defect_id: str) -> dict:
        """Calculate TCI"""
        return self.tci_pfi_tool.calculate_tci(defect_id)

    async def calculate_pfi(self, defect_id: str) -> dict:
        """Calculate PFI"""
        return self.tci_pfi_tool.calculate_pfi(defect_id)

    async def detect_timeline_anomalies(self, defect_id: str) -> dict:
        """Detect timeline anomalies"""
        return self.timeline_tool.detect_anomalies(defect_id)

    async def retrieve_similar_cases(self, **kwargs) -> dict:
        """Retrieve similar cases"""
        result = self.knowledge_tool.retrieve_similar_cases(**kwargs)
        return result.to_dict() if hasattr(result, 'to_dict') else result


async def analyze_defect(defect_id: str) -> dict:
    """
    Complete defect analysis flow

    Directly call tools to get real JIRA data
    """
    client = DirectToolClient()

    print(f"\n{'='*60}")
    print(f"Starting analysis for: {defect_id}")
    print(f"{'='*60}\n")

    result = {
        "defect_id": defect_id,
        "status": "in_progress"
    }

    try:
        # Stage 1: Extract defect facts
        print("[Stage 1] Extracting defect facts...")
        fact_data = await client.extract_defect_facts(defect_id)

        if fact_data.get("error"):
            print(f"   [ERROR] {fact_data.get('error')}")
            result["status"] = "error"
            result["error"] = fact_data.get("error")
            return result

        result["fact"] = fact_data
        result["fact_status"] = "success"

        # Display key info
        print(f"   [OK] Summary: {fact_data.get('summary', 'N/A')[:60]}...")
        print(f"   [OK] Severity: {fact_data.get('severity', 'N/A')}")
        print(f"   [OK] Status: {fact_data.get('status', 'N/A')}")
        print(f"   [OK] Is Mock: {fact_data.get('_mock', False)}")

        # Stage 2: Reconstruct timeline
        print(f"\n[Stage 2] Reconstructing timeline...")
        timeline = await client.reconstruct_timeline(defect_id)
        result["timeline"] = timeline
        print(f"   [OK] Created: {timeline.get('created', 'N/A')}")
        print(f"   [OK] Status Changes: {len(timeline.get('status_changes', []))}")

        # Stage 3: Calculate TCI
        print(f"\n[Stage 3] Calculating TCI...")
        tci_result = await client.calculate_tci(defect_id)
        result["tci"] = tci_result
        print(f"   [OK] TCI: {tci_result.get('tci', 'N/A')}")
        print(f"   [OK] Actual Days: {tci_result.get('actual_days', 'N/A')}")
        print(f"   [OK] Expected Days: {tci_result.get('expected_days', 'N/A')}")

        # Stage 4: Calculate PFI
        print(f"\n[Stage 4] Calculating PFI...")
        pfi_result = await client.calculate_pfi(defect_id)
        result["pfi"] = pfi_result
        print(f"   [OK] PFI: {pfi_result.get('pfi', 'N/A')}")

        # Stage 5: Detect anomalies
        print(f"\n[Stage 5] Detecting timeline anomalies...")
        anomalies = await client.detect_timeline_anomalies(defect_id)
        result["anomalies"] = anomalies
        print(f"   [OK] Anomaly Count: {anomalies.get('anomaly_count', 0)}")

        # Stage 6: Retrieve similar cases
        print(f"\n[Stage 6] Retrieving similar cases...")
        similar = await client.retrieve_similar_cases(
            technical_domain=fact_data.get("root_cause"),
            affected_components=fact_data.get("components", []),
            platform_family=fact_data.get("platform")
        )
        result["similar_cases"] = similar
        print(f"   [OK] Found: {similar.get('total_matches', 0)} similar cases")

        result["status"] = "success"

    except Exception as e:
        print(f"\n[ERROR] Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        result["status"] = "error"
        result["error"] = str(e)

    return result


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Defect Lifecycle Intelligence Agent Test")
    parser.add_argument("defect_id", nargs="?", default="UEFIRM-70862", help="JIRA Issue Key")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    result = await analyze_defect(args.defect_id)

    print(f"\n{'='*60}")
    print(f"Analysis complete - Status: {result['status']}")
    print(f"{'='*60}")

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        # Display summary
        if result["status"] == "success":
            fact = result.get("fact", {})
            print(f"""
Defect ID: {result['defect_id']}
Summary: {fact.get('summary', 'N/A')}
Severity: {fact.get('severity', 'N/A')}
Status: {fact.get('status', 'N/A')}
TCI: {result.get('tci', {}).get('tci', 'N/A')}
PFI: {result.get('pfi', {}).get('pfi', 'N/A')}
Anomalies: {result.get('anomalies', {}).get('anomaly_count', 0)}
Data Source: {'Real JIRA' if not fact.get('_mock') else 'Mock'}
            """)

    return result


if __name__ == "__main__":
    asyncio.run(main())