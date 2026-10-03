from pydantic import BaseModel, Field
from typing import Optional

class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str
    password: str = Field(min_length=6, max_length=100)

class LoginInput(BaseModel):
    email: str
    password: str

class HomeInput(BaseModel):
    budget: float = Field(gt=0)
    room: str = "Living Room"
    style: str = "Modern"
    items: str = ""

class PartyInput(BaseModel):
    budget: float = Field(gt=0)
    guests: int = Field(gt=0, le=10000)
    event_type: str = "Birthday"
    venue: str = "Home"
    preferences: str = ""

class JewelryInput(BaseModel):
    budget: float = Field(gt=0)
    occasion: str = "Wedding"
    style: str = "Elegant"
    preferences: str = ""
