class WhatsAppError(Exception):
    """Base class for WhatsApp exceptions."""

class WhatsAppNotReady(WhatsAppError):
    """Raised when WhatsApp Web is not ready."""

class SessionExpired(WhatsAppError):
    """Raised when the session is expired or invalid."""

class ContactNotFound(WhatsAppError):
    """Raised when a contact cannot be found."""

class ChatNotFound(WhatsAppError):
    """Raised when a chat cannot be opened."""

class MessageSendError(WhatsAppError):
    """Raised when a message fails to send."""

class ElementNotFound(WhatsAppError):
    """Raised when a UI element is not found."""

class AuthenticationRequired(WhatsAppError):
    """Raised when authentication is required."""
