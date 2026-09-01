import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
import hashlib

from auth_security import (
    GENERIC_CREDENTIAL_ERROR,
    LoginThrottleDecision,
    begin_login_attempt,
    peek_source_failure_count,
    record_login_failure,
    record_login_success,
    throttle_exception,
)
from login_captcha import (
    CAPTCHA_REQUIRED_HEADER,
    captcha_exception,
    captcha_required,
    issue_captcha,
    verify_captcha,
)
from mail_account_schemas import MailAccountStatus, MailAccountWrite
from mail_service import MailConfigurationError, MailDeliveryError
from database import get_db
from auth_security_models import RevokedAccessToken
from crud import get_user_by_username, get_user_roles_with_role_names
from permission_service import get_user_permission_codes, user_has_permission
from permission_registry import SUPER_ROLE_NAMES
from schemas import AuthSession, CaptchaChallenge, CaptchaRequirement, Token, LoginRequest
from user_mail_account_service import (
    delete_mail_account,
    save_mail_account,
    serialize_mail_account,
    verify_mail_account,
)

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


def _credential_exception(decision: Optional[LoginThrottleDecision] = None) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"}
    # 提前告知前端「下一次提交需要验证码」，省去登录页额外探测一次。
    if decision is not None and captcha_required(
        decision.account_failure_count, decision.source_failure_count
    ):
        headers[CAPTCHA_REQUIRED_HEADER] = "1"
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=GENERIC_CREDENTIAL_ERROR,
        headers=headers,
    )


def authenticate_user(
    db: Session,
    username: str,
    password: str,
    request: Request,
    *,
    captcha_id: Optional[str] = None,
    captcha_code: Optional[str] = None,
):
    attempt_context, throttle_decision = begin_login_attempt(db, username, request)
    if throttle_decision.blocked:
        raise throttle_exception(throttle_decision)

    # 顺序固定为「先查封禁，再校验验证码，最后校验口令」。
    # 验证码不通过时不计入失败次数，避免用户输错图形码就把自己的账号锁死。
    if captcha_required(
        throttle_decision.account_failure_count, throttle_decision.source_failure_count
    ) and not verify_captcha(db, request, captcha_id, captcha_code):
        raise captcha_exception()

    user = get_user_by_username(db, username=username)
    if not user:
        # 对不存在的账号也执行一次强哈希校验，降低账号枚举的时序差异。
        verify_password(password, _DUMMY_PASSWORD_HASH)
        failure_decision = record_login_failure(db, attempt_context)
        if failure_decision.blocked:
            raise throttle_exception(failure_decision)
        raise _credential_exception(failure_decision)

    if not verify_password(password, user.password_hash) or not user.is_active:
        failure_decision = record_login_failure(db, attempt_context)
        if failure_decision.blocked:
            raise throttle_exception(failure_decision)
        raise _credential_exception(failure_decision)

    record_login_success(db, attempt_context)
    upgraded = upgrade_legacy_password_hash(db, user, password)
    db.commit()
    if upgraded:
        db.refresh(user)
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



def get_user_from_token_value(db: Session, token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        jti: str = payload.get('jti')
        if not username or not jti:
            return None
        if db.get(RevokedAccessToken, hashlib.sha256(jti.encode("utf-8")).hexdigest()) is not None:
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
        detail="登录凭证无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = get_user_from_token_value(db, token)
    if user is None:
        raise credentials_exception
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """撤销当前访问令牌；重复退出保持幂等。"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        expires_at = payload.get("exp")
        user_id = payload.get("user_id")
        if not jti or not expires_at:
            raise _credential_exception()
    except JWTError:
        raise _credential_exception()

    jti_hash = hashlib.sha256(jti.encode("utf-8")).hexdigest()
    db.execute(delete(RevokedAccessToken).where(RevokedAccessToken.expires_at < func.now()))
    if db.get(RevokedAccessToken, jti_hash) is None:
        parsed_user_id = None
        try:
            parsed_user_id = uuid.UUID(user_id) if user_id else None
        except (TypeError, ValueError):
            pass
        db.add(RevokedAccessToken(
            jti_hash=jti_hash,
            user_id=parsed_user_id,
            expires_at=datetime.fromtimestamp(expires_at, timezone.utc),
        ))
        try:
            db.commit()
        except IntegrityError:
            # 并发重复退出可能同时插入同一 JTI，唯一约束冲突等同于撤销成功。
            db.rollback()


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


def require_any_role(*allowed_role_names: str) -> Callable:
    """要求当前用户至少拥有一个指定角色；超级管理员始终放行。"""
    allowed_roles = set(allowed_role_names) | SUPER_ROLE_NAMES

    def role_dependency(
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        role_names = set(get_user_roles_with_role_names(db, current_user.id))
        if role_names.isdisjoint(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"仅以下角色可以访问：{', '.join(allowed_role_names)}",
            )
        return current_user

    return role_dependency


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


def _mail_account_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, MailDeliveryError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    if isinstance(exc, (MailConfigurationError, ValueError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="个人邮箱配置处理失败，请联系管理员检查服务配置",
    )


@router.get("/mail-account", response_model=MailAccountStatus)
def read_current_mail_account(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return serialize_mail_account(db, current_user)


@router.put(
    "/mail-account",
    response_model=MailAccountStatus,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def bind_current_mail_account(
    payload: MailAccountWrite,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return save_mail_account(db, current_user, payload.authorization_code)
    except Exception as exc:
        db.rollback()
        raise _mail_account_exception(exc) from exc


@router.post(
    "/mail-account/verify",
    response_model=MailAccountStatus,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def verify_current_mail_account(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return verify_mail_account(db, current_user)
    except Exception as exc:
        db.rollback()
        raise _mail_account_exception(exc) from exc


@router.delete(
    "/mail-account",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def remove_current_mail_account(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    delete_mail_account(db, current_user)


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


@router.get("/captcha/required", response_model=CaptchaRequirement)
def read_captcha_requirement(request: Request, response: Response, db: Session = Depends(get_db)):
    """登录页首屏探测是否需要验证码。

    只按来源 IP 判定，刻意不接受用户名，避免被用来探测账号是否存在。
    """
    response.headers["Cache-Control"] = "no-store"
    return {"required": captcha_required(0, peek_source_failure_count(db, request))}


@router.get("/captcha", response_model=CaptchaChallenge)
def create_captcha(request: Request, response: Response, db: Session = Depends(get_db)):
    """签发一张一次性图形验证码。"""
    issued = issue_captcha(db, request)
    response.headers["Cache-Control"] = "no-store"
    return {"captcha_id": issued.captcha_id, "image": issued.image, "expires_in": issued.expires_in}


@router.post("/login/json", response_model=Token)
def login_json(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """????(JSON ??)??? token ???????"""
    user = authenticate_user(
        db,
        login_data.username,
        login_data.password,
        request,
        captcha_id=login_data.captcha_id,
        captcha_code=login_data.captcha_code,
    )

    role_names = get_user_roles_with_role_names(db, user.id)
    permissions = get_user_permission_codes(db, user.id)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": str(user.id)},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "roles": role_names, "permissions": permissions, "user_id": str(user.id), "username": user.username, "full_name": user.full_name or user.username}
