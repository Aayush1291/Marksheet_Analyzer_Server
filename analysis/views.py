from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .Handlers import analysis_handler, PDFPercentageAnalyzer, excel_handler
import os
import uuid
from django.conf import settings   
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

class SinglePDFPercentageAnalysisView(APIView):
    def post(self, request):
        try:
            pdf_file = request.FILES.get('marksheet')
            if not pdf_file:
                return Response({"success": False, "message": "No PDF uploaded."}, status=400)

            results, json_url, excel_url = analysis_handler.analyze_pdf_percentage(pdf_file)

            return Response({
                "success": True,
                "message": "Percentage analysis completed.",
                "results": results,
                "json_file": json_url,
                "excel_file": excel_url
            })
        except Exception as e:
            return Response({
                "success": False,
                "message": f"An error occurred: {str(e)}"
            }, status=500)

class MultiplePDFPercentageAnalysisView(APIView):
    """Multiple PDF percentage analysis (SEM1 + SEM2 merge)"""
    
    def post(self, request):
        try:
            sem1_file = request.FILES.get('sem1_pdf')
            sem2_file = request.FILES.get('sem2_pdf')
            
            if not sem1_file or not sem2_file:
                return Response({
                    "success": False,
                    "message": "Both SEM1 and SEM2 PDFs are required."
                }, status=400)

            # Validate file types
            if not sem1_file.name.endswith('.pdf') or not sem2_file.name.endswith('.pdf'):
                return Response({
                    "success": False,
                    "message": "Only PDF files are allowed."
                }, status=400)

            results, json_url, excel_url = PDFPercentageAnalyzer.analyze_multiple_pdfs(
                sem1_file, 
                sem2_file
            )

            # Calculate statistics
            both_sems = sum(1 for r in results if r['Percentage Sem1'] is not None and r['Percentage Sem2'] is not None)
            only_sem1 = sum(1 for r in results if r['Percentage Sem1'] is not None and r['Percentage Sem2'] is None)
            only_sem2 = sum(1 for r in results if r['Percentage Sem1'] is None and r['Percentage Sem2'] is not None)

            return Response({
                "success": True,
                "message": "Multiple PDF analysis completed.",
                "results": results,
                "statistics": {
                    "total_students": len(results),
                    "both_semesters": both_sems,
                    "only_sem1": only_sem1,
                    "only_sem2": only_sem2
                },
                "json_file": json_url,
                "excel_file": excel_url
            })
            
        except Exception as e:
            return Response({
                "success": False,
                "message": f"An error occurred: {str(e)}"
            }, status=500)

class ProcessExcelView(APIView):
    def post(self, request, *args, **kwargs):
        # Check if file is present in request
        try:
            if 'file' not in request.FILES:
                return Response({'error': 'No file uploaded'}, status=400)
            uploaded_file = request.FILES['file']
            
            # Validate file extension
            if not uploaded_file.name.endswith('.xlsx'):
                return Response({'error': 'Only .xlsx files are allowed'}, status=400)            
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save input file
            input_filename = f"{file_id}_input.xlsx"
            input_path = os.path.join(upload_dir, input_filename)
            
            with open(input_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # Generate output filename
            output_filename = f"{file_id}.xlsx"
            output_path = os.path.join(upload_dir, output_filename)
            
            try:
                # Call main function from excel_handlers.py
                excel_handler.process_excel_main(input_path, output_path)
                
                # Generate the response URL
                excel_url = os.path.join(settings.MEDIA_URL, 'uploads', output_filename).replace("\\", "/")
                
                # Optionally delete input file
                if os.path.exists(input_path):
                    os.remove(input_path)

                return Response({'excel_file': excel_url}, status=200)            
            except Exception as e:
                return Response({'error': f'Error processing Excel file: {str(e)}'}, status=500)
        except Exception as e:
            return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

class PassFailAnalysisView(APIView):
    def post(self, request):
        try:
            if 'file' not in request.FILES:
                return Response({'error': 'No file uploaded'}, status=400)
            
            uploaded_file = request.FILES['file']
            
            # Validate file extension
            if not uploaded_file.name.endswith(('.xlsx', '.xls')):
                return Response({'error': 'Only Excel files are allowed'}, status=400)        
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            upload_dir_name = 'uploads'
            upload_dir = os.path.join(settings.MEDIA_ROOT, upload_dir_name)
            
            # Create upload directory if it doesn't exist
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save input file
            input_filename = f"{file_id}.xlsx"
            input_path = os.path.join(upload_dir, input_filename)
            
            with open(input_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            try:
                # Analyze pass/fail and generate chart
                chart_filename = f"{file_id}_chart.png"
                chart_path = os.path.join(upload_dir, chart_filename)
                
                chart_data = excel_handler.analyze_pass_fail(input_path, chart_path)
                
                # Generate response URL
                chart_url = os.path.join(settings.MEDIA_URL, upload_dir_name, chart_filename).replace("\\", "/")
                
                return Response({
                    "chart_url": chart_url,
                    "chart_data": chart_data
                }, status=200)
            
            except Exception as e:
                return Response({
                    "error": f"Error analyzing file: {str(e)}"
                }, status=500)
        except Exception as e:
            return Response({
                "error": f"An unexpected error occurred: {str(e)}"
            }, status=500)
        
class AverageSemestersView(APIView):
    def post(self, request):
        try:
        # Get all uploaded files with keys like 'file1', 'file2', etc.
            files_dict = request.FILES
            
            if not files_dict:
                return Response({"error": "No files provided"}, status=400)
            
            # Extract files in order
            uploaded_files = []
            file_keys = sorted([key for key in files_dict.keys() if key.startswith('file')])
            
            if len(file_keys) < 2:
                return Response({
                    "error": "At least 2 semester files are required"
                }, status=400)
            
            for key in file_keys:
                uploaded_files.append(files_dict[key])
            
            # Validate file extensions
            for uploaded_file in uploaded_files:
                if not uploaded_file.name.endswith(('.xlsx', '.xls')):
                    return Response({
                        "error": f"Invalid file format for {uploaded_file.name}. Only .xlsx and .xls are allowed."
                    }, status=400)
            
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            upload_dir_name = 'uploads'
            upload_dir = os.path.join(settings.MEDIA_ROOT, upload_dir_name)
            
            # Create upload directory if it doesn't exist
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save all input files
            input_paths = []
            for i, uploaded_file in enumerate(uploaded_files):
                input_filename = f"{file_id}_sem{i+1}.xlsx"
                input_path = os.path.join(upload_dir, input_filename)
                
                with open(input_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                input_paths.append(input_path)
            
            # Process and calculate average
            output_filename = f"{file_id}.xlsx"
            output_path = os.path.join(upload_dir, output_filename)
            
            try:
                excel_handler.calculate_semester_average(input_paths, output_path)
                
                # Generate response URL
                excel_url = os.path.join(settings.MEDIA_URL, upload_dir_name, output_filename).replace("\\", "/")
                
                return Response({
                    "excel_file": excel_url
                }, status=200)
            
            except Exception as e:
                return Response({
                    "error": f"Error processing files: {str(e)}"
                }, status=500)
        except Exception as e:
            return Response({
                "error": f"An unexpected error occurred: {str(e)}"
            }, status=500)
