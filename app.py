#!/usr/bin/env python3
"""
SMC Performance Tracker — Cloud Entry Point
Railway / Heroku / Cloud deployment entry point.
"""
import os
import sys
import signal
import logging
from logging.handlers import RotatingFileHandler

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.config import config
from src.database import init_db
from src.webhook_server.app import create_app
from src.tracker.price_tracker import PriceTracker


def setup_logging():
    """Configure application logging."""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler (Railway captures stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    console_handler.setFormatter(console_fmt)
    root_logger.addHandler(console_handler)

    # Optional file handler
    try:
        log_file = config.log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=3
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(console_fmt)
        root_logger.addHandler(file_handler)
    except Exception:
        pass  # File logging optional in cloud

    logging.getLogger('werkzeug').setLevel(logging.WARNING)


# Setup
config.load()
setup_logging()
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("SMC Performance Tracker — Cloud Mode")
logger.info("=" * 60)

# Initialize database
db_path = init_db()
logger.info(f"Database ready: {db_path}")

# Create Flask app
app = create_app()

# Start price tracker (if enabled)
tracker = PriceTracker()
tracker.start()

# Graceful shutdown
def shutdown_handler(signum, frame):
    logger.info("Shutdown signal received...")
    tracker.stop()
    logger.info("Server stopped")
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

host = config.server_host
port = config.server_port

logger.info(f"Server configured on {host}:{port}")
logger.info(f"  Auth required: {config.require_auth}")
logger.info(f"  API Key set: {'Yes' if config.api_key else 'No (WARNING!)'}")
logger.info(f"  Price tracker: {'enabled' if config.price_tracker_enabled else 'disabled'}")
logger.info(f"  Endpoints:")
logger.info(f"    POST /api/v1/signal  (webhook)")
logger.info(f"    GET  /api/v1/health  (health check)")
logger.info(f"    GET  /api/v1/signals (list signals)")
logger.info(f"    GET  /           (dashboard)")

if __name__ == '__main__':
    app.run(host=host, port=port, debug=False)
