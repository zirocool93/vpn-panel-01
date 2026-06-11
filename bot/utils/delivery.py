"""Message delivery error helpers."""
from aiogram.exceptions import TelegramForbiddenError


def is_bot_blocked_error(error: Exception) -> bool:
    """Returns True for Telegram errors that mean the user blocked the bot."""
    return isinstance(error, TelegramForbiddenError)
