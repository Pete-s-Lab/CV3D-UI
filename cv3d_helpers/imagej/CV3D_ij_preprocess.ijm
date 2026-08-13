/*
 * CV3D ImageJ/Fiji preprocessing macro
 *
 * CV3D-integrated draft.
 *
 * Purpose:
 * - Open the raw/source image-volume dataset interactively.
 * - Let the user define the head ROI and one or two eye ROIs.
 * - Save head and eye NRRD outputs directly into the CV3D analysis folder.
 * - Ask the user to estimate facet size with a line selection.
 * - Save preprocessing outputs only; mesh/STL extraction is handled by a separate CV3D macro.
 * - Write a crop log and ImageJ status JSON/TXT for the CV3D GUI.
 *
 * This macro is intentionally NOT headless.
 *
 * Expected CV3D launch argument:
 *
 * mode=cv3d;raw_folder=/path/to/raw;analysis_folder=/path/to/CV0001_CV3D;cv_id=CV0001;active_eyes=eye1,eye2
 *
 * Peter T. Rühr original workflow, adapted for CV3D integration.
 */

script_version = "0.9.9042-cv3d-preprocessing-nrrd-write-fix-autoquit";

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
    print("Running on Unix-like system...");
    dir_sep = "/";
} else if (endsWith(plugins, windows_sep_test)) {
    print("Running on Windows...");
    dir_sep = "\\";
} else {
    print("Could not infer OS path separator from plugins path. Falling back to '/'.");
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


function closeImageJAfterCv3d() {
    if (isOpen("3D Viewer")) {
        selectWindow("3D Viewer");
        run("Close");
    }
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

function waitForRectangleROI(dialog_title, instructions) {
    roi_ok = 0;
    while (roi_ok == 0) {
        run("Select None");
        setTool("rectangle");
        waitForUser(
            dialog_title,
            instructions + "\n\nDraw a rectangular ROI, then click OK."
        );

        if (selectionType() == 0) {
            roi_ok = 1;
        } else {
            waitForUser(
                "Missing rectangle selection",
                "No rectangular ROI was detected for: " + dialog_title + ".\n\n" +
                "Click OK to return to the same ROI-selection step."
            );
        }
    }
}

function findCv3dAnalysisFolder(source_dir) {
    list = getFileList(source_dir);
    found = "";
    found_count = 0;

    for (fi = 0; fi < list.length; fi++) {
        item = list[fi];
        if (endsWith(item, "/")) {
            folder_name = substring(item, 0, lengthOf(item) - 1);
            if (startsWith(folder_name, "CV") && endsWith(folder_name, "_CV3D")) {
                found = folder_name;
                found_count++;
            }
        }
    }

    if (found_count == 1) {
        return found;
    }
    if (found_count > 1) {
        return "MULTIPLE";
    }
    return "";
}

function cvIdFromAnalysisFolderName(folder_name) {
    idx = indexOf(folder_name, "_CV3D");
    if (idx >= 0) {
        return substring(folder_name, 0, idx);
    }
    return folder_name;
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

function argContainsEye(active_eye_string, eye_name) {
    padded = "," + active_eye_string + ",";
    needle = "," + eye_name + ",";
    return indexOf(padded, needle) >= 0;
}

function boolInt(value) {
    if (value != 0) {
        return 1;
    } else {
        return 0;
    }
}




// -----------------------------------------------------------------------------
// CV3D status writing
// -----------------------------------------------------------------------------

function writeCv3dStatus(status, message) {
    status_txt = "";
    status_txt = status_txt + "status=" + status + "\n";
    status_txt = status_txt + "message=" + message + "\n";
    status_txt = status_txt + "script_version=" + script_version + "\n";
    status_txt = status_txt + "cv_id=" + cv_id + "\n";
    status_txt = status_txt + "active_eyes=" + active_eyes + "\n";
    status_txt = status_txt + "head_nrrd=" + head_nrrd_rel + "\n";
    status_txt = status_txt + "facet_size_estimate_csv=" + facet_size_csv_rel + "\n";
    status_txt = status_txt + "crop_log=" + crop_log_rel + "\n";
    status_txt = status_txt + "eye1_present=" + has_eye1 + "\n";
    status_txt = status_txt + "eye1_nrrd=" + eye1_nrrd_rel + "\n";
    status_txt = status_txt + "eye1_stl=" + eye1_stl_rel + "\n";
    status_txt = status_txt + "eye2_present=" + has_eye2 + "\n";
    status_txt = status_txt + "eye2_nrrd=" + eye2_nrrd_rel + "\n";
    status_txt = status_txt + "eye2_stl=" + eye2_stl_rel + "\n";
    status_txt = status_txt + "extract_surfaces=" + extract_surfaces + "\n";
    File.saveString(status_txt, status_txt_path);

    status_json = "";
    status_json = status_json + "{" + "\n";
    status_json = status_json + "  \"status\": \"" + status + "\"," + "\n";
    status_json = status_json + "  \"message\": \"" + message + "\"," + "\n";
    status_json = status_json + "  \"script_version\": \"" + script_version + "\"," + "\n";
    status_json = status_json + "  \"cv_id\": \"" + cv_id + "\"," + "\n";
    status_json = status_json + "  \"active_eyes\": \"" + active_eyes + "\"," + "\n";
    status_json = status_json + "  \"outputs\": {" + "\n";
    status_json = status_json + "    \"head_nrrd\": \"" + head_nrrd_rel + "\"," + "\n";
    status_json = status_json + "    \"facet_size_estimate_csv\": \"" + facet_size_csv_rel + "\"," + "\n";
    status_json = status_json + "    \"crop_log\": \"" + crop_log_rel + "\"," + "\n";
    status_json = status_json + "    \"eye1_nrrd\": \"" + eye1_nrrd_rel + "\"," + "\n";
    status_json = status_json + "    \"eye1_stl\": \"" + eye1_stl_rel + "\"," + "\n";
    status_json = status_json + "    \"eye2_nrrd\": \"" + eye2_nrrd_rel + "\"," + "\n";
    status_json = status_json + "    \"eye2_stl\": \"" + eye2_stl_rel + "\"" + "\n";
    status_json = status_json + "  }," + "\n";
    status_json = status_json + "  \"settings\": {" + "\n";
    status_json = status_json + "    \"extract_surfaces\": \"" + extract_surfaces + "\"," + "\n";
    status_json = status_json + "    \"has_eye1\": \"" + has_eye1 + "\"," + "\n";
    status_json = status_json + "    \"has_eye2\": \"" + has_eye2 + "\"" + "\n";
    status_json = status_json + "  }" + "\n";
    status_json = status_json + "}" + "\n";
    File.saveString(status_json, status_json_path);
}

function abortWithStatus(message) {
    print("CV3D ImageJ preprocessing failed: " + message);
    writeCv3dStatus("failed", message);
    exit(message);
}

function requireFile(abs_path, label) {
    if (!File.exists(abs_path)) {
        abortWithStatus("Missing expected " + label + ": " + abs_path);
    }
}

function saveNrrd(abs_path) {
    // Fiji's NRRD reader and writer are separate plugins. Calling
    // run("Nrrd ...") can invoke the reader and open a file chooser.
    // Use ImageJ's built-in script evaluator to call Fiji's Nrrd_Writer
    // directly, avoiding both that command-name conflict and BeanShell.
    js_path = replace(abs_path, "\\", "\\\\");
    js_path = replace(js_path, "'", "\\'");

    script = "var imp = Packages.ij.WindowManager.getCurrentImage();" +
             "if (imp == null) throw 'No active ImageJ image';" +
             "var writer = new Packages.sc.fiji.io.Nrrd_Writer();" +
             "writer.save(imp, '" + js_path + "');";

    eval("script", script);
}


// -----------------------------------------------------------------------------
// Input mode setup
// -----------------------------------------------------------------------------

arg = getArgument();
cv3d_mode = indexOf(arg, "mode=cv3d") >= 0;

if (cv3d_mode != 0) {
    parent_dir_path = argValue(arg, "raw_folder", "");
    analysis_dir_path = argValue(arg, "analysis_folder", "");
    cv_id = argValue(arg, "cv_id", "CV0000");
    active_eyes = argValue(arg, "active_eyes", "eye1,eye2");
    specimen_name = argValue(arg, "specimen_name", cv_id);

    if (parent_dir_path == "") {
        exit("CV3D mode requires raw_folder argument.");
    }
    if (analysis_dir_path == "") {
        exit("CV3D mode requires analysis_folder argument.");
    }

} else {
    waitForUser(
        "Standalone fallback",
        "No CV3D argument string was provided.\n\n" +
        "Select the raw/source folder that already contains the CVxxxx_CV3D analysis folder created by the CV3D GUI.\n\n" +
        "For normal CV3D use, this macro will later be launched directly from the CV3D GUI."
    );
    parent_dir_path = getDirectory("Select source directory");
    parent_dir_name = File.getName(parent_dir_path);
    specimen_name = parent_dir_name;

    found_cv_folder = findCv3dAnalysisFolder(parent_dir_path);

    if (found_cv_folder == "MULTIPLE") {
        waitForUser(
            "Multiple CV3D folders found",
            "More than one CVxxxx_CV3D folder was found in the selected source folder.\n\n" +
            "The macro will ask for the CV ID to use."
        );
        Dialog.create("Choose CV3D dataset");
        Dialog.addMessage("Enter the CV ID of the existing analysis folder to use.");
        Dialog.addString("CV ID:", "CV0001");
        Dialog.addChoice("Eyes to process:", newArray("eye1", "eye2", "eye1,eye2"), "eye1,eye2");
        Dialog.show();
        cv_id = Dialog.getString();
        active_eyes = Dialog.getChoice();
        analysis_dir_path = parent_dir_path + dir_sep + cv_id + "_CV3D";

    } else if (found_cv_folder != "") {
        cv_id = cvIdFromAnalysisFolderName(found_cv_folder);
        analysis_dir_path = parent_dir_path + dir_sep + found_cv_folder;

        waitForUser(
            "CV3D dataset found",
            "Found CV3D analysis folder:\n\n" +
            analysis_dir_path + "\n\n" +
            "Using CV ID: " + cv_id
        );

        Dialog.create("Standalone active eyes");
        Dialog.addMessage("Using CV ID found in existing analysis folder: " + cv_id);
        Dialog.addChoice("Eyes to process:", newArray("eye1", "eye2", "eye1,eye2"), "eye1,eye2");
        Dialog.show();
        active_eyes = Dialog.getChoice();

    } else {
        waitForUser(
            "No CV3D folder found",
            "Warning: no CVxxxx_CV3D folder was found in the selected source folder.\n\n" +
            "This usually means the dataset has not yet been created in the CV3D GUI.\n\n" +
            "The macro will ask for a CV ID and create/use a matching CVxxxx_CV3D folder."
        );

        Dialog.create("Create/use CV3D folder");
        Dialog.addString("CV ID:", "CV0001");
        Dialog.addChoice("Eyes to process:", newArray("eye1", "eye2", "eye1,eye2"), "eye1,eye2");
        Dialog.show();
        cv_id = Dialog.getString();
        active_eyes = Dialog.getChoice();
        analysis_dir_path = parent_dir_path + dir_sep + cv_id + "_CV3D";
    }
}

has_eye1 = 0;
has_eye2 = 0;
if (indexOf("," + active_eyes + ",", ",eye1,") >= 0) has_eye1 = 1;
if (indexOf("," + active_eyes + ",", ",eye2,") >= 0) has_eye2 = 1;
eye_count = has_eye1 + has_eye2;
print("Parsed active eyes: " + active_eyes);
print("has_eye1 = " + has_eye1);
print("has_eye2 = " + has_eye2);

if (eye_count < 1) {
    exit("No active eyes were supplied. Use active_eyes=eye1, active_eyes=eye2, or active_eyes=eye1,eye2.");
}
if (eye_count > 2) {
    exit("This CV3D draft supports only one or two active eyes.");
}

ensureDir(analysis_dir_path);
ensureDir(analysis_dir_path + dir_sep + "eye1");
ensureDir(analysis_dir_path + dir_sep + "eye2");
ensureDir(analysis_dir_path + dir_sep + "eye1" + dir_sep + "inspection");
ensureDir(analysis_dir_path + dir_sep + "eye2" + dir_sep + "inspection");

head_nrrd_rel = "01_" + cv_id + "_head.nrrd";
facet_size_csv_rel = "01_" + cv_id + "_facet_size_estimate.csv";
crop_log_rel = "01_" + cv_id + "_crop.log";
status_json_rel = "01_" + cv_id + "_ImageJ_status.json";
status_txt_rel = "01_" + cv_id + "_ImageJ_status.txt";

eye1_nrrd_rel = "eye1/01_" + cv_id + "_eye1.nrrd";
eye1_stl_rel = "eye1/01_" + cv_id + "_eye1_ImageJ.stl";
eye2_nrrd_rel = "eye2/01_" + cv_id + "_eye2.nrrd";
eye2_stl_rel = "eye2/01_" + cv_id + "_eye2_ImageJ.stl";

head_nrrd_path = analysis_dir_path + dir_sep + replace(head_nrrd_rel, "/", dir_sep);
facet_size_csv_path = analysis_dir_path + dir_sep + replace(facet_size_csv_rel, "/", dir_sep);
crop_log_path = analysis_dir_path + dir_sep + replace(crop_log_rel, "/", dir_sep);
status_json_path = analysis_dir_path + dir_sep + replace(status_json_rel, "/", dir_sep);
status_txt_path = analysis_dir_path + dir_sep + replace(status_txt_rel, "/", dir_sep);

eye1_nrrd_path = analysis_dir_path + dir_sep + replace(eye1_nrrd_rel, "/", dir_sep);
eye1_stl_path = analysis_dir_path + dir_sep + replace(eye1_stl_rel, "/", dir_sep);
eye2_nrrd_path = analysis_dir_path + dir_sep + replace(eye2_nrrd_rel, "/", dir_sep);
eye2_stl_path = analysis_dir_path + dir_sep + replace(eye2_stl_rel, "/", dir_sep);

extract_surfaces = "false";
writeCv3dStatus("running", "ImageJ preprocessing macro started. Mesh extraction is handled separately.");

print("************************************");
print("CV3D ImageJ preprocessing");
print("script_version = " + script_version);
print("cv_id = " + cv_id);
print("raw/source folder = " + parent_dir_path);
print("analysis folder = " + analysis_dir_path);
print("active_eyes = " + active_eyes);
print("************************************");


// -----------------------------------------------------------------------------
// Open source stack
// -----------------------------------------------------------------------------

function listFilesNonRecurse(dir) {
    list = getFileList(dir);
    out = newArray();
    for (li = 0; li < list.length; li++) {
        if (!endsWith(list[li], "/")) {
            out = Array.concat(out, newArray(list[li]));
        }
    }
    return out;
}

function tryOpenSequenceWithFallback(source_dir, label) {
    print("Opening " + label + " sequence with File.openSequence:");
    print(source_dir);
    File.openSequence(source_dir);

    if (nImages < 1) {
        print("File.openSequence did not open an image. Trying Image Sequence command fallback...");
        run("Image Sequence...", "open=[" + source_dir + "] sort");
    }

    if (nImages < 1) {
        print("Image Sequence fallback still did not open an image.");
    }
}

filelist = listFilesNonRecurse(parent_dir_path);

if (File.exists(parent_dir_path + dir_sep + "DICOMDIR")) {
    print("Trying to open DICOMDIR in " + parent_dir_path + "...");
    run("Bio-Formats", "open=[" + parent_dir_path + dir_sep + "DICOMDIR" + "] color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");

} else {
    if (filelist.length == 0) {
        abortWithStatus("No files found in source directory: " + parent_dir_path);
    }

    Array.print(filelist);
    first_file_lower = toLowerCase(filelist[0]);

    if (endsWith(first_file_lower, ".dcm")) {
        print("Trying to open DICOM sequence in " + parent_dir_path + "...");
        tryOpenSequenceWithFallback(parent_dir_path, "DICOM");

    } else if (endsWith(first_file_lower, ".tif")) {
        if (filelist.length == 1) {
            print("Trying to open single tif file:");
            print(parent_dir_path + dir_sep + filelist[0]);
            open(parent_dir_path + dir_sep + filelist[0]);
        } else {
            print("Trying to open TIFF sequence in " + parent_dir_path + "...");
            tryOpenSequenceWithFallback(parent_dir_path, "TIFF");
        }

    } else if (endsWith(first_file_lower, ".tiff")) {
        if (filelist.length == 1) {
            print("Trying to open single tiff file:");
            print(parent_dir_path + dir_sep + filelist[0]);
            open(parent_dir_path + dir_sep + filelist[0]);
        } else {
            print("Trying to open TIFF sequence in " + parent_dir_path + "...");
            tryOpenSequenceWithFallback(parent_dir_path, "TIFF");
        }

    } else if (endsWith(first_file_lower, ".jp2")) {
        print("Trying to open JP2 sequence in " + parent_dir_path + "...");
        tryOpenSequenceWithFallback(parent_dir_path, "JP2");

    } else if (endsWith(first_file_lower, ".am")) {
        print("Trying to open Amira file in " + parent_dir_path + "...");
        open(parent_dir_path + dir_sep + filelist[0]);

    } else if (endsWith(first_file_lower, ".nrrd")) {
        print("Trying to open NRRD file in " + parent_dir_path + "...");

        nrrd_input_path = parent_dir_path;
        if (!endsWith(nrrd_input_path, "/") && !endsWith(nrrd_input_path, "\\")) {
            nrrd_input_path = nrrd_input_path + dir_sep;
        }
        nrrd_input_path = nrrd_input_path + filelist[0];
        print("NRRD input path: " + nrrd_input_path);

        n_before_open = nImages;
        print("Trying ImageJ open() for NRRD...");
        open(nrrd_input_path);

        if (nImages <= n_before_open) {
            print("ImageJ open() did not open the NRRD. Trying Bio-Formats...");
            run("Bio-Formats", "open=[" + nrrd_input_path + "] color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
        }

        if (nImages <= n_before_open) {
            exit("Could not open NRRD file: " + nrrd_input_path + "\n\nTried ImageJ open() and Bio-Formats. The old Nrrd Writer command is not used for loading because it opens the writer plugin in this Fiji installation.");
        }

    } else if (endsWith(first_file_lower, ".czi")) {
        print("Trying to open Carl Zeiss image file in " + parent_dir_path + "...");
        open(parent_dir_path + dir_sep + filelist[0]);

    } else {
        abortWithStatus("Unsupported or unrecognized input file type: " + filelist[0]);
    }
}

if (nImages < 1) {
    abortWithStatus("No image stack appears to be open after loading source data. Source folder was: " + parent_dir_path);
}

Stack.getDimensions(width, height, channels, slices, frames);
setSlice(round(slices / 2));
makeRectangle(width / 4, height / 4, width / 2, height / 2);
resetMinAndMax();

getPixelSize(unit, px_size, ph, pd);

rename("original");
selectWindow("original");

// Make sure pixel size is identical in all 3 dimensions.
run(
    "Properties...",
    "channels=1 slices=" + slices + " frames=1 pixel_width=" + px_size +
    " pixel_height=" + px_size + " voxel_depth=" + px_size + " unit=" + unit
);


// -----------------------------------------------------------------------------
// Contrast enhancement
// -----------------------------------------------------------------------------

run("Set Measurements...", "min redirect=None decimal=0");
run("Measure");
Min = getResult("Min");
Max = getResult("Max");

if (isOpen("Results")) {
    selectWindow("Results");
    run("Close");
}

setTool("rectangle");
waitForUser("Contrast rectangle", "Define a rectangle and get grey values for contrast enhancement.");
run("Brightness/Contrast...");
run("Select None");

Dialog.create("Settings");
Dialog.addMessage("Grey-value histogram settings");
Dialog.addMessage("___________________________________");
Dialog.addNumber("Minimum value:", Min, 0, 8, "of histogram");
Dialog.addNumber("Maximum value:", Max, 0, 8, "of histogram");
Dialog.show();

min = Dialog.getNumber();
max = Dialog.getNumber();

print("Shifting grey value histogram...");
run("Select None");
run("Min...", "value=" + min + " stack");
run("Max...", "value=" + max + " stack");


// -----------------------------------------------------------------------------
// Head ROI
// -----------------------------------------------------------------------------

waitForRectangleROI("Head ROI", "Define rectangle for head ROI.");
getSelectionBounds(x_head, y_head, w_head, h_head);

waitForUser(
    "Head z-range",
    "1) Check stack for first and last slice number in z direction of head ROI.\n" +
    "2) Afterwards, click OK."
);
curr_slice = getSliceNumber();

Dialog.create("First and last slice");
Dialog.addMessage("Please enter first and last image slice of head ROI.");
Dialog.addMessage("___________________________________");
Dialog.addNumber("First image:", 1);
Dialog.addNumber("Last image:", curr_slice);
Dialog.show();

first_image_head = Dialog.getNumber();
last_image_head = Dialog.getNumber();
run("Select None");


// -----------------------------------------------------------------------------
// Eye ROIs
// -----------------------------------------------------------------------------

x_eye1 = 0; y_eye1 = 0; w_eye1 = 0; h_eye1 = 0;
first_image_eye1 = 0; last_image_eye1 = 0;
title_eye1 = "";
threshold_eye1 = "NA";

x_eye2 = 0; y_eye2 = 0; w_eye2 = 0; h_eye2 = 0;
first_image_eye2 = 0; last_image_eye2 = 0;
title_eye2 = "";
threshold_eye2 = "NA";

if (has_eye1 == 1) {
    waitForRectangleROI("eye1 ROI", "Define rectangle for eye1 ROI.");
    getSelectionBounds(x_eye1, y_eye1, w_eye1, h_eye1);

    waitForUser(
        "eye1 z-range",
        "1) Check stack for first and last slice number in z direction of eye1 ROI.\n" +
        "2) Afterwards, click OK."
    );
    curr_slice = getSliceNumber();

    Dialog.create("First and last slice");
    Dialog.addMessage("Please enter first and last slice of eye1 ROI.");
    Dialog.addMessage("___________________________________");
    Dialog.addNumber("First image:", 1);
    Dialog.addNumber("Last image:", curr_slice);
    Dialog.show();

    first_image_eye1 = Dialog.getNumber();
    last_image_eye1 = Dialog.getNumber();
    run("Select None");
}

if (has_eye2 == 1) {
    waitForRectangleROI("eye2 ROI", "Define rectangle for eye2 ROI.");
    getSelectionBounds(x_eye2, y_eye2, w_eye2, h_eye2);

    waitForUser(
        "eye2 z-range",
        "1) Check stack for first and last slice number in z direction of eye2 ROI.\n" +
        "2) Afterwards, click OK."
    );
    curr_slice = getSliceNumber();

    Dialog.create("First and last slice");
    Dialog.addMessage("Please enter first and last slice of eye2 ROI.");
    Dialog.addMessage("___________________________________");
    Dialog.addNumber("First image:", 1);
    Dialog.addNumber("Last image:", curr_slice);
    Dialog.show();

    first_image_eye2 = Dialog.getNumber();
    last_image_eye2 = Dialog.getNumber();
    run("Select None");
}


// -----------------------------------------------------------------------------
// Scaling and pixel size
// -----------------------------------------------------------------------------

Dialog.create("Scaling settings");
Dialog.addMessage("Head stack scaling target");
Dialog.addMessage("___________________________________");
Dialog.addNumber("Scale head stack to approximately [MB]:", 120);
Dialog.addMessage("___________________________________");
Dialog.addMessage("PTR / CV3D draft");
Dialog.show();
d_size = Dialog.getNumber() / 1024; // MB / 1024 = GB

Dialog.create("Check pixel size");
Dialog.addNumber("Correct pixel size:", px_size, 9, 15, unit);
Dialog.addString("Unit:", unit);
Dialog.show();

px_size = Dialog.getNumber();
unit = Dialog.getString();

// Set corrected pixel size.
selectWindow("original");
run(
    "Properties...",
    "channels=1 slices=" + slices + " frames=1 pixel_width=" + px_size +
    " pixel_height=" + px_size + " voxel_depth=" + px_size + " unit=" + unit
);


// -----------------------------------------------------------------------------
// Facet size estimate from line selection
// -----------------------------------------------------------------------------

selectWindow("original");
setSlice(round(slices / 2));
setTool("line");
waitForUser(
    "Facet size estimate",
    "Draw a straight line across one representative facet.\n\n" +
    "The macro will read the line length and convert it using the current pixel size.\n" +
    "You can correct the value in the next dialog."
);

facet_line_pixels = "NA";
facet_size_estimate = px_size;
facet_measurement_source = "manual_entry_after_failed_or_missing_line_selection";

if (selectionType() == 5) {
    getLine(x1, y1, x2, y2, line_width);
    facet_line_pixels = sqrt(pow(x2 - x1, 2) + pow(y2 - y1, 2));
    facet_size_estimate = roundSuggested2(facet_line_pixels * px_size);
    facet_measurement_source = "ImageJ_straight_line_selection";
} else {
    waitForUser(
        "No straight line detected",
        "No straight line selection was detected.\n\n" +
        "The next dialog will ask for a manual facet-size estimate."
    );
}

Dialog.create("Facet size estimate");
Dialog.addMessage("Facet-size estimate for CV3D downstream defaults.");
Dialog.addMessage("___________________________________");
facet_size_estimate = roundSuggested2(facet_size_estimate);
Dialog.addNumber("Facet size estimate:", facet_size_estimate, suggestedDecimals(facet_size_estimate), 15, unit);
Dialog.show();

facet_size_estimate = Dialog.getNumber();

facet_csv_text = "";
facet_csv_text = facet_csv_text + "cv_id,facet_size_estimate,unit,measurement_source,line_length_pixels,pixel_size,script_version\n";
facet_csv_text = facet_csv_text + cv_id + "," + facet_size_estimate + "," + unit + "," + facet_measurement_source + "," + facet_line_pixels + "," + px_size + "," + script_version + "\n";
File.saveString(facet_csv_text, facet_size_csv_path);

run("Select None");


// -----------------------------------------------------------------------------
// Convert to 8-bit before cropping/export
// -----------------------------------------------------------------------------

selectWindow("original");
run("Select None");
run("8-bit");


// -----------------------------------------------------------------------------
// Crop and save head NRRD
// -----------------------------------------------------------------------------

selectWindow("original");
run("Duplicate...", "title=head duplicate range=" + first_image_head + "-" + last_image_head);
makeRectangle(x_head, y_head, w_head, h_head);
run("Crop");
title_head = getTitle();

Stack.getDimensions(width_orig, height_orig, channels_head, slices_head, frames_head);
o_size = width_orig * height_orig * slices_head / (1024 * 1024 * 1024);
print("Head crop has a size of approximately " + o_size + " GB.");

d = pow(d_size / o_size, 1 / 3);
perc_d = round(100 * d);
d = perc_d / 100;

if (perc_d < 100) {
    print("Scaling head stack to " + perc_d + "% to reach stack size of approximately " + d_size + " GB...");
    run("Scale...", "x=" + d + " y=" + d + " z=" + d + " interpolation=Bicubic average process create");
    scaled_head_title = getTitle();
    selectWindow(scaled_head_title);
    nrrd_file = head_nrrd_path;
    print("Saving " + nrrd_file + "...");
    saveNrrd(nrrd_file);
    getPixelSize(unit_head, px_size_head, ph_head, pd_head);
} else {
    print("No scaling of head stack necessary.");
    perc_d = 100;
    nrrd_file = head_nrrd_path;
    print("Saving " + nrrd_file + "...");
    saveNrrd(nrrd_file);
    px_size_head = px_size;
    unit_head = unit;
}

requireFile(head_nrrd_path, "head NRRD");


// -----------------------------------------------------------------------------
// Crop and save eye NRRDs
// -----------------------------------------------------------------------------

if (has_eye1 == 1) {
    selectWindow("original");
    run("Duplicate...", "title=eye1 duplicate range=" + first_image_eye1 + "-" + last_image_eye1);
    makeRectangle(x_eye1, y_eye1, w_eye1, h_eye1);
    run("Crop");
    title_eye1 = getTitle();
    rename("eye1");
    title_eye1 = getTitle();

    print(title_eye1 + " -> eye1");
    saveNrrd(eye1_nrrd_path);
    requireFile(eye1_nrrd_path, "eye1 NRRD");
}

if (has_eye2 == 1) {
    selectWindow("original");
    run("Duplicate...", "title=eye2 duplicate range=" + first_image_eye2 + "-" + last_image_eye2);
    makeRectangle(x_eye2, y_eye2, w_eye2, h_eye2);
    run("Crop");
    title_eye2 = getTitle();
    rename("eye2");
    title_eye2 = getTitle();

    print(title_eye2 + " -> eye2");
    saveNrrd(eye2_nrrd_path);
    requireFile(eye2_nrrd_path, "eye2 NRRD");
}


// -----------------------------------------------------------------------------
// Mesh extraction moved to separate macro
// -----------------------------------------------------------------------------

threshold_eye1 = "NA_mesh_extraction_separate";
threshold_eye2 = "NA_mesh_extraction_separate";
print("Mesh/STL extraction is intentionally skipped in this preprocessing macro.");

print("************************************");
print("Creating crop log: " + crop_log_path);

log_text = "";
log_text = log_text + "script_version = " + script_version + "\n";
log_text = log_text + "cv_id = " + cv_id + "\n";
log_text = log_text + "raw_folder = " + parent_dir_path + "\n";
log_text = log_text + "analysis_folder = " + analysis_dir_path + "\n";
log_text = log_text + "active_eyes = " + active_eyes + "\n";
log_text = log_text + "px_size = " + px_size + " " + unit + "\n";
log_text = log_text + "hist_min = " + min + "\n";
log_text = log_text + "hist_max = " + max + "\n";
log_text = log_text + "facet_size_estimate = " + facet_size_estimate + " " + unit + "\n";
log_text = log_text + "facet_measurement_source = " + facet_measurement_source + "\n";
log_text = log_text + "facet_line_pixels = " + facet_line_pixels + "\n";
log_text = log_text + "ROI_head = makeRectangle(" + x_head + ", " + y_head + ", " + w_head + ", " + h_head + ");" + "\n";
log_text = log_text + "z_first_head = " + first_image_head + "\n";
log_text = log_text + "z_last_head = " + last_image_head + "\n";
log_text = log_text + "scaling_head = " + d + "\n";
log_text = log_text + "scaling_head_percent = " + perc_d + "\n";
log_text = log_text + "px_size_head = " + px_size_head + " " + unit_head + "\n";
log_text = log_text + "head_nrrd = " + head_nrrd_rel + "\n";

if (has_eye1 == 1) {
    log_text = log_text + "ROI_eye1 = makeRectangle(" + x_eye1 + ", " + y_eye1 + ", " + w_eye1 + ", " + h_eye1 + ");" + "\n";
    log_text = log_text + "z_first_eye1 = " + first_image_eye1 + "\n";
    log_text = log_text + "z_last_eye1 = " + last_image_eye1 + "\n";
    log_text = log_text + "threshold_eye1 = " + threshold_eye1 + "\n";
    log_text = log_text + "eye1_nrrd = " + eye1_nrrd_rel + "\n";
}
if (has_eye2 == 1) {
    log_text = log_text + "ROI_eye2 = makeRectangle(" + x_eye2 + ", " + y_eye2 + ", " + w_eye2 + ", " + h_eye2 + ");" + "\n";
    log_text = log_text + "z_first_eye2 = " + first_image_eye2 + "\n";
    log_text = log_text + "z_last_eye2 = " + last_image_eye2 + "\n";
    log_text = log_text + "threshold_eye2 = " + threshold_eye2 + "\n";
    log_text = log_text + "eye2_nrrd = " + eye2_nrrd_rel + "\n";
}
File.saveString(log_text, crop_log_path);
print("************************************");


// -----------------------------------------------------------------------------
// Final validation/status
// -----------------------------------------------------------------------------

requireFile(head_nrrd_path, "head NRRD");
requireFile(facet_size_csv_path, "facet-size estimate CSV");
requireFile(crop_log_path, "crop log");

if (has_eye1 == 1) {
    requireFile(eye1_nrrd_path, "eye1 NRRD");
}

if (has_eye2 == 1) {
    requireFile(eye2_nrrd_path, "eye2 NRRD");
}

final_status = "partial_without_stl";
final_message = "ImageJ preprocessing finished successfully. Mesh/STL extraction is handled by the separate CV3D mesh extraction macro.";

writeCv3dStatus(final_status, final_message);

print("All done!");
print("Status: " + final_status);
print("Message: " + final_message);
print("************************************");
closeImageJAfterCv3d();
