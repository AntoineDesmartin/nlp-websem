#!/usr/bin/env python3
"""
Script to merge review RDF files with the main knowledge graph.
Handles syntax errors gracefully and reports statistics.
"""

from rdflib import Graph
import sys

def merge_reviews():
    """Merge all review files into kg_reviews_all.ttl"""
    print("=" * 60)
    print("MERGING REVIEW FILES")
    print("=" * 60)
    
    g = Graph()
    files = [
        'data/kg_reviews_attraction.ttl',
        'data/kg_reviews_poi.ttl'
    ]
    
    for filepath in files:
        print(f"\nLoading: {filepath}")
        try:
            before = len(g)
            g.parse(filepath, format='turtle')
            after = len(g)
            print(f"  ✓ Added {after - before:,} triples")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            print(f"  → Trying with format detection...")
            try:
                g.parse(filepath)
                after = len(g)
                print(f"  ✓ Added {after - before:,} triples (auto-format)")
            except Exception as e2:
                print(f"  ✗ Failed: {e2}")
                continue
    
    output_file = 'data/kg_reviews_all.ttl'
    g.serialize(output_file, format='turtle')
    print(f"\n{'=' * 60}")
    print(f"Total review triples: {len(g):,}")
    print(f"Saved to: {output_file}")
    print(f"{'=' * 60}")
    
    return len(g)

def merge_with_main_kg(reviews_count):
    """Merge reviews with kg_linked.ttl to create kg_enriched.ttl"""
    print("\n" + "=" * 60)
    print("MERGING WITH MAIN KNOWLEDGE GRAPH")
    print("=" * 60)
    
    g = Graph()
    
    # Load main KG
    print(f"\nLoading: data/kg_linked.ttl")
    before = len(g)
    g.parse('data/kg_linked.ttl', format='turtle')
    after = len(g)
    print(f"  ✓ Main KG: {after:,} triples")
    
    # Load reviews
    print(f"\nLoading: data/kg_reviews_all.ttl")
    before = after
    g.parse('data/kg_reviews_all.ttl', format='turtle')
    after = len(g)
    print(f"  ✓ Added reviews: {after - before:,} triples")
    
    # Save enriched KG
    output_file = 'data/kg_enriched.ttl'
    g.serialize(output_file, format='turtle')
    
    print(f"\n{'=' * 60}")
    print(f"FINAL ENRICHED KNOWLEDGE GRAPH")
    print(f"{'=' * 60}")
    print(f"Total triples: {len(g):,}")
    print(f"Saved to: {output_file}")
    print(f"{'=' * 60}")
    
    return len(g)

if __name__ == '__main__':
    try:
        reviews_count = merge_reviews()
        total_count = merge_with_main_kg(reviews_count)
        print(f"\n✓ SUCCESS: Knowledge graph enriched with {reviews_count:,} review triples")
        print(f"✓ Final graph: {total_count:,} triples total")
    except Exception as e:
        print(f"\n✗ ERROR: {e}", file=sys.stderr)
        sys.exit(1)
