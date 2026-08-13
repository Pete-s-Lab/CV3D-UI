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
safe_require("CV3D")

SCRIPT_VERSION <- "0.1.4-precomputed-edge-aware-neighbours"
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

parse_neighbour_ids <- function(value) {
  if (length(value) == 0 || is.na(value) || !nzchar(trimws(as.character(value)))) return(character(0))
  out <- trimws(strsplit(as.character(value), split = ";", fixed = TRUE)[[1]])
  out[nzchar(out)]
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
  if (!is.finite(edge_tol) || edge_tol < 0) edge_tol <- 0.5

  neighbour_file <- NULL
  if (!is.null(task$input_neighbours_abs) && length(task$input_neighbours_abs) > 0 && !all(is.na(task$input_neighbours_abs))) {
    neighbour_candidate <- as.character(task$input_neighbours_abs[[1]])
    if (nzchar(neighbour_candidate) && file.exists(neighbour_candidate)) {
      neighbour_file <- normalizePath(neighbour_candidate, winslash = "/", mustWork = TRUE)
    }
  }

  facet_size <- as.numeric(task$parameters$facet_size_estimate %||% 14)
  if (!is.finite(facet_size) || facet_size <= 0) facet_size <- 14

  lattice <- tolower(as.character(task$parameters$lattice %||% "hexagonal"))
  if (!lattice %in% c("hexagonal", "square")) {
    stop("lattice must be either 'hexagonal' or 'square'.", call. = FALSE)
  }

  normal_method <- tolower(as.character(task$parameters$normal_method %||% "envelope"))
  if (!normal_method %in% c("original", "envelope")) {
    stop("normal_method must be either 'original' or 'envelope'.", call. = FALSE)
  }
  normal_envelope_factor <- suppressWarnings(as.numeric(task$parameters$normal_envelope_factor %||% 1.25))
  if (normal_method == "envelope") {
    if (!is.finite(normal_envelope_factor) || !normal_envelope_factor %in% c(1, 1.25, 1.5, 2)) {
      stop("normal_envelope_factor must be one of 1, 1.25, 1.5, or 2 for envelope normals.", call. = FALSE)
    }
  } else {
    normal_envelope_factor <- NA_real_
  }

  message("Calculating optical metrics stepwise with CV3D package functions.")
  message("Facet count: ", nrow(facet_df))
  if (is.null(neighbour_file)) {
    message("Neighbour source: legacy in-step local tangent-plane calculation; edge tolerance=", edge_tol)
  } else {
    message("Neighbour source: precomputed 04B edge-aware neighbour file: ", neighbour_file)
  }
  message("Cores: ", cores)
  message("Facet-size estimate: ", facet_size)
  message("Sampling lattice: ", lattice)
  if (normal_method == "original") {
    message("Facet-normal method: original CV3D.")
  } else {
    message("Facet-normal method: regularised facet-centre envelope; factor=", normal_envelope_factor)
  }

  if (is.null(neighbour_file)) {
    message("Step 05A.1: legacy fallback find_neighbours() using local tangent-plane geometry.")
    neighbours <- CV3D::find_neighbours(
      df = facet_df,
      edge_tol = edge_tol
    )
    neighbour_method <- "local_tangent_plane_legacy_fallback"
    selected_edge_gap_threshold <- NA_real_
  } else {
    message("Step 05A.1: importing precomputed 04B edge-aware neighbours.")
    neighbour_external <- suppressMessages(readr::read_csv(neighbour_file, show_col_types = FALSE))
    need_cols(neighbour_external, c("facet_id", "neighbours", "number_of_neighbours"), "04B neighbour table")
    neighbour_external$facet_id <- as.character(neighbour_external$facet_id)
    if (anyDuplicated(neighbour_external$facet_id) > 0) stop("04B neighbour table contains duplicate facet_id values.", call. = FALSE)
    missing_ids <- setdiff(id_map$facet_id, neighbour_external$facet_id)
    extra_ids <- setdiff(neighbour_external$facet_id, id_map$facet_id)
    if (length(missing_ids) > 0 || length(extra_ids) > 0) {
      stop(
        "04B neighbour table and Step-04 facet-position table contain different facet IDs. ",
        "Missing in 04B: ", paste(missing_ids, collapse = ", "),
        "; extra in 04B: ", paste(extra_ids, collapse = ", "),
        call. = FALSE
      )
    }

    ext_to_int <- stats::setNames(as.character(id_map$ID), as.character(id_map$facet_id))
    map_neighbours <- function(value) {
      ext <- parse_neighbour_ids(value)
      if (length(ext) == 0) return("")
      mapped <- unname(ext_to_int[ext])
      if (any(is.na(mapped))) stop("04B neighbour table contains an unknown neighbour facet ID.", call. = FALSE)
      paste(mapped, collapse = "; ")
    }
    neighbour_external$internal_neighbours <- vapply(neighbour_external$neighbours, map_neighbours, character(1))
    neighbour_external$ID <- unname(ext_to_int[neighbour_external$facet_id])

    metadata_cols <- c(
      "ID", "internal_neighbours", "number_of_neighbours", "is_edge_facet",
      "edge_angular_gap_deg", "edge_gap_threshold_deg", "neighbour_core_spacing_um",
      "shadow_links_removed", "neighbour_method"
    )
    neighbours <- facet_df %>%
      dplyr::left_join(
        neighbour_external %>% dplyr::select(dplyr::any_of(metadata_cols)),
        by = "ID"
      ) %>%
      dplyr::mutate(neighbours = .data$internal_neighbours) %>%
      dplyr::select(-dplyr::any_of("internal_neighbours"))

    neighbour_method <- if ("neighbour_method" %in% names(neighbour_external)) {
      unique(as.character(neighbour_external$neighbour_method))[1]
    } else {
      "edge_aware_mutual6_coregate_angle_shadow"
    }
    selected_edge_gap_threshold <- if ("edge_gap_threshold_deg" %in% names(neighbour_external)) {
      suppressWarnings(as.numeric(neighbour_external$edge_gap_threshold_deg[[1]]))
    } else {
      NA_real_
    }
  }

  if (!"ID" %in% names(neighbours)) stop("Neighbour data have no ID column.", call. = FALSE)
  if ("number_of_neighbours" %in% names(neighbours) && all(neighbours$number_of_neighbours < 2, na.rm = TRUE)) {
    stop("All facets have fewer than two neighbours; cannot calculate facet normals.", call. = FALSE)
  }

  message("Step 05A.2: calculate_facet_size().")
  facet_sizes_raw <- CV3D::calculate_facet_size(neighbours)

  df_w_sizes <- neighbours %>%
    dplyr::left_join(facet_sizes_raw, by = "ID")

  if (!"facet_size_smoothed" %in% names(df_w_sizes)) {
    warning("calculate_facet_size() returned no facet_size_smoothed column; using facet-size estimate for all facets.")
    df_w_sizes$facet_size_smoothed <- facet_size
  }
  if (!"facet_size" %in% names(df_w_sizes)) {
    df_w_sizes$facet_size <- df_w_sizes$facet_size_smoothed
  }

  if (normal_method == "original") {
    message("Step 05A.3: get_facet_normals() — original CV3D estimator.")
    normals <- CV3D::get_facet_normals(
      df = df_w_sizes,
      cores = cores,
      plot_file = NULL,
      plot_results = FALSE,
      verbose = FALSE
    ) %>%
      dplyr::mutate(
        normal_method = "original",
        normal_envelope_factor = NA_real_,
        normal_support_scale_um = NA_real_,
        normal_weight_cutoff_um = NA_real_,
        normal_support_face_count = NA_integer_
      )
  } else {
    if (!"get_facet_normals_envelope" %in% getNamespaceExports("CV3D")) {
      stop(
        "The installed CV3D package does not provide get_facet_normals_envelope(). Update the package before using envelope normals.",
        call. = FALSE
      )
    }
    message("Step 05A.3: get_facet_normals_envelope() — regularised facet-centre envelope.")
    normals <- CV3D::get_facet_normals_envelope(
      df = df_w_sizes,
      envelope_factor = normal_envelope_factor,
      verbose = FALSE
    )
  }

  if (!"ID" %in% names(normals)) stop("Facet-normal output has no ID column.", call. = FALSE)

  # Avoid accidental duplicate coordinate columns from package internals.
  normal_cols <- c("ID", setdiff(names(normals), names(df_w_sizes)))
  normal_cols <- unique(c("ID", normal_cols))
  df_w_normals <- df_w_sizes %>%
    dplyr::left_join(normals %>% dplyr::select(dplyr::any_of(normal_cols)), by = "ID")

  message("Step 05A.4: get_optic_properties().")
  optic_properties <- CV3D::get_optic_properties(
    df = df_w_normals,
    lattice = lattice,
    cores = cores,
    plot_results = FALSE,
    plot_file = NULL,
    verbose = FALSE
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
    c(
      "cv_id", "eye", "facet_id", "internal_ID", "x", "y", "z",
      "facet_size", "facet_size_smoothed", "number_of_neighbours", "neighbours",
      "is_edge_facet", "edge_angular_gap_deg", "edge_gap_threshold_deg",
      "neighbour_core_spacing_um", "shadow_links_removed", "neighbour_method"
    )
  )

  interfacet_angles <- select_existing(
    optic,
    c("cv_id", "eye", "facet_id", "internal_ID", "interfacet_angle_deg", "interfacet_angle_rad", "number_of_neighbours", "neighbours")
  )

  sampling_acuity <- select_existing(
    optic,
    c("cv_id", "eye", "facet_id", "internal_ID", "sampling_lattice", "eye_parameter", "sampling_frequency_rad", "acuity_cpd")
  )

  facet_normals <- select_existing(
    optic,
    c(
      "cv_id", "eye", "facet_id", "internal_ID", "x", "y", "z",
      "norm.x", "norm.y", "norm.z",
      "normal_method", "normal_envelope_factor", "normal_support_scale_um",
      "normal_weight_cutoff_um", "normal_support_face_count"
    )
  )

  numeric_summary <- tibble::tibble(
    cv_id = task$cv_id,
    eye = task$eye,
    facet_count = nrow(optic),
    mean_facet_size = safe_mean(optic, "facet_size_smoothed"),
    median_facet_size = safe_median(optic, "facet_size_smoothed"),
    mean_delta_phi_deg = safe_mean(optic, "interfacet_angle_deg"),
    median_delta_phi_deg = safe_median(optic, "interfacet_angle_deg"),
    mean_eye_parameter = safe_mean(optic, "eye_parameter"),
    mean_sampling_frequency_rad = safe_mean(optic, "sampling_frequency_rad"),
    mean_acuity_cpd = safe_mean(optic, "acuity_cpd"),
    sampling_lattice = lattice,
    facet_normal_method = normal_method,
    facet_normal_envelope_factor = if (normal_method == "envelope") normal_envelope_factor else NA_real_,
    facet_normal_post_neighbour_smoothing = normal_method == "original",
    neighbour_method = neighbour_method,
    edge_gap_threshold_deg = selected_edge_gap_threshold,
    edge_tol = if (is.null(neighbour_file)) edge_tol else NA_real_,
    cores = cores,
    facet_size_estimate = facet_size,
    spatial_unit = "um",
    eye_parameter_unit = "um*rad",
    internal_id_mode = "numeric_internal_ids_blender_facet_id_preserved"
  )

  write_csv_safe(optic, task$output_optic_parameters_abs)
  write_csv_safe(facet_sizes, task$output_facet_sizes_abs)
  write_csv_safe(interfacet_angles, task$output_interfacet_angles_abs)
  write_csv_safe(sampling_acuity, task$output_sampling_acuity_abs)
  write_csv_safe(facet_normals, task$output_facet_normals_abs)
  write_csv_safe(numeric_summary, task$output_optical_summary_abs)

  write_status("success", "05A optical metrics completed successfully.", list(summary = list(
    input_facet_positions = task$input_facet_positions,
    output_optic_parameters = task$output_optic_parameters,
    facet_count = nrow(optic),
    edge_gap_threshold_deg = selected_edge_gap_threshold,
    edge_tol = if (is.null(neighbour_file)) edge_tol else NA_real_,
    cores = cores,
    facet_size_estimate = facet_size,
    sampling_lattice = lattice,
    facet_normal_method = normal_method,
    facet_normal_envelope_factor = if (normal_method == "envelope") normal_envelope_factor else NA_real_,
    facet_normal_post_neighbour_smoothing = normal_method == "original",
    neighbour_method = neighbour_method,
    input_neighbours = if (is.null(neighbour_file)) NULL else task$input_neighbours,
    internal_id_mode = "numeric_internal_ids_blender_facet_id_preserved"
  )))
}

tryCatch(main(), error = function(e) {
  msg <- conditionMessage(e)
  message("CV3D 05A optical metrics failed: ", msg)
  write_status("failed", msg, list(traceback = paste(utils::capture.output(traceback()), collapse = "\n")))
  quit(status = 1, save = "no")
})
