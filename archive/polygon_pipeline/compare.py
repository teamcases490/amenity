import pandas as pd

def compare_scores():
    # Load Phase 1 (centroid) scores
    df_c = pd.read_csv("results/pincode_scores.csv")
    if "pincode" in df_c.columns:
         df_c["pincode"] = df_c["pincode"].astype(str).str.replace(".0", "", regex=False)
    else:
         # Original file might use address column for pincode if read purely from input
         pass
         
    # Load Phase 2 (polygon) scores
    df_p = pd.read_csv("results/polygon_scores.csv")
    df_p["pincode"] = df_p["pincode"].astype(str).str.replace(".0", "", regex=False)
    
    # Merge
    # We might need to handle address column in centroid CSV if it was saved there. If it was saved using main.py, it's 'address'
    df_c = df_c.rename(columns={"address": "pincode", "amenity_index": "score_centroid", "classification": "class_centroid", "total_pois": "pois_centroid"})
    df_c["pincode"] = df_c["pincode"].astype(str).str.replace(".0", "", regex=False)
    
    df_p = df_p.rename(columns={"amenity_index": "score_polygon", "classification": "class_polygon", "total_pois_used": "pois_polygon", "n_pois_in_bbox": "bbox_pois"})
    
    df_merge = pd.merge(df_p, df_c, on="pincode", how="inner")
    
    print(f"Comparing {len(df_merge)} matched pincodes...")
    print( "=" * 100)
    print(f"{'Pincode':<10} | {'Centroid Score (POIs)':<25} | {'Polygon Score (POIs)':<25} | {'Diff':<6}")
    print( "-" * 100)
    
    for _, row in df_merge.iterrows():
        c_str = f"{row['score_centroid']:.1f} {row['class_centroid']} ({row['pois_centroid']})"
        p_str = f"{row['score_polygon']:.1f} {row['class_polygon']} ({row['pois_polygon']}/{row['bbox_pois']})"
        diff = row['score_polygon'] - row['score_centroid']
        diff_str = f"{diff:+.1f}"
        print(f"{row['pincode']:<10} | {c_str:<25} | {p_str:<25} | {diff_str:<6}")
        
if __name__ == "__main__":
    compare_scores()
