user_languages = {}
subscribed_users = set()


def set_user_language(chat_id: int, language: str):
    user_languages[chat_id] = language


def get_user_language(chat_id: int):
    return user_languages.get(chat_id)


def subscribe_user(chat_id: int):
    subscribed_users.add(chat_id)


def unsubscribe_user(chat_id: int):
    subscribed_users.discard(chat_id)


def is_user_subscribed(chat_id: int) -> bool:
    return chat_id in subscribed_users


def get_all_subscribed_users():
    return subscribed_users