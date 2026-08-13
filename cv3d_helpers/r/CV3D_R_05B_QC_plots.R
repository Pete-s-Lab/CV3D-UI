#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript CV3D_R_05B_QC_plots.R <task_json>", call. = FALSE)

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

SCRIPT_VERSION <- "0.1.8-lower-side-view-corrected"
SCRIPT_NAME <- "CV3D_R_05B_QC_plots.R"

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
get_input_eyes <- function(task) {
  if (!is.null(task$input_eyes) && length(task$input_eyes) > 0) {
    entries <- task$input_eyes
    if (is.data.frame(entries)) entries <- split(entries, seq_len(nrow(entries)))
    return(entries)
  }
  list(list(
    eye = task$eye %||% "eye?",
    input_global_coordinates_abs = task$input_global_coordinates_abs %||% "",
    input_landmark_referenced_coordinates_abs = task$input_landmark_referenced_coordinates_abs %||% "",
    input_global_aligned_pointcloud_abs = task$input_global_aligned_pointcloud_abs %||% ""
  ))
}

read_combined_pointcloud <- function(entries, which_key, default_eye) {
  out <- list()
  for (i in seq_along(entries)) {
    entry <- entries[[i]]
    eye_i <- entry$eye %||% default_eye
    path_i <- entry[[which_key]] %||% ""
    if (!nzchar(path_i) || !file.exists(path_i)) next
    df_i <- read_csv_safe(normalizePath(path_i, winslash = "/", mustWork = TRUE))
    df_i$source_eye <- eye_i
    out[[length(out) + 1]] <- df_i
  }
  if (length(out) == 0) stop("No readable input point-cloud files were provided for 05B QC plotting.", call. = FALSE)
  dplyr::bind_rows(out)
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

choose_projection <- function(df, suffix) {
  candidates <- list(
    xy = paste0(c("x", "y"), suffix),
    xz = paste0(c("x", "z"), suffix),
    yz = paste0(c("y", "z"), suffix)
  )
  best_name <- "xy"
  best_score <- -Inf
  for (nm in names(candidates)) {
    cols <- candidates[[nm]]
    if (!all(cols %in% names(df))) next
    xr <- diff(range(df[[cols[[1]]]], na.rm = TRUE))
    yr <- diff(range(df[[cols[[2]]]], na.rm = TRUE))
    score <- xr * yr
    if (!is.finite(score)) score <- -Inf
    if (score > best_score) {
      best_score <- score
      best_name <- nm
    }
  }
  candidates[[best_name]]
}

split_pointcloud <- function(df, coord_suffix, label) {
  need_cols(df, c("point_type", paste0(c("x", "y", "z"), coord_suffix)), label)
  facets <- df %>% dplyr::filter(point_type == "facet")
  landmarks <- df %>% dplyr::filter(point_type == "LM")
  if (!"source_eye" %in% names(facets)) facets$source_eye <- label
  if (!"source_eye" %in% names(landmarks)) landmarks$source_eye <- label
  if (!"landmark" %in% names(landmarks)) landmarks$landmark <- landmarks$point_id
  if (nrow(landmarks) > 0) {
    dedupe_cols <- intersect(c("landmark", paste0(c("x", "y", "z"), coord_suffix)), names(landmarks))
    landmarks <- dplyr::distinct(landmarks, dplyr::across(dplyr::all_of(dedupe_cols)), .keep_all = TRUE)
  }
  if (nrow(facets) == 0) stop(label, " contains no facet rows.", call. = FALSE)
  if (nrow(landmarks) == 0) stop(label, " contains no landmark rows.", call. = FALSE)
  list(facets = facets, landmarks = landmarks)
}

plot_pointcloud_png <- function(pointcloud, out_png, cv_id, eye, coord_suffix, stage_label) {
  pcs <- split_pointcloud(pointcloud, coord_suffix, stage_label)
  facets <- pcs$facets
  landmarks <- pcs$landmarks
  cols_xyz <- paste0(c("x", "y", "z"), coord_suffix)
  need_cols(facets, c(cols_xyz, "facet_size_smoothed"), paste(stage_label, "facets"))
  need_cols(landmarks, c("landmark", cols_xyz), paste(stage_label, "landmarks"))

  proj_cols <- choose_projection(pointcloud, coord_suffix)
  vals <- suppressWarnings(as.numeric(facets$facet_size_smoothed))
  mapped <- map_colors(vals)
  cex <- point_cex_from_size(vals)
  lm_cex_val <- max(mean(cex[is.finite(cex)], na.rm = TRUE) * 1.6, 1.6)
  facet_shape <- ifelse(as.character(facets$source_eye) == "eye2", 17, 16)

  x <- suppressWarnings(as.numeric(facets[[proj_cols[[1]]]]))
  y <- suppressWarnings(as.numeric(facets[[proj_cols[[2]]]]))
  lx <- suppressWarnings(as.numeric(landmarks[[proj_cols[[1]]]]))
  ly <- suppressWarnings(as.numeric(landmarks[[proj_cols[[2]]]]))

  all_x <- c(x, lx)
  all_y <- c(y, ly)
  pad_x <- max(diff(range(all_x, na.rm = TRUE)) * 0.08, 1e-6)
  pad_y <- max(diff(range(all_y, na.rm = TRUE)) * 0.08, 1e-6)

  dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)
  png(out_png, width = 1800, height = 1600, res = 220)
  op <- par(mar = c(4, 4, 4, 6))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot(
    x, y,
    type = "n",
    asp = 1,
    xlab = proj_cols[[1]],
    ylab = proj_cols[[2]],
    main = sprintf("%s %s - %s (%s projection)", cv_id, eye, stage_label, paste(proj_cols, collapse = "/")),
    xlim = range(all_x, na.rm = TRUE) + c(-pad_x, pad_x),
    ylim = range(all_y, na.rm = TRUE) + c(-pad_y, pad_y)
  )
  points(x, y, pch = facet_shape, cex = cex, col = mapped$cols)
  points(lx, ly, pch = 16, cex = lm_cex_val, col = "blue")
  text(lx, ly, labels = as.character(landmarks$landmark), pos = 3, offset = 0.35, cex = 0.78, col = "blue")
  legend("topright", legend = c("eye1 facets", "eye2 facets", "landmarks"), pch = c(16, 17, 16), pt.cex = c(1.1, 1.1, 1.4), col = c("grey50", "grey50", "blue"), bty = "n")
  colorbar_inset(vals, mapped$pal, "Facet size")
  invisible(out_png)
}

compute_facet_radius <- function(size) {
  vals <- suppressWarnings(as.numeric(size)) / 2
  fallback <- 0.1
  good <- is.finite(vals) & vals > 0
  if (any(good)) fallback <- max(mean(vals[good], na.rm = TRUE), 0.001)
  vals[!good] <- fallback
  vals
}

resolve_facet_sphere_radius <- function(size, scale = 0, facet_size_estimate = NA_real_) {
  legacy <- compute_facet_radius(size)
  scale <- suppressWarnings(as.numeric(scale)[1])
  if (!is.finite(scale) || scale < 0) scale <- 0
  if (scale == 0) return(legacy)

  vals <- suppressWarnings(as.numeric(size))
  estimate <- suppressWarnings(as.numeric(facet_size_estimate)[1])
  if (!is.finite(estimate) || estimate <= 0) estimate <- NA_real_
  vals[!is.finite(vals) | vals <= 0] <- estimate
  radius <- 0.5 * vals * scale
  bad <- !is.finite(radius) | radius <= 0
  radius[bad] <- legacy[bad]
  radius
}

compute_landmark_radius <- function(size) {
  vals <- suppressWarnings(as.numeric(size))
  vals <- vals[is.finite(vals) & vals > 0]
  if (length(vals) == 0) return(0.1)
  max(mean(vals, na.rm = TRUE) * 1.5, 0.001)
}

wait_for_rgl_close <- function() {
  repeat {
    devs <- tryCatch(rgl::rgl.dev.list(), error = function(e) integer(0))
    if (length(devs) == 0) break
    Sys.sleep(0.5)
  }
}

set_cv3d_global_rgl_view <- function() {
  # Standard post-05B/05C global-coordinate camera.
  # The camera basis is set explicitly from the desired screen-axis layout:
  # x_global projects diagonally upper-left <-> lower-right,
  # y_global projects diagonally lower-left <-> upper-right,
  # z_global projects upward. Corrected view-direction sign: visually lower the camera relative to the object instead of moving it upward. Dimensions remain iso; FOV keeps normal perspective.
  screen_right <- c(1, 1, 0) / sqrt(2)
  screen_up <- c(-1, 1, 2.41421356)
  screen_up <- screen_up / sqrt(sum(screen_up^2))
  screen_forward <- c(
    screen_right[2] * screen_up[3] - screen_right[3] * screen_up[2],
    screen_right[3] * screen_up[1] - screen_right[1] * screen_up[3],
    screen_right[1] * screen_up[2] - screen_right[2] * screen_up[1]
  )
  screen_forward <- screen_forward / sqrt(sum(screen_forward^2))
  user_matrix <- matrix(c(
    screen_right[1],   screen_right[2],   screen_right[3],   0,
    screen_up[1],      screen_up[2],      screen_up[3],      0,
    screen_forward[1], screen_forward[2], screen_forward[3], 0,
    0,                 0,                 0,                 1
  ), nrow = 4, byrow = TRUE)
  try(rgl::par3d(userMatrix = user_matrix, FOV = 35, zoom = 0.78), silent = TRUE)
}

open_alignment_rgl <- function(pointcloud, cv_id, eye, facet_sphere_scale = 0, facet_size_estimate = NA_real_) {
  pcs <- split_pointcloud(pointcloud, "_global", "05B global aligned point-cloud")
  facets <- pcs$facets
  landmarks <- pcs$landmarks
  vals <- suppressWarnings(as.numeric(facets$facet_size_smoothed))
  cols <- map_colors(vals)$cols
  facet_radius <- resolve_facet_sphere_radius(vals, facet_sphere_scale, facet_size_estimate)
  landmark_radius <- compute_landmark_radius(vals)
  z_offset <- landmark_radius * 2.0

  rgl::open3d(windowRect = c(80, 80, 1800, 1400))
  rgl::bg3d(color = "white")
  rgl::plot3d(facets$x_global, facets$y_global, facets$z_global,
              type = "n",
              xlab = "x_global", ylab = "y_global", zlab = "z_global",
              aspect = "iso",
              box = TRUE)
  rgl::spheres3d(facets$x_global, facets$y_global, facets$z_global,
                 radius = facet_radius,
                 col = cols)
  rgl::spheres3d(landmarks$x_global, landmarks$y_global, landmarks$z_global,
                 radius = landmark_radius,
                 col = "blue")
  rgl::texts3d(landmarks$x_global, landmarks$y_global, landmarks$z_global + z_offset,
               texts = as.character(landmarks$landmark), cex = 0.9, color = "blue")
  rgl::title3d(main = sprintf("%s %s - 05B global alignment QC", cv_id, eye))
  set_cv3d_global_rgl_view()
  wait_for_rgl_close()
}

main <- function() {
  cv_id <- task$cv_id %||% "CVXXXX"
  eye <- task$eye %||% "eye?"
  out_png <- task$output_plot_png_abs
  ref_out_png <- task$output_reference_plot_png_abs %||% ""
  if (is.null(out_png) || !nzchar(out_png)) stop("Task JSON is missing output_plot_png_abs.", call. = FALSE)

  entries <- get_input_eyes(task)
  eyes_used <- vapply(entries, function(x) as.character(x$eye %||% eye), character(1))
  facet_sphere_scale <- suppressWarnings(as.numeric(task$facet_sphere_scale %||% task$parameters$facet_sphere_scale %||% 0)[1])
  if (!is.finite(facet_sphere_scale) || facet_sphere_scale < 0) facet_sphere_scale <- 0
  facet_size_estimate <- suppressWarnings(as.numeric(task$facet_size_estimate %||% task$parameters$facet_size_estimate %||% NA_real_)[1])
  if (!is.finite(facet_size_estimate) || facet_size_estimate <= 0) facet_size_estimate <- NA_real_

  aligned <- read_combined_pointcloud(entries, "input_global_aligned_pointcloud_abs", eye)
  split_pointcloud(aligned, "_global", "05B global aligned point-cloud")

  reference_plot_created <- FALSE
  referenced_ok <- vapply(entries, function(ent) {
    p <- ent$input_landmark_referenced_coordinates_abs %||% ""
    nzchar(p) && file.exists(p)
  }, logical(1))
  if (any(referenced_ok) && nzchar(ref_out_png)) {
    referenced <- read_combined_pointcloud(entries[referenced_ok], "input_landmark_referenced_coordinates_abs", eye)
    plot_pointcloud_png(referenced, ref_out_png, cv_id, paste(unique(eyes_used[referenced_ok]), collapse = "+"), "_reference", "05B landmark-referenced coordinates")
    reference_plot_created <- TRUE
  }

  plot_pointcloud_png(aligned, out_png, cv_id, paste(unique(eyes_used), collapse = "+"), "_global", "05B global alignment QC")

  rgl_status <- "not_requested"
  if (isTRUE(task$open_rgl_window %||% FALSE)) {
    rgl_status <- tryCatch({
      open_alignment_rgl(aligned, cv_id, paste(unique(eyes_used), collapse = "+"), facet_sphere_scale, facet_size_estimate)
      "opened_and_closed"
    }, error = function(e) {
      paste0("failed: ", conditionMessage(e))
    })
  }

  if (startsWith(rgl_status, "failed:")) {
    warning("Optional rgl view failed after PNG creation: ", rgl_status)
  }

  write_status("success", "05B QC plot(s) created successfully.", list(
    summary = list(
      cv_id = cv_id,
      eye = eye,
      eyes_used = unique(eyes_used),
      output_plot_png = task$output_plot_png,
      output_plot_png_abs = out_png,
      output_reference_plot_png = task$output_reference_plot_png %||% NA_character_,
      output_reference_plot_png_abs = ref_out_png,
      reference_plot_created = reference_plot_created,
      open_rgl_window = isTRUE(task$open_rgl_window %||% FALSE),
      rgl_status = rgl_status,
      facet_sphere_scale = facet_sphere_scale,
      facet_size_estimate = facet_size_estimate
    )
  ))
}

tryCatch(main(), error = function(e) {
  msg <- conditionMessage(e)
  message("CV3D 05B QC plot failed: ", msg)
  write_status("failed", msg, list(traceback = paste(utils::capture.output(traceback()), collapse = "\n")))
  quit(status = 1, save = "no")
})
