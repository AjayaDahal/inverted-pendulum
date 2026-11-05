"""Regenerate everything in order: parts, print orientation, assembly and STEP, slicing (every part
and plate as a 3MF project and its G-code), the complete projects (each plate sliced again and
checked), the simulation (it weighs the sliced parts), the firmware's config, the tracker, the BOM,
the viewer manifest, then the gate. Renders: scripts/capture.py (headless Edge) after a geometry change.

Usage: python scripts/build_all.py [--no-slice]
"""
import os
import subprocess
import sys

import asbuilt
import assembly
import make_bom
import make_firmware
import make_print_ready
import make_tracker
import make_viewer
import sim
import structure


def main():
    parts = structure.build()
    make_print_ready.build()
    assembly.write(parts=parts)
    asbuilt.build()
    args, projects_ok = [], True
    try:
        if "--no-slice" in sys.argv:
            print("--no-slice: G-code checks skipped; run slice_all.py before printing")
            args.append("--no-gcode")
        else:
            import make_projects
            import slice_all
            slice_all.main()
            projects_ok = make_projects.main(check=True)
    finally:
        sim.run()
        make_firmware.main()
        make_tracker.main()
        make_bom.main()
        make_viewer.main()
    here = os.path.dirname(os.path.abspath(__file__))
    code = subprocess.call([sys.executable, "check_parts.py", *args], cwd=here)
    sys.exit(code or (0 if projects_ok else 1))


if __name__ == "__main__":
    main()
