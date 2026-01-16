"""
Service GraphRAG Approche 2 : Embeddings + Génération de réponses en langage naturel
Utilise des embeddings pour trouver les entités pertinentes puis génère une réponse
"""
import os
import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Tuple
import requests
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS


class EmbeddingGraphRAGService:
    """
    Service qui utilise des embeddings pour répondre à des questions en langage naturel
    
    Workflow:
    1. Question → Embedding (vecteur)
    2. Recherche similarité avec entités du KG
    3. Extraction contexte des entités pertinentes
    4. Génération réponse en langage naturel avec GPT-4o-mini
    """
    
    def __init__(self, kg_file: str, api_key: str = None, embeddings_file: str = None):
        """
        Initialise le service d'embeddings
        
        Args:
            kg_file: Chemin vers le fichier RDF du graphe de connaissances
            api_key: Clé API OpenRouter pour génération de réponses
            embeddings_file: Chemin vers le fichier d'embeddings pré-calculés (optionnel)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY manquante")
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "openai/gpt-4o-mini"
        
        # Charger le graphe RDF
        print(f"📂 Chargement du graphe depuis {kg_file}...")
        self.graph = Graph()
        self.graph.parse(kg_file, format="turtle")
        print(f"✓ Graphe chargé : {len(self.graph)} triples")
        
        # Namespace
        self.tg = "https://example.org/tourguide#"
        
        # Embeddings
        self.embeddings_file = embeddings_file or "data/embeddings_cache.pkl"
        self.entity_embeddings = {}
        self.entity_info = {}
        
        # Charger ou générer les embeddings
        if Path(self.embeddings_file).exists():
            self._load_embeddings()
        else:
            print("⚠️  Pas d'embeddings en cache, ils seront générés à la demande")
    
    def _load_embeddings(self):
        """Charge les embeddings depuis le cache"""
        try:
            with open(self.embeddings_file, 'rb') as f:
                data = pickle.load(f)
                self.entity_embeddings = data['embeddings']
                self.entity_info = data['info']
            print(f"✓ {len(self.entity_embeddings)} embeddings chargés depuis le cache")
        except Exception as e:
            print(f"⚠️  Erreur chargement embeddings : {e}")
    
    def _save_embeddings(self):
        """Sauvegarde les embeddings dans le cache"""
        try:
            Path(self.embeddings_file).parent.mkdir(exist_ok=True)
            with open(self.embeddings_file, 'wb') as f:
                pickle.dump({
                    'embeddings': self.entity_embeddings,
                    'info': self.entity_info
                }, f)
            print(f"✓ {len(self.entity_embeddings)} embeddings sauvegardés")
        except Exception as e:
            print(f"⚠️  Erreur sauvegarde embeddings : {e}")
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """
        Génère un embedding pour un texte via OpenRouter
        
        Args:
            text: Texte à transformer en embedding
            
        Returns:
            Vecteur numpy de l'embedding
        """
        try:
            # Utiliser l'API d'embeddings d'OpenRouter (via text-embedding-3-small)
            response = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/text-embedding-3-small",
                    "input": text
                },
                timeout=30,
                verify=False
            )
            response.raise_for_status()
            
            embedding = response.json()['data'][0]['embedding']
            return np.array(embedding)
            
        except Exception as e:
            print(f"⚠️  Erreur génération embedding : {e}")
            # Fallback : embedding aléatoire normalisé
            vec = np.random.randn(1536)  # text-embedding-3-small = 1536 dimensions
            return vec / np.linalg.norm(vec)
    
    def _extract_entity_info(self, entity_uri: str) -> Dict[str, Any]:
        """
        Extrait les informations d'une entité du graphe
        
        Args:
            entity_uri: URI de l'entité
            
        Returns:
            Dict avec les propriétés de l'entité
        """
        entity = URIRef(entity_uri)
        info = {"uri": entity_uri}
        
        # Propriétés communes
        for prop in ["name", "polarity", "reviewCount", "category", "latitude", "longitude"]:
            prop_uri = URIRef(self.tg + prop)
            values = list(self.graph.objects(entity, prop_uri))
            if values:
                info[prop] = str(values[0])
        
        # Type (Restaurant, Attraction, POI)
        types = list(self.graph.objects(entity, RDF.type))
        if types:
            type_str = str(types[0]).replace(self.tg, "")
            info["type"] = type_str
        
        return info
    
    def _build_entity_text(self, info: Dict[str, Any]) -> str:
        """
        Construit une représentation textuelle d'une entité pour l'embedding
        
        Args:
            info: Informations de l'entité
            
        Returns:
            Texte décrivant l'entité
        """
        parts = []
        
        if "name" in info:
            parts.append(info["name"])
        
        if "type" in info:
            parts.append(f"Type: {info['type']}")
        
        if "category" in info:
            parts.append(f"Catégorie: {info['category']}")
        
        if "polarity" in info:
            parts.append(f"Note: {info['polarity']}")
        
        if "reviewCount" in info:
            parts.append(f"Avis: {info['reviewCount']}")
        
        return " | ".join(parts)
    
    def build_embeddings(self, limit: int = None):
        """
        Génère les embeddings pour toutes les entités du graphe
        
        Args:
            limit: Nombre max d'entités (None = toutes)
        """
        print("\n🔨 Génération des embeddings des entités...")
        
        # Récupérer toutes les entités de type Place
        query = f"""
        PREFIX tg: <{self.tg}>
        SELECT DISTINCT ?place
        WHERE {{
            ?place a tg:Place .
        }}
        """
        
        results = self.graph.query(query)
        entities = [str(row.place) for row in results]
        
        if limit:
            entities = entities[:limit]
        
        print(f"📊 {len(entities)} entités à traiter")
        
        for i, entity_uri in enumerate(entities, 1):
            if entity_uri in self.entity_embeddings:
                continue
            
            # Extraire infos
            info = self._extract_entity_info(entity_uri)
            text = self._build_entity_text(info)
            
            # Générer embedding
            embedding = self._get_embedding(text)
            
            # Stocker
            self.entity_embeddings[entity_uri] = embedding
            self.entity_info[entity_uri] = info
            
            if i % 10 == 0:
                print(f"   Progression : {i}/{len(entities)}")
        
        print(f"✓ {len(self.entity_embeddings)} embeddings générés")
        self._save_embeddings()
    
    def _find_similar_entities(self, question_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        """
        Trouve les entités les plus similaires à la question
        
        Args:
            question_embedding: Embedding de la question
            top_k: Nombre d'entités à retourner
            
        Returns:
            Liste de (uri, score, info) triée par similarité
        """
        if not self.entity_embeddings:
            return []
        
        similarities = []
        
        for entity_uri, entity_embedding in self.entity_embeddings.items():
            # Similarité cosinus
            similarity = np.dot(question_embedding, entity_embedding)
            similarities.append((entity_uri, similarity, self.entity_info[entity_uri]))
        
        # Trier par similarité décroissante
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def _generate_natural_response(self, question: str, similar_entities: List[Tuple[str, float, Dict]]) -> str:
        """
        Génère une réponse en langage naturel avec GPT-4o-mini
        
        Args:
            question: Question de l'utilisateur
            similar_entities: Entités pertinentes trouvées
            
        Returns:
            Réponse en français
        """
        # Construire le contexte
        context_parts = []
        for uri, score, info in similar_entities:
            name = info.get("name", "Inconnu")
            type_ = info.get("type", "Lieu")
            polarity = info.get("polarity", "N/A")
            review_count = info.get("reviewCount", "N/A")
            category = info.get("category", "N/A")
            
            context_parts.append(
                f"- {name} ({type_}): note {polarity}/1.0, {review_count} avis, catégorie {category}"
            )
        
        context = "\n".join(context_parts)
        
        # Prompt pour génération
        prompt = f"""Tu es un assistant touristique pour Paris. Réponds en français de manière naturelle et concise.

Question de l'utilisateur : {question}

Informations pertinentes du graphe de connaissances :
{context}

Génère une réponse en langage naturel qui répond à la question en utilisant ces informations.
Sois précis, mentionne les noms, les notes et donne des recommandations utiles.
"""
        
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                },
                timeout=60,
                verify=False
            )
            response.raise_for_status()
            
            answer = response.json()["choices"][0]["message"]["content"].strip()
            return answer
            
        except Exception as e:
            return f"Erreur lors de la génération de la réponse : {e}"
    
    def answer_question(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Répond à une question en langage naturel (méthode principale)
        
        Args:
            question: Question en français
            top_k: Nombre d'entités à considérer
            
        Returns:
            Dict avec la réponse et les métadonnées
        """
        print(f"\n❓ Question : {question}")
        
        # Si pas d'embeddings, générer un minimum
        if not self.entity_embeddings:
            print("⚠️  Génération des embeddings (première utilisation)...")
            self.build_embeddings(limit=50)  # Limiter pour le test
        
        # 1. Générer embedding de la question
        print("🔍 Génération de l'embedding de la question...")
        question_embedding = self._get_embedding(question)
        
        # 2. Trouver entités similaires
        print(f"🎯 Recherche des {top_k} entités les plus pertinentes...")
        similar_entities = self._find_similar_entities(question_embedding, top_k)
        
        if not similar_entities:
            return {
                "answer": "Désolé, je n'ai pas trouvé d'informations pertinentes dans le graphe.",
                "entities": [],
                "error": True
            }
        
        print(f"✓ {len(similar_entities)} entités trouvées")
        for uri, score, info in similar_entities[:3]:
            print(f"   - {info.get('name', 'N/A')} (score: {score:.3f})")
        
        # 3. Générer réponse en langage naturel
        print("💬 Génération de la réponse en langage naturel...")
        answer = self._generate_natural_response(question, similar_entities)
        
        return {
            "answer": answer,
            "entities": [
                {
                    "name": info.get("name", "Inconnu"),
                    "type": info.get("type", "Lieu"),
                    "score": float(score),
                    "info": info
                }
                for uri, score, info in similar_entities
            ],
            "error": False,
            "approach": "embeddings"
        }
