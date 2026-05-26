def source_category_allowed(source_category: str, allowed_source_categories: list[str]) -> bool:
    if not allowed_source_categories:
        return True
    return source_category in allowed_source_categories
