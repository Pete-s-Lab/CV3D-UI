bl_info = {
    "name": "CompoundVision3D",
    "blender": (3, 0, 0),
    "category": "View3D",
    "author": "Peter T. Rühr",
    "version": (0, 0, 9031),
    "description": "CompoundVision3D Blender helper. Interactive CV3D cornea extraction and later facet-position helper tools.",
}

import bpy
import csv
import json
import math
import os
import re
import sys
import traceback
from pathlib import Path


CV3D_BLENDER_SCRIPT_VERSION = "0.0.9031-cv3d-step04-fast-candidates-landmark-scale"


# ---------------------------------------------------------------------
# Task / state helpers
# ---------------------------------------------------------------------

def get_scene():
    return bpy.context.scene


def scene_get(key, default=""):
    return get_scene().get(key, default)


def scene_set(key, value):
    get_scene()[key] = value


def report_info(message):
    print("[CV3D]", message)
    try:
        get_scene()["cv3d_last_message"] = str(message)
    except Exception:
        pass


def find_task_path_from_argv():
    """Return the path after Blender's -- separator, if present."""
    argv = sys.argv
    if "--" not in argv:
        return ""
    idx = argv.index("--")
    if idx + 1 >= len(argv):
        return ""
    return argv[idx + 1]


def load_task(task_path):
    path = Path(task_path)
    if not path.exists():
        raise FileNotFoundError(f"CV3D task file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        task = json.load(f)

    scene_set("cv3d_task_path", str(path))
    scene_set("cv3d_task_json", json.dumps(task, indent=2))
    scene_set("cv3d_cv_id", task.get("cv_id", ""))
    scene_set("cv3d_eye", task.get("eye", ""))
    scene_set("cv3d_input_stl_abs", task.get("input_stl_abs", ""))
    scene_set("cv3d_output_stl_abs", task.get("output_cornea_stl_abs", ""))
    scene_set("cv3d_output_blend_abs", task.get("output_blend_abs", ""))
    scene_set("cv3d_status_file_abs", task.get("status_file_abs", ""))
    scene_set("cv3d_task_type", task.get("task_type", ""))
    scene_set("cv3d_facet_size_estimate", float(task.get("facet_size_estimate", 20.0) or 20.0))
    scene_set("cv3d_decimate_ratio", float(task.get("decimate_ratio", 0.5) or 0.5))
    scene_set("cv3d_smooth_iterations", int(task.get("smooth_iterations", 10) or 10))
    scene_set("cv3d_smooth_factor", float(task.get("smooth_factor", 0.5) or 0.5))
    report_info(f"Loaded CV3D task for {task.get('cv_id')} {task.get('eye')}")
    return task


def task_base_dir(task=None):
    raw = scene_get("cv3d_task_path", "")
    if raw:
        p = Path(raw)
        try:
            return p.parents[2]
        except Exception:
            return p.parent
    task = task or current_task()
    af = task.get("analysis_folder", "")
    if af:
        p = Path(str(af))
        if p.is_absolute():
            return p
    return Path.cwd()


def resolve_task_stored_path(stored, task=None):
    if not stored:
        return ""
    p = Path(str(stored))
    if p.is_absolute():
        return str(p)
    return str((task_base_dir(task) / p).resolve())


def current_task():
    raw = scene_get("cv3d_task_json", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def current_blend_path():
    path = bpy.data.filepath
    return str(Path(path).resolve()) if path else ""


def task_output_blend_path():
    task = current_task()
    output_blend = scene_get("cv3d_output_blend_abs", task.get("output_blend_abs", ""))
    return resolve_task_stored_path(output_blend, task) if output_blend else ""


def current_file_is_task_output_blend():
    current = current_blend_path()
    output = task_output_blend_path()
    return bool(current and output and current == output)


def write_status(status, message, extra=None):
    task = current_task()
    status_path = resolve_task_stored_path(scene_get("cv3d_status_file_abs", "") or task.get("status_file_abs", ""), task)
    if not status_path:
        report_info("No status_file_abs defined; status was not written.")
        return

    task_type = task.get("task_type", "")
    step_id = {
        "cornea_extraction": "02_blender_cornea_extraction",
        "facet_position_checking": "04_blender_facet_position_checking",
        "head_landmarking": "05_blender_head_landmarking",
    }.get(task_type, task_type or "unknown")

    payload = {
        "status_version": "0.3",
        "script_version": CV3D_BLENDER_SCRIPT_VERSION,
        "status": status,
        "message": message,
        "task_type": task_type,
        "step_id": step_id,
        "cv_id": scene_get("cv3d_cv_id", task.get("cv_id", "")),
        "eye": scene_get("cv3d_eye", task.get("eye", "")),
        "actions_confirmed": {},
    }

    if task_type == "cornea_extraction":
        payload.update({
            "input_stl_abs": scene_get("cv3d_input_stl_abs", task.get("input_stl_abs", "")),
            "output_cornea_stl_abs": scene_get("cv3d_output_stl_abs", task.get("output_cornea_stl_abs", "")),
            "output_blend_abs": scene_get("cv3d_output_blend_abs", task.get("output_blend_abs", "")),
            "actions_confirmed": {
                "raw_stl_imported": bool(scene_get("cv3d_raw_stl_imported", False)),
                "statistics_shown": True,
                "scene_units_checked": True,
                "corneal_surface_extracted_by_user": status in {"exported", "complete", "complete_with_warning"},
                "modifiers_added": bool(scene_get("cv3d_modifiers_added", False)),
                "normals_recalculated": bool(scene_get("cv3d_normals_recalculated", False)),
                "ascii_stl_exported": status in {"exported", "complete", "complete_with_warning"},
                "single_selected_object_exported": status in {"exported", "complete", "complete_with_warning"},
                "blend_file_saved": status in {"exported", "complete", "complete_with_warning"},
            },
        })

    if task_type == "facet_position_checking":
        payload.update({
            "input_blend_abs": task.get("input_blend_abs", ""),
            "input_facet_candidates_abs": task.get("input_facet_candidates_abs", ""),
            "output_facet_positions_abs": task.get("output_facet_positions_abs", ""),
            "actions_confirmed": {
                "facet_candidates_imported": bool(scene_get("cv3d_facet_candidates_imported", False)),
                "facet_positions_exported": status in {"exported", "complete", "complete_with_warning"},
                "blend_file_saved": status in {"exported", "complete", "complete_with_warning"},
            },
        })

    if task_type == "head_landmarking":
        payload.update({
            "input_head_mesh_abs": task.get("input_head_mesh_abs", ""),
            "output_landmarks_abs": task.get("output_landmarks_abs", ""),
            "output_blend_abs": task.get("output_blend_abs", ""),
            "actions_confirmed": {
                "head_mesh_imported": bool(scene_get("cv3d_head_mesh_imported", False)),
                "landmarks_exported": status in {"exported", "complete", "complete_with_warning"},
                "blend_file_saved": status in {"exported", "complete", "complete_with_warning"},
            },
        })

    if extra:
        payload.update(extra)

    status_path = Path(status_path)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    with status_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    report_info(f"Wrote status JSON: {status_path}")


def setup_view():
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.clip_end = 10000
                    space.overlay.show_stats = True
                    # Equivalent of showing the N-panel/sidebar where supported.
                    try:
                        space.show_region_ui = True
                    except Exception:
                        pass


def activate_cv3d_sidebar():
    """Best-effort activation of the 3D View sidebar.

    Blender exposes reliable control for showing the sidebar, but not a stable
    public API for selecting a specific sidebar category tab. The panel category
    is set to 'CompoundVision3D', so once the sidebar is visible, the tab is
    available and Blender usually keeps the last active category per workspace.
    """
    setup_view()
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        for region in area.regions:
            if region.type != "WINDOW":
                continue
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    try:
                        with bpy.context.temp_override(area=area, region=region, space_data=space):
                            space.show_region_ui = True
                    except Exception:
                        pass


def shift_c_view_all():
    """Approximate Blender Shift+C: frame all and center view/cursor context where possible."""
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        for region in area.regions:
            if region.type != "WINDOW":
                continue
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    try:
                        with bpy.context.temp_override(area=area, region=region, space_data=space):
                            bpy.ops.view3d.view_all(center=True)
                    except Exception:
                        pass


def show_modifier_properties_tab():
    """Switch any visible Properties editor to the Modifiers tab."""
    for area in bpy.context.screen.areas:
        if area.type == "PROPERTIES":
            for space in area.spaces:
                if space.type == "PROPERTIES":
                    try:
                        space.context = "MODIFIER"
                    except Exception:
                        pass


def ensure_object_mode():
    try:
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass


def enable_stl_import_export():
    """Enable legacy STL add-on where needed. Blender 4 may use wm.stl_import/export."""
    try:
        bpy.ops.preferences.addon_enable(module="io_mesh_stl")
    except Exception:
        pass


def import_stl(filepath):
    filepath = str(filepath)
    enable_stl_import_export()

    imported_before = set(bpy.data.objects)
    try:
        bpy.ops.wm.stl_import(filepath=filepath)
    except Exception:
        bpy.ops.import_mesh.stl(filepath=filepath)

    imported_after = set(bpy.data.objects)
    new_objects = list(imported_after - imported_before)
    if not new_objects:
        new_objects = list(bpy.context.selected_objects)

    for obj in bpy.context.selected_objects:
        obj.select_set(False)

    for obj in new_objects:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    return new_objects


def export_selected_stl(filepath):
    filepath = str(filepath)
    enable_stl_import_export()

    # Blender 4.x
    try:
        bpy.ops.wm.stl_export(filepath=filepath, export_selected_objects=True, ascii_format=True)
        return
    except Exception:
        pass

    # Blender 3.x legacy exporter
    try:
        bpy.ops.export_mesh.stl(filepath=filepath, use_selection=True, ascii=True, use_mesh_modifiers=True)
        return
    except Exception:
        # Last attempt without ascii flag, depending on Blender version.
        bpy.ops.export_mesh.stl(filepath=filepath, use_selection=True, use_mesh_modifiers=True)


def selected_mesh_object():
    objs = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if len(objs) != 1:
        return None
    return objs[0]


def add_or_update_modifier(obj, mod_type, name):
    mod = obj.modifiers.get(name)
    if mod is None:
        mod = obj.modifiers.new(name=name, type=mod_type)
    return mod


def recalc_normals_for_object(obj):
    ensure_object_mode()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    scene_set("cv3d_normals_recalculated", True)


def make_export_copy_with_modifiers(obj):
    ensure_object_mode()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Duplicate selected corneal object, convert duplicate to mesh so modifiers are baked
    bpy.ops.object.duplicate()
    dup = bpy.context.object
    dup.name = obj.name + "_CV3D_export_copy"
    bpy.ops.object.convert(target="MESH")
    recalc_normals_for_object(dup)
    return dup


def delete_object(obj):
    ensure_object_mode()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.delete()


# ---------------------------------------------------------------------
# Step 02 operators
# ---------------------------------------------------------------------

class CV3D_OT_LoadTask(bpy.types.Operator):
    bl_idname = "cv3d.load_task"
    bl_label = "Load CV3D task JSON"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        try:
            load_task(self.filepath)
            setup_view()
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            report_info(traceback.format_exc())
            return {"CANCELLED"}

    def invoke(self, context, event):
        self.filepath = scene_get("cv3d_task_path", "")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class CV3D_OT_ImportSourceSTL(bpy.types.Operator):
    bl_idname = "cv3d.import_source_stl"
    bl_label = "Import source STL"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        task = current_task()
        input_path = scene_get("cv3d_input_stl_abs", task.get("input_stl_abs", ""))
        cv_id = scene_get("cv3d_cv_id", task.get("cv_id", "CV"))
        eye = scene_get("cv3d_eye", task.get("eye", "eye"))

        if not input_path or not Path(input_path).exists():
            self.report({"ERROR"}, f"Input STL not found: {input_path}")
            write_status("failed", f"Input STL not found: {input_path}")
            return {"CANCELLED"}

        try:
            ensure_object_mode()
            objs = import_stl(input_path)
            for i, obj in enumerate(objs):
                obj.name = f"{cv_id}_{eye}_source_stl" if i == 0 else f"{cv_id}_{eye}_source_stl_{i+1}"
            scene_set("cv3d_raw_stl_imported", True)
            setup_view()
            shift_c_view_all()

            output_blend = scene_get("cv3d_output_blend_abs", task.get("output_blend_abs", ""))
            if output_blend:
                output_blend_path = Path(output_blend)
                output_blend_path.parent.mkdir(parents=True, exist_ok=True)

                if output_blend_path.exists() and not current_file_is_task_output_blend():
                    message = (
                        "Existing output .blend detected; initial auto-save was skipped to avoid overwrite. "
                        f"Existing file: {output_blend}"
                    )
                    report_info(message)
                    write_status("paused_existing_blend", message)
                    self.report({"WARNING"}, message)
                    return {"CANCELLED"}

                bpy.ops.wm.save_as_mainfile(filepath=output_blend)
                report_info(f"Initial Blender file saved after STL import: {output_blend}")

            self.report({"INFO"}, f"Imported source STL: {input_path}")
            write_status("running", "Source STL imported and initial blend saved; waiting for user cornea extraction/export.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            report_info(traceback.format_exc())
            write_status("failed", f"Could not import STL: {e}")
            return {"CANCELLED"}


class CV3D_OT_AddExportModifiers(bpy.types.Operator):
    bl_idname = "cv3d.add_export_modifiers"
    bl_label = "Add/update decimate + smooth modifiers"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = selected_mesh_object()
        if obj is None:
            self.report({"ERROR"}, "Select exactly one cornea mesh object.")
            return {"CANCELLED"}

        decimate_ratio = float(scene_get("cv3d_decimate_ratio", 0.5))
        smooth_iterations = int(scene_get("cv3d_smooth_iterations", 10))
        smooth_factor = float(scene_get("cv3d_smooth_factor", 0.5))

        dec = add_or_update_modifier(obj, "DECIMATE", "CV3D_Decimate")
        dec.ratio = decimate_ratio

        sm = add_or_update_modifier(obj, "SMOOTH", "CV3D_Smooth")
        sm.iterations = smooth_iterations
        sm.factor = smooth_factor

        scene_set("cv3d_modifiers_added", True)
        show_modifier_properties_tab()
        self.report({"INFO"}, "Added/updated CV3D decimate and smooth modifiers.")
        return {"FINISHED"}


class CV3D_OT_RecalculateNormals(bpy.types.Operator):
    bl_idname = "cv3d.recalculate_normals"
    bl_label = "Recalculate normals outside"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = selected_mesh_object()
        if obj is None:
            self.report({"ERROR"}, "Select exactly one mesh object.")
            return {"CANCELLED"}

        try:
            recalc_normals_for_object(obj)
            self.report({"INFO"}, "Recalculated normals outside for selected object.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            report_info(traceback.format_exc())
            return {"CANCELLED"}



class CV3D_OT_SetLassoSelect(bpy.types.Operator):
    bl_idname = "cv3d.set_lasso_select"
    bl_label = "Set lasso select tool"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.select_lasso")
            self.report({"INFO"}, "Lasso select tool activated.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Could not activate lasso select: {e}")
            return {"CANCELLED"}


class CV3D_OT_SelectMore(bpy.types.Operator):
    bl_idname = "cv3d.select_more"
    bl_label = "Grow selection by neighbours +1"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = bpy.context.active_object
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "A mesh object must be active.")
            return {"CANCELLED"}

        try:
            if obj.mode != "EDIT":
                bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_more()
            self.report({"INFO"}, "Selection grown by one neighbour step.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Could not grow selection: {e}")
            report_info(traceback.format_exc())
            return {"CANCELLED"}


class CV3D_OT_SeparateCorneaSelection(bpy.types.Operator):
    bl_idname = "cv3d.separate_cornea_selection"
    bl_label = "Separate selection as cornea"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        original = bpy.context.active_object
        if original is None or original.type != "MESH":
            self.report({"ERROR"}, "A mesh object must be active.")
            return {"CANCELLED"}

        if original.mode != "EDIT":
            self.report({"ERROR"}, "Select the cornea faces in Edit Mode before using this button.")
            return {"CANCELLED"}

        cv_id = scene_get("cv3d_cv_id", "CV")
        eye = scene_get("cv3d_eye", "eye")
        before = set(bpy.data.objects)

        try:
            bpy.ops.mesh.separate(type="SELECTED")
            bpy.ops.object.mode_set(mode="OBJECT")
            after = set(bpy.data.objects)
            new_objects = list(after - before)

            if not new_objects:
                # Fallback: after separate, Blender often selects both; use selected object that is not original.
                new_objects = [obj for obj in bpy.context.selected_objects if obj != original and obj.type == "MESH"]

            if not new_objects:
                self.report({"ERROR"}, "No new separated object was detected. Was a face selection active?")
                return {"CANCELLED"}

            cornea = new_objects[0]
            cornea.name = f"{cv_id}_{eye}_cornea"

            original.hide_set(True)
            original.hide_render = True

            for obj in bpy.context.selected_objects:
                obj.select_set(False)
            cornea.select_set(True)
            bpy.context.view_layer.objects.active = cornea

            shift_c_view_all()
            self.report({"INFO"}, f"Separated cornea object: {cornea.name}; original hidden.")
            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, f"Could not separate cornea selection: {e}")
            report_info(traceback.format_exc())
            return {"CANCELLED"}



class CV3D_OT_ExportCornea(bpy.types.Operator):
    bl_idname = "cv3d.export_cornea"
    bl_label = "Export selected cornea + save blend"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        task = current_task()
        output_stl = scene_get("cv3d_output_stl_abs", task.get("output_cornea_stl_abs", ""))
        output_blend = scene_get("cv3d_output_blend_abs", task.get("output_blend_abs", ""))

        if not output_stl or not output_blend:
            self.report({"ERROR"}, "Output STL/blend paths are missing from the CV3D task.")
            return {"CANCELLED"}

        obj = selected_mesh_object()
        if obj is None:
            self.report({"ERROR"}, "Select exactly one cornea mesh object before export.")
            return {"CANCELLED"}

        try:
            Path(output_stl).parent.mkdir(parents=True, exist_ok=True)
            Path(output_blend).parent.mkdir(parents=True, exist_ok=True)

            export_copy = make_export_copy_with_modifiers(obj)
            bpy.ops.object.select_all(action="DESELECT")
            export_copy.select_set(True)
            bpy.context.view_layer.objects.active = export_copy

            export_selected_stl(output_stl)
            delete_object(export_copy)

            # Keep the original selected after export.
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            bpy.ops.wm.save_as_mainfile(filepath=output_blend)
            write_status("exported", "Cornea STL exported and blend file saved.")

            self.report({"INFO"}, f"Exported cornea STL and saved blend file for {scene_get('cv3d_eye', '')}.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            report_info(traceback.format_exc())
            write_status("failed", f"Could not export cornea: {e}")
            return {"CANCELLED"}



# ---------------------------------------------------------------------
# Step 04 / 05 collection and export helpers
# ---------------------------------------------------------------------

def get_or_create_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def link_object_to_collection(obj, coll_name):
    coll = get_or_create_collection(coll_name)
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    # Remove object from master scene collection if it was linked there directly.
    try:
        bpy.context.scene.collection.objects.unlink(obj)
    except Exception:
        pass
    return coll


def collection_objects(coll_name):
    coll = bpy.data.collections.get(coll_name)
    return list(coll.objects) if coll else []


def clear_collection(coll_name):
    for obj in collection_objects(coll_name):
        bpy.data.objects.remove(obj, do_unlink=True)


def create_cv3d_material(name, color):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


def task_facet_size_estimate_or_none():
    task = current_task()
    try:
        value = float(task.get("facet_size_estimate"))
        if math.isfinite(value) and value > 0:
            return value
    except Exception:
        pass
    return None


def facet_candidate_sphere_radius():
    facet_size = task_facet_size_estimate_or_none()
    if facet_size is None:
        return 8.0
    # Standard candidate diameter = one third of the facet estimate.
    return max(facet_size / 6.0, 0.0001)


def landmark_sphere_radius():
    facet_size = task_facet_size_estimate_or_none()
    if facet_size is None:
        return 20.0
    # Landmark diameter = three times the facet estimate.
    return max((3.0 * facet_size) / 2.0, 0.0001)


def create_sphere_template_object(radius, material, name="CV3D_template_sphere", segments=16, ring_count=8):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=ring_count,
        radius=radius,
        location=(0, 0, 0),
    )
    template = bpy.context.object
    template.name = name
    template.data.name = f"{name}_mesh"
    template.data.materials.append(material)
    return template


def set_collection_visibility(coll_name, visible=True):
    coll = bpy.data.collections.get(coll_name)
    if coll:
        coll.hide_viewport = not visible
        coll.hide_render = not visible


def import_facet_candidates_from_task():
    task = current_task()
    candidates_path = task.get("input_facet_candidates_abs") or task.get("facet_candidates_file_abs") or ""
    if not candidates_path or not Path(candidates_path).exists():
        raise FileNotFoundError(f"Facet candidates CSV not found: {candidates_path}")

    clear_collection("CV3D_facet_candidates")
    coll = get_or_create_collection("CV3D_facet_candidates")

    radius = facet_candidate_sphere_radius()
    mat = create_cv3d_material("CV3D_candidate_white", (1.0, 1.0, 1.0, 1.0))

    # Fast path: create one real UV-sphere mesh, then instance/copy the object
    # for every candidate. This is much faster than bpy.ops sphere creation per row.
    template = create_sphere_template_object(
        radius=radius,
        material=mat,
        name="CV3D_facet_candidate_template",
        segments=16,
        ring_count=8,
    )

    count = 0
    with open(candidates_path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            x = float(row.get("x", 0))
            y = float(row.get("y", 0))
            z = float(row.get("z", 0))
            point_id = row.get("facet_candidate_id") or row.get("ID") or row.get("facet_id") or str(count + 1)

            obj = template.copy()
            obj.data = template.data  # shared mesh data for speed and low memory use
            obj.location = (x, y, z)
            obj.name = f"facet_candidate_{point_id}"
            obj["cv3d_source_row"] = json.dumps(row)
            coll.objects.link(obj)
            count += 1

    bpy.data.objects.remove(template, do_unlink=True)

    scene_set("cv3d_facet_candidates_imported", True)
    report_info(f"Imported {count} facet candidates into CV3D_facet_candidates with radius {radius:g}.")
    return count


def export_facet_positions_to_csv():
    task = current_task()
    output_path = task.get("output_facet_positions_abs", "")
    if not output_path:
        raise ValueError("Task has no output_facet_positions_abs.")

    objs = [obj for obj in collection_objects("CV3D_facet_candidates") if obj.type in {"MESH", "EMPTY"}]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["cv_id", "eye", "facet_id", "blender_object_name", "x", "y", "z", "data_origin", "edit_status", "notes"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for i, obj in enumerate(objs, start=1):
            writer.writerow({
                "cv_id": task.get("cv_id", ""),
                "eye": task.get("eye", ""),
                "facet_id": f"F{i:06d}",
                "blender_object_name": obj.name,
                "x": obj.location.x,
                "y": obj.location.y,
                "z": obj.location.z,
                "data_origin": "manual_checked",
                "edit_status": "checked",
                "notes": "",
            })

    bpy.ops.wm.save_as_mainfile(filepath=task.get("input_blend_abs") or bpy.data.filepath)
    write_status("exported", f"Exported {len(objs)} checked facet positions.", {"facet_position_count": len(objs)})
    return len(objs)


def setup_facet_checking_scene():
    task = current_task()
    if not collection_objects("CV3D_facet_candidates"):
        import_facet_candidates_from_task()
    set_collection_visibility("CV3D_facet_candidates", True)
    setup_view()
    shift_c_view_all()
    write_status("running", "Facet candidates imported; waiting for manual checking/export.")


def setup_head_landmark_scene():
    task = current_task()
    head_mesh = resolve_task_stored_path(task.get("input_head_mesh_abs", ""), task)
    output_blend = resolve_task_stored_path(task.get("output_blend_abs", ""), task)
    if not head_mesh or not Path(head_mesh).exists():
        raise FileNotFoundError(f"Head mesh STL not found: {head_mesh}")

    if not collection_objects("CV3D_head_mesh"):
        objs = import_stl(head_mesh)
        mat = create_cv3d_material("CV3D_head_mesh_grey", (0.65, 0.65, 0.65, 1.0))
        for i, obj in enumerate(objs):
            obj.name = "CV3D_head_mesh" if i == 0 else f"CV3D_head_mesh_{i+1}"
            obj.data.materials.append(mat)
            obj.lock_location = (True, True, True)
            obj.lock_rotation = (True, True, True)
            obj.lock_scale = (True, True, True)
            link_object_to_collection(obj, "CV3D_head_mesh")
        scene_set("cv3d_head_mesh_imported", True)

    get_or_create_collection("CV3D_landmarks")
    set_collection_visibility("CV3D_head_mesh", True)
    set_collection_visibility("CV3D_landmarks", True)
    setup_view()
    shift_c_view_all()

    if output_blend:
        Path(output_blend).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    write_status("running", "Head mesh ready; waiting for landmark placement/export.")


def place_landmark(name):
    coll = get_or_create_collection("CV3D_landmarks")
    old = bpy.data.objects.get(f"landmark_{name}")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    mat = create_cv3d_material("CV3D_landmark_blue", (0.05, 0.25, 1.0, 1.0))
    loc = bpy.context.scene.cursor.location.copy()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=landmark_sphere_radius(), location=loc)
    obj = bpy.context.object
    obj.name = f"landmark_{name}"
    obj["cv3d_landmark_name"] = name
    obj.data.materials.append(mat)
    link_object_to_collection(obj, "CV3D_landmarks")
    report_info(f"Placed landmark '{name}' at 3D cursor.")


def export_landmarks_to_csv():
    task = current_task()
    output_path = task.get("output_landmarks_abs", "")
    if not output_path:
        raise ValueError("Task has no output_landmarks_abs.")
    names = task.get("landmark_names", ["anterior", "posterior", "left", "right"])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in names:
        obj = bpy.data.objects.get(f"landmark_{name}")
        if obj:
            rows.append({
                "cv_id": task.get("cv_id", ""),
                "landmark": name,
                "x": obj.location.x,
                "y": obj.location.y,
                "z": obj.location.z,
                "data_origin": "manual",
                "notes": "",
            })
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["cv_id", "landmark", "x", "y", "z", "data_origin", "notes"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    output_blend = resolve_task_stored_path(task.get("output_blend_abs", ""), task) or bpy.data.filepath
    if output_blend:
        bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    missing = [name for name in names if not bpy.data.objects.get(f"landmark_{name}")]
    status = "complete_with_warning" if missing else "exported"
    write_status(status, f"Exported {len(rows)} landmarks.", {"landmark_count": len(rows), "missing_landmarks": missing})
    return len(rows)


# ---------------------------------------------------------------------
# Later helper tools retained/adapted from the previous plugin
# ---------------------------------------------------------------------

class CV3D_OT_ImportFacetCandidates(bpy.types.Operator):
    bl_idname = "cv3d.import_facet_candidates"
    bl_label = "Import/reload facet candidates"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            count = import_facet_candidates_from_task()
            self.report({"INFO"}, f"Imported {count} facet candidates.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            report_info(traceback.format_exc())
            return {"CANCELLED"}


class CV3D_OT_AddFacetCandidateAtCursor(bpy.types.Operator):
    bl_idname = "cv3d.add_facet_candidate_at_cursor"
    bl_label = "Add candidate at 3D cursor"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            radius = facet_candidate_sphere_radius()
            mat = create_cv3d_material("CV3D_candidate_white", (1.0, 1.0, 1.0, 1.0))
            loc = bpy.context.scene.cursor.location.copy()
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=radius, location=loc)
            obj = bpy.context.object
            obj.name = "facet_candidate_manual"
            obj.data.materials.append(mat)
            link_object_to_collection(obj, "CV3D_facet_candidates")
            self.report({"INFO"}, "Added facet candidate at 3D cursor.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            report_info(traceback.format_exc())
            return {"CANCELLED"}


class CV3D_OT_ExportFacetPositions(bpy.types.Operator):
    bl_idname = "cv3d.export_facet_positions"
    bl_label = "Export facet positions"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            count = export_facet_positions_to_csv()
            self.report({"INFO"}, f"Exported {count} facet positions.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            report_info(traceback.format_exc())
            write_status("failed", f"Could not export facet positions: {e}")
            return {"CANCELLED"}


class CV3D_OT_PlaceLandmark(bpy.types.Operator):
    bl_idname = "cv3d.place_landmark"
    bl_label = "Place landmark at 3D cursor"
    bl_options = {"REGISTER", "UNDO"}

    landmark_name: bpy.props.StringProperty(default="")

    def execute(self, context):
        try:
            place_landmark(self.landmark_name)
            self.report({"INFO"}, f"Placed landmark: {self.landmark_name}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            report_info(traceback.format_exc())
            return {"CANCELLED"}


class CV3D_OT_ExportLandmarks(bpy.types.Operator):
    bl_idname = "cv3d.export_landmarks"
    bl_label = "Export landmarks"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            count = export_landmarks_to_csv()
            self.report({"INFO"}, f"Exported {count} landmarks.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            report_info(traceback.format_exc())
            write_status("failed", f"Could not export landmarks: {e}")
            return {"CANCELLED"}


# ---------------------------------------------------------------------
# UI panel
# ---------------------------------------------------------------------

class CV3D_PT_Panel(bpy.types.Panel):
    bl_label = "CompoundVision3D"
    bl_idname = "CV3D_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CompoundVision3D"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        task = current_task()
        task_type = task.get("task_type", scene_get("cv3d_task_type", ""))

        layout.label(text="CV3D task")
        layout.label(text=f"Type: {task_type or 'not loaded'}")
        layout.label(text=f"CV ID: {scene_get('cv3d_cv_id', 'not loaded')}")
        if scene_get("cv3d_eye", ""):
            layout.label(text=f"Eye: {scene_get('cv3d_eye', '')}")
        layout.label(text=f"Facet estimate: {scene_get('cv3d_facet_size_estimate', 'NA')}")

        task_loaded = bool(scene_get("cv3d_task_json", ""))
        source_imported = bool(scene_get("cv3d_raw_stl_imported", False))

        col = layout.column(align=True)
        col.label(text="Startup/manual fallback")
        task_row = col.row(align=True)
        task_row.enabled = not task_loaded
        task_row.operator("cv3d.load_task", text="Load task JSON")

        if task_type in {"", "cornea_extraction"}:
            import_row = col.row(align=True)
            import_row.enabled = task_loaded and not source_imported
            import_row.operator("cv3d.import_source_stl", text="Import source STL")

            if task_loaded and source_imported:
                col.label(text="Task loaded and source imported automatically.")

            layout.separator()
            layout.label(text="Step 02 cornea extraction")
            col = layout.column(align=True)
            col.operator("cv3d.set_lasso_select", text="Lasso select tool")
            col.operator("cv3d.select_more", text="Grow selection +1")
            col.operator("cv3d.separate_cornea_selection", text="Separate selection as cornea")
            col.operator("cv3d.add_export_modifiers", text="Add/update export modifiers")
            col.operator("cv3d.recalculate_normals", text="Recalculate normals outside")
            col.operator("cv3d.export_cornea", text="Export selected cornea + save blend")

        if task_type == "facet_position_checking":
            layout.separator()
            layout.label(text="Step 04 facet position checking")
            col = layout.column(align=True)
            col.operator("cv3d.import_facet_candidates", text="Reload facet candidates")
            col.operator("cv3d.add_facet_candidate_at_cursor", text="Add candidate at 3D cursor")
            col.operator("cv3d.export_facet_positions", text="Export facet positions + save blend")
            layout.label(text="Delete false candidates directly in Blender; move retained candidates as needed.")

        if task_type == "head_landmarking":
            layout.separator()
            layout.label(text="Step 05 head landmarking")
            col = layout.column(align=True)
            for name in ["anterior", "posterior", "left", "right"]:
                op = col.operator("cv3d.place_landmark", text=f"Place {name}")
                op.landmark_name = name
            col.operator("cv3d.export_landmarks", text="Export landmarks + save blend")
            layout.label(text="Set the 3D cursor on the head mesh, then place the landmark.")

        msg = scene_get("cv3d_last_message", "")
        if msg:
            layout.separator()
            layout.label(text="Last message:")
            layout.label(text=str(msg)[:80])


classes = [
    CV3D_OT_LoadTask,
    CV3D_OT_ImportSourceSTL,
    CV3D_OT_AddExportModifiers,
    CV3D_OT_RecalculateNormals,
    CV3D_OT_SetLassoSelect,
    CV3D_OT_SelectMore,
    CV3D_OT_SeparateCorneaSelection,
    CV3D_OT_ExportCornea,
    CV3D_OT_ImportFacetCandidates,
    CV3D_OT_AddFacetCandidateAtCursor,
    CV3D_OT_ExportFacetPositions,
    CV3D_OT_PlaceLandmark,
    CV3D_OT_ExportLandmarks,
    CV3D_PT_Panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


def initialize_from_cli():
    task_path = find_task_path_from_argv()
    if not task_path:
        report_info("No CV3D task JSON supplied on command line.")
        return

    try:
        task = load_task(task_path)
        setup_view()
        activate_cv3d_sidebar()
        task_type = task.get("task_type", "")

        if task_type == "cornea_extraction":
            if current_file_is_task_output_blend():
                scene_set("cv3d_raw_stl_imported", True)
                report_info("Opened existing CV3D output .blend; automatic STL import skipped to avoid overwriting work.")
                write_status("running", "Existing Blender file opened; continue extraction/export manually.")
            else:
                bpy.ops.cv3d.import_source_stl()

        elif task_type == "facet_position_checking":
            setup_facet_checking_scene()

        elif task_type == "head_landmarking":
            setup_head_landmark_scene()

        else:
            report_info(f"Unknown or unsupported CV3D task_type: {task_type}")
            write_status("failed", f"Unsupported task_type: {task_type}")

        activate_cv3d_sidebar()
    except Exception as e:
        report_info(traceback.format_exc())
        try:
            write_status("failed", f"Blender initialization failed: {e}")
        except Exception:
            pass


if __name__ == "__main__":
    register()
    initialize_from_cli()
