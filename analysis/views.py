from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .Handlers import analysis_handler

class StatusCheck(APIView):    
    def post(self, request):
        return Response({"success": True, "message": "Students System Working."}, status=status.HTTP_200_OK)

# In your views.py file
import logging

# It's good practice to log errors for debugging
logger = logging.getLogger(__name__)

class AnalysisView(APIView):
    def post(self, request):
        try:
            pdf_file = request.FILES.get('marksheet')
            if not pdf_file:
                return Response({"success": False, "message": "No PDF uploaded."}, status=status.HTTP_400_BAD_REQUEST)

            # Call the handler
            results, json_path, excel_path = analysis_handler.extract_result(file=pdf_file)

            return Response({
                "success": True,
                "message": "Analysis completed.",
                "results": results,
                "json_file": json_path,
                "excel_file": excel_path
            }, status=status.HTTP_200_OK)

        except Exception as e:
            # Log the full traceback for your own debugging
            logger.error(f"Error during PDF analysis: {e}", exc_info=True)
            
            # Return a clean JSON error response to the client
            return Response({
                "success": False,
                "message": f"An error occurred during analysis: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

