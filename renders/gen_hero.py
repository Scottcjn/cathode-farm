#!/usr/bin/env python3
"""'Sunbeam Shelf' — composed Toy Story-style hero scene for BMRT.
Orientation (matches the working scenes): NEGATIVE z = toward camera (front),
POSITIVE z = back, wall far at z=+12. Warm window key, ray-traced soft shadows."""
import os
OUT=os.path.expanduser("~/mac-farm/toyscenes"); os.makedirs(OUT,exist_ok=True)
W,H=960,720

def ball(x,y,z,r,c,ks=0.9,rough=0.05):
    R,G,B=c
    return (f'AttributeBegin\nSurface "plastic" "Ka" [1] "Kd" [0.72] "Ks" [{ks}] "roughness" [{rough}]\n'
            f'Color [{R} {G} {B}]\nTranslate {x} {y} {z}\nSphere {r} {-r} {r} 360\nAttributeEnd\n')

def block(x,y,z,s,c,rot):
    R,G,B=c; h=s/2
    faces=[[-h,-h,h,h,-h,h,h,h,h,-h,h,h],[-h,-h,-h,-h,h,-h,h,h,-h,h,-h,-h],
     [-h,-h,-h,-h,-h,h,-h,h,h,-h,h,-h],[h,-h,-h,h,h,-h,h,h,h,h,-h,h],
     [-h,h,-h,-h,h,h,h,h,h,h,h,-h],[-h,-h,-h,h,-h,-h,h,-h,h,-h,-h,h]]
    o=f'AttributeBegin\nSurface "plastic" "Ks" [0.45] "roughness" [0.09]\nColor [{R} {G} {B}]\nTranslate {x} {y} {z}\nRotate {rot} 0 1 0\n'
    for f in faces: o+='Polygon "P" ['+' '.join(str(v) for v in f)+']\n'
    return o+'AttributeEnd\n'

s=f'''Display "toy_hero.tif" "file" "rgba"
Format {W} {H} 1
PixelSamples 5 5
ShadingRate 0.8
PixelFilter "gaussian" 2.2 2.2
Projection "perspective" "fov" [44]
Translate 0 -2.3 9
Rotate 8 1 0 0
WorldBegin
Attribute "light" "shadows" "on"
LightSource "ambientlight" 1 "intensity" [0.17] "lightcolor" [0.80 0.84 1.0]
LightSource "distantlight" 2 "intensity" [1.35] "lightcolor" [1.0 0.90 0.68]
  "from" [-5 6 -4] "to" [0 1 2]
LightSource "distantlight" 3 "intensity" [0.32] "lightcolor" [0.65 0.78 1.0]
  "from" [5 4 -3] "to" [0 1 2]
# wood floor
AttributeBegin
  Surface "plastic" "Ka" [1] "Kd" [0.85] "Ks" [0.22] "roughness" [0.14]
  Color [0.64 0.44 0.26]
  Polygon "P" [-30 0 -6  30 0 -6  30 0 30  -30 0 30]
AttributeEnd
# back wall, warm
AttributeBegin
  Surface "matte" Color [0.88 0.82 0.68]
  Polygon "P" [-30 0 12  30 0 12  30 22 12  -30 22 12]
AttributeEnd
# sunlit window on the wall
AttributeBegin
  Surface "constant" Color [1.0 0.97 0.86]
  Polygon "P" [-8.6 4.5 11.9  -3.4 4.5 11.9  -3.4 10.5 11.9  -8.6 10.5 11.9]
AttributeEnd
AttributeBegin
  Surface "matte" Color [0.5 0.36 0.25]
  Polygon "P" [-6.1 4.5 11.85  -5.9 4.5 11.85  -5.9 10.5 11.85  -6.1 10.5 11.85]
  Polygon "P" [-8.6 7.4 11.85  -3.4 7.4 11.85  -3.4 7.6 11.85  -8.6 7.6 11.85]
AttributeEnd
'''
# block tower — back-left (positive z)
cols=[[0.88,0.20,0.18],[0.13,0.40,0.85],[0.98,0.78,0.12],[0.16,0.62,0.34]]
s+=block(-3.1,0.75,4.0,1.5,cols[0],10)
s+=block(-1.6,0.75,4.0,1.5,cols[2],-6)
s+=block(-2.35,2.25,4.0,1.5,cols[1],14)
# spinning top — back-right
s+='''AttributeBegin
Surface "plastic" "Ks" [0.9] "roughness" [0.04]
Color [0.85 0.12 0.5]
Translate 3.4 0 3.0
Rotate -90 1 0 0
Cone 1.7 1.0 360
Translate 0 0 1.7
Sphere 0.2 -0.2 0.2 360
AttributeEnd
'''
# peg toy — mid, standing
s+='''AttributeBegin
Surface "plastic" "Ks" [0.55] "roughness" [0.09]
Color [0.90 0.30 0.15]
Translate 0.4 0 1.4
Rotate -90 1 0 0
Cylinder 0.85 0 1.7 360
Disk 1.7 0.85 360
AttributeEnd
'''
s+=ball(0.4,2.35,1.4,0.72,[0.98,0.86,0.72],ks=0.3,rough=0.3)   # head
s+=ball(0.10,2.5,0.72,0.10,[0.08,0.08,0.10],ks=0.2)            # eye L (front = -z from head)
s+=ball(0.70,2.5,0.72,0.10,[0.08,0.08,0.10],ks=0.2)            # eye R
s+=ball(0.40,2.22,0.68,0.09,[0.86,0.36,0.34],ks=0.2)           # nose
s+='''AttributeBegin
Surface "plastic" "Ks" [0.5] "roughness" [0.1]
Color [0.15 0.42 0.85]
Translate 0.4 2.9 1.4
Rotate -90 1 0 0
Cone 0.85 0.7 360
AttributeEnd
'''
s+=ball(-0.7,1.35,1.4,0.34,[0.90,0.30,0.15])   # arm L
s+=ball(1.5,1.35,1.4,0.34,[0.90,0.30,0.15])    # arm R
# bouncing balls — foreground, smaller + spread so the cast shows behind
s+=ball(-3.5,0.75,-0.8,0.75,[0.90,0.15,0.12])    # red, far left
s+=ball(-1.7,0.90,-1.8,0.90,[0.98,0.80,0.10])    # yellow hero, front-center-left
s+=ball(3.6,0.70,-0.6,0.70,[0.10,0.35,0.85])     # blue, far right
s+=ball(2.2,0.50,-2.2,0.50,[0.16,0.66,0.32])     # green, small front
s+='WorldEnd\n'
open(os.path.join(OUT,"toy_hero.rib"),"w").write(s)
print("wrote toy_hero.rib", f"{W}x{H}")
