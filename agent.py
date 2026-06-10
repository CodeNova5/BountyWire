import os
from supabase import create_client, Client
from pydantic import BaseModel
from openai import OpenAI

# Initialize clients
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") # Use Service Role for backend writes
supabase: Client = create_client(supabase_url, supabase_key)

# Using OpenAI SDK pattern (works natively with OpenAI, Groq, or Mistral)
ai_client = OpenAI(
    base_url="https://api.groq.com/openai/v1", # Example: Using Groq for speed
    api_key=os.environ.get("GROQ_API_KEY")
)

class TakeoverAnalysis(BaseModel):
    is_vulnerable: bool
    confidence: str # 'High', 'Medium', 'Low'
    reasoning: str
    signature_found: str

def log_agent_thought(target_id: str, step: str, message: str, level: str = "info"):
    """Pushes the agent's current internal state to Supabase for the UI to stream."""
    supabase.table("agent_logs").insert({
        "target_id": target_id,
        "step_name": step,
        "log_level": level,
        "message": message
    }).execute()

def run_recon_agent(target_id: str, domain: str):
    # Step 1: Subdomain Discovery Simulation
    log_agent_thought(target_id, "Enumeration", f"Starting passive subdomain enumeration for {domain}...")
    
    # In a production agent, you'd run subfinder/assetfinder wrappers here.
    # For our hackathon MVP baseline, let's simulate finding a suspicious subdomain:
    mock_subdomain = f"dev-marketing.{domain}"
    mock_cname = "unclaimed-bucket.wordpress.com" 
    
    subdomain_row = supabase.table("subdomains").insert({
        "target_id": target_id,
        "subdomain": mock_subdomain,
        "cname": mock_cname,
        "http_status": 404
    }).execute()
    
    subdomain_id = subdomain_row.data[0]['id']
    
    # Step 2: Multi-step Reasoning via LLM
    log_agent_thought(target_id, "Analysis Loop", f"Analyzing CNAME record: {mock_cname} for {mock_subdomain}")
    
    prompt = f"""
    You are an expert Automated Bug Bounty Agent. Analyze this asset data:
    Subdomain: {mock_subdomain}
    CNAME: {mock_cname}
    HTTP Status: 404

    Determine if this asset is vulnerable to a Subdomain Takeover. 
    Provide your decision in a clear structured format.
    """
    
    # Structured outputs ensure our agent gives reliable evaluations
    completion = ai_client.beta.chat.completions.parse(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        response_format=TakeoverAnalysis,
    )
    
    analysis = completion.choices[0].message.parsed
    
    # Step 3: Verification & Escalation
    if analysis.is_vulnerable:
        log_agent_thought(
            target_id, 
            "Takeover Verification", 
            f"Vulnerability flagged with {analysis.confidence} confidence. Reasoning: {analysis.reasoning}", 
            level="warning"
        )
        
        # Write finding to Vulnerabilities table
        supabase.table("vulnerabilities").insert({
            "target_id": target_id,
            "subdomain_id": subdomain_id,
            "vuln_type": "Subdomain Takeover",
            "severity": "High" if analysis.confidence == "High" else "Medium",
            "evidence": f"CNAME: {mock_cname} returning 404. Agent Notes: {analysis.reasoning}"
        }).execute()
        
    log_agent_thought(target_id, "Completed", f"Finished evaluation loop for {domain}.")

# Example Execution
if __name__ == "__main__":
    # 1. Create a dummy target to test
    target_res = supabase.table("targets").insert({"domain": "examplecompany.com"}).execute()
    target_id = target_res.data[0]['id']
    
    # 2. Spin up the agent
    run_recon_agent(target_id, "examplecompany.com")