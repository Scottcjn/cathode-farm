#!/usr/bin/env python3
"""'The Bounce' — a Luxo-style bouncing-ball animation for BMRT.
The yellow hero ball bounces across a warm toy room with squash-and-stretch and a
real ray-traced shadow. Emits one RIB per frame. Orientation: -z = toward camera."""
import os, sys, math
OUT=os.path.expanduser("~/mac-farm/toyscenes/bounce_frames"); os.makedirs(OUT,exist_ok=True)
NF=int(sys.argv[1]) if len(sys.argv)>1 else 54
W,H=640,480

def block(x,y,z,s,c,rot):
    R,G,B=c; h=s/2
    faces=[[-h,-h,h,h,-h,h,h,h,h,-h,h,h],[-h,-h,-h,-h,h,-h,h,h,-h,h,-h,-h],
     [-h,-h,-h,-h,-h,h,-h,h,h,-h,h,-h],[h,-h,-h,h,h,-h,h,h,h,h,-h,h],
     [-h,h,-h,-h,h,h,h,h,h,h,h,-h],[-h,-h,-h,h,-h,-h,h,-h,h,-h,-h,h]]
    o=f'AttributeBegin\nSurface "plastic" "Ks" [0.45] "roughness" [0.09]\nColor [{R} {G} {B}]\nTranslate {x} {y} {z}\nRotate {rot} 0 1 0\n'
    for f in faces: o+='Polygon "P" ['+' '.join(str(v) for v in f)+']\n'
    return o+'AttributeEnd\n'

# static warm toy-room backdrop
def backdrop():
    s='''Attribute "light" "shadows" "on"
LightSource "ambientlight" 1 "intensity" [0.17] "lightcolor" [0.80 0.84 1.0]
LightSource "distantlight" 2 "intensity" [1.35] "lightcolor" [1.0 0.90 0.68] "from" [-5 6 -4] "to" [0 1 2]
LightSource "distantlight" 3 "intensity" [0.32] "lightcolor" [0.65 0.78 1.0] "from" [5 4 -3] "to" [0 1 2]
AttributeBegin
Surface "plastic" "Kd" [0.85] "Ks" [0.22] "roughness" [0.14]
Color [0.64 0.44 0.26]
Polygon "P" [-30 0 -6  30 0 -6  30 0 30  -30 0 30]
AttributeEnd
AttributeBegin
Surface "matte" Color [0.88 0.82 0.68]
Polygon "P" [-30 0 12  30 0 12  30 22 12  -30 22 12]
AttributeEnd
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
    cols=[[0.88,0.20,0.18],[0.13,0.40,0.85],[0.98,0.78,0.12]]
    s+=block(-4.2,0.75,4.0,1.5,cols[0],10)
    s+=block(-2.7,0.75,4.0,1.5,cols[2],-6)
    s+=block(-3.45,2.25,4.0,1.5,cols[1],14)
    # blue static ball parked right
    s+='AttributeBegin\nSurface "plastic" "Ks" [0.9] "roughness" [0.05]\nColor [0.10 0.35 0.85]\nTranslate 4.0 0.8 2.0\nSphere 0.8 -0.8 0.8 360\nAttributeEnd\n'
    return s

R0=0.9                    # ball rest radius
x0,x1=-4.5,4.5            # travel range
bounces=3
for f in range(NF):
    t=f/(NF-1)                       # 0..1
    x=x0+(x1-x0)*t
    # bounce height: |sin| with decay, arches get lower
    phase=t*bounces*math.pi
    decay=1.0-0.22*(t*bounces)       # energy loss per arch
    hgt=abs(math.sin(phase))*max(2.6*decay,0.3)
    y=R0+hgt
    # squash/stretch: near floor -> squash; near apex -> stretch
    contact=1.0-min(hgt/0.9,1.0)     # 1 at floor, 0 up high
    sq=1.0+0.30*contact              # horizontal widen at floor
    st=1.0-0.22*contact              # vertical flatten at floor
    # slight stretch in fast rise/fall
    rib=[f'Display "b_{f:04d}.tif" "file" "rgba"',f'Format {W} {H} 1',
         'PixelSamples 3 3','ShadingRate 1.2','PixelFilter "gaussian" 2 2',
         'Projection "perspective" "fov" [46]',
         'Translate 0 -2.2 9','Rotate 8 1 0 0','WorldBegin', backdrop(),
         # the bouncing hero ball
         'AttributeBegin',
         'Surface "plastic" "Ka" [1] "Kd" [0.72] "Ks" [0.9] "roughness" [0.05]',
         'Color [0.98 0.80 0.10]',
         f'Translate {x:.3f} {y:.3f} 0',
         f'Scale {sq:.3f} {st:.3f} {sq:.3f}',
         f'Sphere {R0} {-R0} {R0} 360',
         'AttributeEnd','WorldEnd']
    open(os.path.join(OUT,f"b_{f:04d}.rib"),"w").write("\n".join(rib)+"\n")
print(f"wrote {NF} bounce frames -> {OUT}")
