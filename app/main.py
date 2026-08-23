from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoint import ban, chat, device, location, media, message, role, websocket

app = FastAPI(title="ГИБДД-Очевидец API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(device.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(message.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(location.router, prefix="/api/v1")
app.include_router(websocket.router, prefix="/api/v1")
app.include_router(ban.router, prefix="/api/v1")
app.include_router(role.router, prefix="/api/v1")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "gibdd-backend", "version": "1.0.0"}
