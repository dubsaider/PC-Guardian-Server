"""
Зависимости для FastAPI (dependency injection)
Аутентификация и получение текущего пользователя
"""
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request, Cookie
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from infrastructure.database.session import get_db
from infrastructure.database.models import User
from core.config import settings

security = HTTPBasic()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создать JWT токен"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.access_token_expire_hours)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Проверить JWT токен"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверить пароль"""
    try:
        # Проверяем пароль через bcrypt напрямую
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        # Если не получилось через bcrypt, пробуем через passlib (для обратной совместимости)
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    """Получить хеш пароля"""
    try:
        # Используем bcrypt напрямую
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    except Exception:
        # Fallback на passlib если bcrypt не работает
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.hash(password)


def get_user_from_token(session_token: str, db: Session) -> Optional[User]:
    """Получить пользователя из токена (вспомогательная функция)"""
    if not session_token:
        return None
    
    payload = verify_token(session_token)
    if not payload:
        return None
    
    username: str = payload.get("sub")
    if username is None:
        return None
    
    user = db.query(User).filter(User.username == username).first()
    if user and not user.is_active:
        return None
    
    return user


def get_current_user(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(HTTPBasic(auto_error=False)),
    db: Session = Depends(get_db)
) -> User:
    """
    Получить текущего пользователя из сессии или HTTP Basic Auth
    Dependency для FastAPI endpoints
    """
    # Сначала пробуем получить из сессии (cookie)
    session_token = request.cookies.get("session_token")
    if session_token:
        user = get_user_from_token(session_token, db)
        if user:
            return user
    
    # Если нет сессии, пробуем HTTP Basic Auth (для API)
    if credentials:
        user = db.query(User).filter(User.username == credentials.username).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        
        if not verify_password(credentials.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive"
            )
        
        return user
    
    # Если нет ни сессии, ни Basic Auth - перенаправляем на страницу логина
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated"
    )


def create_user(
    username: str,
    email: str,
    password: str,
    role: str = "viewer",
    db: Session = None
) -> User:
    """Создать пользователя"""
    if db is None:
        from infrastructure.database.session import SessionLocal
        db = SessionLocal()
    
    # Проверяем, существует ли пользователь
    if db.query(User).filter(User.username == username).first():
        raise ValueError("User already exists")
    
    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash(password),
        role=role
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user









