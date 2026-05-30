"""
用户服务 - 基于数据库的用户管理
"""

import hashlib
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

import bcrypt
from pymongo import MongoClient
from bson import ObjectId

from app.core.config import settings
from app.models.user import User, UserCreate, UserUpdate, UserResponse

# 尝试导入日志管理器
try:
    from tradingagents.utils.logging_manager import get_logger
except ImportError:
    # 如果导入失败，使用标准日志
    import logging

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)


logger = get_logger("user_service")


class UserService:
    """用户服务类"""

    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.users_collection = self.db.users

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, "client") and self.client:
            self.client.close()
            logger.info("✅ UserService MongoDB 连接已关闭")

    def __del__(self):
        """析构函数，确保连接被关闭"""
        self.close()

    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希（bcrypt，带盐，自适应成本）。

        bcrypt 输入上限 72 字节，超出会被忽略——显式截断以避免 bcrypt 4.x 抛 ValueError。
        """
        rounds = getattr(settings, "BCRYPT_ROUNDS", 12)
        pw_bytes = password.encode("utf-8")[:72]
        return bcrypt.hashpw(pw_bytes, bcrypt.gensalt(rounds=rounds)).decode("utf-8")

    @staticmethod
    def _is_bcrypt_hash(hashed_password: str) -> bool:
        return hashed_password.startswith(("$2a$", "$2b$", "$2y$"))

    @staticmethod
    def needs_rehash(hashed_password: str) -> bool:
        """非 bcrypt 形态（历史无盐 SHA-256）需在下次登录时升级。"""
        return not UserService._is_bcrypt_hash(hashed_password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码。

        迁移期兼容历史无盐 SHA-256：bcrypt 形态走 bcrypt 校验，其余按 legacy
        SHA-256 校验；登录成功后由 authenticate_user 透明 rehash 到 bcrypt。
        """
        if not hashed_password:
            return False
        if UserService._is_bcrypt_hash(hashed_password):
            try:
                return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
            except (ValueError, TypeError):
                return False
        # legacy 无盐 SHA-256 兜底（仅迁移期存量用户）
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

    async def create_user(self, user_data: UserCreate) -> Optional[User]:
        """创建用户"""
        try:
            # 检查用户名是否已存在
            existing_user = self.users_collection.find_one({"username": user_data.username})
            if existing_user:
                logger.warning(f"用户名已存在: {user_data.username}")
                return None

            # 检查邮箱是否已存在
            existing_email = self.users_collection.find_one({"email": user_data.email})
            if existing_email:
                logger.warning(f"邮箱已存在: {user_data.email}")
                return None

            # 创建用户文档
            user_doc = {
                "username": user_data.username,
                "email": user_data.email,
                "hashed_password": self.hash_password(user_data.password),
                "is_active": True,
                "is_verified": False,
                "is_admin": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
                "preferences": {
                    # 分析偏好
                    "default_market": "A股",
                    "default_depth": "3",  # 1-5级，3级为标准分析（推荐）
                    "default_analysts": ["市场分析师", "基本面分析师"],
                    "auto_refresh": True,
                    "refresh_interval": 30,
                    # 外观设置
                    "ui_theme": "light",
                    "sidebar_width": 240,
                    # 语言和地区
                    "language": "zh-CN",
                    # 通知设置
                    "notifications_enabled": True,
                    "email_notifications": False,
                    "desktop_notifications": True,
                    "analysis_complete_notification": True,
                    "system_maintenance_notification": True,
                },
                "daily_quota": 1000,
                "concurrent_limit": 3,
                "total_analyses": 0,
                "successful_analyses": 0,
                "failed_analyses": 0,
                "favorite_stocks": [],
            }

            result = self.users_collection.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id

            logger.info(f"✅ 用户创建成功: {user_data.username}")
            return User(**user_doc)

        except Exception as e:
            logger.error(f"❌ 创建用户失败: {e}")
            return None

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """用户认证"""
        try:
            logger.info(f"🔍 [authenticate_user] 开始认证用户: {username}")

            # 查找用户
            user_doc = self.users_collection.find_one({"username": username})
            logger.info(f"🔍 [authenticate_user] 数据库查询结果: {'找到用户' if user_doc else '用户不存在'}")

            if not user_doc:
                logger.warning(f"❌ [authenticate_user] 用户不存在: {username}")
                return None

            logger.info(
                f"🔍 [authenticate_user] 用户信息: username={user_doc.get('username')}, email={user_doc.get('email')}, is_active={user_doc.get('is_active')}"
            )

            # 验证密码（不打印任何哈希值——避免日志泄漏哈希前缀削弱密钥强度）
            stored_password_hash = user_doc["hashed_password"]
            if not self.verify_password(password, stored_password_hash):
                logger.warning(f"❌ [authenticate_user] 密码错误: {username}")
                return None

            # 历史无盐 SHA-256 哈希在登录成功后透明升级为 bcrypt（一次性迁移，失败不影响本次登录）
            if self.needs_rehash(stored_password_hash):
                try:
                    self.users_collection.update_one(
                        {"_id": user_doc["_id"]},
                        {"$set": {"hashed_password": self.hash_password(password)}},
                    )
                    logger.info(f"🔐 [authenticate_user] 密码哈希已升级为 bcrypt: {username}")
                except Exception as e:
                    logger.warning(f"⚠️ [authenticate_user] 密码哈希升级失败（不影响登录）: {e}")

            # 检查用户是否激活
            if not user_doc.get("is_active", True):
                logger.warning(f"❌ [authenticate_user] 用户已禁用: {username}")
                return None

            # 更新最后登录时间
            self.users_collection.update_one({"_id": user_doc["_id"]}, {"$set": {"last_login": datetime.utcnow()}})

            logger.info(f"✅ [authenticate_user] 用户认证成功: {username}")
            return User(**user_doc)

        except Exception as e:
            logger.error(f"❌ 用户认证失败: {e}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        try:
            user_doc = self.users_collection.find_one({"username": username})
            if user_doc:
                return User(**user_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取用户失败: {e}")
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据用户ID获取用户"""
        try:
            if not ObjectId.is_valid(user_id):
                return None

            user_doc = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if user_doc:
                return User(**user_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取用户失败: {e}")
            return None

    async def update_user(self, username: str, user_data: UserUpdate) -> Optional[User]:
        """更新用户信息"""
        try:
            update_data = {"updated_at": datetime.utcnow()}

            # 只更新提供的字段
            if user_data.email:
                # 检查邮箱是否已被其他用户使用
                existing_email = self.users_collection.find_one({"email": user_data.email, "username": {"$ne": username}})
                if existing_email:
                    logger.warning(f"邮箱已被使用: {user_data.email}")
                    return None
                update_data["email"] = user_data.email

            if user_data.preferences:
                update_data["preferences"] = user_data.preferences.model_dump()

            if user_data.daily_quota is not None:
                update_data["daily_quota"] = user_data.daily_quota

            if user_data.concurrent_limit is not None:
                update_data["concurrent_limit"] = user_data.concurrent_limit

            result = self.users_collection.update_one({"username": username}, {"$set": update_data})

            if result.modified_count > 0:
                logger.info(f"✅ 用户信息更新成功: {username}")
                return await self.get_user_by_username(username)
            else:
                logger.warning(f"用户不存在或无需更新: {username}")
                return None

        except Exception as e:
            logger.error(f"❌ 更新用户信息失败: {e}")
            return None

    async def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """修改密码"""
        try:
            # 验证旧密码
            user = await self.authenticate_user(username, old_password)
            if not user:
                logger.warning(f"旧密码验证失败: {username}")
                return False

            # 更新密码
            new_hashed_password = self.hash_password(new_password)
            result = self.users_collection.update_one(
                {"username": username}, {"$set": {"hashed_password": new_hashed_password, "updated_at": datetime.utcnow()}}
            )

            if result.modified_count > 0:
                logger.info(f"✅ 密码修改成功: {username}")
                return True
            else:
                logger.error(f"❌ 密码修改失败: {username}")
                return False

        except Exception as e:
            logger.error(f"❌ 修改密码失败: {e}")
            return False

    async def reset_password(self, username: str, new_password: str) -> bool:
        """重置密码（管理员操作）"""
        try:
            new_hashed_password = self.hash_password(new_password)
            result = self.users_collection.update_one(
                {"username": username}, {"$set": {"hashed_password": new_hashed_password, "updated_at": datetime.utcnow()}}
            )

            if result.modified_count > 0:
                logger.info(f"✅ 密码重置成功: {username}")
                return True
            else:
                logger.error(f"❌ 密码重置失败: {username}")
                return False

        except Exception as e:
            logger.error(f"❌ 重置密码失败: {e}")
            return False

    async def create_admin_user(
        self, username: str = "admin", password: str = "admin123", email: str = "admin@tradingagents.cn"
    ) -> Optional[User]:
        """创建管理员用户"""
        try:
            # 检查是否已存在管理员
            existing_admin = self.users_collection.find_one({"username": username})
            if existing_admin:
                logger.info(f"管理员用户已存在: {username}")
                return User(**existing_admin)

            # 创建管理员用户文档
            admin_doc = {
                "username": username,
                "email": email,
                "hashed_password": self.hash_password(password),
                "is_active": True,
                "is_verified": True,
                "is_admin": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
                "preferences": {
                    "default_market": "A股",
                    "default_depth": "深度",
                    "ui_theme": "light",
                    "language": "zh-CN",
                    "notifications_enabled": True,
                    "email_notifications": False,
                },
                "daily_quota": 10000,  # 管理员更高配额
                "concurrent_limit": 10,
                "total_analyses": 0,
                "successful_analyses": 0,
                "failed_analyses": 0,
                "favorite_stocks": [],
            }

            result = self.users_collection.insert_one(admin_doc)
            admin_doc["_id"] = result.inserted_id

            logger.info(f"✅ 管理员用户创建成功: {username}")
            logger.info(f"   密码: {password}")
            logger.info("   ⚠️  请立即修改默认密码！")

            return User(**admin_doc)

        except Exception as e:
            logger.error(f"❌ 创建管理员用户失败: {e}")
            return None

    async def list_users(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        """获取用户列表"""
        try:
            cursor = self.users_collection.find().skip(skip).limit(limit)
            users = []

            for user_doc in cursor:
                user = User(**user_doc)
                users.append(
                    UserResponse(
                        id=str(user.id),
                        username=user.username,
                        email=user.email,
                        is_active=user.is_active,
                        is_verified=user.is_verified,
                        created_at=user.created_at,
                        last_login=user.last_login,
                        preferences=user.preferences,
                        daily_quota=user.daily_quota,
                        concurrent_limit=user.concurrent_limit,
                        total_analyses=user.total_analyses,
                        successful_analyses=user.successful_analyses,
                        failed_analyses=user.failed_analyses,
                    )
                )

            return users

        except Exception as e:
            logger.error(f"❌ 获取用户列表失败: {e}")
            return []

    async def deactivate_user(self, username: str) -> bool:
        """禁用用户"""
        try:
            result = self.users_collection.update_one(
                {"username": username}, {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )

            if result.modified_count > 0:
                logger.info(f"✅ 用户已禁用: {username}")
                return True
            else:
                logger.warning(f"用户不存在: {username}")
                return False

        except Exception as e:
            logger.error(f"❌ 禁用用户失败: {e}")
            return False

    async def activate_user(self, username: str) -> bool:
        """激活用户"""
        try:
            result = self.users_collection.update_one(
                {"username": username}, {"$set": {"is_active": True, "updated_at": datetime.utcnow()}}
            )

            if result.modified_count > 0:
                logger.info(f"✅ 用户已激活: {username}")
                return True
            else:
                logger.warning(f"用户不存在: {username}")
                return False

        except Exception as e:
            logger.error(f"❌ 激活用户失败: {e}")
            return False


# 全局用户服务实例
user_service = UserService()
