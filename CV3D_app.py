"""CV3D UI controller."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import sys
import subprocess
import zipfile
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QDesktopServices, QImage
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
        QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
        QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
        QButtonGroup, QSpinBox, QDoubleSpinBox, QStackedWidget, QTextEdit,
        QVBoxLayout, QWidget, QInputDialog, QSplitter, QSizePolicy, QFrame
    )
except ImportError as e:
    raise SystemExit(
        "PySide6 is required for CV3D UI.\n"
        "Install with: pip install PySide6\n"
    ) from e


APP_VERSION = "0.1.115"

CHANGELOG = [
    "0.1.115: Removed raw facet-size plotting, added optional facet-ID labels to Choose facet value plots, and corrected 05C PDF snapshot sphere scaling/aspect-preserving placement.",
    "0.1.114: Renamed 05A plot actions, moved normals into Choose facet value, defaulted optional rgl views to on, and added a normal-vector visibility toggle with a dedicated normals-options dialog.",
    "0.1.113: Defaulted facet-sphere diameter scaling to 2x and consolidated plot inputs into one options dialog per plot action; dataset creation source inputs are also collected in one dialog.",
    "0.1.112: Shortened R Analysis action labels and added user-scalable facet-sphere diameters for 05A/05B/05C rgl QC plots (1x = facet size, 0 = legacy plot size, dataset estimate used as fallback).",
    "0.1.111: Batched all direction-coloured 05A normal vectors into one rgl segments3d call, duplicating each facet colour for both segment endpoints and preserving the stable 0.1.109 window lifecycle.",
    "0.1.110: Restored direction colour on each 05A normal vector using scalar-colour segment drawing while preserving the stable 0.1.109 rgl lifecycle.",
    "0.1.109: Reset the 05A normals rgl path to the last known-working implementation, retained direction coding on facet positions, removed Unicode from native-rgl text, and stopped swallowing rgl errors.",
    "0.1.108: Restored the proven 03A/03B native-rgl lifetime pattern for all 05A interactive plots.",
    "0.1.107: Fixed 05A interactive rgl lifetime by allowing the native device to initialise before polling and using cur3d()/rgl.dev.list() with startup grace.",
    "0.1.106: Restored the proven rgl current-device keep-open loop for 05A interactive plots and removed both spellings of n_neighbours_used from metric choices.",
    "0.1.105: Kept interactive 05A rgl plots alive until the user closes them and simplified the selected-metric dropdown.",
    "0.1.104: Fixed 05A direction-coloured normal plotting and hid normal-estimator provenance fields from the generic 05A value-plot selector.",
    "0.1.103: Added selectable regularised facet-centre envelope normals for 05A, defaulting to 1.25x, and direction-coloured normal QC plotting.",
    "0.1.102: Standardised Step 04 facet IDs to FXXXXX and reserved F9XXXX for manually added facets.",
    "0.1.101: Made Blender object names authoritative facet identifiers for Step 04 exports and downstream optical analyses.",
    "0.1.100: Added an in-dialog explanation of the 05A neighbour-link tolerance parameter.",
    "0.1.99: Fixed specimen-level Blender task path resolution so head meshes and status files resolve from the dataset root rather than the json subfolder.",
    "0.1.98: Made specimen head-mesh loading for Blender head landmarking robust to stale/hidden head collections and explicitly frames the loaded head mesh.",
    "0.1.97: Increased Blender facet-candidate marker size to 1.5x the previous size.",
    "0.1.96: Automatically open the facet-candidate local-height inspection plot after successful 03C condensation.",
    "0.1.95: Fixed automatic post-03B interactive plotting and made the 03B preview use the selected colour-scale limits in a single eye panel.",
    "0.1.94: Keep the automatically launched 03B thresholded-point rgl plot open for inspection until the user closes it.",
    "0.1.93: Automatically create the thresholded local-height 3D PNG after successful 03B thresholding.",
    "0.1.92: Clarified 03A2 normalization defaults, streamlined action-button labels, and added a visible blocking-process indicator.",
    "0.1.91: Streamlined ImageJ STL extraction: multi-target runs share one Fiji session, accepted thresholds carry forward, and head export uses the preview surface.",
    "0.1.90: Replaced global spherical facet-neighbour inference with CV3D local tangent-plane neighbour detection in 05A.",
    "0.1.89: Final consolidation pass: documentation alignment, robust legacy contrast plotting, and publication-facing cleanup.",
    "0.1.88: Consolidated publication-facing geometry/optics nomenclature, 0-1 local-height contrast handling, projection-centre persistence, bilateral CP centring, circular azimuth summaries, and explicit micrometre units.",
    "0.1.87: Added square/hexagonal lattice selection for Snyder eye parameter and sampling frequency while keeping Feller CPD separate.",
    "0.1.86: Updated 05C projection geometry to CV3D ray-sphere intersections and elevation/azimuth view angles.",
    "0.1.85: Updated the UI and bundled helpers to use the renamed CV3D R package namespace and CV3D branding.",
    "0.1.83: Improved Results/Export QC PDF typography, path wrapping, PDF-safe status symbols, rotated table headers, and stricter equal-unit plot panels.",
    "0.1.82: Polished Results/Export QC PDF text/layout, removed landmark-reference panels, enforced equal-unit coordinate panels, and embeds 05C rgl snapshots.",
    "0.1.77: Set post-global-coordinate rgl camera from explicit screen-axis basis: x diagonal down-right, y diagonal up-right, z upward, with perspective.",
    "0.1.76: Adjusted post-global-coordinate rgl camera to x/y diagonal, z-up perspective view.",
    "0.1.75: Standardized the rgl camera for post-global-coordinate 05B/05C QC views.",
    "0.1.74: Restored eye-wise 05B/05C QC buttons to single-eye plotting; only combined buttons plot both eyes.",
    "0.1.73: Updated the default GitHub repository to Pete-s-Lab/CV3D.",
    "0.1.81: Fixed Results/Export report path handling so final-export files are not nested twice.",
    "0.1.80: Results/Export QC PDF now uses cleaner vector-style QC plots, optional fresh 05C rgl snapshots, and combined plus eye-wise sections.",
    "0.1.72: Results/Export now reports the absolute export folder and creates the QC PDF without requiring matplotlib.",
    "0.1.71: Rebuilds workflow/R Analysis states from existing on-disk outputs when loading recovered or stale datasets.",
    "0.1.70: Added registry recovery for moved/relative dataset folders so existing datasets still open after helper-path migration.",
    "0.1.69: Added final Results/Export output folder, relative helper-path storage, and visible settings entries for all bundled helpers.",
    "0.1.68: Renamed Report / Export to Results / Export and added analysis-ready export tables plus a QC PDF report.",
    "0.1.60: Added a normal-length prompt to the 05A facet-normal QC plot; default normal length is 5x facet size.",
    "0.1.58: Updated 05C QC plots to colour by facet size, use fast vectorized normal plotting, draw normals halfway to the projection sphere, and make rgl snapshots non-fatal.",
    "0.1.57: Moved 05C corneal-projection QC plots to a separate button, added optional rgl projection-sphere inspection, and renamed 05C plot PNGs with a 05C prefix.",
    "0.1.56: Changed 05C default corneal-projection sphere diameter to 15 cm.",
    "0.1.55: 05B crop-log parser is encoding-safe for ImageJ unit symbols and applies ROI translation before landmark alignment.",
    "0.1.53: Added explicit 05B landmark-referenced point-cloud output before global alignment, plus an aligned point-cloud output used by QC plotting.",
    "0.1.52: Added a 05B global-alignment QC plot button with facet-size colours, facet-size/2 spheres, and blue landmarks.",
    "0.1.51: Renamed the 05A edge_tol runtime prompt to Neighbour-link tolerance.",
    "0.1.50: Added selectable 05A single-metric plot buttons with facet labels for Blender-side QC.",
    "0.1.49: Added 05A inspection-plot buttons in the R Analysis tab for optic-parameter and facet-normal PNGs with optional interactive rgl windows.",
    "0.1.48: Bundled the stepwise numeric-internal-ID 05A optical metrics runner and kept R Analysis buttons connected.",
    "0.1.47: Enabled connected R Analysis buttons when prerequisites are present and removed the stale pre-release disabled-state text.",
    "0.1.46: Connected R Analysis steps 05A-05C to package-backed R helper runners and added per-facet output files for optics, alignment, and projections.",
    "0.1.45: Added a separate R Analysis tab between Eye Workflow and Mirroring for downstream R-side analysis steps.",
    "0.1.44: Added an Inspection plots separator/header in each eye workflow panel.",
    "0.1.43: Pre-release helper packaging, bundled helper discovery, cleaned app naming, and mesh status files moved into json/logs folders."
]
REGISTRY_FILE = "CV3D_project_registry.json"
APP_SETTINGS_FILE = Path.home() / ".cv3d_settings.json"
LEGACY_APP_SETTINGS_FILE = Path.home() / ".cv3d_dummy_settings.json"
APP_DIR = Path(__file__).resolve().parent
HELPER_DIR = APP_DIR / "cv3d_helpers"


def safe_filename_token(text: str) -> str:
    token = "".join(ch if ch.isalnum() else "_" for ch in str(text).strip())
    token = token.strip("_")
    return token or "value"
BUNDLED_HELPER_SCRIPTS = {
    "imagej_macro_path": Path("cv3d_helpers/imagej/CV3D_ij_preprocess.ijm"),
    "imagej_mesh_macro_path": Path("cv3d_helpers/imagej/CV3D_ij_mesh.ijm"),
    "blender_script_path": Path("cv3d_helpers/blender/CV3D_blender.py"),
    "r_step03a_script_path": Path("cv3d_helpers/r/CV3D_R_03A_heights.R"),
    "r_step03a_plot_script_path": Path("cv3d_helpers/r/CV3D_R_03A_plot_raw.R"),
    "r_step03a2_script_path": Path("cv3d_helpers/r/CV3D_R_03A2_normalize.R"),
    "r_step03a2_plot_script_path": Path("cv3d_helpers/r/CV3D_R_03A2_plot_norm.R"),
    "r_step03b_script_path": Path("cv3d_helpers/r/CV3D_R_03B_threshold.R"),
    "r_step03b_plot_script_path": Path("cv3d_helpers/r/CV3D_R_03B_plot_threshold.R"),
    "r_step03c_script_path": Path("cv3d_helpers/r/CV3D_R_03C_candidates.R"),
    "r_step05a_script_path": Path("cv3d_helpers/r/CV3D_R_05A_optics.R"),
    "r_step05b_script_path": Path("cv3d_helpers/r/CV3D_R_05B_align.R"),
    "r_step05c_script_path": Path("cv3d_helpers/r/CV3D_R_05C_projection.R"),
    "r_step05a_qc_plot_script_path": Path("cv3d_helpers/r/CV3D_R_05A_QC_plots.R"),
    "r_step05b_qc_plot_script_path": Path("cv3d_helpers/r/CV3D_R_05B_QC_plots.R"),
    "r_step05c_qc_plot_script_path": Path("cv3d_helpers/r/CV3D_R_05C_QC_plots.R"),
    "r_facet_point_plot_script_path": Path("cv3d_helpers/r/CV3D_R_QC_facet_overlay.R"),
}

HELPER_SETTING_KEYS = set(BUNDLED_HELPER_SCRIPTS.keys())


def helper_path_for_storage(key: str, value: Any) -> str:
    """Store helper scripts relative to the app folder when possible."""
    if value is None:
        return ""
    text_value = str(value).strip()
    if not text_value:
        return ""
    if key not in HELPER_SETTING_KEYS:
        return text_value
    try:
        p = Path(text_value)
        if p.is_absolute():
            try:
                return str(p.relative_to(APP_DIR))
            except Exception:
                return text_value
        return text_value
    except Exception:
        return text_value


def helper_file_dialog_start(settings: Dict[str, Any], key: str) -> str:
    value = settings.get(key, "")
    try:
        p = configured_file_path(value)
        if p is not None:
            return str(p.parent)
    except Exception:
        pass
    return str(Path.home())


PARAM_DISPLAY_NAMES = {
    "edge_tol": "Neighbour-link tolerance",
    "cores": "CPU cores",
    "normal_length_facet_size_factor": "Normal length (x facet size)",
    "neighbourhood_radius": "Neighbourhood radius",
}

EYES = ["eye1", "eye2"]

STEP_ORDER = [
    "02_blender_cornea_extraction",
    "03a_local_height_calculation",
    "03a2_local_height_normalization",
    "03b_local_height_thresholding",
    "03c_facet_candidate_condensation",
    "04_blender_facet_check_landmarking",
    "05a_optical_metrics",
    "05b_global_coordinate_rotation",
    "05c_corneal_projections",
]

DOWNSTREAM = {
    "02_blender_cornea_extraction": [
        "03a_local_height_calculation", "03b_local_height_thresholding",
        "03c_facet_candidate_condensation", "04_blender_facet_check_landmarking",
        "05a_optical_metrics", "05b_global_coordinate_rotation",
        "05c_corneal_projections"
    ],
    "03a_local_height_calculation": [
        "03a2_local_height_normalization", "03b_local_height_thresholding", "03c_facet_candidate_condensation",
        "04_blender_facet_check_landmarking", "05a_optical_metrics",
        "05b_global_coordinate_rotation", "05c_corneal_projections"
    ],
    "03a2_local_height_normalization": ["03a_local_height_calculation"],
    "03b_local_height_thresholding": [
        "03c_facet_candidate_condensation", "04_blender_facet_check_landmarking",
        "05a_optical_metrics", "05b_global_coordinate_rotation",
        "05c_corneal_projections"
    ],
    "03c_facet_candidate_condensation": [
        "04_blender_facet_check_landmarking", "05a_optical_metrics",
        "05b_global_coordinate_rotation", "05c_corneal_projections"
    ],
    "04_blender_facet_check_landmarking": [
        "05a_optical_metrics", "05b_global_coordinate_rotation",
        "05c_corneal_projections"
    ],
    "05a_optical_metrics": [],
    "05b_global_coordinate_rotation": ["05c_corneal_projections"],
    "05c_corneal_projections": [],
}

# Immediate upstream products required before each step can run.
# The step itself may be rerun when its own outputs are missing/stale, but its
# required inputs must exist and must not already be marked stale.
REQUIRED_INPUT_STEPS = {
    "02_blender_cornea_extraction": [],
    "03a_local_height_calculation": ["02_blender_cornea_extraction"],
    "03a2_local_height_normalization": ["03a_local_height_calculation"],
    "03b_local_height_thresholding": ["03a_local_height_calculation"],
    "03c_facet_candidate_condensation": ["03b_local_height_thresholding"],
    "04_blender_facet_check_landmarking": ["03c_facet_candidate_condensation"],
    "05a_optical_metrics": ["04_blender_facet_check_landmarking"],
    "05b_global_coordinate_rotation": ["05a_optical_metrics"],
    "05c_corneal_projections": ["05a_optical_metrics", "05b_global_coordinate_rotation"],
}

STEP_LABELS = {
    "00_dataset_setup": "00 Dataset setup",
    "01_imagej_preprocessing": "01 ImageJ preprocessing",
    "02_blender_cornea_extraction": "02 Blender cornea extraction",
    "03a_local_height_calculation": "03A Local height calculation",
    "03a2_local_height_normalization": "03A2 Optional local-height normalization",
    "03b_local_height_thresholding": "03B Local-height thresholding",
    "03c_facet_candidate_condensation": "03C Facet candidate condensation",
    "04_blender_facet_check_landmarking": "04 Facet position checking",
    "05_blender_head_landmarking": "05 Head landmarking",
    "05a_optical_metrics": "05A Optical metrics",
    "05b_global_coordinate_rotation": "05B Global coordinate rotation",
    "05c_corneal_projections": "05C Corneal projections",
    "05d_mirror_missing_eye": "05D Mirror eye outputs",
    "06_report_export": "06 Results/export",
}

STATE_SYMBOL = {
    "not_started": "○",
    "running": "▶",
    "complete": "✓",
    "complete_with_warning": "!",
    "needs_rerun": "↻",
    "failed": "✕",
    "skipped": "–",
    "not_created": "○",
    "exported": "✓",
    "not_exported": "○",
    "outdated_export": "↻",
}



def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _is_abs_path_string(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        return Path(value).is_absolute()
    except Exception:
        return False


def _maybe_relpath(value: str, base: Path) -> str:
    try:
        p = Path(value)
        if p.is_absolute():
            return os.path.relpath(str(p), str(base))
    except Exception:
        pass
    return value


def _relativize_json_data_for_storage(data: Any, base: Optional[Path], parent_key: str = "") -> Any:
    if base is None:
        return data
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            if key == "analysis_folder" and _is_abs_path_string(value):
                out[key] = "."
            elif key in {"raw_folder_path", "analysis_folder_path", "registry_path"} and _is_abs_path_string(value):
                out[key] = _maybe_relpath(value, base)
            elif key.endswith("_abs") and isinstance(value, str):
                out[key] = _maybe_relpath(value, base)
            else:
                out[key] = _relativize_json_data_for_storage(value, base, key)
        return out
    if isinstance(data, list):
        return [_relativize_json_data_for_storage(v, base, parent_key) for v in data]
    if isinstance(data, str) and parent_key.endswith("_abs"):
        return _maybe_relpath(data, base)
    return data


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base = None
    if isinstance(data, dict):
        analysis_folder = data.get("analysis_folder")
        if _is_abs_path_string(analysis_folder):
            base = Path(str(analysis_folder))
        elif path.name == REGISTRY_FILE:
            base = path.parent
        elif isinstance(data.get("dataset_identity"), dict):
            af = data["dataset_identity"].get("analysis_folder_path")
            if _is_abs_path_string(af):
                base = Path(str(af))
            elif path.name.startswith("00_") and path.name.endswith("project_config.json"):
                base = path.parent
    payload = _relativize_json_data_for_storage(data, base)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def resolve_stored_path(base: Path, stored: Any) -> Path:
    p = Path(str(stored))
    return p if p.is_absolute() else (base / p)


def resolve_task_path(task: Dict[str, Any], key: str, analysis_folder: Path) -> Path:
    stored = task.get(key, "")
    return resolve_stored_path(analysis_folder, stored)


def relative_task_argument(task_path: Path, analysis_folder: Path) -> str:
    try:
        return str(task_path.relative_to(analysis_folder))
    except Exception:
        return str(task_path)


def resolve_registry_entry_analysis_folder(project_folder: Path, entry: Dict[str, Any]) -> Path:
    stored = entry.get("analysis_folder") or entry.get("analysis_folder_path") or ""
    return resolve_stored_path(project_folder, stored)


def resolve_registry_entry_raw_folder(project_folder: Path, entry: Dict[str, Any]) -> Path:
    stored = entry.get("raw_folder_path") or entry.get("raw_folder") or entry.get("raw_folder_name") or ""
    return resolve_stored_path(project_folder, stored)


def find_dataset_file_pair(project_folder: Path, cv_id: str, preferred_analysis_folder: Optional[Path] = None) -> Optional[Dict[str, Path]]:
    """Find config/status files for cv_id even if the registry analysis folder is stale."""
    config_name = f"00_{cv_id}_project_config.json"
    status_name = f"00_{cv_id}_status.json"
    candidate_dirs: List[Path] = []
    if preferred_analysis_folder is not None:
        candidate_dirs.extend([
            preferred_analysis_folder,
            preferred_analysis_folder.parent,
            preferred_analysis_folder / f"{cv_id}_CV3D",
        ])
    candidate_dirs.extend([
        project_folder,
        project_folder / f"{cv_id}_CV3D",
    ])
    for base in list(candidate_dirs):
        try:
            if base and base.exists() and base.is_dir():
                candidate_dirs.extend([p for p in base.glob(f"**/{cv_id}_CV3D") if p.is_dir()])
        except Exception:
            pass
    seen = set()
    for folder in candidate_dirs:
        try:
            folder = Path(folder)
            key = str(folder.resolve()) if folder.exists() else str(folder)
        except Exception:
            key = str(folder)
        if key in seen:
            continue
        seen.add(key)
        config_path = folder / config_name
        status_path = folder / status_name
        if config_path.exists() and status_path.exists():
            return {"analysis_folder": folder, "config_path": config_path, "status_path": status_path}
    try:
        config_hits = list(project_folder.rglob(config_name)) if project_folder.exists() else []
    except Exception:
        config_hits = []
    for config_path in config_hits:
        folder = config_path.parent
        status_path = folder / status_name
        if status_path.exists():
            return {"analysis_folder": folder, "config_path": config_path, "status_path": status_path}
    return None


def resolve_config_raw_folder(config: Dict[str, Any], analysis_folder: Path) -> Path:
    stored = config.get("dataset_identity", {}).get("raw_folder_path", "")
    return resolve_stored_path(analysis_folder, stored)


def write_csv(path: Path, fieldnames: List[str], rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)



def configured_file_path(value: Any) -> Optional[Path]:
    """Return a real file path from a settings value, resolving relative helper paths against the app folder."""
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    path = Path(text_value)
    candidates = [path] if path.is_absolute() else [APP_DIR / path, Path.cwd() / path, path]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except Exception:
            pass
    return None


def detect_recommended_cores() -> Dict[str, Any]:
    cores = os.cpu_count() or 1
    if cores < 4:
        max_cores = cores
    elif cores <= 8:
        max_cores = cores - 1
    else:
        max_cores = cores - 2
    return {
        "available_cores_detected": cores,
        "max_cores": max_cores,
        "user_overridden": False,
        "rule": "if available_cores < 4 use all; if 4-8 use n-1; if >8 use n-2",
    }



def bundled_helper_abs_path(settings_key: str) -> Optional[Path]:
    rel = BUNDLED_HELPER_SCRIPTS.get(settings_key)
    if rel is None:
        return None
    path = APP_DIR / rel
    return path if path.is_file() else None


def apply_bundled_helper_paths(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Use bundled helper scripts when this UI is distributed with cv3d_helpers/."""
    settings.setdefault("use_bundled_helpers", True)
    if not settings.get("use_bundled_helpers", True):
        return settings
    for key in BUNDLED_HELPER_SCRIPTS:
        bundled = bundled_helper_abs_path(key)
        if bundled is not None:
            settings[key] = str(BUNDLED_HELPER_SCRIPTS[key])
    return settings

def load_app_settings() -> Dict[str, Any]:
    if not APP_SETTINGS_FILE.exists() and LEGACY_APP_SETTINGS_FILE.exists():
        try:
            shutil.copyfile(LEGACY_APP_SETTINGS_FILE, APP_SETTINGS_FILE)
        except Exception:
            pass

    if APP_SETTINGS_FILE.exists():
        settings = read_json(APP_SETTINGS_FILE)
        settings.setdefault("imagej_executable", "")
        settings.setdefault("imagej_macro_path", "")
        settings.setdefault("imagej_mesh_macro_path", "")
        settings.setdefault("blender_executable", "")
        settings.setdefault("blender_script_path", "")
        settings.setdefault("rscript_executable", "")
        settings.setdefault("r_github_repo", "Pete-s-Lab/CV3D")
        if settings.get("r_github_repo") == "Pete-s-Lab/CV3D":
            settings["r_github_repo"] = "Pete-s-Lab/CV3D"
        settings.setdefault("r_step03a_script_path", "")
        settings.setdefault("r_step03a2_script_path", "")
        settings.setdefault("r_step03a_plot_script_path", "")
        settings.setdefault("r_step03a2_plot_script_path", "")
        settings.setdefault("r_step03b_script_path", "")
        settings.setdefault("r_step03b_plot_script_path", "")
        settings.setdefault("r_step03c_script_path", "")
        settings.setdefault("r_step05a_script_path", "")
        settings.setdefault("r_step05b_script_path", "")
        settings.setdefault("r_step05c_script_path", "")
        settings.setdefault("r_step05a_qc_plot_script_path", "")
        settings.setdefault("r_step05b_qc_plot_script_path", "")
        settings.setdefault("r_step05c_qc_plot_script_path", "")
        settings.setdefault("r_facet_point_plot_script_path", "")
        settings.setdefault("compute_settings", detect_recommended_cores())
        settings.setdefault("use_bundled_helpers", True)
        settings = apply_bundled_helper_paths(settings)
        for key in HELPER_SETTING_KEYS:
            if key in settings:
                settings[key] = helper_path_for_storage(key, settings.get(key, ""))
        return settings
    settings = {
        "app_version": APP_VERSION,
        "compute_settings": detect_recommended_cores(),
        "last_project_folder": None,
        "use_bundled_helpers": True,
        "imagej_executable": "",
        "imagej_macro_path": "",
        "imagej_mesh_macro_path": "",
        "blender_executable": "",
        "blender_script_path": "",
        "rscript_executable": "",
        "r_github_repo": "Pete-s-Lab/CV3D",
        "r_step03a_script_path": "",
        "r_step03a2_script_path": "",
        "r_step03a_plot_script_path": "",
        "r_step03a2_plot_script_path": "",
        "r_step03b_script_path": "",
        "r_step03b_plot_script_path": "",
        "r_step03c_script_path": "",
        "r_step05a_script_path": "",
        "r_step05b_script_path": "",
        "r_step05c_script_path": "",
        "r_step05a_qc_plot_script_path": "",
        "r_step05b_qc_plot_script_path": "",
        "r_step05c_qc_plot_script_path": "",
        "r_facet_point_plot_script_path": "",
    }
    settings = apply_bundled_helper_paths(settings)
    save_app_settings(settings)
    return settings


def save_app_settings(settings: Dict[str, Any]) -> None:
    payload = dict(settings)
    for key in HELPER_SETTING_KEYS:
        if key in payload:
            payload[key] = helper_path_for_storage(key, payload.get(key, ""))
            settings[key] = payload[key]
    write_json(APP_SETTINGS_FILE, payload)


def cv_number(cv_id: str) -> int:
    return int(cv_id.replace("CV", ""))


def format_cv_id(n: int) -> str:
    return f"CV{n:04d}"


def default_registry() -> Dict[str, Any]:
    return {
        "registry_version": "0.3",
        "created_with_cv3d_version": APP_VERSION,
        "last_modified": now(),
        "datasets": [],
    }


def load_or_create_registry(project_folder: Path) -> Dict[str, Any]:
    registry_path = project_folder / REGISTRY_FILE
    if not registry_path.exists():
        reg = default_registry()
        write_json(registry_path, reg)
        return reg
    return read_json(registry_path)


def next_cv_id(registry: Dict[str, Any]) -> str:
    ids = [d.get("cv_id", "CV0000") for d in registry.get("datasets", [])]
    if not ids:
        return "CV0001"
    return format_cv_id(max(cv_number(x) for x in ids) + 1)


def append_log(analysis_folder: Path, cv_id: str, eye: str, step_id: str,
               action: str, state_before: str, state_after: str,
               result: str, messages: str = "", parameters: str = "") -> None:
    log_path = analysis_folder / f"00_{cv_id}_run_log.csv"
    exists = log_path.exists()
    with log_path.open("a", newline="", encoding="utf-8") as f:
        fields = [
            "timestamp", "cv_id", "eye", "step_id", "action", "state_before",
            "state_after", "parameters", "result", "messages"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": now(),
            "cv_id": cv_id,
            "eye": eye,
            "step_id": step_id,
            "action": action,
            "state_before": state_before,
            "state_after": state_after,
            "parameters": parameters,
            "result": result,
            "messages": messages,
        })


def dataset_paths(analysis_folder: Path, cv_id: str) -> Dict[str, Path]:
    return {
        "config": analysis_folder / f"00_{cv_id}_project_config.json",
        "status": analysis_folder / f"00_{cv_id}_status.json",
        "log": analysis_folder / f"00_{cv_id}_run_log.csv",
        "inspection": analysis_folder / "inspection",
    }


def eye_folder_name(eye: str) -> str:
    """Folder name used for all files belonging to one original or derived eye."""
    return eye


def eye_rel_path(eye: str, filename: str) -> str:
    return f"{eye_folder_name(eye)}/{filename}"


def eye_inspection_rel_path(eye: str, filename: str) -> str:
    return f"{eye_folder_name(eye)}/inspection/{filename}"


def eye_json_rel_path(eye: str, filename: str) -> str:
    return f"{eye_folder_name(eye)}/json/{filename}"


def eye_log_rel_path(eye: str, filename: str) -> str:
    return f"{eye_folder_name(eye)}/logs/{filename}"


def dataset_json_rel_path(filename: str) -> str:
    return f"json/{filename}"


def dataset_log_rel_path(filename: str) -> str:
    return f"logs/{filename}"

def lightweight_file_size_mb(path: Path) -> Optional[float]:
    """Return file size in MB without opening/parsing the file."""
    try:
        return path.stat().st_size / (1024 * 1024)
    except Exception:
        return None


def legacy_eye_file_map(cv_id: str, eye: str) -> Dict[str, str]:
    """Pre-v0.1.6 flat-layout file names, used only to migrate legacy datasets."""
    return {
        "nrrd_file": f"01_{cv_id}_{eye}.nrrd",
        "imagej_stl_file": f"01_{cv_id}_{eye}_ImageJ.stl",
        "external_stl_file": None,
        "external_stl_original_path": None,
        "external_stl_notes": "",
        "selected_raw_stl_file": None,

        "cornea_blend_file": f"02_{cv_id}_{eye}_cornea.blend",
        "cornea_stl_file": f"02_{cv_id}_{eye}_cornea.stl",
        "blender_step02_task_file": f"02_{cv_id}_{eye}_Blender_task.json",
        "blender_step02_status_file": f"02_{cv_id}_{eye}_Blender_status.json",

        "r_step03a_task_file": f"03A_{cv_id}_{eye}_R_task.json",
        "r_step03a_status_file": f"03A_{cv_id}_{eye}_R_status.json",
        "triangles_normals_file": f"03_{cv_id}_{eye}_triangles_normals.csv",
        "local_heights_file": f"03_{cv_id}_{eye}_local_heights.csv",
        "local_height_threshold_plot": f"inspection/03_{cv_id}_{eye}_local_height_threshold_plot.png",
        "r_step03a2_task_file": f"03A2_{cv_id}_{eye}_R_task.json",
        "r_step03a2_status_file": f"03A2_{cv_id}_{eye}_R_status.json",
        "local_heights_normalized_file": f"03_{cv_id}_{eye}_local_heights_normalized.csv",
        "local_height_normalization_plot": f"inspection/03_{cv_id}_{eye}_local_height_normalization_plot.png",

        "r_step03b_task_file": f"03B_{cv_id}_{eye}_R_task.json",
        "r_step03b_status_file": f"03B_{cv_id}_{eye}_R_status.json",
        "local_height_thresholded_file": f"03_{cv_id}_{eye}_local_height_thresholded.csv",

        "r_step03c_task_file": f"03C_{cv_id}_{eye}_R_task.json",
        "r_step03c_status_file": f"03C_{cv_id}_{eye}_R_status.json",
        "facet_island_distance_matrix_file": f"03_{cv_id}_{eye}_facet_island_distance_matrix.rds",
        "facet_island_distance_matrix_metadata_file": f"03_{cv_id}_{eye}_facet_island_distance_matrix_metadata.json",
        "facet_candidates_file": f"03_{cv_id}_{eye}_facet_candidates.csv",

        "blender_step04_task_file": f"04_{cv_id}_{eye}_Blender_task.json",
        "blender_step04_status_file": f"04_{cv_id}_{eye}_Blender_status.json",
        "facet_positions_file": f"04_{cv_id}_{eye}_facet_positions.csv",
        "facet_check_blend_file": f"02_{cv_id}_{eye}_cornea.blend",

        "r_step05a_task_file": f"05A_{cv_id}_{eye}_R_task.json",
        "r_step05a_status_file": f"05A_{cv_id}_{eye}_R_status.json",
        "facet_sizes_file": f"05_{cv_id}_{eye}_facet_sizes.csv",
        "interfacet_angles_file": f"05_{cv_id}_{eye}_interfacet_angles.csv",
        "sampling_acuity_file": f"05_{cv_id}_{eye}_sensitivity_acuity.csv",
        "optical_summary_file": f"05_{cv_id}_{eye}_optical_summary.csv",

        "r_step05b_task_file": f"05B_{cv_id}_{eye}_R_task.json",
        "r_step05b_status_file": f"05B_{cv_id}_{eye}_R_status.json",
        "landmark_referenced_coordinates_file": f"05B_{cv_id}_{eye}_landmark_referenced_coordinates.csv",
        "global_aligned_pointcloud_file": f"05B_{cv_id}_{eye}_global_aligned_pointcloud.csv",
        "global_coordinates_file": f"05_{cv_id}_{eye}_global_coordinates.csv",
        "global_rotation_matrix_file": f"05_{cv_id}_{eye}_global_rotation_matrix.csv",
        "global_coordinate_metadata_file": f"05_{cv_id}_{eye}_global_coordinate_metadata.json",

        "r_step05c_task_file": f"05C_{cv_id}_{eye}_R_task.json",
        "r_step05c_status_file": f"05C_{cv_id}_{eye}_R_status.json",
        "corneal_projections_file": f"05_{cv_id}_{eye}_corneal_projections.csv",
    }


def eye_file_map(cv_id: str, eye: str) -> Dict[str, str]:
    """Current per-eye folder layout. All eye-specific outputs live below <analysis>/<eye>/."""
    return {
        "nrrd_file": eye_rel_path(eye, f"01_{cv_id}_{eye}.nrrd"),
        "imagej_stl_file": eye_rel_path(eye, f"01_{cv_id}_{eye}_ImageJ.stl"),
        "external_stl_file": None,
        "external_stl_original_path": None,
        "external_stl_notes": "",
        "selected_raw_stl_file": None,

        "cornea_blend_file": eye_rel_path(eye, f"02_{cv_id}_{eye}_cornea.blend"),
        "cornea_stl_file": eye_rel_path(eye, f"02_{cv_id}_{eye}_cornea.stl"),
        "blender_step02_task_file": eye_json_rel_path(eye, f"02_{cv_id}_{eye}_Blender_task.json"),
        "blender_step02_status_file": eye_json_rel_path(eye, f"02_{cv_id}_{eye}_Blender_status.json"),

        "r_step03a_task_file": eye_json_rel_path(eye, f"03A_{cv_id}_{eye}_R_task.json"),
        "r_step03a_status_file": eye_json_rel_path(eye, f"03A_{cv_id}_{eye}_R_status.json"),
        "triangles_normals_file": eye_rel_path(eye, f"03_{cv_id}_{eye}_triangles_normals.csv"),
        "local_heights_file": eye_rel_path(eye, f"03_{cv_id}_{eye}_local_heights.csv"),
        "local_height_threshold_plot": eye_inspection_rel_path(eye, f"03_{cv_id}_{eye}_local_height_threshold_plot.png"),
        "r_step03a2_task_file": eye_json_rel_path(eye, f"03A2_{cv_id}_{eye}_R_task.json"),
        "r_step03a2_status_file": eye_json_rel_path(eye, f"03A2_{cv_id}_{eye}_R_status.json"),
        "local_heights_normalized_file": eye_rel_path(eye, f"03_{cv_id}_{eye}_local_heights_normalized.csv"),
        "local_height_normalization_plot": eye_inspection_rel_path(eye, f"03_{cv_id}_{eye}_local_height_normalization_plot.png"),

        "r_step03b_task_file": eye_json_rel_path(eye, f"03B_{cv_id}_{eye}_R_task.json"),
        "r_step03b_status_file": eye_json_rel_path(eye, f"03B_{cv_id}_{eye}_R_status.json"),
        "local_height_thresholded_file": eye_rel_path(eye, f"03_{cv_id}_{eye}_local_height_thresholded.csv"),

        "r_step03c_task_file": eye_json_rel_path(eye, f"03C_{cv_id}_{eye}_R_task.json"),
        "r_step03c_status_file": eye_json_rel_path(eye, f"03C_{cv_id}_{eye}_R_status.json"),
        "facet_island_distance_matrix_file": eye_rel_path(eye, f"03_{cv_id}_{eye}_facet_island_distance_matrix.rds"),
        "facet_island_distance_matrix_metadata_file": eye_rel_path(eye, f"03_{cv_id}_{eye}_facet_island_distance_matrix_metadata.json"),
        "facet_candidates_file": eye_rel_path(eye, f"03_{cv_id}_{eye}_facet_candidates.csv"),
        "facet_candidates_plot_file": eye_inspection_rel_path(eye, f"03C_{cv_id}_{eye}_facet_candidates_on_local_height.png"),

        "blender_step04_task_file": eye_json_rel_path(eye, f"04_{cv_id}_{eye}_Blender_task.json"),
        "blender_step04_status_file": eye_json_rel_path(eye, f"04_{cv_id}_{eye}_Blender_status.json"),
        "facet_positions_file": eye_rel_path(eye, f"04_{cv_id}_{eye}_facet_positions.csv"),
        "facet_positions_plot_file": eye_inspection_rel_path(eye, f"04_{cv_id}_{eye}_facet_positions_on_local_height.png"),
        "facet_check_blend_file": eye_rel_path(eye, f"02_{cv_id}_{eye}_cornea.blend"),

        "r_step05a_task_file": eye_json_rel_path(eye, f"05A_{cv_id}_{eye}_R_task.json"),
        "r_step05a_status_file": eye_json_rel_path(eye, f"05A_{cv_id}_{eye}_R_status.json"),
        "optic_parameters_file": eye_rel_path(eye, f"05A_{cv_id}_{eye}_optic_parameters.csv"),
        "facet_normals_file": eye_rel_path(eye, f"05A_{cv_id}_{eye}_facet_normals.csv"),
        "facet_sizes_file": eye_rel_path(eye, f"05A_{cv_id}_{eye}_facet_sizes.csv"),
        "interfacet_angles_file": eye_rel_path(eye, f"05A_{cv_id}_{eye}_interfacet_angles.csv"),
        "sampling_acuity_file": eye_rel_path(eye, f"05A_{cv_id}_{eye}_sampling_acuity.csv"),
        "optical_summary_file": eye_rel_path(eye, f"05A_{cv_id}_{eye}_optical_summary.csv"),

        "r_step05b_task_file": eye_json_rel_path(eye, f"05B_{cv_id}_{eye}_R_task.json"),
        "r_step05b_status_file": eye_json_rel_path(eye, f"05B_{cv_id}_{eye}_R_status.json"),
        "landmark_referenced_coordinates_file": eye_rel_path(eye, f"05B_{cv_id}_{eye}_landmark_referenced_coordinates.csv"),
        "global_aligned_pointcloud_file": eye_rel_path(eye, f"05B_{cv_id}_{eye}_global_aligned_pointcloud.csv"),
        "global_coordinates_file": eye_rel_path(eye, f"05B_{cv_id}_{eye}_global_coordinates.csv"),
        "global_rotation_matrix_file": eye_rel_path(eye, f"05B_{cv_id}_{eye}_global_rotation_matrix.csv"),
        "global_coordinate_metadata_file": eye_rel_path(eye, f"05B_{cv_id}_{eye}_global_coordinate_metadata.json"),

        "r_step05c_task_file": eye_json_rel_path(eye, f"05C_{cv_id}_{eye}_R_task.json"),
        "r_step05c_status_file": eye_json_rel_path(eye, f"05C_{cv_id}_{eye}_R_status.json"),
        "corneal_projections_file": eye_rel_path(eye, f"05C_{cv_id}_{eye}_corneal_projections.csv"),
    }


def ensure_eye_subfolders(analysis_folder: Path, eye_ids: Optional[List[str]] = None) -> None:
    for eye in eye_ids or EYES:
        (analysis_folder / eye_folder_name(eye)).mkdir(parents=True, exist_ok=True)
        (analysis_folder / eye_folder_name(eye) / "inspection").mkdir(parents=True, exist_ok=True)


def _move_existing_file_if_needed(analysis_folder: Path, old_rel: Optional[str], new_rel: Optional[str]) -> None:
    if not old_rel or not new_rel or old_rel == new_rel:
        return
    old_path = analysis_folder / old_rel
    new_path = analysis_folder / new_rel
    if old_path.exists() and not new_path.exists():
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_path), str(new_path))


def migrate_config_to_eye_subfolders(analysis_folder: Path, config: Dict[str, Any]) -> bool:
    """Move legacy flat-layout eye files into per-eye folders and update config paths."""
    if not config:
        return False

    cv_id = config.get("dataset_identity", {}).get("cv_id")
    if not cv_id:
        return False

    changed = False
    ensure_eye_subfolders(analysis_folder, EYES)
    config.setdefault("derived_eyes", {})
    config.setdefault("mirroring_history", [])
    config.setdefault("mirrored_outputs", {})
    config["mirrored_outputs"].setdefault("runs", [])

    for eye in EYES:
        config.setdefault("eyes", {}).setdefault(eye, {"present": True, "anatomical_side": "unknown", "notes": "", "files": {}})
        files = config["eyes"][eye].setdefault("files", {})
        # Migrate the pre-0.1.88 internal key without losing existing files.
        if "sensitivity_acuity_file" in files and "sampling_acuity_file" not in files:
            files["sampling_acuity_file"] = files.pop("sensitivity_acuity_file")
            changed = True
        new_defaults = eye_file_map(cv_id, eye)
        old_defaults = legacy_eye_file_map(cv_id, eye)

        # Remember the current selected STL so we can redirect it if that file is moved.
        selected_before = files.get("selected_raw_stl_file")
        selected_after = selected_before

        for key, new_rel in new_defaults.items():
            if key in {"external_stl_file", "external_stl_original_path", "external_stl_notes", "selected_raw_stl_file"}:
                files.setdefault(key, new_rel)
                continue

            old_rel = files.get(key)
            legacy_rel = old_defaults.get(key)
            if old_rel is None:
                files[key] = new_rel
                changed = True
                continue

            should_rewrite = old_rel == legacy_rel or old_rel.startswith("inspection/") or "/" not in old_rel
            if should_rewrite and old_rel != new_rel:
                _move_existing_file_if_needed(analysis_folder, old_rel, new_rel)
                if selected_before == old_rel:
                    selected_after = new_rel
                files[key] = new_rel
                changed = True

        external = files.get("external_stl_file")
        if external and not str(external).startswith(f"{eye}/"):
            new_external = eye_rel_path(eye, Path(str(external)).name)
            _move_existing_file_if_needed(analysis_folder, str(external), new_external)
            if selected_before == external:
                selected_after = new_external
            files["external_stl_file"] = new_external
            changed = True

        if selected_after != selected_before:
            files["selected_raw_stl_file"] = selected_after
            changed = True

    return changed



def source_folder_stl_candidates(raw_folder: Path) -> List[Path]:
    """Return top-level STL files in a source folder, excluding CV3D analysis folders."""
    if not raw_folder.exists() or not raw_folder.is_dir():
        return []
    candidates: List[Path] = []
    for path in raw_folder.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() != ".stl":
            continue
        candidates.append(path)
    return sorted(candidates, key=lambda p: p.name.lower())


def choose_source_stl_for_eye(candidates: List[Path], eye: str, anatomical_side: str = "unknown") -> Optional[Path]:
    """Choose a source-folder STL for one eye.

    STL-source datasets often contain one complete-head STL; in that case the same
    file is used for each present eye. If multiple top-level STLs exist, simple
    filename hints are used before falling back to the first file alphabetically.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    side = (anatomical_side or "unknown").lower()
    eye_tokens = {
        "eye1": ["eye1", "eye_1", "eye-1", "left", "lft"],
        "eye2": ["eye2", "eye_2", "eye-2", "right", "rgt"],
    }.get(eye, [eye])
    if side in {"left", "right"}:
        eye_tokens = [side, *eye_tokens]

    for token in eye_tokens:
        token = token.lower()
        for candidate in candidates:
            if token in candidate.stem.lower():
                return candidate

    return candidates[0]


def assign_source_stls_from_source_folder(
    config: Dict[str, Any],
    analysis_folder: Path,
    force_select: bool = False,
) -> tuple[bool, List[str]]:
    """Copy STL-source input files into present-eye folders and select them for step 02.

    This applies only to non-image-volume datasets. The original STL remains in the
    source folder; each present eye gets its own copied source STL in its eye folder.
    Manual external STL selections are preserved unless force_select=True.
    """
    if not config or not analysis_folder:
        return False, []

    source_type = config.get("source_data", {}).get("source_type", "image_volume")
    if source_type == "image_volume":
        return False, []

    cv_id = config.get("dataset_identity", {}).get("cv_id")
    raw_folder = resolve_config_raw_folder(config, analysis_folder)
    if not cv_id or not raw_folder:
        return False, []

    candidates = source_folder_stl_candidates(raw_folder)
    changed = False
    messages: List[str] = []

    source_data = config.setdefault("source_data", {})
    source_data["source_folder_stl_candidates"] = [str(p) for p in candidates]

    if not candidates:
        source_data["source_folder_stl_assignment_warnings"] = [
            f"No top-level .stl file found in source folder: {raw_folder}"
        ]
        return True, source_data["source_folder_stl_assignment_warnings"]

    active_eyes = config.get("eye_inventory", {}).get("active_eyes") or [
        eye for eye in EYES if config.get("eyes", {}).get(eye, {}).get("present", False)
    ]

    assignment_records: Dict[str, Any] = {}
    for eye in active_eyes:
        if eye not in EYES:
            continue
        eye_info = config.setdefault("eyes", {}).setdefault(eye, {"present": True, "files": {}})
        if not eye_info.get("present", False):
            continue

        files = eye_info.setdefault("files", {})
        source = choose_source_stl_for_eye(candidates, eye, eye_info.get("anatomical_side", "unknown"))
        if source is None:
            continue

        target_rel = eye_rel_path(eye, f"01_{cv_id}_{eye}_source.stl")
        target_path = analysis_folder / target_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not target_path.exists() or target_path.stat().st_size != source.stat().st_size:
            shutil.copyfile(source, target_path)
            changed = True

        previous_source = files.get("source_stl_file")
        previous_source_path = files.get("source_stl_original_path")
        if previous_source != target_rel or previous_source_path != str(source):
            files["source_stl_file"] = target_rel
            files["source_stl_original_path"] = str(source)
            files["source_stl_assignment_notes"] = (
                "Automatically copied from source folder because dataset source_type is STL-based."
            )
            changed = True

        selected = files.get("selected_raw_stl_file")
        selected_exists = bool(selected and (analysis_folder / str(selected)).exists())
        external = files.get("external_stl_file")
        external_exists = bool(external and (analysis_folder / str(external)).exists())
        should_select_source = force_select or not selected_exists or not external_exists
        if should_select_source and selected != target_rel:
            files["selected_raw_stl_file"] = target_rel
            changed = True

        assignment_records[eye] = {
            "source_folder_stl": str(source),
            "copied_to": target_rel,
            "selected_raw_stl_file": files.get("selected_raw_stl_file"),
        }
        messages.append(f"{eye}: assigned source-folder STL {source.name} → {target_rel}")

    source_data["source_folder_stl_assignments"] = assignment_records
    source_data["source_folder_stl_assignment_warnings"] = []
    changed = True if assignment_records else changed
    return changed, messages


def create_initial_config(
    cv_id: str,
    raw_folder: Path,
    analysis_folder: Path,
    project_folder: Path,
    app_settings: Dict[str, Any],
    source_type: str = "image_volume",
    source_notes: str = "",
) -> Dict[str, Any]:
    imagej_required = source_type == "image_volume"

    config = {
        "config_version": "0.3",
        "dataset_identity": {
            "cv_id": cv_id,
            "raw_folder_name": raw_folder.name,
            "raw_folder_path": str(raw_folder),
            "analysis_folder_name": analysis_folder.name,
            "analysis_folder_path": str(analysis_folder),
            "created": now(),
            "dataset_status": "active",
        },
        "registry": {
            "registry_path": str(project_folder / REGISTRY_FILE),
            "registry_entry_confirmed": True,
        },
        "source_data": {
            "source_type": source_type,
            "source_notes": source_notes,
            "imagej_preprocessing_required": imagej_required,
            "imagej_preprocessing_skipped": not imagej_required,
        },
        "raw_data": {
            "raw_data_folder_is_monitored": False,
            "image_unit": "um",
            "voxel_size_x": None,
            "voxel_size_y": None,
            "voxel_size_z": None,
            "voxel_size_unit": "um",
            "notes": "",
        },
        "compute_settings": app_settings.get("compute_settings", detect_recommended_cores()),
        "software_versions": {
            "cv3d_version": APP_VERSION,
            "imagej_version": None,
            "imagej_macro_version": None,
            "blender_version": None,
            "blender_plugin_version": None,
            "r_version": None,
        },
        "eye_inventory": {
            "minimum_required_eye_count": 1,
            "active_eyes": ["eye1", "eye2"],
            "missing_eyes": [],
            "eye_count_warning": False,
        },
        "parameters": {
            "dataset_defaults": {
                "facet_size_estimate": 25.0,
                "local_height_neighbourhood_radius_factor": 0.5,
                "local_height_threshold": 0.5,
                "local_height_normalization_half_width": None,
                "facet_candidate_neighbour_radius_factor": 0.5,
                "facet_candidate_merge_radius_factor": 0.3,
                "facet_candidate_weight_exponent": 2.0,
                "facet_candidate_max_iterations": 8,
                "facet_candidate_step_size": 0.7,
                "facet_candidate_min_cluster_size": 3,
                "facet_candidate_select_point": "nearest_mode",
                "corneal_projection_sphere_size_cm": 15.0,
                "projection_center_mode": "between_eyes",
                "sampling_lattice": "hexagonal",
                "facet_normal_method": "envelope",
                "facet_normal_envelope_factor": 1.25,
            },
            "eye1_last_used": {},
            "eye2_last_used": {},
        },
        "eyes": {},
        "specimen_files": {
            "crop_log_file": f"01_{cv_id}_crop.log",
            "head_mesh_file": f"01_{cv_id}_head_ImageJ.stl",
            "head_landmark_blend_file": f"05_{cv_id}_head_landmarks.blend",
            "head_landmarks_file": f"05_{cv_id}_landmarks.csv",
            "blender_step05_task_file": dataset_json_rel_path(f"05_{cv_id}_Blender_task.json"),
            "blender_step05_status_file": dataset_json_rel_path(f"05_{cv_id}_Blender_status.json"),
        },
        "derived_eyes": {},
        "mirroring_history": [],
        "mirrored_outputs": {
            "enabled": False,
            "created": None,
            "status": "not_created",
            "latest_run": None,
            "runs": [],
        },
        "report_outputs": {
            "analysis_ready_table": {"file": f"06_{cv_id}_facet_level_analysis_ready.csv", "status": "not_created", "last_created": None},
            "eye_summary": {"file": f"06_{cv_id}_eye_summary.csv", "status": "not_created", "last_created": None},
            "specimen_summary": {"file": f"06_{cv_id}_specimen_summary.csv", "status": "not_created", "last_created": None},
            "metadata_json": {"file": f"06_{cv_id}_export_metadata.json", "status": "not_created", "last_created": None},
            "export_manifest": {"file": f"06_{cv_id}_export_manifest.csv", "status": "not_created", "last_created": None},
            "optic_barplots_png": {"file": f"06_{cv_id}_optic_parameter_summary_barplots.png", "status": "not_created", "last_created": None},
            "cp_view_angles_png": {"file": f"06_{cv_id}_corneal_projection_view_angles_acuity.png", "status": "not_created", "last_created": None},
            "qc_pdf_report": {"file": f"06_{cv_id}_analysis_ready_export_QC_report.pdf", "status": "not_created", "last_created": None},
            "html_report": {"file": f"06_{cv_id}_analysis_ready_export_QC_report.html", "status": "not_created", "last_created": None},
            "parameter_summary": {"file": f"06_{cv_id}_parameter_summary.csv", "status": "not_created", "last_created": None},
            "eye_workflow_summary": {"file": f"06_{cv_id}_eye_workflow_summary.csv", "status": "not_created", "last_created": None},
            "pdf_export": {"file": f"06_{cv_id}_analysis_ready_export_QC_report.pdf", "status": "not_exported", "last_exported": None},
            "zip_export": {"file": f"06_{cv_id}_CV3D_analysis_ready_export.zip", "status": "not_exported", "last_exported": None},
        },
        "parameter_history": [],
    }
    for eye in EYES:
        config["eyes"][eye] = {
            "present": True,
            "anatomical_side": "unknown",
            "notes": "",
            "files": eye_file_map(cv_id, eye),
        }
    return config


def create_initial_status(cv_id: str) -> Dict[str, Any]:
    status = {
        "status_version": "0.3",
        "cv_id": cv_id,
        "last_updated": now(),
        "dataset_state": {
            "state": "active",
            "summary": "Dataset active.",
            "warnings": [],
        },
        "eye_inventory": {},
        "workflow_steps": {
            "00_dataset_setup": {
                "label": STEP_LABELS["00_dataset_setup"],
                "state": "complete",
                "symbol": "✓",
                "last_run": now(),
                "needs_rerun": False,
                "messages": [],
            },
            "01_imagej_preprocessing": {
                "label": STEP_LABELS["01_imagej_preprocessing"],
                "state": "not_started",
                "symbol": "○",
                "last_run": None,
                "needs_rerun": False,
                "messages": [],
            },
        }
    }
    for eye in EYES:
        status["eye_inventory"][eye] = {
            "present": True,
            "state": "active",
            "symbol": "✓",
            "messages": [],
        }
    for step in STEP_ORDER:
        status["workflow_steps"][step] = {"label": STEP_LABELS[step]}
        for eye in EYES:
            status["workflow_steps"][step][eye] = {
                "state": "not_started",
                "symbol": "○",
                "last_run": None,
                "needs_rerun": False,
                "messages": [],
            }

    status["workflow_steps"]["05_blender_head_landmarking"] = {
        "label": STEP_LABELS["05_blender_head_landmarking"],
        "state": "not_started",
        "symbol": "○",
        "last_run": None,
        "needs_rerun": False,
        "messages": [],
    }

    status["workflow_steps"]["05d_mirror_missing_eye"] = {
        "label": STEP_LABELS["05d_mirror_missing_eye"],
        "state": "not_created",
        "symbol": "○",
        "source_eye": None,
        "target_eye": None,
        "needs_rerun": False,
        "messages": [],
    }
    status["workflow_steps"]["06_report_export"] = {
        "label": STEP_LABELS["06_report_export"],
        "analysis_ready_export": {"state": "not_created", "symbol": "○", "last_run": None, "needs_rerun": False, "messages": []},
        "html_report": {"state": "not_created", "symbol": "○", "last_run": None, "needs_rerun": False, "messages": []},
        "pdf_export": {"state": "not_exported", "symbol": "○", "last_exported": None, "outdated_export": False, "messages": []},
        "zip_export": {"state": "not_exported", "symbol": "○", "last_exported": None, "outdated_export": False, "messages": []},
    }
    return status


def _rounded_suggested_value(value: Any) -> float:
    """Round generated/default numeric suggestions without limiting user-entered precision."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    nearest_integer = round(number)
    if math.isclose(number, nearest_integer, rel_tol=0.0, abs_tol=1e-12):
        return float(nearest_integer)
    return round(number, 2)


class CompactDoubleSpinBox(QDoubleSpinBox):
    """Double spin box with compact display and high user-entered precision."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(8)

    def textFromValue(self, value: float) -> str:
        text = super().textFromValue(value)
        decimal_point = str(self.locale().decimalPoint())
        if decimal_point and decimal_point in text:
            text = text.rstrip("0").rstrip(decimal_point)
        if text in {"-0", ""}:
            return "0"
        return text

    def setSuggestedValue(self, value: Any) -> None:
        self.setValue(_rounded_suggested_value(value))


def get_compact_double(
    parent,
    title: str,
    label_text: str,
    suggested_value: Any,
    minimum: float,
    maximum: float,
) -> tuple[float, bool]:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    layout = QVBoxLayout(dlg)
    label = QLabel(label_text)
    label.setWordWrap(True)
    layout.addWidget(label)
    spin = CompactDoubleSpinBox()
    spin.setRange(float(minimum), float(maximum))
    spin.setSuggestedValue(suggested_value)
    layout.addWidget(spin)
    buttons = QHBoxLayout()
    ok_button = QPushButton("OK")
    cancel_button = QPushButton("Cancel")
    ok_button.clicked.connect(dlg.accept)
    cancel_button.clicked.connect(dlg.reject)
    buttons.addWidget(ok_button)
    buttons.addWidget(cancel_button)
    layout.addLayout(buttons)
    accepted = dlg.exec() == QDialog.Accepted
    return spin.value(), accepted


class RuntimeParamDialog(QDialog):
    def __init__(self, title: str, fields: Dict[str, float], parent=None,
                 show_force_matrix: bool = False, force_matrix_checked: bool = False,
                 show_projection_center: bool = False,
                 projection_center_default: str = "between_eyes",
                 show_lattice: bool = False, lattice_default: str = "hexagonal",
                 show_normal_method: bool = False,
                 normal_method_default: str = "envelope",
                 normal_envelope_factor_default: float = 1.25,
                 info_text: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.values: Dict[str, Any] = {}
        layout = QVBoxLayout(self)
        if info_text:
            info = QLabel(info_text)
            info.setWordWrap(True)
            layout.addWidget(info)
        form = QFormLayout()
        self.inputs: Dict[str, QDoubleSpinBox] = {}

        for name, value in fields.items():
            spin = CompactDoubleSpinBox()
            spin.setRange(-1_000_000, 1_000_000)
            spin.setSuggestedValue(value if value is not None else 0.0)
            if name == "edge_tol":
                spin.setToolTip(
                    "Controls how permissively local tangent-plane neighbour links are retained before facet size, normals, and interfacet angles are calculated. "
                    "Higher values keep more candidate links; lower values require links to be closer to the local facet spacing."
                )
            self.inputs[name] = spin
            form.addRow(PARAM_DISPLAY_NAMES.get(name, name), spin)

        self.force_matrix = None
        if show_force_matrix:
            self.force_matrix = QCheckBox("Force new distance matrix")
            self.force_matrix.setChecked(force_matrix_checked)
            if force_matrix_checked:
                self.force_matrix.setEnabled(False)
                self.force_matrix.setText("Force new distance matrix (automatic because rerun is required)")
            form.addRow(self.force_matrix)

        self.projection_group = None
        if show_projection_center:
            self.projection_group = QButtonGroup(self)
            center_box = QGroupBox("Projection sphere center")
            v = QVBoxLayout(center_box)
            valid_projection_modes = {"between_eyes", "eye_center", "head_landmark_center"}
            projection_center_default = str(projection_center_default)
            if projection_center_default not in valid_projection_modes:
                projection_center_default = "between_eyes"
            for i, (label, value) in enumerate([
                ("Center between eyes", "between_eyes"),
                ("Current eye center", "eye_center"),
                ("Head landmark center", "head_landmark_center"),
            ]):
                rb = QRadioButton(label)
                rb.setProperty("value", value)
                if value == projection_center_default:
                    rb.setChecked(True)
                self.projection_group.addButton(rb, i)
                v.addWidget(rb)
            form.addRow(center_box)

        self.lattice_combo = None
        if show_lattice:
            self.lattice_combo = QComboBox()
            self.lattice_combo.addItem("Hexagonal", "hexagonal")
            self.lattice_combo.addItem("Square", "square")
            default_index = self.lattice_combo.findData(str(lattice_default).lower())
            self.lattice_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
            self.lattice_combo.setToolTip(
                "Sampling lattice used for Snyder's eye parameter and sampling frequency. "
                "The local anatomical acuity estimate (acuity_cpd) is calculated independently from the interommatidial angle."
            )
            form.addRow("Sampling lattice", self.lattice_combo)

        self.normal_method_combo = None
        if show_normal_method:
            self.normal_method_combo = QComboBox()
            normal_options = [
                ("Original CV3D", "original", None),
                ("Envelope 1×", "envelope", 1.0),
                ("Envelope 1.25×", "envelope", 1.25),
                ("Envelope 1.5×", "envelope", 1.5),
                ("Envelope 2×", "envelope", 2.0),
            ]
            for label, method, factor in normal_options:
                self.normal_method_combo.addItem(label, {"method": method, "factor": factor})

            wanted_method = str(normal_method_default or "envelope").strip().lower()
            try:
                wanted_factor = float(normal_envelope_factor_default)
            except Exception:
                wanted_factor = 1.25
            wanted_index = -1
            for i in range(self.normal_method_combo.count()):
                data = self.normal_method_combo.itemData(i) or {}
                if str(data.get("method", "")) != wanted_method:
                    continue
                if wanted_method == "original":
                    wanted_index = i
                    break
                factor = data.get("factor")
                if factor is not None and abs(float(factor) - wanted_factor) < 1e-9:
                    wanted_index = i
                    break
            if wanted_index < 0:
                wanted_index = 2  # Envelope 1.25×
            self.normal_method_combo.setCurrentIndex(wanted_index)
            self.normal_method_combo.setToolTip(
                "Facet-normal estimator used for inter-facet angles and downstream optical metrics. "
                "Original CV3D uses the focal/neighbour-triangle estimator with subsequent neighbour-normal averaging. "
                "Envelope methods reconstruct a continuous facet-centre envelope, regularise its vertices, and estimate each normal "
                "from area- and distance-weighted nearby envelope-face normals. The multiplier scales the Gaussian weighting width "
                "relative to local facet spacing. Envelope methods do not apply subsequent neighbour-normal averaging."
            )
            form.addRow("Facet-normal method", self.normal_method_combo)

        self.update_default = QCheckBox("Update default after successful run")
        self.update_default.setChecked(True)
        form.addRow(self.update_default)

        layout.addLayout(form)
        buttons = QHBoxLayout()
        run = QPushButton("Run")
        cancel = QPushButton("Cancel")
        run.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(run)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def accept(self):
        self.values = {k: v.value() for k, v in self.inputs.items()}
        self.values["update_default"] = self.update_default.isChecked()
        if self.force_matrix:
            self.values["force_new_distance_matrix"] = self.force_matrix.isChecked()
        if self.projection_group:
            button = self.projection_group.checkedButton()
            self.values["projection_center_mode"] = button.property("value")
        if self.lattice_combo:
            self.values["lattice"] = self.lattice_combo.currentData()
        if self.normal_method_combo:
            data = self.normal_method_combo.currentData() or {}
            self.values["normal_method"] = str(data.get("method", "envelope"))
            self.values["normal_envelope_factor"] = data.get("factor")
        super().accept()


class PlotOptionsDialog(QDialog):
    """Collect all user-selectable QC plot inputs in one dialog."""

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        metric_choices: Optional[List[tuple[str, str]]] = None,
        show_normal_length: bool = False,
        normal_length_default: float = 5.0,
        open_rgl_default: bool = True,
        facet_sphere_scale_default: float = 2.0,
        show_facet_labels_option: bool = False,
        show_facet_labels_default: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.values: Dict[str, Any] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.metric_combo = None
        self.metric_choices = metric_choices or []
        if self.metric_choices:
            self.metric_combo = QComboBox()
            for col, label in self.metric_choices:
                self.metric_combo.addItem(label, col)
            form.addRow("Value", self.metric_combo)

        self.show_facet_labels = None
        if show_facet_labels_option:
            self.show_facet_labels = QCheckBox("Show facet labels")
            self.show_facet_labels.setChecked(bool(show_facet_labels_default))
            self.show_facet_labels.setToolTip("Show facet IDs next to the facet markers/spheres.")
            form.addRow(self.show_facet_labels)

        self.normal_length_spin = None
        if show_normal_length:
            self.normal_length_spin = CompactDoubleSpinBox()
            self.normal_length_spin.setRange(0.0, 1_000_000.0)
            self.normal_length_spin.setSuggestedValue(normal_length_default)
            self.normal_length_spin.setToolTip("Normal-vector length as a multiple of facet size.")
            form.addRow("Normal length × facet size", self.normal_length_spin)

        self.open_rgl = QCheckBox("Open interactive 3D view")
        self.open_rgl.setChecked(bool(open_rgl_default))
        form.addRow(self.open_rgl)

        self.facet_sphere_scale = CompactDoubleSpinBox()
        self.facet_sphere_scale.setRange(0.0, 1000.0)
        self.facet_sphere_scale.setSuggestedValue(facet_sphere_scale_default)
        self.facet_sphere_scale.setToolTip(
            "Facet-sphere diameter scale. 1 = measured facet diameter (dataset estimate used where unavailable); "
            "2 = twice that diameter; 0 = the legacy fixed marker size."
        )
        self.facet_sphere_scale.setEnabled(self.open_rgl.isChecked())
        self.open_rgl.toggled.connect(self.facet_sphere_scale.setEnabled)
        form.addRow("Facet-sphere diameter scale", self.facet_sphere_scale)

        layout.addLayout(form)

        note = QLabel(
            "Facet-sphere scaling applies to the interactive 3D view. "
            "A value of 0 reproduces the previous fixed marker size."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QHBoxLayout()
        run = QPushButton("Plot")
        cancel = QPushButton("Cancel")
        run.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(run)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def accept(self):
        open_rgl = self.open_rgl.isChecked()
        self.values = {
            "open_rgl_window": open_rgl,
            "facet_sphere_scale": float(self.facet_sphere_scale.value()) if open_rgl else 0.0,
        }
        if self.metric_combo is not None:
            idx = self.metric_combo.currentIndex()
            self.values["selected_metric_col"] = str(self.metric_combo.currentData() or "")
            self.values["selected_metric_label"] = str(self.metric_combo.currentText() or "")
        if self.show_facet_labels is not None:
            self.values["show_facet_labels"] = bool(self.show_facet_labels.isChecked())
        if self.normal_length_spin is not None:
            self.values["normal_length_facet_size_factor"] = float(self.normal_length_spin.value())
        super().accept()


class NormalPlotOptionsDialog(QDialog):
    """Collect the normal-specific display inputs after Normals is selected."""

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        normal_length_default: float = 5.0,
        show_normals_default: bool = True,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.values: Dict[str, Any] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.normal_length_spin = CompactDoubleSpinBox()
        self.normal_length_spin.setRange(0.0, 1_000_000.0)
        self.normal_length_spin.setSuggestedValue(normal_length_default)
        self.normal_length_spin.setToolTip("Normal-vector length as a multiple of facet size.")
        form.addRow("Normal length × facet size", self.normal_length_spin)

        self.show_normals = QCheckBox("Show normal vectors")
        self.show_normals.setChecked(bool(show_normals_default))
        self.show_normals.setToolTip(
            "If unchecked, the plot keeps the direction-coloured facet points/spheres but omits the normal vectors."
        )
        self.show_normals.toggled.connect(self.normal_length_spin.setEnabled)
        form.addRow(self.show_normals)

        layout.addLayout(form)

        note = QLabel("Facet colours still encode normal direction when the vectors are hidden.")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QHBoxLayout()
        run = QPushButton("Plot")
        cancel = QPushButton("Cancel")
        run.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(run)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def accept(self):
        self.values = {
            "normal_length_facet_size_factor": float(self.normal_length_spin.value()),
            "show_normals": bool(self.show_normals.isChecked()),
        }
        super().accept()


class CreateDatasetDialog(QDialog):
    """Collect the raw-folder and source metadata in one dataset-creation dialog."""

    def __init__(self, initial_folder: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create CV3D dataset")
        self.values: Dict[str, Any] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit(str(initial_folder or ""))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse)
        folder_widget = QWidget()
        folder_widget.setLayout(folder_row)
        form.addRow("Raw/source folder", folder_widget)

        self.source_type_combo = QComboBox()
        for value in ["image_volume", "stl_from_3d_scanner", "stl_from_web", "stl_external_other"]:
            self.source_type_combo.addItem(value, value)
        form.addRow("Source type", self.source_type_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional source-data notes")
        self.notes_edit.setMinimumHeight(90)
        form.addRow("Source notes", self.notes_edit)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        create = QPushButton("Create")
        cancel = QPushButton("Cancel")
        create.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(create)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def browse_folder(self):
        start = self.folder_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select raw dataset/source folder", start)
        if folder:
            self.folder_edit.setText(folder)

    def accept(self):
        raw_folder = self.folder_edit.text().strip()
        if not raw_folder:
            QMessageBox.warning(self, "Raw/source folder missing", "Select a raw/source folder first.")
            return
        path = Path(raw_folder)
        if not path.exists() or not path.is_dir():
            QMessageBox.warning(self, "Invalid raw/source folder", "The selected raw/source folder does not exist.")
            return
        self.values = {
            "raw_folder": str(path),
            "source_type": str(self.source_type_combo.currentData()),
            "source_notes": self.notes_edit.toPlainText(),
        }
        super().accept()


class LocalHeightThresholdDialog(QDialog):
    """First 03B prompt: choose raw/normalized source and min/max preview thresholds."""

    def __init__(
        self,
        title: str,
        raw_label: str,
        normalized_label: str,
        normalized_available: bool,
        default_normalized: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.values: Dict[str, Any] = {}

        layout = QVBoxLayout(self)

        source_box = QGroupBox("Input table for local-height thresholding")
        source_layout = QVBoxLayout(source_box)
        self.source_group = QButtonGroup(self)

        self.raw_radio = QRadioButton("Raw local heights")
        self.raw_radio.setProperty("value", "raw_local_heights")
        source_layout.addWidget(self.raw_radio)
        source_layout.addWidget(QLabel(raw_label))

        self.norm_radio = QRadioButton("Normalized local heights")
        self.norm_radio.setProperty("value", "normalized_local_heights")
        self.norm_radio.setEnabled(normalized_available)
        source_layout.addWidget(self.norm_radio)
        norm_detail = QLabel(normalized_label if normalized_available else normalized_label + "  [not available]")
        norm_detail.setEnabled(normalized_available)
        source_layout.addWidget(norm_detail)

        self.source_group.addButton(self.raw_radio, 0)
        self.source_group.addButton(self.norm_radio, 1)

        if normalized_available and default_normalized:
            self.norm_radio.setChecked(True)
        else:
            self.raw_radio.setChecked(True)

        layout.addWidget(source_box)

        form = QFormLayout()

        self.min_threshold_spin = CompactDoubleSpinBox()
        self.min_threshold_spin.setRange(-1_000_000, 1_000_000)
        form.addRow("minimum threshold for preview", self.min_threshold_spin)

        self.max_threshold_spin = CompactDoubleSpinBox()
        self.max_threshold_spin.setRange(-1_000_000, 1_000_000)
        form.addRow("maximum threshold for preview", self.max_threshold_spin)

        layout.addLayout(form)

        note = QLabel(
            "A viridis-coloured eye preview will be created before the final threshold is set. "
            "Both raw-derived and normalized contrast scales run from 0 to 1."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self.source_group.buttonClicked.connect(self.apply_mode_defaults)
        self.apply_mode_defaults()

        buttons = QHBoxLayout()
        run = QPushButton("Create preview")
        cancel = QPushButton("Cancel")
        run.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(run)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def current_mode(self) -> str:
        return self.source_group.checkedButton().property("value")

    def apply_mode_defaults(self):
        self.min_threshold_spin.setSuggestedValue(0.0)
        self.max_threshold_spin.setSuggestedValue(1.0)

    def accept(self):
        mode = self.current_mode()
        column = "local_height_norm_contrast" if mode == "normalized_local_heights" else "local_height_contrast"

        min_threshold = self.min_threshold_spin.value()
        max_threshold = self.max_threshold_spin.value()

        if min_threshold > max_threshold:
            QMessageBox.warning(
                self,
                "Invalid threshold range",
                "The minimum threshold must be smaller than or equal to the maximum threshold."
            )
            return

        self.values = {
            "input_mode": mode,
            "height_column": column,
            "min_threshold": min_threshold,
            "max_threshold": max_threshold,
        }
        super().accept()


class FinalThresholdDialog(QDialog):
    """Second 03B prompt: set the final threshold after inspecting the preview plot."""

    def __init__(self, title: str, suggested_threshold: float, min_threshold: float, max_threshold: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.values: Dict[str, Any] = {}

        layout = QVBoxLayout(self)

        info = QLabel(
            "Inspect the opened local-height preview, then set the final threshold. "
            "This final value is used to create the thresholded point cloud."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.threshold_spin = CompactDoubleSpinBox()
        self.threshold_spin.setRange(float(min_threshold), float(max_threshold))

        if suggested_threshold is None:
            suggested_threshold = (float(min_threshold) + float(max_threshold)) / 2
        self.threshold_spin.setSuggestedValue(suggested_threshold)

        form.addRow("final local-height threshold", self.threshold_spin)

        self.update_default = QCheckBox("Update defaults after successful run")
        self.update_default.setChecked(True)
        form.addRow(self.update_default)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        run = QPushButton("Threshold")
        cancel = QPushButton("Cancel")
        run.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(run)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def accept(self):
        self.values = {
            "local_height_threshold": self.threshold_spin.value(),
            "update_default": self.update_default.isChecked(),
        }
        super().accept()


class FacetCandidateCondensationDialog(QDialog):
    """Prompt for 03C local mode-condensation parameters."""

    def __init__(
        self,
        title: str,
        facet_size_estimate: float,
        suggested: Dict[str, Any],
        max_cores: int,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.values: Dict[str, Any] = {}

        layout = QVBoxLayout(self)

        info = QLabel(
            "03C uses the package function find_facet_candidates_condensed(). "
            "It condenses thresholded local-height points into one candidate point per local mode."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()

        self.neighbour_radius_spin = CompactDoubleSpinBox()
        self.neighbour_radius_spin.setRange(0.000001, 1_000_000)
        self.neighbour_radius_spin.setSuggestedValue(suggested.get("neighbour_radius", facet_size_estimate * 0.5))
        form.addRow("neighbour radius", self.neighbour_radius_spin)

        self.merge_radius_spin = CompactDoubleSpinBox()
        self.merge_radius_spin.setRange(0.000001, 1_000_000)
        self.merge_radius_spin.setSuggestedValue(suggested.get("merge_radius", facet_size_estimate * 0.3))
        form.addRow("merge radius", self.merge_radius_spin)

        self.weight_exponent_spin = CompactDoubleSpinBox()
        self.weight_exponent_spin.setRange(0.0, 20.0)
        self.weight_exponent_spin.setSuggestedValue(suggested.get("weight_exponent", 2.0))
        form.addRow("height-weight exponent", self.weight_exponent_spin)

        self.max_iterations_spin = QSpinBox()
        self.max_iterations_spin.setRange(1, 1000)
        self.max_iterations_spin.setValue(int(suggested.get("max_iterations", 8)))
        form.addRow("maximum iterations", self.max_iterations_spin)

        self.step_size_spin = CompactDoubleSpinBox()
        self.step_size_spin.setRange(0.000001, 1.0)
        self.step_size_spin.setSuggestedValue(suggested.get("step_size", 0.7))
        form.addRow("step size", self.step_size_spin)

        self.min_cluster_size_spin = QSpinBox()
        self.min_cluster_size_spin.setRange(1, 1_000_000)
        self.min_cluster_size_spin.setValue(int(suggested.get("min_cluster_size", 3)))
        form.addRow("minimum group size", self.min_cluster_size_spin)

        self.cores_spin = QSpinBox()
        self.cores_spin.setRange(1, 1024)
        self.cores_spin.setValue(int(suggested.get("cores", max(1, max_cores))))
        form.addRow("cores", self.cores_spin)

        self.select_point_combo = QComboBox()
        self.select_point_combo.addItem("nearest mode point", "nearest_mode")
        self.select_point_combo.addItem("maximum-height point", "max_height")
        current_select = str(suggested.get("select_point", "nearest_mode"))
        idx = self.select_point_combo.findData(current_select)
        self.select_point_combo.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow("candidate point selection", self.select_point_combo)

        self.update_default = QCheckBox("Update defaults after successful run")
        self.update_default.setChecked(True)
        form.addRow(self.update_default)

        layout.addLayout(form)

        note = QLabel(
            f"Facet-size estimate: {facet_size_estimate:g}. "
            "Good starting values are neighbour radius ≈ 0.5× facet diameter and merge radius ≈ 0.3× facet diameter."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QHBoxLayout()
        run = QPushButton("Condense")
        cancel = QPushButton("Cancel")
        run.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(run)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def accept(self):
        self.values = {
            "neighbour_radius": self.neighbour_radius_spin.value(),
            "merge_radius": self.merge_radius_spin.value(),
            "weight_exponent": self.weight_exponent_spin.value(),
            "max_iterations": self.max_iterations_spin.value(),
            "step_size": self.step_size_spin.value(),
            "min_cluster_size": self.min_cluster_size_spin.value(),
            "cores": self.cores_spin.value(),
            "select_point": self.select_point_combo.currentData(),
            "update_default": self.update_default.isChecked(),
        }
        super().accept()


class CV3DMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CV3D")
        self.resize(980, 760)

        self.settings = load_app_settings()
        self.project_folder: Optional[Path] = None
        self.analysis_folder: Optional[Path] = None
        self.config: Optional[Dict[str, Any]] = None
        self.status: Optional[Dict[str, Any]] = None
        self.registry: Optional[Dict[str, Any]] = None
        self._updating_dataset_selector = False

        central = QWidget()
        root = QHBoxLayout(central)

        self.nav = QListWidget()
        self.nav.setFixedWidth(180)
        self.nav.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        for label in ["Project Manager", "Dataset Setup", "ImageJ / Source", "Eye Workflow", "R Analysis", "Mirroring", "Results / Export", "Settings"]:
            QListWidgetItem(label, self.nav)
        self.nav.currentRowChanged.connect(self.change_page)

        self.process_wait_label = QLabel("Waiting for process…")
        self.process_wait_label.setWordWrap(True)
        self.process_wait_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.process_wait_label.setStyleSheet(
            "font-weight: 600; padding: 8px; border: 1px solid #b8b8b8; border-radius: 4px;"
        )
        self.process_wait_label.hide()

        left_widget = QWidget()
        left_widget.setFixedWidth(180)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(self.nav, 1)
        left_layout.addWidget(self.process_wait_label, 0)

        self.dataset_selector = QComboBox()
        self.dataset_selector.setMinimumWidth(220)
        self.dataset_selector.addItem("No project/dataset loaded", None)
        self.dataset_selector.currentIndexChanged.connect(self.on_dataset_selector_changed)

        self.reload_registry_button = QPushButton("Reload registry")
        self.reload_registry_button.clicked.connect(self.reload_registry_from_disk)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Current dataset"))
        top_bar.addWidget(self.dataset_selector, 1)
        top_bar.addWidget(self.reload_registry_button)

        self.pages = QStackedWidget()
        self.project_page = self.make_project_page()
        self.dataset_page = self.make_dataset_page()
        self.imagej_page = self.make_imagej_page()
        self.workflow_page = self.make_workflow_page()
        self.r_analysis_page = self.make_r_analysis_page()
        self.mirror_page = self.make_mirror_page()
        self.report_page = self.make_report_page()
        self.settings_page = self.make_settings_page()

        for page in [self.project_page, self.dataset_page, self.imagej_page, self.workflow_page, self.r_analysis_page, self.mirror_page, self.report_page, self.settings_page]:
            self.pages.addWidget(page)

        # Keep the working area at a practical width. Without this cap, Qt
        # stretches every workflow button and the console/status panes across
        # ultra-wide windows, making the eye workflow harder to use.
        right_widget = QWidget()
        right_widget.setMaximumWidth(860)
        right_widget.setMinimumWidth(640)
        right_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        right_panel = QVBoxLayout(right_widget)
        right_panel.setContentsMargins(6, 6, 6, 6)
        right_panel.addLayout(top_bar)
        right_panel.addWidget(self.pages, 1)

        root.addWidget(left_widget)
        root.addWidget(right_widget)
        root.addStretch(1)
        self.setCentralWidget(central)
        self.nav.setCurrentRow(0)

    def set_waiting_for_process(self, waiting: bool) -> None:
        """Show a visible status immediately before a blocking external process."""
        self.process_wait_label.setVisible(bool(waiting))
        QApplication.processEvents()

    def run_blocking_process(self, *args, **kwargs):
        """Run an external process while making the UI's blocking state explicit."""
        self.set_waiting_for_process(True)
        try:
            return subprocess.run(*args, **kwargs)
        finally:
            self.set_waiting_for_process(False)

    # ---------- UI builders ----------

    def make_project_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.project_label = QLabel("Project folder: none")
        layout.addWidget(self.project_label)

        row = QHBoxLayout()
        btn_open = QPushButton("Open / create project folder")
        btn_open.clicked.connect(self.open_project)
        row.addWidget(btn_open)

        btn_dataset = QPushButton("Create new CV dataset from raw folder")
        btn_dataset.clicked.connect(self.create_dataset)
        row.addWidget(btn_dataset)

        btn_refresh = QPushButton("Reload registry")
        btn_refresh.clicked.connect(self.reload_registry_from_disk)
        row.addWidget(btn_refresh)
        layout.addLayout(row)

        self.registry_view = QTextEdit()
        self.registry_view.setReadOnly(True)
        layout.addWidget(self.registry_view, 1)
        return w

    def make_dataset_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.dataset_summary = QLabel("No dataset loaded.")
        layout.addWidget(self.dataset_summary)

        source_box = QGroupBox("Source data")
        form = QFormLayout(source_box)
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems(["image_volume", "stl_from_3d_scanner", "stl_from_web", "stl_external_other"])
        self.source_notes = QTextEdit()
        self.source_notes.setPlaceholderText("Free text: source details, scanner/web source, scale notes, preprocessing, etc.")
        form.addRow("Source type", self.source_type_combo)
        form.addRow("Raw-data / source notes", self.source_notes)
        layout.addWidget(source_box)

        eyes_box = QGroupBox("Eye inventory")
        grid = QGridLayout(eyes_box)
        self.eye_present = {}
        self.eye_side = {}
        self.eye_notes = {}
        for r, eye in enumerate(EYES):
            cb = QCheckBox(f"{eye} present")
            side = QComboBox()
            side.addItems(["unknown", "left", "right"])
            notes = QLineEdit()
            self.eye_present[eye] = cb
            self.eye_side[eye] = side
            self.eye_notes[eye] = notes
            grid.addWidget(cb, r, 0)
            grid.addWidget(QLabel("Anatomical side"), r, 1)
            grid.addWidget(side, r, 2)
            grid.addWidget(QLabel("Notes"), r, 3)
            grid.addWidget(notes, r, 4)
        layout.addWidget(eyes_box)

        row = QHBoxLayout()
        save = QPushButton("Save dataset metadata / eye inventory")
        save.clicked.connect(self.save_dataset_metadata)
        row.addWidget(save)
        open_analysis = QPushButton("Open analysis folder")
        open_analysis.clicked.connect(self.open_analysis_folder)
        row.addWidget(open_analysis)
        layout.addLayout(row)
        layout.addStretch(1)
        return w

    def make_imagej_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.imagej_summary = QLabel("No dataset loaded.")
        layout.addWidget(self.imagej_summary)

        row = QHBoxLayout()

        run_real = QPushButton("Preprocess image volume")
        run_real.clicked.connect(self.launch_imagej_preprocessing)
        row.addWidget(run_real)

        run_mesh = QPushButton("Extract STL meshes")
        run_mesh.clicked.connect(self.launch_imagej_mesh_extraction)
        row.addWidget(run_mesh)

        check = QPushButton("Check ImageJ/source outputs")
        check.clicked.connect(self.check_imagej_source_outputs)
        row.addWidget(check)
        layout.addLayout(row)

        self.imagej_check_report = QTextEdit()
        self.imagej_check_report.setReadOnly(True)
        self.imagej_check_report.setMinimumHeight(140)
        self.imagej_check_report.setPlainText("Click 'Check ImageJ/source outputs' to validate expected source files for the current dataset.")
        layout.addWidget(QLabel("Source/output check report"))
        layout.addWidget(self.imagej_check_report)

        self.external_stl_boxes: Dict[str, Dict[str, Any]] = {}
        for eye in EYES:
            box = QGroupBox(f"{eye} STL source")
            form = QFormLayout(box)
            label = QLabel("No dataset loaded.")
            notes = QTextEdit()
            notes.setPlaceholderText("External STL notes (coordinates are assumed to be in µm)")
            browse = QPushButton(f"Browse and copy external STL: {eye}")
            browse.clicked.connect(lambda _, e=eye, n=notes: self.copy_external_stl(e, n.toPlainText()))
            form.addRow("Status", label)
            form.addRow("External STL notes", notes)
            form.addRow(browse)
            self.external_stl_boxes[eye] = {"box": box, "label": label, "notes": notes, "browse": browse}
            layout.addWidget(box)

        layout.addStretch(1)
        return w

    def make_workflow_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.workflow_summary = QLabel("No dataset loaded.")
        layout.addWidget(self.workflow_summary)

        validate_row = QHBoxLayout()
        validate_btn = QPushButton("Validate workflow outputs")
        validate_btn.clicked.connect(self.show_workflow_validation_report)
        validate_row.addWidget(validate_btn)
        validate_row.addStretch(1)
        layout.addLayout(validate_row)

        grid = QGridLayout()
        self.workflow_labels: Dict[str, Dict[str, QLabel]] = {eye: {} for eye in EYES}
        self.workflow_buttons: Dict[str, Dict[str, QPushButton]] = {eye: {} for eye in EYES}
        self.threshold_plot_buttons: Dict[str, QPushButton] = {}
        self.raw_local_height_3d_plot_buttons: Dict[str, QPushButton] = {}
        self.local_height_3d_plot_buttons: Dict[str, QPushButton] = {}
        self.facet_candidate_plot_buttons: Dict[str, QPushButton] = {}
        self.facet_position_plot_buttons: Dict[str, QPushButton] = {}

        for col, eye in enumerate(EYES):
            eye_box = QGroupBox(f"{eye} workflow")
            v = QVBoxLayout(eye_box)

            button_specs = [
                ("02_blender_cornea_extraction", "Extract cornea", self.launch_blender_cornea_extraction),
                ("03a_local_height_calculation", "Calculate local heights", self.launch_r_03a_local_heights),
                ("03a2_local_height_normalization", "Normalize local heights (optional)", self.launch_r_03a2_normalize_local_heights),
                ("03b_local_height_thresholding", "Threshold local heights", self.launch_r_03b_local_height_thresholding),
                ("03c_facet_candidate_condensation", "Condense facet candidates", self.launch_r_03c_facet_candidate_condensation),
                ("04_blender_facet_check_landmarking", "Check facet positions", self.launch_blender_facet_position_checking),
            ]
            for step, text, func in button_specs:
                label = QLabel(f"{STEP_LABELS[step]}: ○ not started")
                label.setWordWrap(True)
                btn = QPushButton(f"{text}: {eye}")
                btn.clicked.connect(lambda _, e=eye, s=step, f=func: f(e))
                self.workflow_labels[eye][step] = label
                self.workflow_buttons[eye][step] = btn
                v.addWidget(label)
                v.addWidget(btn)

            plot_separator = QFrame()
            plot_separator.setFrameShape(QFrame.Shape.HLine)
            plot_separator.setFrameShadow(QFrame.Shadow.Sunken)
            v.addSpacing(6)
            v.addWidget(plot_separator)

            plot_header = QLabel("Inspection plots")
            plot_header.setStyleSheet("font-weight: 600; margin-top: 2px;")
            v.addWidget(plot_header)

            plot_btn = QPushButton(f"View local-height threshold plot: {eye}")
            plot_btn.clicked.connect(lambda _, e=eye: self.create_threshold_plot(e))
            self.threshold_plot_buttons[eye] = plot_btn
            v.addWidget(plot_btn)

            raw_plot3d_btn = QPushButton(f"Plot raw local heights 3D (PNG + optional rgl): {eye}")
            raw_plot3d_btn.clicked.connect(lambda _, e=eye: self.plot_raw_local_heights_3d(e))
            self.raw_local_height_3d_plot_buttons[eye] = raw_plot3d_btn
            v.addWidget(raw_plot3d_btn)

            plot3d_btn = QPushButton(f"Plot normalized local heights 3D (PNG + optional rgl): {eye}")
            plot3d_btn.clicked.connect(lambda _, e=eye: self.plot_local_heights_3d(e))
            self.local_height_3d_plot_buttons[eye] = plot3d_btn
            v.addWidget(plot3d_btn)

            thresholded_plot3d_btn = QPushButton(f"Plot thresholded local-height points 3D: {eye}")
            thresholded_plot3d_btn.clicked.connect(lambda _, e=eye: self.plot_thresholded_local_heights_3d(e))
            if not hasattr(self, "thresholded_local_height_3d_plot_buttons"):
                self.thresholded_local_height_3d_plot_buttons = {}
            self.thresholded_local_height_3d_plot_buttons[eye] = thresholded_plot3d_btn
            v.addWidget(thresholded_plot3d_btn)

            facet_candidates_plot_btn = QPushButton(f"Plot facet candidates on local heights: {eye}")
            facet_candidates_plot_btn.clicked.connect(lambda _, e=eye: self.plot_facet_points_on_local_heights(e, "facet_candidates"))
            self.facet_candidate_plot_buttons[eye] = facet_candidates_plot_btn
            v.addWidget(facet_candidates_plot_btn)

            facet_positions_plot_btn = QPushButton(f"Plot facet positions on local heights: {eye}")
            facet_positions_plot_btn.clicked.connect(lambda _, e=eye: self.plot_facet_points_on_local_heights(e, "facet_positions"))
            self.facet_position_plot_buttons[eye] = facet_positions_plot_btn
            v.addWidget(facet_positions_plot_btn)

            grid.addWidget(eye_box, 0, col)
        layout.addLayout(grid)

        specimen_box = QGroupBox("Specimen-level workflow")
        specimen_layout = QVBoxLayout(specimen_box)
        self.head_landmark_status_label = QLabel(f"{STEP_LABELS['05_blender_head_landmarking']}: ○ not started")
        self.head_landmark_button = QPushButton("Set head landmarks")
        self.head_landmark_button.clicked.connect(self.launch_blender_head_landmarking)
        specimen_layout.addWidget(self.head_landmark_status_label)
        specimen_layout.addWidget(self.head_landmark_button)
        layout.addWidget(specimen_box)

        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_panel.setMinimumWidth(0)
        left_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Console output / latest task logs"))
        self.console_output = QTextEdit()
        self.console_output.setMinimumWidth(0)
        self.console_output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.console_output.setReadOnly(True)
        self.console_output.setPlaceholderText(
            "Console output from the most recent R task will appear here. "
            "For now, logs are refreshed after the task finishes and when the workflow page refreshes."
        )
        left_layout.addWidget(self.console_output, 1)

        right_panel = QWidget()
        right_panel.setMinimumWidth(0)
        right_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Messages / status JSON preview"))
        self.messages = QTextEdit()
        self.messages.setMinimumWidth(0)
        self.messages.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.messages.setReadOnly(True)
        right_layout.addWidget(self.messages, 1)

        bottom_splitter.addWidget(left_panel)
        bottom_splitter.addWidget(right_panel)
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 1)
        bottom_splitter.setSizes([1, 1])
        layout.addWidget(bottom_splitter, 1)
        return w

    def make_r_analysis_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.r_analysis_summary = QLabel("No dataset loaded.")
        self.r_analysis_summary.setWordWrap(True)
        layout.addWidget(self.r_analysis_summary)

        note = QLabel(
            "Run downstream R analyses after checked facet positions are available. "
            "05A is eye-specific and does not require head landmarks. 05B and 05C are also eye-specific; 05B uses the specimen-level landmarks for global alignment."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        grid = QGridLayout()
        self.r_analysis_labels: Dict[str, Dict[str, QLabel]] = {eye: {} for eye in EYES}
        self.r_analysis_buttons: Dict[str, Dict[str, QPushButton]] = {eye: {} for eye in EYES}
        self.r_analysis_button_reason_labels: Dict[str, Dict[str, QLabel]] = {eye: {} for eye in EYES}
        self.r_analysis_plot_buttons: Dict[str, Dict[str, QPushButton]] = {eye: {} for eye in EYES}

        analysis_specs = [
            ("05a_optical_metrics", "05A · Optical metrics", self.launch_r_05a_optical_metrics),
            ("05b_global_coordinate_rotation", "05B · Align coordinates", self.launch_r_05b_global_coordinate_rotation),
            ("05c_corneal_projections", "05C · Corneal projections", self.launch_r_05c_corneal_projections),
        ]

        for col, eye in enumerate(EYES):
            eye_box = QGroupBox(f"{eye} R analysis")
            v = QVBoxLayout(eye_box)

            for step, button_text, func in analysis_specs:
                label = QLabel(f"{STEP_LABELS[step]}: ○ not started")
                label.setWordWrap(True)
                btn = QPushButton(button_text)
                btn.clicked.connect(lambda _, e=eye, f=func: f(e))
                reason_label = QLabel("")
                reason_label.setWordWrap(True)
                reason_label.setStyleSheet("color: #7a3b00; font-size: 11px; margin-left: 8px;")
                reason_label.hide()
                self.r_analysis_labels[eye][step] = label
                self.r_analysis_buttons[eye][step] = btn
                self.r_analysis_button_reason_labels[eye][step] = reason_label
                v.addWidget(label)
                v.addWidget(btn)
                v.addWidget(reason_label)

            plot_separator = QFrame()
            plot_separator.setFrameShape(QFrame.Shape.HLine)
            plot_separator.setFrameShadow(QFrame.Shadow.Sunken)
            v.addSpacing(6)
            v.addWidget(plot_separator)

            plot_header = QLabel("Inspection plots")
            plot_header.setStyleSheet("font-weight: 600; margin-top: 2px;")
            v.addWidget(plot_header)

            plot_header_05a = QLabel("05A optical-metric inspection")
            plot_header_05a.setStyleSheet("font-weight: 600; margin-top: 2px;")
            v.addWidget(plot_header_05a)

            optics_plot_btn = QPushButton("Optics overview")
            optics_plot_btn.setToolTip("05A optical-metric overview (PNG; optional interactive rgl).")
            optics_plot_btn.clicked.connect(lambda _, e=eye: self.plot_05a_outputs(e, "optics"))
            self.r_analysis_plot_buttons[eye]["optics"] = optics_plot_btn
            v.addWidget(optics_plot_btn)

            labelled_metric_btn = QPushButton("Choose facet value")
            labelled_metric_btn.setToolTip("Choose a 05A facet value or normal direction and create its QC plot.")
            labelled_metric_btn.clicked.connect(lambda _, e=eye: self.plot_05a_outputs(e, "labelled_metric"))
            self.r_analysis_plot_buttons[eye]["labelled_metric"] = labelled_metric_btn
            v.addWidget(labelled_metric_btn)

            plot_header_05b = QLabel("05B global-alignment inspection")
            plot_header_05b.setStyleSheet("font-weight: 600; margin-top: 6px;")
            v.addWidget(plot_header_05b)

            align_qc_btn = QPushButton("Alignment")
            align_qc_btn.setToolTip("05B global-alignment QC (PNG; optional interactive rgl).")
            align_qc_btn.clicked.connect(lambda _, e=eye: self.plot_05b_qc_outputs(e))
            self.r_analysis_plot_buttons[eye]["05b_qc"] = align_qc_btn
            v.addWidget(align_qc_btn)

            plot_header_05c = QLabel("05C corneal-projection inspection")
            plot_header_05c.setStyleSheet("font-weight: 600; margin-top: 6px;")
            v.addWidget(plot_header_05c)

            projection_qc_btn = QPushButton("Corneal projection")
            projection_qc_btn.setToolTip("05C corneal-projection QC (PNGs; optional interactive rgl).")
            projection_qc_btn.clicked.connect(lambda _, e=eye: self.plot_05c_qc_outputs(e))
            self.r_analysis_plot_buttons[eye]["05c_qc"] = projection_qc_btn
            v.addWidget(projection_qc_btn)

            v.addStretch(1)
            grid.addWidget(eye_box, 0, col)

        layout.addLayout(grid)

        combined_box = QGroupBox("Combined two-eye QC plots")
        combined_layout = QVBoxLayout(combined_box)
        self.r_analysis_combined_05b_btn = QPushButton("Alignment · both eyes")
        self.r_analysis_combined_05b_btn.clicked.connect(lambda: self.plot_05b_qc_outputs(self.preferred_eye_for_combined_qc(), combined=True))
        self.r_analysis_combined_05c_btn = QPushButton("Corneal projection · both eyes")
        self.r_analysis_combined_05c_btn.clicked.connect(lambda: self.plot_05c_qc_outputs(self.preferred_eye_for_combined_qc(), combined=True))
        combined_layout.addWidget(self.r_analysis_combined_05b_btn)
        combined_layout.addWidget(self.r_analysis_combined_05c_btn)
        layout.addWidget(combined_box)

        layout.addStretch(1)
        return w

    def make_mirror_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.mirror_summary = QLabel("No dataset loaded.")
        layout.addWidget(self.mirror_summary)

        controls = QGroupBox("Create mirrored eye outputs")
        form = QFormLayout(controls)

        self.mirror_source_combo = QComboBox()
        self.mirror_target_combo = QComboBox()
        self.mirror_source_combo.currentIndexChanged.connect(self.update_mirror_target_default)
        form.addRow("Source original eye", self.mirror_source_combo)
        form.addRow("Target eye to overwrite/fill", self.mirror_target_combo)

        self.mirror_plane_group = QButtonGroup(self)
        plane_box = QWidget()
        plane_row = QHBoxLayout(plane_box)
        plane_row.setContentsMargins(0, 0, 0, 0)
        for i, (label, value) in enumerate([
            ("XY plane", "xy"),
            ("YZ plane", "yz"),
            ("XZ plane", "xz"),
        ]):
            rb = QRadioButton(label)
            rb.setProperty("value", value)
            if value == "yz":
                rb.setChecked(True)
            self.mirror_plane_group.addButton(rb, i)
            plane_row.addWidget(rb)
        plane_row.addStretch(1)
        form.addRow("Mirror plane", plane_box)

        self.mirror_button = QPushButton("Create mirrored eye outputs")
        self.mirror_button.clicked.connect(self.create_mirrored_outputs)
        form.addRow(self.mirror_button)

        layout.addWidget(controls)

        self.mirror_report = QTextEdit()
        self.mirror_report.setReadOnly(True)
        self.mirror_report.setMinimumHeight(180)
        self.mirror_report.setPlainText("No mirrored outputs created in this session.")
        layout.addWidget(QLabel("Mirroring report"))
        layout.addWidget(self.mirror_report, 1)
        return w

    def make_report_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        title = QLabel("Results / Export")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Analysis-ready outputs and QC report"))

        self.report_summary = QLabel("No dataset loaded.")
        self.report_summary.setWordWrap(True)
        layout.addWidget(self.report_summary)

        readiness_box = QGroupBox("Export readiness")
        readiness_layout = QVBoxLayout(readiness_box)
        self.export_readiness_text = QTextEdit()
        self.export_readiness_text.setReadOnly(True)
        self.export_readiness_text.setMinimumHeight(150)
        readiness_layout.addWidget(self.export_readiness_text)
        layout.addWidget(readiness_box)

        outputs_box = QGroupBox("Generate outputs")
        outputs_layout = QVBoxLayout(outputs_box)
        self.analysis_ready_export_button = QPushButton("Generate analysis-ready tables")
        self.analysis_ready_export_button.clicked.connect(self.generate_analysis_ready_export)
        outputs_layout.addWidget(self.analysis_ready_export_button)
        self.qc_pdf_report_button = QPushButton("Generate QC PDF report")
        self.qc_pdf_report_button.clicked.connect(self.generate_qc_pdf_report)
        outputs_layout.addWidget(self.qc_pdf_report_button)
        self.create_export_zip_button = QPushButton("Create export ZIP")
        self.create_export_zip_button.clicked.connect(self.export_zip)
        outputs_layout.addWidget(self.create_export_zip_button)
        self.open_export_folder_button = QPushButton("Open final export folder")
        self.open_export_folder_button.clicked.connect(self.open_export_folder)
        outputs_layout.addWidget(self.open_export_folder_button)
        layout.addWidget(outputs_box)

        options_box = QGroupBox("Report options")
        options_layout = QVBoxLayout(options_box)
        self.report_include_summary_table = QCheckBox("Include specimen and eye summary tables")
        self.report_include_summary_table.setChecked(True)
        self.report_include_05b_qc = QCheckBox("Include 05B global-coordinate QC plots (combined and eye-wise)")
        self.report_include_05b_qc.setChecked(True)
        self.report_include_cp_plots = QCheckBox("Include 05C corneal-projection QC plots (combined and eye-wise)")
        self.report_include_cp_plots.setChecked(True)
        self.report_include_optic_barplots = QCheckBox("Include 05A optic-parameter summaries and distributions")
        self.report_include_optic_barplots.setChecked(True)
        self.report_include_downstream_examples = QCheckBox("Include additional elevation/azimuth maps for optic parameters")
        self.report_include_downstream_examples.setChecked(True)
        self.report_create_fresh_rgl_snapshots = QCheckBox("Regenerate 05C rgl snapshot PNGs for the report")
        self.report_create_fresh_rgl_snapshots.setChecked(True)
        for cb in [self.report_include_summary_table, self.report_include_05b_qc, self.report_include_cp_plots, self.report_include_optic_barplots, self.report_include_downstream_examples, self.report_create_fresh_rgl_snapshots]:
            options_layout.addWidget(cb)
        layout.addWidget(options_box)

        files_box = QGroupBox("Output files")
        files_layout = QVBoxLayout(files_box)
        self.report_output_files_text = QTextEdit()
        self.report_output_files_text.setReadOnly(True)
        self.report_output_files_text.setMinimumHeight(160)
        files_layout.addWidget(self.report_output_files_text)
        layout.addWidget(files_box, 1)
        return w

    def make_settings_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.settings_summary = QLabel("")
        layout.addWidget(self.settings_summary)

        helper_row = QHBoxLayout()
        auto_helpers = QPushButton("Use bundled helper scripts")
        auto_helpers.clicked.connect(self.use_bundled_helper_scripts)
        helper_row.addWidget(auto_helpers)
        helper_row.addStretch(1)
        layout.addLayout(helper_row)

        form = QFormLayout()
        self.max_cores_spin = QSpinBox()
        self.max_cores_spin.setRange(1, 1024)
        self.max_cores_spin.setValue(int(self.settings["compute_settings"]["max_cores"]))
        form.addRow("Max cores to use", self.max_cores_spin)

        self.imagej_executable_edit = QLineEdit()
        self.imagej_executable_edit.setText(self.settings.get("imagej_executable", ""))
        imagej_exe_row = QHBoxLayout()
        imagej_exe_row.addWidget(self.imagej_executable_edit, 1)
        browse_imagej_exe = QPushButton("Browse")
        browse_imagej_exe.clicked.connect(self.browse_imagej_executable)
        imagej_exe_row.addWidget(browse_imagej_exe)
        form.addRow("ImageJ/Fiji executable", imagej_exe_row)

        self.imagej_macro_edit = QLineEdit()
        self.imagej_macro_edit.setText(self.settings.get("imagej_macro_path", ""))
        imagej_macro_row = QHBoxLayout()
        imagej_macro_row.addWidget(self.imagej_macro_edit, 1)
        browse_imagej_macro = QPushButton("Browse")
        browse_imagej_macro.clicked.connect(self.browse_imagej_macro)
        imagej_macro_row.addWidget(browse_imagej_macro)
        form.addRow("CV3D ImageJ preprocessing macro", imagej_macro_row)

        self.imagej_mesh_macro_edit = QLineEdit()
        self.imagej_mesh_macro_edit.setText(self.settings.get("imagej_mesh_macro_path", ""))
        imagej_mesh_macro_row = QHBoxLayout()
        imagej_mesh_macro_row.addWidget(self.imagej_mesh_macro_edit, 1)
        browse_imagej_mesh_macro = QPushButton("Browse")
        browse_imagej_mesh_macro.clicked.connect(self.browse_imagej_mesh_macro)
        imagej_mesh_macro_row.addWidget(browse_imagej_mesh_macro)
        form.addRow("CV3D ImageJ mesh/STL extraction macro", imagej_mesh_macro_row)

        self.blender_executable_edit = QLineEdit()
        self.blender_executable_edit.setText(self.settings.get("blender_executable", ""))
        blender_exe_row = QHBoxLayout()
        blender_exe_row.addWidget(self.blender_executable_edit, 1)
        browse_blender_exe = QPushButton("Browse")
        browse_blender_exe.clicked.connect(self.browse_blender_executable)
        blender_exe_row.addWidget(browse_blender_exe)
        form.addRow("Blender executable", blender_exe_row)

        self.blender_script_edit = QLineEdit()
        self.blender_script_edit.setText(self.settings.get("blender_script_path", ""))
        blender_script_row = QHBoxLayout()
        blender_script_row.addWidget(self.blender_script_edit, 1)
        browse_blender_script = QPushButton("Browse")
        browse_blender_script.clicked.connect(self.browse_blender_script)
        blender_script_row.addWidget(browse_blender_script)
        form.addRow("CV3D Blender helper script", blender_script_row)

        self.rscript_executable_edit = QLineEdit()
        self.rscript_executable_edit.setText(self.settings.get("rscript_executable", ""))
        rscript_row = QHBoxLayout()
        rscript_row.addWidget(self.rscript_executable_edit, 1)
        browse_rscript = QPushButton("Browse")
        browse_rscript.clicked.connect(self.browse_rscript_executable)
        rscript_row.addWidget(browse_rscript)
        form.addRow("Rscript executable", rscript_row)

        self.r_github_repo_edit = QLineEdit()
        self.r_github_repo_edit.setText(self.settings.get("r_github_repo", "Pete-s-Lab/CV3D"))
        r_repo_row = QHBoxLayout()
        r_repo_row.addWidget(self.r_github_repo_edit, 1)
        check_r_setup = QPushButton("Check R setup")
        check_r_setup.clicked.connect(self.check_r_setup)
        r_repo_row.addWidget(check_r_setup)
        install_r_package = QPushButton("Install/update from GitHub")
        install_r_package.clicked.connect(self.install_or_update_r_package_from_github)
        r_repo_row.addWidget(install_r_package)
        form.addRow("CV3D R package GitHub repo", r_repo_row)

        self.r_step03a_script_edit = QLineEdit()
        self.r_step03a_script_edit.setText(self.settings.get("r_step03a_script_path", ""))
        r_step03a_row = QHBoxLayout()
        r_step03a_row.addWidget(self.r_step03a_script_edit, 1)
        browse_r_step03a = QPushButton("Browse")
        browse_r_step03a.clicked.connect(self.browse_r_step03a_script)
        r_step03a_row.addWidget(browse_r_step03a)
        form.addRow("CV3D R Step 03A runner", r_step03a_row)

        self.r_step03a2_script_edit = QLineEdit()
        self.r_step03a2_script_edit.setText(self.settings.get("r_step03a2_script_path", ""))
        r_step03a2_row = QHBoxLayout()
        r_step03a2_row.addWidget(self.r_step03a2_script_edit, 1)
        browse_r_step03a2 = QPushButton("Browse")
        browse_r_step03a2.clicked.connect(self.browse_r_step03a2_script)
        r_step03a2_row.addWidget(browse_r_step03a2)
        form.addRow("CV3D R Step 03A2 normalization runner", r_step03a2_row)

        self.r_step03a_plot_script_edit = QLineEdit()
        self.r_step03a_plot_script_edit.setText(self.settings.get("r_step03a_plot_script_path", ""))
        r_step03a_plot_row = QHBoxLayout()
        r_step03a_plot_row.addWidget(self.r_step03a_plot_script_edit, 1)
        browse_r_step03a_plot = QPushButton("Browse")
        browse_r_step03a_plot.clicked.connect(self.browse_r_step03a_plot_script)
        r_step03a_plot_row.addWidget(browse_r_step03a_plot)
        form.addRow("CV3D R raw local-height 3D plot runner", r_step03a_plot_row)

        self.r_step03a2_plot_script_edit = QLineEdit()
        self.r_step03a2_plot_script_edit.setText(self.settings.get("r_step03a2_plot_script_path", ""))
        r_step03a2_plot_row = QHBoxLayout()
        r_step03a2_plot_row.addWidget(self.r_step03a2_plot_script_edit, 1)
        browse_r_step03a2_plot = QPushButton("Browse")
        browse_r_step03a2_plot.clicked.connect(self.browse_r_step03a2_plot_script)
        r_step03a2_plot_row.addWidget(browse_r_step03a2_plot)
        form.addRow("CV3D R normalized local-height 3D plot runner", r_step03a2_plot_row)

        self.r_step03b_script_edit = QLineEdit()
        self.r_step03b_script_edit.setText(self.settings.get("r_step03b_script_path", ""))
        r_step03b_row = QHBoxLayout()
        r_step03b_row.addWidget(self.r_step03b_script_edit, 1)
        browse_r_step03b = QPushButton("Browse")
        browse_r_step03b.clicked.connect(self.browse_r_step03b_script)
        r_step03b_row.addWidget(browse_r_step03b)
        form.addRow("CV3D R Step 03B thresholding runner", r_step03b_row)

        self.r_step03b_plot_script_edit = QLineEdit()
        self.r_step03b_plot_script_edit.setText(self.settings.get("r_step03b_plot_script_path", ""))
        r_step03b_plot_row = QHBoxLayout()
        r_step03b_plot_row.addWidget(self.r_step03b_plot_script_edit, 1)
        browse_r_step03b_plot = QPushButton("Browse")
        browse_r_step03b_plot.clicked.connect(self.browse_r_step03b_plot_script)
        r_step03b_plot_row.addWidget(browse_r_step03b_plot)
        form.addRow("CV3D R thresholded local-height 3D plot runner", r_step03b_plot_row)

        self.r_step03c_script_edit = QLineEdit()
        self.r_step03c_script_edit.setText(self.settings.get("r_step03c_script_path", ""))
        r_step03c_row = QHBoxLayout()
        r_step03c_row.addWidget(self.r_step03c_script_edit, 1)
        browse_r_step03c = QPushButton("Browse")
        browse_r_step03c.clicked.connect(self.browse_r_step03c_script)
        r_step03c_row.addWidget(browse_r_step03c)
        form.addRow("CV3D R Step 03C candidate condensation runner", r_step03c_row)

        self.r_step05a_script_edit = QLineEdit()
        self.r_step05a_script_edit.setText(self.settings.get("r_step05a_script_path", ""))
        r_step05a_row = QHBoxLayout()
        r_step05a_row.addWidget(self.r_step05a_script_edit, 1)
        browse_r_step05a = QPushButton("Browse")
        browse_r_step05a.clicked.connect(self.browse_r_step05a_script)
        r_step05a_row.addWidget(browse_r_step05a)
        form.addRow("CV3D R Step 05A optic metrics runner", r_step05a_row)

        self.r_step05b_script_edit = QLineEdit()
        self.r_step05b_script_edit.setText(self.settings.get("r_step05b_script_path", ""))
        r_step05b_row = QHBoxLayout()
        r_step05b_row.addWidget(self.r_step05b_script_edit, 1)
        browse_r_step05b = QPushButton("Browse")
        browse_r_step05b.clicked.connect(self.browse_r_step05b_script)
        r_step05b_row.addWidget(browse_r_step05b)
        form.addRow("CV3D R Step 05B global alignment runner", r_step05b_row)

        self.r_step05c_script_edit = QLineEdit()
        self.r_step05c_script_edit.setText(self.settings.get("r_step05c_script_path", ""))
        r_step05c_row = QHBoxLayout()
        r_step05c_row.addWidget(self.r_step05c_script_edit, 1)
        browse_r_step05c = QPushButton("Browse")
        browse_r_step05c.clicked.connect(self.browse_r_step05c_script)
        r_step05c_row.addWidget(browse_r_step05c)
        form.addRow("CV3D R Step 05C corneal projection runner", r_step05c_row)

        self.r_step05a_qc_plot_script_edit = QLineEdit()
        self.r_step05a_qc_plot_script_edit.setText(self.settings.get("r_step05a_qc_plot_script_path", ""))
        r_step05a_qc_row = QHBoxLayout()
        r_step05a_qc_row.addWidget(self.r_step05a_qc_plot_script_edit, 1)
        browse_r_step05a_qc = QPushButton("Browse")
        browse_r_step05a_qc.clicked.connect(self.browse_r_step05a_qc_plot_script)
        r_step05a_qc_row.addWidget(browse_r_step05a_qc)
        form.addRow("CV3D R 05A QC plot runner", r_step05a_qc_row)

        self.r_step05b_qc_plot_script_edit = QLineEdit()
        self.r_step05b_qc_plot_script_edit.setText(self.settings.get("r_step05b_qc_plot_script_path", ""))
        r_step05b_qc_row = QHBoxLayout()
        r_step05b_qc_row.addWidget(self.r_step05b_qc_plot_script_edit, 1)
        browse_r_step05b_qc = QPushButton("Browse")
        browse_r_step05b_qc.clicked.connect(self.browse_r_step05b_qc_plot_script)
        r_step05b_qc_row.addWidget(browse_r_step05b_qc)
        form.addRow("CV3D R 05B QC plot runner", r_step05b_qc_row)

        self.r_step05c_qc_plot_script_edit = QLineEdit()
        self.r_step05c_qc_plot_script_edit.setText(self.settings.get("r_step05c_qc_plot_script_path", ""))
        r_step05c_qc_row = QHBoxLayout()
        r_step05c_qc_row.addWidget(self.r_step05c_qc_plot_script_edit, 1)
        browse_r_step05c_qc = QPushButton("Browse")
        browse_r_step05c_qc.clicked.connect(self.browse_r_step05c_qc_plot_script)
        r_step05c_qc_row.addWidget(browse_r_step05c_qc)
        form.addRow("CV3D R 05C QC plot runner", r_step05c_qc_row)

        self.r_facet_point_plot_script_edit = QLineEdit()
        self.r_facet_point_plot_script_edit.setText(self.settings.get("r_facet_point_plot_script_path", ""))
        r_facet_point_plot_row = QHBoxLayout()
        r_facet_point_plot_row.addWidget(self.r_facet_point_plot_script_edit, 1)
        browse_r_facet_point_plot = QPushButton("Browse")
        browse_r_facet_point_plot.clicked.connect(self.browse_r_facet_point_plot_script)
        r_facet_point_plot_row.addWidget(browse_r_facet_point_plot)
        form.addRow("CV3D R facet point overlay plot runner", r_facet_point_plot_row)

        layout.addLayout(form)

        save = QPushButton("Save settings")
        save.clicked.connect(self.save_settings)
        layout.addWidget(save)
        layout.addStretch(1)
        self.refresh_settings_page()
        return w

    # ---------- navigation / refresh ----------

    def change_page(self, row: int) -> None:
        self.pages.setCurrentIndex(row)
        self.refresh_all()

    def refresh_all(self) -> None:
        if self.ensure_workflow_schema_current():
            self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_dataset_selector()
        self.refresh_project_page()
        self.refresh_dataset_page()
        self.refresh_imagej_page()
        self.refresh_workflow_page()
        self.refresh_r_analysis_page()
        self.refresh_mirror_page()
        self.refresh_report_page()
        self.refresh_settings_page()

    def refresh_dataset_selector(self) -> None:
        """Populate the global dataset selector from the project registry."""
        if not hasattr(self, "dataset_selector"):
            return

        self._updating_dataset_selector = True
        try:
            current_cv_id = None
            if self.config:
                current_cv_id = self.config.get("dataset_identity", {}).get("cv_id")

            self.dataset_selector.clear()

            if not self.project_folder or not self.registry:
                self.dataset_selector.addItem("No project/dataset loaded", None)
                self.dataset_selector.setEnabled(False)
                return

            datasets = self.registry.get("datasets", [])
            if not datasets:
                self.dataset_selector.addItem("No datasets in current project", None)
                self.dataset_selector.setEnabled(False)
                return

            self.dataset_selector.setEnabled(True)
            selected_index = 0
            for i, entry in enumerate(datasets):
                cv_id = entry.get("cv_id", "UNKNOWN")
                raw_name = entry.get("raw_folder_name", "unnamed raw folder")
                status = entry.get("status", "unknown")
                analysis = entry.get("analysis_folder", "")
                label = f"{cv_id} — {raw_name} — {status}"
                self.dataset_selector.addItem(label, cv_id)
                self.dataset_selector.setItemData(i, analysis, Qt.ItemDataRole.ToolTipRole)
                if cv_id == current_cv_id:
                    selected_index = i

            self.dataset_selector.setCurrentIndex(selected_index)
        finally:
            self._updating_dataset_selector = False

    def on_dataset_selector_changed(self, index: int) -> None:
        if self._updating_dataset_selector:
            return
        cv_id = self.dataset_selector.itemData(index)
        if not cv_id:
            return
        self.load_dataset_by_cv_id(str(cv_id))

    def load_dataset_by_cv_id(self, cv_id: str) -> bool:
        """Load config/status files for a dataset listed in the project registry."""
        if not self.registry:
            return False

        entry = next((d for d in self.registry.get("datasets", []) if d.get("cv_id") == cv_id), None)
        if entry is None:
            QMessageBox.warning(self, "Dataset not found", f"{cv_id} is not listed in the current project registry.")
            return False

        analysis_folder = resolve_registry_entry_analysis_folder(self.project_folder, entry)
        config_path = analysis_folder / f"00_{cv_id}_project_config.json"
        status_path = analysis_folder / f"00_{cv_id}_status.json"

        if not analysis_folder.exists() or not config_path.exists() or not status_path.exists():
            recovered = find_dataset_file_pair(self.project_folder, cv_id, analysis_folder)
            if recovered is not None:
                analysis_folder = recovered["analysis_folder"]
                config_path = recovered["config_path"]
                status_path = recovered["status_path"]
                try:
                    entry["analysis_folder"] = os.path.relpath(str(analysis_folder), str(self.project_folder))
                    self.registry["last_modified"] = now()
                    write_json(self.project_folder / REGISTRY_FILE, self.registry)
                except Exception:
                    pass
            else:
                QMessageBox.warning(
                    self,
                    "Dataset files missing",
                    "Could not find both required dataset files.\n\n"
                    f"Expected:\n{config_path}\n{status_path}\n\n"
                    f"Also searched below project folder:\n{self.project_folder}"
                )
                return False

        self.analysis_folder = analysis_folder
        self.config = read_json(config_path)
        self.status = read_json(status_path)
        schema_changed = self.ensure_workflow_schema_current()
        layout_changed = migrate_config_to_eye_subfolders(self.analysis_folder, self.config)
        stl_changed, _ = assign_source_stls_from_source_folder(self.config, self.analysis_folder, force_select=False)
        recovered_states = self.rebuild_workflow_states_from_existing_outputs()
        if schema_changed or layout_changed or stl_changed or recovered_states:
            self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()
        return True

    def reload_registry_from_disk(self) -> None:
        if not self.project_folder:
            QMessageBox.information(self, "No project", "Open or create a project folder first.")
            return

        self.registry = load_or_create_registry(self.project_folder)

        # Keep the current dataset selected if it still exists. Otherwise load the first dataset.
        current_cv_id = None
        if self.config:
            current_cv_id = self.config.get("dataset_identity", {}).get("cv_id")

        datasets = self.registry.get("datasets", [])
        ids = [d.get("cv_id") for d in datasets]
        if current_cv_id in ids:
            self.load_dataset_by_cv_id(current_cv_id)
        elif datasets:
            first_cv_id = datasets[0].get("cv_id")
            if first_cv_id:
                self.load_dataset_by_cv_id(first_cv_id)
        else:
            self.analysis_folder = None
            self.config = None
            self.status = None
            self.refresh_all()

    def refresh_project_page(self) -> None:
        if self.project_folder:
            self.project_label.setText(f"Project folder: {self.project_folder}")
            if self.registry:
                self.registry_view.setPlainText(json.dumps(self.registry, indent=2))
        else:
            self.project_label.setText("Project folder: none")
            self.registry_view.setPlainText("Open or create a project folder first.")

    def refresh_dataset_page(self) -> None:
        if not self.config:
            self.dataset_summary.setText("No dataset loaded.")
            return
        ident = self.config["dataset_identity"]
        inv = self.config["eye_inventory"]
        self.dataset_summary.setText(
            f"{ident['cv_id']} — raw folder: {ident['raw_folder_name']} — "
            f"active eyes: {', '.join(inv['active_eyes']) or 'none'}"
        )
        self.source_type_combo.setCurrentText(self.config["source_data"]["source_type"])
        self.source_notes.setPlainText(self.config["source_data"].get("source_notes", ""))
        for eye in EYES:
            e = self.config["eyes"][eye]
            self.eye_present[eye].setChecked(bool(e["present"]))
            self.eye_side[eye].setCurrentText(e.get("anatomical_side") or "unknown")
            self.eye_notes[eye].setText(e.get("notes", ""))

    def refresh_imagej_page(self) -> None:
        if not self.config or not self.analysis_folder:
            self.imagej_summary.setText("No dataset loaded.")
            if hasattr(self, "imagej_check_report"):
                self.imagej_check_report.setPlainText("No dataset loaded.")
            return
        src = self.config["source_data"]
        if src["imagej_preprocessing_skipped"]:
            self.imagej_summary.setText("ImageJ preprocessing skipped: dataset starts from STL source.")
        else:
            self.imagej_summary.setText("ImageJ preprocessing active for image-volume source.")

        for eye, widgets in self.external_stl_boxes.items():
            present = self.config["eyes"][eye]["present"]
            files = self.config["eyes"][eye]["files"]
            selected = files.get("selected_raw_stl_file")
            imagej_stl = files.get("imagej_stl_file")
            source_stl = files.get("source_stl_file")
            imagej_exists = (self.analysis_folder / imagej_stl).exists() if imagej_stl else False
            source_exists = (self.analysis_folder / source_stl).exists() if source_stl else False
            widgets["label"].setText(
                f"present={present}; ImageJ STL exists={imagej_exists}; source STL exists={source_exists}; selected={selected}"
            )
            widgets["box"].setEnabled(present)

    def check_imagej_source_outputs(self) -> None:
        """Show a visible validation report for ImageJ or external-STL source files."""
        if not self.config or not self.analysis_folder:
            QMessageBox.information(self, "No dataset", "No dataset loaded.")
            return

        # Re-read config/status in case files were created or edited outside the UI.
        self.load_current_files()
        stl_changed, stl_assignment_messages = assign_source_stls_from_source_folder(self.config, self.analysis_folder, force_select=False)
        if stl_changed:
            self.save_current_files()

        cv_id = self.config["dataset_identity"]["cv_id"]
        source_type = self.config["source_data"]["source_type"]
        imagej_skipped = bool(self.config["source_data"].get("imagej_preprocessing_skipped", False))
        imagej_state = self.status["workflow_steps"]["01_imagej_preprocessing"]["state"]

        lines = []
        warnings = []

        def status_for(rel_path: Optional[str]) -> str:
            if not rel_path:
                return "not set"
            return "OK" if (self.analysis_folder / rel_path).exists() else "MISSING"

        def add_file(label: str, rel_path: Optional[str], critical: bool = False) -> None:
            state = status_for(rel_path)
            suffix = f" — {rel_path}" if rel_path else ""
            if rel_path and state == "OK" and str(rel_path).lower().endswith(".stl"):
                size_mb = lightweight_file_size_mb(self.analysis_folder / rel_path)
                if size_mb is not None:
                    suffix += f" ({size_mb:.1f} MB; lightweight existence/size check only)"
            lines.append(f"{label}: {state}{suffix}")
            if critical and state != "OK":
                warnings.append(f"{label} is {state}.")

        lines.append(f"Dataset: {cv_id}")
        lines.append(f"Analysis folder: {self.analysis_folder}")
        lines.append(f"Source type: {source_type}")
        lines.append(f"ImageJ preprocessing state: {imagej_state}")
        lines.append(f"ImageJ preprocessing skipped: {imagej_skipped}")
        lines.append("")

        if not imagej_skipped:
            add_file("Head ROI NRRD", f"01_{cv_id}_head.nrrd", critical=imagej_state == "complete")
            add_file("Head ImageJ STL", self.config.get("specimen_files", {}).get("head_mesh_file", f"01_{cv_id}_head_ImageJ.stl"), critical=False)
            add_file("Facet-size estimate CSV", f"01_{cv_id}_facet_size_estimate.csv", critical=imagej_state == "complete")
            lines.append("")
        else:
            lines.append("ImageJ outputs are not expected for this source type.")
            candidates = self.config.get("source_data", {}).get("source_folder_stl_candidates", [])
            warnings_from_assignment = self.config.get("source_data", {}).get("source_folder_stl_assignment_warnings", [])
            lines.append(f"Source-folder STL candidates: {len(candidates)}")
            for candidate in candidates:
                lines.append(f"  - {candidate}")
            if stl_assignment_messages:
                lines.append("Source-folder STL assignments:")
                lines.extend(f"  - {msg}" for msg in stl_assignment_messages)
            if warnings_from_assignment:
                warnings.extend(warnings_from_assignment)
            lines.append("")

        active_eyes = self.config["eye_inventory"].get("active_eyes", [])
        if not active_eyes:
            warnings.append("No active eye is currently marked as present.")

        for eye in EYES:
            present = bool(self.config["eyes"][eye]["present"])
            files = self.config["eyes"][eye]["files"]
            lines.append(f"{eye}:")
            lines.append(f"  present: {present}")
            if not present:
                lines.append("  skipped because this eye is marked missing")
                lines.append("")
                continue

            if not imagej_skipped:
                add_file(f"  {eye} ImageJ NRRD", files.get("nrrd_file"), critical=imagej_state == "complete")
                add_file(f"  {eye} ImageJ STL", files.get("imagej_stl_file"), critical=imagej_state == "complete")
            else:
                add_file(f"  {eye} source-folder STL copy", files.get("source_stl_file"), critical=True)
                original_source = files.get("source_stl_original_path")
                if original_source:
                    lines.append(f"  {eye} source-folder STL original: {original_source}")

            external = files.get("external_stl_file")
            if external:
                add_file(f"  {eye} external STL", external, critical=False)
            else:
                lines.append(f"  {eye} external STL: not set")

            selected = files.get("selected_raw_stl_file")
            add_file(f"  {eye} selected raw STL for step 02", selected, critical=True)
            lines.append("")

        if warnings:
            lines.append("Result: CHECK HAS WARNINGS")
            lines.extend(f"- {w}" for w in warnings)
        else:
            lines.append("Result: OK — all currently required source files are present.")

        report = "\n".join(lines)
        self.imagej_check_report.setPlainText(report)
        self.refresh_imagej_page()
        self.imagej_check_report.setPlainText(report)
        QMessageBox.information(self, "ImageJ/source output check", report)

    def latest_console_log_text(self) -> str:
        """Return a compact console view from the newest task log files on disk."""
        if not self.config or not self.analysis_folder:
            return "No dataset loaded."

        log_candidates: List[Path] = []

        # Prioritize known R stdout/stderr and launch-command logs.
        for pattern in [
            "**/logs/*_R_launch_command.txt",
            "**/logs/*_R_stdout.log",
            "**/logs/*_R_stderr.log",
            # Also tolerate older flat eye-folder logs from pre-v0.1.23 projects.
            "*/03A*_R_launch_command.txt",
            "*/03A*_R_stdout.log",
            "*/03A*_R_stderr.log",
            "*/03A2*_R_launch_command.txt",
            "*/03A2*_R_stdout.log",
            "*/03A2*_R_stderr.log",
            "*/03A2P*_R_launch_command.txt",
            "*/03A2P*_R_stdout.log",
            "*/03A2P*_R_stderr.log",
            "*/03AP*_R_launch_command.txt",
            "*/03AP*_R_stdout.log",
            "*/03AP*_R_stderr.log",
        ]:
            log_candidates.extend(self.analysis_folder.glob(pattern))

        log_candidates = [p for p in log_candidates if p.is_file()]
        if not log_candidates:
            return (
                "No task console logs found yet.\n\n"
                "Run 03A or 03A2 to create stdout/stderr and launch-command logs."
            )

        # Show the newest few files together, because stdout/stderr/launch command belong together.
        log_candidates = sorted(log_candidates, key=lambda p: p.stat().st_mtime, reverse=True)
        newest_time = log_candidates[0].stat().st_mtime

        # Keep logs from approximately the same run where possible, then cap to a readable set.
        selected = [p for p in log_candidates if abs(p.stat().st_mtime - newest_time) < 10]
        if len(selected) < 2:
            selected = log_candidates[:4]
        else:
            selected = selected[:6]

        # Sort selected files in a useful order: command, stdout, stderr.
        order = {"launch_command": 0, "stdout": 1, "stderr": 2}
        def sort_key(path: Path) -> tuple[int, str]:
            name = path.name.lower()
            rank = 9
            for token, value in order.items():
                if token in name:
                    rank = value
                    break
            return (rank, name)

        selected = sorted(selected, key=sort_key)

        chunks = []
        for path in selected:
            rel = path.relative_to(self.analysis_folder)
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                content = f"[Could not read log file: {e}]"

            if not content.strip():
                content = "[empty]"

            # Avoid freezing the UI on huge logs.
            max_chars = 20000
            if len(content) > max_chars:
                content = content[-max_chars:]
                content = "[... log truncated to last 20000 characters ...]\n" + content

            chunks.append(f"===== {rel} =====\n{content.rstrip()}\n")

        return "\n".join(chunks).rstrip()


    def refresh_workflow_page(self) -> None:
        if not self.config or not self.status:
            self.workflow_summary.setText("No dataset loaded.")
            self.messages.setPlainText("")
            if hasattr(self, "console_output"):
                self.console_output.setPlainText("No dataset loaded.")
            return
        mirrored_actual = [eye for eye in EYES if self.config.get("eyes", {}).get(eye, {}).get("mirrored")]
        mirror_note = ""
        if mirrored_actual:
            mirror_note = " — mirrored eye(s): " + ", ".join(mirrored_actual)
        self.workflow_summary.setText(
            f"{self.config['dataset_identity']['cv_id']} workflow — "
            f"source: {self.config['source_data']['source_type']}" + mirror_note
        )

        for eye in EYES:
            present = self.config["eyes"][eye]["present"]
            for step in STEP_ORDER:
                # Some future workflow steps still exist in the status/config
                # schema, but are intentionally hidden until their real
                # implementation replaces the legacy placeholders.
                if step not in self.workflow_labels.get(eye, {}):
                    continue

                s = self.status["workflow_steps"][step][eye]
                self.workflow_labels[eye][step].setText(
                    f"{STEP_LABELS[step]}: {s['symbol']} {s['state']}"
                )
                input_problems = self.step_input_problems(step, eye) if present else [f"{eye} not present in scan."]
                if step in self.workflow_buttons.get(eye, {}):
                    self.workflow_buttons[eye][step].setEnabled(present and not input_problems)
                    self.workflow_buttons[eye][step].setToolTip("\n".join(input_problems) if input_problems else "Ready to run or rerun.")

            if hasattr(self, "threshold_plot_buttons") and eye in self.threshold_plot_buttons:
                plot_btn = self.threshold_plot_buttons[eye]
                plot_rel = self.config["eyes"][eye]["files"].get("local_height_threshold_plot")
                plot_path = self.analysis_folder / plot_rel if plot_rel else None
                raw_state = self.status["workflow_steps"]["03a_local_height_calculation"][eye].get("state")
                ready = present and raw_state in ["complete", "complete_with_warning"] and plot_path is not None and plot_path.exists()
                plot_btn.setEnabled(ready)
                if ready:
                    plot_btn.setToolTip("Open the existing 03A local-height threshold plot.")
                elif present:
                    plot_btn.setToolTip("Run 03A local-height calculation first and make sure the threshold plot exists.")
                else:
                    plot_btn.setToolTip(f"{eye} not present in this dataset.")

            if hasattr(self, "raw_local_height_3d_plot_buttons") and eye in self.raw_local_height_3d_plot_buttons:
                raw_plot3d_btn = self.raw_local_height_3d_plot_buttons[eye]
                raw_path = self.analysis_folder / self.config["eyes"][eye]["files"]["local_heights_file"]
                raw_state = self.status["workflow_steps"]["03a_local_height_calculation"][eye].get("state")
                raw_ready = present and raw_state in ["complete", "complete_with_warning"] and raw_path.exists()
                raw_plot3d_btn.setEnabled(raw_ready)
                if raw_ready:
                    raw_plot3d_btn.setToolTip("Create a 3D PNG preview from the raw 03A local-height CSV and optionally open an interactive rgl window.")
                elif present:
                    raw_plot3d_btn.setToolTip("Run 03A Local height calculation first and make sure the raw local-height CSV exists.")
                else:
                    raw_plot3d_btn.setToolTip(f"{eye} not present in this dataset.")

            if hasattr(self, "local_height_3d_plot_buttons") and eye in self.local_height_3d_plot_buttons:
                plot3d_btn = self.local_height_3d_plot_buttons[eye]
                normalized_path = self.analysis_folder / self.config["eyes"][eye]["files"]["local_heights_normalized_file"]
                norm_state = self.status["workflow_steps"]["03a2_local_height_normalization"][eye].get("state")
                ready = present and norm_state in ["complete", "complete_with_warning"] and normalized_path.exists()
                plot3d_btn.setEnabled(ready)
                if ready:
                    plot3d_btn.setToolTip("Create a 3D PNG preview from the normalized local-height CSV and optionally open an interactive rgl window.")
                elif present:
                    plot3d_btn.setToolTip("Run 03A2 normalization first and make sure the normalized local-height CSV exists.")
                else:
                    plot3d_btn.setToolTip(f"{eye} not present in this dataset.")

            if hasattr(self, "thresholded_local_height_3d_plot_buttons") and eye in self.thresholded_local_height_3d_plot_buttons:
                thr_plot_btn = self.thresholded_local_height_3d_plot_buttons[eye]
                thr_path = self.analysis_folder / self.config["eyes"][eye]["files"]["local_height_thresholded_file"]
                thr_state = self.status["workflow_steps"]["03b_local_height_thresholding"][eye].get("state")
                thr_ready = present and thr_state in ["complete", "complete_with_warning"] and thr_path.exists()
                thr_plot_btn.setEnabled(thr_ready)
                if thr_ready:
                    thr_plot_btn.setToolTip("Create a 3D PNG preview of the final local-height thresholded points on the eye.")
                elif present:
                    thr_plot_btn.setToolTip("Run 03B Local-height thresholding first and make sure the thresholded point CSV exists.")
                else:
                    thr_plot_btn.setToolTip(f"{eye} not present in this dataset.")

            if hasattr(self, "facet_candidate_plot_buttons") and eye in self.facet_candidate_plot_buttons:
                btn = self.facet_candidate_plot_buttons[eye]
                files = self.config["eyes"][eye]["files"]
                path = self.analysis_folder / files["facet_candidates_file"]
                state = self.status["workflow_steps"]["03c_facet_candidate_condensation"][eye].get("state")
                ready = present and state in ["complete", "complete_with_warning"] and path.exists()
                btn.setEnabled(ready)
                if ready:
                    btn.setToolTip("Create a background PNG with facet candidates overlaid on the local-height eye.")
                elif present:
                    btn.setToolTip("Run 03C Facet candidate condensation first and make sure the facet-candidate CSV exists.")
                else:
                    btn.setToolTip(f"{eye} not present in this dataset.")

            if hasattr(self, "facet_position_plot_buttons") and eye in self.facet_position_plot_buttons:
                btn = self.facet_position_plot_buttons[eye]
                files = self.config["eyes"][eye]["files"]
                path = self.analysis_folder / files["facet_positions_file"]
                state = self.status["workflow_steps"]["04_blender_facet_check_landmarking"][eye].get("state")
                ready = present and state in ["complete", "complete_with_warning"] and path.exists()
                btn.setEnabled(ready)
                if ready:
                    btn.setToolTip("Create a background PNG with checked facet positions overlaid on the local-height eye.")
                elif present:
                    btn.setToolTip("Run 04 Facet position checking first and make sure the facet-position CSV exists.")
                else:
                    btn.setToolTip(f"{eye} not present in this dataset.")
        if hasattr(self, "head_landmark_status_label"):
            s05 = self.status.get("workflow_steps", {}).get("05_blender_head_landmarking", {})
            self.head_landmark_status_label.setText(
                f"{STEP_LABELS['05_blender_head_landmarking']}: {s05.get('symbol', '○')} {s05.get('state', 'not_started')}"
            )
            if hasattr(self, "head_landmark_button"):
                cv_id = self.config["dataset_identity"]["cv_id"]
                head_mesh_rel = self.config.get("specimen_files", {}).get("head_mesh_file", f"01_{cv_id}_head_ImageJ.stl")
                head_mesh_ok = (self.analysis_folder / head_mesh_rel).exists() if self.analysis_folder else False
                self.head_landmark_button.setEnabled(bool(self.config) and head_mesh_ok)
                self.head_landmark_button.setToolTip(
                    "Ready to launch head landmarking." if head_mesh_ok else f"Expected head mesh missing: {head_mesh_rel}"
                )

        self.messages.setPlainText(json.dumps(self.status, indent=2))
        if hasattr(self, "console_output"):
            self.console_output.setPlainText(self.latest_console_log_text())

    def update_mirror_target_default(self) -> None:
        if not hasattr(self, "mirror_source_combo") or not hasattr(self, "mirror_target_combo"):
            return
        source = self.mirror_source_combo.currentData()
        if source not in EYES or self.mirror_target_combo.count() == 0:
            return
        default_target = "eye2" if source == "eye1" else "eye1"
        for i in range(self.mirror_target_combo.count()):
            if self.mirror_target_combo.itemData(i) == default_target:
                self.mirror_target_combo.setCurrentIndex(i)
                return

    def r_analysis_runner_diagnostic(self, runner_key: str, runner_path: Optional[Path]) -> str:
        configured = self.settings.get(runner_key, "") if runner_key else ""
        bundled = bundled_helper_abs_path(runner_key) if runner_key else None
        parts = []
        parts.append(f"configured setting = {configured}" if configured else "configured setting is empty")
        parts.append(f"bundled fallback = {bundled}" if bundled is not None else "no bundled fallback was found")
        parts.append(f"resolved runner = {runner_path}" if runner_path is not None else "resolved runner = missing")
        return "; ".join(parts)

    def r_analysis_disabled_reason_text(self, eye: str, step: str, present: bool, input_problems: List[str], runner_key: str, runner_path: Optional[Path]) -> str:
        reasons = []
        if not present:
            reasons.append(f"{eye} is not marked as present in the project config.")
        reasons.extend(str(p) for p in (input_problems or []))
        if runner_key and runner_path is None:
            reasons.append(f"R runner missing for {STEP_LABELS.get(step, step)}: {self.r_analysis_runner_diagnostic(runner_key, runner_path)}")
        if not reasons:
            return ""
        return "Disabled because:\n" + "\n".join(f"- {r}" for r in reasons)

    def refresh_r_analysis_page(self) -> None:
        if not hasattr(self, "r_analysis_summary"):
            return

        if not self.config or not self.status:
            self.r_analysis_summary.setText("No dataset loaded.")
            if hasattr(self, "r_analysis_labels"):
                for eye in EYES:
                    for step, label in self.r_analysis_labels.get(eye, {}).items():
                        label.setText(f"{STEP_LABELS[step]}: ○ not started")
                    for step, button in self.r_analysis_buttons.get(eye, {}).items():
                        button.setEnabled(False)
                        button.setToolTip("No dataset loaded.")
                        reason_label = getattr(self, "r_analysis_button_reason_labels", {}).get(eye, {}).get(step)
                        if reason_label is not None:
                            reason_label.setText("Disabled: no dataset loaded.")
                            reason_label.show()
                    for button in getattr(self, "r_analysis_plot_buttons", {}).get(eye, {}).values():
                        button.setEnabled(False)
                        button.setToolTip("No dataset loaded.")
            if hasattr(self, "r_analysis_combined_05b_btn"):
                self.r_analysis_combined_05b_btn.setEnabled(False)
                self.r_analysis_combined_05c_btn.setEnabled(False)
                self.r_analysis_combined_05b_btn.setToolTip("No dataset loaded.")
                self.r_analysis_combined_05c_btn.setToolTip("No dataset loaded.")
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        self.r_analysis_summary.setText(
            f"{cv_id} R analysis — downstream analysis after checked facet positions and head landmarks."
        )

        analysis_steps = [
            "05a_optical_metrics",
            "05b_global_coordinate_rotation",
            "05c_corneal_projections",
        ]

        for eye in EYES:
            present = bool(self.config.get("eyes", {}).get(eye, {}).get("present", False))
            for step in analysis_steps:
                if step not in self.r_analysis_labels.get(eye, {}):
                    continue

                s = self.status.get("workflow_steps", {}).get(step, {}).get(eye, {})
                symbol = s.get("symbol", STATE_SYMBOL.get(s.get("state", "not_started"), "○"))
                state = s.get("state", "not_started")
                last_run = s.get("last_run") or "-"
                messages = s.get("messages", []) or []
                message_tail = "; ".join(messages[-2:]) if messages else ""

                self.r_analysis_labels[eye][step].setText(
                    f"{STEP_LABELS[step]}: {symbol} {state}\nLast: {last_run}"
                    + (f"\n{message_tail}" if message_tail else "")
                )

                input_problems = self.step_input_problems(step, eye) if present else [f"{eye} not present in scan."]
                runner_key = {
                    "05a_optical_metrics": "r_step05a_script_path",
                    "05b_global_coordinate_rotation": "r_step05b_script_path",
                    "05c_corneal_projections": "r_step05c_script_path",
                }.get(step, "")
                runner_path = configured_file_path(self.settings.get(runner_key, "")) if runner_key else None
                if runner_path is None and runner_key:
                    runner_path = bundled_helper_abs_path(runner_key)

                tooltip_lines = []
                if input_problems:
                    tooltip_lines.extend(input_problems)
                else:
                    tooltip_lines.append("Required inputs are present.")

                if runner_path is not None:
                    tooltip_lines.append(f"R runner: {runner_path}")
                else:
                    tooltip_lines.append("R runner is not configured or bundled for this step.")

                btn = self.r_analysis_buttons.get(eye, {}).get(step)
                if btn is not None:
                    enabled = present and not input_problems and runner_path is not None
                    btn.setEnabled(enabled)
                    btn.setToolTip("\n".join(tooltip_lines))
                    reason_label = getattr(self, "r_analysis_button_reason_labels", {}).get(eye, {}).get(step)
                    if reason_label is not None:
                        if enabled:
                            reason_label.clear()
                            reason_label.hide()
                        else:
                            reason_text = self.r_analysis_disabled_reason_text(eye, step, present, input_problems, runner_key, runner_path)
                            if not reason_text:
                                reason_text = "Disabled because the required state could not be verified."
                            reason_label.setText(reason_text)
                            reason_label.show()

            qc_runner = self.resolve_r_analysis_runner("r_step05a_qc_plot_script_path")
            qc05b_runner = self.resolve_r_analysis_runner("r_step05b_qc_plot_script_path")
            qc05c_runner = self.resolve_r_analysis_runner("r_step05c_qc_plot_script_path")
            optics_btn = getattr(self, "r_analysis_plot_buttons", {}).get(eye, {}).get("optics")
            labelled_btn = getattr(self, "r_analysis_plot_buttons", {}).get(eye, {}).get("labelled_metric")
            qc05b_btn = getattr(self, "r_analysis_plot_buttons", {}).get(eye, {}).get("05b_qc")
            qc05c_btn = getattr(self, "r_analysis_plot_buttons", {}).get(eye, {}).get("05c_qc")
            optic_rel = self.config["eyes"][eye]["files"].get("optic_parameters_file")
            normals_rel = self.config["eyes"][eye]["files"].get("facet_normals_file")
            global_rel = self.config["eyes"][eye]["files"].get("global_coordinates_file")
            projection_rel = self.config["eyes"][eye]["files"].get("corneal_projections_file")
            aligned_rel = self.config["eyes"][eye]["files"].get("global_aligned_pointcloud_file")
            plot_ready = present and bool(optic_rel) and (self.analysis_folder / str(optic_rel)).exists()
            normals_ready = plot_ready and bool(normals_rel) and (self.analysis_folder / str(normals_rel)).exists()
            landmarks_rel = self.config.get("specimen_files", {}).get("head_landmarks_file", f"05_{cv_id}_landmarks.csv")
            qc05b_ready = present and bool(global_rel) and (self.analysis_folder / str(global_rel)).exists() and bool(aligned_rel) and (self.analysis_folder / str(aligned_rel)).exists() and (self.analysis_folder / landmarks_rel).exists()
            qc05c_ready = present and bool(global_rel) and (self.analysis_folder / str(global_rel)).exists() and bool(projection_rel) and (self.analysis_folder / str(projection_rel)).exists()
            if optics_btn is not None:
                optics_btn.setEnabled(bool(qc_runner is not None and plot_ready))
                if qc_runner is None:
                    optics_btn.setToolTip("05A QC plot runner not configured.")
                elif not plot_ready:
                    optics_btn.setToolTip("Run 05A first to create optic-parameter outputs.")
                else:
                    optics_btn.setToolTip(f"Create optic-parameter inspection PNG(s) for {eye}.")
            if labelled_btn is not None:
                labelled_btn.setEnabled(bool(qc_runner is not None and plot_ready))
                if qc_runner is None:
                    labelled_btn.setToolTip("05A QC plot runner not configured.")
                elif not plot_ready:
                    labelled_btn.setToolTip("Run 05A first to create optic-parameter outputs.")
                else:
                    labelled_btn.setToolTip(f"Choose one 05A facet value or normal direction and create its inspection plot for {eye}.")
            if qc05b_btn is not None:
                qc05b_btn.setEnabled(bool(qc05b_runner is not None and qc05b_ready))
                if qc05b_runner is None:
                    qc05b_btn.setToolTip("05B QC plot runner not configured.")
                elif not qc05b_ready:
                    qc05b_btn.setToolTip("Run 05B first and make sure the landmark-referenced/aligned 05B point-cloud outputs and specimen-level head landmarks are available.")
                else:
                    qc05b_btn.setToolTip(f"Create a 05B global-alignment QC PNG for {eye} with blue landmarks overlaid.")
            if qc05c_btn is not None:
                qc05c_btn.setEnabled(bool(qc05c_runner is not None and qc05c_ready))
                if qc05c_runner is None:
                    qc05c_btn.setToolTip("05C QC plot runner not configured.")
                elif not qc05c_ready:
                    qc05c_btn.setToolTip("Run 05C first to create corneal-projection outputs.")
                else:
                    qc05c_btn.setToolTip(f"Create 05C corneal-projection QC PNGs for {eye}; optionally open the rgl sphere/normal inspection window.")

        if hasattr(self, "r_analysis_combined_05b_btn"):
            preferred = self.preferred_eye_for_combined_qc()
            eyes_for_qc = self.gather_available_primary_eyes_for_combined_qc(preferred)
            landmarks_rel = self.config.get("specimen_files", {}).get("head_landmarks_file", f"05_{cv_id}_landmarks.csv")
            any_05b_ready = False
            any_05c_ready = False
            for candidate in eyes_for_qc:
                files = self.config.get("eyes", {}).get(candidate, {}).get("files", {})
                global_rel = files.get("global_coordinates_file")
                aligned_rel = files.get("global_aligned_pointcloud_file")
                projection_rel = files.get("corneal_projections_file")
                if bool(global_rel) and bool(aligned_rel) and (self.analysis_folder / str(global_rel)).exists() and (self.analysis_folder / str(aligned_rel)).exists() and (self.analysis_folder / landmarks_rel).exists():
                    any_05b_ready = True
                if bool(global_rel) and bool(projection_rel) and (self.analysis_folder / str(global_rel)).exists() and (self.analysis_folder / str(projection_rel)).exists():
                    any_05c_ready = True
            self.r_analysis_combined_05b_btn.setEnabled(bool(qc05b_runner is not None and any_05b_ready))
            self.r_analysis_combined_05c_btn.setEnabled(bool(qc05c_runner is not None and any_05c_ready))
            self.r_analysis_combined_05b_btn.setToolTip("Create one combined 05B QC plot for eye1 + eye2 if both are available; otherwise plot the available eye." if any_05b_ready else "Run or mirror 05B first for at least one eye.")
            self.r_analysis_combined_05c_btn.setToolTip("Create one combined 05C QC plot for eye1 + eye2 if both are available; otherwise plot the available eye." if any_05c_ready else "Run or mirror 05C first for at least one eye.")

    def refresh_mirror_page(self) -> None:
        if not self.config or not self.status:
            self.mirror_summary.setText("No dataset loaded.")
            if hasattr(self, "mirror_button"):
                self.mirror_button.setEnabled(False)
            if hasattr(self, "mirror_source_combo"):
                self.mirror_source_combo.clear()
                self.mirror_target_combo.clear()
            return

        active = [eye for eye in EYES if self.config.get("eyes", {}).get(eye, {}).get("present", False) and not self.config.get("eyes", {}).get(eye, {}).get("mirrored", False)]
        mirror_state = self.status["workflow_steps"].get("05d_mirror_missing_eye", {}).get("state", "not_created")
        if hasattr(self, "mirror_source_combo"):
            old_source = self.mirror_source_combo.currentData()
            old_target = self.mirror_target_combo.currentData()

            self.mirror_source_combo.blockSignals(True)
            self.mirror_target_combo.blockSignals(True)
            self.mirror_source_combo.clear()
            self.mirror_target_combo.clear()

            for eye in active:
                side = self.config.get("eyes", {}).get(eye, {}).get("anatomical_side") or "unknown side"
                self.mirror_source_combo.addItem(f"{eye} — original source ({side})", eye)
            for eye in EYES:
                present = bool(self.config.get("eyes", {}).get(eye, {}).get("present", False))
                mirrored = bool(self.config.get("eyes", {}).get(eye, {}).get("mirrored", False))
                if mirrored:
                    label = f"Anatomical {eye} — overwrite existing mirrored outputs"
                elif present:
                    label = f"Anatomical {eye} — overwrite 04/05 outputs with mirrored outputs"
                else:
                    label = f"Anatomical {eye} — fill missing eye with mirrored outputs"
                self.mirror_target_combo.addItem(label, eye)

            if old_source in active:
                self.mirror_source_combo.setCurrentIndex(active.index(old_source))
            if old_target in EYES:
                self.mirror_target_combo.setCurrentIndex(EYES.index(old_target))
            elif active:
                source = self.mirror_source_combo.currentData()
                default_target = "eye2" if source == "eye1" else "eye1"
                if default_target in EYES:
                    self.mirror_target_combo.setCurrentIndex(EYES.index(default_target))

            self.mirror_source_combo.blockSignals(False)
            self.mirror_target_combo.blockSignals(False)

        if active:
            mirrored_actual = [eye for eye in EYES if self.config.get("eyes", {}).get(eye, {}).get("mirrored", False)]
            self.mirror_summary.setText(
                f"Mirroring available from present non-mirrored source eye(s): {', '.join(active)}. "
                f"Mirrored actual eye(s): {', '.join(mirrored_actual) if mirrored_actual else 'none'}. "
                f"Current mirror state: {mirror_state}. "
                "Mirroring writes into the actual target eye folder and overwrites existing 04/05 mirrored outputs."
            )
            self.mirror_button.setEnabled(True)
        else:
            self.mirror_summary.setText("Mirroring unavailable: no original eye is marked present.")
            self.mirror_button.setEnabled(False)

    def refresh_report_page(self) -> None:
        if not self.config or not self.status:
            self.report_summary.setText("No dataset loaded.")
            if hasattr(self, "export_readiness_text"):
                self.export_readiness_text.setPlainText("No dataset loaded.")
            for name in ["analysis_ready_export_button", "qc_pdf_report_button", "create_export_zip_button", "open_export_folder_button"]:
                if hasattr(self, name):
                    getattr(self, name).setEnabled(False)
            return
        self.ensure_report_outputs_config()
        rep = self.status["workflow_steps"].setdefault("06_report_export", {"label": STEP_LABELS["06_report_export"]})
        rep.setdefault("analysis_ready_export", {"state": "not_created", "symbol": "○", "last_run": None, "needs_rerun": False, "messages": []})
        rep.setdefault("pdf_export", {"state": "not_exported", "symbol": "○", "last_exported": None, "outdated_export": False, "messages": []})
        rep.setdefault("zip_export", {"state": "not_exported", "symbol": "○", "last_exported": None, "outdated_export": False, "messages": []})
        active_eyes = self.active_export_eyes()
        readiness_lines = self.export_readiness_lines()
        out = self.config.get("report_outputs", {})
        export_folder_rel = out.get("export_folder", {}).get("folder", "")
        export_folder_abs = str(self.analysis_folder / export_folder_rel) if self.analysis_folder and export_folder_rel else "not set"
        self.report_summary.setText(
            f"Analysis-ready export: {rep['analysis_ready_export']['state']} | "
            f"QC PDF: {rep['pdf_export']['state']} | ZIP: {rep['zip_export']['state']} | "
            f"export eyes: {', '.join(active_eyes) if active_eyes else 'none'}\n"
            f"Final export folder: {export_folder_abs}"
        )
        if hasattr(self, "export_readiness_text"):
            self.export_readiness_text.setPlainText("\n".join(readiness_lines))
        can_export = bool(active_eyes)
        if hasattr(self, "analysis_ready_export_button"):
            self.analysis_ready_export_button.setEnabled(can_export)
        if hasattr(self, "qc_pdf_report_button"):
            self.qc_pdf_report_button.setEnabled(can_export)
        if hasattr(self, "create_export_zip_button"):
            self.create_export_zip_button.setEnabled(can_export)
        if hasattr(self, "open_export_folder_button"):
            self.open_export_folder_button.setEnabled(bool(self.analysis_folder and self.analysis_folder.exists()))
        if hasattr(self, "report_output_files_text"):
            out = self.config.get("report_outputs", {})
            lines = []
            folder_info = out.get("export_folder", {})
            export_folder = folder_info.get("folder", "")
            if export_folder:
                folder_exists = (self.analysis_folder / export_folder).exists() if self.analysis_folder else False
                abs_folder = self.analysis_folder / export_folder if self.analysis_folder else Path(export_folder)
                lines.append(f"export_folder: {export_folder} | {abs_folder} | {'exists' if folder_exists else 'missing'}")
            for key in ["analysis_ready_table", "eye_summary", "specimen_summary", "metadata_json", "export_manifest", "optic_barplots_png", "cp_view_angles_png", "qc_pdf_report", "html_report", "zip_export"]:
                info = out.get(key, {})
                fn = info.get("file", "")
                exists = (self.analysis_folder / fn).exists() if fn and self.analysis_folder else False
                status = info.get("status", "")
                lines.append(f"{key}: {fn or 'not set'} | {status} | {'exists' if exists else 'missing'}")
            self.report_output_files_text.setPlainText("\n".join(lines))

    def refresh_settings_page(self) -> None:
        cs = self.settings["compute_settings"]
        self.settings_summary.setText(
            f"Detected cores: {cs.get('available_cores_detected')} | "
            f"Current max cores: {cs.get('max_cores')} | "
            f"User overridden: {cs.get('user_overridden')} | "
            f"Bundled helpers: {bool(self.settings.get('use_bundled_helpers', True))} | "
            f"ImageJ executable set: {bool(self.settings.get('imagej_executable'))} | "
            f"ImageJ preprocessing macro set: {bool(self.settings.get('imagej_macro_path'))} | "
            f"ImageJ mesh macro set: {bool(self.settings.get('imagej_mesh_macro_path'))} | "
            f"Blender executable set: {bool(self.settings.get('blender_executable'))} | "
            f"Blender script set: {bool(self.settings.get('blender_script_path'))} | "
            f"Rscript set: {bool(self.settings.get('rscript_executable'))} | "
            f"R GitHub repo: {self.settings.get('r_github_repo', 'Pete-s-Lab/CV3D')} | "
            f"R 03A runner set: {bool(self.settings.get('r_step03a_script_path'))} | "
            f"R 03A2 runner set: {bool(self.settings.get('r_step03a2_script_path'))} | "
            f"R raw 3D plot runner set: {bool(self.settings.get('r_step03a_plot_script_path'))} | "
            f"R normalized 3D plot runner set: {bool(self.settings.get('r_step03a2_plot_script_path'))} | "
            f"R 03B runner set: {bool(self.settings.get('r_step03b_script_path'))} | "
            f"R 03B plot runner set: {bool(self.settings.get('r_step03b_plot_script_path'))} | "
            f"R 03C runner set: {bool(self.settings.get('r_step03c_script_path'))} | "
            f"R 05A runner set: {bool(self.settings.get('r_step05a_script_path'))} | "
            f"R 05B runner set: {bool(self.settings.get('r_step05b_script_path'))} | "
            f"R 05C runner set: {bool(self.settings.get('r_step05c_script_path'))} | "
            f"R 05A QC runner set: {bool(self.settings.get('r_step05a_qc_plot_script_path'))} | "
            f"R 05B QC runner set: {bool(self.settings.get('r_step05b_qc_plot_script_path'))} | "
            f"R 05C QC runner set: {bool(self.settings.get('r_step05c_qc_plot_script_path'))} | "
            f"R facet overlay plot runner set: {bool(self.settings.get('r_facet_point_plot_script_path'))}"
        )
        if hasattr(self, "imagej_executable_edit"):
            self.imagej_executable_edit.setText(self.settings.get("imagej_executable", ""))
        if hasattr(self, "imagej_macro_edit"):
            self.imagej_macro_edit.setText(self.settings.get("imagej_macro_path", ""))
        if hasattr(self, "imagej_mesh_macro_edit"):
            self.imagej_mesh_macro_edit.setText(self.settings.get("imagej_mesh_macro_path", ""))
        if hasattr(self, "blender_executable_edit"):
            self.blender_executable_edit.setText(self.settings.get("blender_executable", ""))
        if hasattr(self, "blender_script_edit"):
            self.blender_script_edit.setText(self.settings.get("blender_script_path", ""))
        if hasattr(self, "rscript_executable_edit"):
            self.rscript_executable_edit.setText(self.settings.get("rscript_executable", ""))
        if hasattr(self, "r_github_repo_edit"):
            self.r_github_repo_edit.setText(self.settings.get("r_github_repo", "Pete-s-Lab/CV3D"))
        if hasattr(self, "r_step03a_script_edit"):
            self.r_step03a_script_edit.setText(self.settings.get("r_step03a_script_path", ""))
        if hasattr(self, "r_step03a2_script_edit"):
            self.r_step03a2_script_edit.setText(self.settings.get("r_step03a2_script_path", ""))
        if hasattr(self, "r_step03a_plot_script_edit"):
            self.r_step03a_plot_script_edit.setText(self.settings.get("r_step03a_plot_script_path", ""))
        if hasattr(self, "r_step03a2_plot_script_edit"):
            self.r_step03a2_plot_script_edit.setText(self.settings.get("r_step03a2_plot_script_path", ""))
        if hasattr(self, "r_step03b_script_edit"):
            self.r_step03b_script_edit.setText(self.settings.get("r_step03b_script_path", ""))
        if hasattr(self, "r_step03b_plot_script_edit"):
            self.r_step03b_plot_script_edit.setText(self.settings.get("r_step03b_plot_script_path", ""))
        if hasattr(self, "r_step03c_script_edit"):
            self.r_step03c_script_edit.setText(self.settings.get("r_step03c_script_path", ""))
        if hasattr(self, "r_step05a_script_edit"):
            self.r_step05a_script_edit.setText(self.settings.get("r_step05a_script_path", ""))
        if hasattr(self, "r_step05b_script_edit"):
            self.r_step05b_script_edit.setText(self.settings.get("r_step05b_script_path", ""))
        if hasattr(self, "r_step05c_script_edit"):
            self.r_step05c_script_edit.setText(self.settings.get("r_step05c_script_path", ""))
        if hasattr(self, "r_step05a_qc_plot_script_edit"):
            self.r_step05a_qc_plot_script_edit.setText(self.settings.get("r_step05a_qc_plot_script_path", ""))
        if hasattr(self, "r_step05b_qc_plot_script_edit"):
            self.r_step05b_qc_plot_script_edit.setText(self.settings.get("r_step05b_qc_plot_script_path", ""))
        if hasattr(self, "r_step05c_qc_plot_script_edit"):
            self.r_step05c_qc_plot_script_edit.setText(self.settings.get("r_step05c_qc_plot_script_path", ""))
        if hasattr(self, "r_facet_point_plot_script_edit"):
            self.r_facet_point_plot_script_edit.setText(self.settings.get("r_facet_point_plot_script_path", ""))


    def use_bundled_helper_scripts(self) -> None:
        self.settings["use_bundled_helpers"] = True
        apply_bundled_helper_paths(self.settings)
        save_app_settings(self.settings)
        self.refresh_settings_page()
        QMessageBox.information(self, "Bundled helper scripts", "Bundled CV3D helper script paths were detected and saved as relative paths.")

    def browse_imagej_executable(self) -> None:
        start = self.settings.get("imagej_executable") or str(Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ImageJ/Fiji executable",
            start,
            "Executables (*.exe);;All files (*)"
        )
        if file_path:
            self.imagej_executable_edit.setText(file_path)
            self.settings["imagej_executable"] = file_path
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_imagej_macro(self) -> None:
        start = helper_file_dialog_start(self.settings, "imagej_macro_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D ImageJ macro",
            start,
            "ImageJ macros (*.ijm);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("imagej_macro_path", file_path)
            self.imagej_macro_edit.setText(stored)
            self.settings["imagej_macro_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_imagej_mesh_macro(self) -> None:
        start = helper_file_dialog_start(self.settings, "imagej_mesh_macro_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D ImageJ mesh/STL extraction macro",
            start,
            "ImageJ macros (*.ijm);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("imagej_mesh_macro_path", file_path)
            self.imagej_mesh_macro_edit.setText(stored)
            self.settings["imagej_mesh_macro_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def imagej_mesh_target_options(self) -> List[str]:
        if not self.config:
            return ["head"]
        active_eyes = [eye for eye in EYES if self.config.get("eyes", {}).get(eye, {}).get("present", False)]
        opts = ["head + present eyes", "head"]
        opts.extend(active_eyes)
        return opts

    def expected_mesh_output_for_target(self, target: str) -> str:
        cv_id = self.config["dataset_identity"]["cv_id"]
        if target == "head":
            return self.config.get("specimen_files", {}).get("head_mesh_file", f"01_{cv_id}_head_ImageJ.stl")
        return self.config["eyes"][target]["files"].get("imagej_stl_file") or eye_rel_path(target, f"01_{cv_id}_{target}_ImageJ.stl")

    def expected_mesh_status_for_target(self, target: str) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        if target == "head":
            return self.analysis_folder / "json" / f"01MESH_{cv_id}_head_ImageJ_status.json"
        return self.analysis_folder / target / "json" / f"01MESH_{cv_id}_{target}_ImageJ_status.json"

    def update_config_after_mesh_extraction_target(self, target: str) -> None:
        """Update selected STL bookkeeping after ImageJ mesh extraction for one target."""
        if not self.config or not self.analysis_folder:
            return
        cv_id = self.config["dataset_identity"]["cv_id"]

        if target == "head":
            self.config.setdefault("specimen_files", {})["head_mesh_file"] = f"01_{cv_id}_head_ImageJ.stl"
            return

        files = self.config["eyes"][target]["files"]
        expected_stl = eye_rel_path(target, f"01_{cv_id}_{target}_ImageJ.stl")
        expected_nrrd = eye_rel_path(target, f"01_{cv_id}_{target}.nrrd")
        files["imagej_stl_file"] = expected_stl
        files["nrrd_file"] = expected_nrrd

        if (self.analysis_folder / expected_stl).exists():
            files["imagej_stl_available"] = True
            files["selected_raw_stl_file"] = expected_stl
        else:
            files["imagej_stl_available"] = False

    def launch_imagej_mesh_extraction(self) -> None:
        """Launch ImageJ/Fiji mesh extraction for head and/or eyes."""
        if not self.config or not self.status or not self.analysis_folder:
            QMessageBox.warning(self, "No dataset", "Create or load a dataset first.")
            return

        if self.config["source_data"].get("imagej_preprocessing_skipped", False):
            QMessageBox.information(self, "ImageJ skipped", "This dataset starts from an STL source, so ImageJ mesh extraction is skipped.")
            return

        if hasattr(self, "imagej_executable_edit"):
            self.settings["imagej_executable"] = self.imagej_executable_edit.text().strip()
        if hasattr(self, "imagej_mesh_macro_edit"):
            self.settings["imagej_mesh_macro_path"] = self.imagej_mesh_macro_edit.text().strip()
        save_app_settings(self.settings)

        imagej_exe = configured_file_path(self.settings.get("imagej_executable", ""))
        macro_path = configured_file_path(self.settings.get("imagej_mesh_macro_path", ""))

        if imagej_exe is None:
            QMessageBox.warning(self, "ImageJ/Fiji executable missing", "Set a valid ImageJ/Fiji executable in Settings first.")
            self.nav.setCurrentRow(6)
            return

        if macro_path is None:
            QMessageBox.warning(self, "ImageJ mesh macro missing", "Set a valid CV3D ImageJ mesh/STL extraction macro .ijm file in Settings first.")
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        active_eyes = [eye for eye in EYES if self.config.get("eyes", {}).get(eye, {}).get("present", False)]
        if not active_eyes:
            QMessageBox.warning(self, "No active eyes", "At least one eye must be marked present before extracting eye STLs.")
            return

        choice, ok = QInputDialog.getItem(
            self,
            "ImageJ/Fiji STL extraction target",
            "Extract STL for:",
            self.imagej_mesh_target_options(),
            0,
            False
        )
        if not ok:
            return

        if choice == "head + present eyes":
            targets = ["head"] + active_eyes
        else:
            targets = [choice]

        missing_inputs = []
        for target in targets:
            if target == "head":
                input_rel = f"01_{cv_id}_head.nrrd"
            else:
                input_rel = self.config["eyes"][target]["files"].get("nrrd_file") or eye_rel_path(target, f"01_{cv_id}_{target}.nrrd")
            if not (self.analysis_folder / input_rel).exists():
                missing_inputs.append(f"{target}: {input_rel}")

        if missing_inputs:
            QMessageBox.warning(
                self,
                "Missing NRRD input",
                "Mesh extraction needs the cropped NRRD outputs from ImageJ preprocessing.\n\n"
                + "\n".join(missing_inputs)
            )
            return

        expected_outputs = [f"{target}: {self.expected_mesh_output_for_target(target)}" for target in targets]
        session_note = (
            "All selected targets will run in one ImageJ/Fiji session.\n"
            "The accepted threshold from each target will be suggested as the starting value for the next target.\n\n"
            if len(targets) > 1 else
            "ImageJ/Fiji will close automatically after this target is finished.\n\n"
        )
        reply = QMessageBox.question(
            self,
            "Launch ImageJ/Fiji STL extraction",
            "This will launch the interactive ImageJ/Fiji mesh extraction workflow.\n\n"
            + session_note
            + f"CV ID: {cv_id}\n"
            + f"Targets: {', '.join(targets)}\n"
            + f"Analysis folder: {self.analysis_folder}\n\n"
            + "Expected STL outputs:\n" + "\n".join(expected_outputs),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        messages = []
        all_ok = True
        before = self.status["workflow_steps"]["01_imagej_preprocessing"].get("state", "not_started")

        for target in targets:
            append_log(
                self.analysis_folder,
                cv_id,
                target if target in EYES else "",
                "01_imagej_mesh_extraction",
                "launch_imagej_mesh",
                before,
                "running",
                "started",
                f"ImageJ/Fiji STL extraction started for {target}."
            )

        batch_macro_path = None
        try:
            if len(targets) == 1:
                target = targets[0]
                arg = (
                    f"mode=cv3d_mesh;"
                    f"analysis_folder={self.analysis_folder};"
                    f"cv_id={cv_id};"
                    f"target={target};"
                    f"quit_after=1"
                )
                cmd = [str(imagej_exe), "-macro", str(macro_path), arg]
            else:
                logs_dir = self.analysis_folder / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                batch_macro_path = logs_dir / f"_CV3D_{cv_id}_mesh_batch.ijm"

                macro_for_ij = str(macro_path).replace("\\", "/").replace('"', '\\"')
                analysis_for_ij = str(self.analysis_folder).replace("\\", "/").replace('"', '\\"')
                cv_for_ij = str(cv_id).replace('"', '\\"')
                target_literals = ", ".join(f'"{str(t).replace(chr(34), "")}"' for t in targets)

                batch_macro = (
                    f'mesh_macro = "{macro_for_ij}";\n'
                    f'analysis_folder = "{analysis_for_ij}";\n'
                    f'cv_id = "{cv_for_ij}";\n'
                    f'targets = newArray({target_literals});\n'
                    'suggested_threshold = "";\n'
                    'for (bi = 0; bi < targets.length; bi++) {\n'
                    '    subarg = "mode=cv3d_mesh;analysis_folder=" + analysis_folder + ";cv_id=" + cv_id + ";target=" + targets[bi] + ";quit_after=0";\n'
                    '    if (suggested_threshold != "") subarg = subarg + ";suggested_threshold=" + suggested_threshold;\n'
                    '    suggested_threshold = call("ij.IJ.runMacroFile", mesh_macro, subarg);\n'
                    '}\n'
                    'run("Quit");\n'
                )
                batch_macro_path.write_text(batch_macro, encoding="utf-8")
                cmd = [str(imagej_exe), "-macro", str(batch_macro_path)]

            result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder))
            exit_code = result.returncode

        except Exception as e:
            exit_code = -1
            all_ok = False
            messages.append(f"Could not launch ImageJ/Fiji: {e}")
        finally:
            if batch_macro_path is not None:
                try:
                    batch_macro_path.unlink(missing_ok=True)
                except Exception:
                    pass

        for target in targets:
            status_json = self.expected_mesh_status_for_target(target)
            imagej_status = "unknown"
            status_message = ""
            if status_json.exists():
                try:
                    payload = read_json(status_json)
                    imagej_status = str(payload.get("status", "unknown"))
                    status_message = str(payload.get("message", ""))
                except Exception as e:
                    imagej_status = "unreadable_status_json"
                    status_message = str(e)

            self.update_config_after_mesh_extraction_target(target)
            output_rel = self.expected_mesh_output_for_target(target)
            output_exists = (self.analysis_folder / output_rel).exists()

            if exit_code == 0 and imagej_status == "success" and output_exists:
                msg = f"{target}: success — {output_rel}"
                append_log(
                    self.analysis_folder, cv_id, target if target in EYES else "",
                    "01_imagej_mesh_extraction", "launch_imagej_mesh", before,
                    "complete", "success", msg
                )
            else:
                all_ok = False
                msg = (
                    f"{target}: failed or incomplete. "
                    f"exit={exit_code}; status={imagej_status}; output_exists={output_exists}; output={output_rel}"
                )
                if status_message:
                    msg += f"; {status_message}"
                append_log(
                    self.analysis_folder, cv_id, target if target in EYES else "",
                    "01_imagej_mesh_extraction", "launch_imagej_mesh", before,
                    "failed", "failed", msg
                )
            messages.append(msg)

        s = self.status["workflow_steps"]["01_imagej_preprocessing"]
        if all_ok:
            s["state"] = "complete"
            s["symbol"] = STATE_SYMBOL["complete"]
            s["needs_rerun"] = False
        else:
            s["state"] = "complete_with_warning"
            s["symbol"] = STATE_SYMBOL["complete_with_warning"]
            s["needs_rerun"] = False
        s["last_run"] = now()
        s["messages"] = messages

        self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()
        self.check_imagej_source_outputs()

    def imagej_active_eyes_argument(self) -> str:
        if not self.config:
            return "eye1,eye2"
        active = [eye for eye in EYES if self.config.get("eyes", {}).get(eye, {}).get("present", False)]
        return ",".join(active)

    def launch_imagej_preprocessing(self) -> None:
        """Launch Fiji/ImageJ interactively with the CV3D preprocessing macro."""
        if not self.config or not self.status or not self.analysis_folder:
            QMessageBox.warning(self, "No dataset", "Create or load a dataset first.")
            return

        if self.config["source_data"].get("imagej_preprocessing_skipped", False):
            QMessageBox.information(self, "ImageJ skipped", "This dataset starts from an STL source, so ImageJ preprocessing is skipped.")
            return

        if hasattr(self, "imagej_executable_edit"):
            self.settings["imagej_executable"] = self.imagej_executable_edit.text().strip()
        if hasattr(self, "imagej_macro_edit"):
            self.settings["imagej_macro_path"] = self.imagej_macro_edit.text().strip()
        if hasattr(self, "imagej_mesh_macro_edit"):
            self.settings["imagej_mesh_macro_path"] = self.imagej_mesh_macro_edit.text().strip()
        if hasattr(self, "blender_executable_edit"):
            self.settings["blender_executable"] = self.blender_executable_edit.text().strip()
        if hasattr(self, "blender_script_edit"):
            self.settings["blender_script_path"] = self.blender_script_edit.text().strip()
        if hasattr(self, "rscript_executable_edit"):
            self.settings["rscript_executable"] = self.rscript_executable_edit.text().strip()
        if hasattr(self, "r_github_repo_edit"):
            self.settings["r_github_repo"] = self.r_github_repo_edit.text().strip() or "Pete-s-Lab/CV3D"
        if hasattr(self, "r_step03a_script_edit"):
            self.settings["r_step03a_script_path"] = self.r_step03a_script_edit.text().strip()
        if hasattr(self, "r_step03a2_script_edit"):
            self.settings["r_step03a2_script_path"] = self.r_step03a2_script_edit.text().strip()
        if hasattr(self, "r_step03a_plot_script_edit"):
            self.settings["r_step03a_plot_script_path"] = self.r_step03a_plot_script_edit.text().strip()
        if hasattr(self, "r_step03a2_plot_script_edit"):
            self.settings["r_step03a2_plot_script_path"] = self.r_step03a2_plot_script_edit.text().strip()
        if hasattr(self, "r_step03b_script_edit"):
            self.settings["r_step03b_script_path"] = self.r_step03b_script_edit.text().strip()
        if hasattr(self, "r_step03b_plot_script_edit"):
            self.settings["r_step03b_plot_script_path"] = self.r_step03b_plot_script_edit.text().strip()
        if hasattr(self, "r_step03c_script_edit"):
            self.settings["r_step03c_script_path"] = self.r_step03c_script_edit.text().strip()
        if hasattr(self, "r_facet_point_plot_script_edit"):
            self.settings["r_facet_point_plot_script_path"] = self.r_facet_point_plot_script_edit.text().strip()
        save_app_settings(self.settings)

        imagej_exe = configured_file_path(self.settings.get("imagej_executable", ""))
        macro_path = configured_file_path(self.settings.get("imagej_macro_path", ""))

        if imagej_exe is None:
            QMessageBox.warning(self, "ImageJ/Fiji executable missing", "Set a valid ImageJ/Fiji executable in Settings first.")
            self.nav.setCurrentRow(6)
            return

        if macro_path is None:
            QMessageBox.warning(self, "ImageJ macro missing", "Set a valid CV3D ImageJ preprocessing macro .ijm file in Settings first.")
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        raw_folder = resolve_config_raw_folder(self.config, self.analysis_folder)
        active_eyes = self.imagej_active_eyes_argument()

        if not active_eyes:
            QMessageBox.warning(self, "No active eyes", "At least one eye must be marked present before running ImageJ.")
            return

        arg = (
            f"mode=cv3d;"
            f"raw_folder={raw_folder};"
            f"analysis_folder={self.analysis_folder};"
            f"cv_id={cv_id};"
            f"active_eyes={active_eyes};"
            f"specimen_name={self.config['dataset_identity'].get('raw_folder_name', cv_id)}"
        )

        reply = QMessageBox.question(
            self,
            "Launch ImageJ/Fiji",
            "This will open ImageJ/Fiji and run the interactive CV3D preprocessing macro.\n\n"
            f"CV ID: {cv_id}\n"
            f"Active eyes: {active_eyes}\n"
            f"Raw folder: {raw_folder}\n"
            f"Analysis folder: {self.analysis_folder}\n\n"
            "Complete the workflow in ImageJ/Fiji. The Python GUI will wait until ImageJ exits.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        s = self.status["workflow_steps"]["01_imagej_preprocessing"]
        before = s.get("state", "not_started")
        s["state"] = "running"
        s["symbol"] = STATE_SYMBOL["running"]
        s["last_run"] = now()
        s["needs_rerun"] = False
        s["messages"] = ["ImageJ/Fiji launched interactively."]
        self.save_current_files()
        self.refresh_all()

        cmd = [str(imagej_exe), "-macro", str(macro_path), arg]

        try:
            result = self.run_blocking_process(cmd, cwd=str(raw_folder))
            exit_code = result.returncode
        except Exception as e:
            s["state"] = "failed"
            s["symbol"] = STATE_SYMBOL["failed"]
            s["needs_rerun"] = True
            s["messages"] = [f"Could not launch ImageJ/Fiji: {e}"]
            append_log(self.analysis_folder, cv_id, "", "01_imagej_preprocessing", "launch_imagej", before, "failed", "failed", str(e))
            self.save_current_files()
            self.refresh_all()
            QMessageBox.critical(self, "ImageJ launch failed", str(e))
            return

        self.load_current_files()
        status_json = self.analysis_folder / f"01_{cv_id}_ImageJ_status.json"
        status_txt = self.analysis_folder / f"01_{cv_id}_ImageJ_status.txt"

        status_message = ""
        imagej_status = "unknown"
        if status_json.exists():
            try:
                status_payload = read_json(status_json)
                imagej_status = str(status_payload.get("status", "unknown"))
                status_message = str(status_payload.get("message", ""))
            except Exception as e:
                imagej_status = "unreadable_status_json"
                status_message = str(e)
        elif status_txt.exists():
            status_message = status_txt.read_text(encoding="utf-8", errors="replace")
            if "status=success" in status_message:
                imagej_status = "success"
            elif "status=partial_without_stl" in status_message:
                imagej_status = "partial_without_stl"
            elif "status=failed" in status_message:
                imagej_status = "failed"

        self.assign_imagej_outputs_after_real_run()

        if exit_code == 0 and imagej_status in ["success", "partial_without_stl"]:
            state = "complete" if imagej_status == "success" else "complete_with_warning"
            messages = [f"ImageJ/Fiji finished with status: {imagej_status}."]
            if status_message:
                messages.append(status_message)
            self.status["workflow_steps"]["01_imagej_preprocessing"]["state"] = state
            self.status["workflow_steps"]["01_imagej_preprocessing"]["symbol"] = STATE_SYMBOL[state]
            self.status["workflow_steps"]["01_imagej_preprocessing"]["last_run"] = now()
            self.status["workflow_steps"]["01_imagej_preprocessing"]["needs_rerun"] = False
            self.status["workflow_steps"]["01_imagej_preprocessing"]["messages"] = messages
            append_log(self.analysis_folder, cv_id, "", "01_imagej_preprocessing", "launch_imagej", before, state, "success", "; ".join(messages))
        else:
            messages = [f"ImageJ/Fiji exit code: {exit_code}.", f"ImageJ status file status: {imagej_status}."]
            if status_message:
                messages.append(status_message)
            self.status["workflow_steps"]["01_imagej_preprocessing"]["state"] = "failed"
            self.status["workflow_steps"]["01_imagej_preprocessing"]["symbol"] = STATE_SYMBOL["failed"]
            self.status["workflow_steps"]["01_imagej_preprocessing"]["needs_rerun"] = True
            self.status["workflow_steps"]["01_imagej_preprocessing"]["messages"] = messages
            append_log(self.analysis_folder, cv_id, "", "01_imagej_preprocessing", "launch_imagej", before, "failed", "failed", "; ".join(messages))

        self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()
        self.check_imagej_source_outputs()

    def assign_imagej_outputs_after_real_run(self) -> None:
        """Update selected_raw_stl_file and facet-size default after a real ImageJ macro run."""
        if not self.config or not self.analysis_folder:
            return
        cv_id = self.config["dataset_identity"]["cv_id"]
        self.config.setdefault("specimen_files", {}).setdefault("head_mesh_file", f"01_{cv_id}_head_ImageJ.stl")

        facet_csv = self.analysis_folder / f"01_{cv_id}_facet_size_estimate.csv"
        if facet_csv.exists():
            try:
                with facet_csv.open("r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                if rows:
                    value = rows[0].get("facet_size_estimate")
                    if value not in (None, ""):
                        self.config["parameters"]["dataset_defaults"]["facet_size_estimate"] = float(value)
            except Exception:
                pass

        for eye in EYES:
            if not self.config.get("eyes", {}).get(eye, {}).get("present", False):
                continue
            files = self.config["eyes"][eye]["files"]
            expected_stl = files.get("imagej_stl_file") or eye_rel_path(eye, f"01_{cv_id}_{eye}_ImageJ.stl")
            expected_nrrd = files.get("nrrd_file") or eye_rel_path(eye, f"01_{cv_id}_{eye}.nrrd")
            files["imagej_stl_file"] = expected_stl
            files["nrrd_file"] = expected_nrrd

            if (self.analysis_folder / expected_stl).exists():
                files["imagej_stl_available"] = True
                files["selected_raw_stl_file"] = expected_stl
            else:
                files["imagej_stl_available"] = False



    def browse_blender_executable(self) -> None:
        start = self.settings.get("blender_executable") or str(Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Blender executable",
            start,
            "Executables (*.exe);;All files (*)"
        )
        if file_path:
            self.blender_executable_edit.setText(file_path)
            self.settings["blender_executable"] = file_path
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_blender_script(self) -> None:
        start = helper_file_dialog_start(self.settings, "blender_script_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D Blender helper script",
            start,
            "Python scripts (*.py);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("blender_script_path", file_path)
            self.blender_script_edit.setText(stored)
            self.settings["blender_script_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def read_facet_size_estimate_for_task(self) -> float:
        """Read facet size estimate from the dataset-level ImageJ CSV.

        This value is shared by both eyes and must come from:
        <analysis_folder>/01_CVxxxx_facet_size_estimate.csv

        We intentionally do not silently fall back here, because a fallback would hide
        broken ImageJ-output bookkeeping and pass an incorrect value into Blender.
        """
        if not self.config or not self.analysis_folder:
            raise RuntimeError("No dataset/analysis folder is loaded.")

        cv_id = self.config["dataset_identity"]["cv_id"]
        csv_path = self.analysis_folder / f"01_{cv_id}_facet_size_estimate.csv"

        if not csv_path.exists():
            raise FileNotFoundError(
                "Facet-size estimate CSV is missing. Expected dataset-level file:\n"
                f"{csv_path}"
            )

        rows = None
        read_errors = []
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                with csv_path.open("r", encoding=enc, newline="") as f:
                    rows = list(csv.DictReader(f))
                break
            except UnicodeDecodeError as e:
                read_errors.append(f"{enc}: {e}")

        if rows is None:
            raise UnicodeDecodeError(
                "facet_size_estimate_csv",
                b"",
                0,
                1,
                "Could not decode facet-size estimate CSV with utf-8-sig, utf-8, cp1252, or latin-1. "
                + " | ".join(read_errors)
            )

        if not rows:
            raise ValueError(f"Facet-size estimate CSV is empty: {csv_path}")

        if "facet_size_estimate" not in rows[0]:
            raise ValueError(
                "Facet-size estimate CSV has no 'facet_size_estimate' column.\n"
                f"File: {csv_path}\n"
                f"Columns found: {list(rows[0].keys())}"
            )

        value = rows[0].get("facet_size_estimate")
        if value in (None, ""):
            raise ValueError(f"Facet-size estimate value is missing in: {csv_path}")

        try:
            return float(value)
        except Exception as e:
            raise ValueError(
                f"Could not parse facet_size_estimate='{value}' as a number in:\n{csv_path}"
            ) from e

    def timestamp_from_file_mtime(self, path: Path) -> str:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y%m%d-%H%M%S")

    def backup_file_with_mtime(self, path: Path, label: str = "file") -> Optional[Path]:
        """Move an existing file aside using its last-modified timestamp."""
        if not path.exists():
            return None

        timestamp = self.timestamp_from_file_mtime(path)
        candidate = path.with_name(f"{path.stem}_backup_{timestamp}{path.suffix}")
        counter = 1
        while candidate.exists():
            candidate = path.with_name(f"{path.stem}_backup_{timestamp}_{counter}{path.suffix}")
            counter += 1

        shutil.move(str(path), str(candidate))
        return candidate

    def backup_existing_step02_outputs(self, eye: str) -> List[str]:
        """Back up existing Step 02 files before deliberately starting a new Blender extraction."""
        if not self.config or not self.analysis_folder:
            return []

        files = self.config["eyes"][eye]["files"]
        keys = [
            "cornea_blend_file",
            "cornea_stl_file",
            "blender_step02_status_file",
            "blender_step02_task_file",
        ]

        backups: List[str] = []
        for key in keys:
            rel = files.get(key)
            if not rel:
                continue
            original = self.analysis_folder / rel
            backup = self.backup_file_with_mtime(original, key)
            if backup is not None:
                backups.append(f"{rel} -> {backup.relative_to(self.analysis_folder)}")
        return backups

    def preflight_existing_blender_file(self, eye: str) -> str:
        """Return how Step 02 should handle an existing output .blend file."""
        if not self.config or not self.analysis_folder:
            return "cancel"

        files = self.config["eyes"][eye]["files"]
        blend_rel = files.get("cornea_blend_file")
        if not blend_rel:
            return "new"

        blend_path = self.analysis_folder / blend_rel
        if not blend_path.exists():
            return "new"

        modified = datetime.fromtimestamp(blend_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_mb = blend_path.stat().st_size / (1024 * 1024)

        box = QMessageBox(self)
        box.setWindowTitle("Existing Blender file found")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            "An existing Blender file already exists for this eye.\\n\\n"
            f"{blend_rel}\\n\\n"
            f"Last modified: {modified}\\n"
            f"Size: {size_mb:.2f} MB\\n\\n"
            "To avoid losing work, the safest option is to open the existing file and continue."
        )
        open_btn = box.addButton("Open existing and continue", QMessageBox.ButtonRole.AcceptRole)
        backup_btn = box.addButton("Back up existing and start new", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(open_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked == open_btn:
            return "open_existing"
        if clicked == backup_btn:
            backups = self.backup_existing_step02_outputs(eye)
            if backups:
                QMessageBox.information(
                    self,
                    "Step 02 files backed up",
                    "The following existing Step 02 files were moved aside:\\n\\n"
                    + "\\n".join(f"- {line}" for line in backups)
                )
            return "backup_new"
        if clicked == cancel_btn:
            return "cancel"
        return "cancel"

    def create_blender_step02_task(self, eye: str) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        task_rel = files["blender_step02_task_file"]
        selected_raw = files.get("selected_raw_stl_file")

        facet_size = self.read_facet_size_estimate_for_task()

        # Keep the config synchronized for display/defaults, but do not trust it over the CSV.
        self.config["parameters"]["dataset_defaults"]["facet_size_estimate"] = facet_size

        task = {
            "task_type": "cornea_extraction",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_stl": selected_raw,
            "input_stl_abs": str(self.analysis_folder / selected_raw),
            "output_cornea_stl": files["cornea_stl_file"],
            "output_cornea_stl_abs": str(self.analysis_folder / files["cornea_stl_file"]),
            "output_blend": files["cornea_blend_file"],
            "output_blend_abs": str(self.analysis_folder / files["cornea_blend_file"]),
            "status_file": files["blender_step02_status_file"],
            "status_file_abs": str(self.analysis_folder / files["blender_step02_status_file"]),
            "facet_size_estimate": facet_size,
            "decimate_ratio": 0.5,
            "smooth_iterations": 10,
            "smooth_factor": 0.5,
            "notes": "Created by CV3D Python controller for interactive Blender Step 02.",
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)
        return task_path

    def launch_blender_cornea_extraction(self, eye: str) -> None:
        """Launch Blender interactively for Step 02 cornea extraction."""
        if not self.ensure_step_ready("02_blender_cornea_extraction", eye):
            return

        if hasattr(self, "blender_executable_edit"):
            self.settings["blender_executable"] = self.blender_executable_edit.text().strip()
        if hasattr(self, "blender_script_edit"):
            self.settings["blender_script_path"] = self.blender_script_edit.text().strip()
        if hasattr(self, "rscript_executable_edit"):
            self.settings["rscript_executable"] = self.rscript_executable_edit.text().strip()
        if hasattr(self, "r_github_repo_edit"):
            self.settings["r_github_repo"] = self.r_github_repo_edit.text().strip() or "Pete-s-Lab/CV3D"
        if hasattr(self, "r_step03a_script_edit"):
            self.settings["r_step03a_script_path"] = self.r_step03a_script_edit.text().strip()
        if hasattr(self, "r_step03a2_script_edit"):
            self.settings["r_step03a2_script_path"] = self.r_step03a2_script_edit.text().strip()
        if hasattr(self, "r_step03a_plot_script_edit"):
            self.settings["r_step03a_plot_script_path"] = self.r_step03a_plot_script_edit.text().strip()
        if hasattr(self, "r_step03a2_plot_script_edit"):
            self.settings["r_step03a2_plot_script_path"] = self.r_step03a2_plot_script_edit.text().strip()
        if hasattr(self, "r_step03b_script_edit"):
            self.settings["r_step03b_script_path"] = self.r_step03b_script_edit.text().strip()
        if hasattr(self, "r_step03b_plot_script_edit"):
            self.settings["r_step03b_plot_script_path"] = self.r_step03b_plot_script_edit.text().strip()
        if hasattr(self, "r_step03c_script_edit"):
            self.settings["r_step03c_script_path"] = self.r_step03c_script_edit.text().strip()
        if hasattr(self, "r_step05a_script_edit"):
            self.settings["r_step05a_script_path"] = self.r_step05a_script_edit.text().strip()
        if hasattr(self, "r_step05b_script_edit"):
            self.settings["r_step05b_script_path"] = self.r_step05b_script_edit.text().strip()
        if hasattr(self, "r_step05c_script_edit"):
            self.settings["r_step05c_script_path"] = self.r_step05c_script_edit.text().strip()
        save_app_settings(self.settings)

        blender_exe = configured_file_path(self.settings.get("blender_executable", ""))
        blender_script = configured_file_path(self.settings.get("blender_script_path", ""))

        if blender_exe is None:
            QMessageBox.warning(self, "Blender executable missing", "Set a valid Blender executable in Settings first.")
            self.nav.setCurrentRow(6)
            return

        if blender_script is None:
            QMessageBox.warning(self, "Blender helper script missing", "Set a valid CV3D Blender helper .py file in Settings first.")
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]

        blend_launch_mode = self.preflight_existing_blender_file(eye)
        if blend_launch_mode == "cancel":
            return

        try:
            task_path = self.create_blender_step02_task(eye)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cannot create Blender task",
                "Could not read required Step 02 input metadata.\n\n"
                f"{e}"
            )
            return

        existing_blend_path = self.analysis_folder / files["cornea_blend_file"]
        opening_existing_blend = blend_launch_mode == "open_existing" and existing_blend_path.exists()

        reply = QMessageBox.question(
            self,
            "Launch Blender",
            "This will open Blender for interactive cornea extraction.\\n\\n"
            f"CV ID: {cv_id}\\n"
            f"Eye: {eye}\\n"
            f"Input STL: {files.get('selected_raw_stl_file')}\\n"
            f"Output STL: {files.get('cornea_stl_file')}\\n"
            f"Output blend: {files.get('cornea_blend_file')}\\n"
            f"Launch mode: {'open existing .blend' if opening_existing_blend else 'start new from source STL'}\\n\\n"
            "In Blender, use the CV3D panel to export the selected cornea object, then close Blender.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        state_ref = self.status["workflow_steps"]["02_blender_cornea_extraction"][eye]
        before = state_ref.get("state", "not_started")
        state_ref["state"] = "running"
        state_ref["symbol"] = STATE_SYMBOL["running"]
        state_ref["last_run"] = now()
        state_ref["needs_rerun"] = False
        state_ref["messages"] = ["Blender launched interactively."]
        self.save_current_files()
        self.refresh_all()

        if opening_existing_blend:
            cmd = [str(blender_exe), str(existing_blend_path), "--python", str(blender_script), "--", relative_task_argument(task_path, self.analysis_folder)]
        else:
            cmd = [str(blender_exe), "--python", str(blender_script), "--", relative_task_argument(task_path, self.analysis_folder)]

        try:
            result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder))
            exit_code = result.returncode
        except Exception as e:
            self.set_eye_step_state("02_blender_cornea_extraction", eye, "failed", [f"Could not launch Blender: {e}"])
            append_log(self.analysis_folder, cv_id, eye, "02_blender_cornea_extraction", "launch_blender", before, "failed", "failed", str(e))
            self.save_current_files()
            self.refresh_all()
            QMessageBox.critical(self, "Blender launch failed", str(e))
            return

        self.load_current_files()
        files = self.config["eyes"][eye]["files"]
        status_path = self.analysis_folder / files["blender_step02_status_file"]
        output_stl = self.analysis_folder / files["cornea_stl_file"]
        output_blend = self.analysis_folder / files["cornea_blend_file"]

        blender_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                blender_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                blender_status = "unreadable_status_json"
                status_message = str(e)

        if exit_code == 0 and output_stl.exists() and output_blend.exists() and blender_status in ["exported", "complete", "complete_with_warning"]:
            messages = [f"Blender finished with status: {blender_status}."]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("02_blender_cornea_extraction", eye, "complete", messages)
            self.mark_downstream_needs_rerun("02_blender_cornea_extraction", eye)
            append_log(self.analysis_folder, cv_id, eye, "02_blender_cornea_extraction", "launch_blender", before, "complete", "success", "; ".join(messages))
        else:
            messages = [
                f"Blender exit code: {exit_code}.",
                f"Blender status file status: {blender_status}.",
                f"Cornea STL exists: {output_stl.exists()}.",
                f"Blend file exists: {output_blend.exists()}.",
            ]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("02_blender_cornea_extraction", eye, "failed", messages)
            append_log(self.analysis_folder, cv_id, eye, "02_blender_cornea_extraction", "launch_blender", before, "failed", "failed", "; ".join(messages))

        self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()


    def browse_rscript_executable(self) -> None:
        start = self.settings.get("rscript_executable") or str(Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Rscript executable",
            start,
            "Executables (*.exe);;All files (*)"
        )
        if file_path:
            self.rscript_executable_edit.setText(file_path)
            self.settings["rscript_executable"] = file_path
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def r_setup_values_from_ui(self) -> None:
        if hasattr(self, "rscript_executable_edit"):
            self.settings["rscript_executable"] = self.rscript_executable_edit.text().strip()
        if hasattr(self, "r_github_repo_edit"):
            self.settings["r_github_repo"] = self.r_github_repo_edit.text().strip() or "Pete-s-Lab/CV3D"
        if hasattr(self, "r_step03a_script_edit"):
            self.settings["r_step03a_script_path"] = self.r_step03a_script_edit.text().strip()
        if hasattr(self, "r_step03a2_script_edit"):
            self.settings["r_step03a2_script_path"] = self.r_step03a2_script_edit.text().strip()
        if hasattr(self, "r_step03a_plot_script_edit"):
            self.settings["r_step03a_plot_script_path"] = self.r_step03a_plot_script_edit.text().strip()
        if hasattr(self, "r_step03a2_plot_script_edit"):
            self.settings["r_step03a2_plot_script_path"] = self.r_step03a2_plot_script_edit.text().strip()
        if hasattr(self, "r_step03b_script_edit"):
            self.settings["r_step03b_script_path"] = self.r_step03b_script_edit.text().strip()
        if hasattr(self, "r_step03b_plot_script_edit"):
            self.settings["r_step03b_plot_script_path"] = self.r_step03b_plot_script_edit.text().strip()
        if hasattr(self, "r_step03c_script_edit"):
            self.settings["r_step03c_script_path"] = self.r_step03c_script_edit.text().strip()
        save_app_settings(self.settings)

    def run_rscript_expression(self, expression: str, title: str = "Rscript") -> tuple[bool, str]:
        self.r_setup_values_from_ui()
        rscript = configured_file_path(self.settings.get("rscript_executable", ""))

        if rscript is None:
            QMessageBox.warning(
                self,
                "Rscript executable missing",
                "Set a valid Rscript executable in Settings first.\n\n"
                "This should point to Rscript.exe, not R.exe, Rgui.exe, RStudio, or the R installation folder."
            )
            self.nav.setCurrentRow(6)
            return False, ""

        result = self.run_blocking_process(
            [str(rscript), "-e", expression],
            cwd=str(self.project_folder or Path.home()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = (
            f"Command exit code: {result.returncode}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )
        return result.returncode == 0, output

    def check_r_setup(self) -> None:
        self.r_setup_values_from_ui()
        repo = self.settings.get("r_github_repo", "Pete-s-Lab/CV3D")
        expr = (
            'cat(R.version.string, "\\n"); '
            'cat("Rscript:", file.path(R.home("bin"), "Rscript"), "\\n"); '
            'ok <- requireNamespace("CV3D", quietly=TRUE); '
            'cat("CV3D installed:", ok, "\\n"); '
            'if (ok) cat("CV3D version:", as.character(utils::packageVersion("CV3D")), "\\n")'
        )
        ok, output = self.run_rscript_expression(expr, "Check R setup")
        QMessageBox.information(self, "R setup check", f"GitHub repo setting: {repo}\nR package namespace: CV3D\n\n{output}")

    def install_or_update_r_package_from_github(self) -> bool:
        self.r_setup_values_from_ui()
        repo = self.settings.get("r_github_repo", "Pete-s-Lab/CV3D")

        reply = QMessageBox.question(
            self,
            "Install/update CV3D R package from GitHub",
            "This will run Rscript and install/update the CV3D R package from the CV3D GitHub repository.\n\n"
            f"Repository: {repo}\n\n"
            "This may take a while and may install missing R dependencies.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return False

        expr = (
            'options(repos=c(CRAN="https://cloud.r-project.org")); '
            'if (!requireNamespace("remotes", quietly=TRUE)) install.packages("remotes"); '
            f'remotes::install_github("{repo}", upgrade="never", dependencies=TRUE); '
            'cat("CV3D installed/updated. Version:", as.character(utils::packageVersion("CV3D")), "\\n")'
        )
        ok, output = self.run_rscript_expression(expr, "Install/update R package")
        if ok:
            QMessageBox.information(self, "R package installed/updated", output)
        else:
            QMessageBox.warning(self, "R package installation failed", output)
        return ok

    def ensure_r_package_installed(self) -> bool:
        self.r_setup_values_from_ui()
        repo = self.settings.get("r_github_repo", "Pete-s-Lab/CV3D")
        expr = (
            'ok <- requireNamespace("CV3D", quietly=TRUE); '
            'if (!ok) quit(status=2, save="no"); '
            'cat("CV3D version:", as.character(utils::packageVersion("CV3D")), "\\n")'
        )
        ok, output = self.run_rscript_expression(expr, "Check CV3D package")
        if ok:
            return True

        reply = QMessageBox.question(
            self,
            "CV3D R package missing",
            "Rscript is available, but the CV3D R package is not installed.\n\n"
            f"Repository: {repo}\n\n"
            "Install it from GitHub now?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            QMessageBox.warning(self, "R package missing", output)
            return False

        return self.install_or_update_r_package_from_github()

    def browse_helper_script_setting(self, key: str, edit_attr: str, title: str, file_filter: str) -> None:
        start = helper_file_dialog_start(self.settings, key)
        file_path, _ = QFileDialog.getOpenFileName(self, title, start, file_filter)
        if file_path:
            stored = helper_path_for_storage(key, file_path)
            if hasattr(self, edit_attr):
                getattr(self, edit_attr).setText(stored)
            self.settings[key] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_r_step03a_script(self) -> None:
        start = helper_file_dialog_start(self.settings, "r_step03a_script_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D R Step 03A runner",
            start,
            "R scripts (*.R *.r);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("r_step03a_script_path", file_path)
            self.r_step03a_script_edit.setText(stored)
            self.settings["r_step03a_script_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_r_step03a2_script(self) -> None:
        start = helper_file_dialog_start(self.settings, "r_step03a2_script_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D R Step 03A2 normalization runner",
            start,
            "R scripts (*.R *.r);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("r_step03a2_script_path", file_path)
            self.r_step03a2_script_edit.setText(stored)
            self.settings["r_step03a2_script_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_r_step03a_plot_script(self) -> None:
        start = helper_file_dialog_start(self.settings, "r_step03a_plot_script_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D R raw local-height 3D plot runner",
            start,
            "R scripts (*.R *.r);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("r_step03a_plot_script_path", file_path)
            self.r_step03a_plot_script_edit.setText(stored)
            self.settings["r_step03a_plot_script_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_r_step03a2_plot_script(self) -> None:
        start = helper_file_dialog_start(self.settings, "r_step03a2_plot_script_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D R local-height 3D plot runner",
            start,
            "R scripts (*.R *.r);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("r_step03a2_plot_script_path", file_path)
            self.r_step03a2_plot_script_edit.setText(stored)
            self.settings["r_step03a2_plot_script_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_r_step03b_script(self) -> None:
        start = helper_file_dialog_start(self.settings, "r_step03b_script_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D R Step 03B thresholding runner",
            start,
            "R scripts (*.R *.r);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("r_step03b_script_path", file_path)
            self.r_step03b_script_edit.setText(stored)
            self.settings["r_step03b_script_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_r_step03b_plot_script(self) -> None:
        start = helper_file_dialog_start(self.settings, "r_step03b_plot_script_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D R thresholded local-height 3D plot runner",
            start,
            "R scripts (*.R *.r);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("r_step03b_plot_script_path", file_path)
            self.r_step03b_plot_script_edit.setText(stored)
            self.settings["r_step03b_plot_script_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def local_height_thresholding_input_options(self, eye: str) -> Dict[str, Any]:
        files = self.config["eyes"][eye]["files"]
        raw_rel = files["local_heights_file"]
        norm_rel = files["local_heights_normalized_file"]

        raw_path = self.analysis_folder / raw_rel
        norm_path = self.analysis_folder / norm_rel

        raw_state = self.status["workflow_steps"]["03a_local_height_calculation"][eye].get("state")
        norm_state = self.status["workflow_steps"]["03a2_local_height_normalization"][eye].get("state")

        raw_available = raw_state in ["complete", "complete_with_warning"] and raw_path.exists()
        norm_available = norm_state in ["complete", "complete_with_warning"] and norm_path.exists()

        return {
            "raw_rel": raw_rel,
            "raw_abs": raw_path,
            "raw_available": raw_available,
            "raw_column": "local_height_contrast",
            "norm_rel": norm_rel,
            "norm_abs": norm_path,
            "norm_available": norm_available,
            "norm_column": "local_height_norm_contrast",
        }

    def create_r_step03b_preview_task(self, eye: str, input_mode: str, height_column: str, min_threshold: float, max_threshold: float) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        opts = self.local_height_thresholding_input_options(eye)

        if input_mode == "normalized_local_heights":
            input_rel = opts["norm_rel"]
            input_abs = opts["norm_abs"]
        else:
            input_rel = opts["raw_rel"]
            input_abs = opts["raw_abs"]

        task_rel = eye_json_rel_path(eye, f"03BPREV_{cv_id}_{eye}_R_task.json")
        status_rel = eye_json_rel_path(eye, f"03BPREV_{cv_id}_{eye}_R_status.json")
        stdout_rel = eye_log_rel_path(eye, f"03BPREV_{cv_id}_{eye}_R_stdout.log")
        stderr_rel = eye_log_rel_path(eye, f"03BPREV_{cv_id}_{eye}_R_stderr.log")
        preview_plot_rel = eye_inspection_rel_path(eye, f"03B_{cv_id}_{eye}_local_height.png")

        task = {
            "task_type": "local_height_thresholding_preview",
            "preview_only": True,
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_mode": input_mode,
            "input_local_heights": input_rel,
            "input_local_heights_abs": str(input_abs),
            "height_column": height_column,
            "min_threshold": min_threshold,
            "max_threshold": max_threshold,
            "local_height_threshold": None,
            "output_threshold_preview_plot": preview_plot_rel,
            "output_threshold_preview_plot_abs": str(self.analysis_folder / preview_plot_rel),
            "status_file": status_rel,
            "status_file_abs": str(self.analysis_folder / status_rel),
            "stdout_file": stdout_rel,
            "stdout_file_abs": str(self.analysis_folder / stdout_rel),
            "stderr_file": stderr_rel,
            "stderr_file_abs": str(self.analysis_folder / stderr_rel),
            "notes": "Created by CV3D Python controller for 03B local-height viridis preview before final thresholding."
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)
        return task_path

    def run_r_03b_local_height_preview(self, eye: str, input_mode: str, height_column: str, min_threshold: float, max_threshold: float, rscript: Path, runner: Path) -> tuple[bool, Optional[Path]]:
        """Create/open the local-height preview before the final 03B threshold is set."""
        cv_id = self.config["dataset_identity"]["cv_id"]
        try:
            task_path = self.create_r_step03b_preview_task(
                eye=eye,
                input_mode=input_mode,
                height_column=height_column,
                min_threshold=min_threshold,
                max_threshold=max_threshold,
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cannot create R 03B preview task",
                "Could not create required 03B preview metadata.\n\n"
                f"{e}"
            )
            return False, None

        task = read_json(task_path)
        stdout_path = resolve_task_path(task, "stdout_file_abs", self.analysis_folder)
        stderr_path = resolve_task_path(task, "stderr_file_abs", self.analysis_folder)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        launch_diag_path = self.analysis_folder / eye_log_rel_path(eye, f"03BPREV_{cv_id}_{eye}_R_launch_command.txt")
        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]

        try:
            write_text(
                launch_diag_path,
                "Command:\n" + " ".join(f'"{part}"' for part in cmd) + "\n\n"
                f"Working directory:\n{self.analysis_folder}\n"
            )
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_diag_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            QMessageBox.critical(self, "R 03B preview launch failed", str(e))
            self.refresh_all()
            return False, None

        status_path = resolve_task_path(task, "status_file_abs", self.analysis_folder)
        preview_plot_path = resolve_task_path(task, "output_threshold_preview_plot_abs", self.analysis_folder)
        runner_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                runner_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                runner_status = "unreadable_status_json"
                status_message = str(e)

        self.refresh_all()

        if exit_code == 0 and runner_status in ["success", "success_preview"] and preview_plot_path.exists():
            return True, preview_plot_path

        details = [
            f"Rscript exit code: {exit_code}",
            f"Runner status: {runner_status}",
            f"Preview plot exists: {preview_plot_path.exists()}",
            f"Launch log: {launch_diag_path.relative_to(self.analysis_folder)}",
            f"stdout log: {task['stdout_file']}",
            f"stderr log: {task['stderr_file']}",
        ]
        if status_message:
            details.append(status_message)
        QMessageBox.warning(
            self,
            "03B preview creation failed",
            "The local-height preview could not be created.\n\n" + "\n".join(details)
        )
        return False, None


    def create_r_step03b_task(self, eye: str, input_mode: str, height_column: str, min_threshold: float, max_threshold: float, threshold: float) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        task_rel = files["r_step03b_task_file"]

        opts = self.local_height_thresholding_input_options(eye)
        if input_mode == "normalized_local_heights":
            input_rel = opts["norm_rel"]
            input_abs = opts["norm_abs"]
        else:
            input_rel = opts["raw_rel"]
            input_abs = opts["raw_abs"]

        task = {
            "task_type": "local_height_thresholding",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_mode": input_mode,
            "input_local_heights": input_rel,
            "input_local_heights_abs": str(input_abs),
            "height_column": height_column,
            "min_threshold": min_threshold,
            "max_threshold": max_threshold,
            "local_height_threshold": threshold,
            "output_local_height_thresholded": files["local_height_thresholded_file"],
            "output_local_height_thresholded_abs": str(self.analysis_folder / files["local_height_thresholded_file"]),
            "output_threshold_preview_plot": eye_inspection_rel_path(eye, f"03B_{cv_id}_{eye}_local_height.png"),
            "output_threshold_preview_plot_abs": str(self.analysis_folder / eye_inspection_rel_path(eye, f"03B_{cv_id}_{eye}_local_height.png")),
            "status_file": files["r_step03b_status_file"],
            "status_file_abs": str(self.analysis_folder / files["r_step03b_status_file"]),
            "stdout_file": eye_log_rel_path(eye, f"03B_{cv_id}_{eye}_R_stdout.log"),
            "stdout_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"03B_{cv_id}_{eye}_R_stdout.log")),
            "stderr_file": eye_log_rel_path(eye, f"03B_{cv_id}_{eye}_R_stderr.log"),
            "stderr_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"03B_{cv_id}_{eye}_R_stderr.log")),
            "notes": "Created by CV3D Python controller for R Step 03B local-height thresholding."
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)
        return task_path

    def launch_r_03b_local_height_thresholding(self, eye: str) -> None:
        """Launch Rscript for Step 03B local-height thresholding."""
        if not self.ensure_step_ready("03b_local_height_thresholding", eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = configured_file_path(self.settings.get("r_step03b_script_path", ""))

        if rscript is None:
            QMessageBox.warning(
                self,
                "Rscript executable missing",
                "Set a valid Rscript executable in Settings first.\n\n"
                "This should point to Rscript.exe, e.g.\n"
                "C:\\Program Files\\R\\R-4.x.x\\bin\\Rscript.exe"
            )
            self.nav.setCurrentRow(6)
            return

        if not self.ensure_r_package_installed():
            return

        if runner is None:
            QMessageBox.warning(self, "R Step 03B runner missing", "Set a valid CV3D R Step 03B thresholding runner .R file in Settings first.")
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        opts = self.local_height_thresholding_input_options(eye)

        if not opts["raw_available"]:
            QMessageBox.warning(
                self,
                "Raw local heights missing",
                "03B requires completed 03A raw local heights.\n\n"
                f"Required file: {opts['raw_rel']}"
            )
            self.refresh_all()
            return

        defaults = self.config["parameters"]["dataset_defaults"]

        dlg = LocalHeightThresholdDialog(
            "03B Local-height thresholding — preview setup",
            raw_label=f"{opts['raw_rel']}  |  column: local_height_contrast",
            normalized_label=f"{opts['norm_rel']}  |  column: local_height_norm_contrast",
            normalized_available=opts["norm_available"],
            default_normalized=opts["norm_available"],
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        preview_params = dlg.values

        preview_ok, preview_plot_path = self.run_r_03b_local_height_preview(
            eye=eye,
            input_mode=preview_params["input_mode"],
            height_column=preview_params["height_column"],
            min_threshold=float(preview_params["min_threshold"]),
            max_threshold=float(preview_params["max_threshold"]),
            rscript=rscript,
            runner=runner,
        )
        if not preview_ok:
            return

        if preview_plot_path and preview_plot_path.exists():
            # This preview is part of choosing the final threshold, so it should
            # open automatically before the final-threshold prompt.
            self.open_local_path(preview_plot_path, "03B local-height preview plot")

        mode_default = 0.5
        suggested_final = self.get_suggested_value(eye, "local_height_threshold", defaults.get("local_height_threshold", mode_default))
        try:
            suggested_final = float(suggested_final)
        except (TypeError, ValueError):
            suggested_final = mode_default
        if not (float(preview_params["min_threshold"]) <= suggested_final <= float(preview_params["max_threshold"])):
            suggested_final = mode_default

        final_dlg = FinalThresholdDialog(
            "03B Local-height thresholding — final threshold",
            suggested_threshold=suggested_final,
            min_threshold=float(preview_params["min_threshold"]),
            max_threshold=float(preview_params["max_threshold"]),
            parent=self,
        )
        if final_dlg.exec() != QDialog.Accepted:
            return

        params = {**preview_params, **final_dlg.values}
        try:
            task_path = self.create_r_step03b_task(
                eye=eye,
                input_mode=params["input_mode"],
                height_column=params["height_column"],
                min_threshold=float(params["min_threshold"]),
                max_threshold=float(params["max_threshold"]),
                threshold=float(params["local_height_threshold"]),
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cannot create R 03B task",
                "Could not create required Step 03B task metadata.\n\n"
                f"{e}"
            )
            return

        task = read_json(task_path)
        reply = QMessageBox.question(
            self,
            "Launch R Step 03B",
            "This will threshold local-height points in R.\n\n"
            f"CV ID: {cv_id}\n"
            f"Eye: {eye}\n"
            f"Input mode: {task.get('input_mode')}\n"
            f"Input CSV: {task.get('input_local_heights')}\n"
            f"Height column: {task.get('height_column')}\n"
            f"Preview min threshold: {task.get('min_threshold')}\n"
            f"Preview max threshold: {task.get('max_threshold')}\n"
            f"Final threshold: {task.get('local_height_threshold')}\n"
            f"Output CSV: {task.get('output_local_height_thresholded')}\n\n"
            "After successful thresholding, CV3D will automatically save the thresholded local-height 3D PNG and open the interactive 3D plot.\n"
            "The interactive plot remains open until you close it.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        state_ref = self.status["workflow_steps"]["03b_local_height_thresholding"][eye]
        before = state_ref.get("state", "not_started")
        state_ref["state"] = "running"
        state_ref["symbol"] = STATE_SYMBOL["running"]
        state_ref["last_run"] = now()
        state_ref["needs_rerun"] = False
        state_ref["messages"] = ["Rscript launched for Step 03B local-height thresholding."]
        self.save_current_files()
        self.refresh_all()

        stdout_path = resolve_task_path(task, "stdout_file_abs", self.analysis_folder)
        stderr_path = resolve_task_path(task, "stderr_file_abs", self.analysis_folder)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        launch_diag_path = self.analysis_folder / eye_log_rel_path(eye, f"03B_{cv_id}_{eye}_R_launch_command.txt")
        write_text(
            launch_diag_path,
            "Command:\n" + " ".join(f'"{part}"' for part in cmd) + "\n\n"
            f"Working directory:\n{self.analysis_folder}\n"
        )

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_diag_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            self.set_eye_step_state("03b_local_height_thresholding", eye, "failed", [f"Could not launch Rscript: {e}"])
            append_log(self.analysis_folder, cv_id, eye, "03b_local_height_thresholding", "launch_rscript", before, "failed", "failed", str(e))
            self.save_current_files()
            self.refresh_all()
            QMessageBox.critical(self, "Rscript launch failed", str(e))
            return

        self.load_current_files()
        files = self.config["eyes"][eye]["files"]
        status_path = self.analysis_folder / files["r_step03b_status_file"]
        output_thresholded = self.analysis_folder / files["local_height_thresholded_file"]

        r_status = "unknown"
        status_message = ""
        warnings = []
        thresholded_count = None
        if status_path.exists():
            try:
                payload = read_json(status_path)
                r_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
                warnings = payload.get("warnings", []) or []
                thresholded_count = payload.get("summary", {}).get("thresholded_point_count")
            except Exception as e:
                r_status = "unreadable_status_json"
                status_message = str(e)

        thresholding_succeeded = exit_code == 0 and r_status == "success" and output_thresholded.exists()
        if thresholding_succeeded:
            messages = [f"R Step 03B finished with status: {r_status}."]
            if thresholded_count is not None:
                messages.append(f"Thresholded point count: {thresholded_count}.")
            if status_message:
                messages.append(status_message)
            messages.extend(str(w) for w in warnings)
            state = "complete_with_warning" if warnings else "complete"
            self.set_eye_step_state("03b_local_height_thresholding", eye, state, messages)
            self.mark_downstream_needs_rerun("03b_local_height_thresholding", eye)
            append_log(self.analysis_folder, cv_id, eye, "03b_local_height_thresholding", "launch_rscript", before, state, "success", "; ".join(messages))
        else:
            messages = [
                f"Rscript exit code: {exit_code}.",
                f"R status file status: {r_status}.",
                f"Thresholded CSV exists: {output_thresholded.exists()}.",
                f"stdout log: {task['stdout_file']}",
                f"stderr log: {task['stderr_file']}",
            ]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("03b_local_height_thresholding", eye, "failed", messages)
            append_log(self.analysis_folder, cv_id, eye, "03b_local_height_thresholding", "launch_rscript", before, "failed", "failed", "; ".join(messages))

        if params.get("update_default"):
            self.config["parameters"]["dataset_defaults"]["local_height_threshold_min"] = float(params["min_threshold"])
            self.config["parameters"]["dataset_defaults"]["local_height_threshold_max"] = float(params["max_threshold"])
            self.config["parameters"]["dataset_defaults"]["local_height_threshold"] = float(params["local_height_threshold"])
        self.config["parameters"][f"{eye}_last_used"]["local_height_threshold_min"] = float(params["min_threshold"])
        self.config["parameters"][f"{eye}_last_used"]["local_height_threshold_max"] = float(params["max_threshold"])
        self.config["parameters"][f"{eye}_last_used"]["local_height_threshold"] = float(params["local_height_threshold"])
        self.config["parameter_history"].append({
            "timestamp": now(),
            "eye": eye,
            "step": "03B",
            "parameter_values": {
                "input_mode": params["input_mode"],
                "height_column": params["height_column"],
                "min_threshold": float(params["min_threshold"]),
                "max_threshold": float(params["max_threshold"]),
                "local_height_threshold": float(params["local_height_threshold"]),
            },
            "result": r_status,
        })

        self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()

        if thresholding_succeeded:
            self.plot_thresholded_local_heights_3d(eye, automatic=True)

    def plot_thresholded_local_heights_3d(self, eye: str, automatic: bool = False) -> None:
        """Create a 3D PNG preview of 03B thresholded points on the eye."""
        if not self.ensure_eye_and_dataset(eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = configured_file_path(self.settings.get("r_step03b_plot_script_path", ""))

        if rscript is None:
            QMessageBox.warning(
                self,
                "Rscript executable missing",
                "Set a valid Rscript executable in Settings first.\n\n"
                "This should point to Rscript.exe, e.g.\n"
                "C:\\Program Files\\R\\R-4.x.x\\bin\\Rscript.exe"
            )
            self.nav.setCurrentRow(6)
            return

        if runner is None:
            QMessageBox.warning(
                self,
                "R thresholded local-height 3D plot runner missing",
                "Set a valid CV3D R thresholded local-height 3D plot runner .R file in Settings first."
            )
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        thr_state = self.status["workflow_steps"]["03b_local_height_thresholding"][eye].get("state")
        thresholded_rel = files["local_height_thresholded_file"]
        thresholded_path = self.analysis_folder / thresholded_rel
        if thr_state not in ["complete", "complete_with_warning"] or not thresholded_path.exists():
            QMessageBox.warning(
                self,
                "Thresholded local-height points not ready",
                f"03B must be complete and the thresholded local-height CSV must exist for {eye}.\n\n"
                f"03B state: {thr_state}\n"
                f"Required file: {thresholded_rel}\n"
                f"Exists: {thresholded_path.exists()}"
            )
            self.validate_current_workflow_outputs(save_changes=True)
            self.refresh_all()
            return

        task03b_path = self.analysis_folder / files["r_step03b_task_file"]
        if task03b_path.exists():
            task03b = read_json(task03b_path)
            input_rel = task03b.get("input_local_heights") or files["local_heights_file"]
            height_column = task03b.get("height_column") or "local_height_contrast"
            height_column = {
                "local_height_log": "local_height_contrast",
                "local_height_exp10": "local_height_contrast",
                "local_height_log_norm": "local_height_norm_contrast",
                "local_height_norm_exp10": "local_height_norm_contrast",
            }.get(height_column, height_column)
            input_mode = task03b.get("input_mode") or "raw_local_heights"
            threshold = task03b.get("local_height_threshold")
        else:
            input_rel = files["local_heights_file"]
            height_column = "local_height_contrast"
            input_mode = "raw_local_heights"
            threshold = None

        input_path = self.analysis_folder / input_rel
        if not input_path.exists():
            QMessageBox.warning(self, "Missing 03B source table", f"The source table used for 03B is missing:\n\n{input_rel}")
            return

        if automatic:
            # Automatic post-threshold plotting is an inspection step: keep the
            # interactive rgl window alive until the user closes it. The R runner
            # owns that lifetime, so the blocking process call below intentionally
            # waits while the window remains open.
            open_rgl_window = True
        else:
            open_reply = QMessageBox.question(
                self,
                "Open interactive rgl window?",
                "Create the PNG preview only, or also keep an interactive rgl window open for inspection?\n\n"
                "If you choose Yes, the GUI will wait until you close the rgl window.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No
            )
            if open_reply == QMessageBox.StandardButton.Cancel:
                return
            open_rgl_window = (open_reply == QMessageBox.StandardButton.Yes)

        task_rel = eye_json_rel_path(eye, f"03BP_{cv_id}_{eye}_R_task.json")
        status_rel = eye_json_rel_path(eye, f"03BP_{cv_id}_{eye}_R_status.json")
        stdout_rel = eye_log_rel_path(eye, f"03BP_{cv_id}_{eye}_R_stdout.log")
        stderr_rel = eye_log_rel_path(eye, f"03BP_{cv_id}_{eye}_R_stderr.log")
        launch_rel = eye_log_rel_path(eye, f"03BP_{cv_id}_{eye}_R_launch_command.txt")
        plot_rel = eye_inspection_rel_path(eye, f"03B_{cv_id}_{eye}_local_height_thresholded_3d_plot.png")

        task = {
            "task_type": "thresholded_local_height_3d_plot",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_mode": input_mode,
            "input_local_heights": input_rel,
            "input_local_heights_abs": str(input_path),
            "height_column": height_column,
            "local_height_threshold": threshold,
            "input_local_height_thresholded": thresholded_rel,
            "input_local_height_thresholded_abs": str(thresholded_path),
            "output_plot_png": plot_rel,
            "output_plot_png_abs": str(self.analysis_folder / plot_rel),
            "status_file": status_rel,
            "status_file_abs": str(self.analysis_folder / status_rel),
            "stdout_file": stdout_rel,
            "stdout_file_abs": str(self.analysis_folder / stdout_rel),
            "stderr_file": stderr_rel,
            "stderr_file_abs": str(self.analysis_folder / stderr_rel),
            "open_rgl_window": open_rgl_window,
            "notes": "Created by CV3D Python controller for 03B thresholded local-height 3D plotting."
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)

        if not automatic:
            reply = QMessageBox.question(
                self,
                "Create thresholded local-height 3D plot",
                "This will create a PNG preview of the 03B thresholded points on the eye.\n\n"
                f"CV ID: {cv_id}\n"
                f"Eye: {eye}\n"
                f"Source table: {input_rel}\n"
                f"Thresholded table: {thresholded_rel}\n"
                f"Output PNG: {plot_rel}\n"
                f"Open interactive rgl window: {open_rgl_window}\n\n"
                "The GUI will wait until Rscript finishes.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            if reply != QMessageBox.StandardButton.Ok:
                return

        stdout_path = self.analysis_folder / stdout_rel
        stderr_path = self.analysis_folder / stderr_rel
        launch_diag_path = self.analysis_folder / launch_rel
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        write_text(
            launch_diag_path,
            "Command:\n" + " ".join(f'"{part}"' for part in cmd) + "\n\n"
            f"Working directory:\n{self.analysis_folder}\n"
        )

        if automatic:
            try:
                out = stdout_path.open("w", encoding="utf-8", errors="replace")
                err = stderr_path.open("w", encoding="utf-8", errors="replace")
                try:
                    process = subprocess.Popen(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
                finally:
                    out.close()
                    err.close()
                if not hasattr(self, "_background_plot_processes"):
                    self._background_plot_processes = []
                self._background_plot_processes = [p for p in self._background_plot_processes if p.poll() is None]
                self._background_plot_processes.append(process)
                with launch_diag_path.open("a", encoding="utf-8") as f:
                    f.write(f"\nBackground process ID:\n{process.pid}\n")
            except Exception as e:
                QMessageBox.warning(self, "R thresholded 3D plot launch failed", str(e))
            return

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_diag_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            QMessageBox.critical(self, "R thresholded 3D plot launch failed", str(e))
            self.refresh_all()
            return

        status_path = self.analysis_folder / status_rel
        plot_path = resolve_task_path(task, "output_plot_png_abs", self.analysis_folder)
        runner_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                runner_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                runner_status = "unreadable_status_json"
                status_message = str(e)

        self.refresh_all()

        if exit_code == 0 and runner_status == "success" and plot_path.exists():
            # Success is intentionally silent here. The generated PNG path is recorded
            # in the task/status JSON and visible in the console/log panel.
            self.refresh_all()
        else:
            details = [
                f"Rscript exit code: {exit_code}",
                f"Runner status: {runner_status}",
                f"Plot PNG exists: {plot_path.exists()}",
                f"Launch log: {launch_rel}",
                f"stdout log: {stdout_rel}",
                f"stderr log: {stderr_rel}",
            ]
            if status_message:
                details.append(status_message)
            QMessageBox.warning(
                self,
                "Thresholded 3D plot creation failed",
                "The thresholded local-height 3D plotting utility did not finish successfully.\n\n"
                + "\n".join(details)
            )


    def create_r_step03a_task(self, eye: str, neighbourhood_radius: float) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        task_rel = files["r_step03a_task_file"]

        facet_size = self.read_facet_size_estimate_for_task()
        max_cores = int(self.config.get("compute_settings", {}).get("max_cores") or self.settings.get("compute_settings", {}).get("max_cores") or 1)

        task = {
            "task_type": "local_height_calculation",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_cornea_stl": files["cornea_stl_file"],
            "input_cornea_stl_abs": str(self.analysis_folder / files["cornea_stl_file"]),
            "output_triangles_normals": files["triangles_normals_file"],
            "output_triangles_normals_abs": str(self.analysis_folder / files["triangles_normals_file"]),
            "output_local_heights": files["local_heights_file"],
            "output_local_heights_abs": str(self.analysis_folder / files["local_heights_file"]),
            "output_threshold_plot": files["local_height_threshold_plot"],
            "output_threshold_plot_abs": str(self.analysis_folder / files["local_height_threshold_plot"]),
            "status_file": files["r_step03a_status_file"],
            "status_file_abs": str(self.analysis_folder / files["r_step03a_status_file"]),
            "stdout_file": eye_log_rel_path(eye, f"03A_{cv_id}_{eye}_R_stdout.log"),
            "stdout_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"03A_{cv_id}_{eye}_R_stdout.log")),
            "stderr_file": eye_log_rel_path(eye, f"03A_{cv_id}_{eye}_R_stderr.log"),
            "stderr_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"03A_{cv_id}_{eye}_R_stderr.log")),
            "facet_size_estimate": facet_size,
            "local_height_neighbourhood_radius": float(neighbourhood_radius),
            "max_cores": max_cores,
            "invert_local_heights": False,
            "notes": "Created by CV3D Python controller for R Step 03A.",
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)
        return task_path

    def launch_r_03a_local_heights(self, eye: str) -> None:
        """Launch Rscript for Step 03A local height calculation."""
        if not self.ensure_step_ready("03a_local_height_calculation", eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = configured_file_path(self.settings.get("r_step03a_script_path", ""))

        if rscript is None:
            QMessageBox.warning(
                self,
                "Rscript executable missing",
                "Set a valid Rscript executable in Settings first.\n\n"
                "This should point to Rscript.exe, e.g.\n"
                "C:\\Program Files\\R\\R-4.x.x\\bin\\Rscript.exe"
            )
            self.nav.setCurrentRow(6)
            return

        if not self.ensure_r_package_installed():
            return

        if runner is None:
            QMessageBox.warning(self, "R Step 03A runner missing", "Set a valid CV3D R Step 03A runner .R file in Settings first.")
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]

        try:
            facet_size = self.read_facet_size_estimate_for_task()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Facet-size estimate missing",
                "Step 03A needs a facet-size estimate before it can suggest a local-height neighbourhood radius.\n\n"
                f"{e}"
            )
            return

        defaults = self.config["parameters"]["dataset_defaults"]
        if defaults.get("local_height_neighbourhood_radius_factor") is not None:
            default_factor = float(defaults["local_height_neighbourhood_radius_factor"])
        elif defaults.get("local_height_neighbourhood_half_width_factor") is not None:
            default_factor = float(defaults["local_height_neighbourhood_half_width_factor"])
        elif defaults.get("local_height_search_diam_factor") is not None:
            default_factor = float(defaults["local_height_search_diam_factor"]) / 8.0
        else:
            default_factor = 0.5

        last_used = self.config["parameters"].get(f"{eye}_last_used", {})
        if last_used.get("local_height_neighbourhood_radius") is not None:
            suggested_radius = float(last_used["local_height_neighbourhood_radius"])
        elif last_used.get("local_height_neighbourhood_half_width") is not None:
            suggested_radius = float(last_used["local_height_neighbourhood_half_width"])
        elif last_used.get("local_height_search_diam") is not None:
            suggested_radius = float(last_used["local_height_search_diam"]) / 8.0
        else:
            suggested_radius = facet_size * default_factor

        neighbourhood_radius, ok = get_compact_double(
            self,
            "03A local-height neighbourhood",
            "Local-height spherical neighbourhood\n\n"
            f"Facet-size estimate: {facet_size:g}\n"
            "Default suggestion: facet-size estimate × 0.5\n\n"
            "Neighbourhood radius:",
            suggested_radius,
            0.000001,
            1_000_000.0,
        )
        if not ok:
            return

        try:
            task_path = self.create_r_step03a_task(eye, neighbourhood_radius=float(neighbourhood_radius))
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cannot create R 03A task",
                "Could not create required Step 03A task metadata.\n\n"
                f"{e}"
            )
            return

        task = read_json(task_path)
        reply = QMessageBox.question(
            self,
            "Launch R Step 03A",
            "This will run the local height calculation in R. It may take a while.\n\n"
            f"CV ID: {cv_id}\n"
            f"Eye: {eye}\n"
            f"Input cornea STL: {files.get('cornea_stl_file')}\n"
            f"Facet size estimate: {task.get('facet_size_estimate')}\n"
            f"Neighbourhood radius: {task.get('local_height_neighbourhood_radius')}\n"
            f"Max cores: {task.get('max_cores')}\n"
            f"R package: CV3D from {self.settings.get('r_github_repo', 'Pete-s-Lab/CV3D')}\n\n"
            "The GUI will wait until Rscript finishes.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        state_ref = self.status["workflow_steps"]["03a_local_height_calculation"][eye]
        before = state_ref.get("state", "not_started")
        state_ref["state"] = "running"
        state_ref["symbol"] = STATE_SYMBOL["running"]
        state_ref["last_run"] = now()
        state_ref["needs_rerun"] = False
        state_ref["messages"] = ["Rscript launched for Step 03A."]
        self.save_current_files()
        self.refresh_all()

        stdout_path = resolve_task_path(task, "stdout_file_abs", self.analysis_folder)
        stderr_path = resolve_task_path(task, "stderr_file_abs", self.analysis_folder)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        launch_diag_path = self.analysis_folder / eye_log_rel_path(eye, f"03A_{cv_id}_{eye}_R_launch_command.txt")
        write_text(
            launch_diag_path,
            "Command:\n" + " ".join(f'"{part}"' for part in cmd) + "\n\n"
            f"Working directory:\n{self.analysis_folder}\n"
        )

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_diag_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            self.set_eye_step_state("03a_local_height_calculation", eye, "failed", [f"Could not launch Rscript: {e}"])
            append_log(self.analysis_folder, cv_id, eye, "03a_local_height_calculation", "launch_rscript", before, "failed", "failed", str(e))
            self.save_current_files()
            self.refresh_all()
            QMessageBox.critical(self, "Rscript launch failed", str(e))
            return

        self.load_current_files()
        files = self.config["eyes"][eye]["files"]
        status_path = self.analysis_folder / files["r_step03a_status_file"]
        output_tri = self.analysis_folder / files["triangles_normals_file"]
        output_heights = self.analysis_folder / files["local_heights_file"]
        output_plot = self.analysis_folder / files["local_height_threshold_plot"]

        r_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                r_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                r_status = "unreadable_status_json"
                status_message = str(e)

        if exit_code == 0 and r_status == "success" and output_tri.exists() and output_heights.exists() and output_plot.exists():
            messages = [f"R Step 03A finished with status: {r_status}."]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("03a_local_height_calculation", eye, "complete", messages)
            self.mark_downstream_needs_rerun("03a_local_height_calculation", eye)
            append_log(self.analysis_folder, cv_id, eye, "03a_local_height_calculation", "launch_rscript", before, "complete", "success", "; ".join(messages))
        else:
            messages = [
                f"Rscript exit code: {exit_code}.",
                f"R status file status: {r_status}.",
                f"Triangle/normal CSV exists: {output_tri.exists()}.",
                f"Local-height CSV exists: {output_heights.exists()}.",
                f"Threshold plot exists: {output_plot.exists()}.",
                f"stdout log: {task['stdout_file']}",
                f"stderr log: {task['stderr_file']}",
            ]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("03a_local_height_calculation", eye, "failed", messages)
            append_log(self.analysis_folder, cv_id, eye, "03a_local_height_calculation", "launch_rscript", before, "failed", "failed", "; ".join(messages))

        self.config["parameters"][f"{eye}_last_used"]["local_height_neighbourhood_radius"] = float(neighbourhood_radius)
        if facet_size > 0:
            self.config["parameters"]["dataset_defaults"]["local_height_neighbourhood_radius_factor"] = float(neighbourhood_radius) / facet_size

        self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()


    def create_r_step03a2_task(self, eye: str, neighbourhood_radius: float) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        task_rel = files["r_step03a2_task_file"]

        facet_size = self.read_facet_size_estimate_for_task()
        max_cores = int(self.config.get("compute_settings", {}).get("max_cores") or self.settings.get("compute_settings", {}).get("max_cores") or 1)

        task = {
            "task_type": "local_height_normalization",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_local_heights": files["local_heights_file"],
            "input_local_heights_abs": str(self.analysis_folder / files["local_heights_file"]),
            "output_local_heights_normalized": files["local_heights_normalized_file"],
            "output_local_heights_normalized_abs": str(self.analysis_folder / files["local_heights_normalized_file"]),
            "output_normalization_plot": files["local_height_normalization_plot"],
            "output_normalization_plot_abs": str(self.analysis_folder / files["local_height_normalization_plot"]),
            "status_file": files["r_step03a2_status_file"],
            "status_file_abs": str(self.analysis_folder / files["r_step03a2_status_file"]),
            "stdout_file": eye_log_rel_path(eye, f"03A2_{cv_id}_{eye}_R_stdout.log"),
            "stdout_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"03A2_{cv_id}_{eye}_R_stdout.log")),
            "stderr_file": eye_log_rel_path(eye, f"03A2_{cv_id}_{eye}_R_stderr.log"),
            "stderr_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"03A2_{cv_id}_{eye}_R_stderr.log")),
            "facet_size_estimate": facet_size,
            "neighbourhood_radius": neighbourhood_radius,
            "column_to_normalize": "local_height",
            "lower_quantile": 0.10,
            "upper_quantile": 0.90,
            "max_cores": max_cores,
            "notes": "Created by CV3D Python controller for optional R Step 03A2 local-height normalization.",
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)
        return task_path

    def launch_r_03a2_normalize_local_heights(self, eye: str) -> None:
        """Launch optional Rscript Step 03A2 local-height normalization."""
        if not self.ensure_step_ready("03a2_local_height_normalization", eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = configured_file_path(self.settings.get("r_step03a2_script_path", ""))

        if rscript is None:
            QMessageBox.warning(
                self,
                "Rscript executable missing",
                "Set a valid Rscript executable in Settings first.\n\n"
                "This should point to Rscript.exe, e.g.\n"
                "C:\\Program Files\\R\\R-4.x.x\\bin\\Rscript.exe"
            )
            self.nav.setCurrentRow(6)
            return

        if not self.ensure_r_package_installed():
            return

        if runner is None:
            QMessageBox.warning(self, "R Step 03A2 runner missing", "Set a valid CV3D R Step 03A2 normalization runner .R file in Settings first.")
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        self.config["parameters"].setdefault("dataset_defaults", {})
        facet_size = self.read_facet_size_estimate_for_task()
        suggested = facet_size

        dlg = RuntimeParamDialog(
            "03A2 Optional local-height normalization",
            {"neighbourhood_radius": float(suggested)},
            self,
            info_text=(
                f"Default neighbourhood radius: facet-size estimate ({facet_size:g} µm). "
                "Enter the neighbourhood radius to use for normalization."
            ),
        )
        if dlg.exec() != QDialog.Accepted:
            return
        neighbourhood_radius = float(dlg.values["neighbourhood_radius"])

        try:
            task_path = self.create_r_step03a2_task(eye, neighbourhood_radius)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cannot create R 03A2 task",
                "Could not create required Step 03A2 task metadata.\n\n"
                f"{e}"
            )
            return

        task = read_json(task_path)
        reply = QMessageBox.question(
            self,
            "Launch R Step 03A2",
            "This will run optional local-height normalization in R.\n\n"
            f"CV ID: {cv_id}\n"
            f"Eye: {eye}\n"
            f"Input raw local heights: {files.get('local_heights_file')}\n"
            f"Output normalized local heights: {files.get('local_heights_normalized_file')}\n"
            f"Normalization neighbourhood radius: {task.get('neighbourhood_radius')}\n"
            f"Max cores: {task.get('max_cores')}\n\n"
            "The mandatory downstream workflow still uses raw 03A output unless a later step explicitly chooses otherwise.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        state_ref = self.status["workflow_steps"]["03a2_local_height_normalization"][eye]
        before = state_ref.get("state", "not_started")
        state_ref["state"] = "running"
        state_ref["symbol"] = STATE_SYMBOL["running"]
        state_ref["last_run"] = now()
        state_ref["needs_rerun"] = False
        state_ref["messages"] = ["Rscript launched for optional Step 03A2."]
        self.save_current_files()
        self.refresh_all()

        stdout_path = resolve_task_path(task, "stdout_file_abs", self.analysis_folder)
        stderr_path = resolve_task_path(task, "stderr_file_abs", self.analysis_folder)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        launch_diag_path = self.analysis_folder / eye_log_rel_path(eye, f"03A2_{cv_id}_{eye}_R_launch_command.txt")
        write_text(
            launch_diag_path,
            "Command:\n" + " ".join(f'"{part}"' for part in cmd) + "\n\n"
            f"Working directory:\n{self.analysis_folder}\n"
        )

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_diag_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            self.set_eye_step_state("03a2_local_height_normalization", eye, "failed", [f"Could not launch Rscript: {e}"])
            append_log(self.analysis_folder, cv_id, eye, "03a2_local_height_normalization", "launch_rscript", before, "failed", "failed", str(e))
            self.save_current_files()
            self.refresh_all()
            QMessageBox.critical(self, "Rscript launch failed", str(e))
            return

        self.load_current_files()
        files = self.config["eyes"][eye]["files"]
        status_path = self.analysis_folder / files["r_step03a2_status_file"]
        output_norm = self.analysis_folder / files["local_heights_normalized_file"]
        output_plot = self.analysis_folder / files["local_height_normalization_plot"]

        r_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                r_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                r_status = "unreadable_status_json"
                status_message = str(e)

        if exit_code == 0 and r_status == "success" and output_norm.exists() and output_plot.exists():
            messages = [f"R optional Step 03A2 finished with status: {r_status}."]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("03a2_local_height_normalization", eye, "complete", messages)
            if dlg.values.get("update_default"):
                self.config["parameters"].setdefault("dataset_defaults", {})["local_height_normalization_radius"] = neighbourhood_radius
            self.config["parameters"].setdefault(f"{eye}_last_used", {})["local_height_normalization_radius"] = neighbourhood_radius
            append_log(self.analysis_folder, cv_id, eye, "03a2_local_height_normalization", "launch_rscript", before, "complete", "success", "; ".join(messages))
        else:
            messages = [
                f"Rscript exit code: {exit_code}.",
                f"R status file status: {r_status}.",
                f"Normalized local-height CSV exists: {output_norm.exists()}.",
                f"Normalization plot exists: {output_plot.exists()}.",
                f"stdout log: {task['stdout_file']}",
                f"stderr log: {task['stderr_file']}",
            ]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("03a2_local_height_normalization", eye, "failed", messages)
            append_log(self.analysis_folder, cv_id, eye, "03a2_local_height_normalization", "launch_rscript", before, "failed", "failed", "; ".join(messages))

        self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()

    # ---------- project/dataset actions ----------

    def open_project(self) -> None:
        start = self.settings.get("last_project_folder") or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Open / create CV3D project folder", start)
        if not folder:
            return
        self.project_folder = Path(folder)
        self.project_folder.mkdir(parents=True, exist_ok=True)
        self.registry = load_or_create_registry(self.project_folder)
        self.settings["last_project_folder"] = str(self.project_folder)
        save_app_settings(self.settings)

        datasets = self.registry.get("datasets", []) if self.registry else []
        if datasets:
            first_cv_id = datasets[0].get("cv_id")
            if first_cv_id:
                self.load_dataset_by_cv_id(first_cv_id)
            else:
                self.refresh_all()
        else:
            self.analysis_folder = None
            self.config = None
            self.status = None
            self.refresh_all()

    def create_dataset(self) -> None:
        if not self.project_folder or self.registry is None:
            QMessageBox.warning(self, "No project", "Open or create a project folder first.")
            return
        dlg = CreateDatasetDialog(str(self.project_folder), self)
        if dlg.exec() != QDialog.Accepted:
            return
        raw_folder = Path(dlg.values["raw_folder"])
        source_type = str(dlg.values["source_type"])
        source_notes = str(dlg.values["source_notes"])

        cv_id = next_cv_id(self.registry)
        analysis_folder = raw_folder / f"{cv_id}_CV3D"
        analysis_folder.mkdir(exist_ok=False)
        ensure_eye_subfolders(analysis_folder, EYES)

        config = create_initial_config(cv_id, raw_folder, analysis_folder, self.project_folder, self.settings, source_type, source_notes)
        status = create_initial_status(cv_id)

        if source_type != "image_volume":
            status["workflow_steps"]["01_imagej_preprocessing"]["state"] = "skipped"
            status["workflow_steps"]["01_imagej_preprocessing"]["symbol"] = "–"
            status["workflow_steps"]["01_imagej_preprocessing"]["messages"] = ["Dataset starts from STL source."]
            _, stl_messages = assign_source_stls_from_source_folder(config, analysis_folder, force_select=True)
            status["workflow_steps"]["01_imagej_preprocessing"]["messages"].extend(stl_messages)

        write_json(analysis_folder / f"00_{cv_id}_project_config.json", config)
        write_json(analysis_folder / f"00_{cv_id}_status.json", status)
        append_log(analysis_folder, cv_id, "", "00_dataset_setup", "create_dataset", "not_started", "complete", "success")

        self.registry["datasets"].append({
            "cv_id": cv_id,
            "raw_folder_name": raw_folder.name,
            "raw_folder_path": os.path.relpath(str(raw_folder), str(self.project_folder)),
            "analysis_folder": os.path.relpath(str(analysis_folder), str(self.project_folder)),
            "created": now(),
            "status": "active",
            "notes": source_notes,
        })
        self.registry["last_modified"] = now()
        write_json(self.project_folder / REGISTRY_FILE, self.registry)

        self.analysis_folder = analysis_folder
        self.config = config
        self.status = status
        self.refresh_all()
        QMessageBox.information(self, "Dataset created", f"Created {cv_id} in {analysis_folder}")

    def load_current_files(self):
        if not self.analysis_folder or not self.config:
            return
        cv_id = self.config["dataset_identity"]["cv_id"]
        p = dataset_paths(self.analysis_folder, cv_id)
        self.config = read_json(p["config"])
        self.status = read_json(p["status"])
        schema_changed = self.ensure_workflow_schema_current()
        layout_changed = migrate_config_to_eye_subfolders(self.analysis_folder, self.config)
        stl_changed, _ = assign_source_stls_from_source_folder(self.config, self.analysis_folder, force_select=False)
        recovered_states = self.rebuild_workflow_states_from_existing_outputs()
        if schema_changed or layout_changed or stl_changed or recovered_states:
            self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)

    def save_current_files(self):
        if not self.analysis_folder or not self.config or not self.status:
            return
        cv_id = self.config["dataset_identity"]["cv_id"]
        p = dataset_paths(self.analysis_folder, cv_id)
        self.status["last_updated"] = now()
        write_json(p["config"], self.config)
        write_json(p["status"], self.status)

    def ensure_workflow_schema_current(self) -> bool:
        """Add newly introduced workflow/file-map keys to existing datasets."""
        if not self.config or not self.status:
            return False

        cv_id = self.config.get("dataset_identity", {}).get("cv_id")
        if not cv_id:
            return False

        changed = False
        specimen_files = self.config.setdefault("specimen_files", {})
        specimen_defaults = {
            "crop_log_file": f"01_{cv_id}_crop.log",
            "head_mesh_file": f"01_{cv_id}_head_ImageJ.stl",
            "head_landmark_blend_file": f"05_{cv_id}_head_landmarks.blend",
            "head_landmarks_file": f"05_{cv_id}_landmarks.csv",
            "blender_step05_task_file": dataset_json_rel_path(f"05_{cv_id}_Blender_task.json"),
            "blender_step05_status_file": dataset_json_rel_path(f"05_{cv_id}_Blender_status.json"),
        }
        for key, value in specimen_defaults.items():
            if key not in specimen_files:
                specimen_files[key] = value
                changed = True

        # Keep specimen-level task/status JSON out of the analysis-file root.
        # Existing projects created before this layout may still contain flat paths.
        for key in ["blender_step05_task_file", "blender_step05_status_file"]:
            expected = specimen_defaults[key]
            current = specimen_files.get(key)
            if current != expected:
                # Move legacy flat specimen JSON into json/ when possible.
                if self.analysis_folder and current:
                    old_path = self.analysis_folder / current
                    new_path = self.analysis_folder / expected
                    if old_path.exists() and not new_path.exists():
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.move(str(old_path), str(new_path))
                        except Exception:
                            pass
                specimen_files[key] = expected
                changed = True

        # Move the specimen-level Blender launch log from the analysis root into logs/.
        if self.analysis_folder:
            legacy_launch = self.analysis_folder / f"05_{cv_id}_Blender_launch_command.txt"
            nested_launch = self.analysis_folder / dataset_log_rel_path(f"05_{cv_id}_Blender_launch_command.txt")
            if legacy_launch.exists() and not nested_launch.exists():
                nested_launch.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(legacy_launch), str(nested_launch))
                except Exception:
                    pass

        for eye in EYES:
            files = self.config.setdefault("eyes", {}).setdefault(eye, {"present": True, "files": {}}).setdefault("files", {})
            if "sensitivity_acuity_file" in files and "sampling_acuity_file" not in files:
                files["sampling_acuity_file"] = files.pop("sensitivity_acuity_file")
                changed = True
            old_sampling = files.get("sampling_acuity_file")
            new_sampling = eye_file_map(cv_id, eye).get("sampling_acuity_file")
            if old_sampling and new_sampling and str(old_sampling).endswith("_sensitivity_acuity.csv") and old_sampling != new_sampling:
                if self.analysis_folder:
                    _move_existing_file_if_needed(self.analysis_folder, old_sampling, new_sampling)
                files["sampling_acuity_file"] = new_sampling
                changed = True
            for key, value in eye_file_map(cv_id, eye).items():
                if key not in files:
                    files[key] = value
                    changed = True

        workflow = self.status.setdefault("workflow_steps", {})
        for step in STEP_ORDER:
            if step not in workflow:
                workflow[step] = {"label": STEP_LABELS[step]}
                changed = True
            workflow[step].setdefault("label", STEP_LABELS[step])
            for eye in EYES:
                if eye not in workflow[step]:
                    present = bool(self.config.get("eyes", {}).get(eye, {}).get("present", True))
                    workflow[step][eye] = {
                        "state": "not_started" if present else "skipped",
                        "symbol": STATE_SYMBOL["not_started"] if present else STATE_SYMBOL["skipped"],
                        "last_run": None,
                        "needs_rerun": False,
                        "messages": [] if present else [f"{eye} not present in scan."],
                    }
                    changed = True

        step05 = workflow.setdefault("05_blender_head_landmarking", {"label": STEP_LABELS["05_blender_head_landmarking"]})
        step05.setdefault("label", STEP_LABELS["05_blender_head_landmarking"])
        for key, default in {
            "state": "not_started",
            "symbol": "○",
            "last_run": None,
            "needs_rerun": False,
            "messages": [],
        }.items():
            if key not in step05:
                step05[key] = default
                changed = True

        params = self.config.setdefault("parameters", {})
        defaults = params.setdefault("dataset_defaults", {})
        sphere_key = "corneal_projection_sphere_size_cm"
        for container_key in ["dataset_defaults", "eye1_last_used", "eye2_last_used"]:
            container = params.setdefault(container_key, {})
            old_value = container.get(sphere_key)
            try:
                old_value_num = float(old_value)
            except Exception:
                old_value_num = None
            if old_value is None or old_value_num == 2.0:
                container[sphere_key] = 15.0
                changed = True
        if defaults.get("projection_center_mode") in (None, ""):
            defaults["projection_center_mode"] = "between_eyes"
            changed = True
        if defaults.get("local_height_neighbourhood_radius_factor") is None:
            defaults["local_height_neighbourhood_radius_factor"] = 0.5
            changed = True

        return changed

    def workflow_primary_output_keys(self, step: str) -> List[str]:
        """Return biological/data outputs that prove a step has already been run.

        Task/status JSONs are useful provenance, but they are deliberately not used
        here as hard requirements. Older project folders and path-migration patches
        can leave status JSONs stale while the real data products are still present.
        """
        return {
            "02_blender_cornea_extraction": [
                "cornea_stl_file",
                "cornea_blend_file",
            ],
            "03a_local_height_calculation": [
                "triangles_normals_file",
                "local_heights_file",
                "local_height_threshold_plot",
            ],
            "03a2_local_height_normalization": [
                "local_heights_normalized_file",
                "local_height_normalization_plot",
            ],
            "03b_local_height_thresholding": [
                "local_height_thresholded_file",
            ],
            "03c_facet_candidate_condensation": [
                "facet_candidates_file",
            ],
            "04_blender_facet_check_landmarking": [
                "facet_positions_file",
            ],
            "05a_optical_metrics": [
                "optic_parameters_file",
                "facet_normals_file",
                "facet_sizes_file",
                "interfacet_angles_file",
                "sampling_acuity_file",
                "optical_summary_file",
            ],
            "05b_global_coordinate_rotation": [
                "landmark_referenced_coordinates_file",
                "global_aligned_pointcloud_file",
                "global_coordinates_file",
                "global_rotation_matrix_file",
                "global_coordinate_metadata_file",
            ],
            "05c_corneal_projections": [
                "corneal_projections_file",
            ],
        }.get(step, [])

    def workflow_primary_outputs(self, step: str, eye: str) -> List[str]:
        if not self.config:
            return []
        files = self.config.get("eyes", {}).get(eye, {}).get("files", {})
        return [str(files.get(key)) for key in self.workflow_primary_output_keys(step) if files.get(key)]

    def workflow_primary_outputs_present(self, step: str, eye: str) -> bool:
        if not self.analysis_folder:
            return False
        paths = self.workflow_primary_outputs(step, eye)
        return bool(paths) and all((self.analysis_folder / rel_path).exists() for rel_path in paths)

    def rebuild_workflow_states_from_existing_outputs(self) -> bool:
        """Recover workflow/R Analysis state from files that already exist on disk.

        This is intentionally conservative: it only upgrades not-started/skipped/failed
        states when the actual expected data products for a step are present. It does
        not pretend to re-run anything; it marks the step as recovered from disk.
        """
        if not self.config or not self.status or not self.analysis_folder:
            return False

        changed = False
        workflow = self.status.setdefault("workflow_steps", {})
        for step in STEP_ORDER:
            workflow.setdefault(step, {"label": STEP_LABELS.get(step, step)})
            workflow[step].setdefault("label", STEP_LABELS.get(step, step))

        for eye in EYES:
            eye_info = self.config.get("eyes", {}).get(eye, {})
            present = bool(eye_info.get("present", False))
            if not present:
                continue

            is_mirrored = bool(eye_info.get("mirrored", False) or eye_info.get("kind") == "mirrored")
            source_eye = eye_info.get("mirrored_from_eye")
            mirror_plane = eye_info.get("mirror_plane")

            for step in STEP_ORDER:
                if not self.workflow_primary_outputs_present(step, eye):
                    continue

                step_state = workflow[step].setdefault(eye, {})
                current_state = step_state.get("state", "not_started")
                if current_state in {"complete", "complete_with_warning", "needs_rerun", "running"}:
                    continue

                if is_mirrored and step in {"04_blender_facet_check_landmarking", "05a_optical_metrics", "05b_global_coordinate_rotation", "05c_corneal_projections"}:
                    step_state.update({
                        "state": "complete_with_warning",
                        "symbol": "⇄",
                        "last_run": step_state.get("last_run") or now(),
                        "needs_rerun": False,
                        "mirrored": True,
                        "source_eye": source_eye,
                        "mirror_plane": mirror_plane,
                        "messages": [
                            "Recovered from existing mirrored output files on disk; values were mirrored from the source eye and not recalculated."
                        ],
                    })
                else:
                    step_state.update({
                        "state": "complete",
                        "symbol": STATE_SYMBOL["complete"],
                        "last_run": step_state.get("last_run") or now(),
                        "needs_rerun": False,
                        "messages": ["Recovered from existing output files on disk."],
                    })
                changed = True

        specimen_files = self.config.get("specimen_files", {})
        head_landmarks_rel = specimen_files.get("head_landmarks_file")
        if head_landmarks_rel and (self.analysis_folder / str(head_landmarks_rel)).exists():
            step05 = workflow.setdefault("05_blender_head_landmarking", {"label": STEP_LABELS["05_blender_head_landmarking"]})
            if step05.get("state") not in {"complete", "complete_with_warning", "running"}:
                step05.update({
                    "state": "complete",
                    "symbol": STATE_SYMBOL["complete"],
                    "last_run": step05.get("last_run") or now(),
                    "needs_rerun": False,
                    "messages": ["Recovered from existing head-landmark file on disk."],
                })
                changed = True

        return changed

    def workflow_required_outputs(self, step: str, eye: str) -> List[str]:
        """Return data products required for a step to remain complete.

        Status/task JSON files are intentionally excluded. A dataset may have been
        migrated between flat, nested, or relative-path layouts; the biological output
        files are the source of truth for whether the step has usable results.
        """
        return self.workflow_primary_outputs(step, eye)

    def missing_workflow_outputs(self, step: str, eye: str) -> List[str]:
        if not self.analysis_folder:
            return []
        return [
            rel_path
            for rel_path in self.workflow_required_outputs(step, eye)
            if not (self.analysis_folder / rel_path).exists()
        ]

    def validate_current_workflow_outputs(self, save_changes: bool = True) -> List[str]:
        """Synchronize complete workflow states with files on disk.

        Status JSON is useful, but not sufficient: users may delete or replace outputs
        outside the GUI. A step can only remain complete when its expected outputs
        still exist. Missing outputs downgrade the step to needs_rerun and also mark
        completed downstream products as stale.
        """
        if not self.config or not self.status or not self.analysis_folder:
            return []

        changed = False
        messages: List[str] = []
        invalidated_steps: List[tuple[str, str]] = []

        for eye in EYES:
            if not self.config["eyes"].get(eye, {}).get("present", False):
                continue

            for step in STEP_ORDER:
                step_state = self.status["workflow_steps"][step][eye]
                if step_state.get("state") not in ["complete", "complete_with_warning"]:
                    continue

                missing = self.missing_workflow_outputs(step, eye)
                if not missing:
                    continue

                step_state["state"] = "needs_rerun"
                step_state["symbol"] = STATE_SYMBOL["needs_rerun"]
                step_state["needs_rerun"] = True
                step_state["messages"] = [
                    "Expected output file(s) are missing on disk; rerun this step.",
                    *missing,
                ]
                changed = True
                invalidated_steps.append((step, eye))
                messages.append(
                    f"{eye} {STEP_LABELS[step]} marked needs_rerun; missing: {', '.join(missing)}"
                )

        for step, eye in invalidated_steps:
            self.mark_downstream_needs_rerun(step, eye)

        if changed and save_changes:
            self.save_current_files()

        return messages

    def current_workflow_validation_findings(self) -> Dict[str, List[str]]:
        """Return current validation findings after synchronization with disk.

        validate_current_workflow_outputs() reports only newly changed states. This
        helper also reports problems that were already detected automatically during
        refresh/load, especially steps that are already needs_rerun because their
        output files are missing.
        """
        findings = {
            "missing_outputs": [],
            "stale_steps": [],
        }
        if not self.config or not self.status or not self.analysis_folder:
            return findings

        reportable_states = {"complete", "complete_with_warning", "needs_rerun"}
        for eye in EYES:
            if not self.config["eyes"].get(eye, {}).get("present", False):
                continue
            for step in STEP_ORDER:
                step_state = self.status["workflow_steps"][step][eye]
                state = step_state.get("state")
                if state not in reportable_states:
                    continue

                missing = self.missing_workflow_outputs(step, eye)
                if missing:
                    findings["missing_outputs"].append(
                        f"{eye} {STEP_LABELS[step]}: {state}; missing: {', '.join(missing)}"
                    )
                elif state == "needs_rerun":
                    messages = step_state.get("messages") or []
                    reason = "; ".join(str(m) for m in messages) if messages else "rerun required"
                    findings["stale_steps"].append(
                        f"{eye} {STEP_LABELS[step]}: needs_rerun; {reason}"
                    )

        return findings

    def show_workflow_validation_report(self) -> None:
        if not self.config or not self.status or not self.analysis_folder:
            QMessageBox.information(self, "No dataset", "No dataset loaded.")
            return

        newly_changed = self.validate_current_workflow_outputs(save_changes=True)
        findings = self.current_workflow_validation_findings()
        self.refresh_all()

        sections = []
        if newly_changed:
            sections.append(
                "Newly invalidated during this validation:\n"
                + "\n".join(f"- {m}" for m in newly_changed)
            )
        if findings["missing_outputs"]:
            sections.append(
                "Missing required output files:\n"
                + "\n".join(f"- {m}" for m in findings["missing_outputs"])
            )
        if findings["stale_steps"]:
            sections.append(
                "Steps already marked needs_rerun/stale:\n"
                + "\n".join(f"- {m}" for m in findings["stale_steps"])
            )

        if sections:
            report = "Workflow validation found issues for the current dataset.\n\n" + "\n\n".join(sections)
        else:
            report = "Workflow validation OK: all outputs required by complete or stale steps are present, and no step is currently marked needs_rerun."

        QMessageBox.information(self, "Workflow output validation", report)

    def save_dataset_metadata(self) -> None:
        if not self.config:
            return
        self.config["source_data"]["source_type"] = self.source_type_combo.currentText()
        self.config["source_data"]["source_notes"] = self.source_notes.toPlainText()
        imagej_required = self.config["source_data"]["source_type"] == "image_volume"
        self.config["source_data"]["imagej_preprocessing_required"] = imagej_required
        self.config["source_data"]["imagej_preprocessing_skipped"] = not imagej_required

        active, missing = [], []
        for eye in EYES:
            present = self.eye_present[eye].isChecked()
            self.config["eyes"][eye]["present"] = present
            self.config["eyes"][eye]["anatomical_side"] = self.eye_side[eye].currentText()
            self.config["eyes"][eye]["notes"] = self.eye_notes[eye].text()
            self.status["eye_inventory"][eye]["present"] = present
            self.status["eye_inventory"][eye]["state"] = "active" if present else "skipped"
            self.status["eye_inventory"][eye]["symbol"] = "✓" if present else "–"
            self.status["eye_inventory"][eye]["messages"] = [] if present else [f"{eye} not present in scan."]
            if present:
                active.append(eye)
            else:
                missing.append(eye)
                for step in STEP_ORDER:
                    self.status["workflow_steps"][step][eye]["state"] = "skipped"
                    self.status["workflow_steps"][step][eye]["symbol"] = "–"
                    self.status["workflow_steps"][step][eye]["needs_rerun"] = False
                    self.status["workflow_steps"][step][eye]["messages"] = [f"{eye} not present in scan."]

        self.config["eye_inventory"]["active_eyes"] = active
        self.config["eye_inventory"]["missing_eyes"] = missing
        self.config["eye_inventory"]["eye_count_warning"] = len(active) == 1
        warnings = []
        if len(active) == 0:
            warnings.append("At least one eye must be present.")
        if len(active) == 1:
            warnings.append("Only one eye is present in this dataset.")
        self.status["dataset_state"]["warnings"] = warnings

        if not imagej_required:
            self.status["workflow_steps"]["01_imagej_preprocessing"]["state"] = "skipped"
            self.status["workflow_steps"]["01_imagej_preprocessing"]["symbol"] = "–"
            self.status["workflow_steps"]["01_imagej_preprocessing"]["messages"] = ["Dataset starts from STL source."]
            _, stl_messages = assign_source_stls_from_source_folder(self.config, self.analysis_folder, force_select=False)
            self.status["workflow_steps"]["01_imagej_preprocessing"]["messages"].extend(stl_messages)
        else:
            if self.status["workflow_steps"]["01_imagej_preprocessing"]["state"] == "skipped":
                self.status["workflow_steps"]["01_imagej_preprocessing"]["state"] = "not_started"
                self.status["workflow_steps"]["01_imagej_preprocessing"]["symbol"] = "○"
                self.status["workflow_steps"]["01_imagej_preprocessing"]["messages"] = []

        self.save_current_files()
        self.refresh_all()

    def open_analysis_folder(self) -> None:
        if not self.analysis_folder:
            QMessageBox.information(self, "No dataset", "No dataset loaded.")
            return
        self.open_local_path(self.analysis_folder, "analysis folder")

    def save_settings(self) -> None:
        self.settings["compute_settings"]["max_cores"] = self.max_cores_spin.value()
        self.settings["compute_settings"]["user_overridden"] = True
        field_map = {
            "imagej_executable_edit": "imagej_executable",
            "imagej_macro_edit": "imagej_macro_path",
            "imagej_mesh_macro_edit": "imagej_mesh_macro_path",
            "blender_executable_edit": "blender_executable",
            "blender_script_edit": "blender_script_path",
            "rscript_executable_edit": "rscript_executable",
            "r_step03a_script_edit": "r_step03a_script_path",
            "r_step03a2_script_edit": "r_step03a2_script_path",
            "r_step03a_plot_script_edit": "r_step03a_plot_script_path",
            "r_step03a2_plot_script_edit": "r_step03a2_plot_script_path",
            "r_step03b_script_edit": "r_step03b_script_path",
            "r_step03b_plot_script_edit": "r_step03b_plot_script_path",
            "r_step03c_script_edit": "r_step03c_script_path",
            "r_step05a_script_edit": "r_step05a_script_path",
            "r_step05b_script_edit": "r_step05b_script_path",
            "r_step05c_script_edit": "r_step05c_script_path",
            "r_step05a_qc_plot_script_edit": "r_step05a_qc_plot_script_path",
            "r_step05b_qc_plot_script_edit": "r_step05b_qc_plot_script_path",
            "r_step05c_qc_plot_script_edit": "r_step05c_qc_plot_script_path",
            "r_facet_point_plot_script_edit": "r_facet_point_plot_script_path",
        }
        for attr, key in field_map.items():
            if hasattr(self, attr):
                value = getattr(self, attr).text().strip()
                self.settings[key] = helper_path_for_storage(key, value)
        if hasattr(self, "r_github_repo_edit"):
            self.settings["r_github_repo"] = self.r_github_repo_edit.text().strip() or "Pete-s-Lab/CV3D"
        save_app_settings(self.settings)
        if self.config:
            self.config["compute_settings"] = self.settings["compute_settings"]
            self.save_current_files()
        self.refresh_all()

    # ---------- status helpers ----------

    def eye_present(self, eye: str) -> bool:
        return bool(self.config and self.config["eyes"][eye]["present"])

    def set_eye_step_state(self, step: str, eye: str, state: str, messages: Optional[List[str]] = None) -> None:
        s = self.status["workflow_steps"][step][eye]
        before = s["state"]
        s["state"] = state
        s["symbol"] = STATE_SYMBOL.get(state, "?")
        s["last_run"] = now()
        s["needs_rerun"] = state == "needs_rerun"
        s["messages"] = messages or []
        append_log(
            self.analysis_folder, self.config["dataset_identity"]["cv_id"], eye,
            step, "set_step_state", before, state, "success", "; ".join(s["messages"])
        )

    def mark_downstream_needs_rerun(self, step: str, eye: str) -> None:
        for downstream in DOWNSTREAM.get(step, []):
            if self.status["workflow_steps"][downstream][eye]["state"] in ["complete", "complete_with_warning"]:
                self.status["workflow_steps"][downstream][eye]["state"] = "needs_rerun"
                self.status["workflow_steps"][downstream][eye]["symbol"] = "↻"
                self.status["workflow_steps"][downstream][eye]["needs_rerun"] = True
                self.status["workflow_steps"][downstream][eye]["messages"] = [f"Upstream step {step} changed."]
        # Mirroring is a derived output and needs rerun if a source eye changes from step 04 onward.
        mirror = self.status["workflow_steps"].setdefault("05d_mirror_missing_eye", {"label": STEP_LABELS["05d_mirror_missing_eye"], "state": "not_created", "symbol": "○", "messages": []})
        if step in ["04_blender_facet_check_landmarking", "05a_optical_metrics", "05b_global_coordinate_rotation", "05c_corneal_projections"]:
            affected = [
                eye_id for eye_id in EYES
                if self.config and self.config.get("eyes", {}).get(eye_id, {}).get("mirrored_from_eye") == eye
            ]
            single_source_match = mirror.get("source_eye") == eye
            if affected or single_source_match:
                if mirror.get("state") in ["complete", "complete_with_warning", "not_created"]:
                    mirror["state"] = "needs_rerun"
                    mirror["symbol"] = "↻"
                    mirror["needs_rerun"] = True
                    mirror["messages"] = [
                        f"Source eye {eye} changed after mirroring.",
                        *([f"Affected mirrored eye(s): {', '.join(affected)}"] if affected else []),
                    ]

        # Report outdated
        rep = self.status["workflow_steps"]["06_report_export"]
        if rep["html_report"]["state"] == "complete":
            rep["html_report"]["state"] = "needs_rerun"
            rep["html_report"]["symbol"] = "↻"
            rep["html_report"]["needs_rerun"] = True
        if rep["pdf_export"]["state"] == "exported":
            rep["pdf_export"]["state"] = "outdated_export"
            rep["pdf_export"]["symbol"] = "↻"
            rep["pdf_export"]["outdated_export"] = True
        if rep["zip_export"]["state"] == "exported":
            rep["zip_export"]["state"] = "outdated_export"
            rep["zip_export"]["symbol"] = "↻"
            rep["zip_export"]["outdated_export"] = True

    def copy_external_stl(self, eye: str, notes: str) -> None:
        if not self.config or not self.analysis_folder:
            return
        source, _ = QFileDialog.getOpenFileName(self, f"Select external STL for {eye}", str(self.project_folder or Path.home()), "STL files (*.stl);;All files (*)")
        if not source:
            return
        self._copy_external_stl(Path(source), eye, notes)

    def _copy_external_stl(self, source: Path, eye: str, notes: str) -> None:
        cv_id = self.config["dataset_identity"]["cv_id"]
        target_name = eye_rel_path(eye, f"01_{cv_id}_{eye}_external.stl")
        (self.analysis_folder / target_name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, self.analysis_folder / target_name)
        files = self.config["eyes"][eye]["files"]
        files["external_stl_file"] = target_name
        files["external_stl_original_path"] = str(source)
        files["external_stl_notes"] = notes
        files["selected_raw_stl_file"] = target_name
        append_log(self.analysis_folder, cv_id, eye, "01_external_stl", "copy_external_stl", "", "complete", "success", notes)
        self.save_current_files()
        self.refresh_all()

    def create_threshold_plot(self, eye: str) -> None:
        if not self.ensure_eye_and_dataset(eye):
            return
        files = self.config["eyes"][eye]["files"]
        rel_path = files["local_height_threshold_plot"]
        plot_path = self.analysis_folder / rel_path
        if not plot_path.exists():
            QMessageBox.warning(
                self,
                "Missing threshold plot",
                f"The local-height threshold plot is missing for {eye}:\n\n{rel_path}\n\n"
                "Run 03A Local height calculation first. This plot is created by the "
                "local-height calculation step and stored in the inspection folder."
            )
            self.validate_current_workflow_outputs(save_changes=True)
            self.refresh_all()
            return
        self.open_local_path(plot_path, "local-height threshold plot")

    def plot_raw_local_heights_3d(self, eye: str) -> None:
        """Create a 3D PNG preview from the raw 03A local-heights CSV and optionally keep an rgl window open."""
        if not self.ensure_eye_and_dataset(eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = configured_file_path(self.settings.get("r_step03a_plot_script_path", ""))

        if rscript is None:
            QMessageBox.warning(
                self,
                "Rscript executable missing",
                "Set a valid Rscript executable in Settings first.\n\n"
                "This should point to Rscript.exe, e.g.\n"
                "C:\\Program Files\\R\\R-4.x.x\\bin\\Rscript.exe"
            )
            self.nav.setCurrentRow(6)
            return

        if runner is None:
            QMessageBox.warning(
                self,
                "R raw local-height 3D plot runner missing",
                "Set a valid CV3D R raw local-height 3D plot runner .R file in Settings first."
            )
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        raw_state = self.status["workflow_steps"]["03a_local_height_calculation"][eye].get("state")
        input_rel = files["local_heights_file"]
        input_path = self.analysis_folder / input_rel
        if raw_state not in ["complete", "complete_with_warning"] or not input_path.exists():
            QMessageBox.warning(
                self,
                "Raw local heights not ready",
                f"03A must be complete and the raw local-height CSV must exist for {eye}.\n\n"
                f"03A state: {raw_state}\n"
                f"Required file: {input_rel}\n"
                f"Exists: {input_path.exists()}"
            )
            self.validate_current_workflow_outputs(save_changes=True)
            self.refresh_all()
            return

        open_reply = QMessageBox.question(
            self,
            "Open interactive rgl window?",
            "Create the PNG preview only, or also keep an interactive rgl window open for inspection?\n\n"
            "If you choose Yes, the GUI will wait until you close the rgl window.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No
        )
        if open_reply == QMessageBox.StandardButton.Cancel:
            return
        open_rgl_window = (open_reply == QMessageBox.StandardButton.Yes)

        task_rel = eye_json_rel_path(eye, f"03AP_{cv_id}_{eye}_R_task.json")
        status_rel = eye_json_rel_path(eye, f"03AP_{cv_id}_{eye}_R_status.json")
        stdout_rel = eye_log_rel_path(eye, f"03AP_{cv_id}_{eye}_R_stdout.log")
        stderr_rel = eye_log_rel_path(eye, f"03AP_{cv_id}_{eye}_R_stderr.log")
        launch_rel = eye_log_rel_path(eye, f"03AP_{cv_id}_{eye}_R_launch_command.txt")
        plot_rel = eye_inspection_rel_path(eye, f"03_{cv_id}_{eye}_local_heights_raw_3d_plot.png")

        task = {
            "task_type": "raw_local_height_3d_plot",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_local_heights": input_rel,
            "input_local_heights_abs": str(input_path),
            "output_plot_png": plot_rel,
            "output_plot_png_abs": str(self.analysis_folder / plot_rel),
            "status_file": status_rel,
            "status_file_abs": str(self.analysis_folder / status_rel),
            "stdout_file": stdout_rel,
            "stdout_file_abs": str(self.analysis_folder / stdout_rel),
            "stderr_file": stderr_rel,
            "stderr_file_abs": str(self.analysis_folder / stderr_rel),
            "open_rgl_window": open_rgl_window,
            "notes": "Created by CV3D Python controller for raw local-height 3D plotting."
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)

        reply = QMessageBox.question(
            self,
            "Create raw local-height 3D plot",
            "This will create a PNG preview from the raw 03A local-height CSV.\n\n"
            f"CV ID: {cv_id}\n"
            f"Eye: {eye}\n"
            f"Input CSV: {input_rel}\n"
            f"Output PNG: {plot_rel}\n"
            f"Open interactive rgl window: {open_rgl_window}\n\n"
            "The GUI will wait until Rscript finishes.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        stdout_path = self.analysis_folder / stdout_rel
        stderr_path = self.analysis_folder / stderr_rel
        launch_diag_path = self.analysis_folder / launch_rel
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        write_text(
            launch_diag_path,
            "Command:\n" + " ".join(f'"{part}"' for part in cmd) + "\n\n"
            f"Working directory:\n{self.analysis_folder}\n"
        )

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_diag_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            QMessageBox.critical(self, "R raw 3D plot launch failed", str(e))
            self.refresh_all()
            return

        status_path = self.analysis_folder / status_rel
        plot_path = self.analysis_folder / plot_rel
        runner_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                runner_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                runner_status = "unreadable_status_json"
                status_message = str(e)

        self.refresh_all()

        if exit_code == 0 and runner_status == "success" and plot_path.exists():
            # Success is intentionally silent here. The generated PNG path is recorded
            # in the task/status JSON and visible in the console/log panel.
            self.refresh_all()
        else:
            details = [
                f"Rscript exit code: {exit_code}",
                f"Runner status: {runner_status}",
                f"Plot PNG exists: {plot_path.exists()}",
                f"Launch log: {launch_rel}",
                f"stdout log: {stdout_rel}",
                f"stderr log: {stderr_rel}",
            ]
            if status_message:
                details.append(status_message)
            QMessageBox.warning(
                self,
                "Raw 3D plot creation failed",
                "The raw local-height 3D plotting utility did not finish successfully.\n\n"
                + "\n".join(details)
            )


    def plot_local_heights_3d(self, eye: str) -> None:
        """Create a 3D PNG preview from the normalized local-heights CSV and optionally keep an rgl window open."""
        if not self.ensure_eye_and_dataset(eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = configured_file_path(self.settings.get("r_step03a2_plot_script_path", ""))

        if rscript is None:
            QMessageBox.warning(
                self,
                "Rscript executable missing",
                "Set a valid Rscript executable in Settings first.\n\n"
                "This should point to Rscript.exe, e.g.\n"
                "C:\\Program Files\\R\\R-4.x.x\\bin\\Rscript.exe"
            )
            self.nav.setCurrentRow(6)
            return

        if runner is None:
            QMessageBox.warning(
                self,
                "R local-height 3D plot runner missing",
                "Set a valid CV3D R local-height 3D plot runner .R file in Settings first."
            )
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        input_rel = files["local_heights_normalized_file"]
        input_path = self.analysis_folder / input_rel
        if not input_path.exists():
            QMessageBox.warning(
                self,
                "Missing normalized local-height CSV",
                f"The required normalized local-height CSV is missing for {eye}:\n\n{input_rel}\n\n"
                "Run 03A2 Optional local-height normalization first."
            )
            self.validate_current_workflow_outputs(save_changes=True)
            self.refresh_all()
            return

        open_reply = QMessageBox.question(
            self,
            "Open interactive rgl window?",
            "Create the PNG preview only, or also keep an interactive rgl window open for inspection?\n\n"
            "If you choose Yes, the GUI will wait until you close the rgl window.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No
        )
        if open_reply == QMessageBox.StandardButton.Cancel:
            return
        open_rgl_window = (open_reply == QMessageBox.StandardButton.Yes)

        task_rel = eye_json_rel_path(eye, f"03A2P_{cv_id}_{eye}_R_task.json")
        status_rel = eye_json_rel_path(eye, f"03A2P_{cv_id}_{eye}_R_status.json")
        stdout_rel = eye_log_rel_path(eye, f"03A2P_{cv_id}_{eye}_R_stdout.log")
        stderr_rel = eye_log_rel_path(eye, f"03A2P_{cv_id}_{eye}_R_stderr.log")
        launch_rel = eye_log_rel_path(eye, f"03A2P_{cv_id}_{eye}_R_launch_command.txt")
        plot_rel = eye_inspection_rel_path(eye, f"03_{cv_id}_{eye}_local_heights_3d_plot.png")

        task = {
            "task_type": "local_height_3d_plot",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_local_heights_normalized": input_rel,
            "input_local_heights_normalized_abs": str(input_path),
            "output_plot_png": plot_rel,
            "output_plot_png_abs": str(self.analysis_folder / plot_rel),
            "status_file": status_rel,
            "status_file_abs": str(self.analysis_folder / status_rel),
            "stdout_file": stdout_rel,
            "stdout_file_abs": str(self.analysis_folder / stdout_rel),
            "stderr_file": stderr_rel,
            "stderr_file_abs": str(self.analysis_folder / stderr_rel),
            "open_rgl_window": open_rgl_window,
            "notes": "Created by CV3D Python controller for normalized local-height 3D plotting."
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)

        reply = QMessageBox.question(
            self,
            "Create local-height 3D plot",
            "This will create a PNG preview from the normalized local-height CSV.\n\n"
            f"CV ID: {cv_id}\n"
            f"Eye: {eye}\n"
            f"Input CSV: {input_rel}\n"
            f"Output PNG: {plot_rel}\n"
            f"Open interactive rgl window: {open_rgl_window}\n\n"
            "The GUI will wait until Rscript finishes.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        stdout_path = self.analysis_folder / stdout_rel
        stderr_path = self.analysis_folder / stderr_rel
        launch_diag_path = self.analysis_folder / launch_rel
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        write_text(
            launch_diag_path,
            "Command:\n" + " ".join(f'"{part}"' for part in cmd) + "\n\n"
            f"Working directory:\n{self.analysis_folder}\n"
        )

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_diag_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            QMessageBox.critical(self, "R 3D plot launch failed", str(e))
            self.refresh_all()
            return

        status_path = self.analysis_folder / status_rel
        plot_path = self.analysis_folder / plot_rel
        runner_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                runner_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                runner_status = "unreadable_status_json"
                status_message = str(e)

        self.refresh_all()

        if exit_code == 0 and runner_status == "success" and plot_path.exists():
            # Success is intentionally silent here. The generated PNG path is recorded
            # in the task/status JSON and visible in the console/log panel.
            self.refresh_all()
        else:
            details = [
                f"Rscript exit code: {exit_code}",
                f"Runner status: {runner_status}",
                f"Plot PNG exists: {plot_path.exists()}",
                f"Launch log: {launch_rel}",
                f"stdout log: {stdout_rel}",
                f"stderr log: {stderr_rel}",
            ]
            if status_message:
                details.append(status_message)
            QMessageBox.warning(
                self,
                "3D plot creation failed",
                "The local-height 3D plotting utility did not finish successfully.\n\n"
                + "\n".join(details)
            )

    def local_height_background_for_eye(self, eye: str) -> Optional[Dict[str, Any]]:
        """Return the local-height table used as the background for inspection plots."""
        files = self.config["eyes"][eye]["files"]

        # Prefer the exact local-height table/column used in 03B thresholding.
        task03b_path = self.analysis_folder / files["r_step03b_task_file"]
        if task03b_path.exists():
            try:
                task03b = read_json(task03b_path)
                rel = task03b.get("input_local_heights")
                col = task03b.get("height_column")
                if rel and col and (self.analysis_folder / rel).exists():
                    return {
                        "rel": rel,
                        "abs": self.analysis_folder / rel,
                        "height_column": col,
                        "source": "03B input table",
                    }
            except Exception:
                pass

        norm_rel = files.get("local_heights_normalized_file")
        norm_path = self.analysis_folder / norm_rel
        norm_state = self.status["workflow_steps"]["03a2_local_height_normalization"][eye].get("state")
        if norm_rel and norm_state in ["complete", "complete_with_warning"] and norm_path.exists():
            return {
                "rel": norm_rel,
                "abs": norm_path,
                "height_column": "local_height_norm_contrast",
                "source": "normalized local heights",
            }

        raw_rel = files.get("local_heights_file")
        raw_path = self.analysis_folder / raw_rel
        raw_state = self.status["workflow_steps"]["03a_local_height_calculation"][eye].get("state")
        if raw_rel and raw_state in ["complete", "complete_with_warning"] and raw_path.exists():
            return {
                "rel": raw_rel,
                "abs": raw_path,
                "height_column": "local_height_contrast",
                "source": "raw local heights",
            }

        return None

    def plot_facet_points_on_local_heights(self, eye: str, point_kind: str, automatic: bool = False) -> None:
        """Create a background PNG with facet candidates/positions overlaid on the local-height eye."""
        if not self.ensure_eye_and_dataset(eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = configured_file_path(self.settings.get("r_facet_point_plot_script_path", ""))

        if rscript is None:
            QMessageBox.warning(
                self,
                "Rscript executable missing",
                "Set a valid Rscript executable in Settings first.\n\n"
                "This should point to Rscript.exe, e.g.\n"
                "C:\\Program Files\\R\\R-4.x.x\\bin\\Rscript.exe"
            )
            self.nav.setCurrentRow(6)
            return

        if runner is None:
            QMessageBox.warning(
                self,
                "R facet point overlay plot runner missing",
                "Set a valid CV3D R facet point overlay plot runner .R file in Settings first."
            )
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]

        if point_kind == "facet_candidates":
            point_rel = files.get("facet_candidates_file")
            plot_rel = files.get("facet_candidates_plot_file") or eye_inspection_rel_path(eye, f"03C_{cv_id}_{eye}_facet_candidates_on_local_height.png")
            required_step = "03c_facet_candidate_condensation"
            label = "facet candidates"
            task_prefix = "03CP"
            overlay_color = "red"
        elif point_kind == "facet_positions":
            self.make_blender_facet_names_authoritative(eye)
            point_rel = files.get("facet_positions_file")
            plot_rel = files.get("facet_positions_plot_file") or eye_inspection_rel_path(eye, f"04_{cv_id}_{eye}_facet_positions_on_local_height.png")
            required_step = "04_blender_facet_check_landmarking"
            label = "facet positions"
            task_prefix = "04P"
            overlay_color = "red"
        else:
            QMessageBox.warning(self, "Unknown plot type", f"Unknown point plot kind: {point_kind}")
            return

        if not point_rel:
            QMessageBox.warning(self, "Missing point file configuration", f"No configured CSV path found for {label}.")
            return

        if not plot_rel:
            plot_rel = eye_inspection_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_facet_points_on_local_height.png")

        state = self.status["workflow_steps"][required_step][eye].get("state")
        point_path = self.analysis_folder / str(point_rel)
        plot_path = self.analysis_folder / str(plot_rel)
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        if state not in ["complete", "complete_with_warning"] or not point_path.exists():
            QMessageBox.warning(
                self,
                f"{label.capitalize()} not ready",
                f"This plot requires {STEP_LABELS[required_step]} to be complete and its CSV to exist.\n\n"
                f"State: {state}\n"
                f"Required file: {point_rel}\n"
                f"Exists: {point_path.exists()}"
            )
            self.validate_current_workflow_outputs(save_changes=True)
            self.refresh_all()
            return

        background = self.local_height_background_for_eye(eye)
        if background is None:
            QMessageBox.warning(
                self,
                "Local-height background missing",
                "Could not find a raw or normalized local-height table to use as background."
            )
            return

        if automatic:
            open_rgl_window = True
        else:
            open_reply = QMessageBox.question(
                self,
                "Open interactive rgl window?",
                "Create the PNG overlay only, or also keep an interactive rgl 3D window open for inspection?\n\n"
                "The PNG is saved in the background either way. If you choose Yes, the GUI will wait until you close the rgl window.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No
            )
            if open_reply == QMessageBox.StandardButton.Cancel:
                return
            open_rgl_window = (open_reply == QMessageBox.StandardButton.Yes)

        task_rel = eye_json_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_task.json")
        status_rel = eye_json_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_status.json")
        stdout_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_stdout.log")
        stderr_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_stderr.log")
        launch_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_launch_command.txt")

        task = {
            "task_type": "facet_point_overlay_plot",
            "point_kind": point_kind,
            "point_label": label,
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_local_heights": background["rel"],
            "input_local_heights_abs": str(background["abs"]),
            "height_column": background["height_column"],
            "background_source": background["source"],
            "input_points": str(point_rel),
            "input_points_abs": str(point_path),
            "output_plot_png": str(plot_rel),
            "output_plot_png_abs": str(plot_path),
            "output_plot_dir_abs": str(plot_path.parent),
            "overlay_color": overlay_color,
            "open_rgl_window": open_rgl_window,
            "status_file": status_rel,
            "status_file_abs": str(self.analysis_folder / status_rel),
            "stdout_file": stdout_rel,
            "stdout_file_abs": str(self.analysis_folder / stdout_rel),
            "stderr_file": stderr_rel,
            "stderr_file_abs": str(self.analysis_folder / stderr_rel),
            "notes": "Created by CV3D Python controller for background PNG facet-point overlay plotting."
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)

        stdout_path = self.analysis_folder / stdout_rel
        stderr_path = self.analysis_folder / stderr_rel
        launch_diag_path = self.analysis_folder / launch_rel
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        write_text(
            launch_diag_path,
            "Command:\n" + " ".join(f'"{part}"' for part in cmd) + "\n\n"
            f"Working directory:\n{self.analysis_folder}\n"
        )

        if automatic:
            try:
                out = stdout_path.open("w", encoding="utf-8", errors="replace")
                err = stderr_path.open("w", encoding="utf-8", errors="replace")
                try:
                    process = subprocess.Popen(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
                finally:
                    out.close()
                    err.close()
                if not hasattr(self, "_background_plot_processes"):
                    self._background_plot_processes = []
                self._background_plot_processes = [p for p in self._background_plot_processes if p.poll() is None]
                self._background_plot_processes.append(process)
                with launch_diag_path.open("a", encoding="utf-8") as f:
                    f.write(f"\nBackground process ID:\n{process.pid}\n")
            except Exception as e:
                QMessageBox.warning(self, "Facet point plot launch failed", str(e))
            return

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_diag_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            QMessageBox.critical(self, "Facet point plot launch failed", str(e))
            self.refresh_all()
            return

        status_path = self.analysis_folder / status_rel
        plot_path = self.analysis_folder / plot_rel
        runner_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                runner_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                runner_status = "unreadable_status_json"
                status_message = str(e)

        self.refresh_all()

        if not (exit_code == 0 and runner_status == "success" and plot_path.exists()):
            details = [
                f"Rscript exit code: {exit_code}",
                f"Runner status: {runner_status}",
                f"Plot PNG exists: {plot_path.exists()}",
                f"Launch log: {launch_rel}",
                f"stdout log: {stdout_rel}",
                f"stderr log: {stderr_rel}",
            ]
            if status_message:
                details.append(status_message)
            QMessageBox.warning(
                self,
                "Facet point overlay plot failed",
                "The facet point overlay plot was not created successfully.\n\n" + "\n".join(details)
            )

    def get_05a_metric_plot_choices(self, optic_path: Path) -> List[tuple[str, str]]:
        preferred_labels = {
            "facet_size_smoothed": "Facet size",
            "interfacet_angle_deg": "IF angle (deg)",
            "interfacet_angle_rad": "IF angle (rad)",
            "eye_parameter": "Eye parameter",
            "sampling_frequency_rad": "Sampling frequency (rad^-1)",
            "acuity_cpd": "Acuity (cycles/degree)",
            "number_of_neighbours": "Number of neighbours",
        }
        excluded = {
            "cv_id", "eye", "facet_id", "internal_ID", "CV", "ID", "type", "neighbours",
            "x", "y", "z", "norm.x", "norm.y", "norm.z",
            # Normal-estimator provenance/QC fields are retained in the CSV/export,
            # but are not useful as generic per-facet biological metric plots.
            "normal_envelope_factor", "normal_support_scale_um",
            "normal_weight_cutoff_um", "normal_support_face_count", "n_neighbors_used", "n_neighbours_used",
            "facet_size"
        }
        rows: List[Dict[str, str]] = []
        fieldnames: List[str] = []
        try:
            with optic_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = [str(col).strip() for col in (reader.fieldnames or []) if str(col).strip()]
                for idx, row in enumerate(reader):
                    rows.append({str(k): "" if v is None else str(v) for k, v in row.items()})
                    if idx >= 49:
                        break
        except Exception:
            return []

        def looks_numeric(col: str) -> bool:
            values = []
            for row in rows:
                val = (row.get(col) or "").strip()
                if val and val.lower() not in {"na", "nan", "null"}:
                    values.append(val)
            if not values:
                return col in preferred_labels
            for val in values[:10]:
                try:
                    float(val)
                    return True
                except Exception:
                    continue
            return False

        preferred_order = [
            "facet_size_smoothed", "interfacet_angle_deg", "eye_parameter", "acuity_cpd", "sampling_frequency_rad", "interfacet_angle_rad", "number_of_neighbours"
        ]
        ordered: List[str] = []
        for col in preferred_order:
            if col in fieldnames and col not in excluded and looks_numeric(col):
                ordered.append(col)
        for col in fieldnames:
            if col in excluded or col in ordered:
                continue
            if looks_numeric(col):
                ordered.append(col)
        return [(col, preferred_labels.get(col, col)) for col in ordered]

    def facet_size_estimate_for_plot(self) -> Optional[float]:
        """Return a valid dataset-level facet-size estimate for plot fallback, if available."""
        try:
            value = float(self.read_facet_size_estimate_for_task())
            if math.isfinite(value) and value > 0:
                return value
        except Exception:
            pass
        try:
            value = float(self.config.get("parameters", {}).get("dataset_defaults", {}).get("facet_size_estimate"))
            if math.isfinite(value) and value > 0:
                return value
        except Exception:
            pass
        return None

    def default_facet_sphere_scale(self) -> float:
        """Default QC sphere diameter is twice the facet diameter."""
        return 2.0

    def remember_plot_options(self, values: Dict[str, Any]) -> None:
        """Persist non-scientific plot display settings without changing analysis defaults."""
        defaults = self.config.setdefault("parameters", {}).setdefault("dataset_defaults", {})
        if values.get("open_rgl_window"):
            try:
                scale = float(values.get("facet_sphere_scale", 2.0))
                if math.isfinite(scale) and scale >= 0:
                    defaults["facet_sphere_scale_last_used"] = scale
            except Exception:
                pass
        if values.get("normal_length_facet_size_factor") is not None:
            try:
                value = float(values.get("normal_length_facet_size_factor"))
                if math.isfinite(value) and value >= 0:
                    defaults["facet_normal_length_factor"] = value
            except Exception:
                pass
        self.save_current_files()

    def plot_05a_outputs(self, eye: str, plot_kind: str) -> None:
        if not self.ensure_eye_and_dataset(eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = self.resolve_r_analysis_runner("r_step05a_qc_plot_script_path")

        if rscript is None:
            QMessageBox.warning(self, "Rscript executable missing", "Set a valid Rscript executable in Settings first.")
            self.nav.setCurrentRow(7)
            return
        if runner is None:
            QMessageBox.warning(self, "05A QC plot runner missing", "Could not find the bundled or configured 05A QC plot runner.")
            self.nav.setCurrentRow(7)
            return
        if not self.ensure_r_package_installed():
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        optic_rel = files.get("optic_parameters_file")
        normals_rel = files.get("facet_normals_file")
        optic_path = self.analysis_folder / str(optic_rel)
        normals_path = self.analysis_folder / str(normals_rel)

        if not optic_path.exists():
            QMessageBox.warning(self, "05A outputs missing", f"Expected optic-parameter file not found:\n\n{optic_rel}")
            self.refresh_all()
            return
        metric_choices = None
        if plot_kind == "labelled_metric":
            metric_choices = self.get_05a_metric_plot_choices(optic_path)
            if normals_path.exists():
                metric_choices.append(("__facet_normals__", "Normals"))
            if not metric_choices:
                QMessageBox.warning(self, "No plottable 05A values found", "No numeric 05A metric columns or facet normals were found in the 05A outputs.")
                return

        options = PlotOptionsDialog(
            f"{eye} plot options",
            self,
            metric_choices=metric_choices,
            open_rgl_default=True,
            facet_sphere_scale_default=self.default_facet_sphere_scale(),
            show_facet_labels_option=(plot_kind == "labelled_metric"),
            show_facet_labels_default=False,
        )
        if options.exec() != QDialog.Accepted:
            return
        self.remember_plot_options(options.values)

        selected_metric_col = str(options.values.get("selected_metric_col", ""))
        selected_metric_label = str(options.values.get("selected_metric_label", ""))
        open_rgl_window = bool(options.values.get("open_rgl_window", False))
        facet_sphere_scale = float(options.values.get("facet_sphere_scale", 0.0))
        facet_size_estimate = self.facet_size_estimate_for_plot()
        show_facet_labels = bool(options.values.get("show_facet_labels", False))
        normal_length_facet_size_factor = None
        show_normals = True

        if plot_kind == "labelled_metric" and selected_metric_col == "__facet_normals__":
            if not normals_path.exists():
                QMessageBox.warning(self, "05A normals missing", f"Expected facet-normal file not found:\n\n{normals_rel}")
                self.refresh_all()
                return
            try:
                default_factor = float(self.config.get("parameters", {}).get("dataset_defaults", {}).get("facet_normal_length_factor", 5.0))
            except Exception:
                default_factor = 5.0
            normal_options = NormalPlotOptionsDialog(
                f"{eye} normal options",
                self,
                normal_length_default=default_factor,
                show_normals_default=True,
            )
            if normal_options.exec() != QDialog.Accepted:
                return
            self.remember_plot_options(normal_options.values)
            normal_length_facet_size_factor = normal_options.values.get("normal_length_facet_size_factor")
            show_normals = bool(normal_options.values.get("show_normals", True))
            plot_kind = "normals"
            selected_metric_col = ""
            selected_metric_label = "Normals"

        if plot_kind == "optics":
            task_prefix = "05AP"
            label = "05A optic-parameter plot"
            output_png_rel = eye_inspection_rel_path(eye, f"05A_{cv_id}_{eye}_optic_parameters.png")
        elif plot_kind == "normals":
            task_prefix = "05AN"
            label = "05A facet-normal plot"
            output_png_rel = eye_inspection_rel_path(eye, f"05A_{cv_id}_{eye}_facet_normals_direction_colour.png")
        elif plot_kind == "labelled_metric":
            task_prefix = "05AL"
            label = f"05A labelled metric plot ({selected_metric_label})"
            metric_token = safe_filename_token(selected_metric_col)
            label_suffix = "_facet_labels" if show_facet_labels else ""
            output_png_rel = eye_inspection_rel_path(eye, f"05A_{cv_id}_{eye}_metric_{metric_token}{label_suffix}.png")
        else:
            QMessageBox.warning(self, "Unknown plot type", f"Unknown 05A plot kind: {plot_kind}")
            return

        task_rel = eye_json_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_task.json")
        status_rel = eye_json_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_status.json")
        stdout_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_stdout.log")
        stderr_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_stderr.log")
        launch_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{eye}_R_launch_command.txt")

        task = {
            "task_type": "05A_qc_plot",
            "task_prefix": task_prefix,
            "plot_kind": plot_kind,
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_optic_parameters": str(optic_rel),
            "input_optic_parameters_abs": str(optic_path),
            "input_facet_normals": str(normals_rel),
            "input_facet_normals_abs": str(normals_path),
            "output_plot_png": str(output_png_rel),
            "output_plot_png_abs": str(self.analysis_folder / output_png_rel),
            "open_rgl_window": open_rgl_window,
            "facet_sphere_scale": facet_sphere_scale,
            "facet_size_estimate": facet_size_estimate,
            "selected_metric_col": selected_metric_col,
            "selected_metric_label": selected_metric_label,
            "normal_length_facet_size_factor": normal_length_facet_size_factor,
            "show_normals": show_normals,
            "show_facet_labels": show_facet_labels,
            "parameters": {"normal_length_facet_size_factor": normal_length_facet_size_factor} if normal_length_facet_size_factor is not None else {},
            "status_file": status_rel,
            "status_file_abs": str(self.analysis_folder / status_rel),
            "stdout_file": stdout_rel,
            "stdout_file_abs": str(self.analysis_folder / stdout_rel),
            "stderr_file": stderr_rel,
            "stderr_file_abs": str(self.analysis_folder / stderr_rel),
            "notes": "Created by CV3D Python controller for 05A inspection plotting."
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)

        stdout_path = self.analysis_folder / stdout_rel
        stderr_path = self.analysis_folder / stderr_rel
        launch_path = self.analysis_folder / launch_rel
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        launch_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        write_text(launch_path, "Command:\n" + " ".join(f'\"{part}\"' for part in cmd) + "\n\n" + f"Working directory:\n{self.analysis_folder}\n")

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            QMessageBox.critical(self, "05A plot launch failed", str(e))
            self.refresh_all()
            return

        status_path = self.analysis_folder / status_rel
        plot_path = self.analysis_folder / output_png_rel
        runner_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                runner_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                runner_status = "unreadable_status_json"
                status_message = str(e)

        self.refresh_all()

        if not (exit_code == 0 and runner_status == "success" and plot_path.exists()):
            details = [
                f"Rscript exit code: {exit_code}",
                f"Runner status: {runner_status}",
                f"Plot PNG exists: {plot_path.exists()}",
                f"Launch log: {launch_rel}",
                f"stdout log: {stdout_rel}",
                f"stderr log: {stderr_rel}",
            ]
            if status_message:
                details.append(status_message)
            QMessageBox.warning(self, f"{label} failed", f"The {label} was not created successfully.\n\n" + "\n".join(details))

    def preferred_eye_for_combined_qc(self) -> str:
        if not self.config:
            return "eye1"
        for candidate in ["eye1", "eye2"]:
            info = self.config.get("eyes", {}).get(candidate, {})
            if info.get("present", False):
                return candidate
        return "eye1"

    def gather_available_primary_eyes_for_combined_qc(self, preferred_eye: str) -> list:
        eyes = []
        for candidate in ["eye1", "eye2"]:
            info = (self.config or {}).get("eyes", {}).get(candidate, {}) if self.config else {}
            if info.get("present", False):
                eyes.append(candidate)
        if preferred_eye in eyes:
            eyes = [preferred_eye] + [e for e in eyes if e != preferred_eye]
        elif preferred_eye:
            eyes = [preferred_eye] + eyes
        seen = set()
        ordered = []
        for e in eyes:
            if e not in seen:
                seen.add(e)
                ordered.append(e)
        return ordered

    def plot_05b_qc_outputs(self, eye: str, combined: bool = False) -> None:
        if not self.ensure_eye_and_dataset(eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = self.resolve_r_analysis_runner("r_step05b_qc_plot_script_path")

        if rscript is None:
            QMessageBox.warning(self, "Rscript executable missing", "Set a valid Rscript executable in Settings first.")
            self.nav.setCurrentRow(7)
            return
        if runner is None:
            QMessageBox.warning(self, "05B QC plot runner missing", "Could not find the bundled or configured 05B QC plot runner.")
            self.nav.setCurrentRow(7)
            return
        if not self.ensure_r_package_installed():
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        eyes_to_plot = []
        missing_details = []
        landmarks_rel = self.config.get("specimen_files", {}).get("head_landmarks_file", f"05_{cv_id}_landmarks.csv")
        landmarks_path = self.analysis_folder / landmarks_rel
        if not landmarks_path.exists():
            QMessageBox.warning(self, "Head landmarks missing", f"Expected specimen-level head landmarks not found:\n\n{landmarks_rel}")
            self.refresh_all()
            return

        candidate_eyes = self.gather_available_primary_eyes_for_combined_qc(eye) if combined else [eye]
        for candidate in candidate_eyes:
            files = self.config["eyes"].get(candidate, {}).get("files", {})
            global_rel = files.get("global_coordinates_file")
            referenced_rel = files.get("landmark_referenced_coordinates_file")
            aligned_rel = files.get("global_aligned_pointcloud_file")
            global_path = self.analysis_folder / str(global_rel)
            referenced_path = self.analysis_folder / str(referenced_rel)
            aligned_path = self.analysis_folder / str(aligned_rel)
            if global_path.exists() and aligned_path.exists():
                eyes_to_plot.append({
                    "eye": candidate,
                    "input_global_coordinates": str(global_rel),
                    "input_global_coordinates_abs": str(global_path),
                    "input_landmark_referenced_coordinates": str(referenced_rel),
                    "input_landmark_referenced_coordinates_abs": str(referenced_path),
                    "input_global_aligned_pointcloud": str(aligned_rel),
                    "input_global_aligned_pointcloud_abs": str(aligned_path),
                })
            else:
                missing = []
                if not global_path.exists():
                    missing.append(str(global_rel))
                if not aligned_path.exists():
                    missing.append(str(aligned_rel))
                missing_details.append(f"{candidate}: missing " + ", ".join(missing))

        if len(eyes_to_plot) == 0:
            context = "eye1 or eye2" if combined else eye
            QMessageBox.warning(self, "05B outputs missing", f"Could not find usable 05B outputs for {context}.\n\n" + "\n".join(missing_details))
            self.refresh_all()
            return

        options = PlotOptionsDialog(
            f"{eye} plot options",
            self,
            open_rgl_default=True,
            facet_sphere_scale_default=self.default_facet_sphere_scale(),
        )
        if options.exec() != QDialog.Accepted:
            return
        self.remember_plot_options(options.values)
        open_rgl_window = bool(options.values.get("open_rgl_window", False))
        facet_sphere_scale = float(options.values.get("facet_sphere_scale", 0.0))
        facet_size_estimate = self.facet_size_estimate_for_plot()

        task_prefix = "05BP"
        label = "05B global-alignment QC plot"
        output_eye_tag = "both_eyes" if combined and len(eyes_to_plot) > 1 else eye
        output_png_rel = eye_inspection_rel_path(eye, f"05B_{cv_id}_{output_eye_tag}_global_alignment_qc.png")
        output_reference_png_rel = eye_inspection_rel_path(eye, f"05B_{cv_id}_{output_eye_tag}_landmark_reference_qc.png")

        task_rel = eye_json_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_task.json")
        status_rel = eye_json_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_status.json")
        stdout_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_stdout.log")
        stderr_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_stderr.log")
        launch_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_launch_command.txt")

        task = {
            "task_type": "05B_qc_plot",
            "task_prefix": task_prefix,
            "plot_kind": "global_alignment_qc",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_eyes": eyes_to_plot,
            "input_landmarks": str(landmarks_rel),
            "input_landmarks_abs": str(landmarks_path),
            "output_plot_png": str(output_png_rel),
            "output_plot_png_abs": str(self.analysis_folder / output_png_rel),
            "output_reference_plot_png": str(output_reference_png_rel),
            "output_reference_plot_png_abs": str(self.analysis_folder / output_reference_png_rel),
            "open_rgl_window": open_rgl_window,
            "facet_sphere_scale": facet_sphere_scale,
            "facet_size_estimate": facet_size_estimate,
            "status_file": status_rel,
            "status_file_abs": str(self.analysis_folder / status_rel),
            "stdout_file": stdout_rel,
            "stdout_file_abs": str(self.analysis_folder / stdout_rel),
            "stderr_file": stderr_rel,
            "stderr_file_abs": str(self.analysis_folder / stderr_rel),
            "notes": "Created by CV3D Python controller for 05B global-alignment QC plotting.",
        }
        if len(eyes_to_plot) == 1:
            task.update(eyes_to_plot[0])

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)

        stdout_path = self.analysis_folder / stdout_rel
        stderr_path = self.analysis_folder / stderr_rel
        launch_path = self.analysis_folder / launch_rel
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        launch_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        write_text(launch_path, "Command:\n" + " ".join(f'\"{part}\"' for part in cmd) + "\n\n" + f"Working directory:\n{self.analysis_folder}\n")

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            QMessageBox.critical(self, "05B QC plot launch failed", str(e))
            self.refresh_all()
            return

        status_path = self.analysis_folder / status_rel
        plot_path = self.analysis_folder / output_png_rel
        runner_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                runner_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                runner_status = "unreadable_status_json"
                status_message = str(e)

        self.refresh_all()

        if not (exit_code == 0 and runner_status == "success" and plot_path.exists()):
            details = [
                f"Rscript exit code: {exit_code}",
                f"Runner status: {runner_status}",
                f"Plot PNG exists: {plot_path.exists()}",
                f"Launch log: {launch_rel}",
                f"stdout log: {stdout_rel}",
                f"stderr log: {stderr_rel}",
            ]
            if status_message:
                details.append(status_message)
            QMessageBox.warning(self, f"{label} failed", f"The {label} was not created successfully.\n\n" + "\n".join(details))

    def plot_05c_qc_outputs(self, eye: str, combined: bool = False) -> None:
        if not self.ensure_eye_and_dataset(eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = self.resolve_r_analysis_runner("r_step05c_qc_plot_script_path")

        if rscript is None:
            QMessageBox.warning(self, "Rscript executable missing", "Set a valid Rscript executable in Settings first.")
            self.nav.setCurrentRow(7)
            return
        if runner is None:
            QMessageBox.warning(self, "05C QC plot runner missing", "Could not find the bundled or configured 05C QC plot runner.")
            self.nav.setCurrentRow(7)
            return
        if not self.ensure_r_package_installed():
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        eyes_to_plot = []
        missing_details = []
        candidate_eyes = self.gather_available_primary_eyes_for_combined_qc(eye) if combined else [eye]
        for candidate in candidate_eyes:
            files = self.config["eyes"].get(candidate, {}).get("files", {})
            global_rel = files.get("global_coordinates_file")
            projection_rel = files.get("corneal_projections_file")
            global_path = self.analysis_folder / str(global_rel)
            projection_path = self.analysis_folder / str(projection_rel)
            if global_path.exists() and projection_path.exists():
                eyes_to_plot.append({
                    "eye": candidate,
                    "input_global_coordinates": str(global_rel),
                    "input_global_coordinates_abs": str(global_path),
                    "input_corneal_projections": str(projection_rel),
                    "input_corneal_projections_abs": str(projection_path),
                })
            else:
                missing = []
                if not global_path.exists():
                    missing.append(str(global_rel))
                if not projection_path.exists():
                    missing.append(str(projection_rel))
                missing_details.append(f"{candidate}: missing " + ", ".join(missing))

        if len(eyes_to_plot) == 0:
            context = "eye1 or eye2" if combined else eye
            QMessageBox.warning(self, "05C outputs missing", f"Could not find usable 05B/05C outputs for {context}.\n\n" + "\n".join(missing_details))
            self.refresh_all()
            return

        options = PlotOptionsDialog(
            f"{eye} plot options",
            self,
            open_rgl_default=True,
            facet_sphere_scale_default=self.default_facet_sphere_scale(),
        )
        if options.exec() != QDialog.Accepted:
            return
        self.remember_plot_options(options.values)
        open_rgl_window = bool(options.values.get("open_rgl_window", False))
        facet_sphere_scale = float(options.values.get("facet_sphere_scale", 0.0))
        facet_size_estimate = self.facet_size_estimate_for_plot()

        task_prefix = "05CP"
        label = "05C corneal-projection QC plots"
        output_eye_tag = "both_eyes" if combined and len(eyes_to_plot) > 1 else eye
        output_pngs = {
            axis: str(self.analysis_folder / eye_inspection_rel_path(eye, f"05C_{cv_id}_{output_eye_tag}_corneal_projection_{axis}.png"))
            for axis in ["front", "back", "left", "right", "top", "bottom"]
        }
        output_pngs["view_angles"] = str(self.analysis_folder / eye_inspection_rel_path(eye, f"05C_{cv_id}_{output_eye_tag}_corneal_projection_view_angles.png"))
        output_pngs["rgl_3d"] = str(self.analysis_folder / eye_inspection_rel_path(eye, f"05C_{cv_id}_{output_eye_tag}_corneal_projection_3d_qc.png"))

        task_rel = eye_json_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_task.json")
        status_rel = eye_json_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_status.json")
        stdout_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_stdout.log")
        stderr_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_stderr.log")
        launch_rel = eye_log_rel_path(eye, f"{task_prefix}_{cv_id}_{output_eye_tag}_R_launch_command.txt")

        task = {
            "task_type": "05C_qc_plot",
            "task_prefix": task_prefix,
            "plot_kind": "corneal_projection_qc",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_eyes": eyes_to_plot,
            "output_plot_pngs_abs": output_pngs,
            "output_plot_png": eye_inspection_rel_path(eye, f"05C_{cv_id}_{output_eye_tag}_corneal_projection_3d_qc.png"),
            "output_plot_png_abs": output_pngs["rgl_3d"],
            "open_rgl_window": open_rgl_window,
            "facet_sphere_scale": facet_sphere_scale,
            "facet_size_estimate": facet_size_estimate,
            "make_rgl_snapshot": False,
            "status_file": status_rel,
            "status_file_abs": str(self.analysis_folder / status_rel),
            "stdout_file": stdout_rel,
            "stdout_file_abs": str(self.analysis_folder / stdout_rel),
            "stderr_file": stderr_rel,
            "stderr_file_abs": str(self.analysis_folder / stderr_rel),
            "notes": "Created by CV3D Python controller for 05C corneal-projection QC plotting.",
        }
        if len(eyes_to_plot) == 1:
            task.update(eyes_to_plot[0])

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)

        stdout_path = self.analysis_folder / stdout_rel
        stderr_path = self.analysis_folder / stderr_rel
        launch_path = self.analysis_folder / launch_rel
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        launch_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        write_text(launch_path, "Command:\n" + " ".join(f'\"{part}\"' for part in cmd) + "\n\n" + f"Working directory:\n{self.analysis_folder}\n")

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            QMessageBox.critical(self, "05C QC plot launch failed", str(e))
            self.refresh_all()
            return

        status_path = self.analysis_folder / status_rel
        primary_plot_path = Path(output_pngs["view_angles"])
        rgl_snapshot_path = Path(output_pngs["rgl_3d"])
        runner_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                runner_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                runner_status = "unreadable_status_json"
                status_message = str(e)

        self.refresh_all()

        if not (exit_code == 0 and runner_status == "success" and primary_plot_path.exists()):
            details = [
                f"Rscript exit code: {exit_code}",
                f"Runner status: {runner_status}",
                f"Elevation/azimuth PNG exists: {primary_plot_path.exists()}",
                f"3D rgl snapshot PNG exists (optional): {rgl_snapshot_path.exists()}",
                f"Launch log: {launch_rel}",
                f"stdout log: {stdout_rel}",
                f"stderr log: {stderr_rel}",
            ]
            if status_message:
                details.append(status_message)
            QMessageBox.warning(self, f"{label} failed", f"The {label} were not created successfully.\n\n" + "\n".join(details))

    def browse_r_step05a_script(self) -> None:
        self.browse_helper_script_setting("r_step05a_script_path", "r_step05a_script_edit", "Select CV3D R Step 05A optic metrics runner", "R scripts (*.R *.r);;All files (*)")

    def browse_r_step05b_script(self) -> None:
        self.browse_helper_script_setting("r_step05b_script_path", "r_step05b_script_edit", "Select CV3D R Step 05B global alignment runner", "R scripts (*.R *.r);;All files (*)")

    def browse_r_step05c_script(self) -> None:
        self.browse_helper_script_setting("r_step05c_script_path", "r_step05c_script_edit", "Select CV3D R Step 05C corneal projection runner", "R scripts (*.R *.r);;All files (*)")

    def browse_r_step05a_qc_plot_script(self) -> None:
        self.browse_helper_script_setting("r_step05a_qc_plot_script_path", "r_step05a_qc_plot_script_edit", "Select CV3D R 05A QC plot runner", "R scripts (*.R *.r);;All files (*)")

    def browse_r_step05b_qc_plot_script(self) -> None:
        self.browse_helper_script_setting("r_step05b_qc_plot_script_path", "r_step05b_qc_plot_script_edit", "Select CV3D R 05B QC plot runner", "R scripts (*.R *.r);;All files (*)")

    def browse_r_step05c_qc_plot_script(self) -> None:
        self.browse_helper_script_setting("r_step05c_qc_plot_script_path", "r_step05c_qc_plot_script_edit", "Select CV3D R 05C QC plot runner", "R scripts (*.R *.r);;All files (*)")

    def browse_r_step03c_script(self) -> None:
        start = helper_file_dialog_start(self.settings, "r_step03c_script_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D R Step 03C candidate condensation runner",
            start,
            "R scripts (*.R *.r);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("r_step03c_script_path", file_path)
            self.r_step03c_script_edit.setText(stored)
            self.settings["r_step03c_script_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def browse_r_facet_point_plot_script(self) -> None:
        start = helper_file_dialog_start(self.settings, "r_facet_point_plot_script_path")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV3D R facet point overlay plot runner",
            start,
            "R scripts (*.R *.r);;All files (*)"
        )
        if file_path:
            stored = helper_path_for_storage("r_facet_point_plot_script_path", file_path)
            self.r_facet_point_plot_script_edit.setText(stored)
            self.settings["r_facet_point_plot_script_path"] = stored
            self.settings["use_bundled_helpers"] = False
            save_app_settings(self.settings)
            self.refresh_settings_page()

    def create_r_step03c_task(self, eye: str, params: Dict[str, Any]) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]

        task_rel = files["r_step03c_task_file"]
        status_rel = files["r_step03c_status_file"]
        stdout_rel = eye_log_rel_path(eye, f"03C_{cv_id}_{eye}_R_stdout.log")
        stderr_rel = eye_log_rel_path(eye, f"03C_{cv_id}_{eye}_R_stderr.log")
        membership_rel = eye_inspection_rel_path(eye, f"03C_{cv_id}_{eye}_facet_candidate_condensation_membership.csv")

        task = {
            "task_type": "facet_candidate_condensation",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_local_height_thresholded": files["local_height_thresholded_file"],
            "input_local_height_thresholded_abs": str(self.analysis_folder / files["local_height_thresholded_file"]),
            "output_facet_candidates": files["facet_candidates_file"],
            "output_facet_candidates_abs": str(self.analysis_folder / files["facet_candidates_file"]),
            "output_membership": membership_rel,
            "output_membership_abs": str(self.analysis_folder / membership_rel),
            "status_file": status_rel,
            "status_file_abs": str(self.analysis_folder / status_rel),
            "stdout_file": stdout_rel,
            "stdout_file_abs": str(self.analysis_folder / stdout_rel),
            "stderr_file": stderr_rel,
            "stderr_file_abs": str(self.analysis_folder / stderr_rel),
            "parameters": {
                "neighbour_radius": float(params["neighbour_radius"]),
                "merge_radius": float(params["merge_radius"]),
                "weight_exponent": float(params["weight_exponent"]),
                "max_iterations": int(params["max_iterations"]),
                "step_size": float(params["step_size"]),
                "min_cluster_size": int(params["min_cluster_size"]),
                "select_point": str(params["select_point"]),
                "cores": int(params["cores"]),
            },
            "notes": "Created by CV3D Python controller for package-backed 03C facet candidate condensation."
        }

        task_path = self.analysis_folder / task_rel
        write_json(task_path, task)
        return task_path

    def launch_r_03c_facet_candidate_condensation(self, eye: str) -> None:
        """Launch package-backed R Step 03C facet candidate condensation."""
        if not self.ensure_step_ready("03c_facet_candidate_condensation", eye):
            return

        self.r_setup_values_from_ui()

        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = configured_file_path(self.settings.get("r_step03c_script_path", ""))

        if rscript is None:
            QMessageBox.warning(
                self,
                "Rscript executable missing",
                "Set a valid Rscript executable in Settings first.\n\n"
                "This should point to Rscript.exe, e.g.\n"
                "C:\\Program Files\\R\\R-4.x.x\\bin\\Rscript.exe"
            )
            self.nav.setCurrentRow(6)
            return

        if not self.ensure_r_package_installed():
            return

        if runner is None:
            QMessageBox.warning(
                self,
                "R Step 03C runner missing",
                "Set a valid CV3D R Step 03C candidate condensation runner .R file in Settings first."
            )
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        input_path = self.analysis_folder / files["local_height_thresholded_file"]
        step03b_state = self.status["workflow_steps"]["03b_local_height_thresholding"][eye].get("state")

        if step03b_state not in ["complete", "complete_with_warning"] or not input_path.exists():
            QMessageBox.warning(
                self,
                "Thresholded local-height points missing",
                "03C requires completed 03B local-height thresholding.\n\n"
                f"03B state: {step03b_state}\n"
                f"Required file: {files['local_height_thresholded_file']}\n"
                f"Exists: {input_path.exists()}"
            )
            self.refresh_all()
            return

        try:
            facet_size = self.read_facet_size_estimate_for_task()
        except Exception:
            facet_size = float(self.config["parameters"]["dataset_defaults"].get("facet_size_estimate", 25.0))

        max_cores = int(self.config.get("compute_settings", {}).get("max_cores") or self.settings.get("compute_settings", {}).get("max_cores") or 1)
        defaults = self.config["parameters"]["dataset_defaults"]

        suggested = {
            "neighbour_radius": self.get_suggested_value(
                eye,
                "facet_candidate_neighbour_radius",
                facet_size * float(defaults.get("facet_candidate_neighbour_radius_factor", 0.5))
            ),
            "merge_radius": self.get_suggested_value(
                eye,
                "facet_candidate_merge_radius",
                facet_size * float(defaults.get("facet_candidate_merge_radius_factor", 0.3))
            ),
            "weight_exponent": self.get_suggested_value(
                eye,
                "facet_candidate_weight_exponent",
                defaults.get("facet_candidate_weight_exponent", 2.0)
            ),
            "max_iterations": self.get_suggested_value(
                eye,
                "facet_candidate_max_iterations",
                defaults.get("facet_candidate_max_iterations", 8)
            ),
            "step_size": self.get_suggested_value(
                eye,
                "facet_candidate_step_size",
                defaults.get("facet_candidate_step_size", 0.7)
            ),
            "min_cluster_size": self.get_suggested_value(
                eye,
                "facet_candidate_min_cluster_size",
                defaults.get("facet_candidate_min_cluster_size", 3)
            ),
            "select_point": self.get_suggested_value(
                eye,
                "facet_candidate_select_point",
                defaults.get("facet_candidate_select_point", "nearest_mode")
            ),
            "cores": self.get_suggested_value(eye, "facet_candidate_cores", max_cores),
        }

        dlg = FacetCandidateCondensationDialog(
            "03C Facet candidate condensation",
            facet_size_estimate=facet_size,
            suggested=suggested,
            max_cores=max_cores,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        params = dlg.values

        try:
            task_path = self.create_r_step03c_task(eye, params)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cannot create R 03C task",
                "Could not create required Step 03C task metadata.\n\n"
                f"{e}"
            )
            return

        task = read_json(task_path)
        reply = QMessageBox.question(
            self,
            "Launch R Step 03C",
            "This will run package-backed facet candidate condensation in R.\n\n"
            f"CV ID: {cv_id}\n"
            f"Eye: {eye}\n"
            f"Input CSV: {task.get('input_local_height_thresholded')}\n"
            f"Output CSV: {task.get('output_facet_candidates')}\n"
            f"Neighbour radius: {params['neighbour_radius']}\n"
            f"Merge radius: {params['merge_radius']}\n"
            f"Weight exponent: {params['weight_exponent']}\n"
            f"Iterations: {params['max_iterations']}\n"
            f"Cores: {params['cores']}\n\n"
            "The GUI will wait until Rscript finishes. After successful condensation, the facet-candidate inspection plot will open automatically.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        state_ref = self.status["workflow_steps"]["03c_facet_candidate_condensation"][eye]
        before = state_ref.get("state", "not_started")
        state_ref["state"] = "running"
        state_ref["symbol"] = STATE_SYMBOL["running"]
        state_ref["last_run"] = now()
        state_ref["needs_rerun"] = False
        state_ref["messages"] = ["Rscript launched for Step 03C facet candidate condensation."]
        self.save_current_files()
        self.refresh_all()

        stdout_path = resolve_task_path(task, "stdout_file_abs", self.analysis_folder)
        stderr_path = resolve_task_path(task, "stderr_file_abs", self.analysis_folder)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        launch_diag_path = self.analysis_folder / eye_log_rel_path(eye, f"03C_{cv_id}_{eye}_R_launch_command.txt")
        write_text(
            launch_diag_path,
            "Command:\n" + " ".join(f'"{part}"' for part in cmd) + "\n\n"
            f"Working directory:\n{self.analysis_folder}\n"
        )

        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_diag_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            self.set_eye_step_state("03c_facet_candidate_condensation", eye, "failed", [f"Could not launch Rscript: {e}"])
            append_log(self.analysis_folder, cv_id, eye, "03c_facet_candidate_condensation", "launch_rscript", before, "failed", "failed", str(e))
            self.save_current_files()
            self.refresh_all()
            QMessageBox.critical(self, "Rscript launch failed", str(e))
            return

        self.load_current_files()
        files = self.config["eyes"][eye]["files"]
        status_path = self.analysis_folder / files["r_step03c_status_file"]
        output_candidates = self.analysis_folder / files["facet_candidates_file"]

        r_status = "unknown"
        status_message = ""
        candidate_count = None
        warnings = []
        if status_path.exists():
            try:
                payload = read_json(status_path)
                r_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
                warnings = payload.get("warnings", []) or []
                candidate_count = payload.get("summary", {}).get("candidate_count")
            except Exception as e:
                r_status = "unreadable_status_json"
                status_message = str(e)

        condensation_succeeded = exit_code == 0 and r_status == "success" and output_candidates.exists()
        if condensation_succeeded:
            messages = [f"R Step 03C finished with status: {r_status}."]
            if candidate_count is not None:
                messages.append(f"Facet candidate count: {candidate_count}.")
            if status_message:
                messages.append(status_message)
            messages.extend(str(w) for w in warnings)
            state = "complete_with_warning" if warnings else "complete"
            self.set_eye_step_state("03c_facet_candidate_condensation", eye, state, messages)
            self.mark_downstream_needs_rerun("03c_facet_candidate_condensation", eye)
            append_log(self.analysis_folder, cv_id, eye, "03c_facet_candidate_condensation", "launch_rscript", before, state, "success", "; ".join(messages))
        else:
            messages = [
                f"Rscript exit code: {exit_code}.",
                f"R status file status: {r_status}.",
                f"Facet candidates CSV exists: {output_candidates.exists()}.",
                f"stdout log: {task['stdout_file']}",
                f"stderr log: {task['stderr_file']}",
            ]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("03c_facet_candidate_condensation", eye, "failed", messages)
            append_log(self.analysis_folder, cv_id, eye, "03c_facet_candidate_condensation", "launch_rscript", before, "failed", "failed", "; ".join(messages))

        if params.get("update_default"):
            self.config["parameters"]["dataset_defaults"]["facet_candidate_weight_exponent"] = float(params["weight_exponent"])
            self.config["parameters"]["dataset_defaults"]["facet_candidate_max_iterations"] = int(params["max_iterations"])
            self.config["parameters"]["dataset_defaults"]["facet_candidate_step_size"] = float(params["step_size"])
            self.config["parameters"]["dataset_defaults"]["facet_candidate_min_cluster_size"] = int(params["min_cluster_size"])
            self.config["parameters"]["dataset_defaults"]["facet_candidate_select_point"] = str(params["select_point"])
            if facet_size > 0:
                self.config["parameters"]["dataset_defaults"]["facet_candidate_neighbour_radius_factor"] = float(params["neighbour_radius"]) / facet_size
                self.config["parameters"]["dataset_defaults"]["facet_candidate_merge_radius_factor"] = float(params["merge_radius"]) / facet_size

        last_used = self.config["parameters"][f"{eye}_last_used"]
        last_used["facet_candidate_neighbour_radius"] = float(params["neighbour_radius"])
        last_used["facet_candidate_merge_radius"] = float(params["merge_radius"])
        last_used["facet_candidate_weight_exponent"] = float(params["weight_exponent"])
        last_used["facet_candidate_max_iterations"] = int(params["max_iterations"])
        last_used["facet_candidate_step_size"] = float(params["step_size"])
        last_used["facet_candidate_min_cluster_size"] = int(params["min_cluster_size"])
        last_used["facet_candidate_select_point"] = str(params["select_point"])
        last_used["facet_candidate_cores"] = int(params["cores"])

        self.config["parameter_history"].append({
            "timestamp": now(),
            "eye": eye,
            "step": "03C",
            "parameter_values": {
                "neighbour_radius": float(params["neighbour_radius"]),
                "merge_radius": float(params["merge_radius"]),
                "weight_exponent": float(params["weight_exponent"]),
                "max_iterations": int(params["max_iterations"]),
                "step_size": float(params["step_size"]),
                "min_cluster_size": int(params["min_cluster_size"]),
                "select_point": str(params["select_point"]),
                "cores": int(params["cores"]),
            },
            "result": r_status,
        })

        self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()

        if condensation_succeeded:
            self.plot_facet_points_on_local_heights(eye, "facet_candidates", automatic=True)

    def create_blender_step04_task(self, eye: str) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        facet_size = self.read_facet_size_estimate_for_task()

        task = {
            "task_type": "facet_position_checking",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_blend": files["cornea_blend_file"],
            "input_blend_abs": str(self.analysis_folder / files["cornea_blend_file"]),
            "input_cornea_stl": files["cornea_stl_file"],
            "input_cornea_stl_abs": str(self.analysis_folder / files["cornea_stl_file"]),
            "input_facet_candidates": files["facet_candidates_file"],
            "input_facet_candidates_abs": str(self.analysis_folder / files["facet_candidates_file"]),
            "output_facet_positions": files["facet_positions_file"],
            "output_facet_positions_abs": str(self.analysis_folder / files["facet_positions_file"]),
            "status_file": files["blender_step04_status_file"],
            "status_file_abs": str(self.analysis_folder / files["blender_step04_status_file"]),
            "facet_size_estimate": facet_size,
            "notes": "Created by CV3D Python controller for Blender Step 04 facet position checking."
        }
        task_path = self.analysis_folder / files["blender_step04_task_file"]
        write_json(task_path, task)
        return task_path

    def launch_blender_facet_position_checking(self, eye: str) -> None:
        if not self.ensure_step_ready("04_blender_facet_check_landmarking", eye):
            return

        if hasattr(self, "blender_executable_edit"):
            self.settings["blender_executable"] = self.blender_executable_edit.text().strip()
        if hasattr(self, "blender_script_edit"):
            self.settings["blender_script_path"] = self.blender_script_edit.text().strip()
        save_app_settings(self.settings)

        blender_exe = configured_file_path(self.settings.get("blender_executable", ""))
        blender_script = configured_file_path(self.settings.get("blender_script_path", ""))
        if blender_exe is None:
            QMessageBox.warning(self, "Blender executable missing", "Set a valid Blender executable in Settings first.")
            self.nav.setCurrentRow(6)
            return
        if blender_script is None:
            QMessageBox.warning(self, "Blender helper script missing", "Set a valid CV3D Blender helper script in Settings first.")
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        blend_path = self.analysis_folder / files["cornea_blend_file"]
        candidates_path = self.analysis_folder / files["facet_candidates_file"]
        if not blend_path.exists() or not candidates_path.exists():
            QMessageBox.warning(
                self,
                "Step 04 inputs missing",
                "Facet position checking requires the existing Step 02 Blender file and Step 03C facet candidates.\n\n"
                f"Blend: {files['cornea_blend_file']}  exists={blend_path.exists()}\n"
                f"Candidates: {files['facet_candidates_file']}  exists={candidates_path.exists()}"
            )
            self.refresh_all()
            return

        try:
            task_path = self.create_blender_step04_task(eye)
        except Exception as e:
            QMessageBox.warning(self, "Cannot create Blender Step 04 task", str(e))
            return

        reply = QMessageBox.question(
            self,
            "Launch Blender Step 04",
            "This opens the existing Step 02 Blender file for manual facet-position checking.\n\n"
            f"CV ID: {cv_id}\nEye: {eye}\nBlend: {files['cornea_blend_file']}\n"
            f"Input candidates: {files['facet_candidates_file']}\n"
            f"Output facet positions: {files['facet_positions_file']}\n\n"
            "When finished, use the CV3D panel in Blender to export facet positions, then close Blender.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        before = self.status["workflow_steps"]["04_blender_facet_check_landmarking"][eye].get("state", "not_started")
        self.status["workflow_steps"]["04_blender_facet_check_landmarking"][eye]["state"] = "running"
        self.status["workflow_steps"]["04_blender_facet_check_landmarking"][eye]["symbol"] = STATE_SYMBOL["running"]
        self.status["workflow_steps"]["04_blender_facet_check_landmarking"][eye]["last_run"] = now()
        self.status["workflow_steps"]["04_blender_facet_check_landmarking"][eye]["messages"] = ["Blender launched for Step 04 facet position checking."]
        self.save_current_files()
        self.refresh_all()

        launch_rel = eye_log_rel_path(eye, f"04_{cv_id}_{eye}_Blender_launch_command.txt")
        launch_path = self.analysis_folder / launch_rel
        launch_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [str(blender_exe), str(blend_path), "--python", str(blender_script), "--", relative_task_argument(task_path, self.analysis_folder)]
        write_text(launch_path, "Command:\n" + " ".join(chr(34) + str(part) + chr(34) for part in cmd) + "\n")

        try:
            result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder))
            exit_code = result.returncode
            with launch_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            self.set_eye_step_state("04_blender_facet_check_landmarking", eye, "failed", [f"Could not launch Blender: {e}"])
            append_log(self.analysis_folder, cv_id, eye, "04_blender_facet_check_landmarking", "launch_blender", before, "failed", "failed", str(e))
            self.save_current_files()
            self.refresh_all()
            QMessageBox.critical(self, "Blender launch failed", str(e))
            return

        self.load_current_files()
        status_path = self.analysis_folder / files["blender_step04_status_file"]
        output_path = self.analysis_folder / files["facet_positions_file"]
        blender_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                blender_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                blender_status = "unreadable_status_json"
                status_message = str(e)

        if exit_code == 0 and output_path.exists() and blender_status in ["exported", "complete", "complete_with_warning"]:
            messages = [f"Blender finished with status: {blender_status}."]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("04_blender_facet_check_landmarking", eye, "complete", messages)
            self.mark_downstream_needs_rerun("04_blender_facet_check_landmarking", eye)
            append_log(self.analysis_folder, cv_id, eye, "04_blender_facet_check_landmarking", "launch_blender", before, "complete", "success", "; ".join(messages))
        else:
            messages = [
                f"Blender exit code: {exit_code}.",
                f"Blender status file status: {blender_status}.",
                f"Facet positions CSV exists: {output_path.exists()}.",
                f"Launch log: {launch_rel}",
            ]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state("04_blender_facet_check_landmarking", eye, "failed", messages)
            append_log(self.analysis_folder, cv_id, eye, "04_blender_facet_check_landmarking", "launch_blender", before, "failed", "failed", "; ".join(messages))

        self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()

    def create_blender_step05_task(self) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        try:
            facet_size = self.read_facet_size_estimate_for_task()
        except Exception:
            facet_size = None
        files = self.config.setdefault("specimen_files", {})
        files.setdefault("head_mesh_file", f"01_{cv_id}_head_ImageJ.stl")
        files.setdefault("head_landmark_blend_file", f"05_{cv_id}_head_landmarks.blend")
        files.setdefault("head_landmarks_file", f"05_{cv_id}_landmarks.csv")
        files["blender_step05_task_file"] = dataset_json_rel_path(f"05_{cv_id}_Blender_task.json")
        files["blender_step05_status_file"] = dataset_json_rel_path(f"05_{cv_id}_Blender_status.json")

        task = {
            "task_type": "head_landmarking",
            "cv_id": cv_id,
            "analysis_folder": str(self.analysis_folder),
            "input_head_mesh": files["head_mesh_file"],
            "input_head_mesh_abs": str(self.analysis_folder / files["head_mesh_file"]),
            "output_blend": files["head_landmark_blend_file"],
            "output_blend_abs": str(self.analysis_folder / files["head_landmark_blend_file"]),
            "output_landmarks": files["head_landmarks_file"],
            "output_landmarks_abs": str(self.analysis_folder / files["head_landmarks_file"]),
            "status_file": files["blender_step05_status_file"],
            "status_file_abs": str(self.analysis_folder / files["blender_step05_status_file"]),
            "landmark_names": ["anterior", "posterior", "left", "right"],
            "facet_size_estimate": facet_size,
            "notes": "Created by CV3D Python controller for specimen-level head landmarking."
        }
        task_path = self.analysis_folder / files["blender_step05_task_file"]
        write_json(task_path, task)
        return task_path

    def launch_blender_head_landmarking(self) -> None:
        if not self.config or not self.analysis_folder:
            return

        if hasattr(self, "blender_executable_edit"):
            self.settings["blender_executable"] = self.blender_executable_edit.text().strip()
        if hasattr(self, "blender_script_edit"):
            self.settings["blender_script_path"] = self.blender_script_edit.text().strip()
        save_app_settings(self.settings)

        blender_exe = configured_file_path(self.settings.get("blender_executable", ""))
        blender_script = configured_file_path(self.settings.get("blender_script_path", ""))
        if blender_exe is None:
            QMessageBox.warning(self, "Blender executable missing", "Set a valid Blender executable in Settings first.")
            self.nav.setCurrentRow(6)
            return
        if blender_script is None:
            QMessageBox.warning(self, "Blender helper script missing", "Set a valid CV3D Blender helper script in Settings first.")
            self.nav.setCurrentRow(6)
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config.setdefault("specimen_files", {})
        head_mesh_rel = files.get("head_mesh_file", f"01_{cv_id}_head_ImageJ.stl")
        head_mesh_path = self.analysis_folder / head_mesh_rel
        if not head_mesh_path.exists():
            QMessageBox.warning(self, "Head mesh missing", f"Expected head mesh not found:\n\n{head_mesh_rel}")
            self.refresh_all()
            return

        try:
            task_path = self.create_blender_step05_task()
        except Exception as e:
            QMessageBox.warning(self, "Cannot create Blender Step 05 task", str(e))
            return

        self.load_current_files()
        files = self.config["specimen_files"]
        blend_path = self.analysis_folder / files["head_landmark_blend_file"]

        reply = QMessageBox.question(
            self,
            "Launch Blender Step 05",
            "This opens a specimen-level Blender scene for head landmarking.\n\n"
            f"Head mesh: {head_mesh_rel}\n"
            f"Blend: {files['head_landmark_blend_file']}\n"
            f"Output landmarks: {files['head_landmarks_file']}\n\n"
            "Use the fixed landmark buttons in Blender, export landmarks, then close Blender.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        step = self.status.setdefault("workflow_steps", {}).setdefault("05_blender_head_landmarking", {"label": STEP_LABELS["05_blender_head_landmarking"]})
        before = step.get("state", "not_started")
        step.update({"state": "running", "symbol": STATE_SYMBOL["running"], "last_run": now(), "needs_rerun": False, "messages": ["Blender launched for Step 05 head landmarking."]})
        self.save_current_files()
        self.refresh_all()

        launch_rel = dataset_log_rel_path(f"05_{cv_id}_Blender_launch_command.txt")
        launch_path = self.analysis_folder / launch_rel
        launch_path.parent.mkdir(parents=True, exist_ok=True)
        if blend_path.exists():
            cmd = [str(blender_exe), str(blend_path), "--python", str(blender_script), "--", str(task_path.resolve())]
        else:
            cmd = [str(blender_exe), "--python", str(blender_script), "--", str(task_path.resolve())]
        write_text(launch_path, "Command:\n" + " ".join(chr(34) + str(part) + chr(34) for part in cmd) + "\n")

        try:
            result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder))
            exit_code = result.returncode
            with launch_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            step.update({"state": "failed", "symbol": STATE_SYMBOL["failed"], "messages": [f"Could not launch Blender: {e}"]})
            append_log(self.analysis_folder, cv_id, "", "05_blender_head_landmarking", "launch_blender", before, "failed", "failed", str(e))
            self.save_current_files()
            self.refresh_all()
            QMessageBox.critical(self, "Blender launch failed", str(e))
            return

        self.load_current_files()
        step = self.status["workflow_steps"].setdefault("05_blender_head_landmarking", {"label": STEP_LABELS["05_blender_head_landmarking"]})
        status_path = self.analysis_folder / files["blender_step05_status_file"]
        landmarks_path = self.analysis_folder / files["head_landmarks_file"]
        blender_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                blender_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                blender_status = "unreadable_status_json"
                status_message = str(e)

        if exit_code == 0 and landmarks_path.exists() and blender_status in ["exported", "complete", "complete_with_warning"]:
            messages = [f"Blender finished with status: {blender_status}."]
            if status_message:
                messages.append(status_message)
            step.update({"state": "complete", "symbol": STATE_SYMBOL["complete"], "last_run": now(), "needs_rerun": False, "messages": messages})
            append_log(self.analysis_folder, cv_id, "", "05_blender_head_landmarking", "launch_blender", before, "complete", "success", "; ".join(messages))
        else:
            messages = [
                f"Blender exit code: {exit_code}.",
                f"Blender status file status: {blender_status}.",
                f"Landmarks CSV exists: {landmarks_path.exists()}.",
                f"Launch log: {launch_rel}",
            ]
            if status_message:
                messages.append(status_message)
            step.update({"state": "failed", "symbol": STATE_SYMBOL["failed"], "last_run": now(), "needs_rerun": False, "messages": messages})
            append_log(self.analysis_folder, cv_id, "", "05_blender_head_landmarking", "launch_blender", before, "failed", "failed", "; ".join(messages))

        self.save_current_files()
        self.refresh_all()

    def resolve_r_analysis_runner(self, key: str) -> Optional[Path]:
        runner = configured_file_path(self.settings.get(key, ""))
        if runner is not None:
            return runner
        bundled = bundled_helper_abs_path(key)
        if bundled is not None:
            self.settings[key] = str(BUNDLED_HELPER_SCRIPTS.get(key, bundled))
            save_app_settings(self.settings)
            return bundled
        return None

    def run_r_analysis_script(self, eye: str, step: str, runner_key: str, task_path: Path, success_message: str) -> None:
        self.r_setup_values_from_ui()
        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = self.resolve_r_analysis_runner(runner_key)

        if rscript is None:
            QMessageBox.warning(self, "Rscript executable missing", "Set a valid Rscript executable in Settings first.")
            self.nav.setCurrentRow(7)
            return
        if runner is None:
            QMessageBox.warning(self, "R runner missing", f"Could not find the bundled or configured runner for {STEP_LABELS[step]}.")
            self.nav.setCurrentRow(7)
            return
        if not self.ensure_r_package_installed():
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        task = read_json(task_path)
        stdout_path = resolve_task_path(task, "stdout_file_abs", self.analysis_folder)
        stderr_path = resolve_task_path(task, "stderr_file_abs", self.analysis_folder)
        launch_path = self.analysis_folder / eye_log_rel_path(eye, f"{task.get('task_prefix', step)}_{cv_id}_{eye}_R_launch_command.txt")
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        launch_path.parent.mkdir(parents=True, exist_ok=True)

        state_ref = self.status["workflow_steps"][step][eye]
        before = state_ref.get("state", "not_started")
        state_ref.update({"state": "running", "symbol": STATE_SYMBOL["running"], "last_run": now(), "needs_rerun": False, "messages": [f"Rscript launched for {STEP_LABELS[step]}."]})
        self.save_current_files()
        self.refresh_all()

        cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
        write_text(launch_path, "Command:\n" + " ".join(chr(34) + str(part) + chr(34) for part in cmd) + "\n\n" + f"Working directory:\n{self.analysis_folder}\n")
        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open("w", encoding="utf-8", errors="replace") as err:
                result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
            exit_code = result.returncode
            with launch_path.open("a", encoding="utf-8") as f:
                f.write(f"\nExit code:\n{exit_code}\n")
        except Exception as e:
            self.set_eye_step_state(step, eye, "failed", [f"Could not launch Rscript: {e}"])
            append_log(self.analysis_folder, cv_id, eye, step, "launch_rscript", before, "failed", "failed", str(e))
            self.save_current_files()
            self.refresh_all()
            QMessageBox.critical(self, "Rscript launch failed", str(e))
            return

        self.load_current_files()
        task = read_json(task_path)
        status_path = resolve_task_path(task, "status_file_abs", self.analysis_folder)
        runner_status = "unknown"
        status_message = ""
        if status_path.exists():
            try:
                payload = read_json(status_path)
                runner_status = str(payload.get("status", "unknown"))
                status_message = str(payload.get("message", ""))
            except Exception as e:
                runner_status = "unreadable_status_json"
                status_message = str(e)

        missing = self.missing_workflow_outputs(step, eye)
        if exit_code == 0 and runner_status == "success" and not missing:
            messages = [success_message]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state(step, eye, "complete", messages)
            self.mark_downstream_needs_rerun(step, eye)
            append_log(self.analysis_folder, cv_id, eye, step, "launch_rscript", before, "complete", "success", "; ".join(messages))
        else:
            messages = [
                f"Rscript exit code: {exit_code}.",
                f"Runner status: {runner_status}.",
                f"Missing outputs: {', '.join(missing) if missing else 'none'}.",
                f"stdout log: {task.get('stdout_file', '')}",
                f"stderr log: {task.get('stderr_file', '')}",
            ]
            if status_message:
                messages.append(status_message)
            self.set_eye_step_state(step, eye, "failed", messages)
            append_log(self.analysis_folder, cv_id, eye, step, "launch_rscript", before, "failed", "failed", "; ".join(messages))

        self.save_current_files()
        self.validate_current_workflow_outputs(save_changes=True)
        self.refresh_all()

    def make_blender_facet_names_authoritative(self, eye: str) -> bool:
        """Use canonical Blender facet names as facet_id values in an existing Step 04 export."""
        files = self.config["eyes"][eye]["files"]
        path = self.analysis_folder / files["facet_positions_file"]
        if not path.exists():
            return False

        with path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        if "facet_id" not in fieldnames or "blender_object_name" not in fieldnames:
            return False

        def is_canonical(name: str) -> bool:
            return bool(re.fullmatch(r"F\d{5}", str(name or "").strip()))

        def extract_numeric_suffix(value: str):
            m = re.search(r"(\d+)$", str(value or "").strip())
            return int(m.group(1)) if m else None

        def canonical_imported(name: str):
            idx = extract_numeric_suffix(name)
            if idx is None or idx < 0 or idx > 99999:
                return None
            return f"F{idx:05d}"

        used = set()
        planned = []

        for row in rows:
            blender_name = str(row.get("blender_object_name", "") or "").strip()
            if is_canonical(blender_name):
                planned.append(blender_name)
                used.add(blender_name)
            else:
                planned.append(None)

        for i, row in enumerate(rows):
            if planned[i] is not None:
                continue
            blender_name = str(row.get("blender_object_name", "") or "").strip()
            proposed = canonical_imported(blender_name)
            if proposed and proposed not in used:
                planned[i] = proposed
                used.add(proposed)

        manual_counter = max([int(name[1:]) for name in used if is_canonical(name) and name.startswith("F9")] or [90000])
        for i, row in enumerate(rows):
            if planned[i] is not None:
                continue
            while True:
                manual_counter += 1
                if manual_counter > 99999:
                    raise ValueError("No free manual facet IDs remain in the F9XXXX range.")
                proposed = f"F{manual_counter:05d}"
                if proposed not in used:
                    planned[i] = proposed
                    used.add(proposed)
                    break

        if len(set(planned)) != len(planned):
            raise ValueError(
                "Facet names in the facet-position table are not unique after canonical renaming. "
                "Facet names must be unique before downstream analysis can run."
            )

        changed = False
        for row, name in zip(rows, planned):
            if not name:
                continue
            if str(row.get("blender_object_name", "") or "") != name:
                row["blender_object_name"] = name
                changed = True
            if str(row.get("facet_id", "") or "") != name:
                row["facet_id"] = name
                changed = True

        if changed:
            write_csv(path, fieldnames, rows)
        return changed

    def create_r_step05a_task(self, eye: str, edge_tol: float, cores: int, lattice: str, normal_method: str, normal_envelope_factor: Optional[float]) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        self.make_blender_facet_names_authoritative(eye)
        facet_size = self.config.get("parameters", {}).get("dataset_defaults", {}).get("facet_size_estimate", 14)
        task = {
            "task_type": "05A_optical_metrics",
            "task_prefix": "05A",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_facet_positions": files["facet_positions_file"],
            "input_facet_positions_abs": str(self.analysis_folder / files["facet_positions_file"]),
            "output_optic_parameters": files["optic_parameters_file"],
            "output_optic_parameters_abs": str(self.analysis_folder / files["optic_parameters_file"]),
            "output_facet_normals": files["facet_normals_file"],
            "output_facet_normals_abs": str(self.analysis_folder / files["facet_normals_file"]),
            "output_facet_sizes": files["facet_sizes_file"],
            "output_facet_sizes_abs": str(self.analysis_folder / files["facet_sizes_file"]),
            "output_interfacet_angles": files["interfacet_angles_file"],
            "output_interfacet_angles_abs": str(self.analysis_folder / files["interfacet_angles_file"]),
            "output_sampling_acuity": files["sampling_acuity_file"],
            "output_sampling_acuity_abs": str(self.analysis_folder / files["sampling_acuity_file"]),
            "output_optical_summary": files["optical_summary_file"],
            "output_optical_summary_abs": str(self.analysis_folder / files["optical_summary_file"]),
            "output_diagnostic_pdf": eye_inspection_rel_path(eye, f"05A_{cv_id}_{eye}_optic_diagnostics.pdf"),
            "output_diagnostic_pdf_abs": str(self.analysis_folder / eye_inspection_rel_path(eye, f"05A_{cv_id}_{eye}_optic_diagnostics.pdf")),
            "status_file": files["r_step05a_status_file"],
            "status_file_abs": str(self.analysis_folder / files["r_step05a_status_file"]),
            "stdout_file": eye_log_rel_path(eye, f"05A_{cv_id}_{eye}_R_stdout.log"),
            "stdout_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"05A_{cv_id}_{eye}_R_stdout.log")),
            "stderr_file": eye_log_rel_path(eye, f"05A_{cv_id}_{eye}_R_stderr.log"),
            "stderr_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"05A_{cv_id}_{eye}_R_stderr.log")),
            "parameters": {
                "edge_tol": float(edge_tol),
                "cores": int(cores),
                "facet_size_estimate": float(facet_size),
                "lattice": str(lattice),
                "normal_method": str(normal_method),
                "normal_envelope_factor": (float(normal_envelope_factor) if normal_envelope_factor is not None else None),
            },
        }
        task_path = self.analysis_folder / files["r_step05a_task_file"]
        write_json(task_path, task)
        return task_path

    def launch_r_05a_optical_metrics(self, eye: str) -> None:
        if not self.ensure_step_ready("05a_optical_metrics", eye):
            return
        max_cores = int(self.config.get("compute_settings", {}).get("max_cores") or self.settings.get("compute_settings", {}).get("max_cores") or 1)
        defaults = self.config["parameters"]["dataset_defaults"]
        lattice_default = str(defaults.get("sampling_lattice", "hexagonal"))
        normal_method_default = str(defaults.get("facet_normal_method", "envelope"))
        try:
            normal_envelope_factor_default = float(defaults.get("facet_normal_envelope_factor", 1.25))
        except Exception:
            normal_envelope_factor_default = 1.25
        dlg = RuntimeParamDialog(
            "05A Optical metrics",
            {"edge_tol": 0.5, "cores": max_cores},
            self,
            show_lattice=True,
            lattice_default=lattice_default,
            show_normal_method=True,
            normal_method_default=normal_method_default,
            normal_envelope_factor_default=normal_envelope_factor_default,
            info_text=(
                "Neighbour-link tolerance is the relative allowance used when deciding whether a candidate link is a true facet-neighbour link. "
                "At 0.5, links up to 1.5× the larger local facet-spacing estimate of the two facets are retained. "
                "Lower values are stricter; higher values retain more links."
            ),
        )
        if dlg.exec() != QDialog.Accepted:
            return
        lattice = str(dlg.values.get("lattice", "hexagonal"))
        normal_method = str(dlg.values.get("normal_method", "envelope"))
        normal_envelope_factor = dlg.values.get("normal_envelope_factor")
        if normal_method == "envelope":
            try:
                normal_envelope_factor = float(normal_envelope_factor)
            except Exception:
                normal_envelope_factor = 1.25
        else:
            normal_envelope_factor = None
        task_path = self.create_r_step05a_task(
            eye,
            dlg.values["edge_tol"],
            int(dlg.values["cores"]),
            lattice,
            normal_method,
            normal_envelope_factor,
        )
        if dlg.values.get("update_default"):
            defaults["sampling_lattice"] = lattice
            defaults["facet_normal_method"] = normal_method
            if normal_method == "envelope" and normal_envelope_factor is not None:
                defaults["facet_normal_envelope_factor"] = float(normal_envelope_factor)
        self.run_r_analysis_script(eye, "05a_optical_metrics", "r_step05a_script_path", task_path, "05A optical metrics completed.")

    def create_r_step05b_task(self, eye: str, priority: str) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        specimen_files = self.config.get("specimen_files", {})
        landmarks_rel = specimen_files.get("head_landmarks_file", f"05_{cv_id}_landmarks.csv")
        crop_log_rel = specimen_files.get("crop_log_file", f"01_{cv_id}_crop.log")
        head_mesh_rel = specimen_files.get("head_mesh_file", f"01_{cv_id}_head_ImageJ.stl")
        cornea_stl_rel = files.get("cornea_stl_file", eye_rel_path(eye, f"02_{cv_id}_{eye}_cornea.stl"))
        anatomical_side = str(self.config.get("eyes", {}).get(eye, {}).get("anatomical_side", "")).strip().lower()
        expected_lateral_landmark = anatomical_side if anatomical_side in ["left", "right"] else ""
        task = {
            "task_type": "05B_global_coordinate_rotation",
            "task_prefix": "05B",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_optic_parameters": files["optic_parameters_file"],
            "input_optic_parameters_abs": str(self.analysis_folder / files["optic_parameters_file"]),
            "input_landmarks": landmarks_rel,
            "input_landmarks_abs": str(self.analysis_folder / landmarks_rel),
            "input_crop_log": crop_log_rel,
            "input_crop_log_abs": str(self.analysis_folder / crop_log_rel),
            "input_head_mesh": head_mesh_rel,
            "input_head_mesh_abs": str(self.analysis_folder / head_mesh_rel),
            "input_cornea_stl": cornea_stl_rel,
            "input_cornea_stl_abs": str(self.analysis_folder / cornea_stl_rel),
            "output_landmark_referenced_coordinates": files["landmark_referenced_coordinates_file"],
            "output_landmark_referenced_coordinates_abs": str(self.analysis_folder / files["landmark_referenced_coordinates_file"]),
            "output_global_aligned_pointcloud": files["global_aligned_pointcloud_file"],
            "output_global_aligned_pointcloud_abs": str(self.analysis_folder / files["global_aligned_pointcloud_file"]),
            "output_global_coordinates": files["global_coordinates_file"],
            "output_global_coordinates_abs": str(self.analysis_folder / files["global_coordinates_file"]),
            "output_global_rotation_matrix": files["global_rotation_matrix_file"],
            "output_global_rotation_matrix_abs": str(self.analysis_folder / files["global_rotation_matrix_file"]),
            "output_global_coordinate_metadata": files["global_coordinate_metadata_file"],
            "output_global_coordinate_metadata_abs": str(self.analysis_folder / files["global_coordinate_metadata_file"]),
            "status_file": files["r_step05b_status_file"],
            "status_file_abs": str(self.analysis_folder / files["r_step05b_status_file"]),
            "stdout_file": eye_log_rel_path(eye, f"05B_{cv_id}_{eye}_R_stdout.log"),
            "stdout_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"05B_{cv_id}_{eye}_R_stdout.log")),
            "stderr_file": eye_log_rel_path(eye, f"05B_{cv_id}_{eye}_R_stderr.log"),
            "stderr_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"05B_{cv_id}_{eye}_R_stderr.log")),
            "parameters": {"priority": priority, "expected_lateral_landmark": expected_lateral_landmark},
        }
        task_path = self.analysis_folder / files["r_step05b_task_file"]
        write_json(task_path, task)
        return task_path

    def launch_r_05b_global_coordinate_rotation(self, eye: str) -> None:
        if not self.ensure_step_ready("05b_global_coordinate_rotation", eye):
            return
        priority, ok = QInputDialog.getItem(self, "05B Global coordinate rotation", "Alignment priority:", ["RL", "AP"], 0, False)
        if not ok:
            return
        task_path = self.create_r_step05b_task(eye, str(priority))
        self.run_r_analysis_script(eye, "05b_global_coordinate_rotation", "r_step05b_script_path", task_path, "05B global coordinate rotation completed.")

    def create_r_step05c_task(self, eye: str, sphere_size_cm: float, center_mode: str) -> Path:
        cv_id = self.config["dataset_identity"]["cv_id"]
        files = self.config["eyes"][eye]["files"]
        other_eye = "eye2" if eye == "eye1" else "eye1"
        other_files = self.config.get("eyes", {}).get(other_eye, {}).get("files", {})
        other_global_rel = other_files.get("global_coordinates_file", "")
        other_global_abs = str(self.analysis_folder / other_global_rel) if other_global_rel else ""
        if not other_global_rel or not Path(other_global_abs).exists():
            other_global_rel = ""
            other_global_abs = ""
        task = {
            "task_type": "05C_corneal_projections",
            "task_prefix": "05C",
            "cv_id": cv_id,
            "eye": eye,
            "analysis_folder": str(self.analysis_folder),
            "input_global_coordinates": files["global_coordinates_file"],
            "input_global_coordinates_abs": str(self.analysis_folder / files["global_coordinates_file"]),
            "input_other_eye_global_coordinates": other_global_rel,
            "input_other_eye_global_coordinates_abs": other_global_abs,
            "output_corneal_projections": files["corneal_projections_file"],
            "output_corneal_projections_abs": str(self.analysis_folder / files["corneal_projections_file"]),
            "status_file": files["r_step05c_status_file"],
            "status_file_abs": str(self.analysis_folder / files["r_step05c_status_file"]),
            "stdout_file": eye_log_rel_path(eye, f"05C_{cv_id}_{eye}_R_stdout.log"),
            "stdout_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"05C_{cv_id}_{eye}_R_stdout.log")),
            "stderr_file": eye_log_rel_path(eye, f"05C_{cv_id}_{eye}_R_stderr.log"),
            "stderr_file_abs": str(self.analysis_folder / eye_log_rel_path(eye, f"05C_{cv_id}_{eye}_R_stderr.log")),
            "parameters": {
                "corneal_projection_sphere_size_cm": float(sphere_size_cm),
                "corneal_projection_sphere_size_um": float(sphere_size_cm) * 10000.0,
                "projection_center_mode": center_mode,
            },
        }
        task_path = self.analysis_folder / files["r_step05c_task_file"]
        write_json(task_path, task)
        return task_path

    def launch_r_05c_corneal_projections(self, eye: str) -> None:
        if not self.ensure_step_ready("05c_corneal_projections", eye):
            return
        defaults = self.config["parameters"]["dataset_defaults"]
        suggested = self.get_suggested_value(eye, "corneal_projection_sphere_size_cm", defaults.get("corneal_projection_sphere_size_cm", 15.0))
        dlg = RuntimeParamDialog(
            "05C Corneal projections",
            {"corneal_projection_sphere_size_cm": suggested},
            self,
            show_projection_center=True,
            projection_center_default=defaults.get("projection_center_mode", "between_eyes"),
        )
        if dlg.exec() != QDialog.Accepted:
            return
        sphere = dlg.values["corneal_projection_sphere_size_cm"]
        center_mode = dlg.values["projection_center_mode"]
        task_path = self.create_r_step05c_task(eye, sphere, center_mode)
        if dlg.values.get("update_default"):
            defaults["corneal_projection_sphere_size_cm"] = sphere
            defaults["projection_center_mode"] = center_mode
            self.config["parameters"][f"{eye}_last_used"]["corneal_projection_sphere_size_cm"] = sphere
        self.run_r_analysis_script(eye, "05c_corneal_projections", "r_step05c_script_path", task_path, "05C corneal projections completed.")

    def create_mirrored_outputs(self) -> None:
        if not self.config or not self.status or not self.analysis_folder:
            QMessageBox.warning(self, "No dataset", "Create or open a dataset first.")
            return
        if not hasattr(self, "mirror_source_combo"):
            return

        source = self.mirror_source_combo.currentData()
        target = self.mirror_target_combo.currentData()
        plane_button = self.mirror_plane_group.checkedButton() if hasattr(self, "mirror_plane_group") else None
        mirror_plane = str(plane_button.property("value") if plane_button else "yz").lower()

        if not source or not target:
            QMessageBox.warning(self, "Mirroring unavailable", "Choose a source eye and a target anatomical eye first.")
            return
        if source == target:
            QMessageBox.warning(self, "Invalid mirror target", "Source and target are the same eye. Choose the opposite anatomical eye as target.")
            return
        if source not in self.config.get("eyes", {}) or not self.config["eyes"][source].get("present", False):
            QMessageBox.warning(self, "Source eye unavailable", f"{source} is not marked as present.")
            return

        cv_id = self.config["dataset_identity"]["cv_id"]
        source_files = self.config["eyes"][source]["files"]
        derived_eye_id = str(target)
        ensure_eye_subfolders(self.analysis_folder, [derived_eye_id])
        flip_axis = {"xy": "z", "yz": "x", "xz": "y"}.get(mirror_plane, "x")
        created_at = now()

        def wrap_azimuth(value: float) -> float:
            return ((value + 180.0) % 360.0) - 180.0

        def mirror_numeric_value(value: Any) -> Any:
            try:
                if value in (None, ""):
                    return value
                return str(-float(value))
            except Exception:
                return value

        def column_matches_axis(col: str, axis: str) -> bool:
            low = str(col).strip().lower()
            exact = {
                axis, f"{axis}_original", f"{axis}_global", f"{axis}_local", f"{axis}_reference", f"{axis}_aligned",
                f"roi_{axis}", f"{axis}_roi", f"center_{axis}", f"sphere_center_{axis}",
                f"projection_{axis}", f"projection_sphere_center_{axis}", f"corn.proj.{axis}", f"corn_proj_{axis}",
                f"norm.{axis}", f"norm.{axis}_original", f"norm.{axis}_global", f"normal_{axis}", f"n{axis}",
                f"data_{axis}", f"ref_{axis}"
            }
            if low in exact:
                return True
            if low.endswith(f".{axis}") or low.endswith(f"_{axis}"):
                return low.startswith(("norm", "normal", "corn", "projection", "sphere", "center", "roi", "ref", "data"))
            return False

        def mirror_view_angles_if_present(row: Dict[str, Any]) -> None:
            elevation_key = "elevation" if "elevation" in row else ("latitude" if "latitude" in row else None)
            azimuth_key = "azimuth" if "azimuth" in row else ("longitude" if "longitude" in row else None)
            if elevation_key and mirror_plane == "xy":
                row[elevation_key] = mirror_numeric_value(row.get(elevation_key))
            if azimuth_key:
                try:
                    angle = float(row.get(azimuth_key))
                    if mirror_plane == "yz":
                        row[azimuth_key] = str(wrap_azimuth(-angle))
                    elif mirror_plane == "xz":
                        row[azimuth_key] = str(wrap_azimuth(180.0 - angle))
                except Exception:
                    pass

        def row_is_landmark(row: Dict[str, Any]) -> bool:
            # Mixed 05B point-cloud tables contain both facets and specimen-level
            # head landmarks. Mirroring must affect only the eye/facet rows; the
            # specimen landmarks remain the original real landmarks.
            for key in ("point_type", "type"):
                value = str(row.get(key, "")).strip().lower()
                if value in {"lm", "landmark", "landmarks"}:
                    return True
            landmark_value = str(row.get("landmark", "")).strip()
            if landmark_value and landmark_value.lower() not in {"na", "nan", "none"}:
                return True
            for key in ("point_id", "id", "ID"):
                value = str(row.get(key, "")).strip().lower()
                if value in {"anterior", "posterior", "left", "right"}:
                    return True
            return False

        def mirror_csv(src_rel: str, dst_rel: str) -> None:
            src_path = self.analysis_folder / src_rel
            dst_path = self.analysis_folder / dst_rel
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            with src_path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames or [])
                for field in ["mirrored_from_eye", "target_anatomical_eye", "mirror_plane", "source_file", "data_origin"]:
                    if field not in fieldnames:
                        fieldnames.append(field)
                rows = []
                for row in reader:
                    is_landmark = row_is_landmark(row)
                    if not is_landmark:
                        for col in list(row.keys()):
                            if column_matches_axis(col, flip_axis):
                                row[col] = mirror_numeric_value(row[col])
                        mirror_view_angles_if_present(row)
                    if "eye" in row:
                        row["eye"] = derived_eye_id
                    row["data_origin"] = "mirrored_landmark_not_transformed" if is_landmark else "mirrored"
                    row["mirrored_from_eye"] = source
                    row["target_anatomical_eye"] = target
                    row["mirror_plane"] = mirror_plane.upper()
                    row["source_file"] = src_rel
                    rows.append(row)
            write_csv(dst_path, fieldnames, rows)

        def mirror_json(src_rel: str, dst_rel: str) -> None:
            try:
                payload = read_json(self.analysis_folder / src_rel)
            except Exception:
                payload = {"source_json_unreadable": src_rel}
            if isinstance(payload, dict):
                payload.update({
                    "eye": derived_eye_id,
                    "data_origin": "mirrored",
                    "mirrored_from_eye": source,
                    "target_anatomical_eye": target,
                    "mirror_plane": mirror_plane.upper(),
                    "source_file": src_rel,
                    "notes": "Mirrored from existing source-eye output; optical metrics and corneal projections were not recalculated."
                })
            write_json(self.analysis_folder / dst_rel, payload)

        def copy_binary(src_rel: str, dst_rel: str) -> None:
            out_path = self.analysis_folder / dst_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.analysis_folder / src_rel, out_path)

        def remove_path_if_exists(rel: Optional[str]) -> None:
            if not rel:
                return
            p = self.analysis_folder / str(rel)
            if p.is_file():
                try:
                    p.unlink()
                except Exception:
                    pass

        def remove_old_nonactual_mirror_folders() -> None:
            # Older builds created folders such as eye2_mirrored_from_eye1_xz.
            # The current behaviour writes the mirrored result into the actual target eye folder.
            for old_eye_id in list(self.config.get("eyes", {}).keys()):
                if "_mirrored_from_" in str(old_eye_id):
                    old_folder = self.analysis_folder / eye_folder_name(str(old_eye_id))
                    if old_folder.exists() and old_folder.is_dir():
                        shutil.rmtree(old_folder, ignore_errors=True)
                    self.config.get("eyes", {}).pop(old_eye_id, None)
                    self.config.get("derived_eyes", {}).pop(old_eye_id, None)
                    for step_payload in self.status.get("workflow_steps", {}).values():
                        if isinstance(step_payload, dict):
                            step_payload.pop(old_eye_id, None)
                    self.status.get("eye_inventory", {}).pop(old_eye_id, None)

        remove_old_nonactual_mirror_folders()

        target_entry = self.config.setdefault("eyes", {}).setdefault(target, {"present": True, "anatomical_side": target, "notes": "", "files": {}})
        target_files = target_entry.setdefault("files", {})
        default_target_files = eye_file_map(cv_id, target)
        for key, rel in default_target_files.items():
            if key not in target_files or target_files.get(key) in (None, ""):
                target_files[key] = rel
        derived_files = target_files
        derived_files.update({"source_mirrored_from_eye": source, "target_anatomical_eye": target, "mirror_plane": mirror_plane.upper()})

        csv_or_json_keys = [
            "facet_positions_file", "optic_parameters_file", "facet_normals_file", "facet_sizes_file",
            "interfacet_angles_file", "sampling_acuity_file", "optical_summary_file",
            "landmark_referenced_coordinates_file", "global_aligned_pointcloud_file", "global_coordinates_file",
            "global_rotation_matrix_file", "global_coordinate_metadata_file", "corneal_projections_file"
        ]
        optional_binary_pairs = [
            (eye_inspection_rel_path(source, f"05A_{cv_id}_{source}_optic_diagnostics.pdf"),
             eye_inspection_rel_path(target, f"05A_{cv_id}_{target}_optic_diagnostics.pdf"))
        ]

        # Overwrite means: remove old target 04/05 outputs and old target QC PNGs/PDFs first.
        for key in csv_or_json_keys + ["blender_step04_status_file", "r_step05a_status_file", "r_step05b_status_file", "r_step05c_status_file"]:
            remove_path_if_exists(derived_files.get(key))
        target_inspection = self.analysis_folder / eye_folder_name(target) / "inspection"
        if target_inspection.exists():
            for pattern in ["04_*", "05A_*", "05B_*", "05C_*"]:
                for p in target_inspection.glob(pattern):
                    if p.is_file():
                        try:
                            p.unlink()
                        except Exception:
                            pass

        created: List[str] = []
        missing: List[str] = []
        for key in csv_or_json_keys:
            src_rel = source_files.get(key); dst_rel = derived_files.get(key)
            if not src_rel or not dst_rel or not (self.analysis_folder / str(src_rel)).exists():
                missing.append(src_rel or f"{key} not set")
                continue
            src_rel = str(src_rel); dst_rel = str(dst_rel)
            if src_rel.lower().endswith(".csv"):
                mirror_csv(src_rel, dst_rel)
            elif src_rel.lower().endswith(".json"):
                mirror_json(src_rel, dst_rel)
            else:
                copy_binary(src_rel, dst_rel)
            created.append(dst_rel)

        # ROI-reference audit is derived from the 05B metadata filename convention.
        source_meta = source_files.get("global_coordinate_metadata_file")
        derived_meta = derived_files.get("global_coordinate_metadata_file")
        optional_pairs = []
        if source_meta and derived_meta:
            optional_pairs.append((str(source_meta).replace(".json", "_roi_reference.csv"), str(derived_meta).replace(".json", "_roi_reference.csv")))
        optional_pairs.extend(optional_binary_pairs)
        for src_rel, dst_rel in optional_pairs:
            if (self.analysis_folder / str(src_rel)).exists():
                remove_path_if_exists(dst_rel)
                if str(src_rel).lower().endswith(".csv"):
                    mirror_csv(str(src_rel), str(dst_rel))
                else:
                    copy_binary(str(src_rel), str(dst_rel))
                created.append(str(dst_rel))

        if not created:
            report = f"No mirrored files were created for {source} -> {target}.\n\nRun the source eye workflow at least through step 04/05 first, or check that source files exist.\n\nMissing source files:\n" + "\n".join(f"- {m}" for m in missing)
            self.mirror_report.setPlainText(report)
            QMessageBox.warning(self, "No mirror outputs created", report)
            return

        for key, msg in [
            ("blender_step04_status_file", "04 facet positions mirrored from source eye; step was not rerun."),
            ("r_step05a_status_file", "05A optical outputs mirrored from source eye; no recalculation."),
            ("r_step05b_status_file", "05B global-coordinate outputs mirrored from source eye; no recalculation."),
            ("r_step05c_status_file", "05C corneal-projection outputs mirrored from source eye; no recalculation.")
        ]:
            rel = derived_files.get(key)
            if rel:
                write_json(self.analysis_folder / str(rel), {
                    "status": "success",
                    "message": msg,
                    "cv_id": cv_id,
                    "eye": derived_eye_id,
                    "data_origin": "mirrored",
                    "mirrored_from_eye": source,
                    "target_anatomical_eye": target,
                    "mirror_plane": mirror_plane.upper(),
                    "created": created_at
                })
                created.append(str(rel))

        meta_file = eye_rel_path(target, f"05D_{cv_id}_{target}_mirrored_eye_metadata.json")
        meta = {
            "mirroring_version": "0.3.2",
            "cv_id": cv_id,
            "created": created_at,
            "mirrored_eye": target,
            "source_eye": source,
            "target_anatomical_eye": target,
            "target_original_eye_was_present": bool(self.config["eyes"].get(target, {}).get("present", False)),
            "mirror_plane": mirror_plane.upper(),
            "folder": eye_folder_name(target),
            "tag": "mirrored",
            "created_files": created,
            "missing_source_files": missing,
            "notes": f"Mirrored outputs derived from {source} and written into the actual {target} eye folder. Facet positions, 05A optical outputs, 05B global facet outputs, and 05C corneal projections are mirrored from existing files; specimen-level head landmark rows are copied unchanged and are not mirrored."
        }
        write_json(self.analysis_folder / meta_file, meta)
        created.append(meta_file)
        meta["created_files"] = created
        write_json(self.analysis_folder / meta_file, meta)

        target_entry.update({
            "present": True,
            "anatomical_side": target,
            "kind": "mirrored",
            "mirrored": True,
            "mirrored_from_eye": source,
            "target_anatomical_eye": target,
            "mirror_plane": mirror_plane.upper(),
            "notes": "Mirrored eye; 04/05A/05B/05C values are derived from the source eye and were not recalculated.",
            "files": derived_files
        })

        inv = self.config.setdefault("eye_inventory", {})
        active = list(inv.get("active_eyes", []))
        if target not in active:
            active.append(target)
        inv["active_eyes"] = [eye for eye in EYES if eye in active or self.config.get("eyes", {}).get(eye, {}).get("present", False)]
        inv["missing_eyes"] = [eye for eye in EYES if eye not in inv["active_eyes"]]

        workflow = self.status.setdefault("workflow_steps", {})
        for step in STEP_ORDER:
            workflow.setdefault(step, {"label": STEP_LABELS.get(step, step)})
            if step in {"04_blender_facet_check_landmarking", "05a_optical_metrics", "05b_global_coordinate_rotation", "05c_corneal_projections"}:
                state = "complete_with_warning" if missing else "complete"
                message = f"Values mirrored from {source} using {mirror_plane.upper()} plane; this step was not rerun."
                symbol = "⇄"
            else:
                state = "skipped"
                message = f"Skipped for mirrored {target}; upstream source-eye data from {source} were reused."
                symbol = STATE_SYMBOL["skipped"]
            workflow[step][target] = {
                "state": state,
                "symbol": symbol,
                "last_run": created_at,
                "needs_rerun": False,
                "mirrored": True,
                "source_eye": source,
                "target_eye": target,
                "messages": [message]
            }
        self.status.setdefault("eye_inventory", {})[target] = {
            "present": True,
            "state": "mirrored",
            "symbol": "⇄",
            "messages": [f"Mirrored from {source}; represents anatomical {target}; plane {mirror_plane.upper()}."]
        }
        run_record = {
            "created": created_at,
            "mirrored_eye": target,
            "source_eye": source,
            "target_anatomical_eye": target,
            "mirror_plane": mirror_plane.upper(),
            "metadata_file": meta_file,
            "files": created,
            "missing_source_files": missing,
            "status": "complete_with_warning" if missing else "complete"
        }
        self.config.setdefault("derived_eyes", {}).pop(target, None)
        self.config.setdefault("mirroring_history", []).append(run_record)
        mirrored = self.config.setdefault("mirrored_outputs", {})
        mirrored["enabled"] = True
        mirrored["created"] = created_at
        mirrored["status"] = run_record["status"]
        mirrored["latest_run"] = run_record
        mirrored.setdefault("runs", []).append(run_record)
        self.status["workflow_steps"]["05d_mirror_missing_eye"] = {
            "label": STEP_LABELS["05d_mirror_missing_eye"],
            "state": run_record["status"],
            "symbol": "⇄",
            "source_eye": source,
            "target_eye": target,
            "mirrored_eye": target,
            "mirror_plane": mirror_plane.upper(),
            "needs_rerun": False,
            "messages": [
                f"Overwrote mirrored 04/05 outputs in the actual {target} folder.",
                "04/05A/05B/05C eye outputs are mirrored from existing files; optics and CPs were not recalculated; specimen landmarks are not mirrored.",
                *([f"Missing source files: {len(missing)}"] if missing else [])
            ]
        }
        append_log(self.analysis_folder, cv_id, target, "05d_mirror_eye_outputs", "create_mirror", "not_created", run_record["status"], "success", f"source={source}; target={target}; plane={mirror_plane.upper()}; created={len(created)}; missing={len(missing)}")
        self.save_current_files()
        self.refresh_all()

        report_lines = [
            f"Mirrored eye written to actual target folder: {target}",
            f"Source eye: {source}",
            f"Target anatomical eye: {target}",
            f"Mirror plane: {mirror_plane.upper()}",
            "Scope: 04 facet positions -> 05C corneal projections",
            "Optical values and corneal projections were mirrored from existing outputs, not recalculated. Specimen landmarks were copied unchanged.",
            "Existing target 04/05 outputs and old target QC plots were overwritten/cleared.",
            f"Created files: {len(created)}"
        ]
        report_lines.extend(f"- {rel}" for rel in created)
        if missing:
            report_lines.append("")
            report_lines.append(f"Missing source files: {len(missing)}")
            report_lines.extend(f"- {rel}" for rel in missing)
        report = "\n".join(report_lines)
        self.mirror_report.setPlainText(report)
        QMessageBox.information(self, "Mirrored eye outputs created", report)

    def ensure_report_outputs_config(self) -> None:
        if not self.config:
            return
        cv_id = self.config.get("dataset_identity", {}).get("cv_id", "CVXXXX")
        out = self.config.setdefault("report_outputs", {})
        export_folder = f"06_{cv_id}_results_export"
        out.setdefault("export_folder", {"folder": export_folder, "status": "ready", "last_created": None})
        out["export_folder"]["folder"] = export_folder
        defaults = {
            "analysis_ready_table": f"{export_folder}/06_{cv_id}_facet_level_analysis_ready.csv",
            "eye_summary": f"{export_folder}/06_{cv_id}_eye_summary.csv",
            "specimen_summary": f"{export_folder}/06_{cv_id}_specimen_summary.csv",
            "metadata_json": f"{export_folder}/06_{cv_id}_export_metadata.json",
            "export_manifest": f"{export_folder}/06_{cv_id}_export_manifest.csv",
            "optic_barplots_png": f"{export_folder}/06_{cv_id}_optic_parameter_summary_barplots.png",
            "cp_view_angles_png": f"{export_folder}/06_{cv_id}_corneal_projection_view_angles_acuity.png",
            "qc_pdf_report": f"{export_folder}/06_{cv_id}_analysis_ready_export_QC_report.pdf",
            "html_report": f"{export_folder}/06_{cv_id}_analysis_ready_export_QC_report.html",
            "parameter_summary": f"{export_folder}/06_{cv_id}_parameter_summary.csv",
            "eye_workflow_summary": f"{export_folder}/06_{cv_id}_eye_workflow_summary.csv",
            "pdf_export": f"{export_folder}/06_{cv_id}_analysis_ready_export_QC_report.pdf",
            "zip_export": f"{export_folder}/06_{cv_id}_CV3D_analysis_ready_export.zip",
        }
        for key, filename in defaults.items():
            out.setdefault(key, {"file": filename, "status": "not_created", "last_created": None})
            current = str(out[key].get("file", "") or "")
            if not current or Path(current).parent == Path("."):
                out[key]["file"] = filename
            elif not current.startswith(export_folder + "/") and Path(current).name.startswith("06_"):
                out[key]["file"] = f"{export_folder}/{Path(current).name}"
            out[key].setdefault("status", "not_created")
            out[key].setdefault("last_created", None)
        if self.analysis_folder:
            (self.analysis_folder / export_folder).mkdir(parents=True, exist_ok=True)
        self.status.setdefault("workflow_steps", {}).setdefault("06_report_export", {"label": STEP_LABELS["06_report_export"]})
        rep = self.status["workflow_steps"]["06_report_export"]
        rep.setdefault("analysis_ready_export", {"state": "not_created", "symbol": "○", "last_run": None, "needs_rerun": False, "messages": []})
        rep.setdefault("html_report", {"state": "not_created", "symbol": "○", "last_run": None, "needs_rerun": False, "messages": []})
        rep.setdefault("pdf_export", {"state": "not_exported", "symbol": "○", "last_exported": None, "outdated_export": False, "messages": []})
        rep.setdefault("zip_export", {"state": "not_exported", "symbol": "○", "last_exported": None, "outdated_export": False, "messages": []})

    def active_export_eyes(self) -> List[str]:
        if not self.config:
            return []
        eyes = []
        for eye in EYES:
            info = self.config.get("eyes", {}).get(eye, {})
            if info.get("present", False):
                eyes.append(eye)
        return eyes

    def export_readiness_lines(self) -> List[str]:
        if not self.config or not self.analysis_folder:
            return ["No dataset loaded."]
        lines = ["Export readiness:"]
        for eye in self.active_export_eyes():
            info = self.config.get("eyes", {}).get(eye, {})
            files = info.get("files", {})
            mirrored = info.get("mirrored", False)
            provenance = "mirrored" if mirrored else "real"
            lines.append(f"{eye}: present ({provenance})")
            for label, key in [("05A optics", "optic_parameters_file"), ("05B globals", "global_coordinates_file"), ("05C CPs", "corneal_projections_file")]:
                rel = files.get(key, "")
                ok = bool(rel) and (self.analysis_folder / str(rel)).exists()
                prefix = "✓" if ok else "!"
                lines.append(f"  {prefix} {label}: {rel if rel else 'not configured'}")
            if mirrored:
                lines.append(f"  ⇄ mirrored from {info.get('mirrored_from_eye', '?')} | plane {info.get('mirror_plane', '?')}")
        if not self.active_export_eyes():
            lines.append("! No present eyes available for export.")
        return lines

    def read_csv_rows_rel(self, rel: Any) -> List[Dict[str, Any]]:
        if not rel or not self.analysis_folder:
            return []
        path = self.analysis_folder / str(rel)
        if not path.exists():
            return []
        with path.open("r", newline="", encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f))

    def facet_key_from_row(self, row: Dict[str, Any]) -> str:
        for key in ["facet_id", "facetID", "facet", "point_id", "ID", "id"]:
            value = row.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    def index_by_facet(self, rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = self.facet_key_from_row(row)
            if key:
                out[key] = row
        return out

    def is_facet_row(self, row: Dict[str, Any]) -> bool:
        pt = str(row.get("point_type", row.get("type", "facet"))).strip().lower()
        if pt in ["lm", "landmark", "head_landmark"]:
            return False
        if row.get("landmark") not in (None, "") and row.get("facet_id") in (None, ""):
            return False
        return True

    def numeric_or_blank(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            f = float(value)
            if f != f:
                return ""
            return f"{f:.10g}"
        except Exception:
            return str(value)

    def first_existing_value(self, row: Optional[Dict[str, Any]], candidates: List[str]) -> Any:
        if not row:
            return ""
        lower_map = {str(k).lower(): k for k in row.keys()}
        for cand in candidates:
            if cand in row and row[cand] not in (None, ""):
                return row[cand]
            key = lower_map.get(cand.lower())
            if key is not None and row.get(key) not in (None, ""):
                return row[key]
        return ""

    def stats_from_rows(self, rows: List[Dict[str, Any]], column: str) -> Dict[str, str]:
        vals = []
        for row in rows:
            try:
                v = float(row.get(column, ""))
                if v == v:
                    vals.append(v)
            except Exception:
                pass
        if not vals:
            return {"mean": "", "median": "", "sd": ""}
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        mean = sum(vals_sorted) / n
        median = vals_sorted[n // 2] if n % 2 else (vals_sorted[n // 2 - 1] + vals_sorted[n // 2]) / 2
        sd = ""
        if n > 1:
            sd_val = (sum((x - mean) ** 2 for x in vals_sorted) / (n - 1)) ** 0.5
            sd = f"{sd_val:.10g}"
        return {"mean": f"{mean:.10g}", "median": f"{median:.10g}", "sd": sd}

    def range_from_rows(self, rows: List[Dict[str, Any]], column: str) -> Dict[str, str]:
        vals = []
        for row in rows:
            try:
                v = float(row.get(column, ""))
                if v == v:
                    vals.append(v)
            except Exception:
                pass
        if not vals:
            return {"min": "", "max": ""}
        return {"min": f"{min(vals):.10g}", "max": f"{max(vals):.10g}"}

    def circular_interval_from_rows(self, rows: List[Dict[str, Any]], column: str = "azimuth") -> Dict[str, str]:
        vals: List[float] = []
        for row in rows:
            try:
                value = float(row.get(column, ""))
                if value == value:
                    vals.append(value % 360.0)
            except Exception:
                pass
        if not vals:
            return {"start": "", "end": "", "span_deg": ""}
        vals = sorted(vals)
        if len(vals) == 1:
            angle = ((vals[0] + 180.0) % 360.0) - 180.0
            return {"start": f"{angle:.10g}", "end": f"{angle:.10g}", "span_deg": "0"}
        gaps = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
        gaps.append(vals[0] + 360.0 - vals[-1])
        gap_index = max(range(len(gaps)), key=gaps.__getitem__)
        start360 = vals[(gap_index + 1) % len(vals)]
        end360 = vals[gap_index]
        span = 360.0 - gaps[gap_index]
        to_signed = lambda a: ((a + 180.0) % 360.0) - 180.0
        return {
            "start": f"{to_signed(start360):.10g}",
            "end": f"{to_signed(end360):.10g}",
            "span_deg": f"{span:.10g}",
        }

    def collect_analysis_ready_rows(self) -> List[Dict[str, Any]]:
        cv_id = self.config["dataset_identity"]["cv_id"]
        rows: List[Dict[str, Any]] = []
        for eye in self.active_export_eyes():
            eye_info = self.config.get("eyes", {}).get(eye, {})
            files = eye_info.get("files", {})
            global_rows = [r for r in self.read_csv_rows_rel(files.get("global_coordinates_file")) if self.is_facet_row(r)]
            facet_size = self.index_by_facet(self.read_csv_rows_rel(files.get("facet_sizes_file")))
            interfacet = self.index_by_facet(self.read_csv_rows_rel(files.get("interfacet_angles_file")))
            sampling_acuity = self.index_by_facet(self.read_csv_rows_rel(files.get("sampling_acuity_file")))
            optic = self.index_by_facet(self.read_csv_rows_rel(files.get("optic_parameters_file")))
            cp = self.index_by_facet(self.read_csv_rows_rel(files.get("corneal_projections_file")))
            for grow in global_rows:
                fid = self.facet_key_from_row(grow)
                if not fid:
                    continue
                size_row = facet_size.get(fid) or optic.get(fid) or grow
                angle_row = interfacet.get(fid) or optic.get(fid) or grow
                optics_row = sampling_acuity.get(fid) or optic.get(fid) or grow
                normal_row = optic.get(fid) or grow
                cp_row = cp.get(fid) or {}
                out = {
                    "cv_id": cv_id,
                    "eye": eye,
                    "facet_id": fid,
                    "data_origin": "mirrored" if eye_info.get("mirrored") else "real",
                    "mirrored": "TRUE" if eye_info.get("mirrored") else "FALSE",
                    "mirrored_from_eye": eye_info.get("mirrored_from_eye", ""),
                    "mirror_plane": eye_info.get("mirror_plane", ""),
                    "x_global": self.numeric_or_blank(self.first_existing_value(grow, ["x_global", "x"])),
                    "y_global": self.numeric_or_blank(self.first_existing_value(grow, ["y_global", "y"])),
                    "z_global": self.numeric_or_blank(self.first_existing_value(grow, ["z_global", "z"])),
                    "norm.x_global": self.numeric_or_blank(self.first_existing_value(grow, ["norm.x_global", "norm.x", "normal_x", "nx"])),
                    "norm.y_global": self.numeric_or_blank(self.first_existing_value(grow, ["norm.y_global", "norm.y", "normal_y", "ny"])),
                    "norm.z_global": self.numeric_or_blank(self.first_existing_value(grow, ["norm.z_global", "norm.z", "normal_z", "nz"])),
                    "facet_size_um": self.numeric_or_blank(self.first_existing_value(size_row, ["facet_size_um", "facet_size_smoothed", "facet_size", "size", "diameter_um", "facet_diameter_um"])),
                    "interfacet_angle_deg": self.numeric_or_blank(self.first_existing_value(angle_row, ["interfacet_angle_deg", "delta_phi.deg", "delta_phi_deg", "angle_deg", "interfacet_angle"])),
                    "eye_parameter": self.numeric_or_blank(self.first_existing_value(optics_row, ["eye_parameter", "sensitivity", "P", "P_corr", "sensitivity_corr"])),
                    "sampling_frequency_rad": self.numeric_or_blank(self.first_existing_value(optics_row, ["sampling_frequency_rad", "sampling_frequency"])),
                    "sampling_lattice": str(self.first_existing_value(optics_row, ["sampling_lattice", "lattice"])),
                    "acuity_cpd": self.numeric_or_blank(self.first_existing_value(optics_row, ["acuity_cpd", "CPD", "CPD_corr", "cpd", "acuity"])),
                    "facet_normal_method": str(self.first_existing_value(normal_row, ["normal_method", "facet_normal_method"])),
                    "facet_normal_envelope_factor": self.numeric_or_blank(self.first_existing_value(normal_row, ["normal_envelope_factor", "facet_normal_envelope_factor"])),
                    "facet_normal_support_scale_um": self.numeric_or_blank(self.first_existing_value(normal_row, ["normal_support_scale_um", "facet_normal_support_scale_um"])),
                    "facet_normal_weight_cutoff_um": self.numeric_or_blank(self.first_existing_value(normal_row, ["normal_weight_cutoff_um", "facet_normal_weight_cutoff_um"])),
                    "facet_normal_support_face_count": self.numeric_or_blank(self.first_existing_value(normal_row, ["normal_support_face_count", "facet_normal_support_face_count"])),
                    "corn.proj.x": self.numeric_or_blank(self.first_existing_value(cp_row, ["corn.proj.x", "corn_proj_x", "projection_x"])),
                    "corn.proj.y": self.numeric_or_blank(self.first_existing_value(cp_row, ["corn.proj.y", "corn_proj_y", "projection_y"])),
                    "corn.proj.z": self.numeric_or_blank(self.first_existing_value(cp_row, ["corn.proj.z", "corn_proj_z", "projection_z"])),
                    "elevation": self.numeric_or_blank(self.first_existing_value(cp_row, ["elevation", "latitude", "lat"])),
                    "azimuth": self.numeric_or_blank(self.first_existing_value(cp_row, ["azimuth", "longitude", "lon", "long"])),
                    "projection_sphere_center_x": self.numeric_or_blank(self.first_existing_value(cp_row, ["projection_sphere_center_x", "sphere_center_x"])),
                    "projection_sphere_center_y": self.numeric_or_blank(self.first_existing_value(cp_row, ["projection_sphere_center_y", "sphere_center_y"])),
                    "projection_sphere_center_z": self.numeric_or_blank(self.first_existing_value(cp_row, ["projection_sphere_center_z", "sphere_center_z"])),
                    "projection_sphere_radius_um": self.numeric_or_blank(self.first_existing_value(cp_row, ["projection_sphere_radius_um", "sphere_radius_um"])),
                    "projection_center_mode": str(self.first_existing_value(cp_row, ["projection_center_mode", "center_mode"])),
                    "projection_center_source": str(self.first_existing_value(cp_row, ["projection_center_source"])),
                    "projection_sphere_size_cm": self.numeric_or_blank(self.first_existing_value(cp_row, ["projection_sphere_size_cm"])),
                }
                rows.append(out)
        return rows

    def build_eye_summary_rows(self, facet_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        summary_rows: List[Dict[str, Any]] = []
        for scope in self.active_export_eyes() + (["both_eyes"] if facet_rows else []):
            rows = facet_rows if scope == "both_eyes" else [r for r in facet_rows if r.get("eye") == scope]
            if not rows:
                continue
            info = self.config.get("eyes", {}).get(scope, {}) if scope in EYES else {}
            row = {
                "cv_id": self.config["dataset_identity"]["cv_id"],
                "eye_scope": scope,
                "n_facets": str(len(rows)),
                "is_real_eye": "FALSE" if info.get("mirrored") else ("TRUE" if scope in EYES else ""),
                "is_mirrored_eye": "TRUE" if info.get("mirrored") else ("FALSE" if scope in EYES else ""),
                "mirrored_from_eye": info.get("mirrored_from_eye", ""),
                "mirror_plane": info.get("mirror_plane", ""),
                "n_missing_coordinates": str(sum(1 for r in rows if not all(r.get(c) not in (None, "") for c in ["x_global", "y_global", "z_global"]))),
                "n_missing_optic_values": str(sum(1 for r in rows if not all(r.get(c) not in (None, "") for c in ["facet_size_um", "interfacet_angle_deg", "eye_parameter", "acuity_cpd"]))),
                "n_missing_CP_values": str(sum(1 for r in rows if not all(r.get(c) not in (None, "") for c in ["corn.proj.x", "corn.proj.y", "corn.proj.z", "elevation", "azimuth"]))),
            }
            for col, prefix in [("facet_size_um", "facet_size_um"), ("interfacet_angle_deg", "interfacet_angle_deg"), ("eye_parameter", "eye_parameter"), ("sampling_frequency_rad", "sampling_frequency_rad"), ("acuity_cpd", "acuity_cpd")]:
                st = self.stats_from_rows(rows, col)
                row[f"mean_{prefix}"] = st["mean"]
                row[f"median_{prefix}"] = st["median"]
                row[f"sd_{prefix}"] = st["sd"]
            elevation_range = self.range_from_rows(rows, "elevation")
            azimuth_interval = self.circular_interval_from_rows(rows, "azimuth")
            row["elevation_min"] = elevation_range["min"]
            row["elevation_max"] = elevation_range["max"]
            row["azimuth_start"] = azimuth_interval["start"]
            row["azimuth_end"] = azimuth_interval["end"]
            row["azimuth_span_deg"] = azimuth_interval["span_deg"]
            summary_rows.append(row)
        return summary_rows

    def write_export_tables(self) -> Dict[str, Any]:
        self.ensure_report_outputs_config()
        cv_id = self.config["dataset_identity"]["cv_id"]
        out = self.config["report_outputs"]
        created = []
        facet_rows = self.collect_analysis_ready_rows()
        fieldnames = [
            "cv_id", "eye", "facet_id", "data_origin", "mirrored", "mirrored_from_eye", "mirror_plane",
            "x_global", "y_global", "z_global", "norm.x_global", "norm.y_global", "norm.z_global",
            "facet_size_um", "interfacet_angle_deg", "eye_parameter", "sampling_frequency_rad", "sampling_lattice", "acuity_cpd",
            "facet_normal_method", "facet_normal_envelope_factor", "facet_normal_support_scale_um",
            "facet_normal_weight_cutoff_um", "facet_normal_support_face_count",
            "corn.proj.x", "corn.proj.y", "corn.proj.z", "elevation", "azimuth",
            "projection_sphere_center_x", "projection_sphere_center_y", "projection_sphere_center_z",
            "projection_sphere_radius_um", "projection_sphere_size_cm", "projection_center_mode", "projection_center_source",
        ]
        write_csv(self.analysis_folder / out["analysis_ready_table"]["file"], fieldnames, facet_rows)
        created.append(out["analysis_ready_table"]["file"])
        summary_rows = self.build_eye_summary_rows(facet_rows)
        summary_fields = [
            "cv_id", "eye_scope", "n_facets", "is_real_eye", "is_mirrored_eye", "mirrored_from_eye", "mirror_plane",
            "mean_facet_size_um", "median_facet_size_um", "sd_facet_size_um",
            "mean_interfacet_angle_deg", "median_interfacet_angle_deg", "sd_interfacet_angle_deg",
            "mean_eye_parameter", "median_eye_parameter", "sd_eye_parameter",
            "mean_sampling_frequency_rad", "median_sampling_frequency_rad", "sd_sampling_frequency_rad",
            "mean_acuity_cpd", "median_acuity_cpd", "sd_acuity_cpd",
            "elevation_min", "elevation_max", "azimuth_start", "azimuth_end", "azimuth_span_deg",
            "n_missing_coordinates", "n_missing_optic_values", "n_missing_CP_values",
        ]
        write_csv(self.analysis_folder / out["eye_summary"]["file"], summary_fields, summary_rows)
        write_csv(self.analysis_folder / out["specimen_summary"]["file"], summary_fields, [r for r in summary_rows if r.get("eye_scope") == "both_eyes"])
        created.extend([out["eye_summary"]["file"], out["specimen_summary"]["file"]])
        normal_defaults = self.config.get("parameters", {}).get("dataset_defaults", {})
        metadata = {
            "cv_id": cv_id,
            "created": now(),
            "created_with_cv3d_version": APP_VERSION,
            "export_type": "analysis_ready_handoff",
            "active_export_eyes": self.active_export_eyes(),
            "facet_rows": len(facet_rows),
            "summary_rows": len(summary_rows),
            "spatial_unit": "um",
            "eye_parameter_unit": "um*rad",
            "cp_sphere_user_unit": "cm",
            "facet_normal_default_method": normal_defaults.get("facet_normal_method", "envelope"),
            "facet_normal_default_envelope_factor": normal_defaults.get("facet_normal_envelope_factor", 1.25),
            "notes": "CV3D assumes mesh and point-cloud coordinates are in micrometres. acuity_cpd is a local anatomical estimate in cycles per degree.",
        }
        write_json(self.analysis_folder / out["metadata_json"]["file"], metadata)
        created.append(out["metadata_json"]["file"])
        manifest_rows = [
            {"file": out["analysis_ready_table"]["file"], "file_type": "csv", "step": "06_analysis_ready_export", "eye": "all", "description": "Facet-level analysis-ready table; one row per facet.", "created_by": APP_VERSION, "source_files": "05A/05B/05C per-eye outputs"},
            {"file": out["eye_summary"]["file"], "file_type": "csv", "step": "06_analysis_ready_export", "eye": "all", "description": "Eye-wise and combined specimen summary table.", "created_by": APP_VERSION, "source_files": out["analysis_ready_table"]["file"]},
            {"file": out["specimen_summary"]["file"], "file_type": "csv", "step": "06_analysis_ready_export", "eye": "both_eyes", "description": "Specimen-level combined summary row.", "created_by": APP_VERSION, "source_files": out["analysis_ready_table"]["file"]},
            {"file": out["metadata_json"]["file"], "file_type": "json", "step": "06_analysis_ready_export", "eye": "all", "description": "Export metadata and provenance.", "created_by": APP_VERSION, "source_files": "project config/status"},
        ]
        write_csv(self.analysis_folder / out["export_manifest"]["file"], ["file", "file_type", "step", "eye", "description", "created_by", "source_files"], manifest_rows)
        created.append(out["export_manifest"]["file"])
        timestamp = now()
        for key in ["analysis_ready_table", "eye_summary", "specimen_summary", "metadata_json", "export_manifest"]:
            out[key]["status"] = "complete"
            out[key]["last_created"] = timestamp
        return {"facet_rows": facet_rows, "summary_rows": summary_rows, "created_files": created}

    def generate_analysis_ready_export(self) -> None:
        if not self.config or not self.analysis_folder:
            return
        result = self.write_export_tables()
        rep = self.status["workflow_steps"].setdefault("06_report_export", {"label": STEP_LABELS["06_report_export"]})
        rep.setdefault("analysis_ready_export", {"state": "not_created", "symbol": "○", "last_run": None, "needs_rerun": False, "messages": []})
        rep["analysis_ready_export"].update({"state": "complete", "symbol": "✓", "last_run": now(), "needs_rerun": False, "messages": [f"Exported {len(result['facet_rows'])} facet rows."]})
        self.save_current_files()
        self.refresh_all()
        QMessageBox.information(self, "Analysis-ready export complete", f"Created {len(result['created_files'])} export files.\n\nFacet rows: {len(result['facet_rows'])}")

    def create_report_05c_rgl_snapshots(self, export_folder: Path) -> List[str]:
        messages: List[str] = []
        if not self.config or not self.analysis_folder:
            return messages
        rscript = configured_file_path(self.settings.get("rscript_executable", ""))
        runner = self.resolve_r_analysis_runner("r_step05c_qc_plot_script_path")
        if rscript is None or runner is None:
            messages.append("Fresh 05C rgl snapshots skipped because Rscript or the 05C QC runner is not configured.")
            return messages
        if not self.ensure_r_package_installed():
            messages.append("Fresh 05C rgl snapshots skipped because the CV3D R package is unavailable.")
            return messages

        cv_id = self.config["dataset_identity"]["cv_id"]
        report_facet_sphere_scale = self.default_facet_sphere_scale()
        report_facet_size_estimate = self.facet_size_estimate_for_plot()
        scopes = []
        active = [e for e in self.active_export_eyes() if self.config.get("eyes", {}).get(e, {}).get("present", False)]
        if len(active) > 1:
            scopes.append("both_eyes")
        scopes.extend(active)

        for scope in scopes:
            if scope == "both_eyes":
                eyes_to_plot = []
                for candidate in active:
                    files = self.config["eyes"].get(candidate, {}).get("files", {})
                    global_rel = files.get("global_coordinates_file")
                    projection_rel = files.get("corneal_projections_file")
                    if not global_rel or not projection_rel:
                        continue
                    global_path = self.analysis_folder / str(global_rel)
                    projection_path = self.analysis_folder / str(projection_rel)
                    if global_path.exists() and projection_path.exists():
                        eyes_to_plot.append({
                            "eye": candidate,
                            "input_global_coordinates": str(global_rel),
                            "input_global_coordinates_abs": str(global_path),
                            "input_corneal_projections": str(projection_rel),
                            "input_corneal_projections_abs": str(projection_path),
                        })
                if not eyes_to_plot:
                    continue
            else:
                files = self.config["eyes"].get(scope, {}).get("files", {})
                global_rel = files.get("global_coordinates_file")
                projection_rel = files.get("corneal_projections_file")
                if not global_rel or not projection_rel:
                    continue
                global_path = self.analysis_folder / str(global_rel)
                projection_path = self.analysis_folder / str(projection_rel)
                if not (global_path.exists() and projection_path.exists()):
                    continue
                eyes_to_plot = [{
                    "eye": scope,
                    "input_global_coordinates": str(global_rel),
                    "input_global_coordinates_abs": str(global_path),
                    "input_corneal_projections": str(projection_rel),
                    "input_corneal_projections_abs": str(projection_path),
                }]

            task_prefix = "06RGL"
            output_pngs = {axis: str(export_folder / f"06_{cv_id}_{scope}_05C_corneal_projection_{axis}.png") for axis in ["front", "back", "left", "right", "top", "bottom"]}
            output_pngs["view_angles"] = str(export_folder / f"06_{cv_id}_{scope}_05C_corneal_projection_view_angles.png")
            output_pngs["rgl_3d"] = str(export_folder / f"06_{cv_id}_{scope}_05C_corneal_projection_3d_qc.png")
            task_rel = eye_json_rel_path(active[0] if active else "eye1", f"{task_prefix}_{cv_id}_{scope}_R_task.json")
            status_rel = eye_json_rel_path(active[0] if active else "eye1", f"{task_prefix}_{cv_id}_{scope}_R_status.json")
            stdout_rel = eye_log_rel_path(active[0] if active else "eye1", f"{task_prefix}_{cv_id}_{scope}_R_stdout.log")
            stderr_rel = eye_log_rel_path(active[0] if active else "eye1", f"{task_prefix}_{cv_id}_{scope}_R_stderr.log")
            task = {
                "task_type": "05C_qc_plot",
                "task_prefix": task_prefix,
                "plot_kind": "corneal_projection_qc",
                "cv_id": cv_id,
                "eye": scope,
                "analysis_folder": str(self.analysis_folder),
                "input_eyes": eyes_to_plot,
                "output_plot_pngs_abs": output_pngs,
                "output_plot_png_abs": output_pngs["rgl_3d"],
                "output_plot_png": str(Path(output_pngs["rgl_3d"]).name),
                "open_rgl_window": False,
                "make_rgl_snapshot": True,
                "facet_sphere_scale": report_facet_sphere_scale,
                "facet_size_estimate": report_facet_size_estimate,
                "status_file": status_rel,
                "status_file_abs": str(self.analysis_folder / status_rel),
                "stdout_file": stdout_rel,
                "stdout_file_abs": str(self.analysis_folder / stdout_rel),
                "stderr_file": stderr_rel,
                "stderr_file_abs": str(self.analysis_folder / stderr_rel),
                "notes": "Created by CV3D Results/Export for fresh 05C QC rgl snapshots.",
            }
            task_path = self.analysis_folder / task_rel
            write_json(task_path, task)
            (self.analysis_folder / stdout_rel).parent.mkdir(parents=True, exist_ok=True)
            (self.analysis_folder / stderr_rel).parent.mkdir(parents=True, exist_ok=True)
            cmd = [str(rscript), str(runner), relative_task_argument(task_path, self.analysis_folder)]
            try:
                with (self.analysis_folder / stdout_rel).open("w", encoding="utf-8", errors="replace") as out, (self.analysis_folder / stderr_rel).open("w", encoding="utf-8", errors="replace") as err:
                    result = self.run_blocking_process(cmd, cwd=str(self.analysis_folder), stdout=out, stderr=err)
                if result.returncode == 0 and Path(output_pngs["rgl_3d"]).exists():
                    messages.append(f"Fresh 05C rgl snapshot created for {scope}: {Path(output_pngs['rgl_3d']).name}")
                else:
                    messages.append(f"Fresh 05C rgl snapshot failed for {scope}. See {stderr_rel}.")
            except Exception as e:
                messages.append(f"Fresh 05C rgl snapshot failed for {scope}: {e}")
        return messages

    def generate_qc_pdf_report(self) -> None:
        if not self.config or not self.analysis_folder:
            return
        self.ensure_report_outputs_config()
        self.write_export_tables()
        out = self.config["report_outputs"]
        cv_id = self.config["dataset_identity"]["cv_id"]
        export_folder = self.analysis_folder / out["export_folder"]["folder"]
        export_folder.mkdir(parents=True, exist_ok=True)
        pdf_path = self.analysis_folder / out["qc_pdf_report"]["file"]
        html_path = self.analysis_folder / out["html_report"]["file"]
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.parent.mkdir(parents=True, exist_ok=True)

        facet_rows = self.collect_analysis_ready_rows()
        summary_rows = self.build_eye_summary_rows(facet_rows)
        freshness_messages = []
        if getattr(self, "report_create_fresh_rgl_snapshots", None) is not None and self.report_create_fresh_rgl_snapshots.isChecked():
            freshness_messages = self.create_report_05c_rgl_snapshots(export_folder)

        def to_float(row, key):
            try:
                v = float(row.get(key, ""))
                if v == v:
                    return v
            except Exception:
                pass
            return None

        def fmt(value, digits=4):
            if value in (None, ""):
                return ""
            try:
                v = float(value)
                if v != v:
                    return ""
                return f"{v:.{digits}g}"
            except Exception:
                return str(value)

        def pdf_text(text_value):
            safe = str(text_value)
            replacements = {
                "✓": "OK", "✔": "OK", "✗": "not OK", "×": "x",
                "⇄": "derived", "→": "->", "←": "<-", "–": "-", "—": "-",
                "µ": "u", "μ": "u", "°": " deg", "≤": "<=", "≥": ">=",
                "“": '"', "”": '"', "‘": "'", "’": "'",
            }
            for a, b in replacements.items():
                safe = safe.replace(a, b)
            # Built-in PDF Helvetica is Latin-1 here; drop unsupported glyphs before encoding.
            return "".join(ch if ord(ch) < 256 else "" for ch in safe)

        def pdf_escape(text_value):
            safe = pdf_text(text_value)
            return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        def text_cmd(x, y, text_value, size=10, font="F1"):
            return f"BT /{font} {size} Tf {x:.2f} {y:.2f} Td ({pdf_escape(text_value)}) Tj ET"

        def text_rotated_cmd(x, y, text_value, angle_deg=22.5, size=7, font="F2"):
            import math
            a = math.radians(angle_deg)
            c = math.cos(a)
            s = math.sin(a)
            return f"BT /{font} {size} Tf {c:.5f} {s:.5f} {-s:.5f} {c:.5f} {x:.2f} {y:.2f} Tm ({pdf_escape(text_value)}) Tj ET"

        def line_cmd(x1, y1, x2, y2):
            return f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S"

        def rect_cmd(x, y, w, h, fill=False):
            return f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re {'f' if fill else 'S'}"

        def circle_cmd(x, y, r, fill=True):
            k = 0.55228475 * r
            op = "f" if fill else "S"
            return (
                f"{x + r:.2f} {y:.2f} m "
                f"{x + r:.2f} {y + k:.2f} {x + k:.2f} {y + r:.2f} {x:.2f} {y + r:.2f} c "
                f"{x - k:.2f} {y + r:.2f} {x - r:.2f} {y + k:.2f} {x - r:.2f} {y:.2f} c "
                f"{x - r:.2f} {y - k:.2f} {x - k:.2f} {y - r:.2f} {x:.2f} {y - r:.2f} c "
                f"{x + k:.2f} {y - r:.2f} {x + r:.2f} {y - k:.2f} {x + r:.2f} {y:.2f} c {op}"
            )

        def tri_cmd(x, y, r, fill=True):
            pts = [(x, y + r), (x - 0.866*r, y - 0.5*r), (x + 0.866*r, y - 0.5*r)]
            op = 'f' if fill else 'S'
            return f"{pts[0][0]:.2f} {pts[0][1]:.2f} m {pts[1][0]:.2f} {pts[1][1]:.2f} l {pts[2][0]:.2f} {pts[2][1]:.2f} l h {op}"

        def rgb_for_value(v, vmin, vmax):
            anchors = [
                (68/255.0, 1/255.0, 84/255.0),
                (59/255.0, 82/255.0, 139/255.0),
                (33/255.0, 145/255.0, 140/255.0),
                (94/255.0, 201/255.0, 98/255.0),
                (253/255.0, 231/255.0, 37/255.0),
            ]
            if v is None:
                return (0.45, 0.45, 0.45)
            if vmax <= vmin:
                t = 0.5
            else:
                t = max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))
            pos = t * (len(anchors) - 1)
            i = int(pos)
            if i >= len(anchors) - 1:
                return anchors[-1]
            frac = pos - i
            a = anchors[i]
            b = anchors[i+1]
            return tuple(a[j] * (1-frac) + b[j] * frac for j in range(3))

        def shape_for_eye(eye):
            return 'triangle' if str(eye) == 'eye2' else 'circle'

        def draw_marker(cmds, x, y, size, shape, rgb):
            cmds.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg")
            if shape == 'triangle':
                cmds.append(tri_cmd(x, y, size, True))
            else:
                cmds.append(circle_cmd(x, y, size, True))
            cmds.append("0 0 0 rg")

        def new_page(title=None, subtitle=None):
            cmds = ["0 0 0 RG", "0 0 0 rg", "1 w"]
            if title:
                cmds.append(text_cmd(42, 805, title, 16, "F2"))
                if subtitle:
                    cmds.append(text_cmd(42, 789, subtitle, 9, "F1"))
                    cmds.append(line_cmd(42, 782, 553, 782))
                else:
                    cmds.append(line_cmd(42, 790, 553, 790))
            return cmds

        def wrap_pdf_line(line, max_chars=98):
            line = pdf_text(line)
            if len(line) <= max_chars:
                return [line]
            out = []
            rest = line
            while len(rest) > max_chars:
                cut = max(rest.rfind("/", 0, max_chars), rest.rfind("\\", 0, max_chars), rest.rfind(" ", 0, max_chars))
                if cut < max_chars * 0.45:
                    cut = max_chars
                out.append(rest[:cut].rstrip())
                rest = rest[cut:].lstrip(" /\\")
                if out and ("Final export folder:" in out[-1] or "folder:" in out[-1].lower()):
                    max_chars = 92
            if rest:
                out.append(rest)
            return out

        def write_lines(cmds, lines, x=45, y=760, size=10, leading=15, max_lines=42, max_chars=98):
            yy = y
            written = 0
            for line in lines:
                for part in wrap_pdf_line(line, max_chars=max_chars):
                    if written >= max_lines:
                        return yy
                    cmds.append(text_cmd(x, yy, part, size))
                    yy -= leading
                    written += 1
            return yy

        def table_page(title, rows, cols, widths=None, max_rows=28):
            cmds = new_page(title)
            x0, y0 = 42, 748
            row_h = 18
            header_h = 58
            if widths is None:
                widths = [511 / max(1, len(cols))] * len(cols)
            total_w = sum(widths)
            cmds.append("0.93 0.93 0.93 rg")
            cmds.append(rect_cmd(x0, y0 - header_h + 6, total_w, header_h, fill=True))
            cmds.append("0 0 0 rg")
            x = x0
            for i, col in enumerate(cols):
                # Rotate long column names to avoid overlap in narrow PDF tables.
                cmds.append(text_rotated_cmd(x + 5, y0 - header_h + 12, col, angle_deg=22.5, size=6.5, font="F2"))
                x += widths[i]
            y = y0 - header_h - 4
            for r in rows[:max_rows]:
                x = x0
                for i, col in enumerate(cols):
                    val = r.get(col, "")
                    if col not in {"eye_scope", "eye", "mirrored_from_eye", "mirror_plane", "created_by", "file", "description"}:
                        val = fmt(val, 4)
                    txt = pdf_text(val)
                    if len(txt) > max(10, int(widths[i] / 5)):
                        txt = txt[:max(7, int(widths[i]/5)-3)] + "..."
                    cmds.append(text_cmd(x + 2, y - 8, txt, 7))
                    x += widths[i]
                cmds.append("0.86 0.86 0.86 RG")
                cmds.append(line_cmd(x0, y - row_h + 4, x0 + total_w, y - row_h + 4))
                cmds.append("0 0 0 RG")
                y -= row_h
                if y < 55:
                    break
            if len(rows) > max_rows:
                cmds.append(text_cmd(x0, 38, f"Table truncated in PDF; full table is exported as CSV. Rows shown: {max_rows} of {len(rows)}", 8))
            return cmds

        def plot_bounds(xvals, yvals, pad=0.08, force_equal=False):
            if not xvals or not yvals:
                return (0, 1, 0, 1)
            xmin, xmax = min(xvals), max(xvals)
            ymin, ymax = min(yvals), max(yvals)
            xr = xmax - xmin
            yr = ymax - ymin
            if xr <= 0: xr = 1.0
            if yr <= 0: yr = 1.0
            if force_equal:
                rr = max(xr, yr)
                cx = (xmin + xmax) / 2.0
                cy = (ymin + ymax) / 2.0
                xmin, xmax = cx - rr / 2.0, cx + rr / 2.0
                ymin, ymax = cy - rr / 2.0, cy + rr / 2.0
                xr = yr = rr
            return (xmin - xr*pad, xmax + xr*pad, ymin - yr*pad, ymax + yr*pad)

        def fit_equal_units_area(x0, y0, w, h, xbounds, ybounds):
            xr = max(abs(xbounds[1] - xbounds[0]), 1e-9)
            yr = max(abs(ybounds[1] - ybounds[0]), 1e-9)
            desired = xr / yr
            available = w / h
            if available > desired:
                ww = h * desired
                return (x0 + (w - ww) / 2.0, y0, ww, h)
            hh = w / desired
            return (x0, y0 + (h - hh) / 2.0, w, hh)

        def square_plot_area(x0, y0, w, h):
            s = min(w, h)
            return (x0 + (w - s) / 2.0, y0 + (h - s) / 2.0, s, s)

        def view_angle_plot_area(x0, y0, w, h):
            # Azimuth range is twice the elevation range, so equal degree units need a 2:1 panel.
            desired = 2.0
            available = w / h
            if available > desired:
                ww = h * desired
                return (x0 + (w - ww) / 2.0, y0, ww, h)
            hh = w / desired
            return (x0, y0 + (h - hh) / 2.0, w, hh)

        def draw_axes_frame(cmds, x0, y0, w, h, xlabel='', ylabel='', xticks=None, yticks=None, xbounds=None, ybounds=None, grid=True):
            cmds.append("0 0 0 RG")
            cmds.append(rect_cmd(x0, y0, w, h, fill=False))
            if xticks is None and xbounds is not None:
                xticks = [xbounds[0] + i*(xbounds[1]-xbounds[0])/4 for i in range(5)]
            if yticks is None and ybounds is not None:
                yticks = [ybounds[0] + i*(ybounds[1]-ybounds[0])/4 for i in range(5)]
            if grid and xbounds is not None:
                for v in xticks[1:-1]:
                    xx = x0 + (v - xbounds[0]) / (xbounds[1] - xbounds[0]) * w
                    cmds.append("0.88 0.88 0.88 RG")
                    cmds.append(line_cmd(xx, y0, xx, y0 + h))
                for v in yticks[1:-1]:
                    yy = y0 + (v - ybounds[0]) / (ybounds[1] - ybounds[0]) * h
                    cmds.append("0.88 0.88 0.88 RG")
                    cmds.append(line_cmd(x0, yy, x0 + w, yy))
                cmds.append("0 0 0 RG")
            if xbounds is not None:
                for v in xticks:
                    xx = x0 + (v - xbounds[0]) / (xbounds[1] - xbounds[0]) * w
                    cmds.append(text_cmd(xx - 10, y0 - 12, fmt(v, 3), 7))
            if ybounds is not None:
                for v in yticks:
                    yy = y0 + (v - ybounds[0]) / (ybounds[1] - ybounds[0]) * h
                    cmds.append(text_cmd(x0 - 28, yy - 3, fmt(v, 3), 7))
            if xlabel:
                cmds.append(text_cmd(x0 + w/2 - max(20, len(xlabel)*1.8), y0 - 26, xlabel, 8))
            if ylabel:
                cmds.append(text_cmd(x0 - 34, y0 + h/2, ylabel, 8))

        def draw_colorbar(cmds, x, y, h, vmin, vmax, label):
            steps = 40
            for i in range(steps):
                rgb = rgb_for_value(vmin + (i / max(1, steps-1))*(vmax-vmin), vmin, vmax)
                cmds.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg")
                cmds.append(rect_cmd(x, y + i*(h/steps), 10, h/steps + 0.3, fill=True))
            cmds.append("0 0 0 rg")
            cmds.append(rect_cmd(x, y, 10, h, fill=False))
            cmds.append(text_cmd(x + 14, y + h - 2, fmt(vmax, 4), 7))
            cmds.append(text_cmd(x + 14, y - 2, fmt(vmin, 4), 7))
            cmds.append(text_cmd(x - 2, y + h + 10, label, 8))

        def choose_projection_cols(rows, suffix):
            candidates = {
                'xy': [f'x{suffix}', f'y{suffix}'],
                'xz': [f'x{suffix}', f'z{suffix}'],
                'yz': [f'y{suffix}', f'z{suffix}'],
            }
            best = ['x'+suffix, 'y'+suffix]
            best_score = -1.0
            for cols in candidates.values():
                vals1, vals2 = [], []
                for row in rows:
                    v1 = to_float(row, cols[0])
                    v2 = to_float(row, cols[1])
                    if v1 is not None and v2 is not None:
                        vals1.append(v1); vals2.append(v2)
                if len(vals1) < 2:
                    continue
                score = (max(vals1)-min(vals1)) * (max(vals2)-min(vals2))
                if score > best_score:
                    best_score = score
                    best = cols
            return best

        def load_05b_rows(scope):
            rows = []
            eyes = self.active_export_eyes() if scope == 'both_eyes' else [scope]
            for eye in eyes:
                files = self.config.get('eyes', {}).get(eye, {}).get('files', {})
                rel = files.get('global_aligned_pointcloud_file')
                if not rel:
                    continue
                for row in self.read_csv_rows_rel(rel):
                    rr = dict(row)
                    rr['source_eye'] = eye
                    rows.append(rr)
            return rows

        def draw_pointcloud_panel(cmds, panel_title, rows, coord_suffix, x0, y0, w, h):
            if not rows:
                cmds.append(text_cmd(x0, y0 + h/2, f"{panel_title}: no data", 10))
                return
            facets, landmarks = [], []
            for row in rows:
                pt = str(row.get('point_type', row.get('type', 'facet'))).strip().lower()
                if pt in ['lm', 'landmark', 'head_landmark']:
                    landmarks.append(row)
                else:
                    facets.append(row)
            proj_cols = choose_projection_cols(rows, coord_suffix)
            xkey, ykey = proj_cols
            xs, ys, vals, facet_pts, landmark_pts = [], [], [], [], []
            for row in facets:
                xv = to_float(row, xkey); yv = to_float(row, ykey)
                if xv is None or yv is None:
                    continue
                sv = to_float(row, 'facet_size_smoothed')
                facet_pts.append((xv, yv, sv, row.get('source_eye', 'eye1')))
                xs.append(xv); ys.append(yv)
                if sv is not None: vals.append(sv)
            for row in landmarks:
                xv = to_float(row, xkey); yv = to_float(row, ykey)
                if xv is None or yv is None:
                    continue
                landmark_pts.append((xv, yv, str(row.get('landmark', row.get('point_id', 'LM')))))
                xs.append(xv); ys.append(yv)
            if not xs or not ys:
                cmds.append(text_cmd(x0, y0 + h/2, f"{panel_title}: no finite coordinates", 10))
                return
            xmin, xmax, ymin, ymax = plot_bounds(xs, ys, force_equal=True)
            px0, py0, pw, ph = fit_equal_units_area(x0, y0, w, h, (xmin, xmax), (ymin, ymax))
            draw_axes_frame(cmds, px0, py0, pw, ph, xlabel=xkey, ylabel=ykey, xbounds=(xmin, xmax), ybounds=(ymin, ymax), grid=True)
            cmds.append(text_cmd(x0, y0 + h + 10, panel_title, 10, 'F2'))
            vmin, vmax = (min(vals), max(vals)) if vals else (0.0, 1.0)
            if vmax <= vmin: vmax = vmin + 1.0
            for xv, yv, sv, eye in facet_pts:
                px = px0 + (xv - xmin) / (xmax - xmin) * pw
                py = py0 + (yv - ymin) / (ymax - ymin) * ph
                draw_marker(cmds, px, py, 1.6 if shape_for_eye(eye) == 'triangle' else 1.35, shape_for_eye(eye), rgb_for_value(sv, vmin, vmax))
            cmds.append("0 0 1 rg")
            for xv, yv, lab in landmark_pts:
                px = px0 + (xv - xmin) / (xmax - xmin) * pw
                py = py0 + (yv - ymin) / (ymax - ymin) * ph
                cmds.append(circle_cmd(px, py, 2.2, True))
                cmds.append(text_cmd(px + 3, py + 2, lab, 7))
            cmds.append("0 0 0 rg")
            draw_colorbar(cmds, x0 + w + 8, y0 + 20, h - 40, vmin, vmax, 'Facet size')

        def draw_hist_panel(cmds, rows1, rows2, key, title, x0, y0, w, h):
            vals1 = [to_float(r, key) for r in rows1]; vals1 = [v for v in vals1 if v is not None]
            vals2 = [to_float(r, key) for r in rows2]; vals2 = [v for v in vals2 if v is not None]
            vals = vals1 + vals2
            if not vals:
                cmds.append(text_cmd(x0, y0 + h/2, f"{title}: no data", 9))
                return
            vmin, vmax = min(vals), max(vals)
            if vmax <= vmin: vmax = vmin + 1.0
            bins = 20
            step = (vmax - vmin) / bins
            c1 = [0]*bins; c2 = [0]*bins
            for v in vals1:
                c1[min(bins-1, max(0, int((v - vmin) / step)))] += 1
            for v in vals2:
                c2[min(bins-1, max(0, int((v - vmin) / step)))] += 1
            ymax = max(max(c1 or [1]), max(c2 or [1]))
            draw_axes_frame(cmds, x0, y0, w, h, xlabel=key, ylabel='count', xbounds=(vmin, vmax), ybounds=(0, ymax), grid=True)
            cmds.append(text_cmd(x0, y0 + h + 10, title, 9, 'F2'))
            bw = w / bins
            for i in range(bins):
                x = x0 + i*bw
                h1 = (c1[i]/ymax) * (h - 2) if ymax > 0 else 0
                h2 = (c2[i]/ymax) * (h - 2) if ymax > 0 else 0
                cmds.append('0.55 0.55 0.55 rg'); cmds.append(rect_cmd(x + 0.5, y0, bw*0.45, h1, fill=True))
                cmds.append('0.78 0.78 0.78 rg'); cmds.append(rect_cmd(x + bw*0.5, y0, bw*0.45, h2, fill=True))
            cmds.append('0 0 0 rg')

        def optic_barplots_page():
            cmds = new_page('05A optic-parameter summaries', 'Eye-wise means and counts from analysis-ready export tables')
            eye_rows = [r for r in summary_rows if r.get('eye_scope') in EYES]
            metrics = [('n_facets', 'Facet count'), ('mean_facet_size_um', 'Mean facet size (µm)'), ('mean_interfacet_angle_deg', 'Mean interfacet angle (deg)'), ('mean_acuity_cpd', 'Mean acuity (cpd)'), ('mean_eye_parameter', 'Mean eye parameter')]
            left, plot_w, top, plot_h, gap = 68, 420, 735, 86, 22
            labels = [r.get('eye_scope', '') for r in eye_rows]
            for mi, (col, label) in enumerate(metrics):
                y_base = top - mi * (plot_h + gap) - plot_h
                vals = []
                for r in eye_rows:
                    v = to_float(r, col)
                    vals.append(0 if v is None else v)
                max_v = max(vals) if vals else 1
                if max_v <= 0: max_v = 1
                cmds.append(text_cmd(left, y_base + plot_h + 8, label, 10, 'F2'))
                draw_axes_frame(cmds, left, y_base, plot_w, plot_h, xlabel='', ylabel='', xbounds=(0, max(1, len(vals))), ybounds=(0, max_v), grid=True)
                n = max(1, len(vals))
                band = plot_w / n
                for i, v in enumerate(vals):
                    x = left + i*band + band*0.22
                    bar_w = band*0.48
                    hh = (v/max_v) * (plot_h - 8)
                    rgb = (0.35,0.35,0.35) if i % 2 == 0 else (0.62,0.62,0.62)
                    cmds.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg")
                    cmds.append(rect_cmd(x, y_base, bar_w, hh, fill=True))
                    cmds.append('0 0 0 rg')
                    cmds.append(text_cmd(x, y_base - 12, labels[i] if i < len(labels) else f'e{i+1}', 7))
                    cmds.append(text_cmd(x, y_base + hh + 3, fmt(v, 4), 7))
            return cmds

        def optic_histograms_page():
            cmds = new_page('05A optic-parameter distributions', 'Eye1 and eye2 shown as paired histograms')
            rows1 = [r for r in facet_rows if r.get('eye') == 'eye1']
            rows2 = [r for r in facet_rows if r.get('eye') == 'eye2']
            panels = [('facet_size_um', 'Facet size'), ('interfacet_angle_deg', 'Interfacet angle'), ('acuity_cpd', 'Acuity (cpd)'), ('eye_parameter', 'Eye parameter')]
            positions = [(50, 450), (315, 450), (50, 150), (315, 150)]
            for (key, title), (x, y) in zip(panels, positions):
                draw_hist_panel(cmds, rows1, rows2, key, title, x, y, 220, 180)
            cmds.append('0.55 0.55 0.55 rg'); cmds.append(rect_cmd(50, 110, 10, 10, fill=True)); cmds.append('0 0 0 rg'); cmds.append(text_cmd(65, 110, 'eye1', 8))
            cmds.append('0.78 0.78 0.78 rg'); cmds.append(rect_cmd(105, 110, 10, 10, fill=True)); cmds.append('0 0 0 rg'); cmds.append(text_cmd(120, 110, 'eye2', 8))
            return cmds

        def cp_view_points(rows, view_name):
            view_defs = {
                'front': ('corn.proj.x', 'corn.proj.z', 'x_global', 'z_global', 1, 1, 'x (µm)', 'z (µm)'),
                'back': ('corn.proj.x', 'corn.proj.z', 'x_global', 'z_global', -1, 1, '-x (µm)', 'z (µm)'),
                'left': ('corn.proj.y', 'corn.proj.z', 'y_global', 'z_global', 1, 1, 'y (µm)', 'z (µm)'),
                'right': ('corn.proj.y', 'corn.proj.z', 'y_global', 'z_global', -1, 1, '-y (µm)', 'z (µm)'),
                'top': ('corn.proj.x', 'corn.proj.y', 'x_global', 'y_global', 1, 1, 'x (µm)', 'y (µm)'),
                'bottom': ('corn.proj.x', 'corn.proj.y', 'x_global', 'y_global', 1, -1, 'x (µm)', '-y (µm)'),
            }
            pxk, pyk, fxk, fyk, sx, sy, xlab, ylab = view_defs[view_name]
            pts, xvals, yvals = [], [], []
            for row in rows:
                px = to_float(row, pxk); py = to_float(row, pyk); fx = to_float(row, fxk); fy = to_float(row, fyk)
                if px is not None and py is not None and fx is not None and fy is not None:
                    item = {'px': px*sx, 'py': py*sy, 'fx': fx*sx, 'fy': fy*sy, 'val': to_float(row, 'acuity_cpd'), 'eye': row.get('eye','eye1'), 'size': to_float(row,'facet_size_um')}
                    pts.append(item)
                    xvals.extend([item['px'], item['fx']]); yvals.extend([item['py'], item['fy']])
            return pts, xvals, yvals, xlab, ylab

        def draw_cp_projection_panel(cmds, panel_title, rows, view_name, x0, y0, w, h, color_key='acuity_cpd'):
            pts, xvals, yvals, xlab, ylab = cp_view_points(rows, view_name)
            if not pts:
                cmds.append(text_cmd(x0, y0 + h/2, f"{panel_title}: no data", 9))
                return
            xmin, xmax, ymin, ymax = plot_bounds(xvals, yvals, force_equal=True)
            px0, py0, pw, ph = square_plot_area(x0, y0, w, h)
            draw_axes_frame(cmds, px0, py0, pw, ph, xlabel=xlab, ylabel=ylab, xbounds=(xmin,xmax), ybounds=(ymin,ymax), grid=True)
            cmds.append(text_cmd(x0, y0 + h + 10, panel_title, 9, 'F2'))
            vv = [to_float(r, color_key) for r in rows if to_float(r, color_key) is not None]
            vmin, vmax = (min(vv), max(vv)) if vv else (0.0, 1.0)
            if vmax <= vmin: vmax = vmin + 1.0
            for item in pts:
                fx = px0 + (item['fx'] - xmin) / (xmax - xmin) * pw
                fy = py0 + (item['fy'] - ymin) / (ymax - ymin) * ph
                px = px0 + (item['px'] - xmin) / (xmax - xmin) * pw
                py = py0 + (item['py'] - ymin) / (ymax - ymin) * ph
                val = item['val'] if color_key == 'acuity_cpd' else item.get('size')
                rgb = rgb_for_value(val, vmin, vmax)
                draw_marker(cmds, fx, fy, 0.9 if shape_for_eye(item['eye']) == 'triangle' else 0.8, shape_for_eye(item['eye']), rgb)
                draw_marker(cmds, px, py, 1.4 if shape_for_eye(item['eye']) == 'triangle' else 1.2, shape_for_eye(item['eye']), rgb)
            draw_colorbar(cmds, x0 + w + 8, y0 + 16, h - 32, vmin, vmax, color_key)

        def draw_view_angle_panel(cmds, panel_title, rows, x0, y0, w, h, color_key='acuity_cpd'):
            plot_rows = []
            for row in rows:
                azimuth = to_float(row, 'azimuth'); elevation = to_float(row, 'elevation')
                if azimuth is not None and elevation is not None:
                    plot_rows.append((azimuth, elevation, row))
            if not plot_rows:
                cmds.append(text_cmd(x0, y0 + h/2, f"{panel_title}: no data", 9))
                return
            xmin, xmax, ymin, ymax = -180, 180, -90, 90
            px0, py0, pw, ph = view_angle_plot_area(x0, y0, w, h)
            draw_axes_frame(cmds, px0, py0, pw, ph, xlabel='azimuth (deg)', ylabel='elevation (deg)', xbounds=(xmin,xmax), ybounds=(ymin,ymax), xticks=[-180,-90,0,90,180], yticks=[-90,-45,0,45,90], grid=True)
            cmds.append(text_cmd(x0, y0 + h + 10, panel_title, 9, 'F2'))
            vals = [to_float(r, color_key) for _,_,r in plot_rows if to_float(r, color_key) is not None]
            vmin, vmax = (min(vals), max(vals)) if vals else (0.0, 1.0)
            if vmax <= vmin: vmax = vmin + 1.0
            for azimuth, elevation, row in plot_rows[::max(1, len(plot_rows)//2500)]:
                px = px0 + (azimuth - xmin)/(xmax-xmin) * pw
                py = py0 + (elevation - ymin)/(ymax-ymin) * ph
                val = to_float(row, color_key)
                draw_marker(cmds, px, py, 1.4 if shape_for_eye(row.get('eye')) == 'triangle' else 1.2, shape_for_eye(row.get('eye')), rgb_for_value(val, vmin, vmax))
            draw_colorbar(cmds, x0 + w + 8, y0 + 16, h - 32, vmin, vmax, color_key)

        def cp_scope_page(scope_rows, scope_label):
            cmds = new_page(f'05C corneal-projection QC: {scope_label}', '2D projection panels with equal axis units')
            draw_view_angle_panel(cmds, f'{scope_label}: elevation / azimuth coloured by acuity', scope_rows, 42, 470, 250, 150, 'acuity_cpd')
            draw_cp_projection_panel(cmds, f'{scope_label}: front view', scope_rows, 'front', 330, 480, 175, 175, 'acuity_cpd')
            draw_cp_projection_panel(cmds, f'{scope_label}: side view', scope_rows, 'left', 70, 140, 175, 175, 'acuity_cpd')
            draw_cp_projection_panel(cmds, f'{scope_label}: top view', scope_rows, 'top', 330, 140, 175, 175, 'acuity_cpd')
            return cmds

        def view_angle_metric_maps_page():
            cmds = new_page('Additional optic parameter maps', 'Combined-eye elevation/azimuth maps coloured by analysis-ready metrics')
            metrics = [('facet_size_um', 'Facet size'), ('interfacet_angle_deg', 'Interfacet angle'), ('acuity_cpd', 'Acuity (cpd)'), ('eye_parameter', 'Eye parameter')]
            positions = [(42, 495), (305, 495), (42, 170), (305, 170)]
            for (key, title), (x, y) in zip(metrics, positions):
                draw_view_angle_panel(cmds, title, facet_rows, x, y, 220, 130, key)
            return cmds

        def cp_report_pages():
            pages = []
            if facet_rows:
                pages.append(cp_scope_page(facet_rows, 'both eyes'))
            for eye in self.active_export_eyes():
                eye_rows = [r for r in facet_rows if r.get('eye') == eye]
                if eye_rows:
                    pages.append(cp_scope_page(eye_rows, eye))
            return pages

        def pointcloud_report_pages():
            pages = []
            combined_glb = load_05b_rows('both_eyes')
            if combined_glb:
                cmds = new_page('05B coordinate QC: both eyes', 'Global aligned point cloud with equal axis units')
                draw_pointcloud_panel(cmds, 'Global alignment QC', combined_glb, '_global', 92, 250, 360, 360)
                pages.append(cmds)
            eye_cmds = new_page('05B coordinate QC: eye-wise', 'Global aligned point clouds plotted separately')
            positions = [(70, 420), (335, 420), (70, 110), (335, 110)]
            labels = [(f'{eye}: global alignment', load_05b_rows(eye), '_global') for eye in self.active_export_eyes()]
            for (lab, rows, suffix), (x, y) in zip(labels[:4], positions):
                draw_pointcloud_panel(eye_cmds, lab, rows, suffix, x, y, 200, 230)
            if labels:
                pages.append(eye_cmds)
            return pages

        def image_cmd(path, x, y, w, h):
            # Fit raster images into the requested PDF box without changing
            # their aspect ratio. The previous square stretch distorted the
            # 05C rgl snapshots because their native window is rectangular.
            img = QImage(str(path))
            if not img.isNull() and img.width() > 0 and img.height() > 0:
                scale = min(float(w) / float(img.width()), float(h) / float(img.height()))
                fit_w = float(img.width()) * scale
                fit_h = float(img.height()) * scale
                x = float(x) + (float(w) - fit_w) / 2.0
                y = float(y) + (float(h) - fit_h) / 2.0
                w, h = fit_w, fit_h
            return f"__CV3D_IMAGE__|{str(path).replace('|', '_')}|{x:.2f}|{y:.2f}|{w:.2f}|{h:.2f}"

        def rgl_snapshot_pages():
            pages = []
            scopes = []
            if len(self.active_export_eyes()) > 1:
                scopes.append('both_eyes')
            scopes.extend(self.active_export_eyes())
            existing = []
            for scope in scopes:
                p = export_folder / f"06_{cv_id}_{scope}_05C_corneal_projection_3d_qc.png"
                if p.exists():
                    existing.append((scope, p))
            if not existing:
                return pages
            cmds = new_page('05C rgl snapshots', 'Perspective 3D QC snapshots in the global coordinate system')

            # Use the available page area more efficiently. With two eyes the
            # combined view gets a larger top panel and the individual eyes
            # sit side-by-side below it. All images preserve their native
            # aspect ratio via image_cmd().
            if len(existing) >= 3:
                layout = [
                    (existing[0], 137, 445, 320, 250),
                    (existing[1], 42, 155, 240, 190),
                    (existing[2], 313, 155, 240, 190),
                ]
            elif len(existing) == 2:
                layout = [
                    (existing[0], 42, 300, 240, 200),
                    (existing[1], 313, 300, 240, 200),
                ]
            else:
                layout = [
                    (existing[0], 97, 300, 400, 310),
                ]

            for (scope, p), x, y, w, h in layout:
                cmds.append(text_cmd(x, y + h + 12, scope, 10, 'F2'))
                cmds.append(image_cmd(p, x, y, w, h))
            pages.append(cmds)
            return pages

        def qimage_rgb_bytes(path):
            img = QImage(str(path))
            if img.isNull():
                return None
            img = img.convertToFormat(QImage.Format.Format_RGB888)
            width = img.width()
            height = img.height()
            ptr = img.constBits()
            try:
                raw = ptr.tobytes()
            except AttributeError:
                raw = bytes(ptr)
            bpl = img.bytesPerLine()
            rows = []
            for yy in range(height):
                rows.append(raw[yy*bpl:yy*bpl + width*3])
            return width, height, b''.join(rows)

        def build_pdf(path, pages):
            width, height = 595, 842
            objects = []
            def add_obj(data):
                objects.append(data)
                return len(objects)
            catalog_id = add_obj('<< /Type /Catalog /Pages 2 0 R >>')
            pages_id = add_obj('')
            font_id = add_obj('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
            font_bold_id = add_obj('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>')
            page_ids = []
            for cmds_in in pages:
                image_resources = []
                content_cmds = []
                for cmd in cmds_in:
                    if isinstance(cmd, str) and cmd.startswith('__CV3D_IMAGE__|'):
                        _, path_s, xs, ys, ws, hs = cmd.split('|', 5)
                        payload = qimage_rgb_bytes(Path(path_s))
                        if payload is None:
                            content_cmds.append(text_cmd(float(xs), float(ys) + float(hs)/2, 'Image unavailable', 10))
                            continue
                        iw, ih, rgb = payload
                        comp = zlib.compress(rgb)
                        image_id = add_obj(b'<< /Type /XObject /Subtype /Image /Width ' + str(iw).encode('ascii') + b' /Height ' + str(ih).encode('ascii') + b' /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length ' + str(len(comp)).encode('ascii') + b' >>\nstream\n' + comp + b'\nendstream')
                        name = f'Im{len(image_resources)+1}'
                        image_resources.append((name, image_id))
                        content_cmds.append(f"q {float(ws):.2f} 0 0 {float(hs):.2f} {float(xs):.2f} {float(ys):.2f} cm /{name} Do Q")
                    else:
                        content_cmds.append(cmd)
                stream = '\n'.join(content_cmds).encode('latin-1', errors='replace')
                content_id = add_obj(b'<< /Length ' + str(len(stream)).encode('ascii') + b' >>\nstream\n' + stream + b'\nendstream')
                xobj = ''
                if image_resources:
                    xobj = ' /XObject << ' + ' '.join(f'/{name} {objid} 0 R' for name, objid in image_resources) + ' >>'
                page_id = add_obj(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 {font_id} 0 R /F2 {font_bold_id} 0 R >>{xobj} >> /Contents {content_id} 0 R >>")
                page_ids.append(page_id)
            objects[pages_id - 1] = f"<< /Type /Pages /Kids [{' '.join(str(pid) + ' 0 R' for pid in page_ids)}] /Count {len(page_ids)} >>"
            out_bytes = bytearray(b'%PDF-1.4\n%CV3D\n')
            offsets = [0]
            for i, obj in enumerate(objects, start=1):
                offsets.append(len(out_bytes))
                out_bytes.extend(f"{i} 0 obj\n".encode('ascii'))
                if isinstance(obj, bytes):
                    out_bytes.extend(obj)
                else:
                    out_bytes.extend(str(obj).encode('latin-1', errors='replace'))
                out_bytes.extend(b'\nendobj\n')
            xref_pos = len(out_bytes)
            out_bytes.extend(f"xref\n0 {len(objects)+1}\n".encode('ascii'))
            out_bytes.extend(b'0000000000 65535 f \n')
            for off in offsets[1:]:
                out_bytes.extend(f"{off:010d} 00000 n \n".encode('ascii'))
            out_bytes.extend(f"trailer\n<< /Size {len(objects)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode('ascii'))
            path.write_bytes(bytes(out_bytes))

        created_at = now()
        pages = []
        cover = new_page('CV3D analysis-ready export and QC report', 'Analysis-ready outputs and QC summary')
        cover_lines = [
            f'CV ID: {cv_id}',
            f'Created: {created_at}',
            f'App version: {APP_VERSION}',
            f'Export eyes: {", ".join(self.active_export_eyes())}',
            f'Final export folder: {out["export_folder"]["folder"]}',
            f'Absolute path: {export_folder}',
            '',
            'This report summarizes method outputs only. It does not infer biological visual-field categories.',
            'The full analysis-ready data are exported as CSV tables in the same folder.',
        ]
        write_lines(cover, cover_lines, y=758, max_chars=86)
        pages.append(cover)

        readiness = new_page('Workflow status and export readiness', 'Current file-based status and Results / Export status')
        txt = self.export_readiness_text.toPlainText().strip() if getattr(self, 'export_readiness_text', None) is not None else ''
        write_lines(readiness, txt.splitlines()[:34] if txt else ['No export-readiness text available.'], y=760, leading=14, size=9, max_chars=108)
        pages.append(readiness)

        if getattr(self, 'report_include_summary_table', None) is None or self.report_include_summary_table.isChecked():
            cols = ['eye_scope', 'n_facets', 'mean_facet_size_um', 'mean_interfacet_angle_deg', 'mean_acuity_cpd', 'mean_eye_parameter', 'elevation_min', 'elevation_max', 'azimuth_start', 'azimuth_end', 'azimuth_span_deg']
            widths = [48, 38, 52, 58, 50, 54, 42, 42, 42, 42, 46]
            pages.append(table_page('Specimen and eye summary', summary_rows, cols, widths=widths, max_rows=12))

        if getattr(self, 'report_include_optic_barplots', None) is None or self.report_include_optic_barplots.isChecked():
            pages.append(optic_barplots_page())
            pages.append(optic_histograms_page())

        if getattr(self, 'report_include_05b_qc', None) is None or self.report_include_05b_qc.isChecked():
            pages.extend(pointcloud_report_pages())

        if getattr(self, 'report_include_cp_plots', None) is None or self.report_include_cp_plots.isChecked():
            pages.extend(cp_report_pages())
            pages.extend(rgl_snapshot_pages())

        if getattr(self, 'report_include_downstream_examples', None) is not None and self.report_include_downstream_examples.isChecked():
            pages.append(view_angle_metric_maps_page())

        build_pdf(pdf_path, pages)

        manifest_rows = self.read_csv_rows_rel(out['export_manifest']['file'])
        html = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>{cv_id} CV3D analysis-ready export</title></head>
<body><h1>{cv_id} — CV3D analysis-ready export</h1>
<p>Created: {created_at}</p>
<p>Facet rows: {len(facet_rows)}</p>
<p>Export eyes: {', '.join(self.active_export_eyes())}</p>
<p>Final export folder: {export_folder}</p>
<p>QC PDF: {pdf_path.name}</p>
<p>Manifest entries: {len(manifest_rows)}</p>
</body></html>"""
        write_text(html_path, html)
        timestamp = now()
        for key in ['qc_pdf_report', 'pdf_export', 'html_report']:
            if key in out:
                out[key]['status'] = 'complete' if key != 'pdf_export' else 'exported'
                out[key]['last_created'] = timestamp
                out[key]['last_exported'] = timestamp
        rep = self.status['workflow_steps'].setdefault('06_report_export', {'label': STEP_LABELS['06_report_export']})
        rep.setdefault('analysis_ready_export', {'state': 'not_created', 'symbol': '○', 'last_run': None, 'needs_rerun': False, 'messages': []})
        rep.setdefault('html_report', {'state': 'not_created', 'symbol': '○', 'last_run': None, 'needs_rerun': False, 'messages': []})
        rep.setdefault('pdf_export', {'state': 'not_exported', 'symbol': '○', 'last_exported': None, 'outdated_export': False, 'messages': []})
        rep['analysis_ready_export'].update({'state': 'complete', 'symbol': '✓', 'last_run': timestamp, 'needs_rerun': False, 'messages': [f'Exported {len(facet_rows)} facet rows.']})
        rep['html_report'].update({'state': 'complete', 'symbol': '✓', 'last_run': timestamp, 'needs_rerun': False, 'messages': []})
        rep['pdf_export'].update({'state': 'exported', 'symbol': '✓', 'last_exported': timestamp, 'outdated_export': False, 'messages': freshness_messages[:]})
        self.save_current_files()
        self.refresh_all()
        QMessageBox.information(self, 'QC PDF report complete', f'Created analysis-ready export and QC PDF report:\n\n{out["qc_pdf_report"]["file"]}\n\nFolder:\n{export_folder}')

    def generate_html_report(self) -> None:
        self.generate_qc_pdf_report()

    def export_pdf(self) -> None:
        self.generate_qc_pdf_report()

    def export_zip(self) -> None:
        if not self.config or not self.analysis_folder:
            return
        self.ensure_report_outputs_config()
        # Ensure current export tables exist before packaging.
        self.write_export_tables()
        zip_name = self.config["report_outputs"]["zip_export"]["file"]
        zip_path = self.analysis_folder / zip_name
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        include_prefixes = ["06_"]
        include_files = []
        for path in self.analysis_folder.rglob("*"):
            if not path.is_file() or path.resolve() == zip_path.resolve():
                continue
            rel = str(path.relative_to(self.analysis_folder))
            if path.name.startswith(tuple(include_prefixes)) or "/05A_" in rel or "/05B_" in rel or "/05C_" in rel or path.name.startswith("00_"):
                include_files.append(path)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in include_files:
                zf.write(path, path.relative_to(self.analysis_folder))
        timestamp = now()
        rep = self.status["workflow_steps"]["06_report_export"]["zip_export"]
        rep["state"] = "exported"
        rep["symbol"] = "✓"
        rep["last_exported"] = timestamp
        rep["outdated_export"] = False
        self.config["report_outputs"]["zip_export"]["status"] = "exported"
        self.config["report_outputs"]["zip_export"]["last_exported"] = timestamp
        self.save_current_files()
        self.refresh_all()
        QMessageBox.information(self, "Export ZIP created", f"Created export ZIP:\n\n{zip_name}")

    def open_export_folder(self) -> None:
        if self.analysis_folder:
            self.ensure_report_outputs_config()
            folder_rel = self.config.get("report_outputs", {}).get("export_folder", {}).get("folder", "") if self.config else ""
            folder = self.analysis_folder / folder_rel if folder_rel else self.analysis_folder
            folder.mkdir(parents=True, exist_ok=True)
            self.open_local_path(folder, "final export folder")

    # ---------- helpers ----------

    def open_local_path(self, path: Path, description: str = "path") -> bool:
        """Open a local file or folder with the operating system default app."""
        path = Path(path)
        if not path.exists():
            QMessageBox.warning(
                self,
                "Cannot open path",
                f"The {description} does not exist on disk:\n\n{path}"
            )
            return False

        ok = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if not ok:
            QMessageBox.warning(
                self,
                "Cannot open path",
                f"Qt could not open the {description} with the system default application:\n\n{path}"
            )
            return False
        return True

    def ensure_eye_and_dataset(self, eye: str) -> bool:
        if not self.config or not self.status or not self.analysis_folder:
            QMessageBox.warning(self, "No dataset", "Create or open a dataset first.")
            return False
        if eye not in self.config.get("eyes", {}):
            QMessageBox.information(self, "Eye unavailable", f"{eye} is not available in this dataset.")
            return False
        if not self.config["eyes"][eye].get("present", False):
            QMessageBox.information(self, "Eye skipped", f"{eye} is not present in this dataset.")
            return False
        return True

    def step_input_problems(self, step: str, eye: str) -> List[str]:
        """Return missing/stale input problems that should block a step run."""
        if not self.config or not self.status or not self.analysis_folder:
            return ["No dataset loaded."]
        if not self.config["eyes"].get(eye, {}).get("present", False):
            return [f"{eye} is not present in this dataset."]

        if step == "02_blender_cornea_extraction":
            files = self.config["eyes"][eye]["files"]
            selected = files.get("selected_raw_stl_file")
            if not selected:
                return [f"No selected raw STL for {eye}. Run ImageJ preprocessing or add an external STL first."]
            selected_path = self.analysis_folder / selected
            if not selected_path.exists():
                return [f"Selected raw STL is missing on disk: {selected}"]
            # Intentionally keep this preflight lightweight: for large STL files,
            # do not parse/validate geometry just to enable the UI button.
            size_mb = lightweight_file_size_mb(selected_path)
            if size_mb is not None and size_mb <= 0:
                return [f"Selected raw STL is empty: {selected}"]
            return []

        if step == "03a_local_height_calculation":
            # 03A can be rerun whenever the actual cornea STL exists. Do not let
            # a stale/missing Step-02 status JSON from later Blender work block
            # local-height recalculation.
            files = self.config["eyes"][eye]["files"]
            cornea_rel = files.get("cornea_stl_file")
            if not cornea_rel:
                return ["No cornea STL path is configured for this eye."]
            cornea_path = self.analysis_folder / cornea_rel
            if not cornea_path.exists():
                return [f"Cornea STL is missing on disk: {cornea_rel}"]
            size_mb = lightweight_file_size_mb(cornea_path)
            if size_mb is not None and size_mb <= 0:
                return [f"Cornea STL is empty: {cornea_rel}"]
            return []

        if step == "05b_global_coordinate_rotation":
            cv_id = self.config["dataset_identity"]["cv_id"]
            specimen_files = self.config.get("specimen_files", {})
            landmarks_rel = specimen_files.get("head_landmarks_file", f"05_{cv_id}_landmarks.csv")
            crop_log_rel = specimen_files.get("crop_log_file", f"01_{cv_id}_crop.log")
            problems_05b = []
            if not (self.analysis_folder / landmarks_rel).exists():
                problems_05b.append(f"Specimen-level head landmarks are missing: {landmarks_rel}")
            if not (self.analysis_folder / crop_log_rel).exists():
                problems_05b.append(f"ImageJ ROI crop log is missing: {crop_log_rel}")
            if problems_05b:
                return problems_05b

        problems: List[str] = []
        for required_step in REQUIRED_INPUT_STEPS.get(step, []):
            required_state = self.status["workflow_steps"][required_step][eye]
            state = required_state.get("state")
            if state not in ["complete", "complete_with_warning"]:
                label = STEP_LABELS[required_step]
                reason = "; ".join(str(m) for m in required_state.get("messages", []) if m)
                if reason:
                    problems.append(f"Required upstream step is not ready: {label} is {state}. {reason}")
                else:
                    problems.append(f"Required upstream step is not ready: {label} is {state}.")

            missing = self.missing_workflow_outputs(required_step, eye)
            if missing:
                problems.append(
                    f"Required input files from {STEP_LABELS[required_step]} are missing: "
                    + ", ".join(missing)
                )
        return problems

    def ensure_step_ready(self, step: str, eye: str) -> bool:
        if not self.ensure_eye_and_dataset(eye):
            return False

        # Re-sync status with disk immediately before running, because users may
        # delete or replace outputs outside the GUI between refreshes.
        self.validate_current_workflow_outputs(save_changes=True)
        problems = self.step_input_problems(step, eye)
        if problems:
            report = "Cannot run this step because required inputs are missing or stale.\n\n" + "\n".join(
                f"- {problem}" for problem in problems
            )
            QMessageBox.warning(self, "Step inputs not ready", report)
            self.refresh_all()
            return False
        return True

    def get_suggested_value(self, eye: str, key: str, global_default: Any) -> Any:
        if eye == "eye2":
            eye1_val = self.config["parameters"].get("eye1_last_used", {}).get(key)
            if eye1_val is not None:
                return eye1_val
        own_val = self.config["parameters"].get(f"{eye}_last_used", {}).get(key)
        if own_val is not None:
            return own_val
        return global_default


def main() -> int:
    app = QApplication(sys.argv)
    win = CV3DMainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
