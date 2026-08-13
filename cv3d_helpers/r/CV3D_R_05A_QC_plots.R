#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript CV3D_R_05A_QC_plots.R <task_json>", call. = FALSE)

task_json <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

safe_require <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) stop("Required R package is not installed: ", pkg, call. = FALSE)
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

safe_require("jsonlite")
safe_require("readr")
safe_require("dplyr")
safe_require("viridisLite")
safe_require("rgl")
safe_require("CV3D")

SCRIPT_VERSION <- "0.1.20-report-facet-values"
SCRIPT_NAME <- "CV3D_R_05A_QC_plots.R"

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

read_csv_safe <- function(path) {
  suppressMessages(readr::read_csv(path, show_col_types = FALSE))
}

cv3d_standard_face_on_view <- function(df) {
  need_cols(df, c("x", "y", "z", "norm.x", "norm.y", "norm.z"), "Face-on plotting table")
  if (!"view_eye_face_on" %in% getNamespaceExports("CV3D")) {
    stop("The installed CV3D package does not export view_eye_face_on(). Reinstall/update CV3D first.", call. = FALSE)
  }
  tmp <- tempfile(fileext = ".pdf")
  grDevices::pdf(tmp, width = 4, height = 4)
  dev_open <- TRUE
  on.exit({
    if (isTRUE(dev_open)) try(grDevices::dev.off(), silent = TRUE)
    try(unlink(tmp), silent = TRUE)
  }, add = TRUE)
  view <- CV3D::view_eye_face_on(
    df, projection = "2D", reverse = FALSE, long_axis_vertical = TRUE,
    col = NA, pch = NA, cex = 0, axes = FALSE, xlab = "", ylab = ""
  )
  grDevices::dev.off()
  dev_open <- FALSE
  unlink(tmp)
  view
}

face_on_xy <- function(df, view = NULL) {
  if (is.null(view)) view <- cv3d_standard_face_on_view(df)
  xy <- as.matrix(view$projected_coordinates)
  if (ncol(xy) != 2 || nrow(xy) != nrow(df)) {
    stop("view_eye_face_on() returned invalid projected coordinates.", call. = FALSE)
  }
  storage.mode(xy) <- "double"
  colnames(xy) <- c("Face-on x", "Face-on y")
  list(xy = xy, view = view)
}

set_cv3d_standard_rgl_view <- function(view, zoom = 0.82) {
  user_matrix <- as.matrix(view$userMatrix)
  if (!all(dim(user_matrix) == c(4, 4)) || any(!is.finite(user_matrix))) {
    stop("view_eye_face_on() returned an invalid rgl userMatrix.", call. = FALSE)
  }
  rgl::view3d(userMatrix = user_matrix, fov = 0, zoom = zoom, scale = c(1, 1, 1))
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

point_cex_from_size <- function(size, base = 1.2) {
  size <- suppressWarnings(as.numeric(size))
  good <- is.finite(size)
  cex <- rep(base, length(size))
  if (!any(good)) return(cex)
  scaled <- rescale01(size)
  cex[good] <- 0.7 + 1.1 * scaled[good]
  cex
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

plot_metric_panel <- function(df, x, y, value_col, title_text, point_cex, pch = 16) {
  need_cols(df, value_col, title_text)
  vals <- suppressWarnings(as.numeric(df[[value_col]]))
  mapped <- map_colors(vals)
  pad_x <- max(diff(range(x, na.rm = TRUE)) * 0.08, 1e-6)
  pad_y <- max(diff(range(y, na.rm = TRUE)) * 0.08, 1e-6)
  plot(x, y, asp = 1, pch = pch, cex = point_cex, col = mapped$cols,
       xlab = "Face-on x (um)", ylab = "Face-on y (um)", main = title_text,
       xlim = range(x, na.rm = TRUE) + c(-pad_x, pad_x),
       ylim = range(y, na.rm = TRUE) + c(-pad_y, pad_y))
  colorbar_inset(vals, mapped$pal, title_text)
}

plot_optics_png <- function(df, out_png, cv_id, eye) {
  need_cols(df, c("x", "y", "z", "norm.x", "norm.y", "norm.z", "facet_size_smoothed", "interfacet_angle_deg", "eye_parameter", "acuity_cpd"), "Optic-parameter table")
  fo <- face_on_xy(df)
  x <- fo$xy[, 1]; y <- fo$xy[, 2]
  cex <- point_cex_from_size(df$facet_size_smoothed)
  dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)
  png(out_png, width = 2200, height = 1800, res = 220)
  op <- par(mfrow = c(2, 2), mar = c(4, 4, 4, 6), oma = c(0, 0, 2, 0))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot_metric_panel(df, x, y, "facet_size_smoothed", "Facet size", cex)
  plot_metric_panel(df, x, y, "interfacet_angle_deg", "IF angle (deg)", cex)
  plot_metric_panel(df, x, y, "eye_parameter", "Eye parameter", cex)
  plot_metric_panel(df, x, y, "acuity_cpd", "Acuity (cpd)", cex)
  mtext(sprintf("%s %s - 05A optic parameters, standard CV3D face-on view", cv_id, eye), outer = TRUE, cex = 1.2, font = 2)
  invisible(out_png)
}

normal_direction_colors <- function(nrm, na_col = "grey75") {
  # Keep this explicitly as an n x 3 matrix. Base R's pmin/pmax can drop
  # matrix dimensions when a scalar is the first argument, which caused the
  # direction-colour plot to fail at rgb01[, 1] with
  # "incorrect number of dimensions".
  nrm <- as.matrix(nrm)
  if (ncol(nrm) != 3) {
    stop("Normal-direction colour mapping requires an n x 3 normal matrix.", call. = FALSE)
  }
  cols <- rep(na_col, nrow(nrm))
  good <- stats::complete.cases(nrm)
  if (!any(good)) return(cols)
  rgb01 <- (nrm[good, , drop = FALSE] + 1) / 2
  rgb01[rgb01 < 0] <- 0
  rgb01[rgb01 > 1] <- 1
  cols[good] <- grDevices::rgb(rgb01[, 1], rgb01[, 2], rgb01[, 3])
  cols
}

normal_axis_direction_key <- function() {
  axes <- rbind(
    `+x` = c( 1,  0,  0),
    `-x` = c(-1,  0,  0),
    `+y` = c( 0,  1,  0),
    `-y` = c( 0, -1,  0),
    `+z` = c( 0,  0,  1),
    `-z` = c( 0,  0, -1)
  )
  list(labels = rownames(axes), cols = normal_direction_colors(axes))
}


normal_method_label <- function(df) {
  if (!"normal_method" %in% names(df)) return("facet normals")
  method <- unique(stats::na.omit(as.character(df$normal_method)))
  if (length(method) < 1) return("facet normals")
  method <- method[[1]]
  if (tolower(method) == "envelope") {
    factor <- if ("normal_envelope_factor" %in% names(df)) {
      suppressWarnings(as.numeric(stats::na.omit(df$normal_envelope_factor))[1])
    } else {
      NA_real_
    }
    if (is.finite(factor)) return(sprintf("envelope %.4gx", factor))
    return("envelope")
  }
  if (tolower(method) == "original") return("original triangle-based")
  method
}

plot_normals_png <- function(df, out_png, cv_id, eye, normal_length_facet_size_factor = 5.0, show_normals = TRUE, show_facet_labels = FALSE) {
  need_cols(df, c("x", "y", "z", "norm.x", "norm.y", "norm.z"), "Facet-normal table")
  fo <- face_on_xy(df)
  view <- fo$view
  x <- fo$xy[, 1]; y <- fo$xy[, 2]
  nrm <- normalize_normals(df)
  dir_cols <- normal_direction_colors(nrm)
  u <- as.numeric(nrm %*% as.numeric(view$x_direction))
  v <- as.numeric(nrm %*% as.numeric(view$y_direction))
  size <- if ("facet_size_smoothed" %in% names(df)) suppressWarnings(as.numeric(df$facet_size_smoothed)) else rep(NA_real_, length(x))
  normal_length <- normal_lengths_from_facet_size(df, normal_length_facet_size_factor)
  cex <- point_cex_from_size(size, base = 1.0)
  x_end <- x + u * normal_length; y_end <- y + v * normal_length
  plot_x <- if (isTRUE(show_normals)) c(x, x_end) else x
  plot_y <- if (isTRUE(show_normals)) c(y, y_end) else y
  pad_x <- max(diff(range(plot_x, na.rm = TRUE)) * 0.08, 1e-6)
  pad_y <- max(diff(range(plot_y, na.rm = TRUE)) * 0.08, 1e-6)
  method_text <- normal_method_label(df)
  dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)
  png(out_png, width = 1900, height = 1650, res = 220)
  op <- par(mar = c(4, 4, 4.5, 4))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot(x, y, type = "n", asp = 1, xlab = "Face-on x (um)", ylab = "Face-on y (um)",
       main = sprintf("%s %s - 05A %s, standard CV3D face-on view", cv_id, eye, method_text),
       xlim = range(plot_x, na.rm = TRUE) + c(-pad_x, pad_x),
       ylim = range(plot_y, na.rm = TRUE) + c(-pad_y, pad_y))
  if (isTRUE(show_normals)) segments(x0 = x, y0 = y, x1 = x_end, y1 = y_end, col = dir_cols, lwd = 1.5)
  points(x, y, pch = 16, cex = cex, col = dir_cols)
  if (isTRUE(show_facet_labels) && "facet_id" %in% names(df)) {
    text(x, y, labels = as.character(df$facet_id), pos = 4, offset = 0.20, cex = 0.42, col = "black")
  }
  key <- normal_axis_direction_key()
  legend("topright", legend = key$labels, pch = 16, col = key$cols, title = "Normal direction", cex = 0.78, bty = "n")
  detail <- if (isTRUE(show_normals)) sprintf("Normal length: %.4g x facet size", normal_length_facet_size_factor) else "Normal vectors hidden"
  mtext(sprintf("RGB = scaled original (nx, ny, nz); only the view is rotated face-on. %s", detail), side = 3, line = 0.35, cex = 0.72)
  invisible(out_png)
}

plot_labelled_metric_png <- function(df, out_png, cv_id, eye, value_col, value_label = value_col, show_facet_labels = FALSE) {
  required <- c("x", "y", "z", "norm.x", "norm.y", "norm.z", value_col)
  if (isTRUE(show_facet_labels)) required <- c("facet_id", required)
  need_cols(df, required, "Optic-parameter table")
  fo <- face_on_xy(df)
  x <- fo$xy[, 1]; y <- fo$xy[, 2]
  vals <- suppressWarnings(as.numeric(df[[value_col]]))
  mapped <- map_colors(vals)
  facet_labels <- if ("facet_id" %in% names(df)) as.character(df$facet_id) else rep("", nrow(df))
  size_vals <- if ("facet_size_smoothed" %in% names(df)) df$facet_size_smoothed else rep(NA_real_, length(x))
  cex <- point_cex_from_size(size_vals)
  pad_x <- max(diff(range(x, na.rm = TRUE)) * 0.10, 1e-6)
  pad_y <- max(diff(range(y, na.rm = TRUE)) * 0.10, 1e-6)
  dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)
  png(out_png, width = 2200, height = 1800, res = 220)
  op <- par(mar = c(4, 4, 4, 6))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot(x, y, type = "n", asp = 1, xlab = "Face-on x (um)", ylab = "Face-on y (um)",
       main = sprintf("%s - standard CV3D face-on view", value_label),
       xlim = range(x, na.rm = TRUE) + c(-pad_x, pad_x),
       ylim = range(y, na.rm = TRUE) + c(-pad_y, pad_y))
  points(x, y, pch = 16, cex = cex, col = mapped$cols)
  if (isTRUE(show_facet_labels)) text(x, y, labels = facet_labels, pos = 4, offset = 0.20, cex = 0.42, col = "black")
  colorbar_inset(vals, mapped$pal, value_label)
  mtext(sprintf("%s %s - 05A labelled metric (%s)", cv_id, eye, value_col), outer = FALSE, line = 1.2, cex = 1.05, font = 2)
  invisible(out_png)
}

wait_for_rgl_close <- function() {
  # Deliberately identical to the last known-working 05A normals runner.
  repeat {
    devs <- tryCatch(rgl::rgl.dev.list(), error = function(e) integer(0))
    if (length(devs) == 0) break
    Sys.sleep(0.5)
  }
}


compute_radius <- function(df) {
  if ("facet_size_smoothed" %in% names(df)) {
    vals <- suppressWarnings(as.numeric(df$facet_size_smoothed))
    vals <- vals[is.finite(vals)]
    if (length(vals) > 0) return(max(mean(vals) * 0.30, 0.001))
  }
  spans <- c(diff(range(df$x, na.rm = TRUE)), diff(range(df$y, na.rm = TRUE)), diff(range(df$z, na.rm = TRUE)))
  spans <- spans[is.finite(spans)]
  if (length(spans) == 0) return(0.1)
  max(mean(spans) * 0.015, 0.001)
}

compute_facet_radius <- function(df) {
  fallback <- compute_radius(df)
  if (!"facet_size_smoothed" %in% names(df)) return(rep(fallback, nrow(df)))
  radius <- suppressWarnings(as.numeric(df$facet_size_smoothed)) / 2
  radius[!is.finite(radius) | radius <= 0] <- fallback
  radius
}

resolve_facet_sphere_radius <- function(df, scale = 0, facet_size_estimate = NA_real_, legacy_radius = NULL) {
  if (is.null(legacy_radius)) legacy_radius <- rep(compute_radius(df), nrow(df))
  if (length(legacy_radius) == 1) legacy_radius <- rep(legacy_radius, nrow(df))
  scale <- suppressWarnings(as.numeric(scale)[1])
  if (!is.finite(scale) || scale < 0) scale <- 0
  if (scale == 0) return(legacy_radius)

  size <- rep(NA_real_, nrow(df))
  if ("facet_size_smoothed" %in% names(df)) {
    size <- suppressWarnings(as.numeric(df$facet_size_smoothed))
  }
  estimate <- suppressWarnings(as.numeric(facet_size_estimate)[1])
  if (!is.finite(estimate) || estimate <= 0) estimate <- NA_real_
  size[!is.finite(size) | size <= 0] <- estimate

  radius <- 0.5 * size * scale
  bad <- !is.finite(radius) | radius <= 0
  radius[bad] <- legacy_radius[bad]
  radius
}

normalize_normals <- function(df) {
  need_cols(df, c("norm.x", "norm.y", "norm.z"), "Facet-normal table")
  n <- cbind(
    suppressWarnings(as.numeric(df$norm.x)),
    suppressWarnings(as.numeric(df$norm.y)),
    suppressWarnings(as.numeric(df$norm.z))
  )
  lens <- sqrt(rowSums(n^2))
  good <- is.finite(lens) & lens > 0
  n[good, ] <- n[good, , drop = FALSE] / lens[good]
  n[!good, ] <- NA_real_
  colnames(n) <- c("norm.x", "norm.y", "norm.z")
  n
}

normal_lengths_from_facet_size <- function(df, factor = 5.0) {
  factor <- suppressWarnings(as.numeric(factor)[1])
  if (!is.finite(factor) || factor < 0) factor <- 5.0
  fallback <- compute_radius(df) * factor * 2
  if (!"facet_size_smoothed" %in% names(df)) return(rep(fallback, nrow(df)))
  len <- suppressWarnings(as.numeric(df$facet_size_smoothed)) * factor
  len[!is.finite(len) | len < 0] <- fallback
  len
}

open_optics_rgl <- function(df, cv_id, eye, facet_sphere_scale = 0, facet_size_estimate = NA_real_) {
  need_cols(df, c("x", "y", "z", "norm.x", "norm.y", "norm.z", "facet_size_smoothed", "interfacet_angle_deg", "eye_parameter", "acuity_cpd"), "Optic-parameter table")
  view <- cv3d_standard_face_on_view(df)
  legacy_radius <- compute_facet_radius(df)
  sphere_radius <- resolve_facet_sphere_radius(df, facet_sphere_scale, facet_size_estimate, legacy_radius)
  metrics <- list(
    list(col = "facet_size_smoothed", title = "Facet size"),
    list(col = "interfacet_angle_deg", title = "IF angle (deg)"),
    list(col = "eye_parameter", title = "Eye parameter"),
    list(col = "acuity_cpd", title = "Acuity (cpd)")
  )
  rgl::open3d(useNULL = FALSE)
  try(rgl::par3d(windowRect = c(80, 80, 1900, 1500)), silent = TRUE)
  if ("mfrow3d" %in% getNamespaceExports("rgl")) rgl::mfrow3d(2, 2, sharedMouse = TRUE)
  for (m in metrics) {
    vals <- suppressWarnings(as.numeric(df[[m$col]]))
    cols <- map_colors(vals)$cols
    rgl::plot3d(df$x, df$y, df$z, type = "n", xlab = "x", ylab = "y", zlab = "z", aspect = "iso", box = TRUE)
    rgl::spheres3d(df$x, df$y, df$z, radius = sphere_radius, col = cols)
    set_cv3d_standard_rgl_view(view)
    rgl::title3d(main = sprintf("%s %s - %s", cv_id, eye, m$title))
  }
  wait_for_rgl_close()
}

open_normals_rgl <- function(df, cv_id, eye, normal_length_facet_size_factor = 5.0, facet_sphere_scale = 0, facet_size_estimate = NA_real_, show_normals = TRUE, show_facet_labels = FALSE) {
  need_cols(df, c("x", "y", "z", "norm.x", "norm.y", "norm.z"), "Facet-normal table")
  view <- cv3d_standard_face_on_view(df)
  legacy_radius <- rep(compute_radius(df), nrow(df))
  radius <- resolve_facet_sphere_radius(df, facet_sphere_scale, facet_size_estimate, legacy_radius)
  nrm <- normalize_normals(df)
  dir_cols <- normal_direction_colors(nrm)
  method_text <- normal_method_label(df)
  normal_length <- normal_lengths_from_facet_size(df, normal_length_facet_size_factor)
  x2 <- df$x + nrm[, 1] * normal_length
  y2 <- df$y + nrm[, 2] * normal_length
  z2 <- df$z + nrm[, 3] * normal_length
  rgl::open3d(windowRect = c(120, 120, 1500, 1200))
  rgl::plot3d(df$x, df$y, df$z, type = "n", xlab = "x", ylab = "y", zlab = "z", aspect = "iso", box = TRUE)
  rgl::spheres3d(df$x, df$y, df$z, radius = radius, col = dir_cols)
  if (isTRUE(show_facet_labels) && "facet_id" %in% names(df)) {
    finite_radius <- radius[is.finite(radius) & radius > 0]
    offset <- if (length(finite_radius) > 0) max(finite_radius) * 1.8 else compute_radius(df) * 1.8
    rgl::texts3d(df$x + view$view_direction[[1]] * offset,
                 df$y + view$view_direction[[2]] * offset,
                 df$z + view$view_direction[[3]] * offset,
                 texts = as.character(df$facet_id), cex = 0.8, color = "black")
  }
  if (isTRUE(show_normals)) {
    idx <- which(is.finite(df$x) & is.finite(df$y) & is.finite(df$z) & is.finite(x2) & is.finite(y2) & is.finite(z2))
    if (length(idx) > 0) {
      rgl::segments3d(x = as.vector(rbind(df$x[idx], x2[idx])),
                      y = as.vector(rbind(df$y[idx], y2[idx])),
                      z = as.vector(rbind(df$z[idx], z2[idx])),
                      col = rep(dir_cols[idx], each = 2), lwd = 2)
    }
  }
  set_cv3d_standard_rgl_view(view)
  title_text <- if (isTRUE(show_normals)) {
    sprintf("%s %s - %s, face-on normals (normal length %.4g x facet size)", cv_id, eye, method_text, normal_length_facet_size_factor)
  } else {
    sprintf("%s %s - %s, face-on normal direction (vectors hidden)", cv_id, eye, method_text)
  }
  rgl::title3d(main = title_text)
  wait_for_rgl_close()
}

open_labelled_metric_rgl <- function(df, cv_id, eye, value_col, value_label = value_col, facet_sphere_scale = 0, facet_size_estimate = NA_real_, show_facet_labels = FALSE) {
  required <- c("x", "y", "z", "norm.x", "norm.y", "norm.z", value_col)
  if (isTRUE(show_facet_labels)) required <- c("facet_id", required)
  need_cols(df, required, "Optic-parameter table")
  view <- cv3d_standard_face_on_view(df)
  legacy_radius <- rep(compute_radius(df), nrow(df))
  radius <- resolve_facet_sphere_radius(df, facet_sphere_scale, facet_size_estimate, legacy_radius)
  vals <- suppressWarnings(as.numeric(df[[value_col]]))
  cols <- map_colors(vals)$cols
  rgl::open3d(useNULL = FALSE)
  try(rgl::par3d(windowRect = c(80, 80, 1800, 1400)), silent = TRUE)
  rgl::plot3d(df$x, df$y, df$z, type = "n", xlab = "x", ylab = "y", zlab = "z", aspect = "iso", box = TRUE)
  rgl::spheres3d(df$x, df$y, df$z, radius = radius, col = cols)
  if (isTRUE(show_facet_labels)) {
    finite_radius <- radius[is.finite(radius) & radius > 0]
    offset <- if (length(finite_radius) > 0) max(finite_radius) * 1.8 else compute_radius(df) * 1.8
    rgl::texts3d(df$x + view$view_direction[[1]] * offset,
                 df$y + view$view_direction[[2]] * offset,
                 df$z + view$view_direction[[3]] * offset,
                 texts = as.character(df$facet_id), cex = 0.8, color = "black")
  }
  set_cv3d_standard_rgl_view(view)
  rgl::title3d(main = sprintf("%s %s - %s [%s], standard face-on", cv_id, eye, value_label, value_col))
  wait_for_rgl_close()
}

main <- function() {
  plot_kind <- tolower(task$plot_kind %||% "")
  cv_id <- task$cv_id %||% "CVXXXX"
  eye <- task$eye %||% "eye?"
  out_png <- task$output_plot_png_abs
  if (is.null(out_png) || !nzchar(out_png)) stop("Task JSON is missing output_plot_png_abs.", call. = FALSE)

  optics_path <- normalizePath(task$input_optic_parameters_abs, winslash = "/", mustWork = TRUE)
  optics_df <- read_csv_safe(optics_path)
  facet_sphere_scale <- suppressWarnings(as.numeric(task$facet_sphere_scale %||% task$parameters$facet_sphere_scale %||% 0)[1])
  if (!is.finite(facet_sphere_scale) || facet_sphere_scale < 0) facet_sphere_scale <- 0
  facet_size_estimate <- suppressWarnings(as.numeric(task$facet_size_estimate %||% task$parameters$facet_size_estimate %||% NA_real_)[1])
  if (!is.finite(facet_size_estimate) || facet_size_estimate <= 0) facet_size_estimate <- NA_real_
  show_facet_labels <- isTRUE(task$show_facet_labels %||% FALSE)

  if (plot_kind == "optics") {
    plot_optics_png(optics_df, out_png, cv_id, eye)
    rgl_status <- "not_requested"
    if (isTRUE(task$open_rgl_window %||% FALSE)) {
      rgl_status <- tryCatch({
        open_optics_rgl(optics_df, cv_id, eye, facet_sphere_scale, facet_size_estimate)
        "opened_and_closed"
      }, error = function(e) {
        paste0("failed: ", conditionMessage(e))
      })
    }
  } else if (plot_kind == "normals") {
    normals_path <- normalizePath(task$input_facet_normals_abs, winslash = "/", mustWork = TRUE)
    normals_df <- read_csv_safe(normals_path)
    if (!"facet_size_smoothed" %in% names(normals_df) && "facet_size_smoothed" %in% names(optics_df) && "facet_id" %in% names(normals_df) && "facet_id" %in% names(optics_df)) {
      normals_df <- normals_df %>% dplyr::left_join(optics_df %>% dplyr::select(dplyr::any_of(c("facet_id", "facet_size_smoothed"))), by = "facet_id")
    }
    normal_length_facet_size_factor <- suppressWarnings(as.numeric(
      task$normal_length_facet_size_factor %||% task$parameters$normal_length_facet_size_factor %||% 5.0
    )[1])
    if (!is.finite(normal_length_facet_size_factor) || normal_length_facet_size_factor < 0) normal_length_facet_size_factor <- 5.0
    show_normals <- isTRUE(task$show_normals %||% TRUE)
    plot_normals_png(normals_df, out_png, cv_id, eye, normal_length_facet_size_factor, show_normals, show_facet_labels)
    rgl_status <- "not_requested"
    if (isTRUE(task$open_rgl_window %||% FALSE)) {
      # Do not swallow native-rgl errors here. If anything fails after the
      # window is created, propagate it so the UI/status/log shows the actual
      # failing operation instead of silently closing the window.
      open_normals_rgl(normals_df, cv_id, eye, normal_length_facet_size_factor, facet_sphere_scale, facet_size_estimate, show_normals, show_facet_labels)
      rgl_status <- "opened_and_closed"
    }
  } else if (plot_kind == "labelled_metric") {
    metric_col <- as.character(task$selected_metric_col %||% "")
    metric_label <- as.character(task$selected_metric_label %||% metric_col)
    if (!nzchar(metric_col)) stop("Task JSON is missing selected_metric_col for plot_kind labelled_metric.", call. = FALSE)
    plot_labelled_metric_png(optics_df, out_png, cv_id, eye, metric_col, metric_label, show_facet_labels)
    rgl_status <- "not_requested"
    if (isTRUE(task$open_rgl_window %||% FALSE)) {
      rgl_status <- tryCatch({
        open_labelled_metric_rgl(optics_df, cv_id, eye, metric_col, metric_label, facet_sphere_scale, facet_size_estimate, show_facet_labels)
        "opened_and_closed"
      }, error = function(e) {
        paste0("failed: ", conditionMessage(e))
      })
    }
  } else if (plot_kind == "facet_value_report") {
    metric_cols <- as.character(unlist(task$selected_metric_cols %||% character(0), use.names = FALSE))
    metric_labels <- as.character(unlist(task$selected_metric_labels %||% metric_cols, use.names = FALSE))
    out_pngs <- as.character(unlist(task$output_plot_pngs_abs %||% character(0), use.names = FALSE))
    if (length(metric_cols) < 1L) stop("Task JSON is missing selected_metric_cols for plot_kind facet_value_report.", call. = FALSE)
    if (length(metric_labels) != length(metric_cols)) stop("selected_metric_labels must match selected_metric_cols.", call. = FALSE)
    if (length(out_pngs) != length(metric_cols)) stop("output_plot_pngs_abs must match selected_metric_cols.", call. = FALSE)
    for (ii in seq_along(metric_cols)) {
      plot_labelled_metric_png(
        optics_df, out_pngs[[ii]], cv_id, eye,
        metric_cols[[ii]], metric_labels[[ii]], FALSE
      )
    }
    normals_out <- as.character(task$report_normals_output_png_abs %||% "")
    if (nzchar(normals_out)) {
      normals_path <- normalizePath(task$input_facet_normals_abs, winslash = "/", mustWork = TRUE)
      normals_df <- read_csv_safe(normals_path)
      if (!"facet_size_smoothed" %in% names(normals_df) && "facet_size_smoothed" %in% names(optics_df) && "facet_id" %in% names(normals_df) && "facet_id" %in% names(optics_df)) {
        normals_df <- normals_df %>% dplyr::left_join(optics_df %>% dplyr::select(dplyr::any_of(c("facet_id", "facet_size_smoothed"))), by = "facet_id")
      }
      plot_normals_png(normals_df, normals_out, cv_id, eye, 5.0, TRUE, FALSE)
    }
    rgl_status <- "not_requested"
  } else {
    stop("Unknown plot_kind in task JSON: ", plot_kind, call. = FALSE)
  }

  if (startsWith(rgl_status, "failed:")) {
    warning("Optional rgl view failed after PNG creation: ", rgl_status)
  }

  write_status("success", sprintf("05A %s plot created successfully.", plot_kind), list(
    summary = list(
      cv_id = cv_id,
      eye = eye,
      plot_kind = plot_kind,
      output_plot_png = task$output_plot_png,
      output_plot_png_abs = out_png,
      open_rgl_window = isTRUE(task$open_rgl_window %||% FALSE),
      rgl_status = rgl_status,
      facet_sphere_scale = facet_sphere_scale,
      facet_size_estimate = facet_size_estimate,
      normal_length_facet_size_factor = if (exists("normal_length_facet_size_factor")) normal_length_facet_size_factor else NULL,
      show_normals = if (exists("show_normals")) show_normals else NULL,
      show_facet_labels = show_facet_labels
    )
  ))
}

tryCatch(main(), error = function(e) {
  msg <- conditionMessage(e)
  message("CV3D 05A QC plot failed: ", msg)
  write_status("failed", msg, list(traceback = paste(utils::capture.output(traceback()), collapse = "\n")))
  quit(status = 1, save = "no")
})
