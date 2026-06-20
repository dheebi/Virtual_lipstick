import tensorflow as tf

model = tf.keras.models.load_model(
    "model/BestModel.h5",
    compile=False,
    safe_mode=False   # 🔥 important
)