"""A geometric Megaminx simulator. Cuts, stickers and moves share one mesh.

The dodecahedron is the intersection of twelve unit face planes. Cutting
each face by its five neighbours produces its centre, five edges and five
corners. Move permutations follow the geometry, rather than hand-written
colour substitutions. Pochmann R++/D++ follow WCA Article 12d.
"""
import math
import re
from functools import lru_cache
from itertools import combinations
from .puzzles import _dot, _norm, _rotate, _centroid


def cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def clip(points, normal, boundary, greater=False):
    """Clip a convex polygon against a plane, preserving its winding."""
    result = []
    for a,b in zip(points,points[1:]+points[:1]):
        da,db = _dot(a,normal)-boundary,_dot(b,normal)-boundary
        inside_a = da >= -1e-9 if greater else da <= 1e-9
        inside_b = db >= -1e-9 if greater else db <= 1e-9
        if inside_a:
            result.append(a)
        if inside_a != inside_b:
            t = da/(da-db)
            result.append(tuple(a[k]+t*(b[k]-a[k]) for k in range(3)))
    # Plane vertices can occur twice; keeping them corrupts normals.
    clean = []
    for point in result:
        if not clean or sum((a-b)**2 for a,b in zip(clean[-1],point)) > 1e-16:
            clean.append(point)
    if len(clean)>1 and sum((a-b)**2 for a,b in zip(clean[0],clean[-1])) < 1e-16:
        clean.pop()
    return clean if len(clean)>=3 else []


@lru_cache(maxsize=1)
def geometry():
    phi = (1+math.sqrt(5))/2
    raw = [_norm(p) for a in (-1,1) for b in (-1,1)
           for p in ((0,a,b*phi),(a,b*phi,0),(a*phi,0,b))]
    up = raw[0]
    front = max((p for p in raw if .4<_dot(up,p)<.5),key=lambda p:p[0])
    z = _norm(tuple(front[i]-_dot(front,up)*up[i] for i in range(3)))
    x = cross(up,z)
    normals = [(_dot(p,x),_dot(p,up),_dot(p,z)) for p in raw]
    top = max(normals,key=lambda p:p[1])
    ring = sorted((p for p in normals if .4<p[1]<.5),key=lambda p:math.atan2(p[0],p[2]))
    # Front is zero azimuth, with right/left adjacent to it.
    f = min(range(5),key=lambda i:abs(math.atan2(ring[i][0],ring[i][2])))
    ring = ring[f:]+ring[:f]
    named = {"U":top,"F":ring[0],"R":ring[1],"BR":ring[2],"BL":ring[3],"L":ring[4]}
    named.update({"D":tuple(-c for c in top)})
    remaining = [p for p in normals if p not in named.values()]
    for name,normal in zip(("A","C","E","I","BF"),remaining):
        named[name] = normal
    colors = dict(zip(named,("#ffffff","#00b050","#e8231e","#1e5cff","#a552c7","#ff8a00",
                             "#ffd500","#70d5df","#f49ac2","#b0b0b0","#82c95b","#b9a16a")))
    vertices = []
    for a,b,c in combinations(normals,3):
        determinant = _dot(a,cross(b,c))
        if abs(determinant)<1e-8:
            continue
        bc,ca,ab = cross(b,c),cross(c,a),cross(a,b)
        p = tuple((bc[i]+ca[i]+ab[i])/determinant for i in range(3))
        if all(_dot(p,n)<=1+1e-7 for n in normals) and not any(sum((p[i]-q[i])**2 for i in range(3))<1e-12 for q in vertices):
            vertices.append(p)
    stickers, face_names = [], []
    cut = .72
    for name,normal in named.items():
        face = [p for p in vertices if abs(_dot(p,normal)-1)<1e-7]
        u = _norm(tuple(face[0][i]-normal[i] for i in range(3)))
        v = cross(normal,u)
        face.sort(key=lambda p:math.atan2(_dot(p,v),_dot(p,u)))
        pieces = [face]
        for neighbour in normals:
            if not .4<_dot(normal,neighbour)<.5:
                continue
            divided = []
            for polygon in pieces:
                divided.extend(part for part in (clip(polygon,neighbour,cut),clip(polygon,neighbour,cut,True)) if part)
            pieces = divided
        if len(pieces)!=11:
            raise ValueError("Invalid Megaminx face geometry")
        for polygon in pieces:
            stickers.append((tuple(polygon),colors[name],normal))
            face_names.append(name)
    return tuple(stickers),named,cut,tuple(face_names)


def move_spec(token):
    _stickers,normals,cut,_names = geometry()
    rotation = re.fullmatch(r"y([2-4]?)(\'?)",token)
    if rotation:
        amount = int(rotation[1] or 1)*(-1 if rotation[2] else 1)
        return normals["U"],-2,False,-amount*math.tau/5
    if token in ("R++","R--","D++","D--"):
        axis = normals["L" if token[0]=="R" else "U"]
        return axis,cut,True,(1 if token.endswith("++") else -1)*4*math.pi/5
    match = re.fullmatch(r"(BR|BL|BF|[UFRLDACEI])([2-4]?)(\'?)",token)
    if not match or match[1] not in normals:
        raise ValueError("Unsupported Megaminx move: "+token)
    amount = int(match[2] or 1)*(-1 if match[3] else 1)
    return normals[match[1]],cut,False,-amount*2*math.pi/5


@lru_cache(maxsize=96)
def permutation(token):
    stickers,_normals,_cut,_names = geometry()
    axis,threshold,complement,angle = move_spec(token)
    centers = [_centroid(s[0]) for s in stickers]
    result = list(range(len(stickers)))
    for index,(center,sticker) in enumerate(zip(centers,stickers)):
        selected = _dot(center,axis)<threshold-1e-8 if complement else _dot(center,axis)>threshold+1e-8
        if not selected:
            continue
        target = _rotate(center,axis,angle)
        normal = _rotate(sticker[2],axis,angle)
        destination = min(range(len(stickers)),key=lambda j:sum((target[k]-centers[j][k])**2+(normal[k]-stickers[j][2][k])**2 for k in range(3)))
        error = sum((target[k]-centers[destination][k])**2 for k in range(3))
        if error>1e-10:
            raise ValueError("Megaminx move does not preserve sticker geometry")
        result[index] = destination
    if len(set(result))!=len(result):
        raise ValueError("Megaminx move is not a permutation")
    return tuple(result)


def state(alg=""):
    colors = [s[1] for s in geometry()[0]]
    for token in alg.split():
        new = list(colors)
        for src,dst in enumerate(permutation(token)):
            new[dst] = colors[src]
        colors = new
    return tuple(colors)
