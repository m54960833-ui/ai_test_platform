# 被测服务接口的请求/响应模型，字段校验靠 pydantic 兜着
from pydantic import BaseModel, Field


class RegisterReq(BaseModel):
    username: str = Field(min_length=3, max_length=20, description="用户名，3-20位")
    password: str = Field(min_length=6, max_length=32, description="密码，至少6位")
    email: str = ""


class LoginReq(BaseModel):
    username: str
    password: str


class UserUpdateReq(BaseModel):
    email: str = ""
    nickname: str = ""


class OrderCreateReq(BaseModel):
    user_id: int
    product_id: int
    product_name: str = ""
    quantity: int = Field(default=1, ge=1, description="数量，至少1")
    amount: float = Field(gt=0, description="金额必须大于0")


class OrderStatusReq(BaseModel):
    # pending -> paid / cancelled
    status: str = Field(pattern="^(paid|cancelled)$")
