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

# ==================== LIFESPAN ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler - Safe version for Railway"""
    print(f"🚀 [{datetime.now()}] Starting Blood Diagnosis System...")
    
    # Try to load AI services (non-critical)
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
            
    except Exception as e:
        print(f"⚠️ AI setup warning: {e}")
    
    print("✅ Application startup completed")
    
    yield
    
    print(f"🛑 [{datetime.now()}] Shutting down...")

# ==================== FASTAPI APP ====================
app = FastAPI(
    title=os.getenv("APP_NAME", "Blood Diagnosis System"),
    version=os.getenv("APP_VERSION", "1.0.0"),
    description="Blood Diagnosis System with AI-powered analysis",
    lifespan=lifespan
)

# ==================== TEMPLATES ====================
templates = Jinja2Templates(directory="app/templates") if os.path.isdir("app/templates") else None
print(f"✅ Templates: {'Found' if templates else 'Not Found'}")

# ==================== CORS ====================
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
    
    if "application/json" in accept_header:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    
    if templates:
        error_template = f"errors/{exc.status_code}.html"
        template_path = os.path.join("app/templates", error_template)
        
        if os.path.exists(template_path):
            return templates.TemplateResponse(
                error_template,
                {"request": request, "detail": exc.detail},
                status_code=exc.status_code
            )
    
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
    
    print(f"🔥 Unhandled error: {exc}")
    traceback.print_exc()
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", **error_details}
    )

# ==================== HEALTH CHECK ====================
@app.get("/health")
async def health_check():
    """Health check endpoint for Railway"""
    return {
        "status": "healthy",
        "service": "blood_diagnosis",
        "timestamp": datetime.now().isoformat(),
        "version": os.getenv("APP_VERSION", "1.0.0")
    }

# ==================== DEBUG ENDPOINTS ====================
@app.get("/debug/info")
async def debug_info():
    """System information"""
    import sys
    import platform
    
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "current_directory": os.getcwd(),
        "files_in_root": os.listdir(".")[:20],
        "templates_available": templates is not None,
        "static_mounted": os.path.isdir("app/static"),
        "uploads_mounted": os.path.isdir("uploads"),
    }

# ==================== ROUTERS ====================
print("🔄 Loading routers...")

routers_loaded = {
    "public": False,
    "auth": False,
    "admin": False,
    "doctors": False,
    "patients": False
}

# Try to import routers one by one (graceful failure)
try:
    from app.routers import public
    app.include_router(public.router, tags=["public"])
    routers_loaded["public"] = True
    print("✅ Public router loaded")
except Exception as e:
    print(f"⚠️ Public router failed: {e}")

try:
    from app.routers import auth
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    routers_loaded["auth"] = True
    print("✅ Auth router loaded")
except Exception as e:
    print(f"⚠️ Auth router failed: {e}")

try:
    from app.routers import admin
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    routers_loaded["admin"] = True
    print("✅ Admin router loaded")
except Exception as e:
    print(f"⚠️ Admin router failed: {e}")

try:
    from app.routers import doctors
    app.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
    routers_loaded["doctors"] = True
    print("✅ Doctors router loaded")
except Exception as e:
    print(f"⚠️ Doctors router failed: {e}")

try:
    from app.routers import patients
    app.include_router(patients.router, prefix="/patients", tags=["patients"])
    routers_loaded["patients"] = True
    print("✅ Patients router loaded")
except Exception as e:
    print(f"⚠️ Patients router failed: {e}")

# ==================== FALLBACK ROOT ====================
# إذا لم يتم تحميل public router، نعمل fallback
if not routers_loaded["public"]:
    @app.get("/")
    async def root_fallback(request: Request):
        """Fallback root endpoint"""
        if templates and os.path.exists("app/templates/public/index.html"):
            return templates.TemplateResponse(
                "public/index.html",
                {"request": request}
            )
        elif templates and os.path.exists("app/templates/index.html"):
            return templates.TemplateResponse(
                "index.html",
                {"request": request}
            )
        else:
            # إذا لم تكن هناك templates، نعرض صفحة HTML بسيطة
            return JSONResponse({
                "status": "ok",
                "message": "Blood Diagnosis System",
                "version": os.getenv("APP_VERSION", "1.0.0"),
                "routers_loaded": routers_loaded,
                "links": {
                    "api_docs": "/docs",
                    "health": "/health",
                    "debug": "/debug/info"
                }
            })

# ==================== STARTUP MESSAGE ====================
print(f"✅ FastAPI app ready at {datetime.now()}")
print(f"✅ Routers status: {routers_loaded}")
print(f"✅ Endpoints: /, /health, /docs, /debug/info")

# ==================== LOCAL RUN ====================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting server on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)