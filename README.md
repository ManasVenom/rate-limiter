# 🚦 Distributed & In-Memory Rate Limiter in Python

A modular, production-ready rate limiting library in Python designed for high-concurrency microservices and API gateways.

---

## 🎯 Architecture & Roadmap

This project is built incrementally, progressing from pure Python in-memory algorithms to a distributed, sub-5ms Redis-backed rate limiter with custom Lua scripts capable of handling 10,000+ req/s.

| Phase | Milestone | Status | Description |
|:---:|:---|:---:|:---|
| **1** | **In-Memory Token Bucket** | ✅ **Completed** | Thread-safe, burst-tolerant, lazy replenishment, memory cleanup, decorator & HTTP header support |
| **2** | **Sliding Window Log** | 🔄 *Next* | Timestamp-based request tracking to prevent boundary traffic spikes |
| **3** | **Sliding Window Counter / Leaky Bucket** | ⏳ *Planned* | Memory-efficient sliding window approximations & queue-based traffic shaping |
| **4** | **Distributed Redis Backend (Lua Scripts)** | ⏳ *Planned* | Atomic Lua operations eliminating race conditions under high concurrency (10k+ req/s) |
| **5** | **Gateway Middlewares & Benchmarks** | ⏳ *Planned* | FastAPI / Starlette / Flask integration with latency & throughput benchmarking |

---

## 🧠 Algorithm: Token Bucket

### How It Works
1. **Bucket Capacity ($B$):** The maximum number of tokens a bucket can hold at any given time (determines allowable burst size).
2. **Refill Rate ($r$):** The number of tokens added to the bucket every second.
3. **Lazy Evaluation:** Instead of spinning background worker threads for every key, tokens are accrued mathematically when a request arrives:
   $$\text{tokens} = \min(B, \text{tokens}_{\text{prev}} + (t_{\text{now}} - t_{\text{last}}) \times r)$$
4. **Decision:**
   - If $\text{tokens} \ge \text{requested}$: Decrement tokens and return `allowed = True`.
   - If $\text{tokens} < \text{requested}$: Reject request and calculate `retry_after = (requested - tokens) / r`.

---

## 📁 Project Structure

```text
rate-limiter/
├── .gitignore
├── requirements.txt
├── README.md
├── ratelimiter/
│   ├── __init__.py           # Public exports
│   ├── base.py               # BaseRateLimiter ABC & RateLimitResult dataclass
│   ├── token_bucket.py       # Thread-safe TokenBucketLimiter
│   └── decorator.py          # @rate_limit function decorator
├── tests/
│   ├── __init__.py
│   └── test_token_bucket.py  # Unit & concurrency test suite
└── examples/
    └── demo.py               # Interactive CLI demonstration
```

---

## 🚀 Quickstart

### 1. Run Unit Tests
No external dependencies required for core in-memory tests:
```bash
python -m unittest discover tests
```

### 2. Run the Interactive Demo
```bash
python examples/demo.py
```

### 3. Basic Usage in Python

```python
from ratelimiter import TokenBucketLimiter

# Allow burst of 10 requests, refilling at 2 requests per second
limiter = TokenBucketLimiter(capacity=10, refill_rate=2.0)

# Check request for a client
result = limiter.acquire("client_ip_192.168.1.1")

if result.allowed:
    print(f"Request permitted! Tokens remaining: {result.remaining:.2f}")
else:
    print(f"Throttled! Please retry after {result.retry_after:.2f} seconds.")
    print("HTTP Headers to send back:", result.to_headers())
    # Headers output: {'X-RateLimit-Limit': '10', 'X-RateLimit-Remaining': '0', 'Retry-After': '1', ...}
```

### 4. Function / API Decorator

```python
from ratelimiter import TokenBucketLimiter, rate_limit, RateLimitExceeded

limiter = TokenBucketLimiter(capacity=5, refill_rate=1.0)

@rate_limit(limiter, key=lambda user_id, *_: f"user:{user_id}")
def send_notification(user_id: str, message: str):
    return f"Notification sent to {user_id}: {message}"

# Call safely:
try:
    send_notification("usr_99", "Hello!")
except RateLimitExceeded as e:
    print(e)
```

---

## 🔒 Concurrency & Memory Safety
- **Thread Safety:** Bucket state modifications are protected by `threading.Lock`.
- **Memory Leak Protection:** Includes `prune_stale_keys(max_idle_seconds)` to evict idle buckets for transient IP addresses.
- **Deterministic Testing:** Supports custom injectable clocks (`MockClock`) allowing instant simulation of time elapsed without thread sleeps.
