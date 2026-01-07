## 2024-05-23 - [In-memory processing for GLB export]
**Learning:** Found that `hy3dpaint/convert_utils.py` was writing a hardcoded `temp.glb` file to disk during conversion. This not only introduced unnecessary disk I/O latency but also created a critical race condition if multiple requests were processed concurrently.
**Action:** Always check intermediate file creation in data processing pipelines. Prefer in-memory streams (bytes) over temporary files when passing data between libraries (e.g., `trimesh` to `pygltflib`), especially for web server backends where concurrency is expected.
