from django.urls import path

from . import views
from .views import upload_and_analyze

urlpatterns = [
    path('upload/', upload_and_analyze, name='upload_and_analyze'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('', views.home, name='home'),
    path('create/', views.create_cv_page, name='create_cv_page'),

    # 2. PDF'i işleyecek API için YENİ bir adres tanımlıyoruz
    path('api/parse-pdf-for-edit/', views.parse_pdf_for_edit, name='parse_pdf_for_edit'),


    path('create/generate-summary/', views.generate_summary, name='generate-summary'),




]
