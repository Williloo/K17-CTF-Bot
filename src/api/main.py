"""
FastAPI web interface for K17 CTF Bot control panel
Communicates with the bot via IPC to manage leaderboards
"""

from fastapi import FastAPI, HTTPException, Depends, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import sys
import os
from typing import Optional
import secrets
from datetime import datetime, timedelta

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

# Authentication configuration
WEB_USERNAME = os.getenv('WEB_USERNAME', 'admin')
WEB_PASSWORD = os.getenv('WEB_PASSWORD', 'changeme')

# Session storage (in-memory, will reset on restart)
active_sessions = {}  # {session_token: expiry_time}

def create_session() -> str:
    """Create a new session token"""
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=24)
    active_sessions[token] = expiry
    return token

def verify_session(session_token: Optional[str] = Cookie(None)) -> bool:
    """Verify if session token is valid"""
    if not session_token:
        return False
    
    expiry = active_sessions.get(session_token)
    if not expiry:
        return False
    
    if datetime.now() > expiry:
        # Session expired
        del active_sessions[session_token]
        return False
    
    return True

def require_auth(session_token: Optional[str] = Cookie(None)):
    """Dependency to require authentication"""
    if not verify_session(session_token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True

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
    forum_channel_id: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

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
async def root(session_token: Optional[str] = Cookie(None)):
    """Serve login page or main interface based on authentication"""
    if verify_session(session_token):
        return FileResponse("/app/frontend/index.html")
    return FileResponse("/app/frontend/login.html")

@app.post("/api/login")
async def login(request: LoginRequest):
    """Authenticate user and create session"""
    if request.username == WEB_USERNAME and request.password == WEB_PASSWORD:
        token = create_session()
        response = JSONResponse({"status": "success", "message": "Login successful"})
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            max_age=86400,  # 24 hours
            samesite="lax"
        )
        return response
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

@app.post("/api/logout")
async def logout(session_token: Optional[str] = Cookie(None)):
    """Logout user and invalidate session"""
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]
    response = JSONResponse({"status": "success", "message": "Logged out"})
    response.delete_cookie("session_token")
    return response

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/api/cache")
async def get_cache(authenticated: bool = Depends(require_auth)):
    """Get the entire cache from the bot"""
    response = await IPCClient.send_request("get_cache")
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

@app.get("/api/cache/{message_id}")
async def get_cache_message(message_id: int, authenticated: bool = Depends(require_auth)):
    """Get a specific message from cache"""
    response = await IPCClient.send_request("get_cache_message", message_id=message_id)
    if response.get("status") == "error":
        raise HTTPException(status_code=404, detail=response.get("message"))
    return response

@app.post("/api/update-counter")
async def update_counter(request: UpdateCounterRequest, authenticated: bool = Depends(require_auth)):
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
async def trigger_update(authenticated: bool = Depends(require_auth)):
    """Manually trigger leaderboard update"""
    response = await IPCClient.send_request("trigger_update")
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

@app.post("/api/reload-cache")
async def reload_cache(authenticated: bool = Depends(require_auth)):
    """Reload cache from database"""
    response = await IPCClient.send_request("reload_cache")
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

@app.post("/api/create-message")
async def create_message(request: CreateMessageRequest, authenticated: bool = Depends(require_auth)):
    """Create a new tracked message in a channel"""
    response = await IPCClient.send_request(
        "create_message",
        channel_id=int(request.channel_id),  # Convert string to int for bot
        message_type=request.message_type,
        initial_counter=request.initial_counter,
        ctfd_domain=request.ctfd_domain,
        ctfd_api_key=request.ctfd_api_key,
        forum_channel_id=int(request.forum_channel_id) if request.forum_channel_id else 0
    )
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("message"))
    return response

@app.get("/api/tracked-messages")
async def get_tracked_messages(authenticated: bool = Depends(require_auth)):
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
