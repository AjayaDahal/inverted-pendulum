/*
  Inverted pendulum on a belt-driven cart: homing, sensor calibration, a direction self-test,
  swing-up and balance (controller.h). Commands and telemetry over USB serial at 115200 baud: send
  ? for the list.

  Board: Arduino Uno / Nano (ATmega328P) or an ESP32. Library: FastAccelStepper (Library Manager).
  config.h is generated from the design (scripts/make_firmware.py): do not edit it. Your wiring and
  the two direction settings are below. Wiring, the driver's current and the first power-on:
  DESIGN.md, "Electronics and firmware".
*/
#include <Arduino.h>
#include <Wire.h>
#include <FastAccelStepper.h>

#include "config.h"
#include "controller.h"

// ---------------------------------------------------------------- your wiring
#if defined(ARDUINO_ARCH_ESP32)
static const uint8_t PIN_STEP = 25, PIN_DIR = 26, PIN_EN = 27;  // AS5600 on I2C: SDA 21, SCL 22
static const uint8_t PIN_SW_MINUS = 32, PIN_SW_PLUS = 33;       // limit switches, NC to GND
static const uint8_t PIN_ENC_A = 18, PIN_ENC_B = 19;            // option: 600 P/R encoder
#define ISR_ATTR IRAM_ATTR
#else
static const uint8_t PIN_STEP = 9, PIN_DIR = 8, PIN_EN = 7;  // STEP on 9 or 10 (timer 1); AS5600 on A4/A5
static const uint8_t PIN_SW_MINUS = 4, PIN_SW_PLUS = 5;
static const uint8_t PIN_ENC_A = 2, PIN_ENC_B = 3;
#define ISR_ATTR
#endif

// ---------------------------------------------------------------- your machine
#define DIR_HIGH_MOVES_PLUS true  // homing tells you when this must be false
#define ANGLE_SIGN 1              // the d test tells you when this must be -1
#define USE_ENCODER 0             // 1: the 600 P/R encoder instead of the AS5600
#define I2C_HZ 400000             // 100000 if the sensor lead is longer than about 30 cm

static const uint32_t PERIOD_US = 1000000UL / CTL_HZ;
static const uint8_t AS5600_ADDR = 0x36;

FastAccelStepperEngine engine = FastAccelStepperEngine();
FastAccelStepper *stepper = NULL;
Controller ctl;

enum State : uint8_t { IDLE, RUNNING, FAULT };
State state = IDLE;
bool homed = false, calibrated = false, telemetry = false, monitoring = false;
float angle_sign = ANGLE_SIGN;
int32_t hang_ref = 0;  // sensor counts with the pendulum hanging still
float pivot_tau = -1.0f;  // N m, from the f test
uint32_t next_us = 0, overruns = 0, ticks = 0, monitor_ms = 0;

static int32_t steps(float m) {  // metres (or m/s, m/s^2) to steps
  float s = m * CFG_STEPS_PER_M;
  return (int32_t)(s >= 0.0f ? s + 0.5f : s - 0.5f);
}
static bool swMinus() { return digitalRead(PIN_SW_MINUS) == HIGH; }  // NC switch: pressed or a broken wire reads HIGH
static bool swPlus() { return digitalRead(PIN_SW_PLUS) == HIGH; }

static bool fault(const __FlashStringHelper *why) {
  state = FAULT;
  Serial.print(F("FAULT: "));
  Serial.println(why);
  return false;
}

// ---------------------------------------------------------------- angle sensor
#if USE_ENCODER
static const int32_t COUNTS = CFG_COUNTS_ENCODER;
volatile int32_t enc_count = 0;
volatile uint8_t enc_last = 0;
void ISR_ATTR encoderIsr() {
  static const int8_t T[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};
  uint8_t s = (digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B);
  enc_count += T[(enc_last << 2) | s];
  enc_last = s;
}
static bool readCounts(int32_t &c) {
  noInterrupts();
  c = enc_count;
  interrupts();
  return true;
}
static bool sensorOk() { return true; }
static void sensorReport() {}
#else
static const int32_t COUNTS = CFG_COUNTS_AS5600;
static bool as5600Read(uint8_t reg, uint8_t n, uint8_t *buf) {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(AS5600_ADDR, n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}
static bool readCounts(int32_t &c) {
  uint8_t b[2];
  if (!as5600Read(0x0C, 2, b)) return false;  // RAW ANGLE, 12 bit
  c = ((int32_t)(b[0] & 0x0F) << 8) | b[1];
  return true;
}
static bool sensorOk() {  // STATUS: MD magnet detected, not ML (too weak) or MH (too strong)
  uint8_t s;
  return as5600Read(0x0B, 1, &s) && (s & 0x20) && !(s & 0x18);
}
static void sensorReport() {
  uint8_t s, agc, mag[2];
  if (!as5600Read(0x0B, 1, &s) || !as5600Read(0x1A, 1, &agc) || !as5600Read(0x1B, 2, mag)) {
    Serial.print(F(" | AS5600 not answering"));
    return;
  }
  Serial.print(F(" | magnet "));
  Serial.print(s & 0x20 ? F("found") : F("MISSING"));
  if (s & 0x10) Serial.print(F(", too weak: move it closer"));
  if (s & 0x08) Serial.print(F(", too strong: move it away"));
  Serial.print(F(", AGC "));
  Serial.print(agc);  // mid-range (about 64-192 at 5 V) is best
  Serial.print(F(", magnitude "));
  Serial.print(((uint16_t)(mag[0] & 0x0F) << 8) | mag[1]);
}
#endif

// 0 upright (half a turn from hanging), + leaning towards +x; the controller unwraps
static float angleFrom(int32_t c) { return angle_sign * (float)(c - hang_ref) * (2.0f * CTL_PI / COUNTS) + CTL_PI; }

// ---------------------------------------------------------------- homing, calibration, self-test
static bool home() {
  if (swMinus() && swPlus()) return fault(F("both limit switches read open: check the NC wiring"));
  if (swMinus()) return fault(F("the -x switch is pressed: move the cart off it (o, by hand), then h"));
  stepper->enableOutputs();
  stepper->setAcceleration(steps(0.5f));
  stepper->setSpeedInHz(steps(CFG_HOME_SPEED));
  stepper->runBackward();
  uint32_t t0 = millis();
  while (!swMinus()) {
    if (swPlus()) {
      stepper->forceStop();
      return fault(F("homing ran into the +x switch: set DIR_HIGH_MOVES_PLUS to false"));
    }
    if (millis() - t0 > 20000UL) {
      stepper->forceStop();
      return fault(F("homing found no switch in 20 s"));
    }
  }
  stepper->forceStopAndNewPosition(-steps(CFG_X_SWITCH));
  delay(30);
  stepper->moveTo(-steps(CFG_X_SWITCH - CFG_HOME_BACKOFF), true);
  if (swMinus()) return fault(F("the -x switch stays pressed after backing off"));
  stepper->moveTo(0, true);
  homed = true;
  state = IDLE;
  Serial.println(F("homed: the cart is at x = 0"));
  return true;
}

static bool calibrate() {  // the pendulum hangs still, the cart stands
  int32_t first, c, lo = 0, hi = 0;
  float sum = 0.0f;
  if (!readCounts(first)) return fault(F("angle sensor read failed"));
  for (int i = 0; i < 100; i++) {
    delay(5);
    if (!readCounts(c)) return fault(F("angle sensor read failed"));
    int32_t d = c - first;
    if (d > COUNTS / 2) d -= COUNTS;
    if (d < -COUNTS / 2) d += COUNTS;
    sum += d;
    if (d < lo) lo = d;
    if (d > hi) hi = d;
  }
  if (hi - lo > COUNTS / 360) {
    Serial.println(F("still swinging: wait until the pendulum hangs still, then c"));
    return false;
  }
  hang_ref = first + (int32_t)(sum / 100.0f + (sum >= 0.0f ? 0.5f : -0.5f));
#if !USE_ENCODER
  hang_ref = ((hang_ref % COUNTS) + COUNTS) % COUNTS;
#endif
  calibrated = true;
  Serial.println(F("calibrated: hanging = 180 deg"));
  return true;
}

static float meanAngle() {  // near hanging, so no wrap at 180 deg matters
  float s = 0.0f;
  int32_t c;
  for (int i = 0; i < 10; i++) {
    readCounts(c);
    s += Controller::wrap(angleFrom(c) - CTL_PI);
    delay(2);
  }
  return s / 10.0f + CTL_PI;
}

static void directionTest() {
  // The cart starts towards +x: a hanging pendulum lags behind, so its angle must grow past 180 deg.
  if (!homed || !calibrated) {
    Serial.println(F("home (h) and calibrate (c) first"));
    return;
  }
  float th0 = meanAngle(), dev = 0.0f;
  int32_t c;
  stepper->setSpeedInHz(steps(0.3f));
  stepper->setAcceleration(steps(2.0f));
  stepper->move(steps(0.02f));
  uint32_t t0 = millis();
  while (millis() - t0 < 100) {
    if (readCounts(c)) {
      float d = Controller::wrap(angleFrom(c) - th0);
      if (fabsf(d) > fabsf(dev)) dev = d;
    }
    delay(2);
  }
  while (stepper->isRunning()) delay(1);
  delay(2000);
  stepper->moveTo(0, true);
  if (dev > 0.01f) {
    Serial.println(F("direction test passed: motor and angle agree"));
  } else if (dev < -0.01f) {
    angle_sign = -angle_sign;
    Serial.println(F("the angle runs the wrong way: set ANGLE_SIGN to -1 (done until the next reset)"));
  } else {
    Serial.println(F("no swing seen: check the magnet (m) and the pendulum's hub"));
  }
}

static void pivotTest() {
  // A free swing's turning points give the pivot's friction and the true vertical (PivotTest in
  // controller.h); the vertical re-centres the calibration, which friction leaves off by up to
  // friction / m g l.
  if (!calibrated) {
    Serial.println(F("calibrate (c) first, the pendulum hanging still"));
    return;
  }
  Serial.println(F("f test: lift the pendulum to 30-40 deg, hold it still, let go; the cart stays put; s aborts"));
  PivotTest pt;
  pt.reset(0.5f * CTL_PI / 180.0f, 25.0f * CTL_PI / 180.0f);
  bool lifted = false;
  uint32_t t0 = millis(), t_tp = 0, next = micros();
  while (true) {
    if (Serial.available() && Serial.read() == 's') {
      Serial.println(F("aborted"));
      return;
    }
    if ((int32_t)(micros() - next) < 0) continue;
    next += PERIOD_US;
    int32_t c;
    if (!readCounts(c)) {
      fault(F("angle sensor read failed"));
      return;
    }
    float a = Controller::wrap(angleFrom(c) - CTL_PI);  // from hanging
    if (!lifted) {
      if (fabsf(a) > 0.5f) {  // held above 28.6 deg: the hand's jitter stays over the 25 deg start
        lifted = true;
        t0 = millis();
      } else if (millis() - t0 > 30000UL) {
        Serial.println(F("not lifted within 30 s"));
        return;
      }
      continue;
    }
    if (pt.feed(a)) t_tp = millis();
    if (pt.n == 0 ? millis() - t0 > 30000UL : (pt.done(4.0f * CTL_PI / 180.0f) || millis() - t_tp > 4000UL)) break;
  }
  float tau, centre;
  if (!pt.result(CTL_MGL, tau, centre)) {
    Serial.println(F("fewer than 5 swings under 25 deg: far too much friction, or it was not let go"));
    return;
  }
  pivot_tau = tau;
  float mnm = tau * 1000.0f;
  Serial.print(F("pivot friction "));
  Serial.print(mnm, 2);
  Serial.print(F(" mN m (goal "));
  Serial.print(CFG_PIVOT_GOAL * 1000.0f, 2);
  Serial.print(F(", swing-up checked to "));
  Serial.print(CFG_PIVOT_MAX * 1000.0f, 2);
  Serial.print(F("): balanced, it will hunt about "));
  Serial.print(mnm * CFG_HUNT_DEG, 1);
  Serial.print(F(" deg and "));
  Serial.print(mnm * CFG_HUNT_MM, 0);
  Serial.println(F(" mm peak to peak"));
  if (tau > CFG_PIVOT_MAX) Serial.println(F("too stiff for the swing-up: free the pivot first (DESIGN.md, Pendulum)"));
  else if (tau > CFG_PIVOT_GOAL) Serial.println(F("above the goal: free the pivot (DESIGN.md, Pendulum)"));
  float s = angle_sign * centre * COUNTS / (2.0f * CTL_PI);  // the true vertical, in counts from the reference
  hang_ref += (int32_t)(s >= 0.0f ? s + 0.5f : s - 0.5f);
#if !USE_ENCODER
  hang_ref = ((hang_ref % COUNTS) + COUNTS) % COUNTS;
#endif
  Serial.print(F("hanging re-centred by "));
  Serial.print(centre * 57.29578f, 2);
  Serial.println(F(" deg"));
}

// ---------------------------------------------------------------- run
static void startRun() {
  if (!homed || !calibrated) {
    Serial.println(F("home (h) and calibrate (c) first"));
    return;
  }
  if (!sensorOk()) {
    fault(F("angle sensor: no magnet or out of range (m)"));
    return;
  }
  if (pivot_tau > CFG_PIVOT_MAX) Serial.println(F("warning: the pivot is stiffer than the swing-up was checked for (f)"));
  else if (pivot_tau < 0.0f) Serial.println(F("note: f measures the pivot's friction and re-centres hanging"));
  ctl.reset();
  stepper->enableOutputs();
  stepper->setSpeedInHz(steps(CTL_V_MAX));
  stepper->setAcceleration(steps(CTL_A_MAX));
  overruns = 0;
  ticks = 0;
  next_us = micros();
  state = RUNNING;
  Serial.println(F("running: s stops"));
}

static void stopRun() {
  stepper->stopMove();
  if (state == RUNNING) state = IDLE;
  Serial.println(F("stopped"));
}

static void controlStep() {
  if (swMinus() || swPlus()) {
    stepper->forceStop();
    homed = false;
    fault(F("limit switch: home again (h)"));
    return;
  }
  int32_t c;
  if (!readCounts(c)) {
    stepper->stopMove();
    fault(F("angle sensor read failed"));
    return;
  }
  float th = angleFrom(c);
  float x = stepper->getCurrentPosition() / CFG_STEPS_PER_M;
  float v = stepper->getCurrentSpeedInMilliHz(false) * 0.001f / CFG_STEPS_PER_M;
  if (fabsf(x) > CFG_X_SOFT) {
    stepper->stopMove();
    fault(F("soft limit: the cart ran past it"));
    return;
  }
  float u = ctl.step(th, x, v);
  stepper->moveByAcceleration(steps(u), true);
  if (telemetry && ++ticks % (CTL_HZ / 25) == 0) {  // ms, x mm, v mm/s, angle deg, u m/s^2, mode
    Serial.print(millis());
    Serial.print(',');
    Serial.print(x * 1000.0f, 1);
    Serial.print(',');
    Serial.print(v * 1000.0f, 0);
    Serial.print(',');
    Serial.print(Controller::wrap(th) * 57.29578f, 2);
    Serial.print(',');
    Serial.print(u, 2);
    Serial.print(',');
    Serial.println(ctl.mode);
  }
}

// ---------------------------------------------------------------- commands
static void jog(float dx) {
  if ((dx < 0.0f && swMinus()) || (dx > 0.0f && swPlus())) {
    Serial.println(F("a switch is pressed on that side"));
    return;
  }
  stepper->enableOutputs();
  stepper->setSpeedInHz(steps(0.05f));
  stepper->setAcceleration(steps(0.5f));
  stepper->move(steps(dx), true);
}

static void info() {
  int32_t c = 0;
  bool ok = readCounts(c);
  Serial.print(state == RUNNING ? F("running") : state == FAULT ? F("FAULT") : F("idle"));
  Serial.print(homed ? F(", homed") : F(", not homed"));
  Serial.print(calibrated ? F(", calibrated") : F(", not calibrated"));
  Serial.print(F(" | x "));
  Serial.print(stepper->getCurrentPosition() / CFG_STEPS_PER_M * 1000.0f, 1);
  Serial.print(F(" mm | angle "));
  if (!ok) Serial.print(F("?"));
  else if (calibrated) Serial.print(Controller::wrap(angleFrom(c)) * 57.29578f, 2);
  else Serial.print(c);
  Serial.print(calibrated ? F(" deg") : F(" counts"));
  Serial.print(F(" | switches -x "));
  Serial.print(swMinus() ? F("PRESSED") : F("ok"));
  Serial.print(F(", +x "));
  Serial.print(swPlus() ? F("PRESSED") : F("ok"));
  Serial.print(F(" | late periods "));
  Serial.print(overruns);
  sensorReport();
  Serial.println();
}

static void help() {
  Serial.println(F("h home (towards -x)  c calibrate (pendulum hanging still)  d direction test  f pivot friction"));
  Serial.println(F("r run  s stop  o motor off (move the cart by hand)  +/- jog 10 mm  m monitor the sensor  i info"));
  Serial.println(F("t telemetry: ms, x mm, v mm/s, angle deg (0 up), u m/s^2, mode (0 swing, 1 balance)"));
}

static void commands() {
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r' || ch == ' ') continue;
    monitoring = false;
    if (state == RUNNING && ch != 's' && ch != 't') {
      Serial.println(F("running: s stops"));
      continue;
    }
    switch (ch) {
      case '?': help(); break;
      case 'h': state = IDLE; home(); break;
      case 'c': calibrate(); break;
      case 'd': directionTest(); break;
      case 'f': pivotTest(); break;
      case 'r': startRun(); break;
      case 's': stopRun(); break;
      case 'o':
        stepper->disableOutputs();
        homed = false;
        Serial.println(F("motor off: the cart moves by hand; home again (h) after"));
        break;
      case '+': jog(0.01f); break;
      case '-': jog(-0.01f); break;
      case 'm': monitoring = true; break;
      case 'i': info(); break;
      case 't':
        telemetry = !telemetry;
        Serial.println(telemetry ? F("telemetry on") : F("telemetry off"));
        break;
      default: Serial.println(F("? for the commands"));
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SW_MINUS, INPUT_PULLUP);
  pinMode(PIN_SW_PLUS, INPUT_PULLUP);
#if USE_ENCODER
  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), encoderIsr, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_B), encoderIsr, CHANGE);
#else
  Wire.begin();
  Wire.setClock(I2C_HZ);
#if defined(WIRE_HAS_TIMEOUT)
  Wire.setWireTimeout(3000, true);
#elif defined(ARDUINO_ARCH_ESP32)
  Wire.setTimeOut(5);
#endif
#endif
  engine.init();
  stepper = engine.stepperConnectToPin(PIN_STEP);
  if (stepper == NULL) {
    Serial.println(F("FastAccelStepper cannot use PIN_STEP (Uno/Nano: pin 9 or 10)"));
    while (true) delay(1000);
  }
  stepper->setDirectionPin(PIN_DIR, DIR_HIGH_MOVES_PLUS);
  stepper->setEnablePin(PIN_EN);
  stepper->setAutoEnable(false);
  stepper->setForwardPlanningTimeInMs(CFG_PLANNING_MS);
  stepper->disableOutputs();
  Serial.println(F("inverted pendulum: ? for the commands"));
  if (!sensorOk()) Serial.println(F("warning: angle sensor not found or magnet out of range (m to check)"));
}

void loop() {
  commands();
  if (state == RUNNING) {
    uint32_t now = micros();
    if ((int32_t)(now - next_us) >= 0) {
      if ((int32_t)(now - next_us) > (int32_t)PERIOD_US) {
        overruns++;
        next_us = now;
      }
      next_us += PERIOD_US;
      controlStep();
    }
  } else if (monitoring && millis() - monitor_ms >= 200) {
    monitor_ms = millis();
    info();
  }
}
