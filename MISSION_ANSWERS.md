# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`

1. **Hardcode Secrets / Credentials trực tiếp trong source code** ([develop/app.py](01-localhost-vs-production/develop/app.py#L17-L18)):
   - **Bản develop:** `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Nếu push code lên GitHub, key và mật khẩu DB sẽ bị lộ ngay lập tức và nằm vĩnh viễn trong lịch sử Git.
   - **Cách bản production đã sửa:** Đọc hoàn toàn từ biến môi trường thông qua `os.getenv("OPENAI_API_KEY", "")` và `os.getenv("AGENT_API_KEY", "")` trong [production/config.py](01-localhost-vs-production/production/config.py#L27-L32), kèm theo file mẫu `.env.example` (không chứa secret thật).
2. **Không có quản lý cấu hình tập trung (Hardcoded Configuration)** ([develop/app.py](01-localhost-vs-production/develop/app.py#L21-L22)):
   - **Bản develop:** `DEBUG = True`, `MAX_TOKENS = 500` được gán cứng trong file `app.py`, muốn đổi cấu hình giữa môi trường dev/staging/prod phải sửa code.
   - **Cách bản production đã sửa:** Tạo dataclass `Settings` tập trung trong [production/config.py](01-localhost-vs-production/production/config.py#L15-L50) đọc từ biến môi trường (`DEBUG`, `ENVIRONMENT`, `LLM_MODEL`, `MAX_TOKENS`) và có hàm `.validate()` để fail-fast nếu thiếu cấu hình bắt buộc ở môi trường `production`.
3. **Dùng `print()` thay cho Structured Logging và in cả Secret ra console** ([develop/app.py](01-localhost-vs-production/develop/app.py#L33-L38)):
   - **Bản develop:** Dùng `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` làm lộ API key vào hệ thống thu thập log, không có timestamp, log level hay định dạng chuẩn để parse.
   - **Cách bản production đã sửa:** Sử dụng thư viện `logging` với định dạng JSON (`json.dumps(...)`) trong [production/app.py](01-localhost-vs-production/production/app.py#L28-L32) và [production/app.py](01-localhost-vs-production/production/app.py#L111-L122), chỉ ghi metadata an toàn (`event`, `question_length`, `client_ip`, `response_length`), tuyệt đối không log secret.
4. **Thiếu Health Check & Readiness Endpoints** ([develop/app.py](01-localhost-vs-production/develop/app.py#L42-L43)):
   - **Bản develop:** Không có `/health` và `/ready`. Khi deploy lên Cloud/Kubernetes/Docker, orchestrator không biết process còn sống hay đã sẵn sàng nhận traffic chưa.
   - **Cách bản production đã sửa:** Bổ sung `GET /health` (liveness probe trả `200 OK` kèm `uptime_seconds`) và `GET /ready` (readiness probe trả `200` khi `is_ready=True`, trả `503` khi đang khởi động/tắt) tại [production/app.py](01-localhost-vs-production/production/app.py#L135-L161).
5. **Bind cứng `host="localhost"`, `port=8000` và bật `reload=True`** ([develop/app.py](01-localhost-vs-production/develop/app.py#L49-L54)):
   - **Bản develop:** `uvicorn.run("app:app", host="localhost", port=8000, reload=True)`. Khi đóng gói vào Docker container hoặc deploy lên Railway/Render: `localhost` (`127.0.0.1`) không nhận được kết nối từ ngoài container; port trên cloud được cấp động qua biến môi trường `PORT`; còn `reload=True` gây tốn CPU/RAM và không ổn định ở production.
   - **Cách bản production đã sửa:** Đọc `HOST` (mặc định `0.0.0.0`), `PORT` từ env vars và chỉ bật `reload=settings.debug` ([production/app.py](01-localhost-vs-production/production/app.py#L194-L199)).
6. **Không xử lý Graceful Shutdown (`SIGTERM`)** ([develop/app.py](01-localhost-vs-production/develop/app.py)):
   - **Bản develop:** Không quản lý vòng đời ứng dụng và tín hiệu `SIGTERM`, dễ làm đứt ngang các request đang xử lý khi container restart hoặc scale down.
   - **Cách bản production đã sửa:** Dùng `asynccontextmanager` (`lifespan`) để quản lý startup/shutdown và đăng ký `signal.signal(signal.SIGTERM, handle_sigterm)` tại [production/app.py](01-localhost-vs-production/production/app.py#L39-L68) và [production/app.py](01-localhost-vs-production/production/app.py#L180-L189).

---

### Exercise 1.2: Kết quả chạy thử bản `develop` và `production`

- **Gọi thử bản `develop` (`POST /ask?question=Hello`):**
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:39:13 GMT
server: uvicorn
content-length: 95
content-type: application/json

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

- **Gọi thử bản `production` (`GET /health` và `POST /ask`):**
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:40:11 GMT
server: uvicorn
content-length: 129
content-type: application/json

{"status":"ok","uptime_seconds":2.3,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T07:40:12.084250+00:00"}

HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:40:12 GMT
server: uvicorn
content-length: 167
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","model":"gpt-4o-mini"}
```

---

### Exercise 1.3: Bảng so sánh `Develop` vs `Production`

| Feature | Basic (`develop/`) | Advanced (`production/`) | Tại sao quan trọng? |
|---------|--------------------|--------------------------|---------------------|
| **Config & Secrets** | Hardcode trực tiếp trong code (`OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG = True`) | Đọc từ biến môi trường (`os.getenv`) qua `config.py`, dùng `.env.example` làm mẫu | Tách biệt code và cấu hình theo chuẩn 12-Factor App; dễ dàng đổi cấu hình giữa dev/staging/prod mà không sửa code; ngăn chặn rò rỉ API key lên Git. |
| **Network Binding & Port** | Cố định `host="localhost"`, `port=8000`, `reload=True` | `host="0.0.0.0"`, đọc `PORT` động từ biến môi trường, tắt `reload` ở production | Container và Cloud PaaS (Railway, Render, Cloud Run) yêu cầu lắng nghe trên `0.0.0.0` và inject cổng động qua biến `PORT`. |
| **Health & Readiness Checks** | Không có (`❌`) | Có `GET /health` (liveness) và `GET /ready` (readiness trả `200`/`503`) (`✅`) | Giúp nền tảng cloud / load balancer biết khi nào container bị treo để tự động restart (`/health`) và khi nào instance đã sẵn sàng nhận traffic (`/ready`). |
| **Logging** | Dùng `print()`, định dạng tự do, in cả `OPENAI_API_KEY` ra màn hình | Structured JSON logging qua module `logging`, không ghi thông tin nhạy cảm | Log dạng JSON giúp các hệ thống giám sát (ELK, Loki, Datadog, CloudWatch) tự động parse, lọc, tìm kiếm và cảnh báo nhanh chóng mà không làm lộ secret. |
| **Shutdown** | Tắt đột ngột khi nhận tín hiệu dừng | Graceful shutdown với `lifespan` và bắt tín hiệu `SIGTERM` | Đảm bảo khi deploy bản mới hoặc scale down, agent ngừng nhận request mới nhưng vẫn hoàn tất các request đang xử lý dở, tránh lỗi 502/504 cho người dùng. |

---

## Part 2: Docker Containerization

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)

1. **Base image là gì?**
   - `python:3.11` (bản đầy đủ dựa trên Debian, bao gồm cả trình biên dịch C/C++, công cụ phát triển và hệ thống thư viện OS đầy đủ, nặng khoảng ~1 GB).
2. **Working directory là gì?**
   - `/app` (được thiết lập bởi chỉ thị `WORKDIR /app`; mọi lệnh `COPY`, `RUN`, `CMD` phía sau đều thực thi tại thư mục này trong container).
3. **Tại sao `COPY requirements.txt` trước khi `COPY` source code (`app.py`, `utils/`)?**
   - Để tận dụng cơ chế **Docker Layer Caching**. Docker cache từng bước (layer) theo thứ tự từ trên xuống; nếu một layer thay đổi thì toàn bộ các layer bên dưới nó bị mất cache (invalidated) và phải chạy lại. Vì file `requirements.txt` rất ít khi thay đổi so với code `app.py`, việc `COPY requirements.txt` rồi `RUN pip install` trước giúp Docker tái sử dụng lại layer cài đặt thư viện trong những lần sửa code tiếp theo, rút ngắn thời gian build từ hàng phút xuống còn vài giây.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?**
   - **`CMD`** định nghĩa lệnh hoặc tham số mặc định khi chạy container và **dễ dàng bị ghi đè** hoàn toàn nếu người dùng truyền lệnh khác vào cuối `docker run <image> <other_cmd>`.
   - **`ENTRYPOINT`** định nghĩa chương trình thực thi cố định của container (container hoạt động như một file binary); các đối số truyền thêm qua `docker run` sẽ được nối vào sau `ENTRYPOINT` làm tham số (trừ khi dùng cờ `--entrypoint`). Khi kết hợp cả hai, `CMD` đóng vai trò là các tham số mặc định truyền cho `ENTRYPOINT`.

---

### Exercise 2.2: Build và chạy container `my-agent:develop`

- **Lệnh build & chạy:**
```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --name test-dev-agent -p 8000:8000 my-agent:develop
```

- **Kết quả gọi `GET /health` và `POST /ask?question=What%20is%20Docker`:**
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:36:17 GMT
server: uvicorn
content-length: 53
content-type: application/json

{"status":"ok","uptime_seconds":2.6,"container":true}

HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:36:17 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

---

### Exercise 2.3: Multi-stage build & So sánh kích thước Image (`02-docker/production/Dockerfile`)

1. **Stage 1 (`FROM python:3.11-slim AS builder`) làm gì?**
   - Cài đặt các công cụ biên dịch hệ thống (`gcc`, `libpq-dev`) qua `apt-get` và chạy `pip install --no-cache-dir --user -r requirements.txt` để biên dịch & cài đặt toàn bộ Python packages vào thư mục `/root/.local`.
2. **Stage 2 (`FROM python:3.11-slim AS runtime`) làm gì?**
   - Bắt đầu từ một base image `python:3.11-slim` mới tinh, tạo user non-root `appuser`, chỉ copy kết quả thư viện đã cài đặt từ Stage 1 (`COPY --from=builder /root/.local /home/appuser/.local`) cùng mã nguồn ứng dụng (`main.py`, `utils/mock_llm.py`), thiết lập `USER appuser`, `HEALTHCHECK` và khởi chạy `uvicorn` với 2 workers.
3. **Tại sao image nhỏ hơn và an toàn hơn?**
   - Vì dùng base image `python:3.11-slim` đã lược bỏ các gói OS không cần thiết, đồng thời toàn bộ trình biên dịch (`gcc`), header files (`libpq-dev`), apt cache và pip build artifacts ở Stage 1 bị loại bỏ hoàn toàn, không đi vào image `runtime` cuối cùng. Việc không có compiler và chạy dưới quyền `appuser` (non-root) cũng giảm thiểu bề mặt tấn công (attack surface).

- **Kết quả đo kích thước thực tế bằng `docker images my-agent` và `docker inspect`:**

```text
REPOSITORY   TAG        IMAGE ID       CREATED          SIZE
my-agent     advanced   8e0b344f6493   34 minutes ago   163MB
my-agent     develop    ab7b3fe6a089   50 minutes ago   1.15GB
```

| Phiên bản Image | Kích thước hiển thị (`docker images`) | Kích thước chính xác (Bytes / MB) |
|---|---|---|
| **Develop (`my-agent:develop`)** | `1.15GB` | `1,154,311,846 bytes` (**1,154.31 MB**) |
| **Production (`my-agent:advanced`)** | `163MB` | `162,882,178 bytes` (**162.88 MB**) |
| **Chênh lệch (Giảm được)** | **Giảm ~991.43 MB** | **Giảm 85.89%** dung lượng |

---

### Exercise 2.4: Docker Compose Stack (`02-docker/production/docker-compose.yml`)

1. **Các services được khởi chạy và cách giao tiếp:**
   - Gồm **4 services** cùng kết nối vào mạng nội bộ `internal` (bridge network):
     - **`nginx` (`nginx:alpine`)**: Reverse proxy & Load balancer duy nhất mở cổng ra máy host (`80:80`, `443:443`), áp dụng rate limit theo IP (`10r/s`) và gắn security headers (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`), chuyển tiếp request vào `http://agent:8000`.
     - **`agent` (`my-agent:advanced`)**: FastAPI AI Agent chạy trên cổng nội bộ `8000` (không expose trực tiếp ra host), chỉ khởi động sau khi `redis` và `qdrant` đã `healthy` (`depends_on: condition: service_healthy`).
     - **`redis` (`redis:7-alpine`)**: In-memory store ở cổng nội bộ `6379` (lưu volume `redis_data`), phục vụ caching session và rate limiting.
     - **`qdrant` (`qdrant/qdrant:v1.9.0`)**: Vector database ở cổng nội bộ `6333` (lưu volume `qdrant_data`), phục vụ lưu trữ embeddings cho RAG.

2. **Sơ đồ kiến trúc (Architecture Diagram):**

```text
                        ┌──────────────────────────────────────────────────────┐
                        │           Docker Bridge Network (internal)           │
                        │                                                      │
┌──────────┐   :80/:443 │  ┌───────────────┐      :8000      ┌──────────────┐  │
│  Client  │ ─────────▶ │  │     nginx     │ ──────────────▶ │    agent     │  │
│  (Host)  │            │  │ (ReverseProxy)│                 │ (FastAPI x2) │  │
└──────────┘            │  └───────────────┘                 └──────┬───────┘  │
                        │                                           │          │
                        │                             ┌─────────────┴────────┐ │
                        │                             ▼ :6379                ▼ :6333
                        │                      ┌─────────────┐        ┌─────────────┐
                        │                      │    redis    │        │   qdrant    │
                        │                      │(Cache/Limit)│        │ (Vector DB) │
                        │                      └──────┬──────┘        └──────┬──────┘
                        └─────────────────────────────┼──────────────────────┼─┘
                                                      ▼                      ▼
                                                [redis_data]          [qdrant_data]
```

3. **Kết quả kiểm tra trạng thái stack (`docker compose ps`) và gọi thử qua Nginx (`http://localhost`):**

```text
NAME                      IMAGE                  COMMAND                  SERVICE   STATUS                    PORTS
k5-day14-part2-agent-1    k5-day14-part2-agent   "uvicorn main:app --…"   agent     Up 16 seconds (healthy)   8000/tcp
k5-day14-part2-nginx-1    nginx:alpine           "/docker-entrypoint.…"   nginx     Up 15 seconds             0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
k5-day14-part2-qdrant-1   qdrant/qdrant:v1.9.0   "./entrypoint.sh"        qdrant    Up 26 seconds (healthy)   6333-6334/tcp
k5-day14-part2-redis-1    redis:7-alpine         "docker-entrypoint.s…"   redis     Up 26 seconds (healthy)   6379/tcp
```

- **Test `GET http://localhost/health` qua Nginx:**
```http
HTTP/1.1 200 OK
Server: nginx
Date: Thu, 26 Nov 2026 08:38:06 GMT
Content-Type: application/json
Content-Length: 96
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":14.3,"version":"2.0.0","timestamp":"2026-11-26T08:38:06.961192"}
```

- **Test `POST http://localhost/ask` qua Nginx:**
```http
HTTP/1.1 200 OK
Server: nginx
Date: Thu, 26 Nov 2026 08:38:07 GMT
Content-Type: application/json
Content-Length: 126
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```
