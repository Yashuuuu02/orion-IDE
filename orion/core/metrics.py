from prometheus_client import Counter, Histogram, Gauge

pipeline_execution_seconds = Histogram(
    "pipeline_execution_seconds",
    "End-to-end pipeline run duration",
    buckets=[5, 10, 20, 30, 45, 60, 90, 120]
)

component_execution_seconds = Histogram(
    "component_execution_seconds",
    "Per-component execution duration",
    ["component_id"]
)

agent_token_usage_total = Counter(
    "agent_token_usage_total",
    "Total LLM tokens used by agents",
    ["agent_role", "provider"]
)

validation_failures_total = Counter(
    "validation_failures_total",
    "Total validation layer failures",
    ["layer"]
)

checkpoint_size_bytes = Gauge(
    "checkpoint_size_bytes",
    "Size of latest checkpoint snapshot in bytes"
)

llm_api_errors_total = Counter(
    "llm_api_errors_total",
    "Total LLM API errors",
    ["provider", "error_type"]
)
