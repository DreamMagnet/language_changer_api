from typing import Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from constants.app_configuration import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MongoDBService:
    """Singleton MongoDB client service"""

    _instance = None
    _client: Optional[MongoClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_client(cls) -> MongoClient:
        """Get or create MongoDB client instance"""
        if cls._client is None:
            try:
                cls._client = MongoClient(
                    settings.mongo_uri,
                    serverSelectionTimeoutMS=settings.mongo_timeout_ms,
                )
                # Verify connection
                cls._client.admin.command("ping")
                logger.info(f"MongoDB connection established: {settings.mongo_uri}")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
        return cls._client

    @classmethod
    def get_collection(cls) -> Collection:
        """Get the translations collection"""
        client = cls.get_client()
        db = client[settings.mongo_db]
        collection = db[settings.mongo_collection]
        logger.debug(f"Using collection: {settings.mongo_db}.{settings.mongo_collection}")
        return collection

    @classmethod
    def close_connection(cls):
        """Close MongoDB connection"""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            logger.info("MongoDB connection closed")