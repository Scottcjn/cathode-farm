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
typedef struct { int type; V3 a,b,c,d; double r; Mat m; } Prim; /* 0=sphere(a=center,r), 1=quad(a,b,c,d) */
typedef struct { int type; V3 p; V3 col; double inten; } Light;  /* 0=ambient,1=distant(p=dir),2=point(p=pos) */

#define MAXP 64
#define MAXL 8
static Prim prims[MAXP]; static int nprim=0;
static Light lights[MAXL]; static int nlight=0;
static int RESX=320,RESY=240; static double FOV=45;
static M4 cam2world;  /* inverse of the pre-world transform */

/* ---- ray/prim intersection ---- */
static int hit_sphere(V3 ro,V3 rd,V3 c,double r,double *t){
    V3 oc=sub(ro,c);double b=dot(oc,rd),cc=dot(oc,oc)-r*r,d=b*b-cc;
    if(d<0)return 0;double s=sqrt(d),t0=-b-s;if(t0<1e-4)t0=-b+s;if(t0<1e-4)return 0;*t=t0;return 1;}
static int hit_quad(V3 ro,V3 rd,Prim*p,double *t,V3*n){
    V3 e1=sub(p->b,p->a),e2=sub(p->d,p->a);V3 nn=norm(v(e1.y*e2.z-e1.z*e2.y,e1.z*e2.x-e1.x*e2.z,e1.x*e2.y-e1.y*e2.x));
    double den=dot(nn,rd);if(fabs(den)<1e-6)return 0;double tt=dot(sub(p->a,ro),nn)/den;if(tt<1e-4)return 0;
    V3 h=add(ro,scl(rd,tt));V3 hp=sub(h,p->a);
    double u=dot(hp,norm(e1))/len(e1),w=dot(hp,norm(e2))/len(e2);
    if(u<0||u>1||w<0||w>1)return 0;*t=tt;*n=nn;return 1;}

static int trace(V3 ro,V3 rd,double *t,V3 *n,Mat *m){
    int i,best=-1;double bt=1e30,tt;V3 nn;
    for(i=0;i<nprim;i++){
        if(prims[i].type==0){ if(hit_sphere(ro,rd,prims[i].a,prims[i].r,&tt)&&tt<bt){bt=tt;best=i;} }
        else { if(hit_quad(ro,rd,&prims[i],&tt,&nn)&&tt<bt){bt=tt;best=i;} }
    }
    if(best<0)return 0;*t=bt;V3 h=add(ro,scl(rd,bt));
    if(prims[best].type==0)*n=norm(sub(h,prims[best].a));
    else { V3 e1=sub(prims[best].b,prims[best].a),e2=sub(prims[best].d,prims[best].a);
           *n=norm(v(e1.y*e2.z-e1.z*e2.y,e1.z*e2.x-e1.x*e2.z,e1.x*e2.y-e1.y*e2.x));
           if(dot(*n,rd)>0)*n=scl(*n,-1); }
    *m=prims[best].m;return 1;
}
static int shadowed(V3 p,V3 ld,double dist){
    int i;double tt;V3 nn;
    for(i=0;i<nprim;i++){
        if(prims[i].type==0){ if(hit_sphere(p,ld,prims[i].a,prims[i].r,&tt)&&tt<dist)return 1; }
        else { if(hit_quad(p,ld,&prims[i],&tt,&nn)&&tt<dist)return 1; }
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
        if(shadowed(add(p,scl(nn,1e-3)),ld,dist))continue;
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
    do{c=fgetc(rf);}while(c==' '||c=='\t'||c=='\n'||c=='\r');
    if(c==EOF)return 0;
    if(c=='"'){ while((c=fgetc(rf))!=EOF&&c!='"'&&i<255)tok[i++]=c; tok[i]=0; return 2; }
    if(c=='['||c==']'){ tok[0]=c;tok[1]=0;return c=='['?3:4; }
    do{ tok[i++]=c; c=fgetc(rf);}while(c!=EOF&&c!=' '&&c!='\t'&&c!='\n'&&c!='\r'&&c!='['&&c!=']'&&c!='"'&&i<255);
    if(c!=EOF)ungetc(c,rf); tok[i]=0; return 1;
}
static double nums[64];
static int isnumtok(const char*s){ char c=s[0]; return c=='-'||c=='+'||c=='.'||(c>='0'&&c<='9'); }
static int readnums(void){ /* read [ ... ], OR a run of bare numbers (Translate 0 -2.2 8); return count */
    int n=0; long pos=ftell(rf); int tt=nexttok();
    if(tt==3){ while((tt=nexttok())&&tt!=4)nums[n++]=atof(tok); return n; }
    if(tt==1&&isnumtok(tok)){ nums[n++]=atof(tok);
        for(;;){ pos=ftell(rf); tt=nexttok();
            if(tt==1&&isnumtok(tok)) nums[n++]=atof(tok);
            else { fseek(rf,pos,SEEK_SET); break; } }
    } else fseek(rf,pos,SEEK_SET);
    return n;
}

static void parseRIB(const char*path){
    M4 stack[16];int sp=0;M4 cur;Mat curmat;
    m_ident(cur);curmat.col=v(1,1,1);curmat.Ka=1;curmat.Kd=.6;curmat.Ks=0;curmat.rough=.1;curmat.constant=0;
    M4 pre;m_ident(pre);int inworld=0;
    nprim=0;nlight=0;FOV=45;m_ident(cam2world); /* reset scene for a fresh frame */
    rf=fopen(path,"r");if(!rf)return;int tt;
    while((tt=nexttok())){
        if(tt!=1)continue;
        if(!strcmp(tok,"Format")){nexttok();RESX=atoi(tok);nexttok();RESY=atoi(tok);nexttok();}
        else if(!strcmp(tok,"Projection")){nexttok();/*"perspective"*/ int t2=nexttok();/*"fov"*/
            if(t2==2&&!strcmp(tok,"fov")){readnums();FOV=nums[0];} }
        else if(!strcmp(tok,"Translate")){readnums();m_trans(inworld?cur:pre,nums[0],nums[1],nums[2]);}
        else if(!strcmp(tok,"Rotate")){readnums();/* RenderMan is left-handed: negate angle for our right-handed m_rot */ m_rot(inworld?cur:pre,-nums[0],nums[1],nums[2],nums[3]);}
        else if(!strcmp(tok,"WorldBegin")){inworld=1;
            /* camera-to-world = inverse of pre (pre is world->camera). Build simple inverse: pre is T*R composed; invmat via transpose-rot + neg-trans is complex; approximate: we treat pre as identity-usable by ray origin at 0 and applying pre inverse analytically is hard. Instead store pre and invmat numerically below. */
            memcpy(cam2world,pre,sizeof(pre));
        }
        else if(!strcmp(tok,"WorldEnd")){break;}
        else if(!strcmp(tok,"AttributeBegin")||!strcmp(tok,"TransformBegin")){memcpy(stack[sp++],cur,sizeof(cur));}
        else if(!strcmp(tok,"AttributeEnd")||!strcmp(tok,"TransformEnd")){if(sp>0)memcpy(cur,stack[--sp],sizeof(cur));}
        else if(!strcmp(tok,"Color")){readnums();curmat.col=v(nums[0],nums[1],nums[2]);}
        else if(!strcmp(tok,"Surface")){nexttok();/*name*/ char nm[64];strcpy(nm,tok);
            /* read optional param pairs "Ks" [..] etc until next command-ish */
            curmat.Ks=(!strcmp(nm,"plastic")||!strncmp(nm,"shiny",5)||!strcmp(nm,"metal"))?0.6:0.0;
            curmat.rough=0.08;
            curmat.constant=!strcmp(nm,"constant");   /* unlit/emissive surface */
            /* peek params */
            long pos;int t2;
            for(;;){pos=ftell(rf);t2=nexttok();if(t2!=2){fseek(rf,pos,SEEK_SET);break;}
                char key[64];strcpy(key,tok);readnums();
                if(!strcmp(key,"Ks"))curmat.Ks=nums[0];
                else if(!strcmp(key,"Kd"))curmat.Kd=nums[0];
                else if(!strcmp(key,"Ka"))curmat.Ka=nums[0];
                else if(!strcmp(key,"roughness"))curmat.rough=nums[0];
            }
        }
        else if(!strcmp(tok,"LightSource")){nexttok();char nm[64];strcpy(nm,tok);nexttok();/*seq*/
            Light L;L.type=0;L.col=v(1,1,1);L.inten=1;L.p=v(0,0,0);
            if(!strcmp(nm,"distantlight"))L.type=1; else if(!strcmp(nm,"pointlight"))L.type=2; else L.type=0;
            long pos;int t2;V3 from=v(0,0,0),to=v(0,0,0);
            for(;;){pos=ftell(rf);t2=nexttok();if(t2!=2){fseek(rf,pos,SEEK_SET);break;}
                char key[64];strcpy(key,tok);readnums();
                if(!strcmp(key,"intensity"))L.inten=nums[0];
                else if(!strcmp(key,"lightcolor"))L.col=v(nums[0],nums[1],nums[2]);
                else if(!strcmp(key,"from"))from=v(nums[0],nums[1],nums[2]);
                else if(!strcmp(key,"to"))to=v(nums[0],nums[1],nums[2]);
            }
            if(L.type==1)L.p=norm(sub(to,from)); else if(L.type==2)L.p=from;
            if(nlight<MAXL)lights[nlight++]=L;
        }
        else if(!strcmp(tok,"Sphere")){readnums();/*r zmin zmax tmax*/
            if(nprim<MAXP){Prim p;p.type=0;p.r=nums[0];p.a=m_pt(cur,v(0,0,0));p.m=curmat;prims[nprim++]=p;} }
        else if(!strcmp(tok,"Polygon")){nexttok();/*"P"*/ int n=readnums();
            if(nprim<MAXP&&n>=12){Prim p;p.type=1;p.a=m_pt(cur,v(nums[0],nums[1],nums[2]));
                p.b=m_pt(cur,v(nums[3],nums[4],nums[5]));p.c=m_pt(cur,v(nums[6],nums[7],nums[8]));
                p.d=m_pt(cur,v(nums[9],nums[10],nums[11]));p.m=curmat;prims[nprim++]=p;} }
    }
    fclose(rf);
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
    int px,py;
    for(py=0;py<RESY;py++)for(px=0;px<RESX;px++){
        double dx=(2.0*((px+0.5)/RESX)-1.0)*sc*aspect;
        double dy=(1.0-2.0*((py+0.5)/RESY))*sc;
        V3 rd=norm(add(fwd, add(scl(right,dx), scl(tup,dy))));
        putpix(px,py,shade(eye,rd));
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
