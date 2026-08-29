const int LED1_PIN = 3;
const int LED2_PIN = 5;

void setup() {
  pinMode(LED1_PIN, OUTPUT);
  pinMode(LED2_PIN, OUTPUT);
  digitalWrite(LED1_PIN, LOW);
  digitalWrite(LED2_PIN, LOW);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "LED1_ON") {
      digitalWrite(LED1_PIN, HIGH);
      Serial.println("OK:LED1_ON");
    } else if (cmd == "LED1_OFF") {
      digitalWrite(LED1_PIN, LOW);
      Serial.println("OK:LED1_OFF");
    } else if (cmd == "LED2_ON") {
      digitalWrite(LED2_PIN, HIGH);
      Serial.println("OK:LED2_ON");
    } else if (cmd == "LED2_OFF") {
      digitalWrite(LED2_PIN, LOW);
      Serial.println("OK:LED2_OFF");
    } else {
      Serial.println("ERR:CMD");
    }
  }
}
