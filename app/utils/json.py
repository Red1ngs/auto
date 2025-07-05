import json
from pathlib import Path
from typing import Any


def read_json(path: str | Path, default: Any = None) -> Any:
    """
    Прочитать JSON-файл и вернуть данные.
    Если файл не существует — вернуть default или пустой dict.
    """
    path = Path(path)
    if not path.exists():
        return default if default is not None else {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(
    data: Any,
    path: str | Path,
    *,
    indent: int = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = False,
    overwrite: bool = True
) -> None:
    """
    Сохранить данные в JSON-файл.

    :param data: любые сериализуемые данные (dict, list и т.д.)
    :param path: путь до файла
    :param indent: отступы (по умолчанию 2)
    :param sort_keys: сортировка ключей
    :param ensure_ascii: экранировать юникод (по умолчанию False)
    :param overwrite: если False — выбросит ошибку, если файл уже существует
    """
    path = Path(path)
    if not overwrite and path.exists():
        raise FileExistsError(f"Файл уже существует: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
