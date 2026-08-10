#!/usr/bin/env Rscript

# Usage:
#   Rscript CV3D_R_step03C_facet_candidate_condensation.R <task_json>
#
# This runner intentionally keeps the scientific logic in the CV3D
# package. It only reads the task JSON, calls
# CV3D::find_facet_candidates_condensed(), and writes outputs/status.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript CV3D_R_step03C_facet_candidate_condensation.R <task_json>", call. = FALSE)
}

task_json <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

safe_require <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    stop("Required R package is not installed: ", pkg, call. = FALSE)
  }
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

safe_require("jsonlite")
safe_require("readr")
safe_require("dplyr")
safe_require("CV3D")

task <- jsonlite::fromJSON(task_json, simplifyVector = TRUE)
status_file <- task$status_file_abs

write_status <- function(status, message, extra = list()) {
  payload <- c(
    list(
      status = status,
      message = message,
      task_json = task_json,
      script_version = "CV3D_R_step03C_facet_candidate_condensation_0.1.0"
    ),
    extra
  )
  dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(payload, status_file, pretty = TRUE, auto_unbox = TRUE, null = "null")
}

main <- function() {
  if (!exists("find_facet_candidates_condensed", where = asNamespace("CV3D"), inherits = FALSE)) {
    stop(
      "CV3D::find_facet_candidates_condensed() was not found. ",
      "Install/update the package version that contains the 03C condensation function.",
      call. = FALSE
    )
  }

  input_csv <- normalizePath(task$input_local_height_thresholded_abs, winslash = "/", mustWork = TRUE)
  output_csv <- task$output_facet_candidates_abs
  output_membership <- task$output_membership_abs
  params <- task$parameters

  dir.create(dirname(output_csv), recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(output_membership), recursive = TRUE, showWarnings = FALSE)

  message("Reading thresholded local-height points: ", input_csv)
  df <- suppressMessages(readr::read_csv(input_csv, show_col_types = FALSE))

  required_cols <- c("x", "y", "z", "height_value")
  missing_cols <- setdiff(required_cols, names(df))
  if (length(missing_cols) > 0) {
    stop(
      "03C input is missing required column(s): ",
      paste(missing_cols, collapse = ", "),
      call. = FALSE
    )
  }

  message("Running CV3D::find_facet_candidates_condensed() ...")
  result <- CV3D::find_facet_candidates_condensed(
    df = df,
    coord_cols = c("x", "y", "z"),
    height_col = "height_value",
    neighbour_radius = as.numeric(params$neighbour_radius),
    merge_radius = as.numeric(params$merge_radius),
    weight_exponent = as.numeric(params$weight_exponent),
    max_iterations = as.integer(params$max_iterations),
    step_size = as.numeric(params$step_size),
    min_cluster_size = as.integer(params$min_cluster_size),
    select_point = as.character(params$select_point),
    cores = as.integer(params$cores),
    return_details = TRUE,
    verbose = TRUE
  )

  candidates <- result$candidates
  membership <- result$membership

  message("Writing facet candidates: ", output_csv)
  readr::write_csv(candidates, output_csv)

  message("Writing condensation membership diagnostics: ", output_membership)
  readr::write_csv(membership, output_membership)

  warnings <- list()
  if (nrow(candidates) == 0) {
    warnings <- c(warnings, "No facet candidates were produced.")
  }

  write_status(
    "success",
    "03C facet candidate condensation completed successfully.",
    list(
      summary = list(
        input_local_height_thresholded = task$input_local_height_thresholded,
        output_facet_candidates = task$output_facet_candidates,
        output_membership = task$output_membership,
        input_point_count = nrow(df),
        candidate_count = nrow(candidates),
        neighbour_radius = as.numeric(params$neighbour_radius),
        merge_radius = as.numeric(params$merge_radius),
        weight_exponent = as.numeric(params$weight_exponent),
        max_iterations = as.integer(params$max_iterations),
        step_size = as.numeric(params$step_size),
        min_cluster_size = as.integer(params$min_cluster_size),
        select_point = as.character(params$select_point),
        cores = as.integer(params$cores)
      ),
      package_parameters = result$parameters,
      warnings = warnings
    )
  )
}

tryCatch(
  main(),
  error = function(e) {
    msg <- conditionMessage(e)
    tb <- paste(utils::capture.output(traceback()), collapse = "\n")
    message("CV3D 03C facet candidate condensation failed: ", msg)
    if (nzchar(tb)) message(tb)
    write_status("failed", msg, list(traceback = tb))
    quit(status = 1, save = "no")
  }
)
