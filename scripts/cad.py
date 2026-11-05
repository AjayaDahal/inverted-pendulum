"""build123d helpers: boxes, cylinders, slots, nut pockets, prisms, the HTD pulley and rack."""
import math

from build123d import Box, Circle, Cylinder, Face, Plane, Pos, Rectangle, Rot, Vector, Wire, export_stl, extrude

import params as P


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))


def cyl_z(r, x, y, z0, z1):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(r, abs(z1 - z0))


def cyl_y(r, x, z, y0, y1):
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(r, abs(y1 - y0))


def cyl_x(r, y, z, x0, x1):
    return Pos((x0 + x1) / 2, y, z) * Rot(0, 90, 0) * Cylinder(r, abs(x1 - x0))


def slot_z(r, x0, y0, x1, y1, z0, z1):
    """Stadium prism along z from centre (x0, y0) to (x1, y1)."""
    s = cyl_z(r, x0, y0, z0, z1) + cyl_z(r, x1, y1, z0, z1)
    length = math.hypot(x1 - x0, y1 - y0)
    if length > 1e-6:
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        s += Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Rot(0, 0, ang) * Box(length, 2 * r, abs(z1 - z0))
    return s


def slot_y(r, x0, z0, x1, z1, y0, y1):
    """Stadium prism along y from centre (x0, z0) to (x1, z1)."""
    s = cyl_y(r, x0, z0, y0, y1) + cyl_y(r, x1, z1, y0, y1)
    length = math.hypot(x1 - x0, z1 - z0)
    if length > 1e-6:
        ang = math.degrees(math.atan2(z1 - z0, x1 - x0))
        s += Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Rot(0, -ang, 0) * Box(length, abs(y1 - y0), 2 * r)
    return s


def slot_x(r, y0, z0, y1, z1, x0, x1):
    """Stadium prism along x from centre (y0, z0) to (y1, z1)."""
    s = cyl_x(r, y0, z0, x0, x1) + cyl_x(r, y1, z1, x0, x1)
    length = math.hypot(y1 - y0, z1 - z0)
    if length > 1e-6:
        ang = math.degrees(math.atan2(z1 - z0, y1 - y0))
        s += Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Rot(ang, 0, 0) * Box(abs(x1 - x0), length, 2 * r)
    return s


def _hex_face(af, plane):
    r = af / math.sqrt(3)
    pts = [(r * math.cos(math.radians(30 + 60 * k)), r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    return Face(Wire.make_polygon([plane.from_local_coords(Vector(x, y, 0)) for x, y in pts], close=True))


def hex_z(af, x, y, z0, z1, turn=0.0):
    """Hexagonal prism along z, `af` across flats (flats parallel to x when turn = 0)."""
    pl = Plane(origin=(x, y, min(z0, z1)), x_dir=(math.cos(math.radians(turn)), math.sin(math.radians(turn)), 0),
               z_dir=(0, 0, 1))
    return extrude(_hex_face(af, pl), amount=abs(z1 - z0), dir=pl.z_dir)


def hex_y(af, x, z, y0, y1):
    pl = Plane(origin=(x, min(y0, y1), z), x_dir=(1, 0, 0), z_dir=(0, 1, 0))
    return extrude(_hex_face(af, pl), amount=abs(y1 - y0), dir=pl.z_dir)


def hex_x(af, y, z, x0, x1):
    pl = Plane(origin=(min(x0, x1), y, z), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    return extrude(_hex_face(af, pl), amount=abs(x1 - x0), dir=pl.z_dir)


def prism(pts, plane, amount):
    """Extrude the polygon `pts` (local 2-D coordinates of `plane`) by `amount` along the plane's
    normal, whichever way the polygon winds."""
    face = Face(Wire.make_polygon([plane.from_local_coords(Vector(u, v, 0)) for u, v in pts], close=True))
    return extrude(face, amount=amount, dir=plane.z_dir)


def prism_xz(pts, y0, y1):
    """Polygon of (x, z) points extruded from y0 to y1."""
    return prism([(x, -z) for x, z in pts], Plane(origin=(0, min(y0, y1), 0), x_dir=(1, 0, 0), z_dir=(0, 1, 0)),
                 abs(y1 - y0))


def prism_yz(pts, x0, x1):
    """Polygon of (y, z) points extruded from x0 to x1."""
    return prism(pts, Plane(origin=(min(x0, x1), 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0)), abs(x1 - x0))


def prism_xy(pts, z0, z1):
    return prism(pts, Plane(origin=(0, 0, min(z0, z1)), x_dir=(1, 0, 0), z_dir=(0, 0, 1)), abs(z1 - z0))


def screw_hole_z(d, x, y, z0, z1, head=None, head_at="top", head_depth=0.0):
    """Clearance hole along z with an optional counterbore (head = (diameter, depth))."""
    s = cyl_z(d / 2, x, y, z0 - 0.01, z1 + 0.01)
    if head:
        hd, depth = head
        if head_at == "top":
            s += cyl_z(hd / 2 + P.FIT, x, y, z1 - depth, z1 + 0.01)
        else:
            s += cyl_z(hd / 2 + P.FIT, x, y, z0 - 0.01, z0 + depth)
    return s


# ---------------------------------------------------------------- HTD 5M teeth
def pulley_teeth_face(teeth=P.TEETH):
    """The toothed section's outline in the XY plane: the tip circle less the circular grooves."""
    r_c = P.R_TIP - P.GROOVE_DEPTH + P.GROOVE_R
    face = Circle(P.R_TIP)
    for k in range(teeth):
        a = 2 * math.pi * k / teeth
        face -= Pos(r_c * math.cos(a), r_c * math.sin(a)) * Circle(P.GROOVE_R)
    return face


def groove_angle(k, teeth=P.TEETH):
    return 360.0 * k / teeth


def rack_grooves(x0, x1, z_land, y0, y1, phase=0.0):
    """Cylinders along y that cut the belt's tooth seats into a flat jaw whose face is at z_land:
    pitch P.BELT['pitch'], the same groove as the pulley's, centred on x = phase + k * pitch."""
    pitch = P.BELT["pitch"]
    z_c = z_land - P.GROOVE_DEPTH + P.GROOVE_R
    cut = None
    k0 = math.floor((x0 - phase) / pitch) - 1
    k1 = math.ceil((x1 - phase) / pitch) + 1
    for k in range(k0, k1 + 1):
        x = phase + k * pitch
        c = cyl_y(P.GROOVE_R, x, z_c, y0, y1)
        cut = c if cut is None else cut + c
    return cut


def export(part, path):
    export_stl(part, path, tolerance=0.02, angular_tolerance=0.15)


__all__ = ["box", "cyl_x", "cyl_y", "cyl_z", "slot_x", "slot_y", "slot_z", "hex_x", "hex_y", "hex_z", "prism",
           "prism_xz", "prism_yz", "prism_xy", "screw_hole_z", "pulley_teeth_face", "rack_grooves", "export",
           "Rectangle", "Plane"]
