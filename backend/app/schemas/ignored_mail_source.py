from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.ignored_mail_source_service import normalize_ignored_mail_value


class IgnoredMailSourceCreate(BaseModel):
    rule_type: Literal["email", "domain"]
    value: str = Field(min_length=1, max_length=320)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str, info):
        rule_type = info.data.get("rule_type")
        return normalize_ignored_mail_value(str(rule_type), value)


class IgnoredMailSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_type: Literal["email", "domain"]
    normalized_value: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
