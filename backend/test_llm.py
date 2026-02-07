"""
Test script for LLM service
Run with: uv run python test_llm.py
"""
from app.services.llm import llm_service

def test_health_check():
    """Test if Ollama is accessible"""
    print("🔍 Testing Ollama connection...")
    is_healthy = llm_service.health_check()
    
    if is_healthy:
        print("✅ Ollama is running and accessible!")
        return True
    else:
        print("❌ Ollama is not accessible. Make sure it's running:")
        print("   ollama serve")
        return False

def test_basic_chat():
    """Test basic chat functionality"""
    print("\n💬 Testing basic chat...")
    
    messages = [
        {"role": "user", "content": "Say 'Hello, I am working!' in one sentence"}
    ]
    
    try:
        response = llm_service.chat(messages)
        print(f"✅ Response received:\n{response}")
        return True
    except Exception as e:
        print(f"❌ Chat failed: {e}")
        return False

def test_coding_question():
    """Test with a coding question"""
    print("\n🐍 Testing with coding question...")
    
    messages = [
        {"role": "user", "content": "Explain a for loop in Python in 2 sentences"}
    ]
    
    try:
        response = llm_service.chat(messages, temperature=0.3)
        print(f"✅ Response received:\n{response}")
        return True
    except Exception as e:
        print(f"❌ Chat failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("CodeMentor LLM Service Test")
    print("=" * 60)
    
    health_ok = test_health_check()
    
    if health_ok:
        test_basic_chat()
        test_coding_question()
    else:
        print("\n⚠️  Fix Ollama connection before testing chat functionality")
    
    print("\n" + "=" * 60)
    print("Tests complete!")
    print("=" * 60)
