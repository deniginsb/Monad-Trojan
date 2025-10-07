"""
Database Module - Handles all database operations using SQLAlchemy
Stores user data with encrypted private keys
"""
import os
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from security import encrypt_private_key, decrypt_private_key
from security_passphrase import encrypt_with_passphrase, decrypt_with_passphrase

Base = declarative_base()

class User(Base):
    """User model - stores wallet information with encrypted private keys"""
    __tablename__ = 'users'
    
    telegram_id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String(42), nullable=False)
    encrypted_private_key = Column(Text, nullable=False)
    passphrase_salt = Column(Text, nullable=True)  # For passphrase-based encryption
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserSettings(Base):
    """User settings model - stores trading preferences"""
    __tablename__ = 'user_settings'
    
    telegram_id = Column(Integer, primary_key=True, index=True)
    slippage = Column(Float, default=1.0)
    gas_price_mode = Column(String(20), default='normal')
    anti_mev = Column(Integer, default=0)
    notifications_enabled = Column(Integer, default=1)  # NEW: 1=ON, 0=OFF
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TokenHistory(Base):
    """Token history - tracks tokens bought/sold by users"""
    __tablename__ = 'token_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, nullable=False, index=True)
    token_address = Column(String(42), nullable=False)
    token_name = Column(String(100))
    token_symbol = Column(String(20))
    action = Column(String(10))
    amount = Column(String(50))
    tx_hash = Column(String(66))
    created_at = Column(DateTime, default=datetime.utcnow)

class TokenSnapshot(Base):
    """Token snapshot - tracks last known token balances for notification detection"""
    __tablename__ = 'token_snapshots'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, nullable=False, index=True)
    token_address = Column(String(42), nullable=False)
    token_symbol = Column(String(20))
    token_name = Column(String(100))
    balance = Column(String(50))
    is_verified = Column(Integer, default=0)  # 1=verified, 0=not verified
    last_updated = Column(DateTime, default=datetime.utcnow)

class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, db_path: str = 'monad_trojan_bot.db'):
        """Initialize database connection"""
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    def create_user(self, telegram_id: int, wallet_address: str, private_key: str, passphrase: str = None) -> User:
        """
        Create a new user with encrypted private key
        
        Args:
            telegram_id: Telegram user ID
            wallet_address: Wallet address
            private_key: Private key (will be encrypted before storage)
            passphrase: User's passphrase for zero-knowledge encryption
            
        Returns:
            Created User object
        """
        session = self.get_session()
        try:
            if passphrase:
                # Zero-knowledge: double-layer encryption with passphrase
                encrypted_data = encrypt_with_passphrase(private_key, passphrase)
                user = User(
                    telegram_id=telegram_id,
                    wallet_address=wallet_address,
                    encrypted_private_key=encrypted_data['encrypted_key'],
                    passphrase_salt=encrypted_data['salt']
                )
            else:
                # Legacy: single-layer encryption (not recommended)
                encrypted_key = encrypt_private_key(private_key)
                user = User(
                    telegram_id=telegram_id,
                    wallet_address=wallet_address,
                    encrypted_private_key=encrypted_key,
                    passphrase_salt=None
                )
            
            session.add(user)
            session.commit()
            session.refresh(user)
            
            self._create_default_settings(telegram_id, session)
            
            return user
        finally:
            session.close()
    
    def _create_default_settings(self, telegram_id: int, session: Session) -> None:
        """Create default settings for a new user"""
        settings = UserSettings(telegram_id=telegram_id)
        session.add(settings)
        session.commit()
    
    def get_user(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        session = self.get_session()
        try:
            return session.query(User).filter(User.telegram_id == telegram_id).first()
        finally:
            session.close()
    
    def update_user_wallet(self, telegram_id: int, wallet_address: str, private_key: str, passphrase: str = None) -> User:
        """
        Update user's wallet (for importing new wallet)
        
        Args:
            telegram_id: Telegram user ID
            wallet_address: New wallet address
            private_key: New private key (will be encrypted)
            passphrase: User's passphrase for zero-knowledge encryption
            
        Returns:
            Updated User object
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            
            if user:
                if passphrase:
                    encrypted_data = encrypt_with_passphrase(private_key, passphrase)
                    user.wallet_address = wallet_address
                    user.encrypted_private_key = encrypted_data['encrypted_key']
                    user.passphrase_salt = encrypted_data['salt']
                else:
                    encrypted_key = encrypt_private_key(private_key)
                    user.wallet_address = wallet_address
                    user.encrypted_private_key = encrypted_key
                    user.passphrase_salt = None
                
                user.updated_at = datetime.utcnow()
                session.commit()
                session.refresh(user)
            else:
                user = self.create_user(telegram_id, wallet_address, private_key, passphrase)
            
            return user
        finally:
            session.close()
    
    def get_decrypted_private_key(self, telegram_id: int, passphrase: str = None) -> Optional[str]:
        """
        Get decrypted private key for a user
        WARNING: Use immediately and delete from memory
        
        Args:
            telegram_id: Telegram user ID
            passphrase: User's passphrase (required if using passphrase encryption)
            
        Returns:
            Decrypted private key or None if user not found
            
        Raises:
            ValueError: If passphrase is required but not provided, or if incorrect
        """
        user = self.get_user(telegram_id)
        
        if not user or not user.encrypted_private_key:
            return None
        
        # Check if user has passphrase-based encryption
        if user.passphrase_salt:
            if not passphrase:
                raise ValueError("Passphrase required for this wallet")
            return decrypt_with_passphrase(
                user.encrypted_private_key,
                user.passphrase_salt,
                passphrase
            )
        else:
            # Legacy single-layer encryption
            return decrypt_private_key(user.encrypted_private_key)
    
    def get_user_settings(self, telegram_id: int) -> Optional[UserSettings]:
        """Get user settings"""
        session = self.get_session()
        try:
            settings = session.query(UserSettings).filter(
                UserSettings.telegram_id == telegram_id
            ).first()
            
            if not settings:
                self._create_default_settings(telegram_id, session)
                settings = session.query(UserSettings).filter(
                    UserSettings.telegram_id == telegram_id
                ).first()
            
            return settings
        finally:
            session.close()
    
    def update_user_settings(self, telegram_id: int, **kwargs) -> UserSettings:
        """Update user settings"""
        session = self.get_session()
        try:
            settings = session.query(UserSettings).filter(
                UserSettings.telegram_id == telegram_id
            ).first()
            
            if not settings:
                settings = UserSettings(telegram_id=telegram_id)
                session.add(settings)
            
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            settings.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(settings)
            
            return settings
        finally:
            session.close()
    
    def add_token_history(self, telegram_id: int, token_address: str, 
                         action: str, amount: str, tx_hash: str = None,
                         token_name: str = None, token_symbol: str = None) -> TokenHistory:
        """Add a token transaction to history"""
        session = self.get_session()
        try:
            history = TokenHistory(
                telegram_id=telegram_id,
                token_address=token_address,
                token_name=token_name,
                token_symbol=token_symbol,
                action=action,
                amount=amount,
                tx_hash=tx_hash
            )
            
            session.add(history)
            session.commit()
            session.refresh(history)
            
            return history
        finally:
            session.close()
    
    def get_user_tokens(self, telegram_id: int) -> List[str]:
        """Get unique token addresses from user's history"""
        session = self.get_session()
        try:
            tokens = session.query(TokenHistory.token_address).filter(
                TokenHistory.telegram_id == telegram_id
            ).distinct().all()
            
            return [token[0] for token in tokens]
        finally:
            session.close()

db_manager = DatabaseManager()
