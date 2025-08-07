from backend.firebase_config import db
from backend.agents import run_pipeline  # ✅ Import the agent pipeline
from datetime import datetime
import uuid
from fastapi import APIRouter, Form, File, UploadFile
from typing import List
from fastapi.responses import JSONResponse
import os
                
router = APIRouter()

UPLOAD_FOLDER = "backend/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ Final and only /report/ route
@router.post("/report/")
async def submit_report(
    category: str = Form(...),
    location: str = Form(...),
    description: str = Form(...),
    file: List[UploadFile] = File(...)
):
    try:
        # Step 1: AI pipeline
        agent_result = run_pipeline(category, location, description)

        # Step 2: Save media
        report_id = str(uuid.uuid4())
        saved_files = []
        for media in file:
            filename = f"{report_id}_{media.filename}"
            file_location = os.path.join(UPLOAD_FOLDER, filename)
            with open(file_location, "wb") as buffer:
                buffer.write(await media.read())
            saved_files.append(file_location)

        # Step 3: Store in Firestore
        report_data = {
            "report_id": report_id,
            "category": agent_result["category"],
            "location": agent_result["location"],
            "description": agent_result["description"],
            "classification": agent_result["classification"],
            "routing": agent_result["routing"],
            "authority_routing_agent": agent_result["authority_routing"],
            "suggestions": agent_result["suggestions"],
            "media_files": saved_files,
            "timestamp": agent_result["submitted_at"],
            "status": "Pending"
        }

        db.collection("incident_reports").document(report_id).set(report_data)

        return {
            "message": "Report saved with AI enrichment",
            "report_id": report_id,
            "ai_data": agent_result
        }

    except Exception as e:
        return {"error": str(e)}

# ✅ Get all reports
@router.get("/reports/")
async def get_all_reports():
    try:
        docs = db.collection("incident_reports").stream()
        all_reports = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            all_reports.append(data)
        return JSONResponse(content=all_reports)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
