#!/usr/bin/env python3
"""Quick test to confirm unified tool calling works for both models."""

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

@tool
def select_team_tool(fish_indices: list, mimic_choice: str = "none") -> str:
    """Select team tool for testing."""
    return f"Selected: {fish_indices}, mimic: {mimic_choice}"

def test_unified_format():
    """Test that both models use the same tool extraction logic."""
    models = ['llama3.2:3b', 'gpt-oss:20b']
    
    for model_name in models:
        print(f"\n🔧 Testing {model_name}...")
        
        try:
            # Create LLM with tools
            llm = ChatOllama(model=model_name, temperature=0).bind_tools([select_team_tool])
            
            # Simple test message
            messages = [
                SystemMessage(content="Use select_team_tool to select fish indices [0, 1, 2, 3]."),
                HumanMessage(content="Please use select_team_tool with fish_indices=[0, 1, 2, 3]")
            ]
            
            print(f"  Invoking {model_name}...")
            response = llm.invoke(messages)
            
            # Check tool_calls attribute (unified format)
            tool_calls = getattr(response, 'tool_calls', None)
            
            if tool_calls and len(tool_calls) > 0:
                call = tool_calls[0]
                name = call.get('name', 'unknown')
                args = call.get('args', {})
                print(f"  ✅ Tool call: {name} with args: {args}")
                
                # Check if this is the format our code expects
                if isinstance(args, dict) and 'fish_indices' in args:
                    print(f"  ✅ {model_name}: Compatible with our unified extraction logic!")
                else:
                    print(f"  ⚠️  {model_name}: Args format might need special handling")
            else:
                print(f"  ❌ {model_name}: No tool_calls found")
                print(f"     Response type: {type(response)}")
                
        except Exception as e:
            print(f"  ❌ {model_name}: Error - {e}")

if __name__ == "__main__":
    test_unified_format()