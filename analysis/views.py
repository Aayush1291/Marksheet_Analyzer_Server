from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .Handlers import analysis_handler

class StatusCheck(APIView):    
    def post(self, request):
        return Response({"success": True, "message": "Students System Working."}, status=status.HTTP_200_OK)


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
                "results": results,             # return parsed results directly
                "json_file": json_path,         # saved JSON path
                "excel_file": excel_path        # saved Excel path
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
