from typing import Optional

from pydantic import BaseModel


class CaseCreate(BaseModel):
    client_name: str
    phone_number: str
    email: Optional[str] = None
    address: str
    description: Optional[str] = None


class Case(BaseModel):
    id: int
    case_number: str
    client_name: str
    phone_number: str
    email: Optional[str] = None
    address: str
    description: Optional[str] = None
