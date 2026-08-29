import os
from datetime import datetime, timedelta
from typing import Callable, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
import hashlib

from auth_security import (
    GENERIC_CREDENTIAL_ERROR,
    begin_login_attempt,
    record_login_failure,
    record_login_success,
    throttle_exception,
)
from database import get_db
from crud import get_user_by_username, get_user_roles_with_role_names
from permission_service import get_user_permission_codes, user_has_permission
from permission_registry import SUPER_ROLE_NAMES
from schemas import AuthSession, Token, LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set")


def normalize_password_for_bcrypt(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")
    # bcrypt only supports 72 bytes; pre-hash longer passwords to keep login usable.
    if len(password_bytes) > 72:
        return hashlib.sha256(password_bytes).hexdigest()
    return plain_password


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(normalize_password_for_bcrypt(plain_password))


def is_bcrypt_hash(password_hash: Optional[str]) -> bool:
    return isinstance(password_hash, str) and password_hash.startswith(("$2a$", "$2b$", "$2y$"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if is_bcrypt_hash(hashed_password):
        try:
            return pwd_context.verify(normalize_password_for_bcrypt(plain_password), hashed_password)
        except ValueError:
            return False
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def upgrade_legacy_password_hash(db: Session, user, plain_password: str) -> bool:
    if is_bcrypt_hash(user.password_hash):
        return False
    user.password_hash = hash_password(plain_password)
    db.add(user)
    return True


_DUMMY_PASSWORD_HASH = pwd_context.hash("not-a-real-account-password")


def _credential_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=GENERIC_CREDENTIAL_ERROR,
        headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
    )


def authenticate_user(db: Session, username: str, password: str, request: Request):
    attempt_context, throttle_decision = begin_login_attempt(db, username, request)
    if throttle_decision.blocked:
        raise throttle_exception(throttle_decision)

    user = get_user_by_username(db, username=username)
    if not user:
        # 对不存在的账号也执行一次强哈希校验，降低账号枚举的时序差异。
        verify_password(password, _DUMMY_PASSWORD_HASH)
        failure_decision = record_login_failure(db, attempt_context)
        if failure_decision.blocked:
            raise throttle_exception(failure_decision)
        raise _credential_exception()

    if not verify_password(password, user.password_hash) or not user.is_active:
        failure_decision = record_login_failure(db, attempt_context)
        if failure_decision.blocked:
            raise throttle_exception(failure_decision)
        raise _credential_exception()

    record_login_success(db, attempt_context)
    upgraded = upgrade_legacy_password_hash(db, user, password)
    db.commit()
    if upgraded:
        db.refresh(user)
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



def get_user_from_token_value(db: Session, token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        if not username:
            return None
    except JWTError:
        return None

    user = get_user_by_username(db, username=username)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = get_user_from_token_value(db, token)
    if user is None:
        raise credentials_exception
    return user


def require_super_admin(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """仅允许 admin/超级管理员角色调用。"""
    role_names = set(get_user_roles_with_role_names(db, current_user.id))
    if SUPER_ROLE_NAMES.isdisjoint(role_names):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅超级管理员可以执行此操作",
        )
    return current_user


def require_permission(permission_code: str) -> Callable:
    """创建权限依赖，供路由在后端强制执行 RBAC。"""
    def permission_dependency(
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        if not user_has_permission(db, current_user.id, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限：{permission_code}",
            )
        return current_user

    return permission_dependency


def require_module_access(read_permission: str, write_permission: str) -> Callable:
    """按 HTTP 方法区分模块的查看权限和管理权限。"""
    def permission_dependency(
        request: Request,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        permission_code = read_permission if request.method in {"GET", "HEAD", "OPTIONS"} else write_permission
        if not user_has_permission(db, current_user.id, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限：{permission_code}",
            )
        return current_user

    return permission_dependency


def require_any_permission(*permission_codes: str) -> Callable:
    """要求至少拥有一个权限，适用于跨模块共享的基础数据接口。"""
    def permission_dependency(
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        permissions = set(get_user_permission_codes(db, current_user.id))
        if "*" not in permissions and permissions.isdisjoint(permission_codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"至少需要以下权限之一：{', '.join(permission_codes)}",
            )
        return current_user

    return permission_dependency


@router.get("/session", response_model=AuthSession)
def read_current_session(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回当前账号的实时角色与权限，用于前端刷新会话缓存。"""
    return {
        "user_id": str(current_user.id),
        "username": current_user.username,
        "full_name": current_user.full_name or current_user.username,
        "roles": get_user_roles_with_role_names(db, current_user.id),
        "permissions": get_user_permission_codes(db, current_user.id),
    }


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """????(OAuth2 ??)??? token ???????"""
    user = authenticate_user(db, form_data.username, form_data.password, request)

    role_names = get_user_roles_with_role_names(db, user.id)
    permissions = get_user_permission_codes(db, user.id)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": str(user.id)},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "roles": role_names, "permissions": permissions, "user_id": str(user.id), "username": user.username, "full_name": user.full_name or user.username}


@router.post("/login/json", response_model=Token)
def login_json(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """????(JSON ??)??? token ???????"""
    user = authenticate_user(db, login_data.username, login_data.password, request)

    role_names = get_user_roles_with_role_names(db, user.id)
    permissions = get_user_permission_codes(db, user.id)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": str(user.id)},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "roles": role_names, "permissions": permissions, "user_id": str(user.id), "username": user.username, "full_name": user.full_name or user.username}
