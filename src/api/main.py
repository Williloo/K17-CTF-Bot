"""
FastAPI web interface for K17 CTF Bot control panel
Communicates with the bot via IPC to manage leaderboards
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sys
import os
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.ipc import IPCClient
from shared.database import DatabaseManager

app = FastAPI(title="K17 CTF Bot Control Panel")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
db = DatabaseManager()

# Models
class UpdateCounterRequest(BaseModel):
    message_id: str  # String to preserve large integer precision
    value: int

class CreateMessageRequest(BaseModel):
    channel_id: str  # String to preserve large integer precision
    message_type: str = 'counter'  # 'counter' or 'ctfd_tracker'
    initial_counter: int = 0
    ctfd_domain: Optional[str] = None
    ctfd_api_key: Optional[str] = None

@app.on_event("startup")
async def startup():
    """Initialize database connection"""
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    """Close database connection"""
    await db.close()

# API Endpoints

@app.get("/")
async def root():
    """Serve the main web interface"""
    return FileResponse("/app/frontend/index.html")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/api/cache")
async def get_cache():
    """Get the entire cache from the bot"""
    response = await IPCClient.send_request("get_cache")
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

@app.get("/api/cache/{message_id}")
async def get_cache_message(message_id: int):
    """Get a specific message from cache"""
    response = await IPCClient.send_request("get_cache_message", message_id=message_id)
    if response.get("status") == "error":
        raise HTTPException(status_code=404, detail=response.get("message"))
    return response

@app.post("/api/update-counter")
async def update_counter(request: UpdateCounterRequest):
    """Update a counter value"""
    response = await IPCClient.send_request(
        "update_counter",
        message_id=int(request.message_id),  # Convert string to int for bot
        value=request.value
    )
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

@app.post("/api/trigger-update")
async def trigger_update():
    """Manually trigger leaderboard update"""
    response = await IPCClient.send_request("trigger_update")
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

@app.post("/api/reload-cache")
async def reload_cache():
    """Reload cache from database"""
    response = await IPCClient.send_request("reload_cache")
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

@app.post("/api/create-message")
async def create_message(request: CreateMessageRequest):
    """Create a new tracked message in a channel"""
    response = await IPCClient.send_request(
        "create_message",
        channel_id=int(request.channel_id),  # Convert string to int for bot
        message_type=request.message_type,
        initial_counter=request.initial_counter,
        ctfd_domain=request.ctfd_domain,
        ctfd_api_key=request.ctfd_api_key
    )
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

@app.get("/api/tracked-messages")
async def get_tracked_messages():
    """Get all tracked messages from database"""
    messages = await db.get_tracked_messages(
        feature_type="ctf_leaderboard",
        is_active=True
    )
    return {
        "status": "success",
        "data": [dict(msg) for msg in messages]
    }

@app.get("/api/tracked-messages/{message_id}")
async def get_tracked_message(message_id: int):
    """Get a specific tracked message from database"""
    messages = await db.get_tracked_messages(is_active=True)
    for msg in messages:
        if msg['message_id'] == message_id:
            return {"status": "success", "data": dict(msg)}
    raise HTTPException(status_code=404, detail="Message not found")

class DeleteMessageRequest(BaseModel):
    message_id: str  # String to preserve large integer precision
    delete_discord_message: bool = True

@app.post("/api/delete-message")
async def delete_message(request: DeleteMessageRequest):
    """Delete a tracked message from database and optionally from Discord"""
    response = await IPCClient.send_request(
        "delete_message",
        message_id=int(request.message_id),
        delete_discord_message=request.delete_discord_message
    )
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

# Mount static files
app.mount("/static", StaticFiles(directory="/app/frontend"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
