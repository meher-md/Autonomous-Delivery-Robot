import onnx
import sys

try:
    model_path = "/home/mo/ws/mobile/DeliveryBotApp/app/src/main/assets/sherpa/model-en-male/en_US-ryan-low.onnx"
    print(f"Checking {model_path}...")
    onnx_model = onnx.load(model_path)
    onnx.checker.check_model(onnx_model)
    print("Model is VALID.")
except Exception as e:
    print(f"Model is INVALID: {e}")
    sys.exit(1)
