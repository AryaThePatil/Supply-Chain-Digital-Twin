import osmnx as ox
import pickle
import os
import time
from pathlib import Path

def convert_map():
    print("="*60)
    print("🗺️  Map Converter Tool")
    print("="*60)
    
    # 1. Find the file
    datasets_dir = Path("Datasets")
    files = list(datasets_dir.glob("*.osm")) + list(datasets_dir.glob("*.xml"))
    
    if not files:
        print("❌ No .osm or .xml files found in Datasets/ folder.")
        print("   Please convert your .pbf to .osm first (using osmconvert).")
        return

    target_file = files[0]
    print(f"📂 Found file: {target_file}")
    print(f"⚠️  WARNING: Parsing XML is VERY SLOW. This may look frozen.")
    print(f"   It can take 10-20 minutes for large maps.")
    print(f"   DO NOT CLOSE THIS WINDOW.")
    
    start_time = time.time()
    
    try:
        # 2. Load the graph (The slow part)
        print(f"\n⏳ Starting load (Time: {time.strftime('%H:%M:%S')})...")
        G = ox.graph_from_xml(target_file)
        print(f"✅ Loaded! (Took {(time.time() - start_time)/60:.1f} minutes)")
        
        # 3. Save as GraphML (Recommended)
        output_graphml = "nagpur.graphml"
        ox.save_graphml(G, output_graphml)
        print(f"💾 Saved as {output_graphml} (Fast to load)")
        
        # 4. Save as Pickle (For current code compatibility)
        # We need to match the filename expected by road_network.py
        # But for now, let's just save a generic one they can rename
        output_pkl = "cached_map.pkl"
        with open(output_pkl, 'wb') as f:
            pickle.dump(G, f)
        print(f"💾 Saved as {output_pkl} (Python binary)")
        
        print("\n🎉 Done! You can now use these files.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    convert_map()
