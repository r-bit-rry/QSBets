import numpy as np


def convert_numpy_to_native(obj):
    """Convert NumPy types and pandas timestamps to native Python types for better YAML serialization"""
    # Handle pandas Timestamp objects
    if hasattr(obj, "_repr_base") and "timestamp" in str(type(obj)).lower():
        return obj.strftime("%Y-%m-%d")  # Convert to ISO format date string

    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        # Handle timestamp keys by converting them to strings
        result = {}
        for key, value in obj.items():
            # Convert timestamp keys to strings
            if hasattr(key, "_repr_base") and "timestamp" in str(type(key)).lower():
                new_key = key.strftime("%Y-%m-%d")
            else:
                new_key = key
            result[new_key] = convert_numpy_to_native(value)
        return result
    elif isinstance(obj, list):
        return [convert_numpy_to_native(item) for item in obj]
    elif hasattr(obj, "item"):  # Handle numpy scalar objects
        return obj.item()
    else:
        return obj