from __future__ import annotations

from django.contrib.admin import SimpleListFilter
from django.db.models import Count, QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext as _


class FileCountListFilter(SimpleListFilter):
    """Filters on the number of files received for an eye exam.

    `file_count` is calculated from the related session files, not a
    model field, so the queryset is annotated before filtering.

    Counts of `max_count` or more are grouped into the last choice.
    """

    title = _("Files")
    parameter_name = "file_count"
    field_name = "files"
    max_count: int = 4

    def lookups(self, request: HttpRequest, model_admin) -> tuple[tuple[str, str], ...]:  # noqa: ARG002
        lookups: list[tuple[str, str]] = [("0", _("None"))]
        lookups.extend((str(count), str(count)) for count in range(1, self.max_count))
        lookups.append((self.gte_value, _("%(count)s or more") % {"count": self.max_count}))
        return tuple(lookups)

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:  # noqa: ARG002
        """Return the queryset filtered on the annotated file count.

        Unrecognized values are ignored, as they are for any other
        list filter.
        """
        value = self.value()
        if not value or value not in [tpl[0] for tpl in self.lookup_choices]:
            return queryset
        queryset = queryset.annotate(_file_count=Count(self.field_name, distinct=True))
        if value == self.gte_value:
            return queryset.filter(_file_count__gte=self.max_count)
        return queryset.filter(_file_count=int(value))

    @property
    def gte_value(self) -> str:
        return f"{self.max_count}+"
