"""
Main application module for the RiskOptimizer API.
Initializes and configures the Flask application.
"""

import sys

from flasgger import Swagger
from flask import Flask, jsonify
from flask_cors import CORS
from src.api.controllers.auth_controller import auth_bp
from src.api.controllers.blockchain_controller import blockchain_bp
from src.api.controllers.monitoring_controller import monitoring_bp
from src.api.controllers.portfolio_controller import portfolio_bp
from src.api.controllers.risk_controller import risk_bp
from src.api.middleware.error_middleware import error_handling_middleware
from src.api.middleware.rate_limit_middleware import apply_rate_limiting
from src.core.config import config
from src.core.logging import configure_logging, get_logger
from src.infrastructure.cache.redis_cache import redis_cache
from src.infrastructure.database.session import check_db_connection, init_db
from src.utils.performance import apply_performance_monitoring

logger = get_logger(__name__)


def create_app() -> Flask:
    """
    Create and configure the Flask application.

    Returns:
        Configured Flask application
    """
    # Configure logging
    configure_logging()

    # Create Flask app
    app = Flask(__name__)

    # Configure app
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = config.api.max_content_length

    # Configure Swagger for API documentation
    app.config["SWAGGER"] = {
        "title": "RiskOptimizer API",
        "uiversion": 3,
        "version": "1.0.0",
        "description": "API for RiskOptimizer application, providing financial risk analysis and portfolio management.",
    }
    Swagger(app)

    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": config.api.cors_origins}})

    # Register error handling middleware
    error_handling_middleware(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(risk_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(blockchain_bp)

    # Apply rate limiting to API endpoints
    apply_rate_limiting(app)

    # Apply performance monitoring
    apply_performance_monitoring(app)

    # Add health check endpoint
    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint.
        ---
        responses:
            200:
                description: API is healthy
                schema:
                    type: object
                    properties:
                        status:
                            type: string
                            enum: [ok, degraded]
                        version:
                            type: string
                        database:
                            type: boolean
                        cache:
                            type: boolean
            503:
                description: API is degraded (e.g., database or cache connection issues)
        """
        health = {
            "status": "ok",
            "version": "1.0.0",
            "database": check_db_connection(),
            "cache": redis_cache.health_check(),
        }

        # Set overall status
        if not health["database"] or not health["cache"]:
            health["status"] = "degraded"

        status_code = 200 if health["status"] == "ok" else 503
        return jsonify(health), status_code

    # Add API documentation redirect
    @app.route("/", methods=["GET"])
    def index():
        """
        Redirect to API documentation.
        ---
        responses:
            200:
                description: Redirects to Swagger UI documentation
        """
        return jsonify(
            {
                "name": "RiskOptimizer API",
                "version": "1.0.0",
                "documentation": "/apidocs/",
            }
        )

    return app


def init_app() -> Flask:
    """
    Initialize the application.

    Returns:
        Initialized Flask application
    """
    try:
        # Create app
        app = create_app()

        # Initialize database
        init_db()

        # Check Redis connection
        redis_cache.health_check()

        logger.info(
            f"Application initialized successfully in {config.environment} environment"
        )
        return app
    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        sys.exit(1)


# Create application instance
app = init_app()


if __name__ == "__main__":
    # Run application
    app.run(host=config.api.host, port=config.api.port, debug=config.api.debug)
