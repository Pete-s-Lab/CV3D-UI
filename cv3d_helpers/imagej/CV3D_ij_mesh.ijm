/*
 * CV3D ImageJ/Fiji mesh extraction macro
 *
 * CV3D-integrated draft.
 *
 * Purpose:
 * - Load one already-cropped CV3D NRRD volume: eye1, eye2, or head.
 * - Let the user find a good surface threshold using a deliberately downscaled
 *   3D Viewer preview volume of <= 25 MB by default.
 * - Use the accepted threshold on the full-resolution source volume.
 * - Avoid binary-mask STL export because it degrades the mesh and can lose
 *   calibration/voxel-size information.
 * - Open a full-resolution 3D Viewer surface and let the user export that
 *   surface as STL to the expected CV3D path. The 3D Viewer is closed between
 *   preview and final export so both surfaces cannot be shown together.
 *
 * This macro is intentionally semi-interactive. The downscaled 3D Viewer is used
 * for fast threshold preview; the final 3D Viewer surface uses the full-resolution
 * ROI/source stack.
 *
 * Expected CV3D launch argument:
 *
 * mode=cv3d_mesh;analysis_folder=/path/to/CV0001_CV3D;cv_id=CV0001;target=eye1
 *
 * target can be: eye1, eye2, head
 */

script_version = "0.2.6-cv3d-mesh-extraction-3dviewer-status-path-fix";

run("Collect Garbage");
requires("1.39l");

if (isOpen("Log")) {
    selectWindow("Log");
    run("Close");
}
if (isOpen("Results")) {
    selectWindow("Results");
    run("Close");
}
if (isOpen("3D Viewer")) {
    selectWindow("3D Viewer");
    run("Close");
}


// -----------------------------------------------------------------------------
// Basic path and argument helpers
// -----------------------------------------------------------------------------

plugins = getDirectory("plugins");
unix_sep_test = "/plugins/";
windows_sep_test = "\\plugins\\";

if (endsWith(plugins, unix_sep_test)) {
    dir_sep = "/";
} else if (endsWith(plugins, windows_sep_test)) {
    dir_sep = "\\";
} else {
    dir_sep = "/";
}

function ensureDir(path) {
    if (!File.exists(path)) {
        File.makeDirectory(path);
    }
}

function parentDir(path) {
    idx = -1;
    for (pi = lengthOf(path) - 1; pi >= 0; pi--) {
        ch = substring(path, pi, pi + 1);
        if (ch == "/" || ch == "\\") {
            idx = pi;
            break;
        }
    }
    if (idx < 0) {
        return path;
    }
    return substring(path, 0, idx);
}

function argValue(arg_string, key, default_value) {
    parts = split(arg_string, ";");
    prefix = key + "=";
    for (ai = 0; ai < parts.length; ai++) {
        item = parts[ai];
        if (startsWith(item, prefix)) {
            return substring(item, lengthOf(prefix));
        }
    }
    return default_value;
}

function cvIdFromAnalysisFolderPath(folder_path) {
    folder_name = File.getName(folder_path);
    idx = indexOf(folder_name, "_CV3D");
    if (idx >= 0) {
        return substring(folder_name, 0, idx);
    }
    return "CV0000";
}

function relPath(rel_path) {
    return replace(rel_path, "/", dir_sep);
}

function requireFile(abs_path, label) {
    if (!File.exists(abs_path)) {
        abortWithStatus("Missing expected " + label + ": " + abs_path);
    }
}

function close3DViewerIfOpen() {
    // Close the actual 3D Viewer universe, not just an ImageJ image window.
    // This prevents preview and full-resolution surfaces from accumulating
    // in the same 3D Viewer session.
    if (isOpen("3D Viewer")) {
        selectWindow("3D Viewer");
        call("ij3d.ImageJ3DViewer.close");
        wait(500);
        if (isOpen("3D Viewer")) {
            selectWindow("3D Viewer");
            run("Close");
        }
    }
}

function safeDeleteIfExists(path) {
    if (File.exists(path)) {
        File.delete(path);
    }
}

function ensureTrailingSep(path) {
    if (endsWith(path, dir_sep)) {
        return path;
    }
    return path + dir_sep;
}

function isSTLFileName(file_name) {
    lower_name = toLowerCase(file_name);
    return endsWith(lower_name, ".stl");
}

function stlFileListString(folder_path) {
    folder_path = ensureTrailingSep(folder_path);
    file_list = getFileList(folder_path);
    out = "|";
    for (fi = 0; fi < file_list.length; fi++) {
        if (isSTLFileName(file_list[fi])) {
            out = out + file_list[fi] + "|";
        }
    }
    return out;
}

function stlListContains(list_string, file_name) {
    return indexOf(list_string, "|" + file_name + "|") >= 0;
}

function findNewSTLFile(folder_path, before_list_string) {
    folder_path = ensureTrailingSep(folder_path);
    file_list = getFileList(folder_path);
    found_path = "";
    found_count = 0;

    for (fi = 0; fi < file_list.length; fi++) {
        file_name = file_list[fi];
        if (isSTLFileName(file_name) && stlListContains(before_list_string, file_name) == false) {
            found_path = folder_path + file_name;
            found_count++;
        }
    }

    if (found_count == 1) {
        return found_path;
    }
    if (found_count > 1) {
        return "MULTIPLE_NEW_STL_FILES";
    }
    return "";
}

function findLikelySTLFile(folder_path, expected_base_name) {
    folder_path = ensureTrailingSep(folder_path);
    file_list = getFileList(folder_path);
    found_path = "";
    found_count = 0;

    for (fi = 0; fi < file_list.length; fi++) {
        file_name = file_list[fi];
        if (isSTLFileName(file_name) && indexOf(file_name, expected_base_name) >= 0) {
            found_path = folder_path + file_name;
            found_count++;
        }
    }

    if (found_count == 1) {
        return found_path;
    }
    if (found_count > 1) {
        return "MULTIPLE_LIKELY_STL_FILES";
    }
    return "";
}

function renameSTLToExpected(source_path, expected_path) {
    // ImageJ macro functions should return numeric values when used in tests.
    // Return 1 = success, 0 = failure.
    if (source_path == "") return 0;
    if (source_path == "MULTIPLE_NEW_STL_FILES") return 0;
    if (source_path == "MULTIPLE_LIKELY_STL_FILES") return 0;

    if (!File.exists(source_path)) return 0;

    // BoneJ may already have written exactly to the expected path.
    if (source_path == expected_path) return 1;

    if (File.exists(expected_path)) {
        File.delete(expected_path);
    }

    File.rename(source_path, expected_path);
    if (File.exists(expected_path)) return 1;
    return 0;
}

function boneJSurfaceAreaAvailable() {
    // Query the ImageJ menu-command table through the script engine instead of
    // getList("commands"), which is not supported in all Fiji macro builds.
    js = "importClass(Packages.ij.Menus);" +
         "var cmds = Packages.ij.Menus.getCommands();" +
         "(cmds != null && cmds.containsKey('Surface area')) ? '1' : '0';";
    result = eval("script", js);
    return result == "1";
}

function closeAllImageWindows() {
    while (nImages > 0) {
        selectImage(nImages);
        close();
    }
}

function openVolumeStack(abs_path, target_title) {
    closeAllImageWindows();

    print("Trying to open volume with ImageJ open(): " + abs_path);
    open(abs_path);

    if (nImages < 1) {
        print("ImageJ open() did not open an image. Trying Bio-Formats fallback...");
        run("Bio-Formats", "open=[" + abs_path + "] color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
    }

    if (nImages < 1) {
        abortWithStatus(
            "Could not open input volume as an image stack: " + abs_path + "\n\n" +
            "Tried ImageJ open() and Bio-Formats. The old Nrrd Writer command is not used for loading anymore, " +
            "because in some Fiji installations it opens the writer plugin and reports 'No images are open'."
        );
    }

    selectImage(nImages);
    rename(target_title);
    selectWindow(target_title);
    resetMinAndMax();

    Stack.getDimensions(w_check, h_check, c_check, s_check, f_check);
    if (s_check < 2) {
        print("Warning: loaded image has fewer than 2 z-slices. Continuing, but this may not be a valid 3D volume.");
    }
}

function bytesPerVoxelForCurrentImage() {
    bd = bitDepth();
    if (bd <= 8) return 1;
    if (bd <= 16) return 2;
    return 4;
}

function currentStackSizeMB() {
    Stack.getDimensions(w_tmp, h_tmp, c_tmp, s_tmp, f_tmp);
    bpv_tmp = bytesPerVoxelForCurrentImage();
    return w_tmp * h_tmp * s_tmp * bpv_tmp / (1024 * 1024);
}

function currentImageMaxValue() {
    getStatistics(area_tmp, mean_tmp, min_tmp, max_tmp, std_tmp);
    return max_tmp;
}

function sourceStackLooksFullResolution() {
    if (!isOpen(source_title)) {
        return false;
    }

    selectWindow(source_title);
    Stack.getDimensions(w_now, h_now, c_now, s_now, f_now);

    if (w_now != source_w) return false;
    if (h_now != source_h) return false;
    if (s_now != source_s) return false;

    return true;
}

function writeMeshStatus(status, message) {
    status_txt = "";
    status_txt = status_txt + "status=" + status + "\n";
    status_txt = status_txt + "message=" + message + "\n";
    status_txt = status_txt + "script_version=" + script_version + "\n";
    status_txt = status_txt + "cv_id=" + cv_id + "\n";
    status_txt = status_txt + "target=" + target + "\n";
    status_txt = status_txt + "input_nrrd=" + input_rel + "\n";
    status_txt = status_txt + "output_stl=" + stl_rel + "\n";
    status_txt = status_txt + "component_mask=" + mask_rel + "\n";
    status_txt = status_txt + "threshold=" + threshold_value + "\n";
    status_txt = status_txt + "foreground_is_bright=" + foreground_is_bright + "\n";
    status_txt = status_txt + "clicked_component_label=" + clicked_component_label + "\n";
    status_txt = status_txt + "preview_source_mb=" + preview_source_mb + "\n";
    status_txt = status_txt + "preview_scale=" + preview_scale + "\n";
    status_txt = status_txt + "preview_final_mb=" + preview_final_mb + "\n";
    ensureDir(parentDir(status_txt_path));
    File.saveString(status_txt, status_txt_path);

    status_json = "";
    status_json = status_json + "{" + "\n";
    status_json = status_json + "  \"status\": \"" + status + "\"," + "\n";
    status_json = status_json + "  \"message\": \"" + message + "\"," + "\n";
    status_json = status_json + "  \"script_version\": \"" + script_version + "\"," + "\n";
    status_json = status_json + "  \"cv_id\": \"" + cv_id + "\"," + "\n";
    status_json = status_json + "  \"target\": \"" + target + "\"," + "\n";
    status_json = status_json + "  \"outputs\": {" + "\n";
    status_json = status_json + "    \"input_nrrd\": \"" + input_rel + "\"," + "\n";
    status_json = status_json + "    \"output_stl\": \"" + stl_rel + "\"," + "\n";
    status_json = status_json + "    \"component_mask\": \"" + mask_rel + "\"" + "\n";
    status_json = status_json + "  }," + "\n";
    status_json = status_json + "  \"settings\": {" + "\n";
    status_json = status_json + "    \"threshold\": \"" + threshold_value + "\"," + "\n";
    status_json = status_json + "    \"foreground_is_bright\": \"" + foreground_is_bright + "\"," + "\n";
    status_json = status_json + "    \"clicked_component_label\": \"" + clicked_component_label + "\"," + "\n";
    status_json = status_json + "    \"preview_source_mb\": \"" + preview_source_mb + "\"," + "\n";
    status_json = status_json + "    \"preview_scale\": \"" + preview_scale + "\"," + "\n";
    status_json = status_json + "    \"preview_final_mb\": \"" + preview_final_mb + "\"" + "\n";
    status_json = status_json + "  }" + "\n";
    status_json = status_json + "}" + "\n";
    ensureDir(parentDir(status_json_path));
    File.saveString(status_json, status_json_path);
}

function abortWithStatus(message) {
    print("CV3D mesh extraction failed: " + message);
    writeMeshStatus("failed", message);
    exit(message);
}


// -----------------------------------------------------------------------------
// Input mode setup
// -----------------------------------------------------------------------------

arg = getArgument();
cv3d_mesh_mode = indexOf(arg, "mode=cv3d_mesh") >= 0;

if (cv3d_mesh_mode != 0) {
    analysis_dir_path = argValue(arg, "analysis_folder", "");
    cv_id = argValue(arg, "cv_id", "CV0000");
    target = argValue(arg, "target", "eye1");

    if (analysis_dir_path == "") {
        exit("CV3D mesh mode requires analysis_folder argument.");
    }

} else {
    waitForUser(
        "Standalone CV3D mesh extraction",
        "No CV3D mesh argument string was provided.\n\n" +
        "Select the existing CVxxxx_CV3D analysis folder.\n\n" +
        "The macro will then ask whether to extract eye1, eye2, or head."
    );

    analysis_dir_path = getDirectory("Select CV3D analysis folder");
    cv_id_guess = cvIdFromAnalysisFolderPath(analysis_dir_path);

    Dialog.create("CV3D mesh extraction target");
    Dialog.addString("CV ID:", cv_id_guess);
    Dialog.addChoice("Target volume:", newArray("eye1", "eye2", "head"), "eye1");
    Dialog.show();

    cv_id = Dialog.getString();
    target = Dialog.getChoice();
}

if (target != "eye1" && target != "eye2" && target != "head") {
    exit("Unsupported target='" + target + "'. Use target=eye1, target=eye2, or target=head.");
}

ensureDir(analysis_dir_path);
ensureDir(analysis_dir_path + dir_sep + "inspection");
ensureDir(analysis_dir_path + dir_sep + "eye1");
ensureDir(analysis_dir_path + dir_sep + "eye2");
ensureDir(analysis_dir_path + dir_sep + "eye1" + dir_sep + "inspection");
ensureDir(analysis_dir_path + dir_sep + "eye2" + dir_sep + "inspection");
ensureDir(analysis_dir_path + dir_sep + "json");
ensureDir(analysis_dir_path + dir_sep + "logs");
ensureDir(analysis_dir_path + dir_sep + "eye1" + dir_sep + "json");
ensureDir(analysis_dir_path + dir_sep + "eye1" + dir_sep + "logs");
ensureDir(analysis_dir_path + dir_sep + "eye2" + dir_sep + "json");
ensureDir(analysis_dir_path + dir_sep + "eye2" + dir_sep + "logs");

if (target == "head") {
    input_rel = "01_" + cv_id + "_head.nrrd";
    stl_rel = "01_" + cv_id + "_head_ImageJ.stl";
    mask_rel = "inspection/01_" + cv_id + "_head_mesh_component_mask.nrrd";
    status_json_rel = "json/01MESH_" + cv_id + "_head_ImageJ_status.json";
    status_txt_rel = "logs/01MESH_" + cv_id + "_head_ImageJ_status.txt";
    stl_dir = analysis_dir_path;
} else {
    input_rel = target + "/01_" + cv_id + "_" + target + ".nrrd";
    stl_rel = target + "/01_" + cv_id + "_" + target + "_ImageJ.stl";
    mask_rel = target + "/inspection/01_" + cv_id + "_" + target + "_mesh_component_mask.nrrd";
    status_json_rel = target + "/json/01MESH_" + cv_id + "_" + target + "_ImageJ_status.json";
    status_txt_rel = target + "/logs/01MESH_" + cv_id + "_" + target + "_ImageJ_status.txt";
    stl_dir = analysis_dir_path + dir_sep + target;
}

input_path = analysis_dir_path + dir_sep + relPath(input_rel);
stl_path = analysis_dir_path + dir_sep + relPath(stl_rel);
mask_path = analysis_dir_path + dir_sep + relPath(mask_rel);
status_json_path = analysis_dir_path + dir_sep + relPath(status_json_rel);
status_txt_path = analysis_dir_path + dir_sep + relPath(status_txt_rel);

threshold_value = "NA";
foreground_is_bright = "true";
clicked_component_label = "NA";
preview_source_mb = "NA";
preview_scale = "NA";
preview_final_mb = "NA";

writeMeshStatus("running", "CV3D mesh extraction macro started.");

print("************************************");
print("CV3D ImageJ mesh extraction");
print("script_version = " + script_version);
print("cv_id = " + cv_id);
print("target = " + target);
print("analysis folder = " + analysis_dir_path);
print("input_nrrd = " + input_path);
print("output_stl = " + stl_path);
print("************************************");

requireFile(input_path, "input NRRD");

// -----------------------------------------------------------------------------
// Load source volume
// -----------------------------------------------------------------------------

source_title = "cv3d_" + target + "_source";
openVolumeStack(input_path, source_title);
Stack.getDimensions(source_w, source_h, source_c, source_s, source_f);

source_mb = currentStackSizeMB();

Dialog.create("Mesh threshold preview settings");
Dialog.addMessage("The 3D Viewer will only receive a downscaled preview stack.");
Dialog.addMessage("The full source stack is kept for final thresholding and STL export.");
Dialog.addMessage("___________________________________");
Dialog.addNumber("Initial threshold:", 100);
Dialog.addCheckbox("Foreground is bright, i.e. keep voxels >= threshold", true);
Dialog.addNumber("Maximum 3D Viewer preview volume [MB]:", 25);
Dialog.addNumber("3D Viewer resampling factor:", 2);
Dialog.show();

threshold_value = Dialog.getNumber();
foreground_is_bright = Dialog.getCheckbox();
preview_max_mb = Dialog.getNumber();
viewer_resampling = Dialog.getNumber();

if (preview_max_mb <= 0) {
    preview_max_mb = 25;
}
if (preview_max_mb > 25) {
    waitForUser(
        "Preview size capped",
        "The requested preview size was larger than 25 MB.\n\n" +
        "It will be capped to 25 MB to protect the 3D Viewer."
    );
    preview_max_mb = 25;
}
if (viewer_resampling < 1) {
    viewer_resampling = 1;
}


// -----------------------------------------------------------------------------
// Create <=25 MB preview stack for 3D Viewer threshold inspection
// -----------------------------------------------------------------------------

selectWindow(source_title);
preview_source_mb = currentStackSizeMB();
preview_title = "cv3d_" + target + "_preview_max25MB";

if (preview_source_mb > preview_max_mb) {
    preview_scale = pow(preview_max_mb / preview_source_mb, 1 / 3);
    preview_scale = floor(preview_scale * 100) / 100;
    if (preview_scale < 0.01) {
        preview_scale = 0.01;
    }

    print("Creating downscaled 3D Viewer preview.");
    print("Source stack estimate: " + preview_source_mb + " MB");
    print("Preview maximum: " + preview_max_mb + " MB");
    print("Preview isotropic scale: " + preview_scale);

    run("Scale...", "x=" + preview_scale + " y=" + preview_scale + " z=" + preview_scale + " interpolation=Bicubic average process create");
    rename(preview_title);

} else {
    preview_scale = 1;
    print("Source stack estimate is <= preview limit. Creating direct preview duplicate.");
    run("Duplicate...", "title=[" + preview_title + "] duplicate");
}

selectWindow(preview_title);
if (foreground_is_bright == false) {
    run("Invert", "stack");
}
preview_final_mb = currentStackSizeMB();

if (preview_final_mb > 25.1) {
    abortWithStatus("Internal preview-size guard failed. Preview is still larger than 25 MB: " + preview_final_mb + " MB.");
}

print("3D Viewer preview stack estimate: " + preview_final_mb + " MB");


// -----------------------------------------------------------------------------
// Interactive surface threshold preview with 3D Viewer
// -----------------------------------------------------------------------------

threshold_accepted = false;

while (threshold_accepted == false) {
    close3DViewerIfOpen();

    selectWindow(preview_title);
    resetMinAndMax();

    print("Opening 3D Viewer threshold preview for " + target + " with threshold " + threshold_value + ".");
    run("3D Viewer");
    call("ij3d.ImageJ3DViewer.setCoordinateSystem", "false");
    call(
        "ij3d.ImageJ3DViewer.add",
        preview_title,
        "White",
        target + "_threshold_preview",
        threshold_value,
        "true",
        "true",
        "true",
        "" + viewer_resampling,
        "2"
    );

    waitForUser(
        "Inspect threshold preview",
        "Inspect the lightweight 3D Viewer surface preview.\n\n" +
        "Only the preview stack is loaded into 3D Viewer.\n" +
        "Preview stack estimate: " + preview_final_mb + " MB\n\n" +
        "Close/rotate/inspect as needed, then click OK."
    );

    close3DViewerIfOpen();

    Dialog.create("Accept threshold?");
    Dialog.addMessage("Target: " + target);
    Dialog.addMessage("Current threshold: " + threshold_value);
    Dialog.addCheckbox("Accept this threshold", true);
    Dialog.addNumber("Threshold to preview next if not accepted:", threshold_value);
    Dialog.show();

    threshold_accepted = Dialog.getCheckbox();
    threshold_value = Dialog.getNumber();
}

print("Accepted threshold: " + threshold_value);


// -----------------------------------------------------------------------------
// Full-resolution 3D Viewer STL export
// -----------------------------------------------------------------------------

// The scaled preview is only for threshold finding. Final mesh export must use
// the full-resolution source ROI. If the source window was accidentally closed
// or changed, reload it from disk before opening the final 3D Viewer surface.
if (sourceStackLooksFullResolution() == false) {
    print("Full-resolution source stack is missing or changed. Reloading before final 3D Viewer export.");
    openVolumeStack(input_path, source_title);
    Stack.getDimensions(source_w, source_h, source_c, source_s, source_f);
}

selectWindow(source_title);
threshold_work_title = "cv3d_" + target + "_fullres_for_3DViewer_export";
if (isOpen(threshold_work_title)) {
    selectWindow(threshold_work_title);
    close();
}
run("Duplicate...", "title=[" + threshold_work_title + "] duplicate");
selectWindow(threshold_work_title);

if (foreground_is_bright == false) {
    run("Invert", "stack");
}

resetMinAndMax();
clicked_component_label = "full_resolution_3DViewer_surface";
component_mask_title = threshold_work_title;

print("Opening full-resolution 3D Viewer surface for final STL export.");
print("Accepted threshold: " + threshold_value);
print("Expected STL path: " + stl_path);

if (File.exists(stl_path)) {
    overwrite_ok = getBoolean(
        "The output STL already exists:\n\n" + stl_path + "\n\nOverwrite it?",
        "Overwrite",
        "Cancel"
    );
    if (overwrite_ok == 0) {
        abortWithStatus("User cancelled because output STL already exists: " + stl_path);
    }
    File.delete(stl_path);
}

close3DViewerIfOpen();
selectWindow(threshold_work_title);
run("3D Viewer");
call("ij3d.ImageJ3DViewer.setCoordinateSystem", "false");
call(
    "ij3d.ImageJ3DViewer.add",
    threshold_work_title,
    "White",
    "01_" + cv_id + "_" + target + "_ImageJ",
    threshold_value,
    "true",
    "true",
    "true",
    "1",
    "2"
);

export_done = false;
while (export_done == false) {
    waitForUser(
        "Export STL from 3D Viewer",
        "A full-resolution 3D Viewer surface has been opened.\n\n" +
        "Please export this surface from the 3D Viewer as STL and save it exactly here:\n\n" +
        stl_path + "\n\n" +
        "This avoids the binary-mask/BoneJ export path, which produced blocky meshes and wrong scale.\n\n" +
        "After saving the STL, click OK."
    );

    if (File.exists(stl_path)) {
        export_done = true;
    } else {
        retry_export = getBoolean(
            "The expected STL file was not found yet:\n\n" + stl_path + "\n\n" +
            "Retry the 3D Viewer STL export?",
            "Retry",
            "Abort"
        );
        if (retry_export == 0) {
            abortWithStatus("User aborted because the 3D Viewer STL export file was not found: " + stl_path);
        }
    }
}

close3DViewerIfOpen();

writeMeshStatus("success", "Mesh extraction finished successfully.");
print("All done!");
print("Status: success");
print("Output STL: " + stl_path);
print("Final mesh source: full-resolution 3D Viewer surface");
print("************************************");

run("Collect Garbage");
