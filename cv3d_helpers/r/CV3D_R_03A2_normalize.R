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
    script_version = "CV3D_R_step03A2_normalize_local_heights_0.1.0",
    status = status,
    message = message,
    cv_id = task$cv_id,
    eye = task$eye,
    step_id = "03a2_local_height_normalization",
    input_local_heights_abs = task$input_local_heights_abs,
    output_local_heights_normalized_abs = task$output_local_heights_normalized_abs,
    output_normalization_plot_abs = task$output_normalization_plot_abs,
    normalize_diam = task$normalize_diam,
    column_to_normalize = task$column_to_normalize,
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
  write_status("running", "Optional Step 03A2 normalization runner started.")

  # Resolve and validate paths -------------------------------------------------
  input_local_heights <- normalizePath(task$input_local_heights_abs, winslash = "/", mustWork = TRUE)
  out_normalized <- task$output_local_heights_normalized_abs
  out_plot <- task$output_normalization_plot_abs

  dir.create(dirname(out_normalized), recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(out_plot), recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)

  normalize_diam <- as.numeric(task$normalize_diam)
  if (!is.finite(normalize_diam) || normalize_diam <= 0) {
    stop("Invalid normalize_diam in task JSON: ", task$normalize_diam, call. = FALSE)
  }

  max_cores <- as.integer(task$max_cores)
  if (!is.finite(max_cores) || max_cores < 1) max_cores <- 1

  column_to_normalize <- task$column_to_normalize
  if (is.null(column_to_normalize) || is.na(column_to_normalize) || column_to_normalize == "") {
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

  message("Normalizing local heights with normalize_diam = ", normalize_diam, ", cores = ", max_cores)
  normalized <- normalize_local_heights(
    df = local_heights,
    normalize_diam = normalize_diam,
    column_to_normalize = column_to_normalize,
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
  log_norm_values <- if ("local_height_log_norm" %in% names(normalized)) normalized$local_height_log_norm else log10(abs(normalized$local_height_norm) + .Machine$double.eps)
  log_norm_col <- if ("local_height_log_norm_col" %in% names(normalized)) normalized$local_height_log_norm_col else norm_col

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
    log_norm_values,
    col = log_norm_col,
    pch = 16,
    cex = 0.25,
    main = "log-normalized display",
    xlab = "triangle index",
    ylab = "local_height_log_norm"
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
        normalize_diam = normalize_diam,
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
