#!/usr/bin/env python3
"""Test tool calling formats across different Ollama models."""

import json
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

@tool
def test_tool(param1: int, param2: str) -> str:
    """Test tool for checking format compatibility.
    
    Args:
        param1: An integer parameter
        param2: A string parameter
    """
    return f"Tool called with param1={param1}, param2={param2}"

def test_model_tool_format(model_name: str):
    """Test tool calling format for a specific model."""
    print(f"\n🔧 Testing {model_name}...")
    
    try:
        # Create LLM with tool binding
        llm = ChatOllama(model=model_name, temperature=0).bind_tools([test_tool])
        
        # Test message
        messages = [
            SystemMessage(content="You are a helpful assistant. Use the test_tool with param1=42 and param2='hello'."),
            HumanMessage(content="Please call the test_tool with param1=42 and param2='hello'.")
        ]
        
        # Get response
        response = llm.invoke(messages)
        
        # Check for tool_calls attribute (modern format)
        tool_calls = getattr(response, 'tool_calls', None)
        
        if tool_calls:
            print(f"✅ {model_name}: Modern tool_calls format detected")
            print(f"   Tool calls found: {len(tool_calls)}")
            if len(tool_calls) > 0:
                call = tool_calls[0]
                print(f"   First call: {call.get('name', 'unknown')} with args {call.get('args', {})}")
                # Check if args are properly structured
                args = call.get('args', {})
                if isinstance(args, dict) and 'param1' in args and 'param2' in args:
                    print(f"   ✅ Args properly structured: param1={args['param1']}, param2={args['param2']}")
                else:
                    print(f"   ⚠️  Args format issue: {args}")
            return True
        else:
            print(f"❌ {model_name}: No tool_calls attribute found")
            print(f"   Response type: {type(response)}")
            print(f"   Available attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
            return False
            
    except Exception as e:
        print(f"❌ {model_name}: Error - {e}")
        return False

def main():
    """Test tool calling across different models."""
    models_to_test = [
        "llama3.2:3b",      # Current working model
        "gpt-oss:20b",      # Known working with modern format
        "llama3.2:1b",      # Smaller llama model
        "qwen2.5:7b",       # Different model family
        "mistral:7b",       # Different model family
    ]
    
    print("🧪 Testing Tool Calling Formats Across Ollama Models")
    print("=" * 60)
    
    results = {}
    for model in models_to_test:
        try:
            # First check if model is available
            test_llm = ChatOllama(model=model)
            simple_response = test_llm.invoke("Hello")
            if simple_response:
                print(f"✓ {model} is accessible")
                results[model] = test_model_tool_format(model)
            else:
                print(f"❌ {model}: No response to simple query")
                results[model] = False
        except Exception as e:
            print(f"❌ {model}: Not available - {e}")
            results[model] = False
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY:")
    print("=" * 60)
    
    working_models = []
    failed_models = []
    
    for model, success in results.items():
        if success:
            working_models.append(model)
            print(f"✅ {model}: Modern tool format supported")
        else:
            failed_models.append(model)
            print(f"❌ {model}: Modern tool format NOT supported")
    
    print(f"\n🎯 CONCLUSION:")
    if len(working_models) == len(results):
        print("🚀 ALL models support the modern tool_calls format!")
        print("   The unified format can be used for all models.")
    elif len(working_models) > 0:
        print(f"⚠️  Mixed support: {len(working_models)}/{len(results)} models work")
        print("   May need model-specific handling")
    else:
        print("❌ No models support the modern format")

if __name__ == "__main__":
    main()