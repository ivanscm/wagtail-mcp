from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.api import APIField
from wagtail.fields import RichTextField
from wagtail.models import DraftStateMixin, Page, RevisionMixin, TranslatableMixin
from wagtail.snippets.models import register_snippet


class ContentPage(Page):
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("body")]

    api_fields = [APIField("body", writable=True)]


@register_snippet
class Person(models.Model):
    name = models.CharField(max_length=255)

    panels = [FieldPanel("name")]

    api_fields = [APIField("name", writable=True)]

    def __str__(self):
        return self.name


@register_snippet
class DraftablePerson(DraftStateMixin, RevisionMixin, TranslatableMixin, models.Model):
    """A draftable, revisable and translatable snippet.

    Exercises the snippets action/revision endpoints (publish, unpublish,
    revert, copy_for_translation), which only exist for snippet models with the
    relevant mixins. ``writable=True`` on ``name`` is required so create/update
    payloads can set the field through the v3 API write schema.
    """

    name = models.CharField(max_length=255)

    panels = [FieldPanel("name")]

    api_fields = [APIField("name", writable=True)]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["translation_key", "locale"],
                name="unique_translation_key_locale_wagtail_mcp_test_draftableperson",
            )
        ]

    def __str__(self):
        return self.name
