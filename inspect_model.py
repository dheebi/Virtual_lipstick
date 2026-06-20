import zipfile
import json

with zipfile.ZipFile('model/BestModel.keras', 'r') as z:
    with z.open('config.json') as f:
        data = json.load(f)

model_class = data.get("class_name", "")
print("Model Class:", model_class)

config = data.get("config", {})
layers = config.get("layers", [])

results = []
results.append(f"Model Class: {model_class}")
for i, layer in enumerate(layers):
    cls_name = layer.get('class_name', '')
    layer_cfg = layer.get('config', {})
    name = layer_cfg.get('name', 'N/A')
    results.append(f"{i}: {name} ({cls_name})")

with open('inspect_out.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
