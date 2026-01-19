from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ==================== LIFESPAN (Startup / Shutdown safe) ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Safe lifespan for Railway"""
    print(f"🚀 [{datetime.now()}] Starting app...")
    try:
        from app.services.ai_service import cbc_prediction_service
        if hasattr(cbc_prediction_service, "is_available"):
            if cbc_prediction_service.is_available():
                cbc_prediction_service.load_model()
                print("✅ AI model loaded successfully")
            else:
                print("⚠️ AI features disabled (missing dependencies)")
    except Exception as e:
        print(f"⚠️ AI service warning: {e}")
    yield
    print(f"🛑 [{datetime.now()}] App shutdown complete")

# ==================== FASTAPI APP ====================
app = FastAPI(
    title=os.getenv("APP_NAME", "Blood Diagnosis System"),
    version=os.getenv("APP_VERSION", "1.0.0"),
    description="Blood Diagnosis System with AI-powered analysis",
    lifespan=lifespan
)

# ==================== TEMPLATES ====================
if os.path.isdir("app/templates"):
    templates = Jinja2Templates(directory="app/templates")
    print("✅ Templates directory found")
else:
    templates = None
    print("⚠️ Templates directory not found")

# ==================== STATIC FILES ====================
if os.path.isdir("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    print("✅ Static files mounted")
if os.path.isdir("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    print("✅ Uploads mounted")

# ==================== CORS ====================
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ==================== HEALTHCHECK + HOME PAGE ====================
if templates:
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        # تأكد إن عندك home.html
        return templates.TemplateResponse("home.html", {"request": request})
else:
    @app.get("/")
    async def home_fallback():
        return {
            "status": "ok",
            "service": "blood_diagnosis",
            "timestamp": datetime.now().isoformat(),
            "version": os.getenv("APP_VERSION", "1.0.0")
        }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ==================== EXCEPTION HANDLERS ====================
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    accept_header = request.headers.get("accept", "")
    if "application/json" in accept_header or not templates:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return templates.TemplateResponse(
        f"errors/{exc.status_code}.html",
        {"request": request, "detail": exc.detail},
        status_code=exc.status_code
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"🔥 Unhandled error: {exc}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

# ==================== ROUTERS ====================
try:
    from app.routers import auth, doctors, patients, admin, public

    app.include_router(public.router)
    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(admin.router, prefix="/api/admin")
    app.include_router(doctors.router, prefix="/api/doctors")
    app.include_router(patients.router, prefix="/api/patients")
    print("✅ All routers loaded")
except Exception as e:
    print(f"⚠️ Router load failed: {e}")
    @app.get("/api/test")
    async def api_test():
        return {"message": "API running in fallback mode"}
