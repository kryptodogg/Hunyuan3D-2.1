## 2025-02-18 - Async Route Blocking in FastAPI
**Learning:** Defining a route as `async def` in FastAPI does not automatically offload synchronous work to a thread pool. It runs on the main event loop. If the work is CPU/IO bound and synchronous, it blocks the entire server (including health checks).
**Action:** Always check if `async def` routes contain synchronous blocking calls. Use `fastapi.concurrency.run_in_threadpool` or `asyncio.to_thread` to offload them.
