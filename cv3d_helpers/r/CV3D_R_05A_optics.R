#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript CV3D_R_05A_optics.R <task_json>", call. = FALSE)

task_json <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

safe_require <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) stop("Required R package is not installed: ", pkg, call. = FALSE)
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

safe_require("jsonlite")
safe_require("readr")
safe_require("dplyr")
safe_require("tibble")
safe_require("CompoundVision3D")

SCRIPT_VERSION <- "0.1.1-stepwise-numeric-internal-ids"
SCRIPT_NAME <- "CV3D_R_05A_optics.R"

task <- jsonlite::fromJSON(task_json, simplifyVector = TRUE)
status_file <- task$status_file_abs

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0 || all(is.na(x))) y else x
}

write_status <- function(status, message, extra = list()) {
  payload <- c(list(
    status = status,
    message = message,
    task_json = task_json,
    script_name = SCRIPT_NAME,
    script_version = SCRIPT_VERSION
  ), extra)
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
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  readr::write_csv(df, path)
}

select_existing <- function(df, cols) {
  dplyr::select(df, dplyr::any_of(cols))
}

safe_mean <- function(df, col) {
  if (!col %in% names(df)) return(NA_real_)
  vals <- suppressWarnings(as.numeric(df[[col]]))
  if (!any(is.finite(vals))) return(NA_real_)
  mean(vals, na.rm = TRUE)
}

safe_median <- function(df, col) {
  if (!col %in% names(df)) return(NA_real_)
  vals <- suppressWarnings(as.numeric(df[[col]]))
  if (!any(is.finite(vals))) return(NA_real_)
  stats::median(vals, na.rm = TRUE)
}

main <- function() {
  input_file <- normalizePath(task$input_facet_positions_abs, winslash = "/", mustWork = TRUE)
  message("Reading checked facet positions: ", input_file)

  facets_in <- suppressMessages(readr::read_csv(input_file, show_col_types = FALSE))
  need_cols(facets_in, c("facet_id", "x", "y", "z"), "Facet-position table")

  facets_clean <- facets_in %>%
    dplyr::mutate(
      facet_id = as.character(facet_id),
      x = as.numeric(x),
      y = as.numeric(y),
      z = as.numeric(z)
    ) %>%
    dplyr::filter(is.finite(x), is.finite(y), is.finite(z))

  if (nrow(facets_clean) < 4) stop("At least four finite facet positions are required for optical metrics.", call. = FALSE)
  if (anyDuplicated(facets_clean$facet_id) > 0) stop("facet_id values are not unique in the facet-position table.", call. = FALSE)

  # The package internals are most robust with simple numeric IDs, while the
  # Blender-exported facet_id must remain the external key in all CV3D outputs.
  id_map <- facets_clean %>%
    dplyr::mutate(ID = as.character(dplyr::row_number())) %>%
    dplyr::select(ID, facet_id, dplyr::everything())

  facet_df <- id_map %>%
    dplyr::transmute(
      CV = task$cv_id,
      eye = task$eye,
      ID = as.character(ID),
      facet_id = as.character(facet_id),
      type = "facet",
      x = x,
      y = y,
      z = z
    )

  cores <- as.integer(task$parameters$cores %||% 1L)
  if (!is.finite(cores) || cores < 1) cores <- 1L

  edge_tol <- as.numeric(task$parameters$edge_tol %||% 0.5)
  if (!is.finite(edge_tol) || edge_tol <= 0) edge_tol <- 0.5

  facet_size <- as.numeric(task$parameters$facet_size_estimate %||% 14)
  if (!is.finite(facet_size) || facet_size <= 0) facet_size <- 14

  message("Calculating optical metrics stepwise with CompoundVision3D package functions.")
  message("Facet count: ", nrow(facet_df))
  message("Edge tolerance: ", edge_tol)
  message("Cores: ", cores)
  message("Facet-size estimate: ", facet_size)

  message("Step 05A.1: find_neighbours().")
  neighbours <- CompoundVision3D::find_neighbours(
    df = facet_df,
    edge_tol = edge_tol
  )

  if (!"ID" %in% names(neighbours)) stop("find_neighbours() output has no ID column.", call. = FALSE)
  if ("number.of.neighbours" %in% names(neighbours) && all(neighbours$number.of.neighbours < 2, na.rm = TRUE)) {
    stop("All facets have fewer than two neighbours after find_neighbours(); cannot calculate facet normals.", call. = FALSE)
  }

  message("Step 05A.2: calculate_facet_size().")
  facet_sizes_raw <- CompoundVision3D::calculate_facet_size(neighbours)

  df_w_sizes_raw <- neighbours %>%
    dplyr::left_join(
      facet_sizes_raw %>% dplyr::select(-dplyr::any_of("n_used")),
      by = "ID"
    )

  if ("size_avg" %in% names(df_w_sizes_raw)) {
    df_w_sizes <- df_w_sizes_raw %>%
      dplyr::select(-dplyr::any_of("size")) %>%
      dplyr::rename(size = size_avg)
  } else if ("size" %in% names(df_w_sizes_raw)) {
    df_w_sizes <- df_w_sizes_raw
  } else {
    warning("calculate_facet_size() returned no size/size_avg column; using facet-size estimate for all facets.")
    df_w_sizes <- df_w_sizes_raw %>% dplyr::mutate(size = facet_size)
  }

  message("Step 05A.3: get_facet_normals().")
  normals <- CompoundVision3D::get_facet_normals(
    df = df_w_sizes,
    cores = cores,
    plot_file = NULL,
    plot_results = FALSE,
    verbose = TRUE
  )

  if (!"ID" %in% names(normals)) stop("get_facet_normals() output has no ID column.", call. = FALSE)

  # Avoid accidental duplicate coordinate columns from package internals.
  normal_cols <- c("ID", setdiff(names(normals), names(df_w_sizes)))
  normal_cols <- unique(c("ID", normal_cols))
  df_w_normals <- df_w_sizes %>%
    dplyr::left_join(normals %>% dplyr::select(dplyr::any_of(normal_cols)), by = "ID")

  message("Step 05A.4: get_optic_properties().")
  optic_properties <- CompoundVision3D::get_optic_properties(
    df = df_w_normals,
    cores = cores,
    plot_results = FALSE,
    plot_file = NULL,
    verbose = TRUE
  )

  if (!"ID" %in% names(optic_properties)) stop("get_optic_properties() output has no ID column.", call. = FALSE)

  optic <- df_w_normals %>%
    dplyr::left_join(optic_properties, by = "ID")

  if (!"facet_id" %in% names(optic)) optic$facet_id <- NA_character_

  optic <- optic %>%
    dplyr::left_join(id_map %>% dplyr::select(ID, blender_facet_id = facet_id), by = "ID") %>%
    dplyr::mutate(
      cv_id = task$cv_id,
      eye = task$eye,
      facet_id = dplyr::coalesce(.data$blender_facet_id, as.character(.data$facet_id), as.character(.data$ID)),
      internal_ID = .data$ID
    ) %>%
    dplyr::select(-dplyr::any_of("blender_facet_id")) %>%
    dplyr::relocate(cv_id, eye, facet_id, internal_ID, .before = 1)

  # Separate outputs, all keyed by the same facet_id exported from Blender.
  facet_sizes <- select_existing(
    optic,
    c("cv_id", "eye", "facet_id", "internal_ID", "x", "y", "z", "size", "number.of.neighbours", "neighbours")
  )

  interfacet_angles <- select_existing(
    optic,
    c("cv_id", "eye", "facet_id", "internal_ID", "delta_phi.deg", "delta_phi.rad", "number.of.neighbours", "neighbours")
  )

  sensitivity_acuity <- select_existing(
    optic,
    c("cv_id", "eye", "facet_id", "internal_ID", "P", "v", "CPD")
  )

  facet_normals <- select_existing(
    optic,
    c("cv_id", "eye", "facet_id", "internal_ID", "x", "y", "z", "norm.x", "norm.y", "norm.z")
  )

  numeric_summary <- tibble::tibble(
    cv_id = task$cv_id,
    eye = task$eye,
    facet_count = nrow(optic),
    mean_facet_size = safe_mean(optic, "size"),
    median_facet_size = safe_median(optic, "size"),
    mean_delta_phi_deg = safe_mean(optic, "delta_phi.deg"),
    median_delta_phi_deg = safe_median(optic, "delta_phi.deg"),
    mean_P = safe_mean(optic, "P"),
    mean_v = safe_mean(optic, "v"),
    mean_CPD = safe_mean(optic, "CPD"),
    edge_tol = edge_tol,
    cores = cores,
    facet_size_estimate = facet_size,
    internal_id_mode = "numeric_internal_ids_blender_facet_id_preserved"
  )

  write_csv_safe(optic, task$output_optic_parameters_abs)
  write_csv_safe(facet_sizes, task$output_facet_sizes_abs)
  write_csv_safe(interfacet_angles, task$output_interfacet_angles_abs)
  write_csv_safe(sensitivity_acuity, task$output_sensitivity_acuity_abs)
  write_csv_safe(facet_normals, task$output_facet_normals_abs)
  write_csv_safe(numeric_summary, task$output_optical_summary_abs)

  write_status("success", "05A optical metrics completed successfully.", list(summary = list(
    input_facet_positions = task$input_facet_positions,
    output_optic_parameters = task$output_optic_parameters,
    facet_count = nrow(optic),
    edge_tol = edge_tol,
    cores = cores,
    facet_size_estimate = facet_size,
    internal_id_mode = "numeric_internal_ids_blender_facet_id_preserved"
  )))
}

tryCatch(main(), error = function(e) {
  msg <- conditionMessage(e)
  message("CV3D 05A optical metrics failed: ", msg)
  write_status("failed", msg, list(traceback = paste(utils::capture.output(traceback()), collapse = "\n")))
  quit(status = 1, save = "no")
})
