import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
# Import your agent function from your agent.py file
from agent import run_recon_agent 

app = FastAPI(title="Autonomous Recon Agent API")

# Enable CORS so your Next.js frontend can talk to it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, swap with your actual Vercel/Next.js URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase Client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

class ScanRequest(BaseModel):
    domain: str

@app.get("/")
def home():
    return {"status": "Agent online and ready."}

@app.post("/api/scan")
def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    domain = request.domain.strip().lower()
    
    if not domain:
        raise HTTPException(status_code=400, detail="Domain cannot be empty.")
    
    try:
        # 1. Insert target into Supabase to get a target_id
        target_res = supabase.table("targets").insert({
            "domain": domain,
            "status": "scanning"
        }).execute()
        
        target_id = target_res.data[0]['id']
        
        # 2. Fire and forget: Offload the heavy AI agent reasoning to a background thread
        background_tasks.add_task(run_recon_agent, target_id, domain)
        
        # 3. Respond immediately to the frontend to prevent HTTP timeout
        return {
            "success": True,
            "message": f"Scan initiated successfully for {domain}.",
            "target_id": target_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))