import time
import requests
from poly_market_trader.api.llm_provider import LLMProvider, MarketContext, LLMModel

def benchmark_models():
    print("="*60)
    print("🚀 LLM MODEL BENCHMARK")
    print("="*60)
    
    provider = LLMProvider()
    
    if not provider.check_connection():
        print("❌ Could not connect to LMStudio at http://192.168.1.227:1234/v1")
        return

    test_cases = [
        {
            "question": "Will Bitcoin hit $100k by Jan 2026?",
            "desc": "Resolves YES if Binance BTC/USDT > 100000.",
            "yes": 0.45, "no": 0.55
        },
        {
            "question": "Will Solana flip BNB in market cap by Friday?",
            "desc": "Based on CoinGecko market cap.",
            "yes": 0.12, "no": 0.88
        }
    ]
    
    models = [
        LLMModel.NANO.value,
        LLMModel.REASONING.value
    ]
    
    for model in models:
        print(f"\n🧠 Testing Model: {model}")
        print("-" * 50)
        
        total_time = 0
        success_count = 0
        
        for case in test_cases:
            context = MarketContext(
                question=case['question'],
                description=case['desc'],
                yes_price=case['yes'],
                no_price=case['no'],
                volume=150000.0,
                tags=['Crypto', 'Benchmark']
            )
            
            start_time = time.time()
            result = provider.analyze_market(context, model=model)
            duration = time.time() - start_time
            total_time += duration
            
            if result:
                success_count += 1
                print(f"  ✅ [SUCCESS] {duration:.2f}s | Asset: {result.get('asset')} | Target: {result.get('target_value')}")
            else:
                print(f"  ❌ [FAILED]  {duration:.2f}s")
                
        avg_time = total_time / len(test_cases)
        print(f"\n📊 {model} Results:")
        print(f"   Success Rate: {success_count}/{len(test_cases)}")
        print(f"   Avg Latency:  {avg_time:.2f}s")

if __name__ == "__main__":
    benchmark_models()
