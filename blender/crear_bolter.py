# -*- coding: utf-8 -*-
"""
UltramarineGun — construye el bólter en Blender desde cero.

Ejecutar (desde la carpeta del proyecto):
  blender --background --factory-startup --python blender/crear_bolter.py

Qué hace, en orden:
  1. Materiales procedurales (metal gastado, pintura ultramar, oro, empuñadura).
  2. Modelado por perfiles: cada pieza es un "perfil" 2D (vista lateral) que se
     extruye en grosor. Así se modelan muchas armas de juego: primero la silueta.
  3. Biseles (bevel) para que los cantos atrapen la luz.
  4. Agrupa piezas: Cuerpo (fijo), Cargador, Palanca y Gatillo (se animan).
  5. Horneado (bake) de texturas: los materiales procedurales se convierten en
     imágenes PNG, porque Godot no entiende los nodos de Blender.
  6. Animaciones: Disparo, Recarga y Gatillo_vacio (pistas NLA).
  7. Guarda el .blend, exporta UltramarineGun.glb y renderiza vistas previas.

Ejes: X = hacia la boca del cañón, Z = arriba, Y = grosor (el lado -Y es el
que verá la cámara en la tablet). Las medidas del modelo se escriben en cm.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Euler

S = 0.01                       # 1 unidad de perfil = 1 cm
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_TEX = os.path.join(RAIZ, "blender", "texturas")
DIR_FOTOS = os.path.join(RAIZ, "blender", "texturas_descargas")   # materiales CC0 de ambientCG
DIR_EXP = os.path.join(RAIZ, "godot", "assets", "modelos")   # el .glb va directo al juego
DIR_REN = os.path.join(RAIZ, "renders")
FPS = 60
OCULTO = 0.0001                # "escala cero" segura: invisible pero con rotación válida

# ---------------------------------------------------------------------------
# Utilidades de escena
# ---------------------------------------------------------------------------
def limpiar_escena():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                bpy.data.actions, bpy.data.cameras, bpy.data.lights):
        for b in list(col):
            col.remove(b)

def enlazar(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob

def nuevo_objeto(nombre, bm, mat=None):
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me); bm.free()
    if mat: me.materials.append(mat)
    return enlazar(bpy.data.objects.new(nombre, me))

def prisma(nombre, pts, y0, y1, mat, bisel=0.25):
    """Extruye un perfil 2D (x, z en cm) entre y0 e y1 (cm)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x * S, y0 * S, z * S)) for x, z in pts]
    cara = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[cara])
    nuevos = [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, (y1 - y0) * S, 0), verts=nuevos)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = nuevo_objeto(nombre, bm, mat)
    if bisel: biselar(ob, bisel)
    return ob

def caja(nombre, x0, x1, z0, z1, y0, y1, mat, bisel=0.25):
    return prisma(nombre, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], y0, y1, mat, bisel)

def cilindro(nombre, centro, radio, largo, eje, mat, seg=40, bisel=0.15):
    """Cilindro (cm). eje: 'X', 'Y' o 'Z'."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=radio * S,
                          radius2=radio * S, depth=largo * S)
    rot = {"X": Matrix.Rotation(math.radians(90), 4, "Y"),
           "Y": Matrix.Rotation(math.radians(90), 4, "X"),
           "Z": Matrix.Identity(4)}[eje]
    bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(centro) * S, verts=bm.verts)
    ob = nuevo_objeto(nombre, bm, mat)
    if bisel: biselar(ob, bisel)
    return ob

def biselar(ob, ancho_cm, seg=2):
    m = ob.modifiers.new("Bisel", "BEVEL")
    m.width = ancho_cm * S
    m.segments = seg
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(40)
    m.use_clamp_overlap = True

def restar(ob, cortador):
    m = ob.modifiers.new("Corte", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = cortador
    # El bisel debe ir DESPUÉS del corte para biselar también los agujeros.
    for mod in list(ob.modifiers):
        if mod.type == "BEVEL":
            ob.modifiers.move(list(ob.modifiers).index(mod), len(ob.modifiers) - 1)

def aplicar_modificadores(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    viejo = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(viejo)
    me.name = ob.name
    me.set_sharp_from_angle(angle=math.radians(40))   # suave en curvas, duro en cantos

def mover_origen(ob, punto_cm):
    p = Vector(punto_cm) * S
    ob.data.transform(Matrix.Translation(-p))
    ob.location = p

def unir(nombre, objetos):
    # Al unir, Blender solo conserva los modificadores del objeto activo:
    # por eso se aplican antes los biseles de cada pieza.
    for ob in objetos:
        if ob.modifiers:
            aplicar_modificadores(ob)
    for o in bpy.context.view_layer.objects: o.select_set(False)
    for ob in objetos: ob.select_set(True)
    destino = objetos[0]
    bpy.context.view_layer.objects.active = destino
    with bpy.context.temp_override(active_object=destino, object=destino,
                                   selected_objects=objetos,
                                   selected_editable_objects=objetos):
        bpy.ops.object.join()
    destino.name = nombre
    destino.data.name = nombre
    return destino

def espejo_y(pts_y0, pts_y1):
    """Devuelve el rango de grosor del lado contrario (+Y)."""
    return (-pts_y1, -pts_y0)

# ---------------------------------------------------------------------------
# Materiales procedurales (capas: base + desgaste en cantos + suciedad)
# ---------------------------------------------------------------------------
def _mix(nt, tipo, fac, a, b, blend="MIX"):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = tipo
    n.blend_type = blend
    if tipo == "RGBA":
        ia, ib, out = 6, 7, 2
    else:
        ia, ib, out = 2, 3, 0
    for idx, v in ((0, fac), (ia, a), (ib, b)):
        if isinstance(v, (int, float, tuple)):
            n.inputs[idx].default_value = v if not isinstance(v, tuple) else (*v, 1.0) if len(v) == 3 else v
        else:
            nt.links.new(v, n.inputs[idx])
    return n.outputs[out]

def material_capas(nombre, base, base_r, base_m, gasto, gasto_r, gasto_m,
                   desgaste=1.0, suciedad=0.6, escala_ruido=35.0,
                   foto=None, tinte=(1, 1, 1), foto_gasto=None, tinte_gasto=(1, 1, 1),
                   foto_astillas=None, mugre_foto=0.5, escala_foto=3.0, color_de_foto=True):
    """Material por capas. Con `foto` usa un material ESCANEADO (ambientCG) como base:
    su color (teñido con `tinte`), su rugosidad y su relieve. `foto_astillas` aporta un
    mapa real de dónde se saltó la pintura; `foto_gasto` es el metal que queda al descubierto."""
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    L = nt.links.new
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    L(bsdf.outputs[0], out.inputs[0])

    coord = nt.nodes.new("ShaderNodeTexCoord")
    ruido = nt.nodes.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = escala_ruido
    ruido.inputs["Detail"].default_value = 10
    ruido.inputs["Roughness"].default_value = 0.65
    L(coord.outputs["Object"], ruido.inputs["Vector"])

    # Proyección "caja" (triplanar): la foto se proyecta desde los 3 ejes y se mezcla en
    # las esquinas, así no hace falta preocuparse por cómo quedaron las UV.
    def tex_foto(asset, mapa, color=True, escala=escala_foto):
        ruta = os.path.join(DIR_FOTOS, asset, f"{asset}_1K-JPG_{mapa}.jpg")
        img = bpy.data.images.load(ruta, check_existing=True)
        if not color:
            img.colorspace_settings.name = "Non-Color"
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (escala,) * 3
        L(coord.outputs["Object"], mp.inputs["Vector"])
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        n.projection = "BOX"
        n.projection_blend = 0.3
        L(mp.outputs[0], n.inputs["Vector"])
        return n.outputs["Color"]

    def teñir(sock, t):
        return _mix(nt, "RGBA", 1.0, sock, t, blend="MULTIPLY")

    base_sock = teñir(tex_foto(foto, "Color"), tinte) if foto and color_de_foto else base
    gasto_sock = teñir(tex_foto(foto_gasto, "Color", escala=escala_foto * 1.7), tinte_gasto) if foto_gasto else gasto
    foto_rug = tex_foto(foto, "Roughness", False) if foto else None
    foto_alto = tex_foto(foto, "Displacement", False) if foto else None
    mugre_mask = tex_foto("SurfaceImperfections017", "Opacity", False, escala=escala_foto * 0.6)

    # Máscara de cantos: compara la normal real con la normal "biselada".
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = 0.004
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    L(geo.outputs["Normal"], dot.inputs[0]); L(bev.outputs[0], dot.inputs[1])
    canto = nt.nodes.new("ShaderNodeMapRange")
    canto.inputs["From Min"].default_value = 0.92
    canto.inputs["From Max"].default_value = 0.995
    canto.inputs["To Min"].default_value = 1.0
    canto.inputs["To Max"].default_value = 0.0
    L(dot.outputs["Value"], canto.inputs["Value"])

    # desgaste = canto*0.8 + ruido*0.5, umbralizado -> astillas irregulares
    suma = nt.nodes.new("ShaderNodeMath"); suma.operation = "MULTIPLY_ADD"
    L(canto.outputs[0], suma.inputs[0]); suma.inputs[1].default_value = 0.8
    mr = nt.nodes.new("ShaderNodeMath"); mr.operation = "MULTIPLY"
    L(ruido.outputs["Fac"], mr.inputs[0]); mr.inputs[1].default_value = 0.5
    L(mr.outputs[0], suma.inputs[2])
    mascara = nt.nodes.new("ShaderNodeMapRange")
    mascara.inputs["From Min"].default_value = 1.02 - 0.25 * desgaste
    mascara.inputs["From Max"].default_value = 1.08 - 0.25 * desgaste
    L(suma.outputs[0], mascara.inputs["Value"])
    m = mascara.outputs[0]

    # Suciedad en rincones (oclusión ambiental)
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 0.025
    sucio = _mix(nt, "FLOAT", suciedad, 1.0, ao.outputs["AO"])

    # Variación de rugosidad (rayones suaves)
    rayas = nt.nodes.new("ShaderNodeTexNoise")
    rayas.inputs["Scale"].default_value = 120
    rayas.inputs["Detail"].default_value = 4
    mapeo = nt.nodes.new("ShaderNodeMapping")
    mapeo.inputs["Scale"].default_value = (1, 1, 18)
    L(coord.outputs["Object"], mapeo.inputs["Vector"])
    L(mapeo.outputs[0], rayas.inputs["Vector"])
    var_r = nt.nodes.new("ShaderNodeMath"); var_r.operation = "MULTIPLY_ADD"
    L(rayas.outputs["Fac"], var_r.inputs[0]); var_r.inputs[1].default_value = 0.25
    var_r.inputs[2].default_value = base_r - 0.12

    # Rayones finos: ruido muy estirado y umbral estrecho -> líneas sueltas
    def rayon(escala, estiramiento, umbral):
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = estiramiento
        mp.inputs["Rotation"].default_value = (0.3, 0.5, 0.2)
        L(coord.outputs["Object"], mp.inputs["Vector"])
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = escala
        nz.inputs["Detail"].default_value = 2
        L(mp.outputs[0], nz.inputs["Vector"])
        mr2 = nt.nodes.new("ShaderNodeMapRange")
        mr2.inputs["From Min"].default_value = umbral
        mr2.inputs["From Max"].default_value = umbral + 0.012
        L(nz.outputs["Fac"], mr2.inputs["Value"])
        return mr2.outputs[0]
    r1 = rayon(18, (1, 1, 110), 0.76)
    r2 = rayon(24, (110, 1, 1), 0.78)
    rayas_max = nt.nodes.new("ShaderNodeMath"); rayas_max.operation = "MAXIMUM"
    L(r1, rayas_max.inputs[0]); L(r2, rayas_max.inputs[1])
    rayas_f = nt.nodes.new("ShaderNodeMath"); rayas_f.operation = "MULTIPLY"
    L(rayas_max.outputs[0], rayas_f.inputs[0]); rayas_f.inputs[1].default_value = 0.45 * desgaste
    total = nt.nodes.new("ShaderNodeMath"); total.operation = "MAXIMUM"
    L(m, total.inputs[0]); L(rayas_f.outputs[0], total.inputs[1])
    m = total.outputs[0]
    if foto_astillas:
        # Astillas y rayones REALES de la foto (mapa de metalicidad = donde se ve el metal)
        ast = tex_foto(foto_astillas, "Metalness", False, escala=escala_foto * 1.3)
        astm = nt.nodes.new("ShaderNodeMath"); astm.operation = "MULTIPLY"
        L(ast, astm.inputs[0]); astm.inputs[1].default_value = 1.2 * desgaste
        tot2 = nt.nodes.new("ShaderNodeMath"); tot2.operation = "MAXIMUM"; tot2.use_clamp = True
        L(m, tot2.inputs[0]); L(astm.outputs[0], tot2.inputs[1])
        m = tot2.outputs[0]

    # Mugre a gran escala: manchas que oscurecen un poco la superficie
    mugre_n = nt.nodes.new("ShaderNodeTexNoise")
    mugre_n.inputs["Scale"].default_value = 4.0
    mugre_n.inputs["Detail"].default_value = 6
    L(coord.outputs["Object"], mugre_n.inputs["Vector"])
    mugre = nt.nodes.new("ShaderNodeMapRange")
    mugre.inputs["From Min"].default_value = 0.35
    mugre.inputs["From Max"].default_value = 0.7
    mugre.inputs["To Min"].default_value = 0.62
    mugre.inputs["To Max"].default_value = 1.0
    L(mugre_n.outputs["Fac"], mugre.inputs["Value"])

    color = _mix(nt, "RGBA", m, base_sock, gasto_sock)
    albedo = _mix(nt, "RGBA", 1.0, color, sucio, blend="MULTIPLY")
    albedo = _mix(nt, "RGBA", 1.0, albedo, mugre.outputs[0], blend="MULTIPLY")
    # Mugre escaneada: manchas y huellas que oscurecen y hacen más mate la superficie
    mf = nt.nodes.new("ShaderNodeMath"); mf.operation = "MULTIPLY"
    L(mugre_mask, mf.inputs[0]); mf.inputs[1].default_value = mugre_foto
    albedo = _mix(nt, "RGBA", mf.outputs[0], albedo, (0.035, 0.028, 0.022))
    rug_base = var_r.outputs[0]
    if foto_rug:
        # rugosidad de la foto, recentrada alrededor de la rugosidad elegida
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["To Min"].default_value = max(0.05, base_r - 0.18)
        rr.inputs["To Max"].default_value = min(1.0, base_r + 0.22)
        L(foto_rug, rr.inputs["Value"])
        rug_base = rr.outputs[0]
    rug_m = nt.nodes.new("ShaderNodeMath"); rug_m.operation = "MULTIPLY_ADD"; rug_m.use_clamp = True
    L(mf.outputs[0], rug_m.inputs[0]); rug_m.inputs[1].default_value = 0.35
    L(rug_base, rug_m.inputs[2])
    rug = _mix(nt, "FLOAT", m, rug_m.outputs[0], gasto_r)
    met = _mix(nt, "FLOAT", m, base_m, gasto_m)
    L(albedo, bsdf.inputs["Base Color"])
    L(rug, bsdf.inputs["Roughness"])
    L(met, bsdf.inputs["Metallic"])

    # Relieve: metal martillado + la pintura más alta que donde se saltó + rayones hundidos
    martillo = nt.nodes.new("ShaderNodeTexNoise")
    martillo.inputs["Scale"].default_value = 220
    martillo.inputs["Detail"].default_value = 1
    L(coord.outputs["Object"], martillo.inputs["Vector"])
    alto = nt.nodes.new("ShaderNodeMath"); alto.operation = "MULTIPLY_ADD"
    L(martillo.outputs["Fac"], alto.inputs[0]); alto.inputs[1].default_value = 0.12
    resta = nt.nodes.new("ShaderNodeMath"); resta.operation = "SUBTRACT"
    resta.inputs[0].default_value = 1.0; L(m, resta.inputs[1])
    L(resta.outputs[0], alto.inputs[2])
    alto_final = alto
    if foto_alto:
        # relieve escaneado (rayones reales) sumado al de la pintura saltada
        af = nt.nodes.new("ShaderNodeMath"); af.operation = "MULTIPLY_ADD"
        L(foto_alto, af.inputs[0]); af.inputs[1].default_value = 0.5
        L(alto.outputs[0], af.inputs[2])
        alto_final = af
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.0004
    L(alto_final.outputs[0], bump.inputs["Height"])
    L(bump.outputs[0], bsdf.inputs["Normal"])

    # Guardamos qué salidas hay que hornear
    mat["salidas"] = True
    _SALIDAS[nombre] = {"albedo": albedo, "rough": rug, "metal": met}
    return mat

_SALIDAS = {}

def material_simple(nombre, color, rug, met):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rug
    b.inputs["Metallic"].default_value = met
    return mat

def crear_materiales():
    M = {}
    # Tintes calculados con el color promedio de cada foto, para llegar al color buscado:
    # Metal038 promedia ~(0.10, 0.125, 0.14) lineal -> x0.32 = acero pavonado oscuro.
    # Acero PLATEADO gastado (como la foto): x2.4 -> gris plata ~(0.25, 0.29, 0.31);
    # cantos casi blancos de tanto uso y rincones muy oscuros (suciedad 0.9).
    M["metal"] = material_capas("Metal_gastado", (0.25, 0.27, 0.29), 0.36, 1.0,
                                (0.75, 0.76, 0.78), 0.18, 1.0, desgaste=1.15, suciedad=0.9,
                                foto="Metal038", tinte=(1.95, 1.8, 1.72),
                                foto_gasto="Metal054A", tinte_gasto=(1.3, 1.3, 1.3), mugre_foto=0.5)
    # Pintura: color azul propio, pero rugosidad, relieve y ASTILLAS de la foto de pintura rayada.
    M["azul"] = material_capas("Pintura_ultramar", (0.012, 0.045, 0.30), 0.38, 0.0,
                               (0.50, 0.51, 0.53), 0.25, 1.0, desgaste=0.8,
                               foto="PaintedMetal004", color_de_foto=False, foto_astillas="PaintedMetal004",
                               foto_gasto="Metal054A", tinte_gasto=(0.88, 0.88, 0.9), mugre_foto=0.4)
    # Metal048A promedia ~(1.0, 0.75, 0.32) -> tinte para un oro viejo
    M["oro"] = material_capas("Oro_aquila", (0.80, 0.52, 0.16), 0.30, 1.0,
                              (1.0, 0.82, 0.45), 0.15, 1.0, desgaste=0.6, suciedad=0.85,
                              foto="Metal048A", tinte=(0.92, 0.76, 0.48), mugre_foto=0.3)
    M["grip"] = material_capas("Empunadura", (0.018, 0.018, 0.020), 0.70, 0.1,
                               (0.25, 0.25, 0.26), 0.45, 0.8, desgaste=0.6,
                               foto="Metal038", tinte=(1.25, 1.15, 1.1), mugre_foto=0.6, escala_foto=4.5)
    M["oscuro"] = material_capas("Interior_oscuro", (0.006, 0.006, 0.007), 0.6, 0.5,
                                 (0.05, 0.05, 0.05), 0.5, 0.5, desgaste=0.1, suciedad=1.0)
    M["laton"] = material_simple("Laton", (0.78, 0.55, 0.22), 0.28, 1.0)
    for mt in M.values():
        mt.use_fake_user = True
    return M

# ---------------------------------------------------------------------------
# Modelado
# ---------------------------------------------------------------------------
def aquila(prefijo, cx, cz, ext, sentido, mat, k=0.75):
    """Águila bicéfala en relieve, por capas (como un emblema metálico fundido).

    Se dibuja en "unidades de águila" (envergadura ±10) y se escala con k (cm por unidad).
    ext = cara exterior de la placa; sentido = -1 o +1 (hacia dónde sobresale).
    Cada capa tiene su propia altura de relieve: la banda del ala, las plumas largas
    (superpuestas, las de afuera encima), las plumas cortas, cabezas y el pecho, el más alto.
    """
    piezas = []

    def capa(h):                         # relieve de 0 a h cm sobre la placa
        a, b = ext, ext + sentido * h
        return min(a, b), max(a, b)

    def a_cm(pts, s=1):                  # unidades de águila -> cm (s = -1 espeja)
        out = [(cx + s * x * k, cz + z * k) for x, z in pts]
        return out[::-1] if s < 0 else out

    def pluma(raiz, ang, largo, ancho):
        a = math.radians(ang)
        d = Vector((math.sin(a), -math.cos(a)))      # hacia donde apunta la pluma
        p = Vector((math.cos(a), math.sin(a)))       # de lado a lado
        r = Vector(raiz)
        pts = [r - p * ancho / 2, r + p * ancho / 2, r + p * ancho * 0.33 + d * largo * 0.72,
               r + d * largo, r - p * ancho * 0.33 + d * largo * 0.72]
        return [(v.x, v.y) for v in pts]

    banda = [(0.9, 1.7), (3.0, 2.7), (5.5, 3.45), (8.0, 3.95), (10.0, 4.35),
             (9.7, 3.3), (7.5, 2.35), (5.0, 1.35), (2.6, 0.45), (1.0, -0.15)]
    b0, b1 = Vector((1.1, -0.1)), Vector((9.7, 3.25))   # borde inferior de la banda
    cuello = [(0.15, 1.2), (1.25, 1.25), (2.1, 3.0), (0.95, 3.25)]
    cabeza = [(1.65 + 0.9 * math.cos(t), 3.55 + 0.9 * math.sin(t)) for t in [i * math.tau / 20 for i in range(20)]]
    pico = [(2.2, 4.15), (3.5, 4.05), (4.05, 3.55), (4.0, 2.95), (3.55, 3.25), (2.4, 2.9)]   # pico ganchudo

    for s in (1, -1):
        lado = "D" if s > 0 else "I"
        # plumas largas (primarias): más largas y más abiertas hacia la punta del ala
        for i in range(6):
            t = 0.08 + i * 0.165
            raiz = b0 + (b1 - b0) * t + Vector((0, 0.3))
            piezas.append(prisma(f"{prefijo}_primaria{lado}{i}", a_cm(pluma(raiz, 18 + t * 38, 3.3 + 1.6 * t, 1.75), s),
                                 *capa(0.26 + 0.03 * i), mat, bisel=0.05))
        # plumas cortas (coberteras), encima de las largas
        for i in range(5):
            t = 0.16 + i * 0.17
            raiz = b0 + (b1 - b0) * t + Vector((0, 0.45))
            piezas.append(prisma(f"{prefijo}_cobertera{lado}{i}", a_cm(pluma(raiz, 15 + t * 30, 1.7, 1.3), s),
                                 *capa(0.45), mat, bisel=0.05))
        piezas.append(prisma(f"{prefijo}_banda{lado}", a_cm(banda, s), *capa(0.52), mat, bisel=0.06))
        piezas.append(prisma(f"{prefijo}_cuello{lado}", a_cm(cuello, s), *capa(0.55), mat, bisel=0.05))
        piezas.append(prisma(f"{prefijo}_cabeza{lado}", a_cm(cabeza, s), *capa(0.62), mat, bisel=0.07))
        piezas.append(prisma(f"{prefijo}_pico{lado}", a_cm(pico, s), *capa(0.5), mat, bisel=0.04))
        # cola en abanico
        piezas.append(prisma(f"{prefijo}_cola{lado}", a_cm(pluma((0.0, -2.2), 24, 2.1, 1.0), s),
                             *capa(0.4), mat, bisel=0.05))
    piezas.append(prisma(f"{prefijo}_cola_centro", a_cm(pluma((0.0, -2.2), 0, 2.2, 1.05)),
                         *capa(0.42), mat, bisel=0.05))
    # pecho: escudo grande + escudo interior más alto (dos niveles de relieve)
    pecho = [(-1.15, 1.7), (1.15, 1.7), (1.35, -0.4), (0.85, -2.1), (0.0, -2.7), (-0.85, -2.1), (-1.35, -0.4)]
    piezas.append(prisma(f"{prefijo}_pecho", a_cm(pecho), *capa(0.7), mat, bisel=0.08))
    interior = [(x * 0.55, -0.3 + (z + 0.3) * 0.55) for x, z in pecho]
    piezas.append(prisma(f"{prefijo}_pecho2", a_cm(interior), *capa(0.88), mat, bisel=0.06))
    return piezas


def modelar(M):
    cuerpo = []      # piezas fijas que se unirán en "Cuerpo"
    lados = [(-1, (-4.0, -3.5)), (1, (3.5, 4.0))]

    # Receptor (bloque principal)
    # Medidas tomadas de la foto de referencia (1 px de la foto ≈ 0,081 cm).
    # Parte de arriba plana (en la foto no hay escalón ni riel).
    receptor = prisma("Receptor", [(2, 22), (6, 31), (72, 31), (72, 27),
                                   (70, 26), (70, 17), (26, 17), (24, 14), (10, 14), (2, 17)],
                      -3.5, 3.5, M["metal"], bisel=0.35)
    cuerpo.append(receptor)
    # Bloques traseros escalonados (el arranque de la culata, abajo atrás)
    cuerpo.append(prisma("Culata", [(0.2, 12.2), (10.5, 12.2), (10.5, 19.5), (2.5, 20.5), (0.2, 18.0)],
                         -3.3, 3.3, M["metal"], bisel=0.35))
    cuerpo.append(prisma("Culata_bloque", [(0.8, 15.6), (6.8, 15.6), (6.8, 19.2), (0.8, 18.6)],
                         -3.75, 3.75, M["metal"], bisel=0.25))
    cuerpo.append(caja("Culata_junta", 0.6, 10.2, 14.6, 15.0, -3.42, 3.42, M["oscuro"], bisel=0))

    # Placas laterales azules + remaches + águila, en ambos lados
    placa_pts = [(11, 20), (14, 30), (66, 30), (66, 22), (30, 22), (28, 20)]
    for lado, (y0, y1) in lados:
        cuerpo.append(prisma(f"Placa{lado}", placa_pts, y0, y1, M["azul"], bisel=0.2))
        ext = y0 if lado < 0 else y1                     # cara exterior de la placa
        for (x, z) in [(15.5, 28.6), (64.6, 28.6), (64.6, 23.4), (31.5, 23.2)]:
            cuerpo.append(cilindro(f"Remache{lado}_{x}", (x, ext + lado * 0.12, z), 0.45, 0.35, "Y",
                                   M["metal"], seg=16, bisel=0.08))
        cuerpo += aquila(f"Aquila{lado}", 55.5, 25.7, ext, lado, M["oro"], k=0.75)
        # Tornillo grande con ranura, abajo en la placa (como en la foto)
        cuerpo.append(cilindro(f"Tornillo{lado}", (23.0, ext + lado * 0.2, 22.0), 1.45, 0.5, "Y",
                               M["metal"], seg=28, bisel=0.15))
        s0, s1 = (ext - 0.5, ext - 0.38) if lado < 0 else (ext + 0.38, ext + 0.5)
        cuerpo.append(prisma(f"Tornillo_ranura{lado}", [(21.9, 22.55), (22.2, 22.85), (24.1, 21.45), (23.8, 21.15)],
                             s0, s1, M["oscuro"], bisel=0))
        # Disco trasero con ranura de tornillo
        cuerpo.append(cilindro(f"Disco{lado}", (7, lado * 3.7, 22.5), 3.0, 0.6, "Y", M["metal"], bisel=0.12))
        r0, r1 = (-4.15, -3.95) if lado < 0 else (3.95, 4.15)
        cuerpo.append(caja(f"Ranura{lado}", 5.0, 9.0, 22.2, 22.8, r0, r1, M["oscuro"], bisel=0))

    # Ranura larga del cerrojo (lado visible) con marco y una guía metálica adentro
    cuerpo.append(caja("Marco_ventana", 19.4, 40.2, 24.9, 30.0, -4.25, -3.9, M["metal"], bisel=0.12))
    cuerpo.append(caja("Ventana", 20.2, 39.4, 25.6, 29.3, -4.4, -4.1, M["oscuro"], bisel=0.05))
    cuerpo.append(caja("Ventana_guia", 20.2, 39.4, 27.0, 27.9, -4.45, -4.15, M["metal"], bisel=0.08))

    # Miras: trasera alta y delantera en forma de aleta (la foto no tiene riel)
    cuerpo.append(prisma("Mira_trasera", [(16.5, 30.6), (22.6, 30.6), (22.0, 33.4), (17.2, 33.4)],
                         -1.6, 1.6, M["metal"], bisel=0.2))
    cuerpo.append(prisma("Mira_frontal", [(58.5, 30.6), (69.5, 30.6), (69.5, 34.3), (67.8, 34.3)],
                         -1.0, 1.0, M["metal"], bisel=0.2))

    # Guardamanos como en la foto: bloque alto de bordes redondeados, costillas SALIENTES abajo
    # y un panel rectangular hundido arriba.
    guarda = caja("Guardamanos", 46.0, 71.0, 6.6, 21.0, -3.6, 3.6, M["metal"], bisel=0)
    biselar(guarda, 1.3, seg=4)                       # bisel grande = bordes redondeados
    cuerpo.append(guarda)
    for i, x in enumerate([49.2, 53.2, 57.2, 61.2, 65.2, 69.0]):
        for lado in (-1, 1):
            y0, y1 = (-4.15, -3.2) if lado < 0 else (3.2, 4.15)
            costilla = caja(f"Costilla{i}{lado}", x - 0.85, x + 0.85, 7.6, 15.4, y0, y1, M["metal"], bisel=0)
            biselar(costilla, 0.45, seg=3)
            cuerpo.append(costilla)
    for lado in (-1, 1):
        f0, f1 = (-3.95, -3.4) if lado < 0 else (3.4, 3.95)
        cuerpo.append(caja(f"Panel_marco{lado}", 47.4, 69.6, 16.3, 20.0, f0, f1, M["metal"], bisel=0.2))
        p0, p1 = (-4.0, -3.7) if lado < 0 else (3.7, 4.0)
        cuerpo.append(caja(f"Panel_hundido{lado}", 48.1, 68.9, 16.9, 19.4, p0, p1, M["grip"], bisel=0.08))

    # Cañón superior (más grueso, con aro) y bocacha grande con ánima y puerto lateral
    cuerpo.append(cilindro("Canon", (73.0, 0, 26.0), 1.7, 6.0, "X", M["metal"], bisel=0.12))
    cuerpo.append(cilindro("Canon_aro", (75.4, 0, 26.0), 1.95, 0.8, "X", M["metal"], bisel=0.1))
    boca = cilindro("Bocacha", (75.5, 0, 15.5), 4.6, 9, "X", M["metal"], bisel=0.35)
    anima = cilindro("Cortador_anima", (78, 0, 15.5), 1.9, 8, "X", None, bisel=0)
    puerto = cilindro("Cortador_puerto", (77.3, 0, 15.5), 1.45, 12, "Y", None, bisel=0)
    restar(boca, anima); restar(boca, puerto)
    aplicar_modificadores(boca)
    bpy.data.objects.remove(anima, do_unlink=True); bpy.data.objects.remove(puerto, do_unlink=True)
    cuerpo.append(boca)
    cuerpo.append(cilindro("Anima_fondo", (74.15, 0, 15.5), 1.95, 0.3, "X", M["oscuro"], bisel=0))
    for i, x in enumerate([72.2, 74.0]):
        cuerpo.append(cilindro(f"Aro_boca{i}", (x, 0, 15.5), 4.85, 0.7, "X", M["oro"], bisel=0.1))
    # Bloque rectangular bajo la bocacha
    cuerpo.append(caja("Bloque_boca", 70.5, 77.6, 7.0, 11.2, -2.8, 2.8, M["metal"], bisel=0.35))

    # Empuñadura como en la foto: más inclinada hacia atrás, con 3 ANILLOS gruesos que la
    # rodean (salen más por delante, donde van los dedos) y un talón cruzado abajo.
    arriba, abajo = Vector((16.6, 14.6)), Vector((9.0, -4.6))   # eje de la empuñadura
    eje = (abajo - arriba)
    largo_eje = eje.length
    d = eje.normalized()
    pf = Vector((-d.y, d.x))                     # perpendicular hacia delante (+X)
    if pf.x < 0:
        pf = -pf
    def ep(t, off):                              # punto sobre el eje (t 0..1) desplazado "off"
        q = arriba + eje * t + pf * off
        return (q.x, q.y)
    medio = 4.6                                  # media anchura de la empuñadura
    # (21.8, 15.0) sube el canto de arriba hasta el receptor: sin él quedaba un hueco
    grip = prisma("Empunadura", [ep(0, -medio - 0.6), (21.8, 15.0), ep(0, medio + 0.4), ep(1, medio), ep(1, -medio)],
                  -2.6, 2.6, M["grip"], bisel=0)
    biselar(grip, 0.9, seg=3)
    cuerpo.append(grip)
    for i, t in enumerate((0.30, 0.52, 0.74)):
        dt = 0.85 / largo_eje
        anillo = prisma(f"Anillo_grip{i}", [ep(t - dt, -medio - 0.35), ep(t - dt, medio + 1.2),
                                             ep(t + dt, medio + 1.2), ep(t + dt, -medio - 0.35)],
                        -3.05, 3.05, M["grip"], bisel=0)
        biselar(anillo, 0.7, seg=4)
        cuerpo.append(anillo)
    talon = prisma("Talon", [ep(0.97, -medio - 1.0), ep(0.97, medio + 1.3), ep(1.06, medio + 1.4), ep(1.06, -medio - 1.1)],
                   -3.2, 3.2, M["metal"], bisel=0)
    biselar(talon, 0.35, seg=2)
    cuerpo.append(talon)

    # Guardamonte y pozo del cargador
    # (el guardamonte arranca dentro de la empuñadura nueva, que está más atrás)
    cuerpo.append(prisma("Guardamonte", [(19.5, 11), (20.0, 6.5), (31, 6.5), (31, 14), (29.5, 14),
                                         (29.5, 8), (21.8, 8), (21.3, 11)], -0.9, 0.9, M["metal"], bisel=0.15))
    # Caja del gatillo: une el gatillo al cuerpo (antes quedaba un hueco y el gatillo "flotaba").
    # Su base (z=12.6) queda por debajo del pivote del gatillo (z=13.8), que así nace de adentro.
    cuerpo.append(prisma("Caja_gatillo", [(21.5, 12.6), (30.5, 12.6), (30.5, 17.5), (26.5, 17.5), (24.2, 14.6), (21.5, 14.6)],
                         -1.6, 1.6, M["metal"], bisel=0.2))
    cuerpo.append(prisma("Pozo_cargador", [(30, 17), (45.8, 17), (45.8, 12), (30.5, 12)],
                         -3.6, 3.6, M["metal"], bisel=0.3))
    # Botón con estrías verticales (en la foto, delante de la empuñadura y bajo la placa)
    cuerpo.append(caja("Boton_estrias", 22.6, 25.6, 15.4, 19.7, -3.95, -3.4, M["metal"], bisel=0.15))
    for i in range(4):
        x = 23.05 + i * 0.7
        cuerpo.append(caja(f"Estria{i}", x, x + 0.35, 15.8, 19.3, -4.2, -3.9, M["metal"], bisel=0.06))

    # --- Piezas móviles -----------------------------------------------------
    gatillo = prisma("Gatillo", [(25.5, 14), (26.8, 14), (26.8, 12), (25.8, 9.5), (25.0, 9.8),
                                 (25.6, 12)], -0.5, 0.5, M["metal"], bisel=0.1)
    mover_origen(gatillo, (26.1, 0, 13.8))

    # Palanca del cerrojo en CUÑA (como la foto): sale de la ranura, con el frente inclinado
    cuña = prisma("Palanca", [(36.4, 25.4), (38.8, 25.4), (40.2, 30.6), (36.4, 30.6)],
                  -6.6, -3.9, M["metal"], bisel=0.3)
    vastago = caja("Palanca_vastago", 36.0, 39.0, 26.4, 28.6, -4.3, -3.6, M["metal"], bisel=0.1)
    palanca = unir("Palanca", [cuña, vastago])
    mover_origen(palanca, (37.8, 0, 27.75))

    # Cargador curvo tipo banana (como la foto): se genera desde una línea central.
    # c(t) = punto central; el ancho se aplica perpendicular a la curva.
    def centro(t):
        # más corto (24 cm) y con curva más suave que antes, como en la foto
        return Vector((38.0 + 9.0 * t ** 1.6, 12.0 - 24.0 * t))
    def normal(t):
        d = centro(min(1, t + 0.01)) - centro(max(0, t - 0.01))
        return Vector((-d.y, d.x)).normalized()          # apunta hacia delante (+X)
    def ancho(t):
        return 13.0 - 1.6 * t
    def borde(t, off):
        p = centro(t) + normal(t) * off       # Vector 2D: (x, z)
        return (p.x, p.y)
    N = 14
    frente = [borde(i / N, ancho(i / N) / 2) for i in range(N + 1)]
    atras = [borde(i / N, -ancho(i / N) / 2) for i in range(N + 1)]
    frente[0] = (frente[0][0], 12.0); atras[0] = (atras[0][0], 12.0)   # tapa superior plana
    # contorno: arriba-atrás -> todo el borde delantero -> sube por el borde trasero
    carg = [prisma("Cargador", [atras[0]] + frente + atras[:0:-1],
                   -3.3, 3.3, M["metal"], bisel=0.35)]
    # Base robusta con 4 dientes, orientada con la curva al final del cargador
    t1 = 1.0
    c1, n1 = centro(t1), normal(t1)
    tg = Vector((n1.y, -n1.x))                           # tangente hacia abajo
    def p(o_n, o_t):
        q = c1 + n1 * o_n + tg * o_t
        return (q.x, q.y)
    w = ancho(t1) / 2
    carg.append(prisma("Cargador_base", [p(-w - 0.9, -0.8), p(w + 0.9, -0.8), p(w + 0.6, 2.4), p(-w - 0.6, 2.4)],
                       -3.8, 3.8, M["metal"], bisel=0.3))
    for i in range(4):
        o = -w + 1.6 + i * (2 * w - 3.2) / 3
        carg.append(prisma(f"Cargador_diente{i}", [p(o - 0.75, 2.2), p(o + 0.75, 2.2), p(o + 0.6, 3.6), p(o - 0.6, 3.6)],
                           -3.3, 3.3, M["metal"], bisel=0.15))
    # Dos canales con nervio metálico siguiendo la curva, en ambas caras
    def tira(off, medio_ancho, t0=0.08, t1_=0.86, n=10):
        a = [borde(t0 + (t1_ - t0) * i / n, off - medio_ancho) for i in range(n + 1)]
        b = [borde(t0 + (t1_ - t0) * i / n, off + medio_ancho) for i in range(n + 1)]
        return a + b[::-1]
    for j, off in enumerate((-2.4, 2.4)):
        for lado in (-1, 1):
            c0, c1_ = (-3.42, -3.25) if lado < 0 else (3.25, 3.42)
            carg.append(prisma(f"Cargador_canal{j}{lado}", tira(off, 1.25), c0, c1_, M["oscuro"], bisel=0))
            n0, n1_ = (-3.75, -3.3) if lado < 0 else (3.3, 3.75)
            carg.append(prisma(f"Cargador_nervio{j}{lado}", tira(off, 0.5, 0.1, 0.84), n0, n1_, M["metal"], bisel=0.12))
    cargador = unir("Cargador", carg)
    mover_origen(cargador, (38, 0, 12))

    # Aplicar biseles y unir el cuerpo fijo
    for ob in cuerpo + [gatillo, palanca, cargador]:
        if ob.modifiers:
            aplicar_modificadores(ob)
        else:
            ob.data.set_sharp_from_angle(angle=math.radians(40))
    cuerpo_ob = unir("Cuerpo", cuerpo)
    return cuerpo_ob, cargador, palanca, gatillo

# ---------------------------------------------------------------------------
# Efectos: fogonazo (texturas generadas por código) y casquillo
# ---------------------------------------------------------------------------
def imagen_fogonazo(nombre, tam, funcion):
    img = bpy.data.images.new(nombre, tam, tam, alpha=True)
    px = [0.0] * (tam * tam * 4)
    for j in range(tam):
        for i in range(tam):
            r, g, b, a = funcion(i / (tam - 1), j / (tam - 1))
            k = (j * tam + i) * 4
            px[k:k + 4] = (r, g, b, a)
    img.pixels.foreach_set(px)
    img.filepath_raw = os.path.join(DIR_TEX, nombre + ".png")
    img.file_format = "PNG"
    img.save()
    return img

def _color_fuego(nucleo):
    # naranja -> blanco según cuán cerca del núcleo
    return (1.0, 0.42 + 0.58 * nucleo, 0.08 + 0.85 * nucleo)

def estrella(u, v):
    dx, dy = u * 2 - 1, v * 2 - 1
    r = math.hypot(dx, dy); th = math.atan2(dy, dx)
    puntas = 0.22 + 0.78 * abs(math.cos(3 * th)) ** 6
    nucleo = math.exp(-(r / 0.2) ** 2)
    punta = max(0.0, 1 - r / (0.95 * puntas)) ** 2
    a = min(1.0, nucleo + punta * 0.9)
    return (*_color_fuego(nucleo), a)

def llama(u, v):
    dy = abs(v * 2 - 1)
    ancho = 0.18 + 0.82 * (u ** 0.55)
    forma = max(0.0, 1 - dy / ancho) ** 1.6
    a = forma * (1 - u) ** 1.3 * min(1.0, u * 12)
    nucleo = max(0.0, 1 - dy / (ancho * 0.35)) * (1 - u)
    return (*_color_fuego(min(1, nucleo)), min(1.0, a * 1.4))

def material_fogonazo(nombre, img):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    b.inputs["Base Color"].default_value = (0, 0, 0, 1)
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 6.0
    nt.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False
    return mat

def plano(nombre, verts_cm, mat):
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(v) * S) for v in verts_cm]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new("UVMap")
    for loop, c in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop[uv].uv = c
    return nuevo_objeto(nombre, bm, mat)

def crear_efectos(M):
    img_e = imagen_fogonazo("fogonazo_frente", 256, estrella)
    img_l = imagen_fogonazo("fogonazo_lado", 256, llama)
    m_e = material_fogonazo("Fogonazo_frente", img_e)
    m_l = material_fogonazo("Fogonazo_lado", img_l)
    bx, bz, t = 80.2, 15.5, 7.0
    piezas = [plano("Fog_frente", [(bx, -t, bz - t), (bx, t, bz - t), (bx, t, bz + t), (bx, -t, bz + t)], m_e)]
    L, h = 24.0, 6.0
    piezas.append(plano("Fog_lado1", [(bx, 0, bz - h), (bx + L, 0, bz - h), (bx + L, 0, bz + h), (bx, 0, bz + h)], m_l))
    piezas.append(plano("Fog_lado2", [(bx, -h, bz), (bx + L, -h, bz), (bx + L, h, bz), (bx, h, bz)], m_l))
    fog = unir("Fogonazo", piezas)
    mover_origen(fog, (bx, 0, bz))
    fog.visible_shadow = False

    casq = cilindro("Casquillo", (0, 0, 0), 0.75, 2.6, "Y", M["laton"], seg=20, bisel=0.08)
    aplicar_modificadores(casq)
    casq.location = Vector((32, -5, 27)) * S
    return fog, casq

# ---------------------------------------------------------------------------
# Horneado de texturas
# ---------------------------------------------------------------------------
def desplegar_uv(ob):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")

def hornear(ob, tam, muestras):
    desplegar_uv(ob)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    resultado = {}
    for canal, es_color in (("albedo", True), ("rough", False), ("metal", False)):
        img = bpy.data.images.new(f"{ob.name}_{canal}", tam, tam, alpha=False)
        img.colorspace_settings.name = "sRGB" if es_color else "Non-Color"
        temporales = []
        for slot in ob.material_slots:
            mt = slot.material
            nt = mt.node_tree
            salida = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
            emi = nt.nodes.new("ShaderNodeEmission")
            src = _SALIDAS[mt.name][canal]
            nt.links.new(src, emi.inputs["Color"])
            nt.links.new(emi.outputs[0], salida.inputs["Surface"])
            tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
            nt.nodes.active = tex
            temporales.append((nt, emi, tex))
        sc.cycles.samples = muestras if canal == "albedo" else max(8, muestras // 4)
        for o in bpy.context.view_layer.objects: o.select_set(False)
        ob.select_set(True); bpy.context.view_layer.objects.active = ob
        bpy.ops.object.bake(type="EMIT", margin=8, use_clear=True)
        img.filepath_raw = os.path.join(DIR_TEX, f"{ob.name}_{canal}.png")
        img.file_format = "PNG"
        img.save()
        for nt, emi, tex in temporales:
            salida = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
            bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
            nt.nodes.remove(emi); nt.nodes.remove(tex)
            nt.links.new(bsdf.outputs[0], salida.inputs["Surface"])
        resultado[canal] = img
        print(f"  horneado {ob.name}_{canal} ({tam}px)")

    # Mapa de normales: guarda el relieve (rayones, martillado, astillas) en colores RGB
    img = bpy.data.images.new(f"{ob.name}_normal", tam, tam, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    temporales = []
    for slot in ob.material_slots:
        nt = slot.material.node_tree
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
        nt.nodes.active = tex
        temporales.append((nt, tex))
    sc.cycles.samples = 8
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=8, use_clear=True)
    img.filepath_raw = os.path.join(DIR_TEX, f"{ob.name}_normal.png")
    img.file_format = "PNG"
    img.save()
    for nt, tex in temporales:
        nt.nodes.remove(tex)
    resultado["normal"] = img
    print(f"  horneado {ob.name}_normal ({tam}px)")

    # Material final: solo imágenes (lo que Godot sí entiende)
    mat = bpy.data.materials.new(f"M_{ob.name}")
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    for canal, entrada in (("albedo", "Base Color"), ("rough", "Roughness"), ("metal", "Metallic")):
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = resultado[canal]
        nt.links.new(t.outputs["Color"], b.inputs[entrada])
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = resultado["normal"]
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    ob.data.materials.clear()
    ob.data.materials.append(mat)

# ---------------------------------------------------------------------------
# Animaciones (una pista NLA por animación y objeto)
# ---------------------------------------------------------------------------
def _fcurves(act):
    try:
        return list(act.fcurves)
    except Exception:
        cs = []
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    cs += list(cb.fcurves)
        return cs

def animar(ob, nombre, claves, interp="BEZIER"):
    """claves: lista de (frame, dict(loc=..., rot=(grados), esc=...)) en cm / grados."""
    ob.animation_data_create()
    base_loc = ob.location.copy()
    base_rot = ob.rotation_euler.copy()
    base_esc = ob.scale.copy()
    act = bpy.data.actions.new(f"{nombre}_{ob.name}")
    ob.animation_data.action = act
    for f, k in claves:
        ob.location = base_loc + Vector(k.get("loc", (0, 0, 0))) * S
        ob.rotation_euler = Euler([base_rot[i] + math.radians(k.get("rot", (0, 0, 0))[i]) for i in range(3)])
        e = max(k.get("esc", 1.0), OCULTO)   # escala 0 rompe la rotación en Godot
        ob.scale = (e, e, e)
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
        ob.keyframe_insert("scale", frame=f)
    for fc in _fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = interp
    pista = ob.animation_data.nla_tracks.new()
    pista.name = nombre
    pista.strips.new(nombre, 0, act)
    ob.animation_data.action = None
    ob.location, ob.rotation_euler, ob.scale = base_loc, base_rot, base_esc

def crear_animaciones(raiz, cargador, palanca, gatillo, fog, casq):
    R = {}
    # ---- Disparo (≈0,25 s): retroceso, fogonazo, ciclo del cerrojo, casquillo
    animar(raiz, "Disparo", [(0, {}), (2, dict(loc=(-2.2, 0, 0.4), rot=(0, -4.5, 0))),
                              (6, dict(loc=(-0.6, 0, 0.1), rot=(0, -1.2, 0))), (14, {})])
    animar(gatillo, "Disparo", [(0, {}), (1, dict(rot=(0, 14, 0))), (8, dict(rot=(0, 14, 0))), (12, {})])
    animar(palanca, "Disparo", [(0, {}), (2, dict(loc=(-3.5, 0, 0))), (5, {}), (14, {})])
    animar(fog, "Disparo", [(0, dict(esc=0.0)), (1, dict(esc=1.0, rot=(25, 0, 0))),
                            (2, dict(esc=1.3, rot=(25, 0, 0))), (3, dict(esc=0.55, rot=(25, 0, 0))),
                            (4, dict(esc=0.0)), (14, dict(esc=0.0))], interp="CONSTANT")
    animar(casq, "Disparo", [(0, dict(esc=0.0)), (1, dict(esc=1.0)),
                             (6, dict(loc=(-5, -9, 13), rot=(220, 90, 0))),
                             (14, dict(loc=(-12, -22, 2), rot=(600, 260, 0))),
                             (15, dict(esc=0.0, loc=(-12, -22, 2)))])
    # ---- Recarga (≈1,8 s)
    animar(raiz, "Recarga", [(0, {}), (14, dict(rot=(-14, -6, 0), loc=(0, 0, 1.5))),
                             (60, dict(rot=(-14, -6, 0), loc=(0, 0, 1.5))),
                             (63, dict(rot=(-15, -4.5, 0), loc=(0, 0, 2.2))),       # golpe al encajar
                             (70, dict(rot=(-8, -3, 0), loc=(0, 0, 1))),
                             (86, dict(rot=(-6, -2, 0))), (89, dict(rot=(-6, -4, 0), loc=(-0.8, 0, 0))),
                             (108, {})])
    animar(cargador, "Recarga", [(0, {}), (16, {}), (22, dict(loc=(0, 0, -1.2))),
                                 (36, dict(loc=(3, -2, -32), rot=(-10, 22, 0))),
                                 (37, dict(loc=(0, 0, -26), esc=1.0)),
                                 (52, dict(loc=(0, 0, -5), rot=(0, -6, 0))),
                                 (60, dict(loc=(0, 0, 0.4))), (62, {}), (108, {})])
    animar(palanca, "Recarga", [(0, {}), (72, {}), (80, dict(loc=(-6.2, 0, 0))),
                                (85, dict(loc=(-6.2, 0, 0))), (88, {}), (108, {})])
    # ---- Gatillo vacío (clic)
    animar(gatillo, "Gatillo_vacio", [(0, {}), (2, dict(rot=(0, 14, 0))), (10, {})])
    animar(raiz, "Gatillo_vacio", [(0, {}), (2, dict(rot=(0, -0.5, 0))), (10, {})])

def solo_pista(nombre):
    for ob in bpy.data.objects:
        if ob.animation_data:
            for p in ob.animation_data.nla_tracks:
                p.mute = (p.name != nombre)

def todas_las_pistas():
    for ob in bpy.data.objects:
        if ob.animation_data:
            for p in ob.animation_data.nla_tracks:
                p.mute = False

# ---------------------------------------------------------------------------
# Render de vistas previas
# ---------------------------------------------------------------------------
def preparar_render():
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    w = bpy.data.worlds.new("Mundo") if not sc.world else sc.world
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.012, 0.013, 0.017, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0

    def luz(nombre, tipo, pos, energia, color=(1, 1, 1), tam=0.6):
        ld = bpy.data.lights.new(nombre, tipo); ld.energy = energia; ld.color = color
        if tipo == "AREA": ld.size = tam
        ob = enlazar(bpy.data.objects.new(nombre, ld)); ob.location = pos
        mirar(ob, Vector((0.4, 0, 0.15)))
        return ob
    luz("Clave", "AREA", (0.1, -1.0, 1.0), 45, tam=0.5)
    luz("Contra", "AREA", (1.0, 0.9, 0.7), 60, (0.6, 0.75, 1.0), tam=0.4)
    luz("Relleno", "AREA", (-0.6, -0.8, -0.2), 8, (1.0, 0.85, 0.7), 1.2)
    cam = enlazar(bpy.data.objects.new("Camara", bpy.data.cameras.new("Camara")))
    sc.camera = cam
    return cam

def mirar(ob, objetivo):
    d = objetivo - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

def renderizar(cam, archivo, pos, objetivo, lente=50, frame=0, pista=None):
    sc = bpy.context.scene
    cam.location = Vector(pos); cam.data.lens = lente
    mirar(cam, Vector(objetivo))
    # Sin pista: todas las animaciones empiezan en reposo, así que el frame 0 es la pose de reposo.
    todas_las_pistas(); sc.frame_set(0)          # volver a la pose de reposo
    if pista: solo_pista(pista)
    else: frame = 0
    sc.frame_set(frame)
    sc.render.filepath = os.path.join(DIR_REN, archivo)
    sc.render.use_stamp_filename = False   # no grabar la ruta del .blend en los metadatos del PNG
    bpy.ops.render.render(write_still=True)
    print("  render", archivo)

# ---------------------------------------------------------------------------
def main():
    os.makedirs(DIR_TEX, exist_ok=True); os.makedirs(DIR_EXP, exist_ok=True); os.makedirs(DIR_REN, exist_ok=True)
    limpiar_escena()
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.unit_settings.system = "METRIC"
    print("1) materiales"); M = crear_materiales()
    print("2) modelado"); cuerpo, cargador, palanca, gatillo = modelar(M)
    print("3) efectos"); fog, casq = crear_efectos(M)

    print("4) horneado de texturas (tarda unos minutos)")
    muestras = int(os.environ.get("UG_MUESTRAS", "48"))
    hornear(cuerpo, 2048, muestras)
    hornear(cargador, 1024, muestras)
    hornear(palanca, 512, muestras)
    hornear(gatillo, 256, muestras)

    # Raíz: el arma gira desde la empuñadura (como en la mano)
    raiz = enlazar(bpy.data.objects.new("UltramarineGun", None))
    raiz.empty_display_type = "ARROWS"; raiz.empty_display_size = 0.1
    raiz.location = Vector((17, 0, 15)) * S
    bpy.context.view_layer.update()
    for ob in (cuerpo, cargador, palanca, gatillo, fog, casq):
        mw = ob.matrix_world.copy()
        ob.parent = raiz
        ob.matrix_parent_inverse = raiz.matrix_world.inverted()
        ob.matrix_world = mw
    # En reposo el fogonazo y el casquillo no se ven (escala 0); la animación los muestra.
    fog.scale = (OCULTO,) * 3
    casq.scale = (OCULTO,) * 3

    print("5) animaciones"); crear_animaciones(raiz, cargador, palanca, gatillo, fog, casq)
    sc.frame_start, sc.frame_end = 0, 108
    todas_las_pistas()
    sc.frame_set(0)   # pose de reposo: fogonazo y casquillo ocultos al importar en Godot

    print("6) guardar y exportar")
    for o in bpy.context.view_layer.objects: o.select_set(False)
    for ob in (raiz, cuerpo, cargador, palanca, gatillo, fog, casq): ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(DIR_EXP, "UltramarineGun.glb"),
                              export_format="GLB", use_selection=True,
                              export_animation_mode="NLA_TRACKS", export_apply=True,
                              export_yup=True, export_cameras=False, export_lights=False)

    print("7) vistas previas")
    cam = preparar_render()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RAIZ, "blender", "UltramarineGun.blend"))
    renderizar(cam, "01_lateral.png", (0.40, -1.45, 0.08), (0.40, 0, 0.07), lente=50)
    renderizar(cam, "02_tres_cuartos.png", (1.15, -0.95, 0.40), (0.38, 0, 0.06), lente=45)
    renderizar(cam, "03_disparo.png", (1.15, -0.95, 0.40), (0.40, 0, 0.08), lente=45, frame=2, pista="Disparo")
    renderizar(cam, "04_recarga_cargador_fuera.png", (0.40, -1.55, 0.10), (0.40, 0, 0.06), lente=40, frame=30, pista="Recarga")
    renderizar(cam, "05_recarga_palanca.png", (0.30, -0.70, 0.35), (0.38, 0, 0.24), lente=50, frame=82, pista="Recarga")
    renderizar(cam, "06_detalle_aquila.png", (0.55, -0.42, 0.30), (0.56, 0, 0.25), lente=60)
    todas_las_pistas()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RAIZ, "blender", "UltramarineGun.blend"))
    print("LISTO")

if __name__ == "__main__":
    main()
