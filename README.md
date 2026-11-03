# vLLM CPU Deployment on Kubernetes (Minikube)

Справочное решение для развертывания LLM (`Qwen/Qwen2.5-0.5B-Instruct`) на процессоре с использованием фреймворка vLLM в локальном кластере Kubernetes (Minikube).

## Выполненные требования
- **Инфраструктура:** Minikube, Kubernetes v1.37.0, деплой через `kustomize` (Бонус 1).
- **Модель:** `Qwen/Qwen2.5-0.5B-Instruct` (выбрана из-за аппаратных ограничений RAM в 16 ГБ).
- **Вычисления:** Строго CPU (vLLM собран из исходников с поддержкой инструкций AVX2).
- **Безопасность (Rootless):** Контейнеры запускаются от UID 1000, `readOnlyRootFilesystem: true`, `drop: ["ALL"]`, `allowPrivilegeEscalation: false`.
- **Воспроизводимость:** Python-зависимости жестко зафиксированы в `requirements.txt`.
- **Приватность (Кастомное логгирование):** Скрипт `sitecustomize.py` перехватывает логи vLLM и скрывает промпты/ответы, выводя только метаданные.
- **Кэширование (PVC):** Модель скачивается отдельным легковесным `initContainer` (Бонус 2) и сохраняется на `PersistentVolumeClaim`.
- **Управление конфигурацией:** Параметры vLLM вынесены в `ConfigMap`, токены (HF и API) — в `Secret`.
- **Нагрузочное тестирование (Бонус 3):** Проведено, метрики и аналитика приложены ниже.

## Инструкция по локальному запуску

### 1. Сборка Docker-образов
Сборка vLLM из исходников на CPU занимает **от 30 до 60 минут** (компилируется oneDNN и C++ ядра).

    make build

### 2. Запуск Minikube и загрузка образов
Для работы выделяем 4 ядра и 7 ГБ RAM (требуется для стабильности на хостах с 16 ГБ ОЗУ).

    minikube start --driver=docker --cpus=4 --memory=7000 --kubernetes-version=v1.37.0

    minikube image load ghcr.io/your-org/vllm-cpu:local
    minikube image load ghcr.io/your-org/vllm-downloader:0.1.0

### 3. Создание секретов
В секрете передается токен Hugging Face (для скачивания) и Bearer-токен (для защиты API).

    kubectl create namespace vllm --dry-run=client -o yaml | kubectl apply -f -

    kubectl -n vllm create secret generic vllm-secrets \
      --from-literal=HF_TOKEN='hf_dummy' \
      --from-literal=VLLM_API_KEY="$(openssl rand -hex 24)"

### 4. Деплой

    kubectl apply -k k8s/overlays/minikube
    kubectl -n vllm rollout status deploy/vllm --timeout=20m

### 5. Проверка работы
Пробрасываем порт и делаем тестовый запрос к API:

    kubectl -n vllm port-forward svc/vllm 8000:8000 &
    API_KEY=$(kubectl -n vllm get secret vllm-secrets -o jsonpath='{.data.VLLM_API_KEY}' | base64 -d)

    curl -s http://127.0.0.1:8000/v1/chat/completions \
      -H "Authorization: Bearer $API_KEY" \
      -H 'Content-Type: application/json' \
      -d '{"model":"qwen2.5-0.5b-instruct","messages":[{"role":"user","content":"Привет!"}],"max_tokens":50}' | jq

---

## Бонус 3: Нагрузочное тестирование

**Условия теста:** 2 выделенных ядра CPU (`VLLM_CPU_OMP_THREADS_BIND=0-1`), 4 параллельных запроса, генерация 50 токенов на запрос. Всего 16 запросов.

| Метрика | Значение |
|---|---|
| **Всего запросов / Конкурентность** | 16 / 4 |
| **TTFT p50** (Time To First Token) | 7.179 с |
| **TTFT p95** | 32.197 с |
| **Latency p50** (Полное время) | 26.292 с |
| **Latency p95** | 49.717 с |
| **Throughput (RPS)** | 0.126 req/s |
| **Throughput (Генерация)** | **32.95 токенов/с** |

### Аналитика: настройка vLLM для повышения Throughput

**А) Большой поток запросов с маленьким количеством токенов (High RPS):**
В этом сценарии узким местом становится оверхед на планирование (scheduling) и неэффективное использование батча.
- **`--max-num-seqs`**: Увеличить, чтобы держать больше запросов в батче одновременно.
- **`--enable-chunked-prefill`**: Включить, чтобы длинные промпты не блокировали генерацию коротких.
- **Уменьшить `--max-model-len`**: Если контекст не нужен большой, это освободит память под KV-кэш и позволит увеличить размер батча.

**Б) Мало запросов, но с огромным контекстом (Long context):**
Узкое место — время на prefill (обработку промпта) и размер KV-кэша.
- **Увеличить `--max-num-batched-tokens`**: Чтобы длинный промпт обрабатывался за меньшее число итераций (снижает TTFT).
- **Оставить `--enable-chunked-prefill`**: Чтобы не замораживать сервер на время обработки огромного текста.
- **Уменьшить `--max-num-seqs`**: В этом сценарии высокая конкурентность не нужна, важнее, чтобы последовательность влезла в память.
- **Использовать квантование** (`--quantization`): Для весов (AWQ или GPTQ), чтобы освободить память под KV-кэш для длинных контекстов.
