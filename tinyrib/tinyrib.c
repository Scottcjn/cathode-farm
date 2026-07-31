/* TinyRIB - a tiny RenderMan-compliant raytracer for the 68K Macintosh.
 * Reads a subset of RIB, ray-traces spheres + polygons with matte/plastic
 * shading and ray-traced shadows, draws to a Mac window as it goes.
 * Built with Retro68 (m68k-apple-macos-gcc).  (c) Elyan Labs, GPL-2.0.
 */
#ifndef HOST_PREVIEW          /* HOST_PREVIEW: same renderer, compiled on Linux for fast iteration */
#include <Quickdraw.h>
#include <Windows.h>
#include <Fonts.h>
#include <Events.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ---- 3D math ---- */
typedef struct { double x,y,z; } V3;
static V3 v(double x,double y,double z){V3 r;r.x=x;r.y=y;r.z=z;return r;}
static V3 add(V3 a,V3 b){return v(a.x+b.x,a.y+b.y,a.z+b.z);}
static V3 sub(V3 a,V3 b){return v(a.x-b.x,a.y-b.y,a.z-b.z);}
static V3 scl(V3 a,double s){return v(a.x*s,a.y*s,a.z*s);}
static double dot(V3 a,V3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
static double len(V3 a){return sqrt(dot(a,a));}
static V3 norm(V3 a){double l=len(a);return l>1e-9?scl(a,1.0/l):a;}

typedef double M4[16];
static void m_ident(M4 m){int i;for(i=0;i<16;i++)m[i]=0;m[0]=m[5]=m[10]=m[15]=1;}
static void m_mul(M4 r,M4 a,M4 b){M4 t;int i,j,k;for(i=0;i<4;i++)for(j=0;j<4;j++){double s=0;for(k=0;k<4;k++)s+=a[i*4+k]*b[k*4+j];t[i*4+j]=s;}memcpy(r,t,sizeof(t));}
static V3 m_pt(M4 m,V3 p){return v(m[0]*p.x+m[1]*p.y+m[2]*p.z+m[3],
                                   m[4]*p.x+m[5]*p.y+m[6]*p.z+m[7],
                                   m[8]*p.x+m[9]*p.y+m[10]*p.z+m[11]);}
static V3 m_dir(M4 m,V3 p){return v(m[0]*p.x+m[1]*p.y+m[2]*p.z,
                                    m[4]*p.x+m[5]*p.y+m[6]*p.z,
                                    m[8]*p.x+m[9]*p.y+m[10]*p.z);}
static void m_trans(M4 m,double x,double y,double z){M4 t;m_ident(t);t[3]=x;t[7]=y;t[11]=z;m_mul(m,m,t);}
static void m_rot(M4 m,double deg,double ax,double ay,double az){
    double a=deg*3.14159265358979/180.0,c=cos(a),s=sin(a);
    V3 u=norm(v(ax,ay,az));double x=u.x,y=u.y,z=u.z;M4 t;m_ident(t);
    t[0]=c+x*x*(1-c); t[1]=x*y*(1-c)-z*s; t[2]=x*z*(1-c)+y*s;
    t[4]=y*x*(1-c)+z*s; t[5]=c+y*y*(1-c); t[6]=y*z*(1-c)-x*s;
    t[8]=z*x*(1-c)-y*s; t[9]=z*y*(1-c)+x*s; t[10]=c+z*z*(1-c);
    m_mul(m,m,t);
}

/* ---- scene ---- */
typedef struct { V3 col; double Ka,Kd,Ks,rough; int constant; } Mat; /* constant=unlit/emissive */
typedef struct { int type; V3 a,b,c,d; double r; Mat m; V3 bc; double br;
                 V3 qn; short nv; short ax0,ax1; } Prim;
/* 0=sphere,1=planar polygon (nv=3 triangle a,b,c / nv=4 quad a,b,c,d).
   bc/br=bounding sphere (culling); qn=face normal; ax0/ax1=the two axes the face
   projects onto without degenerating (dominant normal component dropped), so the
   inside test is a plain 2D edge-sign test - exact for any shape, not just
   axis-aligned rectangles, and it needs no per-ray divide. All precomputed once. */
typedef struct { int type; V3 p; V3 col; double inten; } Light;  /* 0=ambient,1=distant(p=dir),2=point(p=pos) */

#define MAXP 512
#define MAXL 8
static Prim prims[MAXP]; static int nprim=0;
static Light lights[MAXL]; static int nlight=0;
static int RESX=320,RESY=240; static double FOV=45;
static int SS=1;      /* supersamples per axis (anti-aliasing); from RIB PixelSamples */
static int keyLight=-1; /* only the brightest light casts shadows (fills don't) - faster + standard */
static M4 cam2world;  /* inverse of the pre-world transform */

/* ---- ray/prim intersection ---- */
static int hit_sphere(V3 ro,V3 rd,V3 c,double r,double *t){
    V3 oc=sub(ro,c);double b=dot(oc,rd),cc=dot(oc,oc)-r*r,d=b*b-cc;
    if(d<0)return 0;double s=sqrt(d),t0=-b-s;if(t0<1e-4)t0=-b+s;if(t0<1e-4)return 0;*t=t0;return 1;}
/* quick reject: does the ray's forward half-line miss this bounding sphere? */
static int miss_bound(V3 ro,V3 rd,V3 c,double r){
    V3 oc=sub(c,ro);double tca=dot(oc,rd);if(tca<-r)return 1;
    double d2=dot(oc,oc)-tca*tca;return d2>r*r;}
/* polygon test: ray/plane, then a 2D edge-sign test in the face's dominant plane.
   Correct for triangles and for quads of any shape (the old normalized-edge test
   only agreed with the truth when the two edges happened to be perpendicular). */
static double comp(V3 p,int i){return i==0?p.x:(i==1?p.y:p.z);}
static int in_tri2(double px,double py,double ax,double ay,
                   double bx,double by,double cx,double cy){
    double d1=(px-bx)*(ay-by)-(ax-bx)*(py-by);
    double d2=(px-cx)*(by-cy)-(bx-cx)*(py-cy);
    double d3=(px-ax)*(cy-ay)-(cx-ax)*(py-ay);
    int neg=(d1<0)||(d2<0)||(d3<0), pos=(d1>0)||(d2>0)||(d3>0);
    return !(neg&&pos);   /* all edge signs agree => inside (or on an edge) */
}
static int hit_poly(V3 ro,V3 rd,Prim*p,double *t){
    double den=dot(p->qn,rd);if(fabs(den)<1e-6)return 0;
    double tt=dot(sub(p->a,ro),p->qn)/den;if(tt<1e-4)return 0;
    { V3 h=add(ro,scl(rd,tt));
      double hx=comp(h,p->ax0),hy=comp(h,p->ax1);
      double ax=comp(p->a,p->ax0),ay=comp(p->a,p->ax1);
      double bx=comp(p->b,p->ax0),by=comp(p->b,p->ax1);
      double cx=comp(p->c,p->ax0),cy=comp(p->c,p->ax1);
      if(in_tri2(hx,hy,ax,ay,bx,by,cx,cy)){*t=tt;return 1;}
      if(p->nv==4){ double dx=comp(p->d,p->ax0),dy=comp(p->d,p->ax1);
          if(in_tri2(hx,hy,ax,ay,cx,cy,dx,dy)){*t=tt;return 1;} }
    }
    return 0;}

static int trace(V3 ro,V3 rd,double *t,V3 *n,Mat *m){
    int i,best=-1;double bt=1e30,tt;
    for(i=0;i<nprim;i++){
        if(prims[i].type==0){ if(hit_sphere(ro,rd,prims[i].a,prims[i].r,&tt)&&tt<bt){bt=tt;best=i;} }
        else { if(!miss_bound(ro,rd,prims[i].bc,prims[i].br)&&hit_poly(ro,rd,&prims[i],&tt)&&tt<bt){bt=tt;best=i;} }
    }
    if(best<0)return 0;*t=bt;V3 h=add(ro,scl(rd,bt));
    if(prims[best].type==0)*n=norm(sub(h,prims[best].a));
    else { *n=prims[best].qn; if(dot(*n,rd)>0)*n=scl(*n,-1); }
    *m=prims[best].m;return 1;
}
static int shadowed(V3 p,V3 ld,double dist){
    int i;double tt;
    for(i=0;i<nprim;i++){
        /* emissive props (laser beam, muzzle flash, eyes, sparks) are stand-ins for
           light, not blockers: letting them occlude painted a hard black stripe
           across the floor under the glowing beam.  Skipping them also drops ~20%
           of the shadow-ray work in a firing frame. */
        if(prims[i].m.constant)continue;
        if(prims[i].type==0){ if(hit_sphere(p,ld,prims[i].a,prims[i].r,&tt)&&tt<dist)return 1; }
        else { if(!miss_bound(p,ld,prims[i].bc,prims[i].br)&&hit_poly(p,ld,&prims[i],&tt)&&tt<dist)return 1; }
    }
    return 0;
}
static V3 shade(V3 ro,V3 rd){
    double t;V3 nn;Mat m;
    if(!trace(ro,rd,&t,&nn,&m))return v(0.53,0.60,0.75); /* sky */
    if(m.constant)return m.col;                          /* unlit/emissive (laser, muzzle flash) */
    V3 p=add(ro,scl(rd,t));V3 col=v(0,0,0);int i;
    for(i=0;i<nlight;i++){
        if(lights[i].type==0){ col=add(col,scl(m.col,m.Ka*lights[i].inten)); continue; }
        V3 ld;double dist;
        if(lights[i].type==1){ ld=norm(scl(lights[i].p,-1)); dist=1e30; }
        else { V3 d=sub(lights[i].p,p);dist=len(d);ld=norm(d); }
        if(i==keyLight&&shadowed(add(p,scl(nn,1e-3)),ld,dist))continue;
        double nl=dot(nn,ld);if(nl<0)nl=0;
        col=add(col,scl(v(m.col.x*lights[i].col.x,m.col.y*lights[i].col.y,m.col.z*lights[i].col.z),m.Kd*nl*lights[i].inten));
        if(m.Ks>0&&nl>0){ V3 h=norm(sub(ld,rd));double sp=dot(nn,h);if(sp>0){sp=pow(sp,1.0/(m.rough+.02)); col=add(col,scl(lights[i].col,m.Ks*sp*lights[i].inten));}}
    }
    return col;
}

/* ---- framebuffer + pixel output ---- */
static unsigned char *fb=0;   /* RESX*RESY*3 RGB, for writing PPM frames to disk */
static void putpix(int x,int y,V3 c){
    int r=(int)(c.x*65535),g=(int)(c.y*65535),b=(int)(c.z*65535);
    if(r<0)r=0;if(r>65535)r=65535;if(g<0)g=0;if(g>65535)g=65535;if(b<0)b=0;if(b>65535)b=65535;
#ifndef HOST_PREVIEW
    { RGBColor rc; rc.red=r;rc.green=g;rc.blue=b; SetCPixel(x,y,&rc); }
#endif
    if(fb){long i=((long)y*RESX+x)*3; fb[i]=r>>8; fb[i+1]=g>>8; fb[i+2]=b>>8;}
}
/* write the framebuffer as a binary PPM (P6) on the app's volume */
static void write_ppm(const char*path){
    FILE*f=fopen(path,"wb"); if(!f)return;
    fprintf(f,"P6\n%d %d\n255\n",RESX,RESY);
    fwrite(fb,1,(long)RESX*RESY*3,f);
    fclose(f);
}

/* ---- very small RIB tokenizer ---- */
static FILE*rf; static char tok[256];
static int nexttok(void){
    int c,i=0;
    for(;;){                       /* skip whitespace AND '#' comments to end of line */
        do{c=fgetc(rf);}while(c==' '||c=='\t'||c=='\n'||c=='\r');
        if(c!='#')break;
        while((c=fgetc(rf))!=EOF&&c!='\n'&&c!='\r'){}
        if(c==EOF)break;
    }
    if(c==EOF)return 0;
    if(c=='"'){ while((c=fgetc(rf))!=EOF&&c!='"'&&i<255)tok[i++]=c; tok[i]=0; return 2; }
    if(c=='['||c==']'){ tok[0]=c;tok[1]=0;return c=='['?3:4; }
    do{ tok[i++]=c; c=fgetc(rf);}while(c!=EOF&&c!=' '&&c!='\t'&&c!='\n'&&c!='\r'&&c!='['&&c!=']'&&c!='"'&&i<255);
    if(c!=EOF)ungetc(c,rf); tok[i]=0; return 1;
}
#define MAXNUM 256            /* a Polygon "P" of up to 85 vertices */
static double nums[MAXNUM];
static int isnumtok(const char*s){ char c=s[0]; return c=='-'||c=='+'||c=='.'||(c>='0'&&c<='9'); }
/* read [ ... ], OR a run of bare numbers (Translate 0 -2.2 8); return the count.
   Values past MAXNUM are consumed but dropped: the array must never be written
   past its end (there is no MMU on a 68K Mac to catch it) and the reader must
   still stay in sync with the stream. */
static int readnums(void){
    int n=0; long pos=ftell(rf); int tt=nexttok();
    if(tt==3){ while((tt=nexttok())&&tt!=4){ if(n<MAXNUM)nums[n]=atof(tok); n++; }
               return n>MAXNUM?MAXNUM:n; }
    if(tt==1&&isnumtok(tok)){ nums[n++]=atof(tok);
        for(;;){ pos=ftell(rf); tt=nexttok();
            if(tt==1&&isnumtok(tok)){ if(n<MAXNUM)nums[n]=atof(tok); n++; }
            else { fseek(rf,pos,SEEK_SET); break; } }
    } else fseek(rf,pos,SEEK_SET);
    return n>MAXNUM?MAXNUM:n;
}
/* bounded copy - RIB shader/light names are arbitrary length (real RIBs use paths),
   the token buffer is 256 bytes and these landing pads were 64. */
static void copytok(char*dst,int cap,const char*src){
    int i=0; for(;i<cap-1&&src[i];i++)dst[i]=src[i]; dst[i]=0;
}

/* RIB defaults a shader starts from.  Naming a Surface resets every parameter it
   does not mention - otherwise `Surface "matte"` after a `"Kd" [0.85]` surface keeps
   that Kd and renders too bright. */
static void surface_defaults(Mat*m,const char*nm){
    m->Ka=1; m->Kd=0.6; m->rough=0.08;
    m->Ks=(!strcmp(nm,"plastic")||!strncmp(nm,"shiny",5)||!strcmp(nm,"metal"))?0.6:0.0;
    m->constant=!strcmp(nm,"constant");        /* unlit/emissive surface */
}

/* Append one planar face (nv=3 triangle a,b,c or nv=4 quad a,b,c,d): face normal,
   the projection plane its inside-test uses, and a bounding sphere for culling.
   Degenerate (zero-area) faces are dropped - they have no normal to shade with. */
static void add_face(V3 a,V3 b,V3 c,V3 d,int nv,Mat m){
    V3 e1,e2,nrm; double nx,ny,nz,dd;
    if(nprim>=MAXP)return;
    e1=sub(b,a); e2=sub(nv==4?d:c,a);
    nrm=v(e1.y*e2.z-e1.z*e2.y, e1.z*e2.x-e1.x*e2.z, e1.x*e2.y-e1.y*e2.x);
    if(len(nrm)<1e-12)return;
    { Prim p; p.type=1; p.nv=(short)nv; p.a=a;p.b=b;p.c=c;p.d=(nv==4?d:c); p.m=m;
      p.qn=norm(nrm);
      nx=fabs(p.qn.x);ny=fabs(p.qn.y);nz=fabs(p.qn.z);
      if(nx>=ny&&nx>=nz){p.ax0=1;p.ax1=2;}          /* drop the dominant normal axis */
      else if(ny>=nz){p.ax0=0;p.ax1=2;}
      else {p.ax0=0;p.ax1=1;}
      p.bc=scl(add(add(p.a,p.b),add(p.c,p.d)),nv==4?0.25:(1.0/3.0));
      if(nv==3)p.bc=scl(add(add(p.a,p.b),p.c),1.0/3.0);
      p.br=len(sub(p.a,p.bc));
      dd=len(sub(p.b,p.bc));if(dd>p.br)p.br=dd;
      dd=len(sub(p.c,p.bc));if(dd>p.br)p.br=dd;
      if(nv==4){dd=len(sub(p.d,p.bc));if(dd>p.br)p.br=dd;}
      p.br+=1e-4;
      prims[nprim++]=p; }
}

#define MAXSTACK 32
static void parseRIB(const char*path){
    struct { M4 x; Mat m; int attrs; } stack[MAXSTACK];
    int sp=0,overflow=0;M4 cur;Mat curmat;
    m_ident(cur);curmat.col=v(1,1,1);curmat.Ka=1;curmat.Kd=.6;curmat.Ks=0;curmat.rough=.1;curmat.constant=0;
    M4 pre;m_ident(pre);int inworld=0;
    nprim=0;nlight=0;FOV=45;SS=1;m_ident(cam2world); /* reset scene for a fresh frame */
    rf=fopen(path,"r");if(!rf)return;int tt;
    while((tt=nexttok())){
        if(tt!=1)continue;
        if(!strcmp(tok,"Format")){nexttok();RESX=atoi(tok);nexttok();RESY=atoi(tok);nexttok();}
        else if(!strcmp(tok,"PixelSamples")){readnums();SS=(int)nums[0];if(SS<1)SS=1;if(SS>4)SS=4;}
        else if(!strcmp(tok,"Projection")){nexttok();/*"perspective"*/ int t2=nexttok();/*"fov"*/
            if(t2==2&&!strcmp(tok,"fov")){readnums();FOV=nums[0];} }
        else if(!strcmp(tok,"Translate")){readnums();m_trans(inworld?cur:pre,nums[0],nums[1],nums[2]);}
        else if(!strcmp(tok,"Rotate")){readnums();/* RenderMan is left-handed: negate angle for our right-handed m_rot */ m_rot(inworld?cur:pre,-nums[0],nums[1],nums[2],nums[3]);}
        else if(!strcmp(tok,"WorldBegin")){inworld=1;
            /* camera-to-world = inverse of pre (pre is world->camera). Build simple inverse: pre is T*R composed; invmat via transpose-rot + neg-trans is complex; approximate: we treat pre as identity-usable by ray origin at 0 and applying pre inverse analytically is hard. Instead store pre and invmat numerically below. */
            memcpy(cam2world,pre,sizeof(pre));
        }
        else if(!strcmp(tok,"WorldEnd")){break;}
        /* AttributeBegin saves the WHOLE graphics state (RI spec) - transform AND the
           shading attributes; TransformBegin saves only the transform.  Pushing just
           the transform let Color/Surface leak out of a block and colour whatever came
           next.  Depth past MAXSTACK is counted, not written (stack[16] had no bound
           check at all), so nesting stays balanced instead of scribbling over locals. */
        else if(!strcmp(tok,"AttributeBegin")||!strcmp(tok,"TransformBegin")){
            int isattr=(tok[0]=='A');
            if(sp<MAXSTACK){memcpy(stack[sp].x,cur,sizeof(cur));stack[sp].m=curmat;stack[sp].attrs=isattr;sp++;}
            else overflow++; }
        else if(!strcmp(tok,"AttributeEnd")||!strcmp(tok,"TransformEnd")){
            if(overflow>0)overflow--;
            else if(sp>0){sp--;memcpy(cur,stack[sp].x,sizeof(cur));if(stack[sp].attrs)curmat=stack[sp].m;} }
        else if(!strcmp(tok,"Color")){readnums();curmat.col=v(nums[0],nums[1],nums[2]);}
        else if(!strcmp(tok,"Surface")){nexttok();/*name*/ char nm[64];copytok(nm,sizeof(nm),tok);
            /* a named shader starts from its defaults, then the params it declares */
            surface_defaults(&curmat,nm);
            /* peek params */
            long pos;int t2;
            for(;;){pos=ftell(rf);t2=nexttok();if(t2!=2){fseek(rf,pos,SEEK_SET);break;}
                char key[64];copytok(key,sizeof(key),tok);readnums();
                if(!strcmp(key,"Ks"))curmat.Ks=nums[0];
                else if(!strcmp(key,"Kd"))curmat.Kd=nums[0];
                else if(!strcmp(key,"Ka"))curmat.Ka=nums[0];
                else if(!strcmp(key,"roughness"))curmat.rough=nums[0];
            }
        }
        else if(!strcmp(tok,"LightSource")){nexttok();char nm[64];copytok(nm,sizeof(nm),tok);nexttok();/*seq*/
            Light L;L.type=0;L.col=v(1,1,1);L.inten=1;L.p=v(0,0,0);
            if(!strcmp(nm,"distantlight"))L.type=1; else if(!strcmp(nm,"pointlight"))L.type=2; else L.type=0;
            long pos;int t2;V3 from=v(0,0,0),to=v(0,0,0);
            for(;;){pos=ftell(rf);t2=nexttok();if(t2!=2){fseek(rf,pos,SEEK_SET);break;}
                char key[64];copytok(key,sizeof(key),tok);readnums();
                if(!strcmp(key,"intensity"))L.inten=nums[0];
                else if(!strcmp(key,"lightcolor"))L.col=v(nums[0],nums[1],nums[2]);
                else if(!strcmp(key,"from"))from=v(nums[0],nums[1],nums[2]);
                else if(!strcmp(key,"to"))to=v(nums[0],nums[1],nums[2]);
            }
            if(L.type==1)L.p=norm(sub(to,from)); else if(L.type==2)L.p=from;
            if(nlight<MAXL)lights[nlight++]=L;
        }
        else if(!strcmp(tok,"Sphere")){readnums();/*r zmin zmax tmax*/
            if(nprim<MAXP){Prim p;p.type=0;p.r=nums[0];p.a=m_pt(cur,v(0,0,0));p.m=curmat;
                p.bc=p.a;p.br=p.r; prims[nprim++]=p;} }
        /* Polygon: any vertex count, and the positions may not be the first parameter.
           This used to read whatever parameter came first as "P", require at least 4
           vertices (so every triangle - the commonest RIB primitive - vanished with no
           diagnostic) and silently drop vertices 5..n. */
        else if(!strcmp(tok,"Polygon")){
            int n=0; long pos;int t2;
            for(;;){ pos=ftell(rf); t2=nexttok(); if(t2!=2){fseek(rf,pos,SEEK_SET);break;}
                { char key[64];int cnt;copytok(key,sizeof(key),tok);cnt=readnums();
                  if(!strcmp(key,"P")){n=cnt;break;} } }       /* skip Cs/N/st/... */
            if(n>=9){ int nv=n/3,k;                            /* fan from vertex 0 */
                V3 v0=m_pt(cur,v(nums[0],nums[1],nums[2]));
                for(k=1;k+1<nv;k++){
                    V3 v1=m_pt(cur,v(nums[k*3],nums[k*3+1],nums[k*3+2]));
                    V3 v2=m_pt(cur,v(nums[k*3+3],nums[k*3+4],nums[k*3+5]));
                    if(nv==4&&k==1){                            /* keep quads as one prim */
                        V3 v3=m_pt(cur,v(nums[9],nums[10],nums[11]));
                        add_face(v0,v1,v2,v3,4,curmat); break; }
                    add_face(v0,v1,v2,v2,3,curmat);
                }
            }
        }
    }
    fclose(rf);
    { int i; double best=-1; keyLight=-1;         /* brightest non-ambient light casts shadows */
      for(i=0;i<nlight;i++) if(lights[i].type!=0 && lights[i].inten>best){best=lights[i].inten;keyLight=i;} }
}

/* invmat the world->camera (pre) transform to get camera position + basis.
   pre = R then T applied to world; we solve camera origin = pre^-1 * 0. Since our
   scenes use Translate 0 -h d then Rotate, invmat numerically via Gauss-Jordan. */
static void invmat(M4 a,M4 inv){
    M4 m;memcpy(m,a,sizeof(m));m_ident(inv);int i,j,k;
    for(i=0;i<4;i++){double piv=m[i*4+i];if(fabs(piv)<1e-9){for(j=i+1;j<4;j++)if(fabs(m[j*4+i])>1e-9){for(k=0;k<4;k++){double t=m[i*4+k];m[i*4+k]=m[j*4+k];m[j*4+k]=t;t=inv[i*4+k];inv[i*4+k]=inv[j*4+k];inv[j*4+k]=t;}piv=m[i*4+i];break;}}
        for(k=0;k<4;k++){m[i*4+k]/=piv;inv[i*4+k]/=piv;}
        for(j=0;j<4;j++)if(j!=i){double f=m[j*4+i];for(k=0;k<4;k++){m[j*4+k]-=f*m[i*4+k];inv[j*4+k]-=f*inv[i*4+k];}}
    }
}

/* render the currently-parsed scene into the window (and fb, if allocated) */
static void render_scene(void){
    /* camera straight from the RIB world-to-camera transform.
       eye = pre^-1 * origin;  aim = pre^-1 * (0,0,1)  [RenderMan looks +Z] */
    M4 c2w;invmat(cam2world,c2w);
    V3 eye=m_pt(c2w,v(0,0,0));
    V3 aim=m_pt(c2w,v(0,0,1));
    V3 fwd=norm(sub(aim,eye));
    V3 up=v(0,1,0);
    /* RenderMan is left-handed: +x is screen-right looking down +z, so right = up x fwd */
    V3 right=norm(v(up.y*fwd.z-up.z*fwd.y, up.z*fwd.x-up.x*fwd.z, up.x*fwd.y-up.y*fwd.x));
    V3 tup=v(fwd.y*right.z-fwd.z*right.y, fwd.z*right.x-fwd.x*right.z, fwd.x*right.y-fwd.y*right.x);
    double aspect=(double)RESX/(double)RESY;
    double sc=tan(FOV*3.14159265/360.0);
    double inv=1.0/(double)(SS*SS);
    int px,py,sx,sy;
    for(py=0;py<RESY;py++)for(px=0;px<RESX;px++){
        V3 acc=v(0,0,0);
        for(sy=0;sy<SS;sy++)for(sx=0;sx<SS;sx++){   /* SSxSS supersampled anti-aliasing */
            double ox=(sx+0.5)/SS, oy=(sy+0.5)/SS;
            double dx=(2.0*((px+ox)/RESX)-1.0)*sc*aspect;
            double dy=(1.0-2.0*((py+oy)/RESY))*sc;
            V3 rd=norm(add(fwd, add(scl(right,dx), scl(tup,dy))));
            acc=add(acc,shade(eye,rd));
        }
        putpix(px,py,scl(acc,inv));
    }
}

#ifdef HOST_PREVIEW
int main(int argc,char**argv){
    if(argc<3){fprintf(stderr,"usage: %s in.rib out.ppm\n",argv[0]);return 1;}
    parseRIB(argv[1]);
    if(RESX>440)RESX=440; if(RESY>320)RESY=320;
    fb=(unsigned char*)malloc((long)RESX*RESY*3);
    render_scene();
    if(fb)write_ppm(argv[2]);
    return 0;
}
#else
int main(void){
    WindowPtr w;Rect r;int i;char rib[24],ppm[24];FILE*tf;
    InitGraf(&qd.thePort);InitFonts();InitWindows();InitMenus();InitCursor();

    /* Batch/farm mode: render whatever frameNN.rib files are staged on our volume
       (any subset - each farm node gets a different slice) to frameNN.ppm, then quit. */
    { int first=-1;
      for(i=0;i<100;i++){sprintf(rib,"frame%02d.rib",i);tf=fopen(rib,"r");if(tf){fclose(tf);first=i;break;}}
      if(first>=0){
        sprintf(rib,"frame%02d.rib",first);parseRIB(rib);   /* size the window from the first frame we have */
        if(RESX>440)RESX=440; if(RESY>320)RESY=320;
        SetRect(&r,8,44,8+RESX,44+RESY);
        w=NewCWindow(0,&r,"\pTinyRIB Farm",1,0,(WindowPtr)-1,0,0);SetPort(w);
        for(i=0;i<100;i++){
            sprintf(rib,"frame%02d.rib",i);sprintf(ppm,"frame%02d.ppm",i);
            tf=fopen(rib,"r");if(!tf)continue;fclose(tf);    /* skip frames not assigned to this node */
            parseRIB(rib);
            if(RESX>440)RESX=440; if(RESY>320)RESY=320;
            fb=(unsigned char*)malloc((long)RESX*RESY*3);
            render_scene();
            if(fb){write_ppm(ppm);free(fb);fb=0;}
        }
        tf=fopen("DONE","wb");if(tf){fputs("ok\n",tf);fclose(tf);}  /* host waits on this */
        return 0;
      }
    }

    /* Single interactive mode: render toy.rib and wait for a click. */
    parseRIB("toy.rib");
    if(RESX>440)RESX=440; if(RESY>320)RESY=320;
    SetRect(&r,20,44,20+RESX,44+RESY);
    w=NewCWindow(0,&r,"\pTinyRIB - RenderMan on a 1994 Mac",1,0,(WindowPtr)-1,0,0);SetPort(w);
    render_scene();
    { EventRecord e; while(!WaitNextEvent(mDownMask|keyDownMask,&e,60,0)){} }
    return 0;
}
#endif
