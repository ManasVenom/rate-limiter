"""
Interactive demo script illustrating the Token Bucket Rate Limiter in action.
"""

import time
import sys
import os

# Ensure package is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ratelimiter import TokenBucketLimiter, rate_limit, RateLimitExceeded


def main():
    print("=" * 65)
    print("🚦 TOKEN BUCKET RATE LIMITER DEMO")
    print("=" * 65)

    # 1. Basic Token Bucket Demo
    capacity = 5
    refill_rate = 2.0  # 2 tokens per second
    limiter = TokenBucketLimiter(capacity=capacity, refill_rate=refill_rate)
    user_id = "user_42"

    print(f"\nConfiguration: Capacity = {capacity} tokens, Refill = {refill_rate} tokens/sec")
    print(f"Simulating rapid requests for '{user_id}'...\n")

    print(f"{'#':<4} {'Status':<10} {'Remaining':<12} {'Retry-After':<14} {'Headers'}")
    print("-" * 65)

    for i in range(1, 9):
        result = limiter.acquire(user_id)
        status = "✅ ALLOWED" if result.allowed else "❌ BLOCKED"
        headers = result.to_headers()
        retry_str = f"{result.retry_after:.2f}s" if not result.allowed else "-"
        print(f"{i:<4} {status:<10} {result.remaining:<12.1f} {retry_str:<14} {headers}")
        time.sleep(0.1)

    print("\n⏳ Pausing for 1.5 seconds to allow tokens to replenish...")
    time.sleep(1.5)

    print(f"\nCurrent tokens in bucket: {limiter.get_tokens(user_id):.2f}")
    print("\nAttempting 3 more requests:")
    for i in range(1, 4):
        result = limiter.acquire(user_id)
        status = "✅ ALLOWED" if result.allowed else "❌ BLOCKED"
        print(f"Request {i}: {status} (Remaining tokens: {result.remaining:.2f})")

    # 2. Decorator Demo
    print("\n" + "=" * 65)
    print("🎯 FUNCTION DECORATOR DEMO")
    print("=" * 65)

    api_limiter = TokenBucketLimiter(capacity=3, refill_rate=1.0)

    @rate_limit(api_limiter, key=lambda client_ip: f"ip:{client_ip}")
    def handle_payment_request(client_ip: str, amount: float):
        return f"Payment of ${amount:.2f} processed for {client_ip}"

    ip = "192.168.1.100"
    for i in range(1, 5):
        try:
            msg = handle_payment_request(ip, amount=50.0 * i)
            print(f"Call {i}: {msg}")
        except RateLimitExceeded as e:
            print(f"Call {i}: ⚠️ {e}")

    print("\n" + "=" * 65)
    print("✨ Demo complete! Ready for distributed Redis & additional algorithms.")
    print("=" * 65)


if __name__ == "__main__":
    main()
