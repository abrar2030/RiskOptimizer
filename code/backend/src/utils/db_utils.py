"""
Database optimization utilities for improved query performance.
Provides utilities for query optimization, connection pooling, and database monitoring.
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool
from src.infrastructure.database.session import get_db_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class QueryPerformanceMonitor:
    """Monitor and log slow database queries."""

    def __init__(self, slow_query_threshold: float = 1.0) -> None:
        """Initialize query performance monitor."""
        self.slow_query_threshold = slow_query_threshold
        self.query_stats: Dict[int, Dict[str, Any]] = {}

    def log_slow_query(
        self, query: str, duration: float, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log slow queries for analysis.

        Args:
            query: SQL query string
            duration: Query execution time in seconds
            params: Query parameters
        """
        if duration >= self.slow_query_threshold:
            logger.warning(
                f"Slow query detected: {duration:.3f}s",
                extra={
                    "query": query,
                    "duration": duration,
                    "params": params,
                    "threshold": self.slow_query_threshold,
                },
            )
            query_hash = hash(query)
            if query_hash not in self.query_stats:
                self.query_stats[query_hash] = {
                    "query": query,
                    "count": 0,
                    "total_time": 0,
                    "max_time": 0,
                    "min_time": float("inf"),
                }
            stats = self.query_stats[query_hash]
            stats["count"] += 1
            stats["total_time"] += duration
            stats["max_time"] = max(stats["max_time"], duration)
            stats["min_time"] = min(stats["min_time"], duration)

    def get_query_stats(self) -> List[Dict[str, Any]]:
        """
        Get query performance statistics.

        Returns:
            List of query statistics
        """
        stats_list = []
        for stats in self.query_stats.values():
            avg_time = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
            stats_list.append(
                {
                    "query": (
                        stats["query"][:100] + "..."
                        if len(stats["query"]) > 100
                        else stats["query"]
                    ),
                    "count": stats["count"],
                    "avg_time": avg_time,
                    "max_time": stats["max_time"],
                    "min_time": stats["min_time"],
                    "total_time": stats["total_time"],
                }
            )
        stats_list.sort(key=lambda x: x["total_time"], reverse=True)
        return stats_list


query_monitor = QueryPerformanceMonitor()


@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(
    conn: object,
    cursor: object,
    statement: object,
    parameters: object,
    context: object,
    executemany: bool,
) -> object:
    """Record query start time."""
    context._query_start_time = time.time()


@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(
    conn: object,
    cursor: object,
    statement: object,
    parameters: object,
    context: object,
    executemany: bool,
) -> object:
    """Log query execution time."""
    if hasattr(context, "_query_start_time"):
        duration = time.time() - context._query_start_time
        query_monitor.log_slow_query(statement, duration, parameters)


class DatabaseOptimizer:
    """Database optimization utilities."""

    @staticmethod
    def analyze_table_stats(session: Session, table_name: str) -> Dict[str, Any]:
        """
        Analyze table statistics for optimization.

        Args:
            session: Database session
            table_name: Name of the table to analyze

        Returns:
            Dictionary with table statistics
        """
        try:
            count_query = text(f"SELECT COUNT(*) FROM {table_name}")
            row_count = session.execute(count_query).scalar()
            size_query = text(
                f"SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))"
            )
            table_size = session.execute(size_query).scalar()
            index_query = text(
                "\n                SELECT indexname, indexdef\n                FROM pg_indexes\n                WHERE tablename = :table_name\n            "
            )
            indexes = session.execute(
                index_query, {"table_name": table_name}
            ).fetchall()
            return {
                "table_name": table_name,
                "row_count": row_count,
                "table_size": table_size,
                "indexes": [{"name": idx[0], "definition": idx[1]} for idx in indexes],
            }
        except Exception as e:
            logger.error(f"Error analyzing table {table_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def suggest_indexes(session: Session, table_name: str) -> List[str]:
        """
        Suggest indexes for a table based on query patterns.

        Args:
            session: Database session
            table_name: Name of the table

        Returns:
            List of suggested index creation statements
        """
        suggestions = []
        try:
            if table_name == "portfolios":
                suggestions.extend(
                    [
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_user_id ON {table_name} (user_id);",
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_user_address ON {table_name} (user_address);",
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON {table_name} (created_at);",
                    ]
                )
            elif table_name == "portfolio_allocations":
                suggestions.extend(
                    [
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_portfolio_id ON {table_name} (portfolio_id);",
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_asset_symbol ON {table_name} (asset_symbol);",
                    ]
                )
            elif table_name == "users":
                suggestions.extend(
                    [
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_email ON {table_name} (email);",
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_username ON {table_name} (username);",
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_wallet_address ON {table_name} (wallet_address);",
                    ]
                )
        except Exception as e:
            logger.error(
                f"Error suggesting indexes for {table_name}: {str(e)}", exc_info=True
            )
        return suggestions

    @staticmethod
    def create_indexes(session: Session, table_name: str) -> Dict[str, Any]:
        """
        Create suggested indexes for a table.

        Args:
            session: Database session
            table_name: Name of the table

        Returns:
            Dictionary with creation results
        """
        suggestions = DatabaseOptimizer.suggest_indexes(session, table_name)
        results: Dict[str, List[Any]] = {"created": [], "failed": []}
        for index_sql in suggestions:
            try:
                session.execute(text(index_sql))
                session.commit()
                results["created"].append(index_sql)
                logger.info(f"Created index: {index_sql}")
            except Exception as e:
                session.rollback()
                results["failed"].append({"sql": index_sql, "error": str(e)})
                logger.error(f"Failed to create index: {index_sql}, Error: {str(e)}")
        return results


@contextmanager
def optimized_session(read_only: bool = False) -> Generator[Session, None, None]:
    """
    Context manager for optimized database sessions.

    Args:
        read_only: Whether the session is read-only

    Yields:
        Optimized database session
    """
    with get_db_session() as session:
        try:
            if read_only:
                session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED READ ONLY")
                )
            yield session
        except Exception as e:
            logger.error(f"Error in optimized session: {str(e)}", exc_info=True)
            raise


class ConnectionPoolMonitor:
    """Monitor database connection pool performance."""

    @staticmethod
    def get_pool_stats(engine: Engine) -> Dict[str, Any]:
        """
        Get connection pool statistics.

        Args:
            engine: SQLAlchemy engine

        Returns:
            Dictionary with pool statistics
        """
        try:
            pool = engine.pool
            if isinstance(pool, QueuePool):
                return {
                    "pool_type": "QueuePool",
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                }
            else:
                return {
                    "pool_type": type(pool).__name__,
                    "size": getattr(pool, "size", lambda: "N/A")(),
                    "checked_in": getattr(pool, "checkedin", lambda: "N/A")(),
                    "checked_out": getattr(pool, "checkedout", lambda: "N/A")(),
                }
        except Exception as e:
            logger.error(f"Error getting pool stats: {str(e)}", exc_info=True)
            return {"error": str(e)}


def optimize_database_performance() -> Dict[str, Any]:
    """
    Run database performance optimization.

    Returns:
        Dictionary with optimization results
    """
    results: Dict[str, List[Any]] = {
        "tables_analyzed": [],
        "indexes_created": [],
        "errors": [],
    }
    try:
        with get_db_session() as session:
            tables = ["users", "portfolios", "portfolio_allocations"]
            for table in tables:
                try:
                    stats = DatabaseOptimizer.analyze_table_stats(session, table)
                    results["tables_analyzed"].append(stats)
                    index_results = DatabaseOptimizer.create_indexes(session, table)
                    results["indexes_created"].extend(index_results["created"])
                    if index_results["failed"]:
                        results["errors"].extend(index_results["failed"])
                except Exception as e:
                    error_msg = f"Error optimizing table {table}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Error in database optimization: {str(e)}"
        logger.error(error_msg, exc_info=True)
        results["errors"].append(error_msg)
    return results
