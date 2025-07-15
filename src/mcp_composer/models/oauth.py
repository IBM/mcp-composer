"""OAuth models"""

from pydantic import BaseModel


class BearerAuth(BaseModel):
    """Bearer auth model"""

    token: str


class DynamicBearerAuth(BaseModel):
    """Dynamic Bearer auth model"""

    apikey: str
    token_url: str


class BasicAuth(BaseModel):
    """Basic auth model"""

    username: str
    password: str


class APIkey(BaseModel):
    """API Key model"""

    apikey: str
    value: str
