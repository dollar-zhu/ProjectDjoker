#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>

Arduino_LED_Matrix matrix;
uint8_t heart[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,1,1,1,0,0,1,1,1,0,0,0,
  0,1,1,1,1,1,1,1,1,1,1,0,0,
  0,1,1,1,1,1,1,1,1,1,1,0,0,
  0,0,1,1,1,1,1,1,1,1,0,0,0,
  0,0,0,1,1,1,1,1,1,0,0,0,0,
  0,0,0,0,1,1,1,1,0,0,0,0,0,
  0,0,0,0,0,1,1,0,0,0,0,0,0
};
uint8_t blank[104] = {};

void audioReady(bool ready) {
  digitalWrite(LED_BUILTIN, ready ? LOW : HIGH);
  matrix.draw(ready ? heart : blank);
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  matrix.begin();
  matrix.setGrayscaleBits(1);
  Bridge.begin();
  Bridge.provide_safe("djoker_audio_ready", audioReady);
}

void loop() {}
