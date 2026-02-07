"""
Test streaming functionality
Run with: uv run python test_streaming.py
"""
import asyncio
from app.services.llm import llm_service

async def test_streaming():
    """Test streaming chat"""
    print("🌊 Testing streaming chat...\n")
    print("Question: Count from 1 to 5")
    print("Response: ", end='', flush=True)
    
    messages = [
        {"role": "user", "content": "Count from 1 to 5, separated by commas"}
    ]
    
    try:
        async for chunk in llm_service.chat_stream(messages):
            print(chunk, end='', flush=True)
        print("\n\n✅ Streaming test complete!")
    except Exception as e:
        print(f"\n❌ Streaming failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_streaming())