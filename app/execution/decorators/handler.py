
def handler(action_name: str):
    """Декоратор для регистрации хендлера"""
    def decorator(cls):
        cls._action_name = action_name
        return cls
    return decorator