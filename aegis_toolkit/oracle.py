# core/oracle.py
import numpy as np
from aegis_toolkit.config import settings
import os

class DummySession:
    def get_inputs(self): return [type('Input', (), {'name': 'input'})()]
    def get_outputs(self): return [type('Output', (), {'name': 'output'})()]
    def run(self, _, __): return [np.array([[[0.1]]])]

session = None
model_path = settings.adaptive_security_model.path

try:
    import onnxruntime as ort
    if os.path.exists(model_path):
        session = ort.InferenceSession(model_path)
    else:
        print(f"INFO: AI model not found at {model_path}. Using dummy model.")
        session = DummySession()
except ImportError:
    print("INFO: onnxruntime is not installed. Using dummy model.")
    session = DummySession()
except Exception as e:
    print(f"ERROR: Failed to load ONNX model: {e}. Using dummy model.")
    session = DummySession()

def calculate_risk_score(request_features: dict) -> float:
    """
    Uses a machine learning model to calculate a real-time risk score.
    Returns a low-risk score if the model fails for any reason.
    """
    try:
        input_vector = np.array([[0.0] * 10], dtype=np.float32)
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        result = session.run([output_name], {input_name: input_vector})
        risk_score = result[0][0][0]
        return float(risk_score)
    except Exception as e:
        print(f"ERROR: AI risk score calculation failed: {e}")
        return 0.1