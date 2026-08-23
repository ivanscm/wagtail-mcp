from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.api import APIField
from wagtail.fields import RichTextField
from wagtail.models import Page
from wagtail.snippets.models import register_snippet


class ContentPage(Page):
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("body")]

    api_fields = [APIField("body")]


@register_snippet
class Person(models.Model):
    name = models.CharField(max_length=255)

    panels = [FieldPanel("name")]

    api_fields = [APIField("name")]

    def __str__(self):
        return self.name
