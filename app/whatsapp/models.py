from pydantic import BaseModel

class Contact(BaseModel):
    name: str
    phone: str | None = None

class Message(BaseModel):
    sender: str
    timestamp: str
    text: str
    is_from_me: bool

class SearchResult(BaseModel):
    matches: list[Contact]
    query: str

class ChatMessages(BaseModel):
    contact: str
    messages: list[Message]

class ConnectionStatus(BaseModel):
    connected: bool
    authenticated: bool
    message: str
