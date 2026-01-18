#!/usr/bin/env python3
"""
Apply SPARQL CONSTRUCT rules to simulate inference (alternative to Corese)
"""
import sys
from pathlib import Path
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

TG = Namespace('https://example.org/tourguide#')
SCHEMA = Namespace('http://schema.org/')

def load_rule(rule_file):
    """Load a SPARQL CONSTRUCT rule from file"""
    with open(rule_file, 'r', encoding='utf-8') as f:
        return f.read()

def apply_rules(input_file, output_file, rules_dir='rules'):
    """Apply all inference rules to the graph"""
    print(f"Loading graph: {input_file}")
    g = Graph()
    g.parse(input_file, format='turtle')
    print(f"  ✓ {len(g)} triples loaded")
    
    # Bind namespaces
    g.bind('tg', TG)
    g.bind('schema', SCHEMA)
    
    # List of rule files
    rule_files = [
        'r1_highly_rated_place.rq',
        'r2_top_restaurant.rq',
        'r3_popular_place.rq',
        'r4_hidden_gem.rq',
    ]
    
    total_inferred = 0
    
    for rule_file in rule_files:
        rule_path = Path(rules_dir) / rule_file
        if not rule_path.exists():
            print(f"  ⚠ Rule file not found: {rule_path}")
            continue
        
        print(f"\nApplying rule: {rule_file}")
        try:
            rule_query = load_rule(rule_path)
            
            # Execute CONSTRUCT query
            result_graph = g.query(rule_query).graph
            
            # Count new triples
            new_triples = len(result_graph)
            print(f"  ✓ {new_triples} triples inferred")
            
            # Merge with main graph
            g += result_graph
            total_inferred += new_triples
            
        except Exception as e:
            print(f"  ✗ Error applying rule: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"Total triples after inference: {len(g)}")
    print(f"New triples inferred: {total_inferred}")
    print(f"{'='*60}")
    
    # Save result
    print(f"\nSaving to: {output_file}")
    g.serialize(destination=output_file, format='turtle')
    print("  ✓ Done!")
    
    # Summary statistics
    print("\n📊 Inference Summary:")
    inferred_types = [
        TG.HighlyRatedPlace,
        TG.TopRestaurant,
        TG.PopularPlace,
        TG.HiddenGem,
    ]
    
    for inf_type in inferred_types:
        count = len(list(g.subjects(RDF.type, inf_type)))
        if count > 0:
            print(f"  - {inf_type.split('#')[-1]}: {count}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python apply_inference_rules.py <input.ttl> <output.ttl>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    apply_rules(input_file, output_file)
