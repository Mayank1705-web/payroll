#Automated Payroll Processing System
1. Install required packages:
   pip install -r requirements.txt 
2. Start the server from the root directory:
   uvicorn app.main:app --reload
3. Access interactive API documentation:
   http://127.0.0.1:8000/docs
#API Endpoints
POST/payroll/upload - Upload Payroll
Request URL: http://127.0.0.1:8000/payroll/upload
Server response:
Code	Details: 202	
Response body
{
  "message": "Payroll file accepted for processing",
  "job_id": 1,
  "status": "PENDING",
  "total_rows": 4
}

GET/payroll/jobs/{job_id} - Get Job Status
Request URL: http://127.0.0.1:8000/payroll/jobs/1
Server response:
Code	Details: 200	
Response body
{
  "job_id": 1,
  "payroll_month": "2026-10",
  "status": "COMPLETED",
  "total_rows": 4,
  "processed_rows": 4,
  "success_count": 4,
  "failed_count": 0,
  "error_summary": null
}
GET/payroll/jobs/{job_id}/results - Get Job Results
Request URL: http://127.0.0.1:8000/payroll/jobs/1/results
Server response:
Code	Details: 200	
Response body
{
  "job_id": 1,
  "status": "COMPLETED",
  "total_rows": 4,
  "processed_rows": 4,
  "success_count": 4,
  "failed_count": 0,
  "results": [
    {
      "employee_id": "E101",
      "name": "Rahul",
      "payroll_month": "2026-10",
      "monthly_salary": "60000.00",
      "working_days": 22,
      "present_days": 20,
      "bonus": "5000.00",
      "net_salary": "59545.45"
    },
    {
      "employee_id": "E102",
      "name": "Priya",
      "payroll_month": "2026-10",
      "monthly_salary": "80000.00",
      "working_days": 22,
      "present_days": 22,
      "bonus": "10000.00",
      "net_salary": "90000.00"
    },
    {
      "employee_id": "E103",
      "name": "Amit",
      "payroll_month": "2026-10",
      "monthly_salary": "45000.00",
      "working_days": 22,
      "present_days": 18,
      "bonus": "2000.00",
      "net_salary": "38818.18"
    },
    {
      "employee_id": "E104",
      "name": "Neha",
      "payroll_month": "2026-10",
      "monthly_salary": "70000.00",
      "working_days": 22,
      "present_days": 21,
      "bonus": "3000.00",
      "net_salary": "69818.18"
    }
  ],
  "errors": []
}
GET/payroll/jobs/{job_id}/download - Download Payroll
Request URL: http://127.0.0.1:8000/payroll/jobs/1/download
Server response:
Code	Details: 200	
Response body:
Download file
Response headers:
 content-disposition: attachment; filename="payroll_1.csv" 
 content-type: text/csv; charset=utf-8 
 date: Sat,10 Oct 2026 07:59:37 GMT 
 server: uvicorn 
 transfer-encoding: chunked 
