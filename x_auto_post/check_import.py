try:
    from google.generativeai import ImageGenerationModel
    print("SUCCESS: ImageGenerationModel imported")
except ImportError:
    print("FAIL: ImportError")
except Exception as e:
    print(f"FAIL: {e}")
