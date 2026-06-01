from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)


class CaseGraph:
    """Thin sync wrapper around the Neo4j driver for case knowledge graph queries."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        try:
            from neo4j import GraphDatabase  # type: ignore[import]
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            logger.info("case_graph connected", extra={"service": "backend", "uri": uri})
        except Exception as exc:
            logger.warning("case_graph init failed", extra={"service": "backend", "reason": type(exc).__name__})
            self._driver = None  # type: ignore[assignment]

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return self._driver is not None

    @contextmanager
    def _session(self) -> Generator[Any, None, None]:
        with self._driver.session() as session:  # type: ignore[union-attr]
            yield session

    def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Execute a read Cypher query and return list of record dicts."""
        if not self.available:
            return []
        try:
            with self._session() as session:
                result = session.run(cypher, **params)
                return [record.data() for record in result]
        except Exception as exc:
            logger.warning(
                "case_graph query failed",
                extra={"service": "backend", "reason": type(exc).__name__},
            )
            return []

    def run_write(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Execute a write Cypher query inside an explicit write transaction."""
        if not self.available:
            return []
        try:
            with self._session() as session:
                result = session.run(cypher, **params)
                return [record.data() for record in result]
        except Exception as exc:
            logger.warning(
                "case_graph write failed",
                extra={"service": "backend", "reason": type(exc).__name__},
            )
            return []
