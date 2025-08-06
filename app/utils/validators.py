# app/utils/validators.py
def require_keys(payload: dict, keys: list[str]):
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary")
    for key in keys:
        if key not in payload:
            raise KeyError(f"Missing required key in payload: {key}")
