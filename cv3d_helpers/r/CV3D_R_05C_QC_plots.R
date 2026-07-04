#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript CV3D_R_05C_QC_plots.R <task_json>", call. = FALSE)

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

SCRIPT_VERSION <- "0.1.2-combined-two-eye-qc"
SCRIPT_NAME <- "CV3D_R_05C_QC_plots.R"

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
    input_corneal_projections_abs = task$input_corneal_projections_abs %||% ""
  ))
}

read_combined_projection_df <- function(entries, default_eye) {
  out <- list()
  for (i in seq_along(entries)) {
    entry <- entries[[i]]
    eye_i <- entry$eye %||% default_eye
    global_path <- entry$input_global_coordinates_abs %||% ""
    projection_path <- entry$input_corneal_projections_abs %||% ""
    if (!nzchar(global_path) || !file.exists(global_path) || !nzchar(projection_path) || !file.exists(projection_path)) next
    global <- read_csv_safe(normalizePath(global_path, winslash = "/", mustWork = TRUE))
    projection <- read_csv_safe(normalizePath(projection_path, winslash = "/", mustWork = TRUE))
    need_cols(global, c("facet_id", "x_global", "y_global", "z_global", "norm.x_global", "norm.y_global", "norm.z_global"), "05B global-coordinate table")
    need_cols(projection, c("facet_id", "corn.proj.x", "corn.proj.y", "corn.proj.z", "latitude", "longitude"), "05C projection table")
    df_i <- dplyr::left_join(
      projection,
      global %>% dplyr::select(dplyr::any_of(c("facet_id", "x_global", "y_global", "z_global", "norm.x_global", "norm.y_global", "norm.z_global", "size"))),
      by = "facet_id",
      suffix = c("", ".global_input")
    )
    for (nm in c("x_global", "y_global", "z_global", "norm.x_global", "norm.y_global", "norm.z_global")) {
      alt <- paste0(nm, ".global_input")
      if (alt %in% names(df_i)) {
        if (!nm %in% names(df_i)) df_i[[nm]] <- df_i[[alt]]
        missing_main <- !is.finite(suppressWarnings(as.numeric(df_i[[nm]])))
        df_i[[nm]][missing_main] <- df_i[[alt]][missing_main]
      }
    }
    df_i$source_eye <- eye_i
    out[[length(out) + 1]] <- df_i
  }
  if (length(out) == 0) stop("No readable 05B/05C input files were provided for 05C QC plotting.", call. = FALSE)
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

point_cex_from_size <- function(size, base = 0.65) {
  size <- suppressWarnings(as.numeric(size))
  good <- is.finite(size) & size > 0
  cex <- rep(base, length(size))
  if (!any(good)) return(cex)
  scaled <- rescale01(size)
  cex[good] <- 0.45 + 0.85 * scaled[good]
  cex
}

facet_size_values <- function(df, n = nrow(df)) {
  if ("size" %in% names(df)) {
    vals <- suppressWarnings(as.numeric(df$size))
    if (length(vals) == n && any(is.finite(vals))) return(vals)
  }
  seq_len(n)
}

facet_color_map <- function(df) {
  vals <- facet_size_values(df)
  mapped <- map_colors(vals)
  mapped$values <- vals
  mapped$label <- if ("size" %in% names(df) && any(is.finite(suppressWarnings(as.numeric(df$size))))) "Facet size" else "Facet index"
  mapped
}

make_projection_png <- function(df, view_name, path, cv_id, eye) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)

  view_defs <- list(
    front = list(px = "corn.proj.x", py = "corn.proj.z", fx = "x_global", fy = "z_global", sx = 1,  sy = 1,  xlab = "x (um)",  ylab = "z (um)"),
    back  = list(px = "corn.proj.x", py = "corn.proj.z", fx = "x_global", fy = "z_global", sx = -1, sy = 1,  xlab = "-x (um)", ylab = "z (um)"),
    left  = list(px = "corn.proj.y", py = "corn.proj.z", fx = "y_global", fy = "z_global", sx = 1,  sy = 1,  xlab = "y (um)",  ylab = "z (um)"),
    right = list(px = "corn.proj.y", py = "corn.proj.z", fx = "y_global", fy = "z_global", sx = -1, sy = 1,  xlab = "-y (um)", ylab = "z (um)"),
    top   = list(px = "corn.proj.x", py = "corn.proj.y", fx = "x_global", fy = "y_global", sx = 1,  sy = 1,  xlab = "x (um)",  ylab = "y (um)"),
    bottom = list(px = "corn.proj.x", py = "corn.proj.y", fx = "x_global", fy = "y_global", sx = 1, sy = -1, xlab = "x (um)",  ylab = "-y (um)")
  )
  vd <- view_defs[[view_name]] %||% view_defs$top

  px <- suppressWarnings(as.numeric(df[[vd$px]])) * vd$sx
  py <- suppressWarnings(as.numeric(df[[vd$py]])) * vd$sy
  fx <- suppressWarnings(as.numeric(df[[vd$fx]])) * vd$sx
  fy <- suppressWarnings(as.numeric(df[[vd$fy]])) * vd$sy
  cmap <- facet_color_map(df)
  colour_value <- cmap$values
  mapped <- cmap
  cex <- if ("size" %in% names(df)) point_cex_from_size(df$size) else rep(0.65, length(px))
  facet_shape <- ifelse(as.character(df$source_eye) == "eye2", 17, 16)

  all_x <- c(px, fx)
  all_y <- c(py, fy)
  png(path, width = 1800, height = 1600, res = 220)
  op <- par(mar = c(4, 4, 4, 6))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot(
    all_x, all_y,
    type = "n",
    asp = 1,
    xlab = vd$xlab,
    ylab = vd$ylab,
    main = sprintf("%s %s - 05C corneal projection QC: %s", cv_id, eye, view_name),
    xlim = plot_range(all_x),
    ylim = plot_range(all_y)
  )
  grid(col = "grey88", lty = "dotted")
  points(fx, fy, pch = facet_shape, cex = pmax(cex * 0.55, 0.25), col = mapped$cols)
  points(px, py, pch = facet_shape, cex = cex, col = mapped$cols)
  legend("topright", legend = c("eye1 facets/projections", "eye2 facets/projections"), pch = c(16, 17), pt.cex = c(1.0, 1.0), col = c("grey35", "grey35"), bty = "n")
  colorbar_inset(colour_value, mapped$pal, mapped$label)
  invisible(path)
}

make_latlon_png <- function(df, path, cv_id, eye) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  x <- suppressWarnings(as.numeric(df$longitude))
  y <- suppressWarnings(as.numeric(df$latitude))
  cmap <- facet_color_map(df)
  colour_value <- cmap$values
  mapped <- cmap
  cex <- if ("size" %in% names(df)) point_cex_from_size(df$size) else rep(0.65, length(x))

  png(path, width = 1800, height = 1200, res = 220)
  op <- par(mar = c(4, 4, 4, 6))
  on.exit({par(op); dev.off()}, add = TRUE)
  plot(
    x, y,
    pch = ifelse(as.character(df$source_eye) == "eye2", 17, 16),
    cex = cex,
    col = mapped$cols,
    xlab = "longitude (deg)",
    ylab = "latitude (deg)",
    main = sprintf("%s %s - 05C corneal projection latitude/longitude", cv_id, eye),
    xlim = plot_range(x),
    ylim = plot_range(y)
  )
  grid(col = "grey88", lty = "dotted")
  points(x, y, pch = 16, cex = cex, col = mapped$cols)
  colorbar_inset(colour_value, mapped$pal, mapped$label)
  invisible(path)
}

normalize_vectors <- function(x, y, z) {
  m <- cbind(as.numeric(x), as.numeric(y), as.numeric(z))
  lens <- sqrt(rowSums(m^2))
  good <- is.finite(lens) & lens > 0
  m[good, ] <- m[good, , drop = FALSE] / lens[good]
  m[!good, ] <- NA_real_
  m
}

rgl_add_sphere_wireframe <- function(center, radius, n_lat = 9, n_lon = 18, col = "skyblue") {
  theta <- seq(0, 2 * pi, length.out = 181)
  latitudes <- seq(-pi / 2, pi / 2, length.out = n_lat)
  for (lat in latitudes) {
    rr <- radius * cos(lat)
    z <- center[3] + radius * sin(lat)
    x <- center[1] + rr * cos(theta)
    y <- center[2] + rr * sin(theta)
    rgl::lines3d(x, y, rep(z, length(theta)), col = col, alpha = 0.45)
  }
  phis <- seq(0, 2 * pi, length.out = n_lon + 1)[-(n_lon + 1)]
  vertical <- seq(-pi / 2, pi / 2, length.out = 181)
  for (phi in phis) {
    x <- center[1] + radius * cos(vertical) * cos(phi)
    y <- center[2] + radius * cos(vertical) * sin(phi)
    z <- center[3] + radius * sin(vertical)
    rgl::lines3d(x, y, z, col = col, alpha = 0.35)
  }
}

wait_for_rgl_close <- function() {
  repeat {
    devs <- tryCatch(rgl::rgl.dev.list(), error = function(e) integer(0))
    if (length(devs) == 0) break
    Sys.sleep(0.5)
  }
}

snapshot_rgl <- function(path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  ok <- FALSE
  msg <- ""
  tryCatch({
    rgl::snapshot3d(filename = path, top = TRUE)
    ok <<- file.exists(path)
  }, error = function(e) {
    msg <<- conditionMessage(e)
  })
  if (!ok) {
    tryCatch({
      rgl::rgl.snapshot(filename = path)
      ok <<- file.exists(path)
    }, error = function(e) {
      msg <<- paste(msg, conditionMessage(e), sep = "; ")
    })
  }
  if (!ok) stop("Could not save rgl snapshot: ", msg, call. = FALSE)
  invisible(path)
}

render_rgl_scene <- function(df, path, cv_id, eye, keep_open = FALSE, make_snapshot = FALSE) {
  need_cols(df, c("x_global", "y_global", "z_global", "norm.x_global", "norm.y_global", "norm.z_global", "corn.proj.x", "corn.proj.y", "corn.proj.z", "projection_sphere_center_x", "projection_sphere_center_y", "projection_sphere_center_z", "projection_sphere_radius_um"), "05C projection table")

  facets <- cbind(df$x_global, df$y_global, df$z_global)
  projections <- cbind(df$corn.proj.x, df$corn.proj.y, df$corn.proj.z)
  normals <- normalize_vectors(df$norm.x_global, df$norm.y_global, df$norm.z_global)
  sphere_df <- df %>%
    dplyr::select(dplyr::any_of(c("source_eye", "projection_sphere_center_x", "projection_sphere_center_y", "projection_sphere_center_z", "projection_sphere_radius_um"))) %>%
    dplyr::distinct()
  if (nrow(sphere_df) == 0) stop("Projection sphere center/radius is missing or invalid in 05C output.", call. = FALSE)
  sphere_df$projection_sphere_radius_um <- suppressWarnings(as.numeric(sphere_df$projection_sphere_radius_um))
  sphere_df <- sphere_df %>% dplyr::filter(is.finite(projection_sphere_center_x), is.finite(projection_sphere_center_y), is.finite(projection_sphere_center_z), is.finite(projection_sphere_radius_um), projection_sphere_radius_um > 0)
  if (nrow(sphere_df) == 0) stop("Projection sphere center/radius is missing or invalid in 05C output.", call. = FALSE)
  center <- c(sphere_df$projection_sphere_center_x[1], sphere_df$projection_sphere_center_y[1], sphere_df$projection_sphere_center_z[1])
  radius <- as.numeric(sphere_df$projection_sphere_radius_um[1])

  all_xyz <- rbind(facets, projections, as.matrix(sphere_df[, c("projection_sphere_center_x", "projection_sphere_center_y", "projection_sphere_center_z")]))
  finite_rows <- stats::complete.cases(all_xyz)
  if (!any(finite_rows)) stop("No finite coordinates available for 05C QC plot.", call. = FALSE)

  facet_projection_distance <- sqrt(rowSums((projections - facets)^2))
  normal_length <- 0.5 * facet_projection_distance
  normal_length[!is.finite(normal_length) | normal_length <= 0] <- radius * 0.03

  cmap <- facet_color_map(df)
  projection_cols <- cmap$cols

  rgl::open3d(windowRect = c(80, 80, 1800, 1400))
  on.exit({if (!keep_open) try(rgl::close3d(), silent = TRUE)}, add = TRUE)
  rgl::bg3d(color = "white")

  rgl::plot3d(all_xyz[finite_rows, 1], all_xyz[finite_rows, 2], all_xyz[finite_rows, 3],
              type = "n", xlab = "x_global", ylab = "y_global", zlab = "z_global",
              aspect = "iso", box = TRUE)
  for (ii in seq_len(nrow(sphere_df))) {
    center_i <- c(sphere_df$projection_sphere_center_x[ii], sphere_df$projection_sphere_center_y[ii], sphere_df$projection_sphere_center_z[ii])
    radius_i <- as.numeric(sphere_df$projection_sphere_radius_um[ii])
    rgl_add_sphere_wireframe(center_i, radius_i)
  }

  good_facets <- stats::complete.cases(facets)
  rgl::points3d(facets[good_facets, 1], facets[good_facets, 2], facets[good_facets, 3], size = 4, col = projection_cols[good_facets])

  good_proj <- stats::complete.cases(projections)
  rgl::points3d(projections[good_proj, 1], projections[good_proj, 2], projections[good_proj, 3], size = 6, col = projection_cols[good_proj])

  good_normals <- good_facets & stats::complete.cases(normals) & is.finite(normal_length)
  if (any(good_normals)) {
    idx <- which(good_normals)
    p0 <- facets[idx, , drop = FALSE]
    p1 <- p0 + normals[idx, , drop = FALSE] * normal_length[idx]
    rgl::segments3d(
      x = as.vector(t(cbind(p0[, 1], p1[, 1]))),
      y = as.vector(t(cbind(p0[, 2], p1[, 2]))),
      z = as.vector(t(cbind(p0[, 3], p1[, 3]))),
      col = rep(projection_cols[idx], each = 2),
      alpha = 0.75,
      lwd = 1.5
    )
  }

  for (ii in seq_len(nrow(sphere_df))) {
    center_i <- c(sphere_df$projection_sphere_center_x[ii], sphere_df$projection_sphere_center_y[ii], sphere_df$projection_sphere_center_z[ii])
    rgl::points3d(center_i[1], center_i[2], center_i[3], size = 8, col = "blue")
  }
  rgl::title3d(main = sprintf("%s %s - 05C corneal projection QC", cv_id, eye))
  rgl::view3d(theta = 35, phi = 20, zoom = 0.78)
  snapshot_status <- "not_requested"
  if (isTRUE(make_snapshot) && !is.null(path) && nzchar(path)) {
    snapshot_status <- tryCatch({
      snapshot_rgl(path)
      "created"
    }, error = function(e) {
      paste0("failed: ", conditionMessage(e))
    })
  }
  if (keep_open) wait_for_rgl_close()
  snapshot_status
}

main <- function() {
  cv_id <- task$cv_id %||% "CVXXXX"
  eye <- task$eye %||% "eye?"
  entries <- get_input_eyes(task)
  df <- read_combined_projection_df(entries, eye)

  output_pngs <- task$output_plot_pngs_abs
  if (is.null(output_pngs) || length(output_pngs) == 0) stop("Task JSON is missing output_plot_pngs_abs.", call. = FALSE)

  created <- list()
  plot_eye_label <- paste(unique(df$source_eye), collapse = "+")
  for (axis in c("front", "back", "left", "right", "top", "bottom")) {
    path <- output_pngs[[axis]] %||% ""
    if (nzchar(path)) {
      make_projection_png(df, axis, path, cv_id, plot_eye_label)
      created[[axis]] <- path
    }
  }

  latlon_path <- output_pngs[["latlon"]] %||% ""
  if (nzchar(latlon_path)) {
    make_latlon_png(df, latlon_path, cv_id, plot_eye_label)
    created[["latlon"]] <- latlon_path
  }

  rgl_path <- output_pngs[["rgl_3d"]] %||% task$output_plot_png_abs %||% ""
  open_rgl <- isTRUE(task$open_rgl_window %||% FALSE)
  make_rgl_snapshot <- isTRUE(task$make_rgl_snapshot %||% FALSE)
  rgl_status <- "not_requested"
  if (open_rgl || make_rgl_snapshot) {
    rgl_status <- tryCatch({
      snapshot_status <- render_rgl_scene(df, rgl_path, cv_id, plot_eye_label, keep_open = open_rgl, make_snapshot = make_rgl_snapshot)
      if (nzchar(rgl_path) && file.exists(rgl_path)) created[["rgl_3d"]] <- rgl_path
      if (open_rgl) {
        paste0("opened_and_closed; snapshot_", snapshot_status)
      } else {
        paste0("snapshot_", snapshot_status)
      }
    }, error = function(e) {
      paste0("failed: ", conditionMessage(e))
    })
  }

  rgl_warning <- if (startsWith(rgl_status, "failed:") || grepl("snapshot_failed", rgl_status, fixed = TRUE)) rgl_status else ""

  write_status("success", "05C corneal-projection QC plot(s) created successfully.", list(summary = list(
    cv_id = cv_id,
    eye = eye,
    eyes_used = unique(df$source_eye),
    created_pngs = created,
    open_rgl_window = open_rgl,
    make_rgl_snapshot = make_rgl_snapshot,
    rgl_status = rgl_status,
    rgl_warning = rgl_warning,
    colour_metric = if ("size" %in% names(df)) "facet size" else "facet index",
    normal_length = "0.5 * distance from facet point to corneal-projection point"
  )))
}

tryCatch(main(), error = function(e) {
  msg <- conditionMessage(e)
  message("CV3D 05C QC plot failed: ", msg)
  write_status("failed", msg, list(traceback = paste(utils::capture.output(traceback()), collapse = "\n")))
  quit(status = 1, save = "no")
})
