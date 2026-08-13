#!/usr/bin/env Rscript

# Usage:
#   Rscript CV3D_R_plot_facet_points_on_local_heights.R <task_json>
#
# UI/inspection utility only. Scientific logic remains in the package and
# workflow runners; this script just creates diagnostic PNGs.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript CV3D_R_plot_facet_points_on_local_heights.R <task_json>", call. = FALSE)
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

task <- jsonlite::fromJSON(task_json, simplifyVector = TRUE)
status_file <- task$status_file_abs

write_status <- function(status, message, extra = list()) {
  payload <- c(
    list(
      status = status,
      message = message,
      task_json = task_json,
      script_version = "CV3D_R_plot_facet_points_on_local_heights_0.2.0"
    ),
    extra
  )
  dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(payload, status_file, pretty = TRUE, auto_unbox = TRUE, null = "null")
}

make_viridis <- function(n = 256) {
  grDevices::colorRampPalette(
    c("#440154", "#482878", "#3E4989", "#31688E", "#26828E",
      "#1F9E89", "#35B779", "#6DCD59", "#B4DE2C", "#FDE725")
  )(n)
}

height_to_col <- function(x, pal) {
  x <- as.numeric(x)
  out <- rep("#808080", length(x))
  finite <- is.finite(x)
  if (!any(finite)) return(out)

  rng <- range(x[finite], na.rm = TRUE)
  if (!all(is.finite(rng)) || diff(rng) == 0) {
    out[finite] <- pal[round(length(pal) / 2)]
    return(out)
  }

  scaled <- (x - rng[1]) / diff(rng)
  scaled[!is.finite(scaled)] <- 0.5
  idx <- round(scaled * (length(pal) - 1)) + 1
  idx <- pmax(1, pmin(length(pal), idx))
  pal[idx]
}

add_continuous_legend <- function(height_range, pal, height_column) {
  if (!all(is.finite(height_range)) || diff(height_range) == 0) return(invisible(NULL))

  usr <- graphics::par("usr")
  x_span <- usr[2] - usr[1]
  y_span <- usr[4] - usr[3]

  x_left <- usr[2] - 0.080 * x_span
  x_right <- usr[2] - 0.045 * x_span
  y_bottom <- usr[3] + 0.12 * y_span
  y_top <- usr[4] - 0.12 * y_span

  n <- length(pal)
  y0 <- seq(y_bottom, y_top, length.out = n + 1)
  for (i in seq_len(n)) {
    graphics::rect(x_left, y0[i], x_right, y0[i + 1], col = pal[i], border = NA)
  }
  graphics::rect(x_left, y_bottom, x_right, y_top, border = "black")

  tick_values <- pretty(height_range, n = 5)
  tick_values <- tick_values[tick_values >= height_range[1] & tick_values <= height_range[2]]
  if (length(tick_values) > 0) {
    tick_y <- y_bottom + (tick_values - height_range[1]) / diff(height_range) * (y_top - y_bottom)
    segments(x_right, tick_y, x_right + 0.012 * x_span, tick_y)
    text(x_right + 0.018 * x_span, tick_y, labels = signif(tick_values, 4), adj = c(0, 0.5), cex = 0.7)
  }

  graphics::text(
    x_left,
    y_top + 0.055 * y_span,
    labels = height_column,
    adj = c(0, 0),
    cex = 0.75
  )
}


choose_projection_axes <- function(df) {
  ranges <- vapply(c("x", "y", "z"), function(axis) {
    vals <- as.numeric(df[[axis]])
    vals <- vals[is.finite(vals)]
    if (length(vals) == 0) return(0)
    diff(range(vals, na.rm = TRUE))
  }, numeric(1))

  axes <- names(sort(ranges, decreasing = TRUE))[1:2]
  if (length(axes) < 2 || any(is.na(axes))) axes <- c("x", "y")
  axes
}

set_cv3d_rgl_window_size <- function(scale = 3) {
  width <- 600 * scale
  height <- 450 * scale
  try(rgl::par3d(windowRect = c(40, 40, 40 + width, 40 + height)), silent = TRUE)
}

open_rgl_overlay <- function(local_heights, overlay_points, bg_cols, overlay_color, point_label, sphere_radius) {
  if (!requireNamespace("rgl", quietly = TRUE)) {
    stop("Package rgl is required for the interactive 3D window.", call. = FALSE)
  }

  if (!requireNamespace("CV3D", quietly = TRUE)) {
    stop("Package CV3D is required for the standardised face-on QC view.", call. = FALSE)
  }

  normal_cols <- c("norm.x", "norm.y", "norm.z")
  have_normals <- all(normal_cols %in% names(local_heights))
  view <- NULL
  if (have_normals) {
    view <- CV3D::view_eye_face_on(
      local_heights,
      projection = "3D",
      col = bg_cols,
      rgl_size = 3,
      axes = TRUE
    )
    set_cv3d_rgl_window_size(scale = 3)
  } else {
    message("Surface normals unavailable; using the legacy unconstrained rgl view.")
    rgl::open3d(useNULL = FALSE)
    set_cv3d_rgl_window_size(scale = 3)
    rgl::plot3d(
      local_heights[, c("x", "y", "z")],
      aspect = "iso",
      col = bg_cols,
      size = 3,
      xlab = "x",
      ylab = "y",
      zlab = "z"
    )
  }

  if (nrow(overlay_points) > 0) {
    if (have_normals) {
      overlay_plot <- sweep(
        as.matrix(overlay_points[, c("x", "y", "z")]),
        2,
        view$cloud_centre,
        "-"
      )
    } else {
      overlay_plot <- as.matrix(overlay_points[, c("x", "y", "z")])
    }

    rgl::spheres3d(
      x = overlay_plot[, 1],
      y = overlay_plot[, 2],
      z = overlay_plot[, 3],
      radius = sphere_radius,
      color = overlay_color,
      alpha = 1
    )
  }

  rgl::title3d(main = paste("Local heights +", point_label))
}


get_task_string <- function(x) {
  if (is.null(x) || length(x) == 0) return(NA_character_)
  x <- as.character(x[[1]])
  if (is.na(x) || !nzchar(x)) return(NA_character_)
  x
}

require_existing_path <- function(x, label) {
  path <- get_task_string(x)
  if (is.na(path)) stop(label, " is missing in the task JSON.", call. = FALSE)
  normalizePath(path, winslash = "/", mustWork = TRUE)
}

resolve_output_path <- function(abs_value, rel_value, analysis_folder, label) {
  abs_path <- get_task_string(abs_value)
  if (!is.na(abs_path)) return(abs_path)

  rel_path <- get_task_string(rel_value)
  root <- get_task_string(analysis_folder)
  if (!is.na(rel_path) && !is.na(root)) {
    return(file.path(root, rel_path))
  }

  stop(label, " is missing in the task JSON.", call. = FALSE)
}

ensure_output_dir <- function(path, label) {
  path <- get_task_string(path)
  if (is.na(path)) stop(label, " is missing or invalid.", call. = FALSE)
  out_dir <- dirname(path)
  if (is.na(out_dir) || !nzchar(out_dir) || out_dir == ".") {
    stop(label, " has no valid parent directory: ", path, call. = FALSE)
  }
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  path
}

read_facet_estimate <- function(csv_path) {
  if (!file.exists(csv_path)) return(NA_real_)
  tbl <- tryCatch(
    suppressMessages(readr::read_csv(csv_path, show_col_types = FALSE)),
    error = function(e) NULL
  )
  if (is.null(tbl) || nrow(tbl) == 0) return(NA_real_)

  candidate_cols <- c("facet_size_estimate", "facet_estimate", "estimate", "value")
  col_name <- candidate_cols[candidate_cols %in% names(tbl)][1]
  if (is.na(col_name) || length(col_name) == 0) {
    vals <- suppressWarnings(as.numeric(unlist(tbl[1, ], use.names = FALSE)))
    vals <- vals[is.finite(vals)]
    if (length(vals) == 0) return(NA_real_)
    return(vals[[1]])
  }

  vals <- suppressWarnings(as.numeric(tbl[[col_name]]))
  vals <- vals[is.finite(vals)]
  if (length(vals) == 0) return(NA_real_)
  vals[[1]]
}

resolve_facet_estimate <- function(task, points_csv, local_heights_csv) {
  direct <- suppressWarnings(as.numeric(get_task_string(task$facet_estimate)))
  if (is.finite(direct) && direct > 0) return(direct)

  cv_id <- get_task_string(task$cv_id)
  search_paths <- character(0)

  for (base_path in c(points_csv, local_heights_csv)) {
    eye_dir <- dirname(base_path)
    specimen_dir <- dirname(eye_dir)
    if (!is.na(cv_id) && nzchar(cv_id)) {
      search_paths <- c(search_paths, file.path(specimen_dir, paste0("01_", cv_id, "_facet_size_estimate.csv")))
    }
    search_paths <- c(search_paths, list.files(specimen_dir, pattern = "^01_.*_facet_size_estimate\\.csv$", full.names = TRUE))
  }

  search_paths <- unique(search_paths[file.exists(search_paths)])
  for (p in search_paths) {
    val <- read_facet_estimate(p)
    if (is.finite(val) && val > 0) return(val)
  }

  NA_real_
}

draw_overlay_circles <- function(overlay_points, x_axis, y_axis, radius, fill_col) {
  if (nrow(overlay_points) == 0) return(invisible(NULL))
  graphics::symbols(
    x = overlay_points[[x_axis]],
    y = overlay_points[[y_axis]],
    circles = rep(radius, nrow(overlay_points)),
    inches = FALSE,
    add = TRUE,
    bg = fill_col,
    fg = "black"
  )
}

main <- function() {
  local_heights_csv <- require_existing_path(task$input_local_heights_abs, "input_local_heights_abs")
  points_csv <- require_existing_path(task$input_points_abs, "input_points_abs")
  out_png <- resolve_output_path(
    task$output_plot_png_abs,
    task$output_plot_png,
    task$analysis_folder,
    "output_plot_png_abs"
  )
  out_png <- ensure_output_dir(out_png, "output_plot_png_abs")

  height_column <- get_task_string(task$height_column)
  if (is.na(height_column)) stop("height_column is missing in the task JSON.", call. = FALSE)

  point_label <- get_task_string(task$point_label)
  if (is.na(point_label)) point_label <- "facet points"

  point_kind <- get_task_string(task$point_kind)
  if (is.na(point_kind)) point_kind <- "facet_points"

  overlay_color <- get_task_string(task$overlay_color)
  if (is.na(overlay_color)) overlay_color <- "red"

  open_rgl_window <- isTRUE(task$open_rgl_window)

  message("Reading local-height background: ", local_heights_csv)
  local_heights <- suppressMessages(readr::read_csv(local_heights_csv, show_col_types = FALSE))

  message("Reading overlay points: ", points_csv)
  overlay_points <- suppressMessages(readr::read_csv(points_csv, show_col_types = FALSE))

  missing_local <- setdiff(c("x", "y", "z", height_column), names(local_heights))
  if (length(missing_local) > 0) {
    stop(
      "Local-height table is missing required column(s): ",
      paste(missing_local, collapse = ", "),
      call. = FALSE
    )
  }

  missing_points <- setdiff(c("x", "y", "z"), names(overlay_points))
  if (length(missing_points) > 0) {
    stop(
      "Overlay point table is missing required column(s): ",
      paste(missing_points, collapse = ", "),
      call. = FALSE
    )
  }

  local_heights <- local_heights %>%
    dplyr::mutate(
      x = as.numeric(x),
      y = as.numeric(y),
      z = as.numeric(z),
      .height_value_for_plot = as.numeric(.data[[height_column]])
    ) %>%
    dplyr::filter(is.finite(x), is.finite(y), is.finite(z), is.finite(.height_value_for_plot))

  overlay_points <- overlay_points %>%
    dplyr::mutate(
      x = as.numeric(x),
      y = as.numeric(y),
      z = as.numeric(z)
    ) %>%
    dplyr::filter(is.finite(x), is.finite(y), is.finite(z))

  if (nrow(local_heights) == 0) {
    stop("No finite local-height background points available for plotting.", call. = FALSE)
  }

  facet_estimate <- resolve_facet_estimate(task, points_csv, local_heights_csv)
  if (!is.finite(facet_estimate) || facet_estimate <= 0) {
    stop("Could not resolve a valid facet estimate for sphere overlays.", call. = FALSE)
  }
  overlay_diameter <- 0.33 * facet_estimate
  overlay_radius <- overlay_diameter / 2

  pal <- make_viridis(256)
  bg_cols <- height_to_col(local_heights$.height_value_for_plot, pal)
  height_range <- range(local_heights$.height_value_for_plot, na.rm = TRUE)

  projection_axes <- choose_projection_axes(local_heights)
  x_axis <- projection_axes[1]
  y_axis <- projection_axes[2]

  message("Creating PNG: ", out_png)
  message("Using automatic largest-spread projection: ", x_axis, "/", y_axis)
  grDevices::png(out_png, width = 1500, height = 1500, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({
    graphics::par(old_par)
    try(grDevices::dev.off(), silent = TRUE)
  }, add = TRUE)

  graphics::plot(
    local_heights[[x_axis]],
    local_heights[[y_axis]],
    pch = 16,
    cex = 0.18,
    col = bg_cols,
    asp = 1,
    main = paste0(task$cv_id, " ", task$eye, ": ", point_label, " on local heights"),
    xlab = x_axis,
    ylab = y_axis
  )
  add_continuous_legend(height_range, pal, height_column)

  if (nrow(overlay_points) > 0) {
    draw_overlay_circles(
      overlay_points = overlay_points,
      x_axis = x_axis,
      y_axis = y_axis,
      radius = overlay_radius,
      fill_col = overlay_color
    )
  }

  graphics::legend(
    "bottomright",
    legend = c(paste0(point_label, " (sphere diameter = 0.33 × facet estimate)")),
    pt.bg = overlay_color,
    col = "black",
    pch = 21,
    cex = 0.8,
    bg = "white"
  )

  grDevices::dev.off()

  if (open_rgl_window) {
    message("Opening interactive rgl overlay window. Close it to finish this task.")
    open_rgl_overlay(local_heights, overlay_points, bg_cols, overlay_color, point_label, overlay_radius)
    repeat {
      Sys.sleep(0.2)
      cur <- tryCatch(rgl::rgl.cur(), error = function(e) 0)
      if (is.null(cur) || identical(cur, 0L) || identical(cur, 0)) break
    }
  }

  if (!file.exists(out_png)) {
    stop("PNG was not created: ", out_png, call. = FALSE)
  }

  write_status(
    "success",
    paste0("Facet point overlay plot created successfully for ", point_label, "."),
    list(
      summary = list(
        point_kind = point_kind,
        point_label = point_label,
        input_local_heights = task$input_local_heights,
        input_points = task$input_points,
        output_plot_png = task$output_plot_png,
        height_column = height_column,
        background_source = task$background_source,
        projection_axes = paste(projection_axes, collapse = "/"),
        open_rgl_window = open_rgl_window,
        background_point_count = nrow(local_heights),
        overlay_point_count = nrow(overlay_points),
        facet_estimate = facet_estimate,
        overlay_sphere_diameter = overlay_diameter,
        overlay_sphere_radius = overlay_radius
      )
    )
  )
}

tryCatch(
  main(),
  error = function(e) {
    msg <- conditionMessage(e)
    tb <- paste(utils::capture.output(traceback()), collapse = "\n")
    message("CV3D facet point overlay plot failed: ", msg)
    if (nzchar(tb)) message(tb)
    write_status("failed", msg, list(traceback = tb))
    quit(status = 1, save = "no")
  }
)
