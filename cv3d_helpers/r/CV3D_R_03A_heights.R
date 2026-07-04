#!/usr/bin/env Rscript

# CV3D Step 03A: STL triangle-centre/normal extraction + local height calculation
#
# Usage:
#   Rscript CV3D_R_step03A_local_heights.R <task_json>
#
# The task JSON is written by the CV3D Python controller.
# The CompoundVision3D R package must be installed, normally from:
#   remotes::install_github("Pete-s-Lab/CompoundVision3D")

options(warn = 1)
options(rgl.useNULL = TRUE)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript CV3D_R_step03A_local_heights.R <task_json>", call. = FALSE)
}

task_json <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

load_json <- function(path) {
  if (requireNamespace("jsonlite", quietly = TRUE)) {
    return(jsonlite::fromJSON(path, simplifyVector = TRUE))
  }
  if (requireNamespace("rjson", quietly = TRUE)) {
    return(rjson::fromJSON(file = path))
  }
  stop("Need either the 'jsonlite' or 'rjson' package to read task JSON.", call. = FALSE)
}

write_json <- function(x, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  if (requireNamespace("jsonlite", quietly = TRUE)) {
    json <- jsonlite::toJSON(x, auto_unbox = TRUE, pretty = TRUE, null = "null")
    writeLines(json, path, useBytes = TRUE)
    return(invisible(path))
  }
  if (requireNamespace("rjson", quietly = TRUE)) {
    json <- rjson::toJSON(x)
    writeLines(json, path, useBytes = TRUE)
    return(invisible(path))
  }
  # Last-resort plain status text with .json extension, only used if JSON packages are unavailable.
  writeLines(paste(names(x), unlist(x), sep = "=", collapse = "\n"), path, useBytes = TRUE)
  invisible(path)
}

status_payload <- function(task, status, message, extra = list()) {
  base <- list(
    status_version = "0.1",
    script_version = "CV3D_R_step03A_local_heights_0.3.2_search_diam_prompt",
    status = status,
    message = message,
    cv_id = task$cv_id,
    eye = task$eye,
    step_id = "03a_local_height_calculation",
    input_cornea_stl_abs = task$input_cornea_stl_abs,
    output_triangles_normals_abs = task$output_triangles_normals_abs,
    output_local_heights_abs = task$output_local_heights_abs,
    output_threshold_plot_abs = task$output_threshold_plot_abs,
    facet_size_estimate = task$facet_size_estimate,
    max_cores = task$max_cores
  )
  utils::modifyList(base, extra)
}

task <- load_json(task_json)

status_file <- task$status_file_abs
if (is.null(status_file) || is.na(status_file) || status_file == "") {
  stop("Task JSON has no status_file_abs.", call. = FALSE)
}

write_status <- function(status, message, extra = list()) {
  write_json(status_payload(task, status, message, extra), status_file)
}

tryCatch({
  write_status("running", "Step 03A R runner started.")

  # Resolve and validate paths -------------------------------------------------
  input_stl <- normalizePath(task$input_cornea_stl_abs, winslash = "/", mustWork = TRUE)

  out_triangles <- task$output_triangles_normals_abs
  out_heights <- task$output_local_heights_abs
  out_plot <- task$output_threshold_plot_abs

  dir.create(dirname(out_triangles), recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(out_heights), recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(out_plot), recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)

  facet_size <- as.numeric(task$facet_size_estimate)
  if (!is.finite(facet_size) || facet_size <= 0) {
    stop("Invalid facet_size_estimate in task JSON: ", task$facet_size_estimate, call. = FALSE)
  }

  search_diam <- suppressWarnings(as.numeric(task$local_height_search_diam))
  if (!is.finite(search_diam) || search_diam <= 0) {
    search_diam <- facet_size * 3
    message("No valid local_height_search_diam in task JSON; falling back to facet_size_estimate * 3 = ", search_diam)
  }

  max_cores <- as.integer(task$max_cores)
  if (!is.finite(max_cores) || max_cores < 1) max_cores <- 1

  invert <- FALSE
  if (!is.null(task$invert_local_heights)) {
    invert <- isTRUE(task$invert_local_heights)
  }

  # Load installed CompoundVision3D package ------------------------------------
  if (!requireNamespace("CompoundVision3D", quietly = TRUE)) {
    stop(
      "The CompoundVision3D R package is not installed. ",
      "Install it with remotes::install_github('Pete-s-Lab/CompoundVision3D') or use the GUI install button.",
      call. = FALSE
    )
  }
  suppressPackageStartupMessages(library(CompoundVision3D))

  # Required dependencies used directly here.
  suppressPackageStartupMessages(requireNamespace("readr"))
  suppressPackageStartupMessages(requireNamespace("dplyr"))

  # 1) STL triangles -> triangle-centre/normal tibble ------------------------
  # We call STL_triangles() directly because the older convert_STL_to_tibble()
  # wrapper enforces a historical *_surface.stl filename suffix.
  message("Importing STL triangles: ", input_stl)
  triangles <- STL_triangles(file_name = input_stl, plot_results = FALSE, verbose = TRUE)
  # Coordinates are used exactly as exported by Blender/STL.
  # No automatic *1000 scaling is applied here.

  readr::write_csv(triangles, out_triangles, progress = FALSE)

  # 2) Raw local heights only --------------------------------------------------
  message("Calculating RAW local heights only with facet_size_estimate = ", facet_size, ", search_diam = ", search_diam, " and cores = ", max_cores)
  message("Normalization is intentionally NOT run in Step 03A.")

  heights <- calculate_local_heights(
    df = triangles,
    search_diam = search_diam,
    cores = max_cores,
    plot_file = NULL,
    verbose = TRUE,
    invert = invert
  )

  if (!"local_height" %in% names(heights)) {
    stop("calculate_local_heights() returned no 'local_height' column.", call. = FALSE)
  }

  finite_local_heights <- is.finite(as.numeric(heights$local_height))
  if (!any(finite_local_heights)) {
    stop("calculate_local_heights() returned no finite raw local_height values.", call. = FALSE)
  }

  # Step 03A output must not contain fake fallback-normalized values.
  # Normalization will be handled by a separate optional step later.
  forbidden_norm_cols <- intersect(
    names(heights),
    c(
      "local_height_norm",
      "local_height_norm_col",
      "local_height_log_norm",
      "local_height_log_norm_col",
      "normalized_local_height",
      "normalized_local_height_col"
    )
  )
  if (length(forbidden_norm_cols) > 0) {
    heights <- heights[, setdiff(names(heights), forbidden_norm_cols), drop = FALSE]
  }

  readr::write_csv(heights, out_heights, progress = FALSE)

  # 3) Threshold/inspection plot ---------------------------------------------
  png(filename = out_plot, width = 1800, height = 600, res = 150)
  old_par <- par(no.readonly = TRUE)
  on.exit({
    try(par(old_par), silent = TRUE)
    try(dev.off(), silent = TRUE)
  }, add = TRUE)

  par(mfrow = c(1, 3))

  raw_col <- if ("local_height_col" %in% names(heights)) heights$local_height_col else "black"
  filtered_col <- if ("local_height_filterd_col" %in% names(heights)) heights$local_height_filterd_col else raw_col
  log_values <- if ("local_height_log" %in% names(heights)) heights$local_height_log else log10(abs(heights$local_height) + .Machine$double.eps)
  log_col <- if ("local_height_log_col" %in% names(heights)) heights$local_height_log_col else filtered_col

  plot(
    heights$local_height,
    col = raw_col,
    pch = 16,
    cex = 0.25,
    main = "raw local height",
    xlab = "triangle index",
    ylab = "local_height"
  )
  plot(
    heights$local_height,
    col = filtered_col,
    pch = 16,
    cex = 0.25,
    main = "raw height, clipped colours",
    xlab = "triangle index",
    ylab = "local_height"
  )
  plot(
    log_values,
    col = log_col,
    pch = 16,
    cex = 0.25,
    main = "log display only",
    xlab = "triangle index",
    ylab = "log display value"
  )
  dev.off()

  # Final validation ----------------------------------------------------------
  required <- c(out_triangles, out_heights, out_plot)
  missing <- required[!file.exists(required)]
  if (length(missing) > 0) {
    stop("Step 03A finished but required output file(s) are missing: ", paste(missing, collapse = "; "), call. = FALSE)
  }

  write_status(
    "success",
    "Step 03A local height calculation completed.",
    list(
      summary = list(
        triangle_count = nrow(triangles),
        local_height_count = nrow(heights),
        facet_size_estimate = facet_size,
        local_height_search_diam = search_diam,
        max_cores_used = max_cores,
        scaled_stl_coordinates_by_1000 = FALSE,
        normalization_performed = FALSE,
        finite_local_height_count = sum(is.finite(as.numeric(heights$local_height))),
        local_height_min = min(as.numeric(heights$local_height), na.rm = TRUE),
        local_height_max = max(as.numeric(heights$local_height), na.rm = TRUE)
      )
    )
  )

  message("CV3D Step 03A completed successfully.")

}, error = function(e) {
  msg <- conditionMessage(e)
  try(write_status("failed", msg), silent = TRUE)
  message("CV3D Step 03A failed: ", msg)
  quit(status = 1, save = "no")
})
