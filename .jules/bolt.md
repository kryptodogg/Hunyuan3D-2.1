## 2025-02-18 - FastAPI Synchronous Handlers Blocking Event Loop
**Learning:** In FastAPI, `async def` routes run on the main event loop. Calling synchronous blocking functions (like heavy model inference) directly within them blocks the entire server, preventing other endpoints (like health checks) from responding.
**Action:** Always wrap blocking synchronous calls in `fastapi.concurrency.run_in_threadpool` (or `asyncio.to_thread`) when inside an `async def` handler. Ensure global resources (like semaphores) are properly initialized or have fallback mechanisms if used in these handlers.
