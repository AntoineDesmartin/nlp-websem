"""
Script de démarrage pour l'application TourGuide Paris
"""
import uvicorn

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🗼 TourGuide Paris - Assistant Touristique Intelligent")
    print("="*60)
    print("\n📍 Ouvre ton navigateur : http://localhost:8000")
    print("📚 Documentation API : http://localhost:8000/docs")
    print("\nAppuie sur Ctrl+C pour arrêter l'application")
    print("="*60 + "\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
