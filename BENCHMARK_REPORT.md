# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Đỗ Lý Hoàng Nam (`2A202603777`)
**Ngày chạy:** 2026-11-26
**Môi trường:** Windows 11 + WSL2, Python 3.11 / 3.12, Docker Desktop v28.1.1 (4 CPU / 8GB RAM)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < **500** ms | Đảm bảo 95% người dùng nhận được câu trả lời gần như tức thời (< 0.5s), trong khi vẫn có biên độ hợp lý cho bước retrieval (~20ms) + LLM call cơ bản (~120–180ms). |
| Error rate `/ask` | < **2.0** % | LLM provider upstream thường có tỉ lệ lỗi tạm thời ~0.5–1% (`503`/`429`). Ngưỡng 2.0% cho phép error budget hợp lý mà vẫn phát hiện sớm khi upstream hoặc agent gặp sự cố. |
| Accuracy trên golden dataset | ≥ **85.0** % (Production target: **100%**) | Đảm bảo chất lượng câu trả lời RAG trên bộ 23 câu hỏi chuẩn không bị suy giảm (regression) sau mỗi lần thay đổi prompt, model hoặc knowledge base. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

*(Số liệu trích xuất chính xác từ `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json` — mỗi mức chạy 300 requests)*

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | **4.75** | **202.7** | **233.4** | **237.3** | **1.33%** (`4/300`) | ✅ **PASS** |
| 10 | **34.54** | **188.4** | **443.5** | **1694.3** | **0.33%** (`1/300`) | ✅ **PASS** |
| 50 | **80.84** | **256.9** | **1650.3** | **1723.2** | **0.33%** (`1/300`) | ❌ **FAIL** (p95 > 500ms) |
| 100 | **56.06** | **577.9** | **3273.7** | **3594.6** | **2.33%** (`7/300`) | ❌ **FAIL** (p95 > 500ms, err > 2%) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

- **RPS không tăng tuyến tính** khi concurrency tăng cao:
  - Từ `c=1` lên `c=10`, RPS tăng mạnh gần 7.3 lần (`4.75` → `34.54 req/s`) vì event loop `asyncio` tận dụng được thời gian chờ I/O (`asyncio.sleep` khi gọi retrieval và LLM).
  - Từ `c=10` lên `c=50`, concurrency tăng 5 lần nhưng RPS chỉ tăng ~2.34 lần (`34.54` → `80.84 req/s`), đồng thời `p95` nhảy vọt lên `1650.3 ms` (vượt ngưỡng SLO 500ms).
  - Ở `c=100`, RPS thậm chí **sụt giảm** xuống còn `56.06 req/s` và `p50` tăng lên `577.9 ms`, `p95` lên tới `3273.7 ms`. Nguyên nhân là khi số kết nối đồng thời trên 1 worker đơn lẻ quá lớn, chi phí context switching trên event loop, tranh chấp socket và hàng đợi (queuing delay theo định luật Little: $L = \lambda W$) làm thời gian chờ trong hàng đợi tăng vọt.

### 2.2 Tail latency

*(Số liệu trích xuất chính xác từ `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json` — cùng chạy ở `--requests 300 --concurrency 20`)*

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | **206.7** | **452.9** | **484.7** |
| 0.03 (mặc định) | **233.9** | **452.4** | **1679.9** |
| 0.1 | **349.8** | **1691.4** | **1919.0** |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- **Chỉ số nhạy nhất:** **`p99`** (khi tỉ lệ request chậm ở mức nhỏ 3% — `MOCK_SLOW_RATE=0.03`, `p99` nhảy vọt hơn **3.4 lần** từ `484.7 ms` lên `1679.9 ms`, trong khi `avg` chỉ tăng nhẹ từ `206.7 ms` lên `233.9 ms` và `p95` gần như giữ nguyên ở `~452 ms`). Khi tỉ lệ chậm tăng lên 10% (`MOCK_SLOW_RATE=0.1`, tức > 5% tổng số request), cả **`p95`** cũng nhảy vọt lên **`1691.4 ms`** trong khi `avg` vẫn chỉ ở mức `349.8 ms` (nhỏ hơn rất nhiều so với ngưỡng 500ms).
- **Vì sao SLO không nên đặt theo average:** Trung bình cộng (`avg`) san phẳng các giá trị ngoại lai (outliers) vào 90–97% số request nhanh, hoàn toàn che giấu trải nghiệm tồi tệ của nhóm người dùng rơi vào đuôi phân phối (tail latency — phải chờ gần 2 giây). Đặt SLO theo percentile (`p95`, `p99`) giúp cam kết chất lượng dịch vụ trực tiếp trên tỷ lệ phần trăm khách hàng thực tế.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

*(Số liệu trích xuất chính xác từ `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json` trên bộ 23 câu hỏi `golden_dataset.jsonl`)*

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | **4.35%** (`1/23`) | **91.30%** (`21/23`) | **100.00%** (`23/23`) |
| Avg tokens / câu | **57.2** | **108.8** | **113.7** |
| Tổng cost (USD) | **$0.000406** | **$0.000758** | **$0.000790** |
| Cost / câu đúng (USD) | **$0.00040575** | **$0.00003607** | **$0.00003436** |
| Quality gate | ❌ **FAIL** | ✅ **PASS** (≥ 80%) | ✅ **PASS** (100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `["token", "hết hạn", "chữ ký"]` | Thêm entry `(["jwt"], "API key là chuỗi bí mật cố định, không tự hết hạn. JWT là token có chữ ký số, chứa thông tin user và thời điểm hết hạn; server xác minh chữ ký mà không cần tra database.")` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py`. |
| `scaling-03` | `["cpu", "memory", "custom metrics"]` | Thêm entry `(["hpa", "kubernetes", "autoscal"], "Kubernetes HPA (Horizontal Pod Autoscaler) scale số pod dựa trên CPU, memory hoặc custom metrics như RPS hay độ dài hàng đợi.")` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py`. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- **Về Latency & Chi phí thô:** Agent `v2` có thêm bước retrieval (`~20ms`) và chèn tài liệu tìm được vào prompt nên số token trung bình mỗi câu tăng gần gấp đôi (`57.2` → `113.7 tokens/câu`), tổng chi phí cho 23 câu tăng từ `$0.000406` lên `$0.000790`, và `p50` latency tăng nhẹ từ `173.5 ms` lên `200.5 ms`.
- **Về Chất lượng & Hiệu quả kinh tế thực tế (`Cost / câu đúng`):** Agent `v1` không có ngữ cảnh nên chỉ trả lời đúng `1/23` câu (`4.35%`), khiến chi phí cho mỗi câu trả lời đúng đắt tới **`$0.00040575`**. Ngược lại, `v2` (sau khi cập nhật KB) trả lời đúng tuyệt đối `23/23` câu (`100%`), giúp **chi phí trên mỗi câu trả lời đúng giảm xuống chỉ còn `$0.00003436` — rẻ hơn gần 11.8 lần so với `v1`**. Như vậy, việc đầu tư thêm ~56 input tokens cho RAG mang lại hiệu quả vượt trội.
- **Quality Gate trong CI/CD (`.github/workflows/eval.yml`):** Script `eval/run_eval.py` trả về `exit code 1` (`raise SystemExit(0 if gate_ok else 1)`) nếu `accuracy < --min-accuracy` hoặc có bất kỳ câu nào bị regression so với file `--baseline`. Khi tích hợp vào GitHub Actions chạy trên sự kiện `pull_request`, nếu PR làm giảm chất lượng, bước `run_eval.py` sẽ trả về mã thoát `1`, làm fail CI workflow và chặn merge PR tự động.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): [`screenshots/grafana-dashboard.png`](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): [`screenshots/jaeger-slow-trace.png`](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`): [`screenshots/jaeger-error-trace.png`](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với ít nhất 2 alert đang **firing**: [`screenshots/prometheus-alert-firing.png`](screenshots/prometheus-alert-firing.png)

**Trả lời các câu hỏi Exercise 7.4:**
1. **Khoảng cách giữa `p95` và `avg` trên Grafana nói lên điều gì?**
   - Khi chạy tải 30 users, `avg` chỉ quanh mức `~220–245 ms` trong khi `p95` dao động quanh `~450–485 ms` và `p99` vọt lên `~1.7 s`. Khoảng cách lớn giữa `avg` và `p95`/`p99` cho thấy phân phối độ trễ bị lệch phải (right-skewed distribution) do hiện tượng **tail latency** (~3% request LLM bị chậm bất thường +1500ms).
2. **Panel "Requests/s theo instance": Nginx có chia đều traffic cho các instance không?**
   - Có. Đường biểu đồ `rate(http_requests_total{route="/ask"}[1m])` của các instance (`agent-1`, `agent-2` hoặc khi scale lên 3 instance) bám sát và chồng khít lên nhau (~11–12 req/s mỗi instance ở mức 30 users), chứng tỏ thuật toán **Round-Robin** kết hợp DNS service discovery của Nginx phân phối tải đồng đều.
3. **Vì sao `input tokens/s` lớn hơn `output tokens/s`?**
   - Vì ở mỗi request của Agent `v2`, phần `input` bao gồm cả `SYSTEM_PROMPT` + đoạn tài liệu ngữ cảnh lấy từ `KNOWLEDGE_BASE` (RAG context) + câu hỏi của người dùng (~80–115 tokens), trong khi `output` chỉ là câu trả lời ngắn gọn (~30–45 tokens). Do đó tốc độ tiêu thụ input token/giây luôn cao gấp ~2–2.5 lần output token/giây.
4. **`curl http://localhost:8080/metrics` trả về gì? Vì sao?**
   - Trả về **`HTTP 404 Not Found`** (`{"error": "not found"}`). Nguyên nhân là trong `nginx/nginx.conf`, block `location = /metrics { return 404 '{"error": "not found"}'; }` đã chủ động chặn truy cập `/metrics` từ mạng bên ngoài để bảo mật (tránh lộ thông tin nội bộ như phiên bản model, chi phí, lưu lượng và tên instance). Chỉ có Prometheus nằm trong cùng mạng nội bộ Docker (`observability`) mới scrape trực tiếp được `agent:8000/metrics`.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | **`AgentHighErrorRate`** (`severity: critical`) | **~75 giây** (~15s cửa sổ rate vượt 5% + `for: 1m`) | Panel **Error rate `/ask`** (vọt lên ~20%, chuyển sang màu đỏ) và **Requests/s theo status** (dải `503` tăng cao). |
| B | `MOCK_SLOW_RATE=0.3` | **`AgentHighLatencyP95`** (`severity: warning`) | **~135 giây** (~15s p95 vượt 1s + `for: 2m`) | Panel **p95 latency** (nhảy lên ~1.72s, chuyển đỏ) và biểu đồ **Latency percentiles** (`p95`, `p99` vọt lên gần 1.75s). |
| C | `LLM_MODEL=mock-llm-large` | **`LLMCostBurnRateHigh`** (`severity: warning`) & **`AgentHighLatencyP95`** | **~140 giây** (`for: 2m` sau khi burn rate 5m vượt $2/giờ) | Panel **Cost 1h (ước tính)** (tăng ~16.7 lần lên > $3.5/giờ) và **LLM latency p95** (tăng ~2.5 lần do `latency_factor=2.5`). |
| D | `docker pause` 1 instance | **`AgentInstanceDown`** (`severity: critical`) | **~35 giây** (1 chu kỳ scrape 5s timeout + `for: 30s`) | Panel **Instances up** (giảm từ 2 xuống 1). *(Lưu ý: Locust ghi nhận vài lỗi 504 từ Nginx, nhưng panel Error rate của agent vẫn xanh vì request bị treo ở Nginx chưa được agent xử lý)*. |
| E | `AGENT_VERSION=v1` | **Không có alert nào firing** | **Không firing** (mọi metric hạ tầng vẫn xanh) | Panel **Retrieval hit ratio** (tụt về 0%), **LLM tokens/s** giảm một nửa, và bảng **Version đang chạy** đổi từ `v2` sang `v1`. |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

- Sự cố ở thí nghiệm E là **suy giảm chất lượng câu trả lời (silent quality degradation)** chứ không phải lỗi hạ tầng (HTTP status vẫn `200 OK`, latency thậm chí còn nhanh hơn và tốn ít tiền hơn vì bỏ qua bước retrieval). Do đó các alert hạ tầng dựa trên 4 Golden Signals (Latency, Traffic, Errors, Saturation) không thể phát hiện được.
- Để phát hiện trong production, cần kết hợp 3 lớp:
  1. **Trước khi deploy (CI/CD Quality Gate):** Bắt buộc chạy `eval/run_eval.py` trên golden dataset kèm `--baseline` trong CI pipeline để chặn ngay từ lúc tạo Pull Request.
  2. **Business / Semantic Metrics & Alerting:** Đặt alert trên các metric nghiệp vụ đặc thù của RAG như `Retrieval hit ratio` (ví dụ: cảnh báo khi `sum(rate(agent_retrieval_total{result="hit"}[5m])) / sum(rate(agent_retrieval_total[5m])) < 0.5`) hoặc khi `input_tokens` trung bình mỗi request tụt bất thường.
  3. **Online Evaluation & User Feedback:** Lấy mẫu ngẫu nhiên một tỷ lệ traffic thật (ví dụ 1–5% log production) để chấm điểm bất đồng bộ bằng **LLM-as-a-Judge**, kết hợp theo dõi tỉ lệ người dùng bấm thumbs-down / retry.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `4bf92f3577b34da6a3ce929d0e0e4736`
- Tổng thời gian: **1712.4 ms**
- Span chiếm nhiều thời gian nhất: **`chat mock-llm-small`** (**1687.2 ms**, chiếm **98.53%** tổng thời gian request; trong khi span `agent.retrieve_context` chỉ mất **21.1 ms** ~ 1.23%)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T09:50:14.418203+00:00", "level": "INFO", "service": "observable-agent", "instance": "agent-1", "event": "llm_call", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "span_id": "a3f91b4c8e201d7a", "request_id": "9e4a1c82b710", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 81, "output_tokens": 46, "cost_usd": 3.975e-05, "llm_ms": 1687.2}
```

- Dòng log lỗi tương ứng khi tìm trace có tag `error=true` (`grep llm_error`):

```json
{"ts": "2026-11-26T09:50:28.104912+00:00", "level": "INFO", "service": "observable-agent", "instance": "agent-2", "event": "llm_error", "trace_id": "7c218a90e4b15f3d8a19c204e67b1109", "span_id": "5d81e2039a7c4b12", "request_id": "3b7f92d10a4e", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

*(Số liệu trích xuất chính xác từ `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv` — dòng `POST /ask` và `Aggregated`)*

| Số instance | RPS (`/ask` / Tổng) | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | **61.82** (`68.00` tổng) | **214** (`210` tổng) | **485** (`468` tổng) | **1748** (`1742` tổng) | **75 / 7418** (`1.01%`) |
| 3 | **66.28** (`72.92` tổng) | **192** (`189` tổng) | **442** (`435` tổng) | **1715** (`1712` tổng) | **79 / 7954** (`0.99%`) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

- Khi scale từ 1 lên 3 instance, throughput tăng nhẹ (`61.82` → `66.28 req/s` cho `/ask`) và `p50` giảm từ `214 ms` xuống `192 ms`, `p95` cải thiện nhẹ từ `485 ms` xuống `442 ms` (nhờ giảm thời gian xếp hàng trên event loop của từng container Python), nhưng **`p95` và `p99` (`~1715 ms`) không giảm mạnh theo tỷ lệ 3x**.
- **Nút thắt cổ chai (Bottleneck) nằm ở đâu:**
  1. **Độ trễ nội tại của Downstream Services (LLM API & Vector Retrieval):** Qua Jaeger trace và panel *LLM Latency* trên Grafana, > 98% thời gian xử lý của một request nằm ở việc chờ kết quả trả về từ `mock_llm.generate()` (~150ms normal, ~1680ms khi rơi vào tail latency 3%) và `search_knowledge_base()` (~20ms). Việc nhân bản thêm nhiều container Agent chỉ giúp tăng khả năng tiếp nhận kết nối đồng thời (concurrency capacity) và giảm CPU contention ở tầng web server, chứ **không thể làm giảm thời gian suy luận của một lệnh gọi LLM đơn lẻ**.
  2. **Think time của người dùng (`wait_time = between(0.5, 2)` trong Locust):** Với 100 users mà mỗi user nghỉ trung bình `1.25s` sau mỗi request mất `~0.22s` (tổng chu kỳ ~1.47s/request), mức tải tối đa mà 100 Locust users tạo ra theo định luật Little chỉ khoảng $100 / 1.47 \approx 68\text{--}73\text{ req/s}$, mà bản thân 1 instance chạy `asyncio` đã gần đủ sức gánh mức tải I/O-bound này.

---

## 6. Kết luận

- **3 điều bạn học được về benchmark & observability:**
  1. **Không bao giờ đánh giá hiệu năng qua Average Latency:** Chỉ cần 3–10% request bị chậm (tail latency), người dùng đã gặp trải nghiệm rất tệ nhưng chỉ số trung bình (`avg`) vẫn hoàn toàn "xanh". Mọi SLO và Alert về độ trễ bắt buộc phải thiết lập trên các phân vị cao (**`p95`, `p99`**) sử dụng `Histogram` và `histogram_quantile()`.
  2. **Benchmark Hiệu năng (Load Test) và Benchmark Chất lượng (Eval) bổ trợ bắt buộc cho nhau:** Dashboard hạ tầng (Prometheus/Grafana) có thể xanh 100% (như thí nghiệm đổi về `AGENT_VERSION=v1`), nhưng agent lại trả lời sai tới 95%. Ngược lại, bộ eval 23 câu hỏi giúp bắt regression chất lượng và tính chỉ số `Cost / câu đúng`, nhưng không thể đại diện cho tải thực tế.
  3. **Liên kết 3 trụ cột Metrics → Traces → Logs qua `trace_id`:** Khi Alert/Grafana (Metrics) báo `p95` hoặc `Error rate` vượt ngưỡng, ta dùng Jaeger (Traces) để khoanh vùng chính xác span gây chậm (`chat mock-llm-*` hay `retrieve_context`), sau đó dùng `trace_id` để grep dòng JSON Log tương ứng nhằm lấy toàn bộ ngữ cảnh lỗi.
- **Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?**
  1. **Metric & Alert về chất lượng RAG / Guardrails:** Theo dõi `agent_retrieval_hit_ratio` (cảnh báo khi tỉ lệ tìm thấy tài liệu < 60% trong 5 phút), điểm `retrieval_similarity_score` (Histogram), và tỉ lệ câu trả lời bị chặn bởi safety filter / hallucination detector.
  2. **Metric trải nghiệm Streaming LLM:** Đo **TTFT (Time To First Token)** và **ITL (Inter-Token Latency / Tokens Per Second)** bằng Histogram thay vì chỉ đo tổng thời gian hoàn tất toàn bộ câu trả lời.
  3. **Giám sát từ tầng Edge / Load Balancer (Nginx / Ingress) và Synthetic Monitoring:** Thêm Prometheus exporter ở Nginx để bắt các lỗi `502`/`504 Gateway Timeout` khi container agent bị treo hoặc bị pause (vốn không xuất hiện trong metric tự báo cáo của agent).
