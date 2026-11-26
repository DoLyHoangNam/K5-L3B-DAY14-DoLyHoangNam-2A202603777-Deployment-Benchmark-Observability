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

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/app.py`)

1. **API key được kiểm tra ở đâu?**
   - Được kiểm tra trong hàm dependency `verify_api_key(api_key: str = Security(api_key_header))` ([04-api-gateway/develop/app.py](04-api-gateway/develop/app.py#L36-L54)) sử dụng `APIKeyHeader(name="X-API-Key", auto_error=False)` và được gắn vào endpoint `POST /ask` thông qua `_key: str = Depends(verify_api_key)`.
2. **Điều gì xảy ra nếu thiếu hoặc sai key?**
   - Nếu **thiếu** header `X-API-Key` (`not api_key`): trả về mã lỗi **`HTTP 401 Unauthorized`** (`Missing API key. Include header: X-API-Key: <your-key>`).
   - Nếu **sai** key (`api_key != API_KEY`): bản `develop` trả về **`HTTP 403 Forbidden`** (`Invalid API key.`). *(Lưu ý: Trong chuẩn hợp đồng của Final Project Part 6, cả thiếu lẫn sai key đều thống nhất trả về `HTTP 401`)*.
3. **Làm sao để rotate (xoay vòng) API key mà không gây downtime?**
   - Thay vì chỉ đọc 1 key đơn lẻ, cấu hình biến môi trường chứa danh sách các key đang có hiệu lực (ví dụ `AGENT_API_KEYS=new_key,old_key`). Khi rotate:
     1. Thêm `new_key` vào biến môi trường trên Cloud song song với `old_key` và reload service.
     2. Cập nhật các client chuyển sang gọi bằng `new_key`.
     3. Sau khi toàn bộ client đã chuyển sang `new_key`, xoá `old_key` khỏi biến môi trường.

- **Kết quả test `curl -i` trên bản `develop` (`AGENT_API_KEY=secret-key-123`):**

```http
# 1. Không gửi X-API-Key -> 401 Unauthorized
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 08:41:42 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# 2. Gửi X-API-Key: secret-key-123 -> 200 OK
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:41:42 GMT
server: uvicorn
content-length: 122
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

---

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (`04-api-gateway/production/`)

1. **Giải thích luồng JWT (`auth.py`):**
   - Client gửi `username` / `password` (`student` / `demo123`) tới `POST /auth/token`. Server xác thực qua `authenticate_user()`, sau đó gọi `create_token()` ký một JWT bằng thuật toán `HS256` với `SECRET_KEY`, bên trong payload chứa `sub` (username), `role` (`user` hoặc `admin`), `iat` và `exp` (hết hạn sau 60 phút).
   - Ở các request tiếp theo tới `POST /ask`, client đính kèm header `Authorization: Bearer <REDACTED_JWT_TOKEN>`. Hàm `verify_token()` dùng `jwt.decode()` kiểm tra chữ ký số và thời hạn `exp` một cách **stateless** (không cần truy vấn database mỗi request).
2. **Trả lời câu hỏi Rate Limiting (`rate_limiter.py`):**
   - **Thuật toán sử dụng:** **Sliding Window Log / Counter** (lưu danh sách các mốc thời gian timestamp của từng request trong `deque` cho mỗi `user_id`; mỗi khi có request mới sẽ loại bỏ các timestamp cũ hơn `now - 60s`).
   - **Giới hạn (Limit):** Với role `user` (`student`) là **10 requests / 60 giây** (`rate_limiter_user`); với role `admin` (`teacher`) là **100 requests / 60 giây** (`rate_limiter_admin`).
   - **Cách phân quyền / bypass hoặc nâng limit cho admin:** Trong `app.py` (dòng 141), sau khi `verify_token` trích xuất `role` từ JWT payload, hệ thống chọn bộ giới hạn theo role: `limiter = rate_limiter_admin if role == "admin" else rate_limiter_user` (hoặc có thể bỏ qua bước gọi `limiter.check()` nếu `role == "admin"`).

- **Kết quả test `curl -i` cho 3 trường hợp `401`, `200`, `429` (đã che JWT token):**

```http
# Trường hợp 1: Gọi POST /ask không có JWT token -> 401 Unauthorized
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 08:41:48 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 76
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

# Trường hợp 2: Đăng nhập student/demo123 lấy token, gọi POST /ask với Authorization: Bearer <REDACTED_JWT_TOKEN> (Request #1) -> 200 OK
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:41:48 GMT
server: uvicorn
content-length: 215
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Explain JWT","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}

# Trường hợp 3: Gửi liên tiếp vượt quá 10 requests/phút (Request #11) với Authorization: Bearer <REDACTED_JWT_TOKEN> -> 429 Too Many Requests
HTTP/1.1 429 Too Many Requests
date: Thu, 26 Nov 2026 08:42:56 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795682636
retry-after: 57
content-length: 98
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":57}}
```

---

### Exercise 4.4: Cost Guard Implementation (`cost_guard.py`)

- **Tại sao cần cả Rate Limiter lẫn Cost Guard?**
  - **Rate Limiter** bảo vệ hệ thống theo **tần suất gọi (requests/phút)** chống spam/DDoS ngắn hạn.
  - **Cost Guard** bảo vệ **ngân sách tài chính (USD/ngày hoặc USD/tháng)**: một người dùng có thể gửi ít request (không vi phạm rate limit) nhưng mỗi request lại chứa prompt rất dài hoặc yêu cầu sinh hàng nghìn output tokens suốt cả ngày, dẫn tới chi phí LLM API tăng vọt.
- **Cách thiết kế và cài đặt Cost Guard với Redis (stateless, dùng chung cho nhiều worker/instance):**
  1. **Trước khi gọi LLM (`check_budget`)**:
     - Tạo key theo ngày (hoặc tháng), ví dụ `cost:daily:{YYYY-MM-DD}` (hoặc `budget:{user_id}:{YYYY-MM}`).
     - Đọc tổng chi phí hiện tại từ Redis (`float(r.get(key) or 0.0)`).
     - Nếu `current_cost >= DAILY_BUDGET_USD`, chặn ngay lập tức bằng `raise HTTPException(status_code=402, detail="Daily budget exceeded")` mà không tốn tiền gọi LLM.
  2. **Sau khi gọi LLM (`record_cost`)**:
     - Tính chi phí thực tế từ số lượng `input_tokens` và `output_tokens`:
       $$\text{cost} = \frac{\text{input\_tokens}}{1000} \times \text{PRICE\_INPUT\_PER\_1K} + \frac{\text{output\_tokens}}{1000} \times \text{PRICE\_OUTPUT\_PER\_1K}$$
     - Cộng dồn nguyên tử (atomic) vào Redis bằng lệnh `r.incrbyfloat(key, cost)` và đặt `r.expire(key, 86400 * 2)` để tự động dọn key cũ.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Check vs Readiness Check (`05-scaling-reliability/develop/app.py`)

| Tiêu chí | Liveness Probe (`GET /health`) | Readiness Probe (`GET /ready`) |
|---|---|---|
| **Câu hỏi trả lời** | *"Process container của Agent có còn sống (không bị deadlock/crash) không?"* | *"Agent đã sẵn sàng nhận và xử lý traffic từ người dùng chưa?"* |
| **Mã HTTP trả về** | Luôn trả về **`200 OK`** miễn là event loop của FastAPI/Uvicorn còn phản hồi (kể cả khi Redis/DB tạm thời mất kết nối). | Trả về **`200 OK`** khi mọi điều kiện sẵn sàng (`_is_ready=True`, kết nối Redis/DB thông suốt); trả về **`503 Service Unavailable`** khi đang khởi động, đang shutdown hoặc mất kết nối Redis. |
| **Hành động của Orchestrator / Load Balancer** | Nếu `/health` thất bại liên tiếp → Platform (Docker/K8s/Railway/Render) sẽ **kill và restart lại container**. | Nếu `/ready` trả `503` → Load Balancer (Nginx/K8s Service) **tạm ngưng gửi request mới** tới instance này nhưng **không** kill container, cho phép nó tự phục hồi hoặc hoàn tất shutdown. |
| **Tại sao `/health` không được phụ thuộc Redis?** | Nếu `/health` trả `503` khi Redis bảo trì hoặc chập chờn, orchestrator sẽ restart toàn bộ dàn container Agent liên tục (cascading restart loop), làm sập cả hệ thống thay vì chỉ tạm ngưng nhận traffic qua `/ready`. | `/ready` chịu trách nhiệm kiểm tra `redis.ping()`, giúp cô lập tạm thời instance mất kết nối Redis khỏi vòng xoay load balancing. |

---

### Exercise 5.2: Graceful Shutdown (`SIGTERM`)

- **Vấn đề nếu tắt đột ngột:** Khi deploy phiên bản mới, scale down hoặc `docker stop`, hệ thống gửi tín hiệu `SIGTERM` cho container. Nếu process thoát ngay lập tức, các request LLM đang xử lý dở (thường mất vài giây) sẽ bị cắt ngang, làm client nhận lỗi `502 Bad Gateway` hoặc mất dữ liệu.
- **Quy trình Graceful Shutdown trong `05-scaling-reliability/develop/app.py`:**
  1. **Theo dõi request đang chạy:** Middleware `track_requests` tăng biến đếm `_in_flight_requests += 1` khi bắt đầu mỗi request và giảm `_in_flight_requests -= 1` trong khối `finally`.
  2. **Nhận tín hiệu `SIGTERM`:** Container orchestrator gửi `SIGTERM`. Handler `handle_sigterm` ghi nhận log và chuyển giao cho Uvicorn kích hoạt phần `shutdown` trong `lifespan(app)`.
  3. **Ngừng nhận traffic mới:** Cờ `_is_ready` được gán ngay về `False` → `GET /ready` lập tức trả về `503 Service Unavailable`, báo cho Load Balancer ngừng định tuyến request mới vào instance này.
  4. **Chờ hoàn tất in-flight requests:** Vòng lặp `while _in_flight_requests > 0 and elapsed < timeout:` chờ tối đa 30 giây (`timeout_graceful_shutdown=30`) cho tới khi các request đang xử lý xong xuôi (`200 OK`), đóng kết nối sạch sẽ rồi mới thoát process với `exit code 0`.

---

### Exercise 5.3: Stateless Design với Redis (`05-scaling-reliability/production/app.py`)

- **Tại sao lưu state trong RAM (`conversation_history = {}`) bị hỏng khi scale nhiều instances?**
  - Mỗi container/worker chạy trong một không gian bộ nhớ (RAM) độc lập. Khi có Load Balancer chia tải kiểu Round-Robin qua 3 instances:
    - Lượt 1: User gửi câu hỏi → Nginx đẩy vào **Instance 1** → lịch sử lưu trong RAM của Instance 1.
    - Lượt 2: User gửi câu hỏi tiếp theo kèm `session_id` → Nginx đẩy sang **Instance 2** → RAM của Instance 2 không hề có `session_id` này → Agent mất trí nhớ hoặc báo lỗi `404 Session not found`.
    - Ngoài ra, nếu một instance restart hoặc scale down, toàn bộ lịch sử hội thoại trong RAM của nó biến mất vĩnh viễn.
- **Giải pháp Stateless với Redis:**
  - Các Agent instances không lưu bất kỳ trạng thái phiên làm việc nào trong RAM.
  - Mọi thao tác đọc/ghi lịch sử hội thoại (`save_session`, `load_session`, `append_to_history`) đều truy xuất trực tiếp vào **Redis dùng chung** dưới key `session:{session_id}` kèm thời hạn tự huỷ `TTL = 3600s` (`_redis.setex(...)`).
  - Nhờ đó, bất kỳ instance nào nhận request cũng đọc được đầy đủ ngữ cảnh trước đó của `session_id`, cho phép scale ngang từ 1 lên $N$ instances hoặc thay thế instance bất kỳ lúc nào.

---

### Exercise 5.4 & 5.5: Load Balancing với Nginx & Kiểm thử Stateless (`test_stateless.py`)

- **Lệnh khởi chạy stack 3 instances:**
```bash
cd 05-scaling-reliability/production
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
python test_stateless.py
docker compose -p k5-day14-scaling down
```

- **Cơ chế hoạt động của stack:**
  - Docker Compose khởi chạy 1 container `redis:7-alpine`, 3 replicas của service `agent` (mỗi container tự sinh một `INSTANCE_ID = instance-<hex>`), và 1 container `nginx:alpine` lắng nghe ở cổng `8080:80`.
  - Nginx sử dụng Docker internal DNS resolver (`127.0.0.11`) để phân giải tên miền `agent:8000` ra IP của cả 3 container agent và phân phối các request theo thuật toán **Round-Robin** (kèm cơ chế tự động thử sang instance khác nếu gặp lỗi: `proxy_next_upstream error timeout http_503`).

- **Kết quả chạy `python test_stateless.py` (5 câu hỏi liên tiếp trong cùng 1 `session_id`):**
```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 9c4f1a2e-7b8d-4e3a-91c2-5f6a8b0d3e19

Request 1: [instance-a18f3c]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-7d2e9b]
  Q: Why do we need containers?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ...

Request 3: [instance-4c91e0]
  Q: What is Kubernetes?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ...

Request 4: [instance-a18f3c]
  Q: How does load balancing work?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ...

Request 5: [instance-7d2e9b]
  Q: What is Redis used for?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ...

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-a18f3c', 'instance-7d2e9b', 'instance-4c91e0'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build on...
  [user]: Why do we need containers?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đ...
  [user]: What is Kubernetes?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đ...
  [user]: How does load balancing work?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đ...
  [user]: What is Redis used for?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đ...

✅ Session history preserved across all instances via Redis!
```

- **Giải thích kết quả:**
  - Cả 5 request trong cùng một phiên hội thoại (`session_id`) được Nginx chia đều luân phiên qua cả 3 instance (`instance-a18f3c`, `instance-7d2e9b`, `instance-4c91e0`).
  - Khi gọi `GET /chat/{session_id}/history`, toàn bộ **10 messages** (5 cặp `user` + `assistant`) đều được bảo toàn đầy đủ theo đúng thứ tự thời gian vì mọi instance đều đọc/ghi chung vào Redis thay vì bộ nhớ cục bộ.

---

## Part 6: Final Project — `check_production_ready.py` Output

Đã hoàn thiện toàn bộ 12 tiêu chí trong `06-lab-complete/` (`app/config.py`, `app/redis_client.py`, `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`, `app/main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`).

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

## Part 3: Cloud Deployment (CP6)

### Exercise 3.1: Deploy Agent Part 6 (`06-lab-complete/`) lên Cloud

- **Nền tảng sử dụng:** Railway (kèm dịch vụ Managed Redis được liên kết qua biến `REDIS_URL`).
- **Thư mục deploy:** `06-lab-complete/` (sử dụng multi-stage `Dockerfile` và `railway.toml`).
- **Public URL:** `https://k5-l3b-day14-dolyhoangnam-agent-production.up.railway.app` (chi tiết cấu hình và lệnh kiểm thử trong [DEPLOYMENT.md](DEPLOYMENT.md)).
- **Screenshots:**
  - Dashboard: [`screenshots/dashboard.png`](screenshots/dashboard.png)
  - Service Running: [`screenshots/running.png`](screenshots/running.png)
  - Test Results (4 lệnh tự kiểm `200`, `200`, `401`, `200`): [`screenshots/test.png`](screenshots/test.png)

- **Kết quả chạy 4 lệnh tự kiểm ở CP6:**
```bash
$ curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
200
$ curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
200
$ curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
401
$ curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
200
```

---

### Exercise 3.2: So sánh `railway.toml` với `render.yaml`

| Tiêu chí | `railway.toml` (Railway) | `render.yaml` (Render Blueprint) | Tại sao có sự khác biệt? |
|---|---|---|---|
| **Định dạng & Phạm vi** | Định dạng **TOML**, cấu hình cho **1 service đơn lẻ** trong thư mục hiện tại (`[build]`, `[deploy]`). | Định dạng **YAML** (Infrastructure-as-Code Blueprint), khai báo được **nhiều services và databases** (web service, Redis, PostgreSQL...) trong cùng một file dưới danh sách `services:`. | Railway quản lý đa dịch vụ và biến môi trường trực tiếp trên Project Canvas/CLI, nên file `railway.toml` chỉ cần chỉ định cách build & chạy service đó; còn Render dùng Blueprint để đồng bộ toàn bộ kiến trúc stack từ Git. |
| **Khai báo Build** | Dùng `builder = "DOCKERFILE"` (hoặc `NIXPACKS`/`RAILPACK`) và `dockerfilePath = "Dockerfile"`. | Khai báo `type: web` và `runtime: docker` (hoặc `runtime: python` kèm `buildCommand` và `startCommand`). | Railway mặc định tự nhận diện code qua Nixpacks nên cần cờ `builder = "DOCKERFILE"`, trong khi Render phân loại rõ `runtime` của từng `type` service. |
| **Quản lý Biến môi trường & Secrets** | Không khai báo `envVars` trong `railway.toml`; mọi biến và secret được đặt qua lệnh `railway variables set` hoặc trên Dashboard để tránh lộ trong Git. | Hỗ trợ khai báo danh sách `envVars` ngay trong `render.yaml`: biến thường dùng `value: ...`, còn secret dùng **`generateValue: true`** (tự sinh ngẫu nhiên) hoặc **`sync: false`** (bắt buộc nhập tay trên Dashboard khi tạo Blueprint). | Render Blueprint hướng tới việc đóng gói cả schema biến môi trường vào IaC mà vẫn đảm bảo nguyên tắc 12-Factor không lưu plaintext secret vào Git. |
| **Health Check & Restart Policy** | `healthcheckPath = "/health"`, `healthcheckTimeout = 30`, có `restartPolicyType = "ON_FAILURE"` và `restartPolicyMaxRetries = 3`. | `healthCheckPath: /health` (camelCase); cơ chế tự động restart khi container fail được nền tảng quản lý mặc định. | Cả hai đều gọi `GET /health` để xác nhận container mới đã sẵn sàng trước khi chuyển luồng traffic (Zero-Downtime Deployment). |

---

### Exercise 3.3: Phân tích CI/CD Pipeline của GCP Cloud Run (`03-cloud-deployment/production-cloud-run/`)

Qua hai file `cloudbuild.yaml` và `service.yaml`, pipeline CI/CD tự động trên Google Cloud hoạt động qua **4 bước tuần tự** khi có commit mới được đẩy lên nhánh `main`:
1. **Step 1 — Automated Testing (`id: test`)**: Khởi chạy container tạm `python:3.11-slim`, cài đặt `requirements.txt` cùng `pytest` và chạy bộ kiểm thử `pytest tests/ -v --tb=short`. Nếu bất kỳ test nào fail, toàn bộ pipeline dừng ngay lập tức, không build và không deploy.
2. **Step 2 — Build Docker Image (`id: build`, `waitFor: [test]`)**: Dùng `gcr.io/cloud-builders/docker` để build image gắn 2 tag (`gcr.io/$PROJECT_ID/ai-agent:$COMMIT_SHA` để định danh chính xác phiên bản theo commit và `:latest`), đồng thời dùng `--cache-from` để tận dụng layer cache từ bản build trước.
3. **Step 3 — Push lên Container Registry (`id: push`, `waitFor: [build]`)**: Đẩy image vừa build (`--all-tags`) lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Step 4 — Deploy lên Cloud Run (`id: deploy`, `waitFor: [push]`)**: Dùng `gcloud run deploy` để triển khai image theo đúng tag `$COMMIT_SHA` lên vùng `asia-southeast1` với cấu hình production được định nghĩa đồng bộ trong `service.yaml` (Knative Service): tự động scale từ `minScale: 1` (tránh cold start) đến `maxScale: 10` (mỗi instance chịu tối đa `containerConcurrency: 80` với `1 CPU / 512Mi RAM`), nạp secret an toàn từ **Google Secret Manager** (`--set-secrets=OPENAI_API_KEY=openai-key:latest`, `secretKeyRef`) và kiểm tra sức khoẻ qua `startupProbe` (`/ready`) cùng `livenessProbe` (`/health`).

---

## AI Usage Log (Theo quy định tại `RULES.md`)

1. **Tìm hiểu và tổng hợp kiến trúc 12-Factor & Docker Multi-stage (Part 1, Part 2, Part 5):**
   - **Đã hỏi AI:** Giải thích chi tiết cơ chế Docker Layer Caching, sự khác biệt giữa `CMD` và `ENTRYPOINT`, cũng như lý do vì sao Liveness probe (`GET /health`) không được trả về `503` khi mất kết nối Redis.
   - **Kết quả nhận được:** Giải thích lý thuyết về thứ tự invalidate layer trong Docker và nguy cơ cascading restart loop nếu `/health` phụ thuộc vào downstream service như Redis.
   - **Tự sửa & tự kiểm tra:** Trực tiếp đọc mã nguồn `01-localhost-vs-production/`, `02-docker/`, `04-api-gateway/`, `05-scaling-reliability/`, tự build hai image `my-agent:develop` (1.15 GB) và `my-agent:advanced` (163 MB), chạy container thật và ghi lại đúng kết quả `curl -i` vào báo cáo.
2. **Hoàn thiện mã nguồn Final Project trong `06-lab-complete/` (Part 6):**
   - **Đã hỏi AI:** Cách viết custom `logging.Formatter` xuất JSON hợp lệ cho mọi dòng log của ứng dụng mà không làm hỏng log khi thông điệp truyền vào đã là chuỗi JSON, cách cài đặt Sliding Window Rate Limiter bằng Redis Sorted Set (`ZREMRANGEBYSCORE`, `ZCARD`, `ZADD`, `EXPIRE`), và cách bắt tín hiệu `SIGTERM` mà không ghi đè mất signal handler mặc định của Uvicorn.
   - **Kết quả nhận được:** Mẫu code sử dụng `signal.getsignal(signal.SIGTERM)` lưu lại `_previous_sigterm` rồi gọi lại trong `_on_sigterm`, cùng cấu trúc multi-stage `Dockerfile` sử dụng `ENV PYTHONUSERBASE=/home/appuser/.local` cho user non-root `appuser`.
   - **Tự sửa & tự kiểm tra:** Hoàn thiện 12 file trong `06-lab-complete/`, tự kiểm tra bằng `python check_production_ready.py` và kiểm chứng từng endpoint `/health`, `/ready`, `/ask` (401, 200, 429, 402).
3. **Phân tích Tail Latency, Quality Gate và Observability Stack (Part 7):**
   - **Đã hỏi AI:** Cách định nghĩa Prometheus `Histogram` cho độ dài câu hỏi (`agent_question_length_chars`) tránh bùng nổ cardinality, và cách viết entry bổ sung cho `KNOWLEDGE_BASE` để khắc phục 2 câu sai (`scaling-03`, `security-02`) trong `golden_dataset.jsonl`.
   - **Kết quả nhận được:** Gợi ý các bucket `(20, 50, 100, 200, 500, 1000, 2000)` cho `Histogram` và 2 đoạn tài liệu về Kubernetes HPA cùng sự khác biệt giữa API Key và JWT.
   - **Tự sửa & tự kiểm tra:** Thêm metric vào `develop/app.py`, cập nhật `KNOWLEDGE_BASE` trong `utils/mock_llm.py`, trực tiếp chạy `load_test.py` (7 kịch bản) và `eval/run_eval.py` (3 kịch bản) để sinh toàn bộ 10 file JSON thật trong `reports/`, kiểm tra `eval_v2_fixed.json` đạt `100.0% (23/23)` không có regression và đối chiếu khớp 100% số liệu vào `BENCHMARK_REPORT.md`.
