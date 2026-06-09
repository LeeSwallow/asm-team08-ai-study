from __future__ import annotations

import logging
from functools import lru_cache

from app.ai_engine.retrieval.knowledge_retriever import KnowledgeRetriever
from app.core.config import get_settings
from app.infra.case_graph import CaseGraph
from app.infra.neo4j_knowledge_repository import Neo4jKnowledgeGraphRepository

logger = logging.getLogger(__name__)


@lru_cache
def get_knowledge_retriever() -> KnowledgeRetriever:
    settings = get_settings()
    if not settings.neo4j_uri:
        logger.info("BE_NEO4J_URI not set; knowledge_retriever in no-op mode")
        return KnowledgeRetriever(None)
    try:
        graph = CaseGraph(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        logger.info("knowledge_retriever initialized with Neo4j")
        return KnowledgeRetriever(Neo4jKnowledgeGraphRepository(graph))
    except Exception as exc:
        logger.warning(
            "knowledge_retriever neo4j init failed, using no-op retriever",
            extra={"service": "backend", "reason": type(exc).__name__},
        )
        return KnowledgeRetriever(None)
