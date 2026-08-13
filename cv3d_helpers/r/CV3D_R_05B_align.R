#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript CV3D_R_05B_align.R <task_json>", call. = FALSE)

task_json <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0 || all(is.na(x))) y else x
}

safe_require <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    stop("Required R package is not installed: ", pkg, call. = FALSE)
  }
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

safe_require("jsonlite")
safe_require("readr")
safe_require("dplyr")
safe_require("tibble")
safe_require("CV3D")

SCRIPT_VERSION <- "0.2.3-croplog-encoding-safe-roi-translation"
SCRIPT_NAME <- "CV3D_R_05B_align.R"

task <- jsonlite::fromJSON(task_json, simplifyVector = TRUE)
status_file <- task$status_file_abs

write_status <- function(status, message, extra = list()) {
  if (is.null(status_file) || length(status_file) == 0 || is.na(status_file)) return(invisible(NULL))
  payload <- c(
    list(
      status = status,
      message = message,
      task_json = task_json,
      script_name = SCRIPT_NAME,
      script_version = SCRIPT_VERSION
    ),
    extra
  )
  dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(payload, status_file, pretty = TRUE, auto_unbox = TRUE, null = "null")
}

need_cols <- function(df, cols, label) {
  missing <- setdiff(cols, names(df))
  if (length(missing) > 0) {
    stop(label, " is missing required column(s): ", paste(missing, collapse = ", "), call. = FALSE)
  }
}

write_csv_safe <- function(df, path) {
  if (is.null(path) || length(path) == 0 || is.na(path) || !nzchar(as.character(path[[1]]))) return(invisible(NULL))
  dir.create(dirname(as.character(path[[1]])), recursive = TRUE, showWarnings = FALSE)
  readr::write_csv(df, as.character(path[[1]]))
}

normalise_task_path <- function(path, label, mustWork = TRUE) {
  if (is.null(path) || length(path) == 0 || is.na(path) || !nzchar(as.character(path[[1]]))) {
    stop("Missing required task field for ", label, ".", call. = FALSE)
  }
  normalizePath(as.character(path[[1]]), winslash = "/", mustWork = mustWork)
}

first_non_null <- function(...) {
  vals <- list(...)
  for (v in vals) {
    if (!is.null(v) && length(v) > 0 && !all(is.na(v))) return(v)
  }
  NULL
}

trim_ws <- function(x) {
  # Use byte-wise trimming because ImageJ/Fiji crop logs can contain unit symbols
  # that are not valid in the active Windows R locale. Keys are ASCII; numeric
  # parsing below is also byte-wise.
  gsub("^[ \t\r\n]+|[ \t\r\n]+$", "", as.character(x), useBytes = TRUE)
}

normalize_token <- function(x) {
  x <- as.character(x)
  x <- suppressWarnings(iconv(x, from = "", to = "ASCII//TRANSLIT", sub = "_"))
  x[is.na(x)] <- ""
  x <- tolower(x)
  x <- gsub("[^a-z0-9]+", "_", x, useBytes = TRUE)
  x <- gsub("^_+|_+$", "", x, useBytes = TRUE)
  x
}

parse_numbers <- function(x) {
  # Keep this byte-wise: the value may contain a non-ASCII unit such as a micro
  # sign from ImageJ, and Windows R may otherwise throw "input string ... is invalid".
  x <- as.character(x)
  x <- gsub("[^0-9eE+\\.\\-]+", " ", x, useBytes = TRUE)
  x <- trim_ws(x)
  if (!nzchar(x)) return(numeric(0))
  parts <- unlist(strsplit(x, "[ \t\r\n]+", perl = FALSE, useBytes = TRUE), use.names = FALSE)
  parts <- parts[nzchar(parts)]
  suppressWarnings(as.numeric(parts[is.finite(suppressWarnings(as.numeric(parts)))]))
}

parse_first_number <- function(x, label) {
  nums <- parse_numbers(x)
  if (length(nums) < 1 || !is.finite(nums[[1]])) {
    stop("Could not parse numeric value for ", label, " from: ", as.character(x), call. = FALSE)
  }
  nums[[1]]
}

read_crop_log_lines <- function(path) {
  # Read as raw bytes first. This avoids locale-dependent failures on crop-log
  # lines containing unit symbols, especially "um" with a micro sign.
  n <- file.info(path)$size
  if (is.na(n) || n <= 0) return(character(0))
  con <- file(path, open = "rb")
  on.exit(close(con), add = TRUE)
  raw <- readBin(con, what = "raw", n = n)
  txt <- rawToChar(raw)

  txt_utf8 <- suppressWarnings(iconv(txt, from = "UTF-8", to = "UTF-8", sub = " "))
  if (length(txt_utf8) == 1 && !is.na(txt_utf8)) {
    txt <- txt_utf8
  } else {
    txt_latin1 <- suppressWarnings(iconv(txt, from = "latin1", to = "UTF-8", sub = " "))
    if (length(txt_latin1) == 1 && !is.na(txt_latin1)) txt <- txt_latin1
  }

  unlist(strsplit(txt, "\\r\\n|\\n|\\r", perl = TRUE, useBytes = TRUE), use.names = FALSE)
}

read_crop_log_key_values <- function(path) {
  lines <- read_crop_log_lines(path)
  lines <- trim_ws(lines)
  lines <- lines[nzchar(lines)]
  lines <- lines[!grepl("^#", lines, useBytes = TRUE)]
  has_eq <- grepl("=", lines, fixed = TRUE, useBytes = TRUE)
  if (!any(has_eq)) {
    stop(
      "Crop log is not in the expected ImageJ key-value format. Expected lines such as ",
      "'px_size = ...' and 'ROI_eye1 = makeRectangle(...)'. File: ", path,
      call. = FALSE
    )
  }
  lines <- lines[has_eq]
  keys <- trim_ws(sub("=.*$", "", lines, useBytes = TRUE))
  vals <- trim_ws(sub("^[^=]*=", "", lines, useBytes = TRUE))
  names(vals) <- keys
  vals
}

crop_get <- function(kv, key, required = TRUE) {
  if (key %in% names(kv)) return(unname(kv[[key]]))
  key_norm <- normalize_token(key)
  nms_norm <- normalize_token(names(kv))
  idx <- which(nms_norm == key_norm)
  if (length(idx) >= 1) return(unname(kv[[idx[[1]]]]))
  if (required) {
    stop("Crop log is missing required key: ", key, call. = FALSE)
  }
  NULL
}

parse_roi_origin_from_crop_log <- function(kv, roi_label) {
  roi_key <- paste0("ROI_", roi_label)
  roi_value <- crop_get(kv, roi_key, required = TRUE)
  nums <- parse_numbers(roi_value)
  if (length(nums) < 4) {
    stop("Could not parse ", roi_key, " as makeRectangle(x, y, width, height): ", roi_value, call. = FALSE)
  }

  z_key <- paste0("z_first_", roi_label)
  z_first <- parse_first_number(crop_get(kv, z_key, required = TRUE), z_key)

  # ImageJ stack ranges are 1-based. Local NRRD/STL coordinates start at z = 0,
  # so the original-stack z origin in pixel units is first_slice - 1.
  # For eye-minus-head translation this is equivalent to z_first_eye - z_first_head.
  c(x = nums[[1]], y = nums[[2]], z = z_first - 1, width = nums[[3]], height = nums[[4]])
}

get_task_numeric_vector <- function(task) {
  p <- task$parameters
  raw <- first_non_null(
    task$px_size_um, task$pixel_size_um, task$voxel_size_um,
    task$px_size, task$pixel_size, task$voxel_size,
    p$px_size_um, p$pixel_size_um, p$voxel_size_um,
    p$px_size, p$pixel_size, p$voxel_size
  )
  if (is.null(raw)) return(NULL)
  if (is.data.frame(raw)) raw <- as.list(raw[1, , drop = TRUE])
  if (is.list(raw) && !is.null(names(raw)) && length(names(raw)) > 0) {
    nms <- normalize_token(names(raw))
    names(raw) <- nms
    x <- first_non_null(raw$x, raw$px_size_x_um, raw$pixel_size_x_um, raw$voxel_size_x_um, raw$px_size_x, raw$pixel_size_x, raw$voxel_size_x)
    y <- first_non_null(raw$y, raw$px_size_y_um, raw$pixel_size_y_um, raw$voxel_size_y_um, raw$px_size_y, raw$pixel_size_y, raw$voxel_size_y)
    z <- first_non_null(raw$z, raw$px_size_z_um, raw$pixel_size_z_um, raw$voxel_size_z_um, raw$px_size_z, raw$pixel_size_z, raw$voxel_size_z)
    if (!is.null(x) && !is.null(y) && !is.null(z)) {
      return(c(x = as.numeric(x[[1]]), y = as.numeric(y[[1]]), z = as.numeric(z[[1]])))
    }
  }
  if (is.character(raw) && length(raw) == 1) {
    raw <- strsplit(raw, "[,;[:space:]]+")[[1]]
    raw <- raw[nzchar(raw)]
  }
  raw_num <- suppressWarnings(as.numeric(unlist(raw)))
  raw_num <- raw_num[is.finite(raw_num)]
  if (length(raw_num) == 1) return(c(x = raw_num[[1]], y = raw_num[[1]], z = raw_num[[1]]))
  if (length(raw_num) >= 3) return(c(x = raw_num[[1]], y = raw_num[[2]], z = raw_num[[3]]))
  NULL
}

get_px_size_um <- function(task, crop_log_kv) {
  # In the bundled ImageJ preprocessing macro the original stack calibration is
  # written to 01_<cv_id>_crop.log as: px_size = <value> <unit>
  # This is the value needed for ROI-origin translation. Do not use px_size_head;
  # that can differ after optional head-stack downscaling.
  raw_crop <- first_non_null(
    crop_get(crop_log_kv, "px_size", required = FALSE),
    crop_get(crop_log_kv, "pixel_size", required = FALSE),
    crop_get(crop_log_kv, "voxel_size", required = FALSE)
  )
  if (!is.null(raw_crop)) {
    px <- parse_first_number(raw_crop, "crop log px_size")
    return(c(x = px, y = px, z = px))
  }

  from_task <- get_task_numeric_vector(task)
  if (!is.null(from_task)) return(from_task)

  stop(
    "Missing pixel size. Expected 'px_size = <value> <unit>' in the ImageJ crop log ",
    "or a task/parameters field named px_size, pixel_size, voxel_size, or *_um.",
    call. = FALSE
  )
}

add_missing_cols <- function(df, cols) {
  for (nm in setdiff(cols, names(df))) df[[nm]] <- NA
  df[, cols, drop = FALSE]
}

select_existing_cols <- function(df, cols) {
  cols <- cols[cols %in% names(df)]
  df[, unique(cols), drop = FALSE]
}

make_roi_reference <- function(kv, task) {
  eye_label <- as.character(first_non_null(task$eye, task$parameters$eye_roi_label, "eye1")[[1]])
  head_label <- as.character(first_non_null(task$parameters$head_roi_label, "head")[[1]])
  explicit_eye_label <- first_non_null(task$parameters$eye_roi_label, task$eye_roi_label)
  if (!is.null(explicit_eye_label)) eye_label <- as.character(explicit_eye_label[[1]])

  px_size_um <- get_px_size_um(task, kv)
  if (any(!is.finite(px_size_um)) || any(px_size_um <= 0)) {
    stop("Pixel size must be positive finite numeric x/y/z values.", call. = FALSE)
  }

  head_origin <- parse_roi_origin_from_crop_log(kv, head_label)
  eye_origin <- parse_roi_origin_from_crop_log(kv, eye_label)

  head_origin_px <- head_origin[c("x", "y", "z")]
  eye_origin_px <- eye_origin[c("x", "y", "z")]
  translation_px <- eye_origin_px - head_origin_px
  translation_um <- translation_px * px_size_um

  roi_reference <- tibble::tibble(
    roi = c("head", "eye", "eye_minus_head_translation"),
    crop_log_label = c(head_label, eye_label, NA_character_),
    x_px = c(head_origin_px[["x"]], eye_origin_px[["x"]], translation_px[["x"]]),
    y_px = c(head_origin_px[["y"]], eye_origin_px[["y"]], translation_px[["y"]]),
    z_px = c(head_origin_px[["z"]], eye_origin_px[["z"]], translation_px[["z"]]),
    width_px = c(head_origin[["width"]], eye_origin[["width"]], NA_real_),
    height_px = c(head_origin[["height"]], eye_origin[["height"]], NA_real_),
    px_size_x_um = px_size_um[["x"]],
    px_size_y_um = px_size_um[["y"]],
    px_size_z_um = px_size_um[["z"]],
    x_um = c(head_origin_px[["x"]] * px_size_um[["x"]], eye_origin_px[["x"]] * px_size_um[["x"]], translation_um[["x"]]),
    y_um = c(head_origin_px[["y"]] * px_size_um[["y"]], eye_origin_px[["y"]] * px_size_um[["y"]], translation_um[["y"]]),
    z_um = c(head_origin_px[["z"]] * px_size_um[["z"]], eye_origin_px[["z"]] * px_size_um[["z"]], translation_um[["z"]])
  )

  list(
    eye_label = eye_label,
    head_label = head_label,
    px_size_um = px_size_um,
    head_origin_px = head_origin_px,
    eye_origin_px = eye_origin_px,
    translation_px = translation_px,
    translation_um = translation_um,
    roi_reference = roi_reference
  )
}

main <- function() {
  optic_file <- normalise_task_path(task$input_optic_parameters_abs, "05A optic-parameter table", mustWork = TRUE)
  landmarks_file <- normalise_task_path(task$input_landmarks_abs, "head landmark table", mustWork = TRUE)
  crop_log_file <- normalise_task_path(task$input_crop_log_abs, "ImageJ crop log", mustWork = TRUE)

  message("Reading 05A optic parameters: ", optic_file)
  optic <- suppressMessages(readr::read_csv(optic_file, show_col_types = FALSE))
  need_cols(optic, c("facet_id", "x", "y", "z", "norm.x", "norm.y", "norm.z"), "05A optic-parameter table")

  message("Reading head landmarks: ", landmarks_file)
  landmarks <- suppressMessages(readr::read_csv(landmarks_file, show_col_types = FALSE))
  need_cols(landmarks, c("landmark", "x", "y", "z"), "Head landmark table")

  message("Reading ImageJ crop log: ", crop_log_file)
  crop_log <- read_crop_log_key_values(crop_log_file)
  roi <- make_roi_reference(crop_log, task)

  message(
    "Applying ImageJ ROI translation before landmark alignment: dx=", round(roi$translation_um[["x"]], 6),
    " um, dy=", round(roi$translation_um[["y"]], 6),
    " um, dz=", round(roi$translation_um[["z"]], 6), " um"
  )

  names_needed <- c("anterior", "posterior", "left", "right")
  missing_lm <- setdiff(names_needed, landmarks$landmark)
  if (length(missing_lm) > 0) {
    stop("Missing landmark(s): ", paste(missing_lm, collapse = ", "), call. = FALSE)
  }

  facets_ref <- optic %>%
    dplyr::mutate(
      cv_id = task$cv_id,
      eye = task$eye,
      point_id = as.character(facet_id),
      point_type = "facet",
      landmark = NA_character_,
      ID = as.character(facet_id),
      type = "facet",
      x_original = as.numeric(x),
      y_original = as.numeric(y),
      z_original = as.numeric(z),
      norm.x_original = as.numeric(norm.x),
      norm.y_original = as.numeric(norm.y),
      norm.z_original = as.numeric(norm.z),
      x_reference = as.numeric(x) + roi$translation_um[["x"]],
      y_reference = as.numeric(y) + roi$translation_um[["y"]],
      z_reference = as.numeric(z) + roi$translation_um[["z"]],
      norm.x_reference = as.numeric(norm.x),
      norm.y_reference = as.numeric(norm.y),
      norm.z_reference = as.numeric(norm.z),
      x = x_reference,
      y = y_reference,
      z = z_reference
    )

  lm_ref <- landmarks %>%
    dplyr::filter(landmark %in% names_needed) %>%
    dplyr::transmute(
      cv_id = task$cv_id,
      eye = task$eye,
      facet_id = NA_character_,
      point_id = as.character(landmark),
      point_type = "LM",
      landmark = as.character(landmark),
      ID = as.character(landmark),
      type = "LM",
      x_original = as.numeric(x),
      y_original = as.numeric(y),
      z_original = as.numeric(z),
      norm.x_original = NA_real_,
      norm.y_original = NA_real_,
      norm.z_original = NA_real_,
      x_reference = as.numeric(x),
      y_reference = as.numeric(y),
      z_reference = as.numeric(z),
      norm.x_reference = NA_real_,
      norm.y_reference = NA_real_,
      norm.z_reference = NA_real_,
      x = x_reference,
      y = y_reference,
      z = z_reference,
      norm.x = NA_real_,
      norm.y = NA_real_,
      norm.z = NA_real_,
      facet_size = NA_real_,
      facet_size_smoothed = NA_real_
    )

  common_cols <- union(names(facets_ref), names(lm_ref))
  combined <- dplyr::bind_rows(add_missing_cols(facets_ref, common_cols), add_missing_cols(lm_ref, common_cols))

  reference_cols <- c(
    "cv_id", "eye", "point_id", "point_type", "landmark", "facet_id", "internal_ID", "ID", "type",
    "x_original", "y_original", "z_original",
    "x_reference", "y_reference", "z_reference",
    "norm.x_original", "norm.y_original", "norm.z_original",
    "norm.x_reference", "norm.y_reference", "norm.z_reference",
    "facet_size", "facet_size_smoothed", "interfacet_angle_deg", "interfacet_angle_rad", "sampling_lattice", "eye_parameter", "sampling_frequency_rad", "acuity_cpd", "number_of_neighbours", "neighbours"
  )
  reference_pointcloud <- select_existing_cols(combined, reference_cols)

  priority <- as.character(task$parameters$priority %||% "RL")
  if (!priority %in% c("RL", "AP")) priority <- "RL"

  message("Running CV3D::align_pointcloud() with priority=", priority)
  aligned <- CV3D::align_pointcloud(
    df = combined,
    coord_x = "x", coord_y = "y", coord_z = "z",
    vector_x = "norm.x", vector_y = "norm.y", vector_z = "norm.z",
    landmark_col = "ID",
    landmark_names = list(anterior = "anterior", posterior = "posterior", left = "left", right = "right"),
    priority = priority
  )

  rotation_matrix <- attr(aligned, "rotation_matrix_rows_xyz")
  if (is.null(rotation_matrix)) {
    stop("align_pointcloud() did not return attribute 'rotation_matrix_rows_xyz'.", call. = FALSE)
  }
  translation <- attr(aligned, "translation_applied")

  aligned_pointcloud <- aligned %>%
    dplyr::mutate(
      x_global = as.numeric(x),
      y_global = as.numeric(y),
      z_global = as.numeric(z),
      norm.x_global = suppressWarnings(as.numeric(norm.x)),
      norm.y_global = suppressWarnings(as.numeric(norm.y)),
      norm.z_global = suppressWarnings(as.numeric(norm.z))
    ) %>%
    select_existing_cols(c(
      "cv_id", "eye", "point_id", "point_type", "landmark", "facet_id", "internal_ID", "ID", "type",
      "x_original", "y_original", "z_original",
      "x_reference", "y_reference", "z_reference",
      "x_global", "y_global", "z_global",
      "norm.x_original", "norm.y_original", "norm.z_original",
      "norm.x_reference", "norm.y_reference", "norm.z_reference",
      "norm.x_global", "norm.y_global", "norm.z_global",
      "facet_size", "facet_size_smoothed", "interfacet_angle_deg", "interfacet_angle_rad", "sampling_lattice", "eye_parameter", "sampling_frequency_rad", "acuity_cpd", "number_of_neighbours", "neighbours"
    ))

  facets_out <- aligned_pointcloud %>%
    dplyr::filter(point_type == "facet") %>%
    select_existing_cols(c(
      "cv_id", "eye", "facet_id", "internal_ID",
      "x_original", "y_original", "z_original",
      "x_reference", "y_reference", "z_reference",
      "x_global", "y_global", "z_global",
      "norm.x_original", "norm.y_original", "norm.z_original",
      "norm.x_reference", "norm.y_reference", "norm.z_reference",
      "norm.x_global", "norm.y_global", "norm.z_global",
      "facet_size", "facet_size_smoothed", "interfacet_angle_deg", "interfacet_angle_rad", "sampling_lattice", "eye_parameter", "sampling_frequency_rad", "acuity_cpd", "number_of_neighbours", "neighbours"
    ))

  matrix_rows <- tibble::tibble(
    row = rep(c("x", "y", "z"), each = 3),
    col = rep(c("input_x", "input_y", "input_z"), times = 3),
    value = as.numeric(t(rotation_matrix))
  )

  write_csv_safe(reference_pointcloud, task$output_landmark_referenced_coordinates_abs)
  write_csv_safe(aligned_pointcloud, task$output_global_aligned_pointcloud_abs)
  write_csv_safe(facets_out, task$output_global_coordinates_abs)
  write_csv_safe(matrix_rows, task$output_global_rotation_matrix_abs)

  roi_reference_out <- first_non_null(
    task$output_roi_reference_abs,
    task$output_global_coordinate_roi_reference_abs,
    task$parameters$output_roi_reference_abs
  )
  if (is.null(roi_reference_out)) {
    meta_path <- task$output_global_coordinate_metadata_abs
    if (!is.null(meta_path) && length(meta_path) > 0 && !is.na(meta_path) && nzchar(as.character(meta_path[[1]]))) {
      roi_reference_out <- sub("\\.json$", "_roi_reference.csv", as.character(meta_path[[1]]), ignore.case = TRUE)
    }
  }
  write_csv_safe(roi$roi_reference, roi_reference_out)

  metadata <- list(
    cv_id = task$cv_id,
    eye = task$eye,
    script_version = SCRIPT_VERSION,
    alignment_method = "crop_log_roi_translation_then_landmark_align_pointcloud",
    priority = priority,
    required_landmarks = names_needed,
    crop_log = crop_log_file,
    crop_log_format = "ImageJ key-value text log",
    crop_log_px_size_key = "px_size",
    head_roi_key = paste0("ROI_", roi$head_label),
    eye_roi_key = paste0("ROI_", roi$eye_label),
    z_origin_rule = "z_px = z_first - 1; translation uses eye z_first minus head z_first",
    px_size_um = as.list(roi$px_size_um),
    head_origin_px = as.list(roi$head_origin_px),
    eye_origin_px = as.list(roi$eye_origin_px),
    roi_translation_px = as.list(roi$translation_px),
    roi_translation_um = as.list(roi$translation_um),
    landmark_alignment_translation_applied = as.numeric(translation),
    rotation_matrix_rows_xyz = unname(rotation_matrix),
    input_optic_parameters = task$input_optic_parameters,
    input_landmarks = task$input_landmarks,
    input_crop_log = task$input_crop_log,
    output_landmark_referenced_coordinates = task$output_landmark_referenced_coordinates,
    output_global_aligned_pointcloud = task$output_global_aligned_pointcloud,
    output_global_coordinates = task$output_global_coordinates,
    output_roi_reference = roi_reference_out
  )
  dir.create(dirname(task$output_global_coordinate_metadata_abs), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(metadata, task$output_global_coordinate_metadata_abs, pretty = TRUE, auto_unbox = TRUE, null = "null")

  write_status("success", "05B crop-log ROI translation plus landmark alignment completed successfully.", list(summary = list(
    facet_count = nrow(facets_out),
    point_count = nrow(aligned_pointcloud),
    priority = priority,
    alignment_method = "crop_log_roi_translation_then_landmark_align_pointcloud",
    roi_translation_um = as.list(roi$translation_um),
    output_landmark_referenced_coordinates = task$output_landmark_referenced_coordinates,
    output_global_aligned_pointcloud = task$output_global_aligned_pointcloud,
    output_global_coordinates = task$output_global_coordinates,
    output_roi_reference = roi_reference_out
  )))
}

tryCatch(main(), error = function(e) {
  msg <- conditionMessage(e)
  message("CV3D 05B alignment failed: ", msg)
  write_status("failed", msg, list(traceback = paste(utils::capture.output(traceback()), collapse = "\n")))
  quit(status = 1, save = "no")
})
