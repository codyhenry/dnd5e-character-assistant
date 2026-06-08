from __future__ import annotations

from copy import deepcopy


def normalize_json_path(path: str) -> str:
    return path.strip()


def _tokenize(path: str) -> list[str | int]:
    normalized = normalize_json_path(path)
    if not normalized:
        raise ValueError('Path cannot be empty.')

    tokens: list[str | int] = []
    i = 0
    expect_segment = True

    while i < len(normalized):
        if normalized[i] == '.':
            if expect_segment:
                raise ValueError('Invalid dot placement in path.')
            expect_segment = True
            i += 1
            continue

        key_start = i
        while i < len(normalized) and normalized[i] not in '.[':
            if normalized[i] == ']':
                raise ValueError('Unexpected closing bracket in path.')
            i += 1

        key = normalized[key_start:i]
        if not key:
            raise ValueError('Object keys in path cannot be empty.')
        tokens.append(key)
        expect_segment = False

        while i < len(normalized) and normalized[i] == '[':
            close_index = normalized.find(']', i)
            if close_index == -1:
                raise ValueError('Missing closing bracket in path.')
            index_text = normalized[i + 1:close_index]
            if not index_text.isdigit():
                raise ValueError('List index must be a non-negative integer.')
            tokens.append(int(index_text))
            i = close_index + 1
            expect_segment = False

    if expect_segment:
        raise ValueError('Path cannot end with a dot.')

    if not tokens:
        raise ValueError('Path cannot be empty.')

    for token in tokens:
        if isinstance(token, str) and token.strip() == '':
            raise ValueError('Object keys in path cannot be empty.')

    return tokens


def validate_json_path(path: str) -> bool:
    try:
        _tokenize(path)
        return True
    except ValueError:
        return False


def get_value_at_path(data: dict | list, path: str):
    current = data
    for token in _tokenize(path):
        if isinstance(token, int):
            if not isinstance(current, list):
                raise KeyError(f'Expected list while reading index {token}.')
            current = current[token]
            continue

        if not isinstance(current, dict):
            raise KeyError(f'Expected object while reading key {token}.')
        current = current[token]
    return current


def _resolve_parent(data: dict | list, path: str):
    tokens = _tokenize(path)
    if len(tokens) == 1:
        return data, tokens[0]

    parent_tokens = tokens[:-1]
    last_token = tokens[-1]
    current = data
    for token in parent_tokens:
        if isinstance(token, int):
            if not isinstance(current, list):
                raise KeyError(f'Expected list while reading index {token}.')
            current = current[token]
            continue

        if not isinstance(current, dict):
            raise KeyError(f'Expected object while reading key {token}.')
        if token not in current:
            raise KeyError(f'Key {token} not found.')
        current = current[token]

    return current, last_token


def set_value_at_path(data: dict | list, path: str, value):
    result = deepcopy(data)
    parent, last_token = _resolve_parent(result, path)

    if isinstance(last_token, int):
        if not isinstance(parent, list):
            raise KeyError('Target parent is not a list.')
        parent[last_token] = value
    else:
        if not isinstance(parent, dict):
            raise KeyError('Target parent is not an object.')
        parent[last_token] = value
    return result


def remove_value_at_path(data: dict | list, path: str):
    result = deepcopy(data)
    parent, last_token = _resolve_parent(result, path)

    if isinstance(last_token, int):
        if not isinstance(parent, list):
            raise KeyError('Target parent is not a list.')
        parent.pop(last_token)
    else:
        if not isinstance(parent, dict):
            raise KeyError('Target parent is not an object.')
        if last_token not in parent:
            raise KeyError(f'Key {last_token} not found.')
        del parent[last_token]

    return result


def add_value_at_path(data: dict | list, path: str, value):
    result = deepcopy(data)
    parent, last_token = _resolve_parent(result, path)

    if isinstance(last_token, int):
        if not isinstance(parent, list):
            raise KeyError('Target parent is not a list.')
        if last_token > len(parent):
            raise IndexError('List index is out of range for add operation.')
        parent.insert(last_token, value)
    else:
        if not isinstance(parent, dict):
            raise KeyError('Target parent is not an object.')
        parent[last_token] = value

    return result
