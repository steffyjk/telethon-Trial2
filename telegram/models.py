from django.db import models
import django
django.setup()

class Contact(models.Model):
    session_id = models.CharField(max_length=36)
    user_id = models.BigIntegerField()
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name or ''} {self.last_name or ''}"

    class Meta:
        unique_together = ('session_id', 'user_id')

class Chat(models.Model):
    session_id = models.CharField(max_length=36)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='chats')
    message_id = models.BigIntegerField()
    message_text = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField()
    is_sent = models.BooleanField(default=False)

    class Meta:
        unique_together = ('session_id', 'contact', 'message_id')
        indexes = [models.Index(fields=['session_id', 'timestamp'])]

class Conversation(models.Model):
    session_id = models.CharField(max_length=36)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='conversations')
    dialog_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    last_message = models.TextField()
    timestamp = models.CharField(max_length=50)
    unread_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('session_id', 'contact', 'dialog_id')