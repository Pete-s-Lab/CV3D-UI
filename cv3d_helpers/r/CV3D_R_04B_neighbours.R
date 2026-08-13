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

SCRIPT_VERSION <- "0.1.2-standard-face-on-threshold-qc"
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

make_face_on_view_df <- function(df) {
  need_cols(df, c("x", "y", "z"), "Face-on plotting table")
  base <- data.frame(
    ID = if ("facet_id" %in% names(df)) as.character(df$facet_id) else if ("ID" %in% names(df)) as.character(df$ID) else as.character(seq_len(nrow(df))),
    x = as.numeric(df$x), y = as.numeric(df$y), z = as.numeric(df$z),
    stringsAsFactors = FALSE
  )

  if (all(c("norm.x", "norm.y", "norm.z") %in% names(df))) {
    base$norm.x <- as.numeric(df$norm.x)
    base$norm.y <- as.numeric(df$norm.y)
    base$norm.z <- as.numeric(df$norm.z)
    return(base)
  }

  if (!"get_facet_normals_envelope" %in% getNamespaceExports("CV3D")) {
    stop("The installed CV3D package does not export get_facet_normals_envelope(), which is required only to orient the 04B QC plots face-on.", call. = FALSE)
  }
  normals <- CV3D::get_facet_normals_envelope(base[, c("ID", "x", "y", "z")], envelope_factor = 1.25, verbose = FALSE)
  idx <- match(base$ID, as.character(normals$ID))
  if (anyNA(idx)) stop("Could not match temporary display normals back to all facet positions.", call. = FALSE)
  base$norm.x <- as.numeric(normals$norm.x[idx])
  base$norm.y <- as.numeric(normals$norm.y[idx])
  base$norm.z <- as.numeric(normals$norm.z[idx])
  base
}

make_face_on_xy <- function(df) {
  if (!"view_eye_face_on" %in% getNamespaceExports("CV3D")) {
    stop("The installed CV3D package does not export view_eye_face_on(). Reinstall/update CV3D first.", call. = FALSE)
  }
  view_df <- make_face_on_view_df(df)
  tmp <- tempfile(fileext = ".pdf")
  grDevices::pdf(tmp, width = 4, height = 4)
  dev_open <- TRUE
  on.exit({
    if (isTRUE(dev_open)) try(grDevices::dev.off(), silent = TRUE)
    try(unlink(tmp), silent = TRUE)
  }, add = TRUE)
  view <- CV3D::view_eye_face_on(
    view_df, projection = "2D", reverse = FALSE, long_axis_vertical = TRUE,
    col = NA, pch = NA, cex = 0, axes = FALSE, xlab = "", ylab = ""
  )
  grDevices::dev.off()
  dev_open <- FALSE
  unlink(tmp)
  xy <- as.matrix(view$projected_coordinates)
  if (nrow(xy) != nrow(df) || ncol(xy) != 2L || any(!is.finite(xy))) {
    stop("view_eye_face_on() returned invalid 04B projected coordinates.", call. = FALSE)
  }
  xy
}

run_edge_aware <- function(facets, threshold) {
  CV3D::find_neighbours_edge_aware(
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
}


parse_neighbour_ids <- function(x) {
  if (length(x) == 0 || is.na(x) || !nzchar(trimws(as.character(x)))) return(character(0))
  out <- trimws(strsplit(as.character(x), ";", fixed = TRUE)[[1]])
  out[nzchar(out)]
}

plot_neighbours_qc <- function(df, path, cv_id, eye) {
  need_cols(df, c("facet_id", "x", "y", "z", "neighbours", "number_of_neighbours", "is_edge_facet"), "04B neighbour table")
  xy <- make_face_on_xy(df)
  ids <- as.character(df$facet_id)
  counts <- suppressWarnings(as.integer(df$number_of_neighbours))
  counts[!is.finite(counts)] <- 0L
  edge <- as.logical(df$is_edge_facet)
  edge[is.na(edge)] <- FALSE
  threshold <- if ("edge_gap_threshold_deg" %in% names(df)) suppressWarnings(as.numeric(df$edge_gap_threshold_deg[[1]])) else NA_real_

  neighbour_cols <- c("#440154", "#414487", "#2A788E", "#22A884", "#7AD151", "#FDE725", "#FFE066")
  point_cols <- neighbour_cols[pmax(0L, pmin(6L, counts)) + 1L]

  edges_i <- integer(0)
  edges_j <- integer(0)
  for (i in seq_len(nrow(df))) {
    nb <- parse_neighbour_ids(df$neighbours[[i]])
    if (length(nb) == 0) next
    jj <- match(nb, ids)
    jj <- jj[is.finite(jj) & jj > i]
    if (length(jj) > 0) {
      edges_i <- c(edges_i, rep.int(i, length(jj)))
      edges_j <- c(edges_j, jj)
    }
  }

  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  grDevices::png(path, width = 2200, height = 1050, res = 180)
  on.exit(grDevices::dev.off(), add = TRUE)
  op <- par(mfrow = c(1, 2), mar = c(3.5, 3.5, 3.5, 1.0), oma = c(0.5, 0.5, 3.0, 0.5))
  on.exit(par(op), add = TRUE)

  plot(xy[, 1], xy[, 2], type = "n", asp = 1,
       xlab = "Face-on x", ylab = "Face-on y", main = "Retained neighbour graph")
  if (length(edges_i) > 0) {
    segments(xy[edges_i, 1], xy[edges_i, 2], xy[edges_j, 1], xy[edges_j, 2], col = "grey82", lwd = 0.65)
  }
  points(xy[, 1], xy[, 2], pch = 21, bg = point_cols,
         col = ifelse(edge, "tomato3", "grey25"), lwd = ifelse(edge, 1.5, 0.7), cex = 1.18)
  legend("topright", legend = 0:6, pt.bg = neighbour_cols, pch = 21,
         title = "Neighbours", cex = 0.72, bty = "n")

  plot(xy[, 1], xy[, 2], asp = 1, pch = 21,
       bg = "grey94", col = "grey85", cex = 0.95,
       xlab = "Face-on x", ylab = "Face-on y", main = "Detected edge facets")
  if (any(edge)) {
    points(xy[edge, 1], xy[edge, 2], pch = 21, bg = point_cols[edge], col = "tomato3", lwd = 1.5, cex = 1.35)
  }
  legend("topright", legend = 0:6, pt.bg = neighbour_cols, pch = 21,
         title = "Edge neighbours", cex = 0.72, bty = "n")

  threshold_text <- if (is.finite(threshold)) sprintf(" | edge gap > %g deg", threshold) else ""
  mtext(sprintf("%s %s - 04B neighbours QC%s", cv_id, eye, threshold_text), outer = TRUE, cex = 1.25, font = 2)
  invisible(path)
}
plot_threshold_comparison <- function(facets, graphs, thresholds, path, xy = NULL) {
  if (is.null(xy)) xy <- make_face_on_xy(facets)
  neighbour_cols <- c("#440154", "#414487", "#2A788E", "#22A884", "#7AD151", "#FDE725", "#FFE066")
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  grDevices::png(path, width = 2400, height = 1600, res = 180)
  on.exit(grDevices::dev.off(), add = TRUE)
  op <- par(mfrow = c(2, 3), mar = c(3.2, 3.2, 3.1, 1.0), oma = c(1.0, 1.0, 3.2, 0.5))
  on.exit(par(op), add = TRUE)

  for (ii in seq_along(thresholds)) {
    thr <- thresholds[[ii]]
    g <- graphs[[ii]]
    edge <- as.logical(g$is_edge_facet)
    edge[is.na(edge)] <- FALSE
    counts <- suppressWarnings(as.integer(g$number_of_neighbours))
    counts[!is.finite(counts)] <- 0L
    point_cols <- neighbour_cols[pmax(0L, pmin(6L, counts)) + 1L]

    plot(
      xy[, 1], xy[, 2], asp = 1, pch = 21,
      bg = "grey94", col = "grey85", cex = 0.92,
      xlab = "Face-on x", ylab = "Face-on y",
      main = sprintf("gap > %g deg: %d edge facets", thr, sum(edge))
    )
    if (any(edge)) {
      points(xy[edge, 1], xy[edge, 2], pch = 21,
             bg = point_cols[edge], col = "tomato3", lwd = 1.5, cex = 1.30)
    }
    legend("topright", legend = 0:6, pt.bg = neighbour_cols, pch = 21,
           title = "Edge neighbours", cex = 0.68, bty = "n")
  }
  mtext("04B edge-threshold decision: detected edge facets coloured by retained neighbour count", outer = TRUE, cex = 1.25, font = 2)
  invisible(path)
}

main <- function() {
  if (!all(c("detect_facet_edges", "find_neighbours_edge_aware", "view_eye_face_on", "get_facet_normals_envelope") %in% getNamespaceExports("CV3D"))) {
    stop(
      "The installed CV3D package does not provide all functions required by the 04B neighbour/QC workflow. Install the accompanying current CV3D package first.",
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

    # Run the exact final neighbour method at every candidate threshold so the
    # decision figure shows what each threshold would actually retain.
    graphs <- lapply(thresholds, function(thr) run_edge_aware(facets, thr))
    edge_info <- graphs[[1]]
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
    xy <- make_face_on_xy(facets)
    plot_threshold_comparison(facets, graphs, thresholds, task$output_comparison_png_abs, xy = xy)

    counts <- stats::setNames(vapply(graphs, function(g) sum(as.logical(g$is_edge_facet), na.rm = TRUE), integer(1)), as.character(thresholds))
    write_status("success", "04B edge-threshold comparison created successfully.", list(summary = list(
      mode = "preview",
      thresholds_deg = thresholds,
      edge_counts = as.list(counts),
      output_comparison_png = task$output_comparison_png,
      output_edge_gap_table = task$output_edge_gap_table
    )))
    return(invisible(NULL))
  }

  if (mode == "qc") {
    input_neighbours <- normalizePath(task$input_neighbours_abs, winslash = "/", mustWork = TRUE)
    neighbours_df <- suppressMessages(readr::read_csv(input_neighbours, show_col_types = FALSE))
    output_png <- task$output_qc_png_abs
    if (is.null(output_png) || !nzchar(as.character(output_png))) stop("04B QC task is missing output_qc_png_abs.", call. = FALSE)
    plot_neighbours_qc(neighbours_df, output_png, task$cv_id %||% "CVXXXX", task$eye %||% "eye?")
    write_status("success", "04B neighbour QC plot created successfully.", list(summary = list(
      mode = "qc",
      output_qc_png = task$output_qc_png,
      facet_count = nrow(neighbours_df)
    )))
    return(invisible(NULL))
  }

  if (mode == "final") {
    threshold <- as.numeric(task$edge_gap_threshold_deg %||% 90)
    if (!is.finite(threshold)) stop("edge_gap_threshold_deg must be finite.", call. = FALSE)

    g <- run_edge_aware(facets, threshold)

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
