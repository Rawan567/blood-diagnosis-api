# main.py (في جذر المشروع - بجانب app/)
"""
Entry point for Railway deployment
This file is in the ROOT directory, not inside app/
"""
import sys
import os
import traceback

print("=" * 60)
print("🚀 BLOOD DIAGNOSIS SYSTEM - STARTING")
print("=" * 60)
print(f"📁 Current directory: {os.getcwd()}")
print(f"📁 Files here: {os.listdir('.')}")
print(f"🐍 Python path: {sys.path[:3]}")

try:
    # استورد الـ app من app.main
    from app.main import app
    print("✅ SUCCESS: Imported FastAPI app from app.main")
    print(f"✅ App title: {app.title}")
    
except ImportError as e:
    print(f"❌ CRITICAL: Failed to import app from app.main")
    print(f"❌ Error: {e}")
    traceback.print_exc()
    print("\n🔍 Trying alternative imports...")
    
    # حاول طرق بديلة
    try:
        # أضف app directory إلى path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app.main import app
        print("✅ SUCCESS: Imported with modified path")
    except ImportError as e2:
        print(f"❌ All import attempts failed: {e2}")
        sys.exit(1)

# Debug endpoint خاص بملف الدخول
@app.get("/entry-point")
async def entry_point_info():
    return {
        "message": "This request went through the root main.py",
        "entry_file": __file__,
        "app_module": app.__module__
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🌐 Starting uvicorn on port {port}")
    print(f"🔗 Health check: http://localhost:{port}/")
    print(f"🔗 Debug: http://localhost:{port}/debug/imports")
    uvicorn.run(app, host="0.0.0.0", port=port)