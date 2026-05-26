from .models import DNDOption


def create_option(**kwargs) -> DNDOption:
    return DNDOption.objects.create(**kwargs)
