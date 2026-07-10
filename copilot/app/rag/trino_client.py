"""
AION Copilot — Trino SQL Executor
====================================
Executes generated SQL against Trino and returns results.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from trino.dbapi import connect
from trino.auth import BasicAuthentication

from app.core.config import settings

logger = logging.getLogger("aion-copilot.trino")


class TrinoExecutor:
    """Execute SQL against Trino and return structured results."""

    def __init__(self):
        self._connection = None

    def _get_connection(self):
        if self._connection is None:
            self._connection = connect(
                host=settings.trino_host,
                port=settings.trino_port,
                user=settings.trino_user,
                source=settings.trino_source,
                catalog=settings.trino_catalog,
                schema=settings.trino_schema,
            )
        return self._connection

    async def execute(
        self,
        sql: str,
        max_rows: int = 50,
        params: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query against Trino and return results as list of dicts.

        Args:
            sql: SQL query to execute
            max_rows: Maximum rows to return
            params: Optional query parameters

        Returns:
            List of row dicts with column names as keys
        """
        import asyncio

        logger.info("Executing SQL against Trino: %.200s", sql)

        def _execute_sync():
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)

            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Fetch results
            rows = []
            for row in cursor.fetchmany(max_rows + 1):
                if len(rows) >= max_rows:
                    break
                rows.append(dict(zip(columns, row)))

            return rows

        # Run synchronous Trino client in thread pool
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _execute_sync)

        logger.info("Trino returned %d rows", len(results))
        return results

    async def execute_with_metadata(
        self,
        sql: str,
        max_rows: int = 50,
    ) -> Tuple[List[Dict], Dict]:
        """Execute SQL and return results + metadata (row count, column types)."""
        import asyncio

        def _execute_sync():
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)

            columns = [desc[0] for desc in cursor.description]
            column_types = [desc[1] for desc in cursor.description]

            rows = []
            for row in cursor.fetchmany(max_rows + 1):
                if len(rows) >= max_rows:
                    break
                rows.append(dict(zip(columns, row)))

            metadata = {
                "columns": columns,
                "column_types": column_types,
                "row_count": len(rows),
                "truncated": len(rows) >= max_rows,
            }
            return rows, metadata

        loop = asyncio.get_event_loop()
        results, metadata = await loop.run_in_executor(None, _execute_sync)

        return results, metadata

    async def validate_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SQL without executing (EXPLAIN).
        Returns (is_valid, error_message).
        """
        import asyncio

        def _validate_sync():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(f"EXPLAIN {sql}")
                return True, None
            except Exception as e:
                return False, str(e)

        loop = asyncio.get_event_loop()
        is_valid, error = await loop.run_in_executor(None, _validate_sync)
        return is_valid, error

    async def get_table_schema(self, table_name: str) -> Dict:
        """Retrieve table schema from Trino for context enrichment."""
        import asyncio

        def _schema_sync():
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(f"DESCRIBE {settings.trino_catalog}.{settings.trino_schema}.{table_name}")

            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "name": row[0],
                    "type": row[1],
                    "comment": row[2] if len(row) > 2 else None,
                })
            return {"table": table_name, "columns": columns}

        loop = asyncio.get_event_loop()
        schema = await loop.run_in_executor(None, _schema_sync)
        return schema

    async def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None
