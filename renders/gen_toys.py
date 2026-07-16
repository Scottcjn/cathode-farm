#!/usr/bin/env python3
"""Original 'Toy Story'-flavored RenderMan scenes for BMRT.
Warm window light, wood floor, plastic toys, ray-traced soft shadows."""
import os, math
OUT = os.path.expanduser("~/mac-farm/toyscenes")
os.makedirs(OUT, exist_ok=True)
W, H = 640, 480

HEAD = lambda name: f'''Display "{name}.tif" "file" "rgba"
Format {W} {H} 1
PixelSamples 4 4
ShadingRate 1.0
PixelFilter "gaussian" 2 2
Projection "perspective" "fov" [40]
'''

# warm three-point lighting + a wood floor, shared across scenes
def world_open():
    return '''WorldBegin
Attribute "light" "shadows" "on"
LightSource "ambientlight" 1 "intensity" [0.18] "lightcolor" [0.85 0.85 1.0]
LightSource "distantlight" 2 "intensity" [1.15] "lightcolor" [1.0 0.93 0.78]
  "from" [4 6 -3] "to" [0 0 0]
LightSource "distantlight" 3 "intensity" [0.35] "lightcolor" [0.7 0.8 1.0]
  "from" [-5 3 2] "to" [0 0 0]
# wood floor
AttributeBegin
  Surface "plastic" "Ka" [1] "Kd" [0.85] "Ks" [0.25] "roughness" [0.12]
  Color [0.62 0.42 0.24]
  Polygon "P" [-20 0 -20  20 0 -20  20 0 20  -20 0 20]
AttributeEnd
# back wall (warm)
AttributeBegin
  Surface "matte"
  Color [0.86 0.80 0.66]
  Polygon "P" [-20 0 12  20 0 12  20 20 12  -20 20 12]
AttributeEnd
'''

def ball(x,y,z,r,col,ks=0.9,rough=0.05):
    R,G,B=col
    return f'''AttributeBegin
Surface "plastic" "Ka" [1] "Kd" [0.7] "Ks" [{ks}] "roughness" [{rough}]
Color [{R} {G} {B}]
Translate {x} {y} {z}
Sphere {r} {-r} {r} 360
AttributeEnd
'''

def block(x,y,z,s,col,rot=0):
    R,G,B=col; h=s/2
    faces=[
     [-h,-h,h, h,-h,h, h,h,h, -h,h,h],[-h,-h,-h,-h,h,-h,h,h,-h,h,-h,-h],
     [-h,-h,-h,-h,-h,h,-h,h,h,-h,h,-h],[h,-h,-h,h,h,-h,h,h,h,h,-h,h],
     [-h,h,-h,-h,h,h,h,h,h,h,h,-h],[-h,-h,-h,h,-h,-h,h,-h,h,-h,-h,h]]
    s_=f'AttributeBegin\nSurface "plastic" "Ks" [0.4] "roughness" [0.1]\nColor [{R} {G} {B}]\nTranslate {x} {y} {z}\nRotate {rot} 0 1 0\n'
    for f in faces: s_+=f'Polygon "P" [{" ".join(str(v) for v in f)}]\n'
    return s_+'AttributeEnd\n'

def cyl(x,y,z,r,h,col,ks=0.6):
    R,G,B=col
    return f'''AttributeBegin
Surface "plastic" "Ks" [{ks}] "roughness" [0.08]
Color [{R} {G} {B}]
Translate {x} {y} {z}
Rotate -90 1 0 0
Cylinder {r} 0 {h} 360
Disk {h} {r} 360
AttributeEnd
'''

def cam(dist, height, tilt):
    return f'Translate 0 {-height} {dist}\nRotate {tilt} 1 0 0\n'

# ---- Scene 1: the bouncing balls (Pixar-icon vibe) ----
def scene_balls():
    s=HEAD("toy_balls")+cam(9,2.2,8)+world_open()
    s+=ball(-2.4,1.0,0, 1.0, [0.90,0.15,0.12])      # red
    s+=ball( 0.0,1.3,-1.2,1.3,[0.98,0.80,0.10])      # yellow (hero, bigger)
    s+=ball( 2.3,0.85,0.3,0.85,[0.10,0.35,0.85])     # blue
    s+=ball( 0.9,0.6,1.6, 0.6,[0.15,0.65,0.30])      # green, front
    s+=ball(-1.3,0.55,1.9,0.55,[0.95,0.45,0.75])     # pink
    s+='WorldEnd\n'
    return s

# ---- Scene 2: alphabet blocks + a top ----
def scene_blocks():
    s=HEAD("toy_blocks")+cam(8,2.4,10)+world_open()
    cols=[[0.88,0.2,0.18],[0.15,0.4,0.85],[0.98,0.78,0.12],[0.2,0.65,0.35]]
    # bottom row of 3, then 2, then 1 (pyramid)
    xs=[-2,0,2];
    for i,x in enumerate(xs): s+=block(x,0.75,0,1.5,cols[i%4],rot=i*8)
    for i,x in enumerate([-1,1]): s+=block(x,2.25,0,1.5,cols[(i+2)%4],rot=15)
    s+=block(0,3.75,0,1.5,cols[1],rot=-10)
    # a spinning top beside them
    s+=cyl(3.0,0,1.8,0.0,0.0,[0,0,0])  # placeholder no-op removed below
    s+='''AttributeBegin
Surface "plastic" "Ks" [0.9] "roughness" [0.04]
Color [0.85 0.1 0.5]
Translate 3.2 0.0 2.2
Rotate -90 1 0 0
Cone 1.4 0.9 360
Translate 0 0 1.4
Sphere 0.18 -0.18 0.18 360
AttributeEnd
'''
    s+='WorldEnd\n'
    return s

# ---- Scene 3: a little peg toy figure ----
def scene_figure():
    s=HEAD("toy_figure")+cam(7,2.3,9)+world_open()
    # body (cylinder), head (sphere), arms (spheres on stalks), hat (cone)
    s+=cyl(0,0,0,0.9,1.8,[0.90,0.30,0.15])           # red body
    s+=ball(0,2.5,0,0.75,[0.98,0.86,0.72],ks=0.3,rough=0.3) # head (skin)
    s+=ball(-0.35,2.65,0.6,0.10,[0.1,0.1,0.12],ks=0.2) # eye L
    s+=ball( 0.35,2.65,0.6,0.10,[0.1,0.1,0.12],ks=0.2) # eye R
    s+=ball(0,2.35,0.72,0.09,[0.85,0.35,0.35],ks=0.2)  # nose
    s+=ball(-1.05,1.4,0,0.35,[0.90,0.30,0.15])         # arm L
    s+=ball( 1.05,1.4,0,0.35,[0.90,0.30,0.15])         # arm R
    # blue hat
    s+='''AttributeBegin
Surface "plastic" "Ks" [0.5] "roughness" [0.1]
Color [0.15 0.4 0.85]
Translate 0 3.05 0
Rotate -90 1 0 0
Cone 0.9 0.7 360
AttributeEnd
'''
    s+='WorldEnd\n'
    return s

scenes={"toy_balls":scene_balls,"toy_blocks":scene_blocks,"toy_figure":scene_figure}
for name,fn in scenes.items():
    open(os.path.join(OUT,name+".rib"),"w").write(fn())
print("wrote:", ", ".join(scenes.keys()))
