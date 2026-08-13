#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript CV3D_R_05C_projection.R <task_json>", call. = FALSE)

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

SCRIPT_VERSION <- "0.3.0-view-angles"
SCRIPT_NAME <- "CV3D_R_05C_projection.R"

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

write_csv_safe <- function(df, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  readr::write_csv(df, path)
}


rescale01 <- function(x) {
  x <- suppressWarnings(as.numeric(x))
  good <- is.finite(x)
  out <- rep(NA_real_, length(x))
  if (!any(good)) return(out)
  xr <- range(x[good], na.rm = TRUE)
  if (!is.finite(xr[1]) || !is.finite(xr[2])) return(out)
  if (xr[1] == xr[2]) {
    out[good] <- 0.5
  } else {
    out[good] <- (x[good] - xr[1]) / (xr[2] - xr[1])
  }
  out
}

map_colors <- function(values, n = 256, na_col = "grey80") {
  values <- suppressWarnings(as.numeric(values))
  cols <- rep(na_col, length(values))
  good <- is.finite(values)
  pal <- viridisLite::viridis(n)
  if (any(good)) {
    scaled <- rescale01(values[good])
    idx <- pmin(n, pmax(1, floor(scaled * (n - 1)) + 1))
    cols[good] <- pal[idx]
  }
  list(cols = cols, pal = pal)
}

point_cex_from_size <- function(size, base = 0.65) {
  size <- suppressWarnings(as.numeric(size))
  good <- is.finite(size) & size > 0
  cex <- rep(base, length(size))
  if (!any(good)) return(cex)
  scaled <- rescale01(size)
  cex[good] <- 0.45 + 0.85 * scaled[good]
  cex
}

plot_range <- function(x, pad_fraction = 0.08) {
  x <- suppressWarnings(as.numeric(x))
  good <- is.finite(x)
  if (!any(good)) return(c(-1, 1))
  r <- range(x[good], na.rm = TRUE)
  span <- diff(r)
  if (!is.finite(span) || span <= 0) span <- max(abs(r), 1, na.rm = TRUE)
  r + c(-1, 1) * span * pad_fraction
}

colorbar_inset <- function(values, pal, label) {
  values <- suppressWarnings(as.numeric(values))
  good <- is.finite(values)
  if (!any(good)) {
    mtext(paste0(label, "\n(all NA)"), side = 4, line = 2.8, cex = 0.75)
    return(invisible(NULL))
  }
  zlim <- range(values[good], na.rm = TRUE)
  usr <- par("usr")
  x0 <- usr[2] + 0.04 * (usr[2] - usr[1])
  x1 <- usr[2] + 0.10 * (usr[2] - usr[1])
  y0 <- usr[3]
  y1 <- usr[4]
  par(xpd = NA)
  rasterImage(as.raster(matrix(rev(pal), ncol = 1)), x0, y0, x1, y1)
  at <- pretty(zlim, n = 4)
  at <- at[at >= zlim[1] & at <= zlim[2]]
  if (length(at) == 0) at <- zlim
  y_at <- y0 + (at - zlim[1]) / max(zlim[2] - zlim[1], .Machine$double.eps) * (y1 - y0)
  axis(4, at = y_at, labels = formatC(at, digits = 4, format = "fg"), las = 1, cex.axis = 0.72)
  mtext(label, side = 4, line = 3.8, cex = 0.82)
  par(xpd = FALSE)
}

make_projection_png <- function(df, view_name, path, title) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)

  view_defs <- list(
    front = list(x = "corn.proj.x", y = "corn.proj.z", sx = 1,  sy = 1,  xlab = "x projection (µm)",  ylab = "z projection (µm)"),
    back  = list(x = "corn.proj.x", y = "corn.proj.z", sx = -1, sy = 1,  xlab = "-x projection (µm)", ylab = "z projection (µm)"),
    left  = list(x = "corn.proj.y", y = "corn.proj.z", sx = 1,  sy = 1,  xlab = "y projection (µm)",  ylab = "z projection (µm)"),
    right = list(x = "corn.proj.y", y = "corn.proj.z", sx = -1, sy = 1,  xlab = "-y projection (µm)", ylab = "z projection (µm)"),
    top   = list(x = "corn.proj.x", y = "corn.proj.y", sx = 1,  sy = 1,  xlab = "x projection (µm)",  ylab = "y projection (µm)"),
    bottom = list(x = "corn.proj.x", y = "corn.proj.y", sx = 1, sy = -1, xlab = "x projection (µm)",  ylab = "-y projection (µm)")
  )
  vd <- view_defs[[view_name]] %||% view_defs$top

  x <- suppressWarnings(as.numeric(df[[vd$x]])) * vd$sx
  y <- suppressWarnings(as.numeric(df[[vd$y]])) * vd$sy
  colour_value <- if ("projection_ray_length_um" %in% names(df)) df$projection_ray_length_um else df$elevation
  mapped <- map_colors(colour_value)
  cex <- if ("facet_size_smoothed" %in% names(df)) point_cex_from_size(df$facet_size_smoothed) else rep(0.65, length(x))

  png(path, width = 1800, height = 1600, res = 220)
  op <- par(mar = c(4, 4, 4, 6))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot(
    x, y,
    pch = 16,
    cex = cex,
    col = mapped$cols,
    asp = 1,
    xlab = vd$xlab,
    ylab = vd$ylab,
    main = title,
    xlim = plot_range(x),
    ylim = plot_range(y)
  )
  grid(col = "grey88", lty = "dotted")
  points(x, y, pch = 16, cex = cex, col = mapped$cols)
  colorbar_inset(colour_value, mapped$pal, "Ray length (µm)")
  mtext(sprintf("Projected facets: %s | sphere diameter: %.4g cm", sum(is.finite(x) & is.finite(y)), unique(df$projection_sphere_size_cm)[1]), side = 3, line = 0.25, cex = 0.78)
  invisible(path)
}

make_view_angles_png <- function(df, path, cv_id, eye) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  x <- suppressWarnings(as.numeric(df$azimuth))
  y <- suppressWarnings(as.numeric(df$elevation))
  colour_value <- if ("projection_ray_length_um" %in% names(df)) df$projection_ray_length_um else seq_along(x)
  mapped <- map_colors(colour_value)
  cex <- if ("facet_size_smoothed" %in% names(df)) point_cex_from_size(df$facet_size_smoothed) else rep(0.65, length(x))

  png(path, width = 1800, height = 1200, res = 220)
  op <- par(mar = c(4, 4, 4, 6))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot(
    x, y,
    pch = 16,
    cex = cex,
    col = mapped$cols,
    xlab = "azimuth (deg)",
    ylab = "elevation (deg)",
    main = sprintf("%s %s - 05C corneal projection elevation/azimuth", cv_id, eye),
    xlim = plot_range(x),
    ylim = plot_range(y)
  )
  grid(col = "grey88", lty = "dotted")
  points(x, y, pch = 16, cex = cex, col = mapped$cols)
  colorbar_inset(colour_value, mapped$pal, "Ray length (µm)")
  invisible(path)
}

main <- function() {
  global_file <- normalizePath(task$input_global_coordinates_abs, winslash = "/", mustWork = TRUE)
  message("Reading global coordinates: ", global_file)
  df <- suppressMessages(readr::read_csv(global_file, show_col_types = FALSE))
  need_cols(df, c("facet_id", "x_global", "y_global", "z_global", "norm.x_global", "norm.y_global", "norm.z_global"), "Global-coordinate table")

  cp_diam_um <- suppressWarnings(as.numeric(task$parameters$corneal_projection_sphere_size_um %||% NA_real_))
  if (!is.finite(cp_diam_um) || cp_diam_um <= 0) {
    cp_diam_cm <- suppressWarnings(as.numeric(task$parameters$corneal_projection_sphere_size_cm %||% 15.0))
    if (!is.finite(cp_diam_cm) || cp_diam_cm <= 0) cp_diam_cm <- 15.0
    cp_diam_um <- cp_diam_cm * 10000
  }
  cp_diam_cm <- cp_diam_um / 10000
  sphere_radius <- cp_diam_um / 2
  center_mode <- as.character(task$parameters$projection_center_mode %||% "between_eyes")

  center_eye <- c(mean(df$x_global, na.rm = TRUE), mean(df$y_global, na.rm = TRUE), mean(df$z_global, na.rm = TRUE))
  center_source <- "current_eye_centroid"
  if (center_mode == "eye_center") {
    sphere_center <- center_eye
  } else if (center_mode == "head_landmark_center") {
    sphere_center <- c(0, 0, 0)
    center_source <- "global_anatomical_origin"
  } else {
    center_mode <- "between_eyes"
    other_path <- as.character(task$input_other_eye_global_coordinates_abs %||% "")
    if (nzchar(other_path) && file.exists(other_path)) {
      other_df <- suppressMessages(readr::read_csv(other_path, show_col_types = FALSE))
      need_cols(other_df, c("x_global", "y_global", "z_global"), "Other-eye global-coordinate table")
      other_center <- c(
        mean(other_df$x_global, na.rm = TRUE),
        mean(other_df$y_global, na.rm = TRUE),
        mean(other_df$z_global, na.rm = TRUE)
      )
      if (all(is.finite(other_center))) {
        sphere_center <- (center_eye + other_center) / 2
        center_source <- "midpoint_of_both_eye_centroids"
      } else {
        sphere_center <- center_eye
        sphere_center[1] <- 0
        center_source <- "single_eye_midline_estimate"
      }
    } else {
      sphere_center <- center_eye
      sphere_center[1] <- 0
      center_source <- "single_eye_midline_estimate"
    }
  }

  message("Calculating corneal projection intersections with sphere diameter ", cp_diam_cm, " cm.")
  out <- df %>%
    dplyr::mutate(
      corn.proj.x = NA_real_, corn.proj.y = NA_real_, corn.proj.z = NA_real_,
      projection_ray_length_um = NA_real_,
      elevation = NA_real_, azimuth = NA_real_
    )

  for (i in seq_len(nrow(out))) {
    point <- c(out$x_global[i], out$y_global[i], out$z_global[i])
    vec <- c(out$norm.x_global[i], out$norm.y_global[i], out$norm.z_global[i])
    if (!all(is.finite(point)) || !all(is.finite(vec))) next
    xyz <- CV3D::ray_sphere_intersection(
      point = point,
      direction = vec,
      sphere_center = sphere_center,
      sphere_radius = sphere_radius
    )
    out$corn.proj.x[i] <- xyz[1]
    out$corn.proj.y[i] <- xyz[2]
    out$corn.proj.z[i] <- xyz[3]
    if (all(is.finite(xyz))) {
      out$projection_ray_length_um[i] <- sqrt(sum((xyz - point)^2))
    }
  }

  view_angles <- CV3D::cartesian_to_view_angles(
    x = out$corn.proj.x,
    y = out$corn.proj.y,
    z = out$corn.proj.z,
    center = sphere_center
  )
  out$elevation <- view_angles$elevation
  out$azimuth <- view_angles$azimuth

  out <- out %>%
    dplyr::mutate(
      projection_center_mode = center_mode,
      projection_center_source = center_source,
      projection_sphere_center_x = sphere_center[1],
      projection_sphere_center_y = sphere_center[2],
      projection_sphere_center_z = sphere_center[3],
      projection_sphere_radius_um = sphere_radius,
      projection_sphere_size_um = cp_diam_um,
      projection_sphere_size_cm = cp_diam_cm
    )

  write_csv_safe(out, task$output_corneal_projections_abs)

  valid_projection <- is.finite(out$corn.proj.x) & is.finite(out$corn.proj.y) & is.finite(out$corn.proj.z)

  write_status("success", "05C corneal projections completed successfully.", list(summary = list(
    facet_count = nrow(out),
    projected_facet_count = sum(valid_projection),
    projection_center_mode = center_mode,
    projection_center_source = center_source,
    projection_sphere_size_cm = cp_diam_cm,
    projection_sphere_size_um = cp_diam_um,
    projection_sphere_radius_um = sphere_radius,
    output_corneal_projections = task$output_corneal_projections
  )))
}

tryCatch(main(), error = function(e) {
  msg <- conditionMessage(e)
  message("CV3D 05C corneal projections failed: ", msg)
  write_status("failed", msg, list(traceback = paste(utils::capture.output(traceback()), collapse = "\n")))
  quit(status = 1, save = "no")
})
