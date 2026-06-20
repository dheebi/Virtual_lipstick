import traceback
import tensorflow as tf

class EncoderBlock(tf.keras.layers.Layer):
    def __init__(self, **kwargs):
        super(EncoderBlock, self).__init__(**kwargs)

try:
    model = tf.keras.models.load_model('model/BestModel.h5', custom_objects={'EncoderBlock': EncoderBlock}, compile=False)
    print("Success!")
except Exception as e:
    with open('error_trace.txt', 'w', encoding='utf-8') as f:
        f.write(traceback.format_exc())
