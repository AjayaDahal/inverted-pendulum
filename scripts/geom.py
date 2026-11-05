"""Mesh and STL helpers shared by the scripts, and the repository's paths."""
import math
import os
import struct

import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PARTS_DIR = os.path.join(ROOT, "parts")
ASSEMBLY = os.path.join(PARTS_DIR, "assembly")      # printed parts in their own (local) frame
VITAMINS = os.path.join(PARTS_DIR, "vitamins")      # the owner's hardware, local frames
ASBUILT = os.path.join(PARTS_DIR, "as_built")       # v0: the machine as photographed
PRINT = os.path.join(PARTS_DIR, "print_ready")      # print orientation, on the bed
ASSEMBLY_JSON = os.path.join(PARTS_DIR, "assembly.json")


def rotation(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], float)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def transform(tris, R=None, t=(0, 0, 0)):
    out = np.asarray(tris, float) if R is None else np.asarray(tris, float) @ np.asarray(R, float).T
    return out + np.asarray(t, float)


def mat4(R=None, t=(0.0, 0.0, 0.0)):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    M[:3, 3] = t
    return M


def apply4(tris, M):
    M = np.asarray(M, float)
    return transform(tris, M[:3, :3], M[:3, 3])


def signed_volume(tris):
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    return float(np.sum(np.einsum("ij,ij->i", a, np.cross(b, c))) / 6.0)


def write_stl(path, tris):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tris = np.asarray(tris, np.float64)
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-20
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"] = nrm
    rec["v"] = tris
    with open(path, "wb") as f:
        f.write(os.path.basename(path).encode()[:80].ljust(80, b"\0"))
        f.write(struct.pack("<I", len(tris)))
        f.write(rec.tobytes())


def read_stl(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        verts = [list(map(float, ln.split()[1:4])) for ln in data.decode("utf-8", "replace").splitlines()
                 if ln.strip().startswith("vertex")]
        return np.array(verts, float).reshape(-1, 3, 3)
    n = struct.unpack("<I", data[80:84])[0]
    rec = np.frombuffer(data[84:84 + 50 * n], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    return rec["v"].astype(np.float64)


def bounds(tris):
    v = np.asarray(tris, float).reshape(-1, 3)
    return v.min(0), v.max(0)
