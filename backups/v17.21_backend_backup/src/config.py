"""
SMC Performance Tracker — Cloud Configuration
Uses environment variables for Railway deployment.
"""
import os
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    """Application configuration from environment variables."""
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self):
        self._loaded = True
        logger.info("Configuration loaded from environment variables")
        return self

    @property
    def server_host(self):
        return os.environ.get('HOST', '0.0.0.0')

    @property
    def server_port(self):
        return int(os.environ.get('PORT', 5000))

    @property
    def api_key(self):
        return os.environ.get('SMC_API_KEY', '')

    @property
    def require_auth(self):
        return os.environ.get('REQUIRE_AUTH', 'true').lower() in ('true', '1', 'yes')

    @property
    def db_path(self):
        return os.environ.get('DATABASE_PATH', os.path.join(PROJECT_ROOT, 'data', 'smc_tracker.db'))

    @property
    def price_tracker_enabled(self):
        return os.environ.get('PRICE_TRACKER_ENABLED', 'false').lower() in ('true', '1', 'yes')

    @property
    def price_poll_interval(self):
        return int(os.environ.get('PRICE_POLL_INTERVAL', 15))

    @property
    def timeout_bars(self):
        return int(os.environ.get('TIMEOUT_BARS', 200))

    @property
    def timeout_minutes(self):
        return int(os.environ.get('TIMEOUT_MINUTES', 4320))

    @property
    def log_level(self):
        return os.environ.get('LOG_LEVEL', 'INFO')

    @property
    def log_file(self):
        return os.environ.get('LOG_FILE', os.path.join(PROJECT_ROOT, 'logs', 'smc_tracker.log'))

    def get(self, *keys, default=None):
        """Compatibility method for nested config access."""
        # Map common paths to env vars
        key_path = '.'.join(keys)
        mapping = {
            'server.host': self.server_host,
            'server.port': self.server_port,
            'server.debug': os.environ.get('DEBUG', 'false').lower() in ('true', '1'),
            'auth.api_key': self.api_key,
            'auth.require_auth': self.require_auth,
            'database.path': self.db_path,
            'price_tracker.enabled': self.price_tracker_enabled,
            'price_tracker.provider': os.environ.get('PRICE_PROVIDER', 'mock'),
            'price_tracker.api_key': os.environ.get('PRICE_API_KEY', ''),
            'price_tracker.poll_interval_seconds': self.price_poll_interval,
            'price_tracker.timeout_bars': self.timeout_bars,
            'price_tracker.timeout_minutes': self.timeout_minutes,
            'logging.level': self.log_level,
            'logging.file': self.log_file,
        }
        return mapping.get(key_path, default)


# Global config instance
config = Config()
