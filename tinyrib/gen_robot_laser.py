#!/usr/bin/env python3
"""'Robot Shooting a Laser' - a higher-quality animation for TinyRIB (our RenderMan
renderer on the emulated 1994 Mac). Anti-aliased (PixelSamples), higher resolution,
cinematic camera push-in, eased motion with recoil, a detailed robot, a layered glowing
laser, and a shockwave impact. Emits frameNN.rib using only what TinyRIB supports:
spheres, polygon boxes, matte/plastic/constant surfaces, distant lights, a RIB camera.
Usage: gen_robot_laser.py [NFRAMES] [WIDTH] [HEIGHT] [SAMPLES]   (c) Elyan Labs, GPL-2.0."""
import os, sys, math
OUT  = os.environ.get("TINYRIB_OUT") or os.path.expanduser("~/mac-farm/tinyrib")
os.makedirs(OUT, exist_ok=True)
NF   = int(sys.argv[1]) if len(sys.argv) > 1 else 24
W    = int(sys.argv[2]) if len(sys.argv) > 2 else 256
H    = int(sys.argv[3]) if len(sys.argv) > 3 else 192
SAMP = int(sys.argv[4]) if len(sys.argv) > 4 else 2

def ease(t):  # smoothstep in/out
    return t*t*(3-2*t)

def box(cx,cy,cz, hx,hy,hz, col, surf="plastic", ks=0.5, rough=0.12):
    R,G,B = col
    s  = f'AttributeBegin\nSurface "{surf}" "Ks" [{ks}] "roughness" [{rough}]\nColor [{R} {G} {B}]\n'
    X0,X1=cx-hx,cx+hx; Y0,Y1=cy-hy,cy+hy; Z0,Z1=cz-hz,cz+hz
    for f in ([X0,Y0,Z1,X1,Y0,Z1,X1,Y1,Z1,X0,Y1,Z1],[X1,Y0,Z0,X0,Y0,Z0,X0,Y1,Z0,X1,Y1,Z0],
              [X0,Y0,Z0,X0,Y0,Z1,X0,Y1,Z1,X0,Y1,Z0],[X1,Y0,Z1,X1,Y0,Z0,X1,Y1,Z0,X1,Y1,Z1],
              [X0,Y1,Z1,X1,Y1,Z1,X1,Y1,Z0,X0,Y1,Z0],[X0,Y0,Z0,X1,Y0,Z0,X1,Y0,Z1,X0,Y0,Z1]):
        s += 'Polygon "P" [' + ' '.join(f'{v:.3f}' for v in f) + ']\n'
    return s + 'AttributeEnd\n'

def ball(x,y,z,r, col, surf="plastic", ks=0.6, rough=0.08):
    R,G,B=col
    return (f'AttributeBegin\nSurface "{surf}" "Ks" [{ks}] "roughness" [{rough}]\n'
            f'Color [{R} {G} {B}]\nTranslate {x} {y} {z}\nSphere {r} {-r} {r} 360\nAttributeEnd\n')

STEEL=[0.44,0.49,0.58]; STEELD=[0.28,0.32,0.40]; CANNON=[0.58,0.61,0.68]; TRIM=[0.16,0.18,0.24]
def robot(recoil, look):
    # recoil shifts the whole robot back a touch; look nudges the head/eyes
    rx=-2.5-recoil*0.35
    s  = box(rx-0.42,0.55,0.05, 0.26,0.55,0.30, STEELD)          # leg L
    s += box(rx+0.42,0.55,-0.05,0.26,0.55,0.30, STEELD)          # leg R
    s += box(rx-0.42,0.13,0.18, 0.30,0.12,0.42, TRIM)            # foot L
    s += box(rx+0.42,0.13,0.18, 0.30,0.12,0.42, TRIM)            # foot R
    s += box(rx,1.75,0.0, 0.85,0.78,0.55, STEEL)                 # torso
    s += box(rx,1.75,-0.57, 0.55,0.5,0.04, TRIM)                 # chest plate (-z = camera side)
    s += ball(rx,1.82,-0.63, 0.15, [0.15,0.95,1.0], surf="constant")  # chest core (glow)
    s += box(rx-0.9,1.75,0.0, 0.12,0.55,0.4, STEELD)             # shoulder L
    s += box(rx+0.9,1.9,0.0,  0.12,0.28,0.4, STEELD)             # shoulder R (cannon)
    # head + visor
    s += box(rx,2.82,0.0, 0.52,0.44,0.5, STEEL)
    s += box(rx+look*0.05,2.86,-0.53, 0.42,0.16,0.03, TRIM)      # visor slot
    s += ball(rx-0.22+look*0.05,2.9,-0.58, 0.10,[0.2,1.0,1.0], surf="constant") # eye L
    s += ball(rx+0.22+look*0.05,2.9,-0.58, 0.10,[0.2,1.0,1.0], surf="constant") # eye R
    s += box(rx,3.42,0.0, 0.05,0.2,0.05, STEELD)                 # antenna
    s += ball(rx,3.66,0.0, 0.10,[1.0,0.3,0.2], surf="constant")  # antenna tip
    s += box(rx-0.95,1.3,0.0, 0.19,0.6,0.21, STEELD)             # left arm hanging
    s += ball(rx-0.95,0.72,0.0, 0.2,STEELD)                      # left fist
    # right arm = cannon (moves back with recoil)
    ax=rx+0.55-recoil*0.28
    s += box(ax,1.9,0.0, 0.55,0.22,0.22, CANNON)                 # upper cannon arm
    s += box(ax+0.85,1.9,0.0, 0.36,0.32,0.32, CANNON)            # cannon housing
    s += box(ax+0.85,1.9,0.0, 0.30,0.36,0.13, TRIM)             # housing band
    s += ball(ax+1.25,1.9,0.0, 0.21, STEELD, ks=0.75)           # muzzle ring
    return s, (ax+1.45, 1.9, 0.0)   # muzzle tip

TARGET_X = 5.0
def frame(f):
    t = f/(NF-1)
    charge = ease(max(0.0, min(1.0, t/0.30)))
    firing = 0.30 < t < 0.88
    firet  = ease(max(0.0, min(1.0,(t-0.30)/0.30)))   # beam reaches target
    impact = max(0.0, (t-0.56)/0.44)                  # 0..1 burst
    recoil = 0.0
    if firing:
        rp=(t-0.30)/0.58
        recoil = math.exp(-rp*7.0)*math.sin(rp*22)*0.5 + max(0,0.5-rp)*0.5   # sharp kick, settle
    look = math.sin(t*6.28)*0.3

    # cinematic slow push-in + slight rise
    dolly = 12.2 - ease(t)*2.2
    rise  = -2.35 - ease(t)*0.25
    tilt  = 5.0 + ease(t)*1.5

    rob, mz = robot(recoil, look)
    mx,my,mzz = mz
    rib = [f'Display "frame{f:02d}.tif" "file" "rgba"', f'Format {W} {H} 1',
           f'PixelSamples {SAMP} {SAMP}', 'Projection "perspective" "fov" [48]',
           f'Translate 0 {rise:.3f} {dolly:.3f}', f'Rotate {tilt:.3f} 1 0 0', 'WorldBegin',
           'LightSource "ambientlight" 1 "intensity" [0.20] "lightcolor" [0.62 0.68 0.92]',
           'LightSource "distantlight" 2 "intensity" [1.25] "lightcolor" [1.0 0.93 0.80] "from" [-6 7 -5] "to" [-2 1 0]',
           'LightSource "distantlight" 3 "intensity" [0.45] "lightcolor" [0.45 0.6 1.0] "from" [7 3 -4] "to" [0 1 0]',
           'LightSource "distantlight" 4 "intensity" [0.35] "lightcolor" [1.0 0.5 0.4] "from" [8 2 6] "to" [-1 1 0]']
    rib.append('AttributeBegin\nSurface "plastic" "Ks" [0.28] "roughness" [0.22]\n'
               'Color [0.19 0.21 0.27]\nPolygon "P" [-40 0 -8  40 0 -8  40 0 30  -40 0 30]\nAttributeEnd')
    rib.append('AttributeBegin\nSurface "matte"\nColor [0.12 0.14 0.22]\n'
               'Polygon "P" [-40 0 14  40 0 14  40 26 14  -40 26 14]\nAttributeEnd')
    rib.append(rob)

    # muzzle charge/idle glow (while firing the flash ball below replaces it -
    # they share a centre, so drawing both only buries the smaller one)
    if not firing:
        rib.append(ball(mx,my,mzz, 0.10 + 0.32*charge, [1.0,0.85,0.35], surf="constant"))

    if firing:
        tip = mx + (TARGET_X-mx)*firet
        thick = 0.16 + 0.05*math.sin(f*2.2)
        cx=(mx+tip)/2.0; hx=(tip-mx)/2.0
        z_out = mzz                                      # -z is toward the camera, so
        z_mid = z_out - (thick*2.4 + thick*1.5)          # each layer sits in front of
        z_core= z_mid - (thick*1.5 + thick*0.6)          # the wider one behind it
        rib.append(box(cx,my,z_out,  hx, thick*2.4, thick*2.4, [0.75,0.10,0.08], surf="constant"))  # soft outer
        rib.append(box(cx,my,z_mid,  hx, thick*1.5, thick*1.5, [0.98,0.16,0.12], surf="constant"))  # red
        rib.append(box(cx,my,z_core, hx, thick*0.6, thick*0.6, [1.0,0.96,0.88], surf="constant"))   # core
        rib.append(ball(mx,my,mzz, 0.32+0.07*math.sin(f*3.0), [1.0,0.6,0.2], surf="constant"))   # flash
        for k in range(2):
            bx = mx + (tip-mx)*(((f*0.17)+k*0.5) % 1.0)
            rib.append(ball(bx,my,z_core-(thick*0.6+0.13), 0.13, [1.0,1.0,0.92], surf="constant"))  # pulses

    tgt_cx = TARGET_X+0.6
    if impact <= 0.0:
        rib.append(box(tgt_cx,1.55,0.0, 0.45,0.95,0.5, [0.78,0.22,0.18]))
        rib.append(box(tgt_cx,1.55,-0.52, 0.3,0.6,0.03, [0.9,0.3,0.25]))
    else:
        n = 16
        for k in range(n):
            a = k*(2*math.pi/n) + 0.3
            d = 0.4 + impact*3.0
            sx = tgt_cx + math.cos(a)*d
            sy = 1.55 + math.sin(a)*d*0.85
            r  = max(0.05, 0.30*(1.0-impact*0.55))
            rib.append(ball(sx,sy,0.0, r, [1.0, 0.8-0.5*impact, 0.2], surf="constant"))
        # shockwave ring (thin flat boxes) + core flash
        if impact < 0.8:
            ir = 0.3 + impact*3.5; tw = 0.12
            for (ex,ey) in [(ir,0),(-ir,0),(0,ir*0.8),(0,-ir*0.8)]:
                rib.append(ball(tgt_cx+ex,1.55+ey,0.0, 0.14*(1-impact*0.7), [1.0,0.95,0.8], surf="constant"))
        if impact < 0.6:
            rib.append(ball(tgt_cx,1.55,0.0, 1.2*(1-impact), [1.0,0.93,0.72], surf="constant"))

    rib.append('WorldEnd')
    return "\n".join(rib) + "\n"

for f in range(NF):
    open(os.path.join(OUT, f"frame{f:02d}.rib"), "w").write(frame(f))
print(f"wrote {NF} HQ frames -> {OUT}/frameNN.rib  ({W}x{H}, {SAMP}x{SAMP} AA)")
