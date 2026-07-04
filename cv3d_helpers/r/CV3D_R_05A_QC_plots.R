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

SCRIPT_VERSION <- "0.1.4-normal-length-factor-prompt"
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

choose_projection <- function(df) {
  candidates <- list(
    xy = c("x", "y"),
    xz = c("x", "z"),
    yz = c("y", "z")
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

plot_metric_panel <- function(df, proj_cols, value_col, title_text, point_cex, pch = 16) {
  need_cols(df, c(proj_cols, value_col), title_text)
  vals <- suppressWarnings(as.numeric(df[[value_col]]))
  mapped <- map_colors(vals)
  x <- suppressWarnings(as.numeric(df[[proj_cols[[1]]]]))
  y <- suppressWarnings(as.numeric(df[[proj_cols[[2]]]]))
  pad_x <- max(diff(range(x, na.rm = TRUE)) * 0.08, 1e-6)
  pad_y <- max(diff(range(y, na.rm = TRUE)) * 0.08, 1e-6)
  plot(
    x, y,
    asp = 1,
    pch = pch,
    cex = point_cex,
    col = mapped$cols,
    xlab = proj_cols[[1]],
    ylab = proj_cols[[2]],
    main = title_text,
    xlim = range(x, na.rm = TRUE) + c(-pad_x, pad_x),
    ylim = range(y, na.rm = TRUE) + c(-pad_y, pad_y)
  )
  colorbar_inset(vals, mapped$pal, title_text)
}

plot_optics_png <- function(df, out_png, cv_id, eye) {
  need_cols(df, c("x", "y", "z", "size", "delta_phi.deg", "P", "CPD"), "Optic-parameter table")
  proj_cols <- choose_projection(df)
  cex <- point_cex_from_size(df$size)
  dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)
  png(out_png, width = 2200, height = 1800, res = 220)
  op <- par(mfrow = c(2, 2), mar = c(4, 4, 4, 6), oma = c(0, 0, 2, 0))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot_metric_panel(df, proj_cols, "size", "Facet size", cex)
  plot_metric_panel(df, proj_cols, "delta_phi.deg", "IF angle (deg)", cex)
  plot_metric_panel(df, proj_cols, "P", "Eye parameter P", cex)
  plot_metric_panel(df, proj_cols, "CPD", "CPD", cex)
  mtext(sprintf("%s %s - 05A optic parameters (%s projection)", cv_id, eye, paste(proj_cols, collapse = "/")), outer = TRUE, cex = 1.2, font = 2)
  invisible(out_png)
}

plot_normals_png <- function(df, out_png, cv_id, eye, normal_length_facet_size_factor = 5.0) {
  need_cols(df, c("x", "y", "z", "norm.x", "norm.y", "norm.z"), "Facet-normal table")
  proj_cols <- choose_projection(df)
  norm_cols <- switch(
    paste(proj_cols, collapse = "/"),
    "x/y" = c("norm.x", "norm.y"),
    "x/z" = c("norm.x", "norm.z"),
    c("norm.y", "norm.z")
  )
  x <- suppressWarnings(as.numeric(df[[proj_cols[[1]]]]))
  y <- suppressWarnings(as.numeric(df[[proj_cols[[2]]]]))
  nrm <- normalize_normals(df)
  norm_map <- c("norm.x" = 1, "norm.y" = 2, "norm.z" = 3)
  u <- nrm[, norm_map[[norm_cols[[1]]]]]
  v <- nrm[, norm_map[[norm_cols[[2]]]]]
  size <- if ("size" %in% names(df)) suppressWarnings(as.numeric(df$size)) else rep(NA_real_, length(x))
  normal_length <- normal_lengths_from_facet_size(df, normal_length_facet_size_factor)
  cex <- point_cex_from_size(size, base = 1.0)
  x_end <- x + u * normal_length
  y_end <- y + v * normal_length
  pad_x <- max(diff(range(c(x, x_end), na.rm = TRUE)) * 0.08, 1e-6)
  pad_y <- max(diff(range(c(y, y_end), na.rm = TRUE)) * 0.08, 1e-6)

  dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)
  png(out_png, width = 1800, height = 1600, res = 220)
  op <- par(mar = c(4, 4, 4, 4))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot(
    x, y,
    type = "n",
    asp = 1,
    xlab = proj_cols[[1]],
    ylab = proj_cols[[2]],
    main = sprintf("%s %s - 05A facet normals (%s projection)", cv_id, eye, paste(proj_cols, collapse = "/")),
    xlim = range(c(x, x_end), na.rm = TRUE) + c(-pad_x, pad_x),
    ylim = range(c(y, y_end), na.rm = TRUE) + c(-pad_y, pad_y)
  )
  points(x, y, pch = 16, cex = cex, col = "grey70")
  segments(x0 = x, y0 = y, x1 = x_end, y1 = y_end, col = "#D95F02", lwd = 1.4)
  legend("topright", legend = c("facet positions", sprintf("facet normals (%.4g x facet size)", normal_length_facet_size_factor)), pch = c(16, NA), lty = c(NA, 1), col = c("grey50", "#D95F02"), bty = "n")
  mtext(sprintf("Normal length: %.4g x facet size", normal_length_facet_size_factor), side = 3, line = 0.25, cex = 0.78)
  invisible(out_png)
}

plot_labelled_metric_png <- function(df, out_png, cv_id, eye, value_col, value_label = value_col) {
  need_cols(df, c("facet_id", "x", "y", "z", value_col), "Optic-parameter table")
  proj_cols <- choose_projection(df)
  vals <- suppressWarnings(as.numeric(df[[value_col]]))
  mapped <- map_colors(vals)
  x <- suppressWarnings(as.numeric(df[[proj_cols[[1]]]]))
  y <- suppressWarnings(as.numeric(df[[proj_cols[[2]]]]))
  facet_labels <- as.character(df$facet_id)
  size_vals <- if ("size" %in% names(df)) df$size else rep(NA_real_, length(x))
  cex <- point_cex_from_size(size_vals)
  pad_x <- max(diff(range(x, na.rm = TRUE)) * 0.10, 1e-6)
  pad_y <- max(diff(range(y, na.rm = TRUE)) * 0.10, 1e-6)

  dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)
  png(out_png, width = 2200, height = 1800, res = 220)
  op <- par(mar = c(4, 4, 4, 6))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot(
    x, y,
    type = "n",
    asp = 1,
    xlab = proj_cols[[1]],
    ylab = proj_cols[[2]],
    main = sprintf("%s (%s projection)", value_label, paste(proj_cols, collapse = "/")),
    xlim = range(x, na.rm = TRUE) + c(-pad_x, pad_x),
    ylim = range(y, na.rm = TRUE) + c(-pad_y, pad_y)
  )
  points(x, y, pch = 16, cex = cex, col = mapped$cols)
  text(x, y, labels = facet_labels, pos = 4, offset = 0.20, cex = 0.42, col = "black")
  colorbar_inset(vals, mapped$pal, value_label)
  mtext(sprintf("%s %s - 05A labelled metric (%s)", cv_id, eye, value_col), outer = FALSE, line = 1.2, cex = 1.05, font = 2)
  invisible(out_png)
}

wait_for_rgl_close <- function() {
  repeat {
    devs <- tryCatch(rgl::rgl.dev.list(), error = function(e) integer(0))
    if (length(devs) == 0) break
    Sys.sleep(0.5)
  }
}

compute_radius <- function(df) {
  if ("size" %in% names(df)) {
    vals <- suppressWarnings(as.numeric(df$size))
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
  if (!"size" %in% names(df)) return(rep(fallback, nrow(df)))
  radius <- suppressWarnings(as.numeric(df$size)) / 2
  radius[!is.finite(radius) | radius <= 0] <- fallback
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
  if (!"size" %in% names(df)) return(rep(fallback, nrow(df)))
  len <- suppressWarnings(as.numeric(df$size)) * factor
  len[!is.finite(len) | len < 0] <- fallback
  len
}

open_optics_rgl <- function(df, cv_id, eye) {
  need_cols(df, c("x", "y", "z", "size", "delta_phi.deg", "P", "CPD"), "Optic-parameter table")
  sphere_radius <- compute_facet_radius(df)
  metrics <- list(
    list(col = "size", title = "Facet size"),
    list(col = "delta_phi.deg", title = "IF angle (deg)"),
    list(col = "P", title = "Eye parameter P"),
    list(col = "CPD", title = "CPD")
  )
  rgl::open3d(windowRect = c(80, 80, 1900, 1500))
  if ("mfrow3d" %in% getNamespaceExports("rgl")) {
    rgl::mfrow3d(2, 2, sharedMouse = TRUE)
  }
  for (m in metrics) {
    vals <- suppressWarnings(as.numeric(df[[m$col]]))
    cols <- map_colors(vals)$cols
    rgl::plot3d(df$x, df$y, df$z,
                type = "n",
                xlab = "x", ylab = "y", zlab = "z",
                aspect = "iso",
                box = TRUE)
    rgl::spheres3d(df$x, df$y, df$z,
                   radius = sphere_radius,
                   col = cols)
    rgl::title3d(main = sprintf("%s %s - %s", cv_id, eye, m$title))
  }
  wait_for_rgl_close()
}

open_normals_rgl <- function(df, cv_id, eye, normal_length_facet_size_factor = 5.0) {
  need_cols(df, c("x", "y", "z", "norm.x", "norm.y", "norm.z"), "Facet-normal table")
  radius <- compute_radius(df)
  nrm <- normalize_normals(df)
  normal_length <- normal_lengths_from_facet_size(df, normal_length_facet_size_factor)
  x2 <- df$x + nrm[, 1] * normal_length
  y2 <- df$y + nrm[, 2] * normal_length
  z2 <- df$z + nrm[, 3] * normal_length

  rgl::open3d(windowRect = c(120, 120, 1500, 1200))
  rgl::plot3d(df$x, df$y, df$z,
              type = "s",
              radius = radius,
              col = "grey70",
              xlab = "x", ylab = "y", zlab = "z",
              aspect = "iso",
              box = TRUE)
  seg_mat <- cbind(df$x, df$y, df$z, x2, y2, z2)
  rgl::segments3d(x = as.vector(t(seg_mat[, c(1, 4)])),
                  y = as.vector(t(seg_mat[, c(2, 5)])),
                  z = as.vector(t(seg_mat[, c(3, 6)])),
                  col = "#D95F02", lwd = 2)
  rgl::title3d(main = sprintf("%s %s - facet normals (normal length %.4g x facet size)", cv_id, eye, normal_length_facet_size_factor))
  wait_for_rgl_close()
}

open_labelled_metric_rgl <- function(df, cv_id, eye, value_col, value_label = value_col) {
  need_cols(df, c("facet_id", "x", "y", "z", value_col), "Optic-parameter table")
  radius <- compute_radius(df)
  vals <- suppressWarnings(as.numeric(df[[value_col]]))
  cols <- map_colors(vals)$cols
  z_offset <- radius * 1.8
  rgl::open3d(windowRect = c(80, 80, 1800, 1400))
  rgl::plot3d(df$x, df$y, df$z,
              type = "s",
              radius = radius,
              col = cols,
              xlab = "x", ylab = "y", zlab = "z",
              aspect = "iso",
              box = TRUE)
  rgl::texts3d(df$x, df$y, df$z + z_offset, texts = as.character(df$facet_id), cex = 0.8, color = "black")
  rgl::title3d(main = sprintf("%s %s - %s [%s]", cv_id, eye, value_label, value_col))
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

  if (plot_kind == "optics") {
    plot_optics_png(optics_df, out_png, cv_id, eye)
    rgl_status <- "not_requested"
    if (isTRUE(task$open_rgl_window %||% FALSE)) {
      rgl_status <- tryCatch({
        open_optics_rgl(optics_df, cv_id, eye)
        "opened_and_closed"
      }, error = function(e) {
        paste0("failed: ", conditionMessage(e))
      })
    }
  } else if (plot_kind == "normals") {
    normals_path <- normalizePath(task$input_facet_normals_abs, winslash = "/", mustWork = TRUE)
    normals_df <- read_csv_safe(normals_path)
    if (!"size" %in% names(normals_df) && "size" %in% names(optics_df) && "facet_id" %in% names(normals_df) && "facet_id" %in% names(optics_df)) {
      normals_df <- normals_df %>% dplyr::left_join(optics_df %>% dplyr::select(dplyr::any_of(c("facet_id", "size"))), by = "facet_id")
    }
    normal_length_facet_size_factor <- suppressWarnings(as.numeric(
      task$normal_length_facet_size_factor %||% task$parameters$normal_length_facet_size_factor %||% 5.0
    )[1])
    if (!is.finite(normal_length_facet_size_factor) || normal_length_facet_size_factor < 0) normal_length_facet_size_factor <- 5.0
    plot_normals_png(normals_df, out_png, cv_id, eye, normal_length_facet_size_factor)
    rgl_status <- "not_requested"
    if (isTRUE(task$open_rgl_window %||% FALSE)) {
      rgl_status <- tryCatch({
        open_normals_rgl(normals_df, cv_id, eye, normal_length_facet_size_factor)
        "opened_and_closed"
      }, error = function(e) {
        paste0("failed: ", conditionMessage(e))
      })
    }
  } else if (plot_kind == "labelled_metric") {
    metric_col <- as.character(task$selected_metric_col %||% "")
    metric_label <- as.character(task$selected_metric_label %||% metric_col)
    if (!nzchar(metric_col)) stop("Task JSON is missing selected_metric_col for plot_kind labelled_metric.", call. = FALSE)
    plot_labelled_metric_png(optics_df, out_png, cv_id, eye, metric_col, metric_label)
    rgl_status <- "not_requested"
    if (isTRUE(task$open_rgl_window %||% FALSE)) {
      rgl_status <- tryCatch({
        open_labelled_metric_rgl(optics_df, cv_id, eye, metric_col, metric_label)
        "opened_and_closed"
      }, error = function(e) {
        paste0("failed: ", conditionMessage(e))
      })
    }
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
      normal_length_facet_size_factor = if (exists("normal_length_facet_size_factor")) normal_length_facet_size_factor else NULL
    )
  ))
}

tryCatch(main(), error = function(e) {
  msg <- conditionMessage(e)
  message("CV3D 05A QC plot failed: ", msg)
  write_status("failed", msg, list(traceback = paste(utils::capture.output(traceback()), collapse = "\n")))
  quit(status = 1, save = "no")
})
