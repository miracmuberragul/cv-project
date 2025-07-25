# analyzer/models.py
from django.db import models

class Resume(models.Model):

    pdf_file = models.FileField(upload_to='resumes/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    analysis_result = models.JSONField(null=True, blank=True)


    def __str__(self):
        return f"Resume - {self.user_id}"



class CV(models.Model):

    html_content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CV - {self.created_at.strftime('%Y-%m-%d %H:%M')}"