
import os
import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.agents.designer import DesignAgent

def extract_modes(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    modes = {}
    
    # Define regex patterns for start of each mode block
    patterns = {
        "Mission Control": r'if mode == "🛰️ Mission Control":',
        "The Hangar": r'elif mode == "🛠️ The Hangar":',
        "System Architecture": r'elif mode == "🏗️ System Architecture":',
        "Polymarket Scanner": r'elif mode == "🎯 Polymarket Scanner":',
        "Content Library": r'elif mode == "📚 Content Library":',
        "Advisor Chat": r'elif mode == "🧠 Advisor Chat":',
        "Planner": r'elif mode == "📋 Planner":'
    }
    
    # Find start indices
    indices = []
    for mode, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            indices.append((match.start(), mode))
    
    indices.sort()
    
    # Extract blocks
    for i in range(len(indices)):
        start_idx, mode_name = indices[i]
        end_idx = indices[i+1][0] if i < len(indices) - 1 else len(content)
        modes[mode_name] = content[start_idx:end_idx]
        
    return modes

def main():
    print("🎨 Starting Design Audit with DesignAgent...")
    
    ui_path = Path(__file__).parent.parent / "ui_v2.py"
    modes = extract_modes(ui_path)
    
    agent = DesignAgent()
    
    report_lines = [
        "# 🎨 Valhalla V2 Design Audit Report",
        f"\n**Date**: {os.popen('date').read().strip()}",
        "\n---"
    ]
    
    for mode_name, code_block in modes.items():
        print(f"   Analzying {mode_name}...")
        
        # Analyze
        result = agent.analyze_ui(code_block, context=f"Streamlit Dashboard - {mode_name} Mode")
        
        if "error" in result:
            print(f"Error analyzing {mode_name}: {result['error']}")
            continue
            
        analysis = result.get("analysis", {})
        
        # Format report section
        report_lines.append(f"\n## {mode_name}")
        report_lines.append(f"**Summary**: {analysis.get('summary', 'N/A')}\n")
        
        report_lines.append("### Critical Issues")
        issues = analysis.get("issues", [])
        if not issues:
            report_lines.append("No critical issues found.")
        else:
            for issue in issues[:5]:  # Top 5
                icon = "🔴" if issue.get('severity') == 'high' else "🟠" if issue.get('severity') == 'medium' else "🟡"
                report_lines.append(f"- {icon} **[{issue.get('category', 'General')}]**: {issue.get('description')}")
                report_lines.append(f"  - *Fix*: {issue.get('suggestion')}")
                
        report_lines.append("\n### Quick Wins")
        for win in analysis.get("quick_wins", [])[:3]:
            report_lines.append(f"- ✨ {win}")
            
        report_lines.append("\n---")
    
    # Write report
    output_path = Path(__file__).parent.parent / "design_audit.md"
    with open(output_path, "w") as f:
        f.write("\n".join(report_lines))
        
    print(f"\n✅ Audit Complete! Report saved to {output_path}")

if __name__ == "__main__":
    main()
