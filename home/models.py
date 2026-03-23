import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models

# Create your models here.

# -----------------users registration-----------------
class userProfile(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    confirm_password = models.CharField(max_length=255)  # Not recommended to store, use validation
    mobile = models.CharField(max_length=15, unique=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    status = models.CharField(max_length=10,  default='waiting')

    def __str__(self):
        return self.name

    def set_password(self, raw_password: str) -> None:
        self.password = make_password(raw_password)
        self.confirm_password = ''

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)


class VoiceConversationSession(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(userProfile, on_delete=models.CASCADE, related_name='voice_sessions')
    language = models.CharField(max_length=20, default='te-IN')
    channel = models.CharField(max_length=20, default='voice')
    title = models.CharField(max_length=255, blank=True, default='')
    last_asr_confidence = models.FloatField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.name} - {self.session_id}"


class VoiceConversationTurn(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    )

    session = models.ForeignKey(VoiceConversationSession, on_delete=models.CASCADE, related_name='turns')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    message_text = models.TextField()
    normalized_text = models.TextField(blank=True, default='')
    source = models.CharField(max_length=20, default='text')
    language = models.CharField(max_length=20, default='te-IN')
    asr_confidence = models.FloatField(null=True, blank=True)
    intent = models.CharField(max_length=50, blank=True, default='')
    extracted_parameters = models.JSONField(default=dict, blank=True)
    predicted_crop = models.CharField(max_length=120, blank=True, default='')
    model_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role} @ {self.created_at:%Y-%m-%d %H:%M:%S}"

