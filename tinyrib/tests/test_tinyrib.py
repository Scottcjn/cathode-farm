#!/usr/bin/env python3
"""TinyRIB conformance tests.

Builds the renderer with -DHOST_PREVIEW (same source the Macs run, only the pixel
output differs), renders small RIB scenes and asserts what came out.  Pure stdlib,
no pytest, no network:

    python3 tinyrib/tests/test_tinyrib.py

Every case here is a thing the renderer used to get wrong, plus regressions that
pin the behaviour of the two scenes the repo ships.
(c) Elyan Labs, GPL-2.0.
"""
import os, subprocess, sys, tempfile, math

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, "..", "tinyrib.c")
BIN  = None
TMP  = None
fails = []


# ---------- harness ----------
def build():
    global BIN, TMP
    TMP = tempfile.mkdtemp(prefix="tinyrib-test-")
    BIN = os.path.join(TMP, "tinyrib_host")
    cc = os.environ.get("CC", "cc")
    subprocess.run([cc, "-DHOST_PREVIEW", "-O2", "-o", BIN, SRC, "-lm"], check=True)


class Img:
    """A rendered frame; px(x, y) -> (r, g, b), 0..255."""
    def __init__(self, path):
        with open(path, "rb") as f:
            data = f.read()
        # P6 header: magic, width height, maxval - each followed by whitespace
        fields, i = [], 2
        while len(fields) < 3:
            while data[i:i + 1].isspace():
                i += 1
            j = i
            while not data[j:j + 1].isspace():
                j += 1
            fields.append(int(data[i:j])); i = j
        self.w, self.h, _ = fields
        self.body = data[i + 1:]

    def px(self, x, y):
        o = (y * self.w + x) * 3
        return tuple(self.body[o:o + 3])

    def colors(self):
        return {self.px(x, y) for y in range(self.h) for x in range(self.w)}


def render(rib, name="t"):
    rp = os.path.join(TMP, name + ".rib")
    pp = os.path.join(TMP, name + ".ppm")
    with open(rp, "w") as f:
        f.write(rib)
    r = subprocess.run([BIN, rp, pp], capture_output=True, timeout=120)
    assert r.returncode == 0, f"renderer exited {r.returncode}: {r.stderr.decode()[:300]}"
    return Img(pp)


RES = 64
FOV = 45.0
DIST = 6.0            # camera sits at z = -DIST looking down +z


def head(fov=FOV, dist=DIST, samples=1):
    return (f"Format {RES} {RES} 1\nPixelSamples {samples} {samples}\n"
            f'Projection "perspective" "fov" [{fov}]\n'
            f"Translate 0 0 {dist}\nWorldBegin\n"
            'LightSource "ambientlight" 1 "intensity" [1.0]\n')


def to_px(X, Y, dist=DIST, fov=FOV):
    """Where a point (X, Y, 0) lands, for the camera the header above sets up."""
    sc = math.tan(fov * math.pi / 360.0)
    px = RES / 2.0 * (1 + (X / dist) / sc)
    py = RES / 2.0 * (1 - (Y / dist) / sc)
    return int(px), int(py)


def near(a, b, tol=6):
    return all(abs(a[i] - b[i]) <= tol for i in range(3))


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        fails.append(name)


SKY = (135, 153, 191)   # the unlit background shade() returns on a miss


# ---------- attribute scoping (RI spec: AttributeBegin saves the whole state) ----------
def test_color_does_not_leak_out_of_a_block():
    im = render(head() +
                'Surface "matte"\nColor [1 0 0]\n'
                "AttributeBegin\n"
                "Color [0 1 0]\n"
                'Polygon "P" [-2 1 0  -0.2 1 0  -0.2 2 0  -2 2 0]\n'
                "AttributeEnd\n"
                # no Color here: must still be the red set before the block
                'Polygon "P" [0.2 1 0  2 1 0  2 2 0  0.2 2 0]\n'
                "WorldEnd\n", "colorscope")
    inside = im.px(*to_px(-1.0, 1.5))
    after = im.px(*to_px(1.0, 1.5))
    check("Color set inside AttributeBegin applies there",
          near(inside, (0, 255, 0)), inside)
    check("Color does not leak past AttributeEnd", near(after, (255, 0, 0)), after)


def test_shader_params_do_not_leak_out_of_a_block():
    """The floor block in gen_toys.py declares "Kd" [0.85]; the wall after it only
    says Surface "matte" and used to inherit that Kd and render too bright."""
    # a head-on distant light, so the pixel is Kd-driven and not clipped by ambient
    lit = (f"Format {RES} {RES} 1\n"
           f'Projection "perspective" "fov" [{FOV}]\n'
           f"Translate 0 0 {DIST}\nWorldBegin\n"
           'LightSource "distantlight" 1 "intensity" [1.0] "from" [0 0 -1] "to" [0 0 0]\n'
           'Surface "matte"\nColor [1 1 1]\n')
    base = (lit +
            "AttributeBegin\n"
            'Surface "matte" "Kd" [0.85]\n'
            'Polygon "P" [-2 1 0  -0.2 1 0  -0.2 2 0  -2 2 0]\n'
            "AttributeEnd\n"
            'Surface "matte"\n'
            'Polygon "P" [0.2 1 0  2 1 0  2 2 0  0.2 2 0]\n'
            "WorldEnd\n")
    ref = (lit +
           'Polygon "P" [0.2 1 0  2 1 0  2 2 0  0.2 2 0]\n'
           "WorldEnd\n")
    a = render(base, "kdleak").px(*to_px(1.0, 1.5))
    b = render(ref, "kdref").px(*to_px(1.0, 1.5))
    check("Kd from a previous block does not survive AttributeEnd", near(a, b), f"{a} vs {b}")


def test_constant_does_not_leak_out_of_a_block():
    im = render(head() + 'Surface "matte"\nColor [0.5 0.5 0.5]\n'
                "AttributeBegin\n"
                'Surface "constant"\nColor [1 1 1]\n'
                'Polygon "P" [-2 1 0  -0.2 1 0  -0.2 2 0  -2 2 0]\n'
                "AttributeEnd\n"
                'Polygon "P" [0.2 1 0  2 1 0  2 2 0  0.2 2 0]\n'
                "WorldEnd\n", "constleak")
    emissive = im.px(*to_px(-1.0, 1.5))
    after = im.px(*to_px(1.0, 1.5))
    check("constant surface is unlit/full brightness", near(emissive, (255, 255, 255)), emissive)
    check("constant does not leak past AttributeEnd",
          near(after, (128, 128, 128), 3), after)


def test_transformbegin_keeps_attributes():
    """TransformBegin/End saves only the transform - a Color set inside is meant to
    stay in force afterwards.  (This is the half the old code got right.)"""
    im = render(head() + 'Surface "matte"\nColor [1 0 0]\n'
                "TransformBegin\n"
                "Color [0 0 1]\n"
                "Translate -1 1.5 0\n"
                'Polygon "P" [-0.8 -0.5 0  0.8 -0.5 0  0.8 0.5 0  -0.8 0.5 0]\n'
                "TransformEnd\n"
                'Polygon "P" [0.2 1 0  2 1 0  2 2 0  0.2 2 0]\n'
                "WorldEnd\n", "xformscope")
    after = im.px(*to_px(1.0, 1.5))
    check("Color survives TransformEnd (transform-only scope)",
          near(after, (0, 0, 255)), after)


def test_deep_nesting_does_not_smash_the_stack():
    depth = 40                      # the stack was 16 entries with no bound check
    rib = head() + 'Surface "matte"\nColor [1 0 0]\n'
    rib += ("AttributeBegin\nColor [0 1 0]\nTranslate 0 0 1\n" * depth)
    rib += "AttributeEnd\n" * depth
    rib += 'Polygon "P" [-1 1 0  1 1 0  1 2 0  -1 2 0]\nWorldEnd\n'
    im = render(rib, "deep")
    got = im.px(*to_px(0.0, 1.5))
    check(f"{depth}-deep AttributeBegin nesting unwinds to the outer state",
          near(got, (255, 0, 0)), got)


# ---------- polygons ----------
def test_triangle_is_rendered():
    im = render(head() + 'Surface "matte"\nColor [0 1 0]\n'
                'Polygon "P" [-1.5 -1 0  1.5 -1 0  0 1.5 0]\nWorldEnd\n', "tri")
    got = im.px(*to_px(0.0, -0.5))
    check("3-vertex Polygon renders", near(got, (0, 255, 0)), got)


def test_pentagon_keeps_all_its_vertices():
    pts = [(math.cos(math.radians(90 + 72 * k)) * 1.6,
            math.sin(math.radians(90 + 72 * k)) * 1.6) for k in range(5)]
    P = "  ".join(f"{x:.4f} {y:.4f} 0" for x, y in pts)
    im = render(head() + 'Surface "matte"\nColor [0 0 1]\n'
                f'Polygon "P" [{P}]\nWorldEnd\n', "pent")
    # a point inside the pentagon but outside the first-four-vertices quad, i.e. it
    # only exists if vertex 5 was kept
    inside = im.px(*to_px(1.2, 0.2))
    check("5-vertex Polygon is not truncated to 4 vertices",
          near(inside, (0, 0, 255)), inside)


def test_sheared_quad_keeps_its_far_corner():
    """u = dot(hp, edge)/|edge| is only the affine coordinate when the two edges are
    perpendicular; on a sheared quad it threw the far corner away."""
    im = render(head() + 'Surface "matte"\nColor [1 1 0]\n'
                'Polygon "P" [-1.5 -1 0  0.5 -1 0  1.5 1 0  -0.5 1 0]\nWorldEnd\n', "shear")
    corner = im.px(*to_px(1.15, 0.75))      # well inside, near the sheared far corner
    outside = im.px(*to_px(-1.15, 0.75))    # mirror point, outside the quad
    check("sheared quad renders its far corner", near(corner, (255, 255, 0)), corner)
    check("sheared quad does not render outside itself", near(outside, SKY, 3), outside)


def test_trapezoid_shape_is_respected():
    im = render(head() + 'Surface "matte"\nColor [1 0 1]\n'
                'Polygon "P" [-1.8 -1 0  1.8 -1 0  0.5 1 0  -0.5 1 0]\nWorldEnd\n', "trap")
    inside = im.px(*to_px(0.0, 0.8))
    outside = im.px(*to_px(1.4, 0.8))       # inside the bounding rect, outside the trapezoid
    check("trapezoid interior renders", near(inside, (255, 0, 255)), inside)
    check("trapezoid does not spill past its slanted edge", near(outside, SKY, 3), outside)


def test_positions_found_when_P_is_not_the_first_parameter():
    im = render(head() + 'Surface "matte"\nColor [0 1 1]\n'
                'Polygon "Cs" [1 0 0  1 0 0  1 0 0  1 0 0] '
                '"P" [-1 1 0  1 1 0  1 2 0  -1 2 0]\nWorldEnd\n', "pparam")
    got = im.px(*to_px(0.0, 1.5))
    check('Polygon finds "P" when another parameter comes first',
          near(got, (0, 255, 255)), got)


def test_huge_polygon_does_not_overflow_the_number_buffer():
    n = 60                                  # nums[] was 64 doubles, unbounded
    pts = [(math.cos(2 * math.pi * k / n) * 1.5, math.sin(2 * math.pi * k / n) * 1.5)
           for k in range(n)]
    P = "  ".join(f"{x:.4f} {y:.4f} 0" for x, y in pts)
    im = render(head() + 'Surface "matte"\nColor [1 1 1]\n'
                f'Polygon "P" [{P}]\nWorldEnd\n', "bigpoly")
    got = im.px(*to_px(0.0, 0.0))
    check(f"{n}-vertex Polygon renders without corrupting memory",
          near(got, (255, 255, 255)), got)


# ---------- tokenizer ----------
def test_comments_are_not_executed():
    im = render(head() + 'Surface "matte"\nColor [0 1 0]\n'
                "# Color [1 0 0] would repaint this if comments were parsed\n"
                "## RenderMan RIB-Structure 1.1\n"
                'Polygon "P" [-1 1 0  1 1 0  1 2 0  -1 2 0]\n'
                "WorldEnd\n", "comment")
    got = im.px(*to_px(0.0, 1.5))
    check("# comments are skipped, not executed", near(got, (0, 255, 0)), got)


def test_long_shader_name_is_not_a_buffer_overflow():
    long_plastic = "/usr/local/renderman/shaders/" + "x" * 200 + "/plastic"
    im = render(head() + f'Surface "{long_plastic}"\nColor [1 0 0]\n'
                'Polygon "P" [-1 1 0  1 1 0  1 2 0  -1 2 0]\nWorldEnd\n', "longname")
    got = im.px(*to_px(0.0, 1.5))
    check("230-char shader name does not smash the 64-byte name buffer",
          got != (0, 0, 0) and near(got, (255, 0, 0), 60), got)


# ---------- shadows ----------
SHADOW_HEAD = ('Format 64 64 1\nProjection "perspective" "fov" [45]\n'
               "Translate 0 -1.5 7\nRotate 12 1 0 0\nWorldBegin\n"
               'LightSource "ambientlight" 1 "intensity" [0.15]\n'
               'LightSource "distantlight" 2 "intensity" [1.0] "from" [0 8 0] "to" [0 0 0]\n'
               'Surface "matte"\nColor [1 1 1]\n'
               'Polygon "P" [-20 0 -6  20 0 -6  20 0 20  -20 0 20]\n')


def _floor_under_blocker(surf):
    im = render(SHADOW_HEAD +
                "AttributeBegin\n"
                f'Surface "{surf}"\nColor [0.8 0.2 0.2]\n'
                "Translate 0 2.2 0\nSphere 0.7 -0.7 0.7 360\n"
                "AttributeEnd\nWorldEnd\n", "sh_" + surf)
    # the light is straight overhead, so the shadow lands directly below the sphere;
    # the sphere itself is high enough that the floor there is visible.
    col, best = None, None
    for y in range(40, 60):
        p = im.px(32, y)
        if best is None or sum(p) < sum(best):
            best, col = p, p
    return best


def test_solid_geometry_casts_a_shadow():
    dark = _floor_under_blocker("matte")
    check("a matte sphere still casts a shadow on the floor", sum(dark) < 200, dark)


def test_emissive_geometry_does_not_cast_a_shadow():
    dark = _floor_under_blocker("constant")
    check("an emissive (constant) prop does not paint a black shadow",
          sum(dark) > 300, dark)


# ---------- regression on the scenes the repo ships ----------
def test_shipped_toy_scene_still_has_its_four_balls():
    toy = os.path.join(HERE, "..", "toy.rib")
    if not os.path.exists(toy):
        check("toy.rib present", False, toy)
        return
    pp = os.path.join(TMP, "toy.ppm")
    subprocess.run([BIN, toy, pp], check=True, timeout=300)
    cols = Img(pp).colors()

    def present(c):
        return any(near(k, c, 24) for k in cols)
    for name, rgb in [("red", (229, 38, 30)), ("yellow", (249, 204, 25)),
                      ("blue", (25, 89, 216))]:
        check(f"toy.rib still renders the {name} ball", present(rgb))


def test_robot_animation_shows_the_face_it_builds():
    """gen_robot_laser.py authored the visor, both eyes, the chest plate and the chest
    core at +z - which is away from the camera - so they rendered inside the head and
    torso blocks.  Removing them left the frame byte-identical."""
    gen = os.path.join(HERE, "..", "gen_robot_laser.py")
    if not os.path.exists(gen):
        check("gen_robot_laser.py present", False, gen)
        return
    out = os.path.join(TMP, "anim")
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, TINYRIB_OUT=out)
    subprocess.run([sys.executable, gen, "30", "160", "120", "1"],
                   check=True, env=env, capture_output=True)
    pp = os.path.join(TMP, "anim00.ppm")
    subprocess.run([BIN, os.path.join(out, "frame00.rib"), pp], check=True, timeout=300)
    cols = Img(pp).colors()
    eye = (51, 255, 255)          # constant [0.2 1.0 1.0], so it renders exactly
    check("robot's glowing eyes are actually visible in frame 00",
          any(near(c, eye, 3) for c in cols))

    pp24 = os.path.join(TMP, "anim24.ppm")
    subprocess.run([BIN, os.path.join(out, "frame24.rib"), pp24], check=True, timeout=300)
    c24 = Img(pp24).colors()
    for name, rgb in [("outer glow", (191, 25, 20)), ("red layer", (249, 40, 30)),
                      ("white core", (255, 244, 224))]:
        check(f"laser beam's {name} reaches the frame",
              any(near(c, rgb, 3) for c in c24))


def main():
    build()
    print("TinyRIB conformance tests")
    for fn in sorted([f for f in globals() if f.startswith("test_")]):
        try:
            globals()[fn]()
        except Exception as e:          # a crash is a failed case, not a lost run
            print(f"  FAIL {fn} raised {e}")
            fails.append(fn)
    print()
    if fails:
        print(f"{len(fails)} FAILED: {', '.join(fails)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
