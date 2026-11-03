"""Pure geometry and state for the non-cubic notation models.

No GUI objects live here. State is shared between the large viewer,
thumbnails and transition endpoints, so a picture cannot use a different
colour convention from its animation.
"""
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from .cube import FACE_COLORS
from .puzzles import (Pyraminx, Skewb, _dot, _norm, _rotate, _centroid,
    sq1_parse, sq1_format, sq1_units, _SQ1_START, _UNIT0, _side_colour, _is_corner_piece)
from .megaminx import cross, clip

NON_CUBES = ("pyram","skewb","sq1","minx","clock")


@dataclass(frozen=True)
class Surface:
    points: tuple
    color: str
    key: object = None

    @property
    def center(self):
        return _centroid(self.points)


def surface(points, color, key=None, normal=None):
    points = tuple(points)
    n = cross(tuple(points[1][i]-points[0][i] for i in range(3)),
              tuple(points[2][i]-points[0][i] for i in range(3)))
    if _dot(n,normal or _centroid(points))<0:
        points = points[::-1]
    return Surface(points,color,key)


def normal_of(points):
    a,b,c = points[:3]
    n = cross(tuple(b[i]-a[i] for i in range(3)),tuple(c[i]-a[i] for i in range(3)))
    return _norm(n) if _dot(n,n)>1e-18 else (0,0,0)


def tokens(puzzle, alg):
    return [sq1_format([p]) for p in sq1_parse(alg)] if puzzle=="sq1" else alg.split()


@lru_cache(maxsize=2)
def corner_model(puzzle):
    return (Pyraminx if puzzle=="pyram" else Skewb)()


def corner_scene(puzzle,alg):
    model = (Pyraminx if puzzle=="pyram" else Skewb)().apply(alg)
    return tuple(surface(points,color,index) for index,(points,color) in enumerate(zip(model.geometry,model.colors)))


def _box(x0,x1,y0,y1,z0,z1,color="#151515",key=None):
    out = []
    for axis, value in ((0,x0),(0,x1),(1,y0),(1,y1),(2,z0),(2,z1)):
        bounds = ((x0,x1),(y0,y1),(z0,z1))
        others = [i for i in range(3) if i!=axis]
        points = []
        for a,b in ((0,0),(1,0),(1,1),(0,1)):
            p = [0,0,0]
            p[axis] = value
            p[others[0]],p[others[1]] = bounds[others[0]][a],bounds[others[1]][b]
            points.append(tuple(p))
        normal = tuple((1 if value==bounds[axis][1] else -1) if i==axis else 0 for i in range(3))
        out.append(surface(points,color,key,normal))
    return out


SQ1_AXIS = (math.cos(math.radians(_UNIT0+90)),0,-math.sin(math.radians(_UNIT0+90)))


def sq1_scene(alg):
    units = sq1_units(alg)
    result = []
    for layer in (0,1):
        lay = units[layer*12:(layer+1)*12]
        y, inner_y = (1,.34) if layer==0 else (-1,-.34)
        for index,unit in enumerate(lay):
            pid = _SQ1_START[unit]
            same_next = _SQ1_START[lay[(index+1)%12]]==pid
            same_prev = _SQ1_START[lay[(index-1)%12]]==pid
            corner = _is_corner_piece(pid)
            r0 = math.sqrt(2) if corner and same_prev else 1/math.cos(math.pi/12)
            r1 = math.sqrt(2) if corner and same_next else 1/math.cos(math.pi/12)
            angle = math.radians(_UNIT0+30*index)
            a = (math.cos(angle)*r0,y,-math.sin(angle)*r0)
            b = (math.cos(angle+math.pi/6)*r1,y,-math.sin(angle+math.pi/6)*r1)
            key = ("layer",layer,unit)
            if not (corner and same_prev):
                top_points = [(0,y,0),a,b]
                if corner and same_next:
                    top_points.append((math.cos(angle+math.pi/3)*r0,y,-math.sin(angle+math.pi/3)*r0))
                result.append(surface(top_points,"#ffffff" if unit<12 else "#ffd500",key,(0,1 if layer==0 else -1,0)))
            ai,bi = (a[0],inner_y,a[2]),(b[0],inner_y,b[2])
            result.append(surface((a,ai,bi,b),_side_colour(_UNIT0+30*(unit%12)+15),key))
            result.append(surface(((0,inner_y,0),bi,ai),"#151515",key,(0,-1 if layer==0 else 1,0)))
    # Equatorial pieces keep their own physical orientation after a slice.
    slash_parity = sum(p=="/" for p in sq1_parse(alg))%2
    for face in _box(-1,1,-.30,.30,-1,1):
        n = normal_of(face.points)
        color = FACE_COLORS["R" if n[0]>.5 else "L" if n[0]<-.5 else "F" if n[2]>.5 else "B"] if abs(n[1])<.5 else "#151515"
        for right in (False,True):
            points = clip(list(face.points),SQ1_AXIS,0,right)
            if not points:
                continue
            if right and slash_parity:
                points = [_rotate(p,SQ1_AXIS,math.pi) for p in points]
            result.append(surface(points,color,("belt",right)))
    return tuple(result)


PIN_CORNERS = {"UL":(0,0),"UR":(0,2),"DL":(2,0),"DR":(2,2)}


def clock_selection(name):
    if name in PIN_CORNERS:
        return (name,)
    if name=="ALL":
        return tuple(PIN_CORNERS)
    return tuple(pin for pin in PIN_CORNERS if name in pin) if name in ("U","R","D","L") else ()


def clock_delta(name):
    front,back = [0]*9,[0]*9
    for pin in clock_selection(name):
        row,col = PIN_CORNERS[pin]
        for r in (row//2,row//2+1):
            for c in (col//2,col//2+1):
                front[r*3+c] = 1
        back[row*3+2-col] = -1
    return tuple(front+back)


def clock_state(alg):
    values = [0]*18
    flipped = False
    pins = ()
    for token in alg.split():
        if token=="y2":
            flipped = not flipped
            pins = ()
            continue
        match = re.fullmatch(r"(ALL|UR|UL|DR|DL|[URDL])(\d+)([+-])",token)
        if not match:
            if token in PIN_CORNERS:
                pins = tuple(set(pins+(token,)))
                continue
            raise ValueError("Unsupported Clock move: "+token)
        name,amount,sign = match.groups()
        amount = int(amount)*(1 if sign=="+" else -1)
        delta = clock_delta(name)
        for index,d in enumerate(delta):
            dst = (index+9)%18 if flipped else index
            values[dst] += d*amount
        pins = ()
    return tuple(v%12 for v in values),flipped,pins


def _disc(cx,cy,z,radius,color,key,back=False,steps=32):
    points = [(cx+radius*math.cos(a*math.tau/steps),cy+radius*math.sin(a*math.tau/steps),z) for a in range(steps)]
    return surface(points,color,key,(0,0,-1 if back else 1))


def clock_scene(alg,values=None,active_pins=None,pin_lift=1.0):
    actual,flipped,pins = clock_state(alg)
    values = actual if values is None else values
    pins = pins if active_pins is None else active_pins
    outline = []
    for cx,cy,start in ((1.09,1.09,0),(-1.09,1.09,90),(-1.09,-1.09,180),(1.09,-1.09,270)):
        for step in range(9):
            angle = math.radians(start+step*90/8)
            outline.append((cx+.23*math.cos(angle),cy+.23*math.sin(angle)))
    out = []
    for z in (-.13,.13):
        out.append(surface([(x,y,z) for x,y in outline],"#27282b","case",(0,0,1 if z>0 else -1)))
    for a,b in zip(outline,outline[1:]+outline[:1]):
        out.append(surface(((a[0],a[1],-.13),(b[0],b[1],-.13),(b[0],b[1],.13),(a[0],a[1],.13)),"#353638","case"))
    for side in (0,1):
        sign = 1 if side==0 else -1
        z = sign*.145
        for row in range(3):
            for col in range(3):
                index = side*9+row*3+col
                x,y = (col-1)*.82,(1-row)*.82
                x *= sign
                out.append(_disc(x,y,z,.358,"#090a0c",("bezel",index),side==1))
                out.append(_disc(x,y,z+sign*.003,.318,"#ece8dd" if side==0 else "#697c93",("dial",index),side==1))
                for hour in range(12):
                    angle = hour*math.pi/6
                    a = (x+sign*math.sin(angle)*.269,y+math.cos(angle)*.269,z+sign*.007)
                    b = (x+sign*math.sin(angle)*.295,y+math.cos(angle)*.295,z+sign*.007)
                    width = .009 if hour else .014
                    points = ((a[0]-width,a[1],a[2]),(b[0]-width,b[1],b[2]),(b[0]+width,b[1],b[2]),(a[0]+width,a[1],a[2]))
                    # Tangent offset avoids degenerate horizontal markers.
                    tangent = (math.cos(angle)*width,-sign*math.sin(angle)*width,0)
                    points = tuple(tuple(p[k]+s*tangent[k] for k in range(3)) for p,s in ((a,-1),(b,-1),(b,1),(a,1)))
                    out.append(surface(points,"#2a2b30" if side==0 else "#dfe4ee",("tick",index,hour),(0,0,sign)))
                angle = values[index]*math.pi/6
                tip = (x+sign*math.sin(angle)*.235,y+math.cos(angle)*.235,z+sign*.013)
                left = (x-.033,y-.026,z+sign*.013)
                right = (x+.033,y-.026,z+sign*.013)
                out.append(surface((left,right,tip),"#242629" if side==0 else "#faf1cc",("hand",index),(0,0,sign)))
                out.append(_disc(x,y,z+sign*.017,.038,"#d3aa30",("hub",index),side==1,16))
        for pin,(row,col) in PIN_CORNERS.items():
            selected = side==int(flipped) and pin in pins
            x,y = (col-1)*.41*sign,(1-row)*.41
            lift = pin_lift if selected else 0.0
            pin_z = z+sign*(.025+.05*lift)
            for index in range(16):
                a,b = index*math.tau/16,(index+1)*math.tau/16
                p,q = (x+.083*math.cos(a),y+.083*math.sin(a)),(x+.083*math.cos(b),y+.083*math.sin(b))
                side_color = "#%02x%02x%02x" % tuple(round(a+(b-a)*lift) for a,b in zip((52,49,42),(142,116,44)))
                out.append(surface(((p[0],p[1],z),(q[0],q[1],z),(q[0],q[1],pin_z),(p[0],p[1],pin_z)),side_color,("pinSide",side,pin)))
            pin_color = "#%02x%02x%02x" % tuple(round(a+(b-a)*lift) for a,b in zip((77,72,64),(244,204,12)))
            out.append(_disc(x,y,pin_z,.083,pin_color,("pin",side,pin),side==1,24))
    if flipped:
        out = [Surface(tuple(_rotate(p,(0,1,0),math.pi) for p in s.points),s.color,s.key) for s in out]
    return tuple(out)


@lru_cache(maxsize=192)
def scene(puzzle,alg=""):
    if puzzle in ("pyram","skewb"):
        return corner_scene(puzzle,alg)
    if puzzle=="sq1":
        return sq1_scene(alg)
    if puzzle=="clock":
        return clock_scene(alg)
    if puzzle=="minx":
        from .megaminx import geometry,state
        return tuple(surface(points,color,index,normal) for index,((points,_home,normal),color) in enumerate(zip(geometry()[0],state(alg))))
    raise ValueError("Unsupported 3D puzzle: "+puzzle)


def move_spec(puzzle,token):
    if puzzle in ("pyram","skewb"):
        axis,threshold = corner_model(puzzle).MOVES[token[0]]
        return _norm(axis),threshold,False,(1 if token.endswith("'") else -1)*math.tau/3
    if puzzle=="minx":
        from .megaminx import move_spec as spec
        return spec(token)
    return None


def transition_scene(puzzle,source_alg,token,progress,inverse=False):
    """Interpolate a single physical move from the source, including shape changes."""
    direction = -1 if inverse else 1
    source = scene(puzzle,source_alg)
    if puzzle=="clock":
        values,flipped,_pins = clock_state(source_alg)
        if token=="y2":
            return tuple(Surface(tuple(_rotate(p,(0,1,0),math.pi*progress) for p in s.points),s.color,s.key) for s in source)
        match = re.fullmatch(r"(ALL|UR|UL|DR|DL|[URDL])(\d+)([+-])",token)
        if not match:
            return source
        name,amount,sign = match.groups()
        amount = int(amount)*(1 if sign=="+" else -1)*direction*progress
        target = list(values)
        for index,delta in enumerate(clock_delta(name)):
            target[(index+9)%18 if flipped else index] += delta*amount
        lift = max(0,math.sin(math.pi*progress))**.6
        return clock_scene(source_alg,tuple(target),clock_selection(name),lift)
    spec = move_spec(puzzle,token)
    result = []
    if puzzle=="sq1":
        move = sq1_parse(token)[0]
        for s in source:
            axis,angle = (0,1,0),0
            if move=="/":
                if _dot(s.center,SQ1_AXIS)>1e-8:
                    axis,angle = SQ1_AXIS,math.pi*direction*progress
            elif s.key[0]=="layer":
                layer = s.key[1]
                angle = (move[1] if layer else -move[0])*math.pi/6*direction*progress
            result.append(Surface(tuple(_rotate(p,axis,angle) for p in s.points),s.color,s.key))
        return tuple(result)
    axis,threshold,complement,angle = spec
    for s in source:
        selected = _dot(s.center,axis)<threshold-1e-8 if complement else _dot(s.center,axis)>threshold+1e-8
        points = tuple(_rotate(p,axis,angle*progress*direction) for p in s.points) if selected else s.points
        result.append(Surface(points,s.color,s.key))
    # Seal the exposed cut on corner-turning and pentagonal models.
    crossing = []
    for s in source:
        for a,b in zip(s.points,s.points[1:]+s.points[:1]):
            da,db = _dot(a,axis)-threshold,_dot(b,axis)-threshold
            if da*db < -1e-12:
                t = da/(da-db)
                p = tuple(a[k]+t*(b[k]-a[k]) for k in range(3))
                if not any(sum((p[k]-q[k])**2 for k in range(3))<1e-12 for q in crossing):
                    crossing.append(p)
            elif abs(da)<1e-8 and not any(sum((a[k]-q[k])**2 for k in range(3))<1e-12 for q in crossing):
                crossing.append(a)
    if len(crossing)>=3 and 0<progress<1:
        center = _centroid(crossing)
        u = _norm(tuple(crossing[0][i]-center[i] for i in range(3)))
        v = cross(axis,u)
        crossing.sort(key=lambda p:math.atan2(_dot(p,v),_dot(p,u)))
        for sign in (1,-1):
            result.append(surface(crossing,"#151515","cap",tuple(c*sign for c in axis)))
    return tuple(result)
