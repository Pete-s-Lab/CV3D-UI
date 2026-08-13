#!/usr/bin/env Rscript

# CV3D Step 03A2: Optional local-height normalization
#
# Usage:
#   Rscript CV3D_R_step03A2_normalize_local_heights_v0_1_0.R <task_json>
#
# The task JSON is written by the CV3D Python controller.
# The CV3D R package must be installed, normally from:
#   remotes::install_github("Pete-s-Lab/CV3D")

options(warn = 1)
options(rgl.useNULL = TRUE)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript CV3D_R_step03A2_normalize_local_heights_v0_1_0.R <task_json>", call. = FALSE)
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
  writeLines(paste(names(x), unlist(x), sep = "=", collapse = "\n"), path, useBytes = TRUE)
  invisible(path)
}

status_payload <- function(task, status, message, extra = list()) {
  base <- list(
    status_version = "0.1",
    script_version = "CV3D_R_step03A2_normalize_local_heights_0.1.1",
    status = status,
    message = message,
    cv_id = task$cv_id,
    eye = task$eye,
    step_id = "03a2_local_height_normalization",
    input_local_heights_abs = task$input_local_heights_abs,
    output_local_heights_normalized_abs = task$output_local_heights_normalized_abs,
    output_normalization_plot_abs = task$output_normalization_plot_abs,
    neighbourhood_radius = task$neighbourhood_radius,
    column_to_normalize = task$column_to_normalize,
    max_cores = task$max_cores
  )
  utils::modifyList(base, extra)
}

scalar_numeric_or <- function(x, default = NA_real_) {
  value <- suppressWarnings(as.numeric(x))
  if (length(value) < 1 || !is.finite(value[[1]])) {
    return(default)
  }
  value[[1]]
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
  write_status("running", "Optional Step 03A2 normalization runner started.")

  # Resolve and validate paths -------------------------------------------------
  input_local_heights <- normalizePath(task$input_local_heights_abs, winslash = "/", mustWork = TRUE)
  out_normalized <- task$output_local_heights_normalized_abs
  out_plot <- task$output_normalization_plot_abs

  dir.create(dirname(out_normalized), recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(out_plot), recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)

  neighbourhood_radius <- scalar_numeric_or(task$neighbourhood_radius)
  if (!is.finite(neighbourhood_radius) || neighbourhood_radius <= 0) {
    legacy_half_width <- scalar_numeric_or(task$neighbourhood_half_width)
    legacy_normalize_diam <- scalar_numeric_or(task$normalize_diam)
    if (is.finite(legacy_half_width) && legacy_half_width > 0) {
      neighbourhood_radius <- legacy_half_width
      message("Using legacy neighbourhood_half_width as spherical neighbourhood radius: ", neighbourhood_radius)
    } else if (is.finite(legacy_normalize_diam) && legacy_normalize_diam > 0) {
      neighbourhood_radius <- legacy_normalize_diam
      message("Using legacy normalize_diam as spherical neighbourhood radius: ", neighbourhood_radius)
    } else {
      stop("Invalid neighbourhood_radius in task JSON.", call. = FALSE)
    }
  }

  max_cores <- as.integer(scalar_numeric_or(task$max_cores, 1))
  if (!is.finite(max_cores) || max_cores < 1) max_cores <- 1

  lower_quantile <- scalar_numeric_or(task$lower_quantile, 0.10)
  upper_quantile <- scalar_numeric_or(task$upper_quantile, 0.90)
  if (lower_quantile < 0 || upper_quantile > 1 || lower_quantile >= upper_quantile) {
    stop("Normalization quantiles must satisfy 0 <= lower_quantile < upper_quantile <= 1.", call. = FALSE)
  }

  column_to_normalize <- task$column_to_normalize
  if (is.null(column_to_normalize) || length(column_to_normalize) != 1 || is.na(column_to_normalize) || column_to_normalize == "") {
    column_to_normalize <- "local_height"
  }

  # Load installed CV3D package ------------------------------------
  if (!requireNamespace("CV3D", quietly = TRUE)) {
    stop(
      "The CV3D R package is not installed. ",
      "Install it with remotes::install_github('Pete-s-Lab/CV3D') or use the GUI install button.",
      call. = FALSE
    )
  }
  suppressPackageStartupMessages(library(CV3D))
  suppressPackageStartupMessages(requireNamespace("readr"))
  suppressPackageStartupMessages(requireNamespace("dplyr"))

  message("Reading raw local heights: ", input_local_heights)
  local_heights <- readr::read_csv(input_local_heights, show_col_types = FALSE, progress = FALSE)

  if (!column_to_normalize %in% names(local_heights)) {
    stop("Input local-height CSV has no column named '", column_to_normalize, "'.", call. = FALSE)
  }
  finite_input <- is.finite(as.numeric(local_heights[[column_to_normalize]]))
  if (!any(finite_input)) {
    stop("Input column '", column_to_normalize, "' contains no finite values.", call. = FALSE)
  }

  message("Normalizing local heights with neighbourhood_radius = ", neighbourhood_radius, ", quantiles = ", lower_quantile, "-", upper_quantile, ", cores = ", max_cores)
  normalized <- normalize_local_heights(
    df = local_heights,
    neighbourhood_radius = neighbourhood_radius,
    column_to_normalize = column_to_normalize,
    lower_quantile = lower_quantile,
    upper_quantile = upper_quantile,
    cores = max_cores,
    plot_file = NULL,
    plot_results = FALSE,
    verbose = TRUE
  )

  if (!"local_height_norm" %in% names(normalized)) {
    stop("normalize_local_heights() returned no 'local_height_norm' column.", call. = FALSE)
  }
  finite_norm <- is.finite(as.numeric(normalized$local_height_norm))
  if (!any(finite_norm)) {
    stop("normalize_local_heights() returned no finite local_height_norm values.", call. = FALSE)
  }

  readr::write_csv(normalized, out_normalized, progress = FALSE)

  # Create a simple deterministic inspection PNG independent of rgl.
  png(filename = out_plot, width = 1800, height = 600, res = 150)
  old_par <- par(no.readonly = TRUE)
  on.exit({
    try(par(old_par), silent = TRUE)
    try(dev.off(), silent = TRUE)
  }, add = TRUE)

  par(mfrow = c(1, 3))
  raw_col <- if ("local_height_col" %in% names(normalized)) normalized$local_height_col else "black"
  norm_col <- if ("local_height_norm_col" %in% names(normalized)) normalized$local_height_norm_col else "black"
  norm_contrast_values <- if ("local_height_norm_contrast" %in% names(normalized)) {
    normalized$local_height_norm_contrast
  } else {
    pmin(pmax((10^as.numeric(normalized$local_height_norm) - 1) / 9, 0), 1)
  }
  norm_contrast_col <- if ("local_height_norm_contrast_col" %in% names(normalized)) normalized$local_height_norm_contrast_col else norm_col

  plot(
    normalized[[column_to_normalize]],
    col = raw_col,
    pch = 16,
    cex = 0.25,
    main = paste0("raw ", column_to_normalize),
    xlab = "triangle index",
    ylab = column_to_normalize
  )
  plot(
    normalized$local_height_norm,
    col = norm_col,
    pch = 16,
    cex = 0.25,
    main = "normalized local height",
    xlab = "triangle index",
    ylab = "local_height_norm"
  )
  plot(
    norm_contrast_values,
    col = norm_contrast_col,
    pch = 16,
    cex = 0.25,
    main = "normalized peak-enhanced contrast",
    xlab = "triangle index",
    ylab = "local_height_norm_contrast"
  )
  dev.off()

  required <- c(out_normalized, out_plot)
  missing <- required[!file.exists(required)]
  if (length(missing) > 0) {
    stop("Step 03A2 finished but required output file(s) are missing: ", paste(missing, collapse = "; "), call. = FALSE)
  }

  write_status(
    "success",
    "Optional Step 03A2 local-height normalization completed.",
    list(
      summary = list(
        row_count = nrow(normalized),
        neighbourhood_radius = neighbourhood_radius,
        column_to_normalize = column_to_normalize,
        max_cores_used = max_cores,
        finite_input_count = sum(finite_input),
        finite_normalized_count = sum(finite_norm),
        normalized_min = min(as.numeric(normalized$local_height_norm), na.rm = TRUE),
        normalized_max = max(as.numeric(normalized$local_height_norm), na.rm = TRUE)
      )
    )
  )

  message("CV3D optional Step 03A2 completed successfully.")

}, error = function(e) {
  msg <- conditionMessage(e)
  try(write_status("failed", msg), silent = TRUE)
  message("CV3D optional Step 03A2 failed: ", msg)
  quit(status = 1, save = "no")
})
