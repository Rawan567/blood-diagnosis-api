from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ==================== LIFESPAN SAFE ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 [{datetime.now()}] Starting Blood Diagnosis System...")
    try:
        from app.services.ai_service import cbc_prediction_service
        if hasattr(cbc_prediction_service, "is_available") and cbc_prediction_service.is_available():
            cbc_prediction_service.load_model()
            print("✅ AI model loaded")
        else:
            print("⚠️ AI features disabled or missing dependencies")
    except Exception as e:
        print(f"⚠️ AI service failed: {e}")
    yield
    print(f"🛑 [{datetime.now()}] Application shutdown")

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

# ==================== HOME PAGE / HEALTHCHECK ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if templates and os.path.exists("app/templates/home.html"):
        return templates.TemplateResponse("home.html", {"request": request})
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
    if "application/json" in request.headers.get("accept", "") or not templates:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return templates.TemplateResponse(
        f"errors/{exc.status_code}.html",
        {"request": request, "detail": exc.detail},
        status_code=exc.status_code
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    print(f"🔥 Unhandled error: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
            "timestamp": datetime.now().isoformat()
        }
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
