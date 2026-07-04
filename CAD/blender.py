import bpy
import math
import re
from mathutils import Vector

# Paths (absolute)
GRAPH_HTML_PATH = r"C:\xampp\htdocs\research\gearbox_connection_graph.html"

# Settings
COLLECTION_NAME = "Exploded_Gearbox"
EXPLODE_AXIS = Vector((0, 1, 0))   # +Y = right
EXPLODE_AMOUNT = 70.0

FRAME_ASSEMBLED = 1
FRAME_EXPLODED = 40

# Clear scene (NO bpy.ops select_all)
def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for datablock in (bpy.data.meshes, bpy.data.materials, bpy.data.textures, bpy.data.images):
        for x in list(datablock):
            if x.users == 0:
                datablock.remove(x)

clear_scene()

# Collection helper
def ensure_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col

col = ensure_collection(COLLECTION_NAME)

def add_to_collection(obj, target_col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    target_col.objects.link(obj)

# Materials (unique per code)
mat_cache = {}

def hsl_to_rgba(h, s, l, a=1.0):
    import colorsys
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r, g, b, a)

def material_for_code(code):
    if code in mat_cache:
        return mat_cache[code]
    h = (code * 0.08) % 1.0
    rgba = hsl_to_rgba(h, 0.75, 0.55, 1.0)

    mat = bpy.data.materials.get(f"MAT_{code:02d}")
    if mat is None:
        mat = bpy.data.materials.new(name=f"MAT_{code:02d}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
            bsdf.inputs["Roughness"].default_value = 0.45
            bsdf.inputs["Metallic"].default_value = 0.0

    mat_cache[code] = mat
    return mat

def assign_material(obj, code):
    mat = material_for_code(code)
    if obj.data is None:
        return
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

# Graph HTML parsing: disassemblyStep
def parse_disassembly_steps_from_graph_html(path):
    txt = open(path, "r", encoding="utf-8").read()
    m = re.search(r"const\s+disassemblyStep\s*=\s*\{([^}]*)\}\s*;", txt, flags=re.S)
    if not m:
        raise RuntimeError("Could not find disassemblyStep in gearbox_connection_graph.html")
    body = m.group(1)
    pairs = re.findall(r"([A-Za-z0-9]+)\s*:\s*(\d+)", body)
    steps = {k: int(v) for (k, v) in pairs}
    if not steps:
        raise RuntimeError("Parsed disassemblyStep but got empty result.")
    return steps

disassembly_step = parse_disassembly_steps_from_graph_html(GRAPH_HTML_PATH)
MAX_STEP = max(disassembly_step.values())

# Hardcoded qty (from gearbox.xlsx) — no openpyxl needed
PART_QTY = {
    1:1, 2:4, 3:2, 4:1, 5:1, 6:1, 7:1, 8:1, 9:1, 10:1,
    11:3, 12:1, 13:1, 14:1, 15:1,
    16:8, 17:2, 18:4, 19:24, 20:1,
    21:1, 22:1, 23:1, 24:1
}

# Node -> part code mapping (from gearboox.xlsx)
node_to_part = {
    # Fasteners
    "F1":16, "F2":17, "F3SX":19, "F3DX":19, "F4":21, "F5":22, "F6":23, "F7":24,
    # Components
    "C1":1,
    "C2SX":2, "C2DX":2,
    "C3SX":3, "C3DX":3,
    "C4":4, "C5":5, "C6":6,
    "C7":7, "C8":8, "C9":9, "C10":10,
    "C11SX":11, "C11DX":11,
    "C12":12, "C13":13, "C14":14,
    "C15":15,
    "C16":18,
    "C17":20
}

# For each part code, use the earliest removal among all mapped nodes
PART_STEP = {code: MAX_STEP for code in range(1, 25)}
for node_id, part_code in node_to_part.items():
    if node_id in disassembly_step:
        PART_STEP[part_code] = min(PART_STEP[part_code], disassembly_step[node_id])

# Part geometry types (proxy)
PART_TYPE = {
    1: "Base",
    2: "Bearings12",
    3: "Bearings14",
    4: "Shaft5",
    5: "Shaft4",
    6: "Shaft3",
    7: "Sprocket3",
    8: "Sprocket4RH",
    9: "Sprocket4",
    10:"Sprocket5",
    11: "Flange4",
    12: "Flange5",
    13: "BearingSealNoHole",
    14: "BearingSealWithHole",
    15: "Cover",
    16: "ScrewM12x30",)
    17: "PositioningPin",
    18: "Hook",
    19: "FlangeScrews",
    20: "Spacer",
    21: "Key3",
    22: "Key4RH",
    23: "Key4",
    24: "Key5"
}

CENTER = Vector((0.0, 0.0, 0.0))

def explode_factor(step_removed):
    # step_removed=1 -> factor=1 (furthest)
    # step_removed=MAX_STEP -> factor=0
    return max(0.0, min(1.0, (MAX_STEP - step_removed) / (MAX_STEP - 1)))

def base_loc_for(code, idx, qty):
    t = PART_TYPE[code]

    if t == "Base":
        return CENTER.copy()

    if t == "Bearings12":
        x = -25 if idx < 2 else 25
        y = -12 if (idx % 2 == 0) else 12
        return Vector((x, y, 9.5))

    if t == "Bearings14":
        x = -25 if idx == 0 else 25
        return Vector((x, 0.0, 9.8))

    if t in ("Shaft3", "Shaft4", "Shaft5"):
        y = {"Shaft3": -6.0, "Shaft4": 0.0, "Shaft5": 6.0}[t]
        return Vector((0.0, y, 10.0))

    if t.startswith("Sprocket"):
        x = 32.0
        y = {"Sprocket3": -6.0, "Sprocket4RH": -2.0, "Sprocket4": 2.0, "Sprocket5": 6.0}[t]
        return Vector((x, y, 10.0))

    if t == "Flange4":
        x = -5.0
        y = [-14.0, 0.0, 14.0][idx % 3]
        return Vector((x, y, 6.0))

    if t == "Flange5":
        return Vector((10.0, 0.0, 6.0))

    if t in ("BearingSealNoHole", "BearingSealWithHole"):
        x = -25.0 if t == "BearingSealNoHole" else 25.0
        return Vector((x, 0.0, 7.0))

    if t == "Cover":
        return Vector((0.0, 0.0, 24.0))

    if t == "ScrewM12x30":
        r = 24.0
        ang = 2 * math.pi * idx / max(1, qty)
        return Vector((0.0, r * math.sin(ang), 30.0))

    if t == "PositioningPin":
        y = -10.0 if idx == 0 else 10.0
        return Vector((0.0, y, 17.0))

    if t == "Hook":
        r = 18.0
        ang = 2 * math.pi * idx / max(1, qty)
        return Vector((-3.0, r * math.cos(ang), 12.0))

    if t == "FlangeScrews":
        r = 26.0
        ang = 2 * math.pi * idx / max(1, qty)
        z = 18.0 + (2.0 if (idx % 2 == 0) else -2.0)
        return Vector((2.0, r * math.sin(ang), z))

    if t == "Spacer":
        return Vector((0.0, 0.0, 9.0))

    if t in ("Key3", "Key4RH", "Key4", "Key5"):
        x = -28.0
        y = {"Key3": -6.0, "Key4RH": -2.0, "Key4": 2.0, "Key5": 6.0}[t]
        return Vector((x, y, 9.5))

    return CENTER.copy()

# Geometry (proxies)
def make_box(name, size_xyz, loc, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_xyz[0]/2, size_xyz[1]/2, size_xyz[2]/2)
    return obj

def make_cyl(name, radius, depth, loc, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.name = name
    return obj

def make_torus(name, major_r, minor_r, loc, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major_r, minor_radius=minor_r, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.name = name
    return obj

def make_plate(name, radius, thickness, loc):
    return make_cyl(name, radius, thickness, loc, rot=(0, 0, 0))

def select_only(objs):
    for o in bpy.data.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]

def make_bolt_proxy(code, idx, loc, rot):
    head = make_cyl(f"{code:02d}_Screw_head_{idx:02d}", 2.4, 2.0, loc, rot=rot)
    shaft_loc = Vector((loc.x, loc.y, loc.z - 7.5))
    shaft = make_cyl(f"{code:02d}_Screw_shaft_{idx:02d}", 1.1, 12.0, shaft_loc, rot=rot)

    select_only([head, shaft])
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = f"{code:02d}_Screw_{idx:02d}"
    return obj

def make_hook_proxy(code, idx, loc):
    a = make_box(f"{code:02d}_Hook_A_{idx:02d}", (4, 8, 10),
                 Vector((loc.x, loc.y - 3.5, loc.z + 4)))
    b = make_box(f"{code:02d}_Hook_B_{idx:02d}", (28, 4, 5),
                 Vector((loc.x, loc.y + 10.0, loc.z - 2.5)))

    select_only([a, b])
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = f"{code:02d}_Hook_{idx:02d}"
    return obj

# Camera + light (data API)
def setup_camera_light():
    cam_data = bpy.data.cameras.new("CameraData")
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    cam_obj.location = (-90, -60, 40)
    cam_obj.rotation_euler = (math.radians(65), 0.0, math.radians(35))
    add_to_collection(cam_obj, col)
    bpy.context.scene.camera = cam_obj

    light_data = bpy.data.lights.new(name="Sun", type='SUN')
    light_data.energy = 2.0
    light_obj = bpy.data.objects.new("Light", light_data)
    light_obj.location = (0, 0, 80)
    add_to_collection(light_obj, col)

setup_camera_light()

# Build exploded model
scene = bpy.context.scene
scene.frame_start = FRAME_ASSEMBLED
scene.frame_end = FRAME_EXPLODED

EXPLODE_DIR = EXPLODE_AXIS.normalized()
bolt_rot = (math.radians(90), 0.0, 0.0)

for code in range(1, 25):
    qty = int(PART_QTY.get(code, 1))
    step_removed = PART_STEP.get(code, MAX_STEP)

    factor = explode_factor(step_removed)
    explode_vec = EXPLODE_DIR * (EXPLODE_AMOUNT * factor)

    t = PART_TYPE.get(code, "Base")

    for i in range(qty):
        loc0 = base_loc_for(code, i, qty)
        loc1 = loc0 + explode_vec
        name_prefix = f"{code:02d}_{i:02d}"

        if t == "Base":
            obj = make_box(name_prefix + "_Base", (90, 55, 16), loc0)

        elif t == "Bearings12":
            obj = make_torus(name_prefix + "_Bear12", 6.5, 2.0, loc0, rot=(math.radians(90), 0, 0))

        elif t == "Bearings14":
            obj = make_torus(name_prefix + "_Bear14", 7.5, 1.7, loc0, rot=(math.radians(90), 0, 0))

        elif t in ("Shaft3", "Shaft4", "Shaft5"):
            obj = make_cyl(name_prefix + f"_{t}", 2.3, 85, loc0, rot=(0, math.radians(90), 0))

        elif t in ("Sprocket3", "Sprocket4RH", "Sprocket4", "Sprocket5"):
            obj = make_cyl(name_prefix + f"_{t}", 4.8, 10.0, loc0, rot=(0, math.radians(90), 0))

        elif t in ("Flange4", "Flange5"):
            obj = make_plate(name_prefix + f"_{t}", 18.0, 2.5, loc0)

        elif t in ("BearingSealNoHole", "BearingSealWithHole"):
            obj = make_torus(name_prefix + f"_{t}", 9.0, 1.5, loc0, rot=(math.radians(90), 0, 0))

        elif t == "Cover":
            obj = make_plate(name_prefix + "_Cover", 28.0, 3.0, loc0)

        elif t in ("ScrewM12x30", "FlangeScrews"):
            obj = make_bolt_proxy(code, i, loc0, rot=bolt_rot)

        elif t == "PositioningPin":
            obj = make_cyl(name_prefix + "_Pin", 1.4, 18.0, loc0, rot=(0, math.radians(90), 0))

        elif t == "Hook":
            obj = make_hook_proxy(code, i, loc0)

        elif t == "Spacer":
            obj = make_cyl(name_prefix + "_Spacer", 3.6, 10.0, loc0)

        elif t in ("Key3", "Key4RH", "Key4", "Key5"):
            obj = make_box(name_prefix + f"_{t}", (12, 4, 3), loc0)

        else:
            obj = make_box(name_prefix + "_Fallback", (5, 5, 5), loc0)

        assign_material(obj, code)
        add_to_collection(obj, col)

        # keyframes for exploded view
        obj.location = loc0
        obj.keyframe_insert(data_path="location", frame=FRAME_ASSEMBLED)
        obj.location = loc1
        obj.keyframe_insert(data_path="location", frame=FRAME_EXPLODED)

print("Done: exploded proxy gearbox built from HTML graph + hardcoded qty/mapping (no openpyxl).")

