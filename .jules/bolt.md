## 2024-05-23 - FastAPI Async Blocking
**Learning:** `async def` routes in FastAPI run on the main event loop. Calling synchronous heavy functions (like model inference) directly inside them blocks the entire server, including health checks.
**Action:** Always wrap synchronous blocking calls in `await run_in_threadpool(...)` or `asyncio.to_thread(...)` within `async def` routes.
