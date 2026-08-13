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
 * - Create the final surface from the full-resolution calibrated source volume.
 * - Open exactly one 3D Viewer at a time and let the user export its surface as
 *   STL to the expected CV3D path.
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

script_version = "0.2.8-cv3d-mesh-extraction-streamlined-session-01";

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

function roundSuggested2(value) {
    return round(value * 100) / 100;
}

function suggestedDecimals(value) {
    rounded_value = roundSuggested2(value);
    if (abs(rounded_value - round(rounded_value)) < 0.000000001) {
        return 0;
    }
    return 2;
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

function closeAll3DViewers() {
    // The 3D Viewer can have multiple universes with the same window title.
    // Close the universes themselves so no stale viewer can receive new content.
    for (close_pass = 0; close_pass < 3; close_pass++) {
        js = "var u = Packages.ij3d.Image3DUniverse.universes;" +
             "for (var i = u.size() - 1; i >= 0; i--) {" +
             "  try { u.get(i).close(); } catch (e) {}" +
             "}" +
             "'' + u.size();";
        remaining = eval("script", js);
        if (remaining == "0") break;
        wait(250);
    }
    wait(300);
}

function viewerHasContent(content_name) {
    js_name = replace(content_name, "\\", "\\\\");
    js_name = replace(js_name, "'", "\\'");
    js = "var u = Packages.ij3d.Image3DUniverse.universes;" +
         "(u.size() > 0 && u.get(0).getContent('" + js_name + "') != null) ? '1' : '0';";
    result = eval("script", js);
    if (result == "1") {
        return 1;
    }
    return 0;
}

function openSingle3DSurface(image_title, content_name, threshold_value_local, resampling_local) {
    closeAll3DViewers();
    selectWindow(image_title);
    run("3D Viewer");
    wait(400);

    call(
        "ij3d.ImageJ3DViewer.add",
        image_title,
        "White",
        content_name,
        threshold_value_local,
        "true",
        "true",
        "true",
        resampling_local,
        "2"
    );

    content_ready = false;
    for (viewer_wait = 0; viewer_wait < 40; viewer_wait++) {
        if (viewerHasContent(content_name)) {
            content_ready = true;
            break;
        }
        wait(250);
    }

    if (content_ready == false) {
        abortWithStatus(
            "The 3D Viewer opened, but the expected surface was not created: " + content_name
        );
    }

    call("ij3d.ImageJ3DViewer.select", content_name);
    call("ij3d.ImageJ3DViewer.setCoordinateSystem", "false");
    call("ij3d.ImageJ3DViewer.resetView");
    wait(300);
}


function closeImageJAfterCv3d() {
    closeAll3DViewers();
    if (isOpen("Results")) {
        selectWindow("Results");
        run("Close");
    }
    if (isOpen("Log")) {
        selectWindow("Log");
        run("Close");
    }
    while (nImages > 0) {
        selectImage(nImages);
        setOption("Changes", false);
        close();
    }
    run("Collect Garbage");
    wait(250);
    run("Quit");
}

function closeAllImageWindows() {
    while (nImages > 0) {
        selectImage(nImages);
        setOption("Changes", false);
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
            "Tried ImageJ open() and Bio-Formats."
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
    quit_after = parseInt(argValue(arg, "quit_after", "1"));
    suggested_threshold_arg = argValue(arg, "suggested_threshold", "");

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
    quit_after = 1;
    suggested_threshold_arg = "";
}

if (isNaN(quit_after)) {
    quit_after = 1;
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

threshold_default = 100;
if (suggested_threshold_arg != "") {
    parsed_suggested_threshold = parseFloat(suggested_threshold_arg);
    if (!isNaN(parsed_suggested_threshold)) {
        threshold_default = parsed_suggested_threshold;
    }
}

Dialog.create("Mesh threshold preview settings");
Dialog.addMessage("The 3D Viewer will only receive a downscaled preview stack.");
if (target == "head") {
    Dialog.addMessage("For the head ROI, this preview surface is also used for STL export; a full-resolution 3D Viewer surface is not created.");
} else {
    Dialog.addMessage("The full source stack is kept for final eye STL export.");
}
if (suggested_threshold_arg != "") {
    Dialog.addMessage("The initial threshold below is suggested from the previously accepted ROI threshold.");
}
Dialog.addMessage("___________________________________");
threshold_default = roundSuggested2(threshold_default);
Dialog.addNumber("Initial threshold (suggested):", threshold_default, suggestedDecimals(threshold_default));
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
    selectWindow(preview_title);
    resetMinAndMax();

    print("Opening 3D Viewer threshold preview for " + target + " with threshold " + threshold_value + ".");
    print("This may take a while. If this fails, try increasing the threshold, cropping your sample, or exporting the STL with another software.");
    preview_content_name = target + "_threshold_preview";
    openSingle3DSurface(
        preview_title,
        preview_content_name,
        "" + threshold_value,
        "" + viewer_resampling
    );

    waitForUser(
        "Inspect threshold preview",
        "Inspect the lightweight 3D Viewer surface preview.\n\n" +
        "Only the preview stack is loaded into 3D Viewer.\n" +
        "Preview stack estimate: " + preview_final_mb + " MB\n\n" +
        "Close/rotate/inspect as needed, then click OK."
    );

    closeAll3DViewers();

    Dialog.create("Accept threshold?");
    Dialog.addMessage("Target: " + target);
    Dialog.addMessage("Current threshold: " + threshold_value);
    Dialog.addCheckbox("Accept this threshold", true);
    threshold_value = roundSuggested2(threshold_value);
    Dialog.addNumber("Threshold to preview next if not accepted:", threshold_value, suggestedDecimals(threshold_value));
    Dialog.show();

    threshold_accepted = Dialog.getCheckbox();
    threshold_value = Dialog.getNumber();
}

print("Accepted threshold: " + threshold_value);


// -----------------------------------------------------------------------------
// Final 3D Viewer STL export
// -----------------------------------------------------------------------------

if (File.exists(stl_path)) {
    overwrite_ok = getBoolean(
        "The output STL already exists:

" + stl_path + "

Overwrite it?",
        "Overwrite",
        "Cancel"
    );
    if (overwrite_ok == 0) {
        abortWithStatus("User cancelled because output STL already exists: " + stl_path);
    }
    File.delete(stl_path);
}

final_content_name = "01_" + cv_id + "_" + target + "_ImageJ";

if (target == "head") {
    selectWindow(preview_title);
    resetMinAndMax();
    print("Opening downscaled 3D Viewer surface for final head STL export.");
    print("This may take a while. If this fails, try increasing the threshold, cropping your sample, or exporting the STL with another software.");
    print("Accepted threshold: " + threshold_value);
    print("Expected STL path:");
    print(stl_path);
    openSingle3DSurface(
        preview_title,
        final_content_name,
        "" + threshold_value,
        "" + viewer_resampling
    );
    mesh_source_label = "downscaled 3D Viewer preview surface";
    export_surface_message = "The accepted head preview surface is ready in the 3D Viewer.";
} else {
    if (sourceStackLooksFullResolution() == false) {
        print("Full-resolution source stack is missing or changed. Reloading before final 3D Viewer export.");
        openVolumeStack(input_path, source_title);
        Stack.getDimensions(source_w, source_h, source_c, source_s, source_f);
    }

    selectWindow(source_title);
    threshold_work_title = "cv3d_" + target + "_fullres_for_3DViewer_export";
    if (isOpen(threshold_work_title)) {
        selectWindow(threshold_work_title);
        setOption("Changes", false);
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
    print("This may take a while. If this fails, try increasing the threshold, cropping your sample, or exporting the STL with another software.");
    print("Accepted threshold: " + threshold_value);
    print("Expected STL path:");
    print(stl_path);

    openSingle3DSurface(
        threshold_work_title,
        final_content_name,
        "" + threshold_value,
        "1"
    );
    mesh_source_label = "full-resolution 3D Viewer surface";
    export_surface_message = "The full-resolution eye surface is ready in the 3D Viewer.";
}

export_done = false;
while (export_done == false) {
    waitForUser(
        "Export STL from 3D Viewer",
        export_surface_message + "\n\n" +
        "Export it as STL and save it to this exact path:\n\n" +
        "Expected STL path:\n" +
        stl_path + "\n\n" +
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

closeAll3DViewers();

writeMeshStatus("success", "Mesh extraction finished successfully.");
print("All done!");
print("Status: success");
print("Output STL: " + stl_path);
print("Mesh source: " + mesh_source_label);
print("************************************");

if (quit_after == 1) {
    closeImageJAfterCv3d();
} else {
    closeAll3DViewers();
    closeAllImageWindows();
    run("Collect Garbage");
    return "" + threshold_value;
}
