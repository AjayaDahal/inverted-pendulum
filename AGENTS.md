# Notes for agents

- The owner's rule: **nothing new to buy**. Design around the parts on his machine (2020/2040
  frame, 8 mm rods on SK8s, SC8UU blocks, KP08s, NEMA 17, HTD 5M 15 mm belt, AS5600 or a 600 P/R
  optical encoder, his own driver and controller) and plain M3/M4/M5 screws with 20-series
  T-nuts. Everything else is printed. `BOM.md` lists it all.
- His photos are in `git_ignore_this/` and stay private: the folder is in `.gitignore`; never
  commit or publish them, or any picture taken from them.
- The frame's size is an estimate from the photos (`REPORT.md`, O1). When he measures it, put the
  numbers in `scripts/params.py` (`FRAME_L`, `FRAME_W`, `FRAME_H`, `ROD_SPACING`, `ROD_L`) and run
  `python scripts/build_all.py`. Every other dimension follows from them.
- After any change to `scripts/` or `slicer_profiles/`, run `python scripts/build_all.py`
  (rebuild, re-slice, re-simulate, verify; `--no-slice` without the slicer).
  `python scripts/check_parts.py` must pass before anything is printed; CI runs it on every push.
- Generated, never edit by hand: `parts/` (STLs, `assembly.json`, `sim.json`, the STEP), `3mf/`,
  `gcode/`, `BOM.md`, `viewer/manifest.json`, `renders/`. In `tracker.md` edit only the Status
  column. The gate fails when any of them is stale.
- The belt is the point of the redesign: pulleys and clamp in one plane (y = 0), both axles at one
  height, flanges on both sides, a toothed clamp, a tensioner that also squares the idler
  (`DESIGN.md`, "How the belt runs now"). The gate's `belt` check holds that; keep it passing
  rather than loosening it.
- The pendulum must turn a full circle at every cart position (swing-up needs it): the gate's
  `pendulum` check sweeps it. Anything added to the cart's front must stay out of that disc.
- Control numbers come from `scripts/sim.py`, which weighs the sliced parts. After changing a
  pendulum or carriage part, `build_all.py` re-runs it; update `DESIGN.md`'s Control section if
  the gains or times move.
- Renders: after a geometry change, `python scripts/capture.py` (headless Edge, a few minutes)
  re-renders `renders/*.png` and the README's GIFs; `--gif` redoes only the animations. Check a
  GIF has more than one frame: Pillow merges identical frames into one.
- When a finding is fixed or a new one is found, update `REPORT.md` (status table and text) in
  the same commit.
- Pushing to GitHub over HTTPS: very large packs get reset on this network. Push in commits of
  about 20 MB or less (the G-code folders are the large part).
