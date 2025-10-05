from django.urls import path
from .views import *

urlpatterns = [
    path('status-check/', StatusCheck.as_view(), name='analysis'),
    path('get-analysis-data/', AnalysisView.as_view(), name='analysis'),

    path('get-single-pdf-percentage-analysis-data/', SinglePDFPercentageAnalysisView.as_view(), name='single_pdf_percentage_analysis'),
    path('get-multiple-pdf-percentage-analysis-data/', MultiplePDFPercentageAnalysisView.as_view(), name='multiple_pdf_percentage_analysis'),

    path('get-kt-students/', ProcessExcelView.as_view(), name='process-excel'),
    path('pass-fail-analysis/', PassFailAnalysisView.as_view(), name='pass_fail_analysis'),
    path('average-semesters/', AverageSemestersView.as_view(), name='average_semesters'),

]
