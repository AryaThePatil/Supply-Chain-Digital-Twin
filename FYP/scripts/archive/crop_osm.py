import xml.etree.ElementTree as ET
from pathlib import Path
import sys

# CONFIGURATION (Nagpur City Center)
# Matches your simulation_config.yaml
NORTH = 21.1500
SOUTH = 21.1450
EAST = 79.0750
WEST = 79.0700

INPUT_FILE = "Datasets/western-zone-251203.osm_01.osm"
OUTPUT_FILE = "Datasets/nagpur_cropped.osm"

def crop_osm():
    print("="*60)
    print("✂️  Offline Map Cropper")
    print("="*60)
    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Bounds: N={NORTH}, S={SOUTH}, E={EAST}, W={WEST}")
    print("-" * 60)

    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {INPUT_FILE}")
        return

    print("🚀 Starting crop process...")
    print("   This reads the file line-by-line to save RAM.")
    print("   It may take 5-10 minutes. Please wait.")

    valid_nodes = set()
    nodes_kept = 0
    ways_kept = 0
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
        # Write Header
        out_f.write("<?xml version='1.0' encoding='UTF-8'?>\n")
        out_f.write("<osm version='0.6' generator='PythonCustomCropper'>\n")
        
        # We use a simple state machine parser because standard XML parsers 
        # try to build a tree (which crashes RAM for 5GB files)
        
        with open(INPUT_FILE, 'r', encoding='utf-8', errors='ignore') as in_f:
            in_way = False
            in_node = False
            keeping_node = False
            way_buffer = []
            way_has_valid_node = False
            
            line_count = 0
            
            for line in in_f:
                line_count += 1
                if line_count % 1000000 == 0:
                    print(f"   Processed {line_count/1000000:.1f} million lines...", end='\r')
                
                stripped = line.strip()
                
                # 1. Handle Nodes
                if stripped.startswith("<node"):
                    # Default assumption
                    in_node = False
                    keeping_node = False
                    
                    try:
                        lat_start = line.find('lat="') + 5
                        lat_end = line.find('"', lat_start)
                        lat = float(line[lat_start:lat_end])
                        
                        lon_start = line.find('lon="') + 5
                        lon_end = line.find('"', lon_start)
                        lon = float(line[lon_start:lon_end])
                        
                        # Check bounds
                        if SOUTH <= lat <= NORTH and WEST <= lon <= EAST:
                            # Keep this node
                            # Check if self-closing
                            if stripped.endswith("/>"):
                                out_f.write(line)
                                nodes_kept += 1
                                # Extract ID
                                id_start = line.find('id="') + 4
                                id_end = line.find('"', id_start)
                                node_id = line[id_start:id_end]
                                valid_nodes.add(node_id)
                            else:
                                # Multi-line node, start keeping
                                in_node = True
                                keeping_node = True
                                out_f.write(line)
                                nodes_kept += 1
                                # Extract ID
                                id_start = line.find('id="') + 4
                                id_end = line.find('"', id_start)
                                node_id = line[id_start:id_end]
                                valid_nodes.add(node_id)
                        else:
                            # Not in bounds
                            if not stripped.endswith("/>"):
                                in_node = True
                                keeping_node = False
                                
                    except Exception:
                        pass # Skip malformed lines
                
                elif in_node:
                    if keeping_node:
                        out_f.write(line)
                    if stripped.startswith("</node>"):
                        in_node = False
                        keeping_node = False

                # 2. Handle Ways
                elif stripped.startswith("<way"):
                    in_way = True
                    way_buffer = [line]
                    way_has_valid_node = False
                    
                elif in_way:
                    way_buffer.append(line)
                    
                    # Check for node references
                    if stripped.startswith("<nd"):
                        try:
                            ref_start = line.find('ref="') + 5
                            ref_end = line.find('"', ref_start)
                            ref_id = line[ref_start:ref_end]
                            
                            if ref_id in valid_nodes:
                                way_has_valid_node = True
                        except:
                            pass
                            
                    if stripped.startswith("</way>"):
                        in_way = False
                        # If the way connects to at least one valid node, keep it
                        if way_has_valid_node:
                            for buf_line in way_buffer:
                                # Check if this is a node reference
                                if buf_line.strip().startswith("<nd"):
                                    try:
                                        ref_start = buf_line.find('ref="') + 5
                                        ref_end = buf_line.find('"', ref_start)
                                        ref_id = buf_line[ref_start:ref_end]
                                        
                                        # Only write <nd> if the node exists in our file
                                        if ref_id in valid_nodes:
                                            out_f.write(buf_line)
                                    except:
                                        # If malformed, skip
                                        pass
                                else:
                                    # Write other lines (tags, <way>, </way>)
                                    out_f.write(buf_line)
                            ways_kept += 1
                        way_buffer = []
                        
                # 3. Handle Relations (Skip)
                elif stripped.startswith("<relation"):
                    pass 
                    
        # Write Footer
        out_f.write("</osm>\n")

    print(f"\n\n✅ Done!")
    print(f"   Nodes kept: {nodes_kept}")
    print(f"   Ways kept:  {ways_kept}")
    print(f"   Saved to:   {OUTPUT_FILE}")
    print("\n👉 Now run: python main.py")

if __name__ == "__main__":
    crop_osm()
