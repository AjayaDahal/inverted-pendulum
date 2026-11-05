// The pendulum's controller: one call per control period. A line-for-line port of
// scripts/sim.py's Controller (same names, same order); check_parts.py replays a simulation through
// this file (firmware/test/controller_test.cpp) and compares every command.
#pragma once
#include <math.h>
#include "config.h"

struct Controller {
  enum { SWING = 0, BALANCE = 1, HIST = 8 };
  int mode;
  bool have_prev;
  float th_prev, w, z;
  int kick;      // control periods into a kick, -1: none
  int wait;      // periods before another kick may start
  int still;     // periods the pendulum has rested near hanging
  float kick_dir;
  float hist[HIST];  // the last commands, oldest first

  void reset() {
    mode = SWING;
    have_prev = false;
    th_prev = 0.0f;
    w = 0.0f;
    z = 0.0f;
    kick = -1;
    wait = 0;
    still = 0;
    kick_dir = 1.0f;
    for (int i = 0; i < HIST; i++) hist[i] = 0.0f;
  }

  static float wrap(float a) {  // to (-pi, pi]
    while (a > CTL_PI) a -= 2.0f * CTL_PI;
    while (a <= -CTL_PI) a += 2.0f * CTL_PI;
    return a;
  }

  static float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

  // th_meas: angle (rad, 0 upright, + leaning towards +x, any turn); x: cart (m); v: cart speed
  // (m/s). Returns the cart acceleration to command (m/s^2).
  float step(float th_meas, float x, float v) {
    const float dt = CTL_DT;
    if (!have_prev) {
      th_prev = th_meas;
      have_prev = true;
    }
    float d = wrap(th_meas - th_prev);
    th_prev = th_meas;
    w += CTL_ALPHA * (d / dt - w);
    float th = wrap(th_meas);
    float c = cosf(th);
    float u;
    if (mode == BALANCE && fabsf(th) > CTL_FALL) {
      mode = SWING;
      still = 0;
    }
    if (mode == SWING && kick < 0 && c > CTL_CATCH_COS && fabsf(th + w / CTL_W0) < CTL_CATCH_XI) {
      mode = BALANCE;  // near the top and coasting into it: little left to correct
      z = 0.0f;
    }
    if (mode == BALANCE) {
      // the state once the commands still on their way to the motor have acted (linear model)
      float xp = x, vp = v, thp = th, wp = w;
      for (int i = 0; i < CTL_PRED_N; i++) {
        float uq = hist[HIST - CTL_PRED_N + i];
        wp += (CTL_A_LIN * thp - CTL_B_LIN * uq) * dt;
        thp += wp * dt;
        xp += (vp + 0.5f * uq * dt) * dt;
        vp += uq * dt;
      }
      u = -(CTL_K[0] * xp + CTL_K[1] * vp + CTL_K[2] * thp + CTL_K[3] * wp + CTL_K[4] * z);
      if (fabsf(u) < CTL_A_MAX) z = clampf(z + x * dt, -CTL_Z_MAX, CTL_Z_MAX);
    } else if (kick >= 0) {
      u = kick_dir * (kick < CTL_KICK_N ? CTL_KICK_A : -CTL_KICK_A);
      kick += 1;
      if (kick >= 2 * CTL_KICK_N) {
        kick = -1;
        wait = CTL_WAIT_N;
      }
    } else {
      float e = 0.5f * CTL_J * w * w + CTL_MGL * (c - 1.0f - CTL_E_REF);
      float fade = 1.0f - (x / CTL_X_PUMP) * (x / CTL_X_PUMP);  // no pumping near the travel ends
      if (fade < 0.0f) fade = 0.0f;
      // cart speed ~ -sin(theta), saturated (beats pivot friction at small swings) and led by
      // CTL_LEAD s (the cart's reversal lags): its acceleration ~ -omega cos(theta) pumps energy
      // in, while speed and travel stay bounded
      float vt = -CTL_PUMP * fade * tanhf(-CTL_KE * e / CTL_MGL) * tanhf(CTL_KS * sinf(th + w * CTL_LEAD));
      u = CTL_KV * (vt - v) - CTL_KX * x;
      if (wait > 0) wait -= 1;
      if (c < -0.95f && fabsf(w) < CTL_STILL_W && wait == 0) {
        still += 1;
        if (still >= CTL_STILL_N) {  // at rest near hanging: kick, towards the centre
          kick = 0;
          still = 0;
          kick_dir = x > 0.0f ? -1.0f : 1.0f;
        }
      } else {
        still = 0;
      }
    }
    u = clampf(u, -CTL_A_MAX, CTL_A_MAX);
    if ((v >= CTL_V_MAX && u > 0.0f) || (v <= -CTL_V_MAX && u < 0.0f)) u = 0.0f;
    for (int i = 0; i < HIST - 1; i++) hist[i] = hist[i + 1];
    hist[HIST - 1] = u;
    return u;
  }
};

// The f test (pendulum.ino): the pendulum swings freely from about 30 deg, the cart standing.
// Coulomb friction at the pivot takes the same angle off every half swing (2 friction / m g l) and
// moves each half swing's centre by +-friction / m g l; viscous drag takes off in proportion to
// the swing. A straight line through the decrements of consecutive spans against the spans gives
// the Coulomb part (it makes the balanced pendulum hunt), and the turning points, weighted
// 1-2-1, give the true vertical. Checked on simulated swings by firmware/test/controller_test.cpp.
struct PivotTest {
  enum { N = 48 };
  float tp[N];  // turning points below the start limit, rad from the hanging reference
  int n, dir;
  bool armed;
  float ext, hyst, limit;

  void reset(float hysteresis, float start_limit) {
    n = 0;
    dir = 0;
    armed = false;
    ext = 0.0f;
    hyst = hysteresis;
    limit = start_limit;
  }

  // a: angle from hanging (rad). Returns true when it records a turning point.
  bool feed(float a) {
    if (!armed) {
      ext = a;
      armed = true;
      return false;
    }
    if (dir == 0) {
      if (fabsf(a - ext) < hyst) return false;
      dir = a > ext ? 1 : -1;
      ext = a;
      return false;
    }
    if ((dir > 0 && a > ext) || (dir < 0 && a < ext)) {
      ext = a;
      return false;
    }
    if (fabsf(a - ext) < hyst) return false;
    bool added = false;
    if ((n > 0 || fabsf(ext) < limit) && n < N) {  // from the first one under the limit, every one
      tp[n++] = ext;
      added = true;
    }
    dir = -dir;
    ext = a;
    return added;
  }

  bool done(float min_span) const { return n >= N || (n >= 2 && fabsf(tp[n - 1] - tp[n - 2]) < min_span); }

  // Coulomb friction (N m) and the true vertical (rad from the reference); false below 5 turning points.
  bool result(float mgl, float &tau, float &centre) const {
    if (n < 5) return false;
    float sx = 0.0f, sy = 0.0f, sxx = 0.0f, sxy = 0.0f, sc = 0.0f;
    int m = n - 2;
    for (int i = 0; i < m; i++) {
      float s1 = fabsf(tp[i + 1] - tp[i]), s2 = fabsf(tp[i + 2] - tp[i + 1]);
      float x = 0.5f * (s1 + s2), y = s1 - s2;
      sx += x;
      sy += y;
      sxx += x * x;
      sxy += x * y;
      sc += 0.25f * (tp[i] + 2.0f * tp[i + 1] + tp[i + 2]);
    }
    float den = m * sxx - sx * sx;
    float kappa = den > 1e-9f ? (m * sxy - sx * sy) / den : 0.0f;
    if (kappa < 0.0f) kappa = 0.0f;
    float d4 = (sy - kappa * sx) / m;  // 4 x friction / m g l
    tau = d4 > 0.0f ? 0.25f * mgl * d4 : 0.0f;
    centre = sc / m;
    return true;
  }
};
