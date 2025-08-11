# app/main.py
import os, json, asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from prometheus_fastapi_instrumentator import Instrumentator

# Optional shared logger
try:
    from arch_logging import init_logger
    _log = init_logger("service-api")
    def log_info(evt, **kw): _log.info(evt, **kw)
    def log_error(evt, **kw): _log.error(evt, **kw)
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _l = logging.getLogger("service-api")
    def log_info(evt, **kw): _l.info("%s %s", evt, kw)
    def log_error(evt, **kw): _l.error("%s %s", evt, kw)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC           = os.getenv("KAFKA_TOPIC", "hello.events")
REDIS_URL       = os.getenv("REDIS_URL", "redis://:redispass@redis:6379/0")
TESTING         = os.getenv("TESTING", "0") == "1"

class DummyProducer:
    async def start(self): pass
    async def stop(self): pass
    async def send_and_wait(self, *a, **k): return

class MiniRedis:
    def __init__(self): self._kv = {}
    def incr(self, k): self._kv[k] = int(self._kv.get(k, 0)) + 1; return self._kv[k]
    def ping(self): return True

def create_app(testing: bool = TESTING) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Initialize dependencies
        if testing:
            app.state.producer = DummyProducer()
            app.state.redis = MiniRedis()
            log_info("startup_complete", testing=True)
            yield
            return

        import redis
        from aiokafka import AIOKafkaProducer

        app.state.redis = redis.Redis.from_url(REDIS_URL)

        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, linger_ms=5)
        for attempt in range(1, 16):
            try:
                await producer.start()
                break
            except Exception as e:
                if attempt == 15:
                    log_error("kafka_start_failed", error=str(e))
                    raise
                await asyncio.sleep(1)
        app.state.producer = producer
        log_info("startup_complete", testing=False)
        try:
            yield
        finally:
            try:
                await producer.stop()
            except Exception:
                pass

    app = FastAPI(title="hello-arch-api", lifespan=lifespan)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    @app.get("/healthz")
    def healthz(request: Request):
        try:
            request.app.state.redis.ping()
            return {"status": "ok"}
        except Exception as e:
            log_error("redis_unhealthy", error=str(e))
            raise HTTPException(status_code=500, detail="redis unhealthy")

    @app.post("/hello")
    async def hello(payload: dict, request: Request):
        try:
            msg = json.dumps(payload).encode()
            await request.app.state.producer.send_and_wait(TOPIC, msg)
            request.app.state.redis.incr("hello_api_requests")
            log_info("event_produced", topic=TOPIC, bytes=len(msg))
            return {"ok": True}
        except Exception as e:
            log_error("produce_failed", error=str(e))
            raise HTTPException(status_code=500, detail="kafka produce failed")

    return app

# ASGI entrypoint
app = create_app()
