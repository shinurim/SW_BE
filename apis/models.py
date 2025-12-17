from django.db import models
from django.db.models import JSONField

class UserData(models.Model):
    uuid = models.IntegerField(null=True, blank=True)
    user_id = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    email =  models.CharField(max_length=200, blank=True, null=True)
    keywords = models.CharField(max_length=200, blank=True, null=True)
    
    class Meta:
        db_table = "users"
    

class SegmentHistory(models.Model):
    user_id = models.CharField(max_length=100, blank=True, null=True)
    segment_name = models.CharField(max_length=255)
    user_input = models.TextField(blank=True, null=True)
    main = models.CharField(max_length=50, blank=True, null=True)
    sub  = models.CharField(max_length=50, blank=True, null=True)
    stage3 = models.JSONField()
    insight = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "segment_history"

    def __str__(self):
        return f"{self.segment_name} ({self.id})"