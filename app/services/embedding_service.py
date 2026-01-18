"""
Service GraphRAG Approche 2 : Embeddings + Génération de réponses en langage naturel
Utilise des embeddings pour trouver les entités pertinentes puis génère une réponse
"""
import os
import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
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
        Extrait les informations ENRICHIES d'une entité du graphe
        
        Args:
            entity_uri: URI de l'entité
            
        Returns:
            Dict avec toutes les propriétés de l'entité (TourPedia + Schema.org + inférées)
        """
        entity = URIRef(entity_uri)
        info = {"uri": entity_uri}
        
        # Propriétés TourPedia de base
        tg_props = {
            "name": "name",
            "polarity": "polarity",
            "numReviews": "numReviews",  # Garder le nom original pour le frontend
            "category": "category",
            "lat": "latitude",
            "lng": "longitude",
            "address": "address"
        }
        
        for prop_name, info_key in tg_props.items():
            prop_uri = URIRef(self.tg + prop_name)
            values = list(self.graph.objects(entity, prop_uri))
            if values:
                # Pour polarity et numReviews : prendre la valeur maximale (ignorer les 0)
                if prop_name in ["polarity", "numReviews"]:
                    numeric_values = []
                    for v in values:
                        try:
                            num_val = float(str(v))
                            if num_val > 0:  # Ignorer les valeurs nulles
                                numeric_values.append(num_val)
                        except:
                            pass
                    if numeric_values:
                        info[info_key] = str(max(numeric_values))  # Prendre la valeur maximale
                    else:
                        # Si pas de valeurs > 0, prendre la première valeur quand même
                        info[info_key] = str(values[0])
                else:
                    info[info_key] = str(values[0])
        
        # Essayer rdfs:label si pas de tg:name
        if "name" not in info:
            label_uri = URIRef("http://www.w3.org/2000/01/rdf-schema#label")
            labels = list(self.graph.objects(entity, label_uri))
            if labels:
                info["name"] = str(labels[0])
        
        # Propriétés d'inférence (issues des règles SPARQL)
        inference_props = {
            "inferredRating": "inferredRating",
            "inferenceReason": "inferenceReason"
        }
        
        for prop_name, info_key in inference_props.items():
            prop_uri = URIRef(self.tg + prop_name)
            values = list(self.graph.objects(entity, prop_uri))
            if values:
                info[info_key] = str(values[0])
        
        # Types (classes de base + classes inférées)
        types = list(self.graph.objects(entity, RDF.type))
        type_list = []
        inferred_classes = []
        
        # Priorité des types (plus spécifique = priorité plus élevée)
        type_priority = {
            "Restaurant": 3,
            "Attraction": 3,
            "POI": 3,
            "HighlyRatedPlace": 2,
            "TopRestaurant": 2,
            "PopularPlace": 2,
            "HiddenGem": 2,
            "TrendingPlace": 2,
            "MustVisitAttraction": 2,
            "ConsistentQuality": 2,
            "Place": 1  # Type générique (priorité la plus basse)
        }
        
        for t in types:
            type_str = str(t).replace(self.tg, "")
            type_list.append(type_str)
            
            # Classes inférées spéciales
            if type_str in ["HighlyRatedPlace", "TopRestaurant", "PopularPlace", 
                           "HiddenGem", "TrendingPlace", "MustVisitAttraction", "ConsistentQuality"]:
                inferred_classes.append(type_str)
        
        # Sélectionner le type le plus spécifique (priorité la plus élevée)
        if type_list:
            type_list_sorted = sorted(type_list, key=lambda t: type_priority.get(t, 0), reverse=True)
            info["type"] = type_list_sorted[0]  # Type principal (plus spécifique)
            info["allTypes"] = ", ".join(type_list)
        
        if inferred_classes:
            info["inferredClasses"] = ", ".join(inferred_classes)
        
        # Compter les reviews Schema.org
        schema_review_count = len(list(self.graph.subjects(
            URIRef("http://schema.org/about"),
            entity
        )))
        if schema_review_count > 0:
            info["schemaReviews"] = str(schema_review_count)
        
        # Vérifier les liens externes (Wikidata/DBpedia)
        owl_same_as = URIRef("http://www.w3.org/2002/07/owl#sameAs")
        external_links = list(self.graph.objects(entity, owl_same_as))
        
        for link in external_links:
            link_str = str(link)
            if "wikidata.org" in link_str:
                info["wikidataLink"] = link_str
            elif "dbpedia.org" in link_str:
                info["dbpediaLink"] = link_str
        
        # Topics
        has_topic_uri = URIRef(self.tg + "hasTopic")
        topics = list(self.graph.objects(entity, has_topic_uri))
        if topics:
            topic_names = [str(t).split("#")[-1] for t in topics]
            info["topics"] = ", ".join(topic_names)
        
        return info
    
    def _build_entity_text(self, info: Dict[str, Any]) -> str:
        """
        Construit une représentation textuelle ENRICHIE d'une entité pour l'embedding
        
        Args:
            info: Informations de l'entité
            
        Returns:
            Texte descriptif riche pour embedding
        """
        parts = []
        
        # Nom
        if "name" in info:
            parts.append(f"Nom: {info['name']}")
        
        # Type principal
        if "type" in info:
            parts.append(f"Type: {info['type']}")
        
        # Classes inférées (badges de qualité)
        if "inferredClasses" in info:
            parts.append(f"Qualités: {info['inferredClasses']}")
        
        # Catégorie
        if "category" in info:
            parts.append(f"Catégorie: {info['category']}")
        
        # Topics
        if "topics" in info:
            parts.append(f"Topics: {info['topics']}")
        
        # Notes et avis (TourPedia)
        if "polarity" in info:
            rating_text = f"Note TourPedia: {float(info['polarity']):.1f}/10"
            parts.append(rating_text)
        
        if "inferredRating" in info:
            rating_text = f"Note calculée: {float(info['inferredRating']):.2f}/5.0"
            parts.append(rating_text)
        
        if "reviewCount" in info:
            parts.append(f"Avis TourPedia: {info['reviewCount']}")
        
        if "schemaReviews" in info:
            parts.append(f"Reviews enrichies: {info['schemaReviews']}")
        
        # Raison d'inférence (contexte sémantique)
        if "inferenceReason" in info:
            parts.append(f"Caractéristique: {info['inferenceReason']}")
        
        # Localisation
        if "address" in info:
            parts.append(f"Adresse: {info['address']}")
        
        # Liens externes (signal de qualité/importance)
        if "wikidataLink" in info:
            parts.append("Lié à Wikidata")
        
        if "dbpediaLink" in info:
            parts.append("Lié à DBpedia")
        
        return " | ".join(parts)
    
    def build_embeddings(self, limit: int = None):
        """
        Génère les embeddings pour toutes les entités ENRICHIES du graphe
        Inclut : Places de base + classes inférées
        
        Args:
            limit: Nombre max d'entités (None = toutes)
        """
        print("\n🔨 Génération des embeddings des entités ENRICHIES...")
        
        # Récupérer les entités TRIÉES par qualité (note PUIS nombre d'avis)
        # FIX: Prioriser 1) Note élevée, 2) Nombre d'avis (au lieu de l'inverse)
        query = f"""
        PREFIX tg: <{self.tg}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        
        SELECT DISTINCT ?place ?numReviews ?polarity
        WHERE {{
            {{ ?place a tg:Place . }}
            UNION {{ ?place a tg:Restaurant . }}
            UNION {{ ?place a tg:Attraction . }}
            UNION {{ ?place a tg:POI . }}
            
            OPTIONAL {{ ?place tg:numReviews ?numReviews }}
            OPTIONAL {{ ?place tg:polarity ?polarity }}
        }}
        ORDER BY DESC(?polarity) DESC(?numReviews)
        """
        
        results = self.graph.query(query)
        entities = [str(row.place) for row in results]
        
        if limit:
            entities = entities[:limit]
        
        print(f"📊 {len(entities)} entités à traiter (avec classes inférées)")
        
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
    
    def _detect_entity_type_from_question(self, question: str) -> Optional[str]:
        """
        Détecte le type d'entité recherché à partir de la question
        
        Args:
            question: Question de l'utilisateur
            
        Returns:
            Type d'entité ('Restaurant', 'Attraction', 'POI') ou None si non détecté
        """
        question_lower = question.lower()
        
        # Mots-clés pour restaurants
        restaurant_keywords = [
            "restaurant", "bistrot", "brasserie", "café", "bar", "manger",
            "repas", "cuisine", "gastronomie", "dîner", "déjeuner"
        ]
        
        # Mots-clés pour attractions (musées, monuments, sites)
        attraction_keywords = [
            "musée", "museum", "monument", "cathédrale", "église", "château",
            "tour", "attraction", "visite", "site", "culturel", "historique",
            "patrimoine", "art", "exposition", "arc", "triomphe", "basilique",
            "panthéon", "obélisque", "palais", "invalides", "sacré", "dame",
            "chapelle", "abbaye", "conciergerie", "opéra"
        ]
        
        # Mots-clés pour POI (points d'intérêt généraux)
        poi_keywords = [
            "point d'intérêt", "poi", "lieu", "endroit", "place"
        ]
        
        # Compter les occurrences de chaque catégorie
        restaurant_count = sum(1 for kw in restaurant_keywords if kw in question_lower)
        attraction_count = sum(1 for kw in attraction_keywords if kw in question_lower)
        poi_count = sum(1 for kw in poi_keywords if kw in question_lower)
        
        # Retourner le type le plus probable
        if attraction_count > 0:
            return "Attraction"
        elif restaurant_count > 0:
            return "Restaurant"
        elif poi_count > 0:
            return "POI"
        
        return None  # Type non détecté, garder tous les résultats
    
    def _find_similar_entities(self, question: str, question_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        """
        Trouve les entités les plus similaires à la question
        AVEC FILTRAGE PAR TYPE pour éviter de retourner des restaurants quand on cherche des musées
        
        Args:
            question: Question de l'utilisateur (pour détecter le type)
            question_embedding: Embedding de la question
            top_k: Nombre d'entités à retourner
            
        Returns:
            Liste de (uri, score, info) triée par similarité
        """
        if not self.entity_embeddings:
            return []
        
        # Détecter le type d'entité recherché
        target_type = self._detect_entity_type_from_question(question)
        
        if target_type:
            print(f"🎯 Type détecté dans la question : {target_type}")
        else:
            print("🔍 Type non détecté, recherche sur tous les types")
        
        similarities = []
        
        for entity_uri, entity_embedding in self.entity_embeddings.items():
            entity_info = self.entity_info[entity_uri]
            entity_type = entity_info.get("type", "")
            
            # Filtrer par type si détecté
            if target_type and entity_type != target_type:
                continue
            
            # FIX: Filtrer les lieux mal notés (polarity < 6.5)
            # Pour éviter de retourner des lieux 4-5/10 quand on demande "bien notés"
            polarity = entity_info.get("polarity")
            if polarity:
                try:
                    if float(polarity) < 6.5:
                        continue  # Skip les lieux mal notés
                except ValueError:
                    pass  # Si conversion échoue, garder l'entité
            
            # Similarité cosinus
            similarity = np.dot(question_embedding, entity_embedding)
            similarities.append((entity_uri, similarity, entity_info))
        
        # Trier par similarité décroissante
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        filtered_count = len(similarities)
        print(f"✓ {filtered_count} entités après filtrage (type={target_type or 'tous'})")
        
        return similarities[:top_k]
    
    def _generate_natural_response(self, question: str, similar_entities: List[Tuple[str, float, Dict]]) -> str:
        """
        Génère une réponse en langage naturel ENRICHIE avec GPT-4o-mini
        Exploite toutes les métadonnées : classes inférées, reviews, alignement LOD
        
        Args:
            question: Question de l'utilisateur
            similar_entities: Entités pertinentes trouvées
            
        Returns:
            Réponse conversationnelle en français
        """
        # Construire le contexte ENRICHI
        context_parts = []
        for uri, score, info in similar_entities:
            name = info.get("name", "Inconnu")
            type_ = info.get("type", "Lieu")
            
            # Construire description enrichie
            desc_parts = [f"**{name}** ({type_})"]
            
            # Notes multiples (priorité à polarity/10 pour cohérence visuelle)
            if "polarity" in info:
                desc_parts.append(f"Note TourPedia: {info['polarity']}/10")
            elif "inferredRating" in info:
                desc_parts.append(f"Note calculée: {info['inferredRating']}/5.0")
            
            # Compteurs d'avis
            review_parts = []
            if "reviewCount" in info:
                review_parts.append(f"{info['reviewCount']} avis TourPedia")
            if "schemaReviews" in info:
                review_parts.append(f"{info['schemaReviews']} reviews enrichies")
            if review_parts:
                desc_parts.append(" + ".join(review_parts))
            
            # Classes inférées (badges de qualité)
            if "inferredClasses" in info:
                desc_parts.append(f"🏆 Badges: {info['inferredClasses']}")
            
            # Raison d'inférence
            if "inferenceReason" in info:
                desc_parts.append(f"💡 {info['inferenceReason']}")
            
            # Catégorie et topics
            if "category" in info:
                desc_parts.append(f"Catégorie: {info['category']}")
            if "topics" in info:
                desc_parts.append(f"Topics: {info['topics']}")
            
            # Adresse
            if "address" in info:
                desc_parts.append(f"📍 {info['address']}")
            
            # Liens externes (gage de notoriété)
            external = []
            if "wikidataLink" in info:
                external.append("Wikidata")
            if "dbpediaLink" in info:
                external.append("DBpedia")
            if external:
                desc_parts.append(f"🌐 Lié à: {', '.join(external)}")
            
            context_parts.append(" | ".join(desc_parts))
        
        context = "\n\n".join(context_parts)
        
        # Prompt enrichi pour génération
        prompt = f"""Tu es un assistant touristique expert pour Paris. Réponds en français de manière naturelle, précise et engageante.

Question de l'utilisateur : {question}

Informations ENRICHIES du graphe de connaissances (incluant classes inférées, reviews, alignement LOD) :

{context}

Instructions:
- Réponds de manière conversationnelle et naturelle
- Mentionne les noms des lieux, leurs notes et leurs caractéristiques spéciales (badges 🏆)
- Si un lieu a des badges (HighlyRated, TopRestaurant, HiddenGem, etc.), explique pourquoi c'est pertinent
- Si un lieu est lié à Wikidata/DBpedia, c'est un signe de notoriété
- Donne des recommandations utiles et contextualisées
- Sois concis (2-3 paragraphes maximum)
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
        
        # 2. Trouver entités similaires (avec filtrage par type)
        print(f"🎯 Recherche des {top_k} entités les plus pertinentes...")
        similar_entities = self._find_similar_entities(question, question_embedding, top_k)
        
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
