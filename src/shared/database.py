import asyncpg
import os
from typing import Optional, List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

## Manages Connections to Database
class DatabaseManager:    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    ## Establishes connection to Database
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME', 'k17_bot'),
            min_size=5,
            max_size=20
        )
        logger.info("✅ Database connection pool established")
        await self._initialize_tables()
    
    ## Closes connection to Database
    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("✅ Database connection pool closed")
    
    ## Initialize database tables
    async def _initialize_tables(self):
        """Create tables if they don't exist"""
        async with self.pool.acquire() as conn: # type: ignore
            # Tracked messages table - generic for any bot feature
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tracked_messages (
                    id SERIAL PRIMARY KEY,
                    message_id BIGINT UNIQUE NOT NULL,
                    channel_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    feature_type VARCHAR(50) NOT NULL,
                    metadata JSONB,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Reaction role configs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reaction_role_configs (
                    id SERIAL PRIMARY KEY,
                    message_id BIGINT REFERENCES tracked_messages(message_id) ON DELETE CASCADE,
                    emoji VARCHAR(100) NOT NULL,
                    role_id BIGINT NOT NULL,
                    mode VARCHAR(20) DEFAULT 'toggle',
                    UNIQUE(message_id, emoji)
                )
            """)
            
            # Audit logs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT,
                    action_type VARCHAR(50) NOT NULL,
                    details JSONB,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracked_messages_feature 
                ON tracked_messages(feature_type, is_active)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracked_messages_guild 
                ON tracked_messages(guild_id, is_active)
            """)
            
        logger.info("✅ Database tables initialized")
    
    ## ==================== TRACKED MESSAGES ====================
    async def add_tracked_message(
        self, 
        message_id: int, 
        channel_id: int, 
        guild_id: int,
        feature_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Add a message to track for any feature"""
        query = """
            INSERT INTO tracked_messages 
            (message_id, channel_id, guild_id, feature_type, metadata)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (message_id) 
            DO UPDATE SET 
                metadata = $5,
                updated_at = NOW()
            RETURNING id
        """
        async with self.pool.acquire() as conn: # type: ignore
            row = await conn.fetchrow(
                query, message_id, channel_id, guild_id, 
                feature_type, json.dumps(metadata) if metadata else None
            )
            logger.info(f"Tracked message {message_id} for {feature_type}")
            return row['id'] # type: ignore
    
    async def get_tracked_messages(
        self, 
        feature_type: Optional[str] = None,
        guild_id: Optional[int] = None,
        is_active: bool = True
    ) -> List[asyncpg.Record]:
        """Get tracked messages, optionally filtered by feature type or guild"""
        conditions = ["is_active = $1"]
        params: List[Any] = [is_active]
        param_idx = 2
        
        if feature_type:
            conditions.append(f"feature_type = ${param_idx}")
            params.append(feature_type)
            param_idx += 1
        
        if guild_id:
            conditions.append(f"guild_id = ${param_idx}")
            params.append(guild_id)
        
        query = f"""
            SELECT * FROM tracked_messages
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
        """
        
        async with self.pool.acquire() as conn: # type: ignore
            return await conn.fetch(query, *params)
    
    async def update_tracked_message_metadata(
        self,
        message_id: int,
        metadata: Dict[str, Any]
    ):
        """Update metadata for a tracked message"""
        query = """
            UPDATE tracked_messages
            SET metadata = $2, updated_at = NOW()
            WHERE message_id = $1
        """
        async with self.pool.acquire() as conn: # type: ignore
            await conn.execute(query, message_id, json.dumps(metadata))
    
    async def deactivate_tracked_message(self, message_id: int):
        """Mark a tracked message as inactive"""
        query = """
            UPDATE tracked_messages
            SET is_active = false, updated_at = NOW()
            WHERE message_id = $1
        """
        async with self.pool.acquire() as conn: # type: ignore
            await conn.execute(query, message_id)
            logger.info(f"Deactivated tracked message {message_id}")
    

    ## ==================== REACTION ROLES ====================
    ## TODO
    async def add_reaction_role(
        self,
        message_id: int,
        emoji: str,
        role_id: int,
        mode: str = 'toggle'
    ):
        """Add a reaction role configuration"""
        query = """
            INSERT INTO reaction_role_configs 
            (message_id, emoji, role_id, mode)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (message_id, emoji) 
            DO UPDATE SET role_id = $3, mode = $4
        """
        async with self.pool.acquire() as conn: # type: ignore
            await conn.execute(query, message_id, emoji, role_id, mode)
            logger.info(f"Added reaction role {emoji} -> {role_id} on message {message_id}")
    
    async def get_reaction_roles(self, message_id: int) -> List[asyncpg.Record]:
        """Get all reaction role configs for a message"""
        query = """
            SELECT rrc.* 
            FROM reaction_role_configs rrc
            JOIN tracked_messages tm ON rrc.message_id = tm.message_id
            WHERE rrc.message_id = $1 AND tm.is_active = true
        """
        async with self.pool.acquire() as conn: # type: ignore
            return await conn.fetch(query, message_id)
    
    async def get_all_reaction_role_messages(self) -> List[asyncpg.Record]:
        """Get all active reaction role messages with their configs"""
        query = """
            SELECT 
                tm.message_id,
                tm.channel_id,
                tm.guild_id,
                json_agg(
                    json_build_object(
                        'emoji', rrc.emoji,
                        'role_id', rrc.role_id,
                        'mode', rrc.mode
                    )
                ) as reactions
            FROM tracked_messages tm
            JOIN reaction_role_configs rrc ON tm.message_id = rrc.message_id
            WHERE tm.feature_type = 'reaction_roles' AND tm.is_active = true
            GROUP BY tm.message_id, tm.channel_id, tm.guild_id
        """
        async with self.pool.acquire() as conn: # type: ignore
            return await conn.fetch(query)
    
    ## ==================== AUDIT LOGS ====================
    async def log_action(
        self, 
        guild_id: int, 
        action_type: str, 
        details: Dict[str, Any],
        user_id: Optional[int] = None
    ):
        """Log an action to the audit log"""
        query = """
            INSERT INTO audit_logs (guild_id, user_id, action_type, details, timestamp)
            VALUES ($1, $2, $3, $4, NOW())
        """
        async with self.pool.acquire() as conn: # type: ignore
            await conn.execute(
                query, 
                guild_id, 
                user_id,
                action_type, 
                json.dumps(details)
            )
    
    async def get_audit_logs(
        self,
        guild_id: int,
        limit: int = 100,
        action_type: Optional[str] = None
    ) -> List[asyncpg.Record]:
        """Get audit logs for a guild"""
        if action_type:
            query = """
                SELECT * FROM audit_logs
                WHERE guild_id = $1 AND action_type = $2
                ORDER BY timestamp DESC
                LIMIT $3
            """
            params = [guild_id, action_type, limit]
        else:
            query = """
                SELECT * FROM audit_logs
                WHERE guild_id = $1
                ORDER BY timestamp DESC
                LIMIT $2
            """
            params = [guild_id, limit]
        
        async with self.pool.acquire() as conn: # type: ignore
            return await conn.fetch(query, *params)