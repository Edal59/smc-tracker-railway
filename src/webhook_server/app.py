"""
SMC Performance Tracker — Flask Application Factory (Cloud)
Main webhook server + web dashboard.
"""
import logging
from flask import Flask
from flask_cors import CORS

from src.config import config

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__,
                template_folder='../../templates',
                static_folder='../../static')

    # CORS for API access
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Config
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024  # 8KB max payload
    app.config['JSON_SORT_KEYS'] = False
    app.config['SECRET_KEY'] = config.api_key or 'smc-tracker-secret'

    # Register API blueprint
    from src.webhook_server.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # Register web dashboard blueprint
    from src.dashboard_routes import dashboard_bp
    app.register_blueprint(dashboard_bp)

    # Error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return {'error': 'Bad request', 'message': str(e)}, 400

    @app.errorhandler(401)
    def unauthorized(e):
        return {'error': 'Unauthorized', 'message': 'Invalid or missing API key'}, 401

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found'}, 404

    @app.errorhandler(413)
    def payload_too_large(e):
        return {'error': 'Payload too large', 'message': 'Max 8KB'}, 413

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal server error: {e}", exc_info=True)
        return {'error': 'Internal server error'}, 500

    logger.info("Flask application created (cloud mode)")
    return app
