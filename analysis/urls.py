from django.urls import path
from .views import *

urlpatterns = [
    path('status-check/', StatusCheck.as_view(), name='analysis'),
    path('get-analysis-data/', AnalysisView.as_view(), name='analysis'),
]
