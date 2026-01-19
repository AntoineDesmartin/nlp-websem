"""
Service de recommandation basé sur les prédictions TransE
"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

class RecommendationService:
    def __init__(self, recommendations_file: str):
        """Initialise le service avec le fichier de recommandations"""
        print(f"Chargement des recommandations depuis {recommendations_file}...")
        with open(recommendations_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        # Extraire les recommandations par touriste
        # Le format est: {"recommendations": {"tourist_uri": [{"place": "...", "score": ...}]}}
        self.recommendations = self.data.get("recommendations", {})
        
        print(f"✓ {len(self.recommendations)} touristes avec recommandations")
    
    def get_all_tourists(self) -> List[str]:
        """Retourne la liste de tous les touristes"""
        return list(self.recommendations.keys())
    
    def find_tourist_by_profile(self, nationality: str, season: str, budget: str) -> Optional[str]:
        """
        Trouve un touriste correspondant au profil demandé
        
        Args:
            nationality: Code pays (US, GB, DE, IT, ES, FR, NL)
            season: Saison (spring, summer, autumn, winter)
            budget: Budget (budget, medium, luxury)
            
        Returns:
            URI du touriste correspondant ou None
        """
        # Mapping des codes pays vers les langues utilisées dans le KG
        nationality_to_language = {
            'US': 'english',
            'GB': 'english', 
            'DE': 'dutch',  # Approximation
            'IT': 'italian',
            'ES': 'spanish',
            'FR': 'french',
            'NL': 'dutch'
        }
        
        language = nationality_to_language.get(nationality, 'english')
        
        # Construire le pattern de recherche
        # Format: tourist_dutch_autumn_budget
        tourist_pattern = f"tourist_{language}_{season}_{budget}"
        
        # Chercher dans les URIs de touristes
        for tourist_uri in self.recommendations.keys():
            if tourist_pattern in tourist_uri:
                return tourist_uri
        
        # Si pas trouvé, essayer sans le budget (fallback)
        tourist_pattern_no_budget = f"tourist_{language}_{season}"
        for tourist_uri in self.recommendations.keys():
            if tourist_pattern_no_budget in tourist_uri:
                return tourist_uri
        
        return None
    
    def get_recommendations_for_tourist(self, tourist_uri: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Récupère les top-K recommandations pour un touriste"""
        if tourist_uri not in self.recommendations:
            return []
        
        predictions = self.recommendations[tourist_uri][:top_k]
        
        # Formater les résultats
        results = []
        for i, pred in enumerate(predictions):
            results.append({
                "place_uri": pred.get("place"),
                "score": pred.get("score"),
                "rank": i + 1
            })
        
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du modèle"""
        metrics = {}
        if "metrics_table" in self.data:
            for metric in self.data["metrics_table"]:
                key = f"{metric.get('Side', '')}_{metric.get('Metric', '')}"
                metrics[key] = metric.get("Value")
        
        return {
            "model": self.data.get("model", "TransE"),
            "relation": self.data.get("relation", "likesPlace"),
            "metrics": metrics
        }
    
    def get_sample_tourist(self) -> str:
        """Retourne un touriste exemple pour la démo"""
        tourists = self.get_all_tourists()
        if tourists:
            return tourists[0]
        return None
