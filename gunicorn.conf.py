"""
gunicorn.conf.py
Gunicorn production configuration.
Workers: 2*CPU+1 (standard formula for I/O-bound Flask apps).
Timeout: 120s — accommodates OpenAI API calls (default 60s + buffer).
"""

import multiprocessing
import os

# ------------------------------------------------------------------ #
# Workers and threads
# ------------------------------------------------------------------ #
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
threads = int(os.environ.get("GUNICORN_THREADS", 2))
worker_class = "sync"

# ------------------------------------------------------------------ #
# Timeouts
# ------------------------------------------------------------------ #
# AI requests can take up to ~30s; voice transcription up to ~60s.
# 120s gives ample headroom while preventing runaway connections.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
graceful_timeout = 30
keepalive = 5

# ------------------------------------------------------------------ #
# Binding
# ------------------------------------------------------------------ #
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# ------------------------------------------------------------------ #
# Logging
# ------------------------------------------------------------------ #
accesslog = "-"   # stdout
errorlog = "-"    # stderr
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# ------------------------------------------------------------------ #
# Process naming
# ------------------------------------------------------------------ #
proc_name = "personal-ai-assistant"

# ------------------------------------------------------------------ #
# Security
# ------------------------------------------------------------------ #
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
