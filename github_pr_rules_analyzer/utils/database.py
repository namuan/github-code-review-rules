"""
Database connection and session management utilities
"""

import logging
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from ..config import get_database_url

# Global variables
engine = None
SessionLocal = None
Base = declarative_base()


def get_engine() -> Engine:
    """
    Get database engine instance
    
    Returns:
        SQLAlchemy engine instance
    """
    global engine
    
    if engine is None:
        database_url = get_database_url()
        
        # Create engine with specific SQLite settings
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,
            pool_recycle=300,
        )
        
        # Add event listeners for better SQLite performance
        if database_url.startswith("sqlite"):
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=1000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
                cursor.close()
    
    return engine


def get_session_local() -> sessionmaker:
    """
    Get session local factory
    
    Returns:
        Session factory instance
    """
    global SessionLocal
    
    if SessionLocal is None:
        engine = get_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Get database session dependency for FastAPI
    
    Yields:
        Database session
    """
    db = get_session_local()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """
    Create all database tables
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """
    Drop all database tables
    """
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)


def check_database_connection() -> bool:
    """
    Check if database connection is working
    
    Returns:
        True if connection is successful, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        return True
    except Exception as e:
        logging.error(f"Database connection check failed: {e}")
        return False


def get_database_info() -> dict:
    """
    Get database information
    
    Returns:
        Dictionary with database information
    """
    engine = get_engine()
    database_url = get_database_url()
    
    info = {
        "database_url": database_url,
        "driver": engine.driver,
        "pool_size": str(engine.pool.size()),
        "pool_timeout": str(engine.pool.timeout),
        "pool_recycle": str(engine.pool.recycle),
    }
    
    if database_url.startswith("sqlite"):
        # Get SQLite file info
        db_path = Path(database_url.replace("sqlite:///", ""))
        if db_path.exists():
            info["file_size"] = f"{db_path.stat().st_size / 1024 / 1024:.2f} MB"
            info["file_path"] = str(db_path.absolute())
        else:
            info["file_size"] = "Not created"
            info["file_path"] = str(db_path.absolute())
    
    return info


class DatabaseManager:
    """Database manager for common operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def initialize_database(self) -> bool:
        """
        Initialize database with tables and basic setup
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Initializing database...")
            
            # Create tables
            create_tables()
            
            # Check connection
            if check_database_connection():
                self.logger.info("Database initialized successfully")
                return True
            else:
                self.logger.error("Database connection failed after initialization")
                return False
                
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            return False
    
    def reset_database(self) -> bool:
        """
        Reset database by dropping all tables and recreating them
        
        Returns:
            True if reset successful, False otherwise
        """
        try:
            self.logger.warning("Resetting database...")
            
            # Drop tables
            drop_tables()
            
            # Recreate tables
            create_tables()
            
            self.logger.info("Database reset successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Database reset failed: {e}")
            return False
    
    def backup_database(self, backup_path: Path) -> bool:
        """
        Create a backup of the SQLite database
        
        Args:
            backup_path: Path where to create the backup
            
        Returns:
            True if backup successful, False otherwise
        """
        try:
            database_url = get_database_url()
            
            if not database_url.startswith("sqlite"):
                self.logger.error("Backup only supported for SQLite databases")
                return False
            
            # Get current database path
            db_path = Path(database_url.replace("sqlite:///", ""))
            
            if not db_path.exists():
                self.logger.error("Database file does not exist")
                return False
            
            # Create backup
            import shutil
            shutil.copy2(db_path, backup_path)
            
            self.logger.info(f"Database backup created at {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Database backup failed: {e}")
            return False