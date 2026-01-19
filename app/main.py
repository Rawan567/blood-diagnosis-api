from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ==================== LIFESPAN FIXED ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler - SAFE VERSION for Railway"""
    # Startup - بدون crash
    print(f"🚀 [{datetime.now()}] Starting Blood Diagnosis System...")
    
    # محاولة تحميل الـ AI بدون فشل
    try:
        print("🤖 Attempting to load AI services...")
        from app.services.ai_service import cbc_prediction_service
        
        if hasattr(cbc_prediction_service, 'is_available'):
            if cbc_prediction_service.is_available():
                cbc_prediction_service.load_model()
                print("✅ AI prediction model loaded successfully")
            else:
                print("⚠️ AI prediction features disabled (missing dependencies)")
        else:
            print("⚠️ cbc_prediction_service structure unexpected")
            
    except ImportError as e:
        print(f"⚠️ AI import warning: {e}")
        # مش خطأ قاتل، التطبيق يكمل
    except Exception as e:
        print(f"⚠️ AI setup warning: {e}")
        # مش خطأ قاتل
    
    print("✅ Application startup completed")
    
    yield  # التطبيق شغال هنا
    
    # Shutdown
    print(f"🛑 [{datetime.now()}] Shutting down...")
    # أي cleanup هنا في المستقبل

# ==================== FASTAPI APP ====================
app = FastAPI(
    title=os.getenv("APP_NAME", "Blood Diagnosis System"),
    version=os.getenv("APP_VERSION", "1.0.0"),
    description="Blood Diagnosis System with AI-powered analysis",
    lifespan=lifespan  # استخدم الـ lifespan المعدل
)

# ==================== HEALTH CHECK (للـ Railway) ====================
@app.get("/")
async def root_healthcheck():
    """Health check endpoint for Railway"""
    return {
        "status": "ok",
        "service": "blood_diagnosis",
        "timestamp": datetime.now().isoformat(),
        "version": os.getenv("APP_VERSION", "1.0.0")
    }

@app.get("/health")
async def health_check():
    """Additional health endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ==================== DEBUG ENDPOINTS ====================
@app.get("/debug/imports")
async def debug_imports():
    """Check if all imports work"""
    results = {}
    
    modules_to_test = [
        ("fastapi", "fastapi"),
        ("starlette", "starlette"),
        ("sqlalchemy", "sqlalchemy"),
        ("pandas", "pandas"),
        ("sklearn", "sklearn"),
        ("numpy", "numpy"),
    ]
    
    for name, module in modules_to_test:
        try:
            __import__(module)
            results[name] = "✅ OK"
        except ImportError as e:
            results[name] = f"❌ {str(e)}"
    
    # Test app imports
    try:
        from app.routers import auth
        results["app.routers.auth"] = "✅ OK"
    except Exception as e:
        results["app.routers.auth"] = f"❌ {str(e)}"
    
    try:
        from app.services import ai_service
        results["app.services.ai_service"] = "✅ OK"
    except Exception as e:
        results["app.services.ai_service"] = f"❌ {str(e)}"
    
    return results

@app.get("/debug/info")
async def debug_info():
    """System information"""
    import sys
    import platform
    
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "current_directory": os.getcwd(),
        "files_in_root": os.listdir(".")[:10],
        "environment": {k: v for k, v in os.environ.items() if 'KEY' not in k and 'SECRET' not in k}
    }

# ==================== TEMPLATES SETUP ====================
# Initialize templates
if os.path.isdir("app/templates"):
    templates = Jinja2Templates(directory="app/templates")
    print("✅ Templates directory found")
else:
    templates = None
    print("⚠️ Templates directory not found")

# ==================== CORS CONFIGURATION ====================
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== STATIC FILES ====================
if os.path.isdir("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    print("✅ Static files mounted")

if os.path.isdir("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    print("✅ Uploads directory mounted")

# ==================== EXCEPTION HANDLERS ====================
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    accept_header = request.headers.get("accept", "")
    
    # Handle JSON requests
    if "application/json" in accept_header:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    
    # Handle HTML requests (if templates available)
    if templates:
        error_template = f"errors/{exc.status_code}.html"
        if os.path.exists(os.path.join("app/templates", error_template)):
            return templates.TemplateResponse(
                error_template,
                {"request": request, "detail": exc.detail},
                status_code=exc.status_code
            )
    
    # Fallback
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    import traceback
    
    error_details = {
        "error": str(exc),
        "type": type(exc).__name__,
        "timestamp": datetime.now().isoformat()
    }
    
    # Log the error
    print(f"🔥 Unhandled error: {exc}")
    traceback.print_exc()
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            **error_details
        }
    )

# ==================== ROUTERS (مع Import Safe) ====================
print("🔄 Setting up routers...")

# حاول تحمل الـ routers، لو فشل التطبيق يكمل بدونهم
try:
    from app.routers import auth, doctors, patients, admin, public
    
    app.include_router(public.router, prefix="", tags=["public"])
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    app.include_router(doctors.router, prefix="/api/doctors", tags=["doctors"])
    app.include_router(patients.router, prefix="/api/patients", tags=["patients"])
    
    print("✅ All routers loaded successfully")
    
except ImportError as e:
    print(f"⚠️ Router import failed: {e}")
    print("⚠️ Running in API-only mode (no routers)")
    
    # أبسط routes للـ API
    @app.get("/api/test")
    async def api_test():
        return {"message": "API is working", "routers": "disabled"}
    
except Exception as e:
    print(f"⚠️ Router setup error: {e}")

# ==================== STARTUP MESSAGE ====================
print(f"✅ FastAPI app created successfully at {datetime.now()}")
print(f"✅ App title: {app.title}")
print(f"✅ Debug endpoints: /debug/imports, /debug/info")
print(f"✅ Health check: /, /health")

# ==================== LOCAL RUN SUPPORT ====================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting server on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)