from django.conf import settings
from django.db import models


class Campaign(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_campaigns')
    active_ruleset = models.ForeignKey(
        'rulesets.Ruleset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_for_campaigns',
    )
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through='CampaignMembership', related_name='campaigns')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CampaignMembership(models.Model):
    class Role(models.TextChoices):
        DM = 'DM', 'Dungeon Master'
        PLAYER = 'PLAYER', 'Player'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campaign_memberships')
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'campaign')

    def __str__(self):
        return f'{self.user} in {self.campaign} ({self.role})'
