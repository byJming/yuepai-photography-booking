from pydantic import BaseModel, Field


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=128)


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class TotpEnableRequest(BaseModel):
    totp_code: str = Field(pattern=r"^\d{6}$")
