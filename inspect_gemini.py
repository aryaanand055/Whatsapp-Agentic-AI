"""
Interactive Gemini Inspector for the Workshop.
Demonstrates how the Gemini model responds and what raw JSON tool calls look like.

Run this script:
    python inspect_gemini.py
"""

import asyncio
import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def main():
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("❌ Error: Please set LLM_API_KEY in your .env file first!")
        return

    client = genai.Client(api_key=api_key)
    model = os.getenv("LLM_MODEL", "gemini-2.0-flash")

    print("\n" + "=" * 60)
    print("🤖 WORKSHOP DEMO: INSPECTING GEMINI'S RAW TOOL CALLS")
    print("=" * 60)
    print(f"Using Model: {model}\n")

    # 1. Define a tool in Gemini format
    sample_tools = [
        {
            "type": "function",
            "name": "whatsapp_search_contact",
            "description": "Search for a contact on WhatsApp by name or phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The contact name to look for"}
                },
                "required": ["name"]
            }
        },
        {
            "type": "function",
            "name": "whatsapp_send_message",
            "description": "Send a WhatsApp message to a contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {"type": "string", "description": "The recipient's name"},
                    "messages": {"type": "array", "items": {"type": "string"}, "description": "Lines of text to send"}
                },
                "required": ["contact", "messages"]
            }
        }
    ]

    print("🛠️ Available Tools Given to Gemini:")
    for t in sample_tools:
        print(f"  • {t['name']}: {t['description']}")
    print("-" * 60)

    test_prompts = [
        "Find Mom on WhatsApp",
        "Send a message to Rahul saying 'I will reach in 10 minutes'",
        "What is the capital of France?"  # No tool needed!
    ]

    for user_prompt in test_prompts:
        print(f"\n💬 User Input: \"{user_prompt}\"")
        print("Thinking...")

        interaction = await client.aio.interactions.create(
            model=model,
            input=user_prompt,
            tools=sample_tools,
            system_instruction="You are a helpful WhatsApp assistant. Use tools when needed."
        )

        all_steps = getattr(interaction, "steps", []) or []
        function_calls = [s for s in all_steps if getattr(s, "type", "") == "function_call"]

        if function_calls:
            for call in function_calls:
                print("\n  🎯 [GEMINI DECIDED TO CALL A TOOL!]")
                print(f"     Tool Name : {getattr(call, 'name', '')}")
                print(f"     Call ID   : {getattr(call, 'id', '')}")
                print(f"     Arguments : {json.dumps(getattr(call, 'arguments', {}), indent=8)}")
        else:
            print(f"\n  🗣️ [GEMINI ANSWERED DIRECTLY (NO TOOL)]: {getattr(interaction, 'output_text', '')}")

        print("-" * 60)

    print("\n🎉 Demo Complete! Notice how Gemini outputs structured JSON instead of plain conversation when an action is required.\n")

if __name__ == "__main__":
    asyncio.run(main())
