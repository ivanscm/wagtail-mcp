from blog.blocks import BaseStreamBlock
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import (
    FieldPanel,
    FieldRowPanel,
    InlinePanel,
    MultiFieldPanel,
    PageChooserPanel,
)
from wagtail.api import APIField
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page


class HomePage(Page):
    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Homepage image",
    )
    hero_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Write an introduction for the site",
    )
    hero_cta = models.CharField(
        verbose_name="Hero CTA",
        max_length=255,
        blank=True,
        help_text="Text to display on Call to Action",
    )
    hero_cta_link = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Hero CTA link",
        help_text="Choose a page to link to for the Call to Action",
    )

    body = StreamField(
        BaseStreamBlock(),
        verbose_name="Home content block",
        blank=True,
        use_json_field=True,
    )

    featured_section_3_title = models.CharField(
        blank=True,
        max_length=255,
        help_text="Heading for the blog featured section",
    )
    featured_section_3 = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Blog index page; up to six child posts are shown on the homepage.",
        verbose_name="Featured section (blog)",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("image"),
                FieldPanel("hero_text"),
                FieldPanel("hero_cta"),
                PageChooserPanel("hero_cta_link"),
            ],
            "Hero",
        ),
        FieldPanel("body"),
        MultiFieldPanel(
            [
                FieldPanel("featured_section_3_title"),
                PageChooserPanel("featured_section_3"),
            ],
            "Blog section",
        ),
    ]

    api_fields = [
        APIField("image", writable=True),
        APIField("hero_text", writable=True),
        APIField("hero_cta", writable=True),
        APIField("hero_cta_link", writable=True),
        APIField("body", writable=True),
        APIField("featured_section_3_title", writable=True),
        APIField("featured_section_3", writable=True),
    ]

    subpage_types = ["blog.BlogIndexPage", "home.FormPage"]


class FormField(AbstractFormField):
    page = ParentalKey("FormPage", on_delete=models.CASCADE, related_name="form_fields")


class FormPage(AbstractEmailForm):
    """Contact form, to exercise form-related tasks (fields, submissions)."""

    intro = RichTextField(blank=True)
    thank_you_text = RichTextField(blank=True)

    content_panels = AbstractEmailForm.content_panels + [
        FormSubmissionsPanel(),
        FieldPanel("intro"),
        InlinePanel("form_fields", label="Form fields"),
        FieldPanel("thank_you_text"),
        MultiFieldPanel(
            [
                FieldRowPanel(
                    [
                        FieldPanel("from_address"),
                        FieldPanel("to_address"),
                    ]
                ),
                FieldPanel("subject"),
            ],
            "Email",
        ),
    ]

    api_fields = [
        APIField("intro", writable=True),
        APIField("thank_you_text", writable=True),
    ]

    parent_page_types = ["home.HomePage"]
    subpage_types = []


@register_setting(icon="site")
class SocialMediaSettings(BaseSiteSetting):
    """Site-wide footer links, to exercise site settings tasks."""

    instagram = models.URLField(blank=True)
    mastodon = models.URLField(blank=True)
    footer_text = models.CharField(max_length=255, blank=True)
