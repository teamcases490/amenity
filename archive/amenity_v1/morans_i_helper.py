"""
Add Moran's I calculation method to AdvancedFeatureExtractor class
"""

def _calculate_morans_i(self, coords: np.ndarray) -> float:
    """
    Calculate Moran's I spatial autocorrelation index.
    
    Moran's I ranges from -1 to +1:
    - +1: Perfect positive autocorrelation (clustered)
    - 0: Random spatial pattern
    - -1: Perfect negative autocorrelation (dispersed)
    
    Args:
        coords: Nx2 array of coordinates
    
    Returns:
        Moran's I value (-1 to +1)
    """
    try:
        if len(coords) < 4:
            return 0.0
        
        from scipy.spatial import distance_matrix
        
        # Create spatial weights matrix (inverse distance)
        dist_matrix = distance_matrix(coords, coords)
        np.fill_diagonal(dist_matrix, 1)  # Avoid division by zero
        
        # Inverse distance weights (closer = higher weight)
        weights = 1 / dist_matrix
        np.fill_diagonal(weights, 0)  # No self-weight
        
        # Normalize weights (row-standardization)
        row_sums = weights.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1  # Avoid division by zero
        weights = weights / row_sums
        
        # For simplicity, use density as the attribute
        # (In full implementation, you'd use actual POI attributes)
        # Here we use a simple proxy: distance from centroid
        centroid = coords.mean(axis=0)
        values = np.array([np.linalg.norm(coord - centroid) for coord in coords])
        
        # Calculate Moran's I
        n = len(values)
        mean_val = values.mean()
        
        # Numerator: sum of weighted cross-products
        numerator = 0
        for i in range(n):
            for j in range(n):
                numerator += weights[i, j] * (values[i] - mean_val) * (values[j] - mean_val)
        
        # Denominator: variance * sum of weights
        variance = ((values - mean_val) ** 2).sum()
        sum_weights = weights.sum()
        
        if variance == 0 or sum_weights == 0:
            return 0.0
        
        morans_i = (n / sum_weights) * (numerator / variance)
        
        # Clip to valid range
        return max(-1.0, min(1.0, morans_i))
        
    except Exception as e:
        logger.error(f"Error calculating Moran's I: {e}")
        return 0.0
