from .models import DNDOption


def search_options(*, option_types=None, traits=None):
    queryset = DNDOption.objects.all()
    if option_types:
        queryset = queryset.filter(option_type__in=option_types)
    if traits:
        queryset = queryset.filter(traits__contains=traits)
    return queryset
