#!/usr/bin/env python3
"""
Quick test script to simulate inference and generate kg_inferred.ttl
Alternative to using Corese GUI
"""
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

def main():
    print("="*60)
    print("ÉTAPE 15: Application des règles d'inférence")
    print("="*60)
    
    input_file = "data/kg_linked.ttl"
    output_file = "data/kg_inferred.ttl"
    
    if not Path(input_file).exists():
        print(f"❌ Erreur: {input_file} n'existe pas")
        print("   Exécutez d'abord les étapes précédentes pour générer kg_linked.ttl")
        return 1
    
    print("\n🔄 Méthode recommandée: Corese GUI")
    print("-" * 60)
    print("1. Télécharger Corese: https://github.com/Wimmics/corese/releases")
    print("2. Lancer: java -jar corese-server-4.5.0.jar -lp")
    print("3. Ouvrir: http://localhost:8080")
    print("4. Charger: data/kg_linked.ttl")
    print("5. Charger les 7 règles depuis rules/")
    print("6. Exécuter l'inférence")
    print("7. Exporter: data/kg_inferred.ttl")
    
    print("\n⚙️ Alternative: Script Python (simulation)")
    print("-" * 60)
    print("python scripts/apply_inference_rules.py data/kg_linked.ttl data/kg_inferred.ttl")
    
    response = input("\n❓ Voulez-vous exécuter le script Python maintenant? (o/n): ")
    
    if response.lower() in ['o', 'oui', 'y', 'yes']:
        print("\n🚀 Lancement de l'inférence avec Python...")
        print("-" * 60)
        
        try:
            from scripts.apply_inference_rules import apply_rules
            apply_rules(input_file, output_file)
            
            print("\n✅ Inférence terminée avec succès!")
            print(f"   Fichier créé: {output_file}")
            
            # Validation SHACL
            print("\n🔍 Validation SHACL...")
            print("-" * 60)
            import subprocess
            result = subprocess.run(
                ["python", "scripts/validate_shacl.py", output_file],
                capture_output=True,
                text=True
            )
            print(result.stdout)
            
            if result.returncode == 0:
                print("✅ Validation SHACL réussie!")
            else:
                print("⚠️ Validation SHACL a échoué")
                print(result.stderr)
            
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            return 1
    else:
        print("\n💡 Utilisez Corese GUI pour de meilleurs résultats")
        print("   Ou exécutez manuellement:")
        print("   python scripts/apply_inference_rules.py data/kg_linked.ttl data/kg_inferred.ttl")
    
    print("\n" + "="*60)
    print("PROCHAINE ÉTAPE: Link Prediction")
    print("="*60)
    print("pip install pykeen torch pandas tqdm")
    print("python scripts/build_reco_graph.py ...")
    print("python scripts/train_transe.py ...")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
