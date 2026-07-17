#!/usr/bin/env python3
"""'Robot Shooting a Laser' - an animation for TinyRIB (our RenderMan renderer on
the emulated 1994 Mac). Emits frameNN.rib, one per frame, using only what TinyRIB
supports: spheres, polygon boxes, matte/plastic/constant surfaces, distant+ambient
lights, and a RIB camera. A robot faces the camera, charges its cannon, and fires a
pulsing laser to the right into a target that bursts. (c) Elyan Labs, GPL-2.0."""
import os, sys, math
OUT = os.path.expanduser("~/mac-farm/tinyrib")
NF  = int(sys.argv[1]) if len(sys.argv) > 1 else 18
W, H = 160, 120

def box(cx,cy,cz, hx,hy,hz, col, surf="plastic", ks=0.5, rough=0.12):
    R,G,B = col
    s  = f'AttributeBegin\nSurface "{surf}" "Ks" [{ks}] "roughness" [{rough}]\n'
    s += f'Color [{R} {G} {B}]\n'
    # 8 corners around center, 6 faces as quads (absolute coords)
    X0,X1 = cx-hx,cx+hx; Y0,Y1 = cy-hy,cy+hy; Z0,Z1 = cz-hz,cz+hz
    faces = [
        [X0,Y0,Z1, X1,Y0,Z1, X1,Y1,Z1, X0,Y1,Z1],  # front +z
        [X1,Y0,Z0, X0,Y0,Z0, X0,Y1,Z0, X1,Y1,Z0],  # back  -z
        [X0,Y0,Z0, X0,Y0,Z1, X0,Y1,Z1, X0,Y1,Z0],  # left  -x
        [X1,Y0,Z1, X1,Y0,Z0, X1,Y1,Z0, X1,Y1,Z1],  # right +x
        [X0,Y1,Z1, X1,Y1,Z1, X1,Y1,Z0, X0,Y1,Z0],  # top   +y
        [X0,Y0,Z0, X1,Y0,Z0, X1,Y0,Z1, X0,Y0,Z1],  # bottom-y
    ]
    for f in faces:
        s += 'Polygon "P" [' + ' '.join(f'{v:.3f}' for v in f) + ']\n'
    return s + 'AttributeEnd\n'

def ball(x,y,z,r, col, surf="plastic", ks=0.6, rough=0.08):
    R,G,B = col
    return (f'AttributeBegin\nSurface "{surf}" "Ks" [{ks}] "roughness" [{rough}]\n'
            f'Color [{R} {G} {B}]\nTranslate {x} {y} {z}\nSphere {r} {-r} {r} 360\nAttributeEnd\n')

# --- the robot (faces camera; right arm is the cannon, extended to +x) ---
STEEL   = [0.42,0.47,0.55]
STEELD  = [0.30,0.34,0.42]
CANNON  = [0.55,0.58,0.64]
def robot():
    s  = box(-2.9,0.55,0.0, 0.28,0.55,0.32, STEELD)   # left leg
    s += box(-2.1,0.55,0.0, 0.28,0.55,0.32, STEELD)   # right leg
    s += box(-2.5,1.75,0.0, 0.85,0.75,0.55, STEEL)    # torso
    s += ball(-2.5,1.85,0.60, 0.14, [0.1,0.9,1.0], surf="constant")  # chest core (glow)
    s += box(-2.5,2.85,0.0, 0.50,0.42,0.48, STEEL)    # head
    s += ball(-2.72,2.90,0.46, 0.10, [0.2,1.0,1.0], surf="constant") # eye L
    s += ball(-2.28,2.90,0.46, 0.10, [0.2,1.0,1.0], surf="constant") # eye R
    s += box(-2.5,3.42,0.0, 0.05,0.18,0.05, STEELD)   # antenna
    s += ball(-2.5,3.66,0.0, 0.10, [1.0,0.3,0.2], surf="constant")   # antenna tip
    s += box(-3.45,1.35,0.0, 0.20,0.60,0.22, STEELD)  # left arm (down)
    # right arm = cannon, extended toward +x
    s += box(-1.35,1.95,0.0, 0.55,0.22,0.22, CANNON)  # upper cannon arm
    s += box(-0.45,1.95,0.0, 0.35,0.30,0.30, CANNON)  # cannon housing
    s += ball(-0.10,1.95,0.0, 0.20, STEELD, ks=0.7)   # muzzle ring
    return s

MUZZLE = (0.12, 1.95, 0.0)   # where the beam leaves the barrel
TARGET_X = 5.0

def frame(f):
    t = f/(NF-1)
    # phases: charge, fire (with a cool-down at the very end), impact burst
    charge = max(0.0, min(1.0, t/0.28))
    fire   = 1.0 if 0.28 < t < 0.86 else 0.0   # beam cuts off for the last frames
    firet  = max(0.0, (t-0.28)/0.40)           # 0..1: beam tip reaches target
    impact = max(0.0, (t-0.58)/0.42)           # 0..1 during impact burst
    mx,my,mz = MUZZLE

    rib = [f'Display "frame{f:02d}.tif" "file" "rgba"', f'Format {W} {H} 1',
           'PixelSamples 1 1', 'Projection "perspective" "fov" [50]',
           'Translate 0 -2.2 11', 'Rotate 5 1 0 0', 'WorldBegin',
           'LightSource "ambientlight" 1 "intensity" [0.22] "lightcolor" [0.7 0.75 0.95]',
           'LightSource "distantlight" 2 "intensity" [1.1] "lightcolor" [1.0 0.95 0.85] "from" [-6 7 -5] "to" [-2 1 0]',
           'LightSource "distantlight" 3 "intensity" [0.4] "lightcolor" [0.5 0.6 1.0] "from" [6 4 -4] "to" [0 1 0]']
    # dark metal floor
    rib.append('AttributeBegin\nSurface "plastic" "Ks" [0.3] "roughness" [0.2]\n'
               'Color [0.20 0.22 0.28]\nPolygon "P" [-30 0 -6  30 0 -6  30 0 26  -30 0 26]\nAttributeEnd')
    # back wall (cool, dim)
    rib.append('AttributeBegin\nSurface "matte"\nColor [0.14 0.16 0.24]\n'
               'Polygon "P" [-30 0 13  30 0 13  30 24 13  -30 24 13]\nAttributeEnd')
    rib.append(robot())

    # charge glow at the muzzle (grows while charging, flickers while firing)
    glow = 0.10 + 0.35*charge
    if fire: glow = 0.32 + 0.10*math.sin(f*1.7)
    rib.append(ball(mx,my,mz, glow, [1.0,0.85,0.3], surf="constant"))

    tgt_cx = TARGET_X+0.6
    if fire:
        # beam tip advances quickly to the target, then holds
        tip = mx + (TARGET_X-mx)*min(1.0, firet*2.4)
        thick = 0.17 + 0.06*math.sin(f*2.1)          # pulsing thickness
        cx = (mx+tip)/2.0; hx = (tip-mx)/2.0
        # outer red glow beam
        rib.append(box(cx,my,mz, hx, thick*1.9, thick*1.9, [0.95,0.12,0.10], surf="constant"))
        # white-hot core
        rib.append(box(cx,my,mz, hx, thick*0.7, thick*0.7, [1.0,0.95,0.85], surf="constant"))
        # muzzle flash
        rib.append(ball(mx,my,mz, 0.30+0.06*math.sin(f*3.0), [1.0,0.6,0.2], surf="constant"))
        # travelling energy bolt along the beam
        bx = mx + (tip-mx)*((f*0.17) % 1.0)
        rib.append(ball(bx,my,mz, 0.15, [1.0,1.0,0.9], surf="constant"))

    # target block until it's hit, then a bright expanding burst
    if impact <= 0.0:
        rib.append(box(tgt_cx,1.6,0.0, 0.45,0.95,0.5, [0.80,0.22,0.18]))
    else:
        n = 12
        for k in range(n):
            a = k*(2*math.pi/n) + 0.3
            d = 0.4 + impact*2.6
            sx = tgt_cx + math.cos(a)*d
            sy = 1.6 + math.sin(a)*d*0.85
            r  = max(0.06, 0.30*(1.0-impact*0.6))
            rib.append(ball(sx,sy,0.0, r, [1.0, 0.85-0.5*impact, 0.25], surf="constant"))
        # big flash at the moment of impact, fading out
        if impact < 0.7:
            rib.append(ball(tgt_cx,1.6,0.0, 1.1*(1-impact), [1.0,0.92,0.7], surf="constant"))

    rib.append('WorldEnd')
    return "\n".join(rib) + "\n"

for f in range(NF):
    open(os.path.join(OUT, f"frame{f:02d}.rib"), "w").write(frame(f))
print(f"wrote {NF} robot-laser frames -> {OUT}/frameNN.rib  ({W}x{H})")
