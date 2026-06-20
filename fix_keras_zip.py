import zipfile
import json
import os
import shutil

model_path = 'model/BestModel.keras'
fixed_model_path = 'model/BestModel_fixed.keras'

# Extract to temp dir
temp_dir = 'temp_keras_zip'
if os.path.exists(temp_dir):
    shutil.rmtree(temp_dir)
os.makedirs(temp_dir)

with zipfile.ZipFile(model_path, 'r') as z:
    z.extractall(temp_dir)

config_path = os.path.join(temp_dir, 'config.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config_str = f.read()

# Keras 3 uses "batch_shape", Keras 2 uses "batch_input_shape" for InputLayer.
# Let's replace "batch_shape" with "batch_input_shape" in the config string completely:
config_str = config_str.replace('"batch_shape":', '"batch_input_shape":')

with open(config_path, 'w', encoding='utf-8') as f:
    f.write(config_str)

# Zip it back up
with zipfile.ZipFile(fixed_model_path, 'w') as z:
    for root, _, files in os.walk(temp_dir):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, temp_dir)
            z.write(file_path, arcname)

print("Created BestModel_fixed.keras")
shutil.rmtree(temp_dir)
