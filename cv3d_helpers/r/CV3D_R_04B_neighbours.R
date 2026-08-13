#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript CV3D_R_04B_neighbours.R <task_json>", call. = FALSE)

task_json <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

safe_require <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) stop("Required R package is not installed: ", pkg, call. = FALSE)
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

safe_require("jsonlite")
safe_require("readr")
safe_require("CV3D")

SCRIPT_VERSION <- "0.1.0-edge-aware-neighbours"
SCRIPT_NAME <- "CV3D_R_04B_neighbours.R"
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
  if (length(missing) > 0) stop(label, " is missing required column(s): ", paste(missing, collapse = ", "), call. = FALSE)
}

read_facets <- function(path) {
  raw <- suppressMessages(readr::read_csv(path, show_col_types = FALSE))
  id_col <- if ("facet_id" %in% names(raw)) "facet_id" else if ("ID" %in% names(raw)) "ID" else NA_character_
  if (is.na(id_col)) stop("Facet-position table must contain facet_id or ID.", call. = FALSE)
  need_cols(raw, c("x", "y", "z"), "Facet-position table")

  out <- data.frame(
    ID = as.character(raw[[id_col]]),
    x = as.numeric(raw$x),
    y = as.numeric(raw$y),
    z = as.numeric(raw$z),
    stringsAsFactors = FALSE
  )
  out <- out[is.finite(out$x) & is.finite(out$y) & is.finite(out$z), , drop = FALSE]
  if (nrow(out) < 4L) stop("At least four finite facet positions are required.", call. = FALSE)
  if (anyDuplicated(out$ID) > 0L) stop("Facet IDs must be unique.", call. = FALSE)
  out
}

make_pca_xy <- function(df) {
  p <- stats::prcomp(as.matrix(df[, c("x", "y", "z")]), center = TRUE, scale. = FALSE)
  p$x[, 1:2, drop = FALSE]
}

plot_threshold_comparison <- function(df, gap_deg, thresholds, path) {
  xy <- make_pca_xy(df)
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  grDevices::png(path, width = 2400, height = 1600, res = 180)
  on.exit(grDevices::dev.off(), add = TRUE)
  op <- par(mfrow = c(2, 3), mar = c(3.2, 3.2, 3.1, 1.0), oma = c(1.0, 1.0, 3.2, 0.5))
  on.exit(par(op), add = TRUE)

  for (thr in thresholds) {
    edge <- is.finite(gap_deg) & gap_deg > thr
    plot(
      xy[, 1], xy[, 2], asp = 1, pch = 21,
      bg = ifelse(edge, "tomato", "grey85"), col = "grey25", cex = 1.25,
      xlab = "PCA 1", ylab = "PCA 2",
      main = sprintf("gap > %g deg: %d edge facets", thr, sum(edge))
    )
  }
  mtext("Edge-facet detection threshold comparison", outer = TRUE, cex = 1.35, font = 2)
}

main <- function() {
  if (!all(c("detect_facet_edges", "find_neighbours_edge_aware") %in% getNamespaceExports("CV3D"))) {
    stop(
      "The installed CV3D package does not provide the edge-aware neighbour functions. Install the accompanying CV3D package patch first.",
      call. = FALSE
    )
  }

  input_file <- normalizePath(task$input_facet_positions_abs, winslash = "/", mustWork = TRUE)
  facets <- read_facets(input_file)
  mode <- tolower(as.character(task$mode %||% "preview"))

  if (mode == "preview") {
    thresholds <- as.numeric(task$thresholds_deg %||% c(80, 85, 90, 95, 100, 105))
    thresholds <- thresholds[is.finite(thresholds)]
    if (length(thresholds) == 0L) stop("No valid edge thresholds were supplied.", call. = FALSE)

    edge_info <- CV3D::detect_facet_edges(facets, gap_threshold_deg = thresholds[[1]])
    gap_deg <- as.numeric(edge_info$edge_angular_gap_deg)

    gap_table <- data.frame(
      cv_id = task$cv_id,
      eye = task$eye,
      facet_id = facets$ID,
      x = facets$x,
      y = facets$y,
      z = facets$z,
      edge_angular_gap_deg = gap_deg,
      stringsAsFactors = FALSE
    )
    dir.create(dirname(task$output_edge_gap_table_abs), recursive = TRUE, showWarnings = FALSE)
    readr::write_csv(gap_table, task$output_edge_gap_table_abs)
    plot_threshold_comparison(facets, gap_deg, thresholds, task$output_comparison_png_abs)

    counts <- stats::setNames(vapply(thresholds, function(thr) sum(is.finite(gap_deg) & gap_deg > thr), integer(1)), as.character(thresholds))
    write_status("success", "04B edge-threshold comparison created successfully.", list(summary = list(
      mode = "preview",
      thresholds_deg = thresholds,
      edge_counts = as.list(counts),
      output_comparison_png = task$output_comparison_png,
      output_edge_gap_table = task$output_edge_gap_table
    )))
    return(invisible(NULL))
  }

  if (mode == "final") {
    threshold <- as.numeric(task$edge_gap_threshold_deg %||% 90)
    if (!is.finite(threshold)) stop("edge_gap_threshold_deg must be finite.", call. = FALSE)

    g <- CV3D::find_neighbours_edge_aware(
      facets,
      edge_gap_threshold_deg = threshold,
      k = 6,
      core_k = 3,
      tangent_k = 12,
      knn_search = 20,
      interior_link_factor = 1.5,
      edge_link_factor = 1.4,
      shadow_angle_fraction = 2 / 3,
      shadow_angle_min_deg = 30,
      shadow_angle_max_deg = 45,
      shadow_radial_ratio = 1.15,
      shadow_min_remaining = 2,
      verbose = FALSE
    )

    shadow_cutoff <- attr(g, "shadow_angle_threshold_deg")
    shadow_removed <- attr(g, "shadow_removed_links")
    if (is.null(shadow_removed)) shadow_removed <- data.frame()

    out <- data.frame(
      cv_id = task$cv_id,
      eye = task$eye,
      facet_id = as.character(g$ID),
      x = as.numeric(g$x),
      y = as.numeric(g$y),
      z = as.numeric(g$z),
      neighbours = as.character(g$neighbours),
      number_of_neighbours = as.integer(g$number_of_neighbours),
      is_edge_facet = as.logical(g$is_edge_facet),
      edge_angular_gap_deg = as.numeric(g$edge_angular_gap_deg),
      edge_gap_threshold_deg = as.numeric(g$edge_gap_threshold_deg),
      neighbour_core_spacing_um = as.numeric(g$neighbour_core_spacing_um),
      shadow_links_removed = as.integer(g$shadow_links_removed),
      neighbour_method = "edge_aware_mutual6_coregate_angle_shadow",
      stringsAsFactors = FALSE
    )

    dir.create(dirname(task$output_neighbours_abs), recursive = TRUE, showWarnings = FALSE)
    readr::write_csv(out, task$output_neighbours_abs)

    if (!is.null(task$output_shadow_removed_links_abs) && nzchar(as.character(task$output_shadow_removed_links_abs))) {
      dir.create(dirname(task$output_shadow_removed_links_abs), recursive = TRUE, showWarnings = FALSE)
      readr::write_csv(shadow_removed, task$output_shadow_removed_links_abs)
    }

    write_status("success", "04B edge-aware neighbours completed successfully.", list(summary = list(
      mode = "final",
      edge_gap_threshold_deg = threshold,
      facet_count = nrow(out),
      edge_facet_count = sum(out$is_edge_facet, na.rm = TRUE),
      mean_neighbour_count = mean(out$number_of_neighbours, na.rm = TRUE),
      shadow_angle_threshold_deg = shadow_cutoff,
      shadow_links_removed = nrow(shadow_removed),
      neighbour_method = "edge_aware_mutual6_coregate_angle_shadow",
      output_neighbours = task$output_neighbours
    )))
    return(invisible(NULL))
  }

  stop("Unknown 04B task mode: ", mode, call. = FALSE)
}

tryCatch(main(), error = function(e) {
  msg <- conditionMessage(e)
  message("CV3D 04B neighbour step failed: ", msg)
  write_status("failed", msg, list(traceback = paste(utils::capture.output(traceback()), collapse = "\n")))
  quit(status = 1, save = "no")
})
