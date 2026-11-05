// Tests the firmware's controller.h against scripts/sim.py, on the host (g++ or clang++).
// 1. Replays simulated control periods through Controller and compares every command with the
//    simulation's. scripts/make_firmware.py (and check_parts.py) writes the vectors: angle, x, v,
//    command, mode per line; a line starting with # starts a new run.
// 2. Runs PivotTest (the f test) on simulated free swings of this pendulum: it must find the
//    pivot's Coulomb friction and the true vertical, with and without viscous drag.
// Prints one JSON line last; exits 1 on any failure.
#include <math.h>
#include <stdio.h>

#include "../pendulum/controller.h"

// Float against the simulation's double: m/s^2, scaled by 1 + |command|.
static const double TOL = 5e-3;
static const double PI_D = 3.14159265358979323846;

// A free swing from 30 deg (RK4 at 1 kHz, AS5600 counts at the control rate) with Coulomb friction
// tau (N m) and viscous drag cv (N m s), the hanging reference e0 (rad) off the true vertical.
static bool pivotCase(double tau, double cv, double e0, double &tau_est, double &centre_err) {
  const double J = CTL_J, mgl = CTL_MGL, dt = 0.001, q = 2.0 * PI_D / CFG_COUNTS_AS5600;
  double th = 30.0 * PI_D / 180.0, w = 0.0;
  PivotTest p;
  p.reset(0.5f * CTL_PI / 180.0f, 25.0f * CTL_PI / 180.0f);
  for (int k = 0; k < 90000; k++) {
    if (k % (1000 / CTL_HZ) == 0) {
      p.feed((float)(floor((th + e0) / q + 0.5) * q));
      if (p.done(4.0f * CTL_PI / 180.0f)) break;
    }
    double t[4], v[4], a[4];
    for (int s = 0; s < 4; s++) {
      double h = s == 0 ? 0.0 : (s == 3 ? dt : 0.5 * dt);
      t[s] = th + (s ? h * v[s - 1] : 0.0);
      v[s] = w + (s ? h * a[s - 1] : 0.0);
      a[s] = (-mgl * sin(t[s]) - cv * v[s] - tau * tanh(v[s] * 50.0)) / J;
    }
    th += dt / 6.0 * (v[0] + 2.0 * v[1] + 2.0 * v[2] + v[3]);
    w += dt / 6.0 * (a[0] + 2.0 * a[1] + 2.0 * a[2] + a[3]);
  }
  float te = 0.0f, ce = 0.0f;
  if (!p.result(CTL_MGL, te, ce)) return false;
  tau_est = te;
  centre_err = ce - e0;
  return true;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: %s vectors.csv\n", argv[0]);
    return 2;
  }
  FILE *f = fopen(argv[1], "r");
  if (!f) {
    perror(argv[1]);
    return 2;
  }
  Controller c;
  c.reset();
  char line[512];
  long runs = 0, n = 0, bad = 0;
  double worst = 0.0, worst_ratio = 0.0;
  while (fgets(line, sizeof line, f)) {
    if (line[0] == '#') {
      c.reset();
      runs++;
      continue;
    }
    double th, x, v, u_ref;
    int mode_ref;
    if (sscanf(line, "%lf,%lf,%lf,%lf,%d", &th, &x, &v, &u_ref, &mode_ref) != 5) continue;
    float u = c.step((float)th, (float)x, (float)v);
    double du = fabs((double)u - u_ref);
    double tol = TOL * (1.0 + fabs(u_ref));
    if (du > worst) worst = du;
    if (du / tol > worst_ratio) worst_ratio = du / tol;
    if (du > tol || c.mode != mode_ref) {
      if (bad < 5) printf("run %ld, period %ld: command %.6f, sim %.6f; mode %d, sim %d\n", runs, n, u, u_ref, c.mode, mode_ref);
      bad++;
    }
    n++;
  }
  fclose(f);

  // the f test: friction within 0.1 mN m + 15 %, vertical within 0.1 deg
  const double taus[] = {0.25e-3, 0.5e-3, 1.0e-3, 2.5e-3}, cvs[] = {0.0, 2e-4}, e0s[] = {0.0, 0.5 * PI_D / 180.0};
  int cases = 0, pbad = 0;
  double tau_err = 0.0, centre_err = 0.0;
  for (double tau : taus)
    for (double cv : cvs)
      for (double e0 : e0s) {
        double te = -1.0, ce = 0.0;
        bool ok = pivotCase(tau, cv, e0, te, ce);
        cases++;
        double et = fabs(te - tau);
        if (ok && et > tau_err) tau_err = et;
        if (ok && fabs(ce) > centre_err) centre_err = fabs(ce);
        if (!ok || et > 0.1e-3 + 0.15 * tau || fabs(ce) > 0.1 * PI_D / 180.0) {
          printf("f test, friction %.2f mN m, drag %.1e N m s, reference off %.2f deg: %s %.3f mN m, vertical off %.3f deg\n",
                 tau * 1e3, cv, e0 * 180.0 / PI_D, ok ? "found" : "too few swings", te * 1e3, ce * 180.0 / PI_D);
          pbad++;
        }
      }
  printf("{\"runs\": %ld, \"steps\": %ld, \"mismatches\": %ld, \"worst_du\": %.3g, \"worst_ratio\": %.3g, "
         "\"pivot_cases\": %d, \"pivot_bad\": %d, \"pivot_tau_err_mNm\": %.3g, \"pivot_centre_err_deg\": %.3g}\n",
         runs, n, bad, worst, worst_ratio, cases, pbad, tau_err * 1e3, centre_err * 180.0 / PI_D);
  return (bad || pbad) ? 1 : 0;
}
