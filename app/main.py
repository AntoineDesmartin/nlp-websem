"""
API FastAPI pour l'application TourGuide Paris
"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Ajouter le dossier parent au path
sys.path.append(str(Path(__file__).parent.parent))

from app.config import (
    KG_FILE, RECOMMENDATIONS_FILE, APP_TITLE, APP_VERSION,
    GRAPHRAG_MODE, OPENROUTER_API_KEY
)
from app.services.sparql_client import SPARQLClient
from app.services.reco_service import RecommendationService
from app.services.explain_service import ExplainService
from app.services.openrouter_service import OpenRouterSPARQLService
from app.services.embedding_service import EmbeddingGraphRAGService

# Initialisation de l'application
app = FastAPI(title=APP_TITLE, version=APP_VERSION)

# Monter les fichiers statiques
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Initialisation des services
print("🚀 Initialisation de TourGuide Paris...")
sparql_client = SPARQLClient(str(KG_FILE))
reco_service = RecommendationService(str(RECOMMENDATIONS_FILE))
explain_service = ExplainService()

# GraphRAG avec OpenRouter
print(f"📊 Mode GraphRAG: {GRAPHRAG_MODE}")
if GRAPHRAG_MODE == "openrouter":
    print(f"🤖 Provider LLM: OpenRouter (GPT-4o-mini)")
    try:
        openrouter_service = OpenRouterSPARQLService(api_key=OPENROUTER_API_KEY)
        print("✓ Service OpenRouter initialisé !")
    except ValueError as e:
        print(f"⚠️  OpenRouter non disponible: {e}")
        print("   → Mode 'patterns' sera utilisé par défaut")
        openrouter_service = None
else:
    openrouter_service = None

# GraphRAG Approche 2 : Embeddings
print("\n🧠 Initialisation de l'Approche 2 (Embeddings)...")
try:
    embedding_service = EmbeddingGraphRAGService(
        kg_file=str(KG_FILE),
        api_key=OPENROUTER_API_KEY
    )
    print("✓ Service Embeddings initialisé !")
except Exception as e:
    print(f"⚠️  Service Embeddings non disponible: {e}")
    embedding_service = None

print("✓ Tous les services sont prêts !")

# Modèles de données
class QuestionRequest(BaseModel):
    question: str
    mode: Optional[str] = None  # "patterns" ou "llm"

class QuestionResponse(BaseModel):
    query_type: str
    sparql: str
    explanation: str
    results: List[Dict[str, Any]]
    count: int
    mode: Optional[str] = None
    provider: Optional[str] = None

class NLResponse(BaseModel):
    """Réponse en langage naturel (Approche 2 embeddings)"""
    answer: str
    entities: List[Dict[str, Any]]
    approach: str
    error: bool = False

# Routes

@app.get("/")
async def root():
    """Page d'accueil - sert le fichier HTML"""
    return FileResponse("app/static/index.html")

@app.get("/api/stats")
async def get_stats():
    """Retourne des statistiques sur le graphe de connaissances"""
    return {
        "total_triples": len(sparql_client.graph),
        "total_tourists": len(reco_service.get_all_tourists()),
        "model_metrics": reco_service.get_metrics(),
        "graphrag_mode": GRAPHRAG_MODE,
        "llm_provider": "OpenRouter (GPT-4o-mini)" if GRAPHRAG_MODE == "openrouter" else None
    }

@app.post("/api/ask_nl", response_model=NLResponse)
async def ask_question_nl(request: QuestionRequest):
    """
    Endpoint GraphRAG Approche 2 : répond en langage naturel avec embeddings
    
    Exemple : "Quels sont les meilleurs restaurants ?"
    Retourne une réponse conversationnelle générée par IA
    """
    try:
        if not embedding_service:
            return NLResponse(
                answer="⚠️ Le service d'embeddings n'est pas disponible. Assure-toi que OPENROUTER_API_KEY est configurée.",
                entities=[],
                approach="embeddings",
                error=True
            )
        
        result = embedding_service.answer_question(request.question, top_k=5)
        
        if result.get("error"):
            return NLResponse(
                answer=result.get("answer", "Erreur lors de la génération de la réponse"),
                entities=[],
                approach="embeddings",
                error=True
            )
        
        return NLResponse(
            answer=result["answer"],
            entities=result["entities"],
            approach="embeddings",
            error=False
        )
    except HTTPException:
        raise
    except Exception as e:
        return NLResponse(
            answer=f"Erreur : {str(e)}",
            entities=[],
            approach="embeddings",
            error=True
        )

@app.post("/api/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """
    Endpoint principal : transforme une question en SPARQL et exécute la requête
    
    Exemple : "Quels sont les meilleurs restaurants ?"
    Mode : "patterns" (règles) ou "openrouter" (génération avec GPT-4o-mini)
    """
    try:
        # Choix du mode
        mode = request.mode or GRAPHRAG_MODE
        
        if mode == "openrouter" and openrouter_service:
            # Approche GraphRAG avec OpenRouter
            query_info = openrouter_service.question_to_sparql(request.question)
            
            if query_info.get("error"):
                raise HTTPException(status_code=500, detail=query_info.get("explanation"))
            
            # Exécuter la requête SPARQL générée
            results = sparql_client.query(query_info["sparql"])
            
            return QuestionResponse(
                query_type="openrouter_generated",
                sparql=query_info["sparql"],
                explanation=query_info["explanation"],
                results=results,
                count=len(results),
                mode="openrouter",
                provider=query_info.get("provider")
            )
        else:
            # Approche patterns (ancienne)
            query_info = explain_service.question_to_sparql(request.question)
            results = sparql_client.query(query_info["sparql"])
            
            return QuestionResponse(
                query_type=query_info["query_type"],
                sparql=query_info["sparql"],
                explanation=query_info["explanation"],
                results=results,
                count=len(results),
                mode="patterns",
                provider=None
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")

@app.get("/api/places/top")
async def get_top_places(limit: int = 10):
    """Récupère les lieux les mieux notés"""
    try:
        results = sparql_client.get_top_rated_places(limit)
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/places/type/{place_type}")
async def get_places_by_type(place_type: str):
    """Récupère les lieux par type (Restaurant, Attraction, POI)"""
    try:
        if place_type not in ["Restaurant", "Attraction", "POI"]:
            raise HTTPException(status_code=400, detail="Type invalide")
        results = sparql_client.get_places_by_type(place_type)
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/places/search")
async def search_places(q: str):
    """Recherche des lieux par nom"""
    try:
        results = sparql_client.search_places_by_name(q)
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/places/map")
async def get_places_map():
    """Récupère tous les lieux avec coordonnées pour affichage carte"""
    try:
        results = sparql_client.get_places_with_coordinates()
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/linked-data")
async def get_linked_data():
    """Récupère les informations sur les liens vers le web de données"""
    try:
        results = sparql_client.get_linked_data_info()
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recommendations/tourists")
async def get_tourists():
    """Liste tous les touristes disponibles"""
    try:
        tourists = reco_service.get_all_tourists()
        return {"tourists": tourists, "count": len(tourists)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recommendations/sample")
async def get_sample_recommendation():
    """Obtient une recommandation exemple"""
    try:
        sample_tourist = reco_service.get_sample_tourist()
        if not sample_tourist:
            raise HTTPException(status_code=404, detail="Aucun touriste trouvé")
        
        recommendations = reco_service.get_recommendations_for_tourist(sample_tourist, top_k=10)
        
        # Enrichir avec les infos des lieux
        enriched_recs = []
        for rec in recommendations:
            place_uri = rec["place_uri"]
            if place_uri:  # Vérifier que l'URI n'est pas None
                try:
                    place_details = sparql_client.get_place_details(place_uri)
                    enriched_recs.append({
                        **rec,
                        "place_name": place_details.get("name", place_details.get("http://www.w3.org/2000/01/rdf-schema#label", "Inconnu")),
                        "polarity": place_details.get("polarity", place_details.get("https://example.org/tourguide#polarity", "N/A"))
                    })
                except Exception as place_error:
                    # Si on ne peut pas récupérer les détails, on ajoute quand même la recommandation
                    enriched_recs.append({
                        **rec,
                        "place_name": "Lieu inconnu",
                        "polarity": "N/A"
                    })
        
        return {
            "tourist": sample_tourist,
            "recommendations": enriched_recs,
            "count": len(enriched_recs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recommendations/{tourist_id}")
async def get_recommendations(tourist_id: str, top_k: int = 10):
    """Récupère les recommandations pour un touriste spécifique"""
    try:
        # Le tourist_id doit être l'URI complète
        if not tourist_id.startswith("http"):
            tourist_id = f"https://example.org/tourguide#{tourist_id}"
        
        recommendations = reco_service.get_recommendations_for_tourist(tourist_id, top_k)
        
        if not recommendations:
            raise HTTPException(status_code=404, detail="Touriste non trouvé ou pas de recommandations")
        
        # Enrichir avec les infos des lieux
        enriched_recs = []
        for rec in recommendations:
            place_uri = rec["place_uri"]
            if place_uri:
                try:
                    place_details = sparql_client.get_place_details(place_uri)
                    enriched_recs.append({
                        **rec,
                        "place_name": place_details.get("name", place_details.get("http://www.w3.org/2000/01/rdf-schema#label", "Inconnu")),
                        "polarity": place_details.get("polarity", place_details.get("https://example.org/tourguide#polarity", "N/A"))
                    })
                except Exception:
                    enriched_recs.append({
                        **rec,
                        "place_name": "Lieu inconnu",
                        "polarity": "N/A"
                    })
        
        return {
            "tourist": tourist_id,
            "recommendations": enriched_recs,
            "count": len(enriched_recs)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🗼 TourGuide Paris - Assistant Touristique Intelligent")
    print("="*60)
    print("\n📍 Ouvre ton navigateur : http://localhost:8000")
    print("📚 Documentation API : http://localhost:8000/docs")
    print("\n" + "="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
