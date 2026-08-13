#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript CV3D_R_step03B_plot_thresholded_local_heights.R <task_json>", call. = FALSE)
}

task_json <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

safe_require <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) stop("Required R package is not installed: ", pkg, call. = FALSE)
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

safe_require("jsonlite")
safe_require("readr")
safe_require("dplyr")
safe_require("rgl")
safe_require("CV3D")

task <- jsonlite::fromJSON(task_json, simplifyVector = TRUE)
status_file <- task$status_file_abs

write_status <- function(status, message, extra = list()) {
  payload <- c(
    list(
      status = status,
      message = message,
      task_json = task_json,
      script_version = "CV3D_R_step03B_plot_thresholded_local_heights_0.1.1"
    ),
    extra
  )
  dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(payload, status_file, pretty = TRUE, auto_unbox = TRUE, null = "null")
}

fallback_col <- function(x) {
  x <- as.numeric(x)
  finite <- is.finite(x)
  out <- rep("#808080", length(x))
  if (!any(finite)) return(out)
  rng <- range(x[finite], na.rm = TRUE)
  if (!is.finite(rng[1]) || !is.finite(rng[2]) || diff(rng) == 0) return(out)
  scaled <- (x - rng[1]) / diff(rng)
  scaled[!is.finite(scaled)] <- 0.5
  idx <- round(scaled * 999) + 1
  idx <- pmax(1, pmin(1000, idx))
  grDevices::grey.colors(1000, start = 0, end = 1)[idx]
}


set_cv3d_rgl_window_size <- function(scale = 3) {
  width <- 600 * scale
  height <- 450 * scale
  try(rgl::par3d(windowRect = c(40, 40, 40 + width, 40 + height)), silent = TRUE)
}


main <- function() {
  input_csv <- normalizePath(task$input_local_heights_abs, winslash = "/", mustWork = TRUE)
  thresholded_csv <- normalizePath(task$input_local_height_thresholded_abs, winslash = "/", mustWork = TRUE)
  out_png <- task$output_plot_png_abs
  height_column <- task$height_column
  if (identical(height_column, "local_height_log")) height_column <- "local_height_contrast"
  if (identical(height_column, "local_height_log_norm")) height_column <- "local_height_norm_contrast"
  open_rgl <- isTRUE(task$open_rgl_window)

  dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)

  message("Reading local-height source table: ", input_csv)
  df <- suppressMessages(readr::read_csv(input_csv, show_col_types = FALSE))
  message("Reading thresholded local-height point cloud: ", thresholded_csv)
  thr <- suppressMessages(readr::read_csv(thresholded_csv, show_col_types = FALSE))

  required_df_cols <- c("x", "y", "z")
  missing_df <- setdiff(required_df_cols, names(df))
  if (length(missing_df) > 0) stop("Source table is missing required columns: ", paste(missing_df, collapse = ", "), call. = FALSE)

  required_thr_cols <- c("x", "y", "z")
  missing_thr <- setdiff(required_thr_cols, names(thr))
  if (length(missing_thr) > 0) stop("Thresholded table is missing required columns: ", paste(missing_thr, collapse = ", "), call. = FALSE)

  df <- df %>% dplyr::mutate(x = as.numeric(x), y = as.numeric(y), z = as.numeric(z))
  thr <- thr %>% dplyr::mutate(x = as.numeric(x), y = as.numeric(y), z = as.numeric(z))

  # Convert legacy exponentiated height columns to the current 0--1 contrast
  # scales before plotting older datasets. Legacy colour columns are not reused
  # because their mapping was defined on the old 1--10/exponentiated scales.
  if (!"local_height_contrast" %in% names(df)) {
    legacy_name <- if ("local_height_exp10" %in% names(df)) {
      "local_height_exp10"
    } else if ("local_height_log" %in% names(df)) {
      "local_height_log"
    } else {
      NA_character_
    }
    legacy_exp <- if (!is.na(legacy_name)) {
      as.numeric(df[[legacy_name]])
    } else if ("local_height" %in% names(df)) {
      10^as.numeric(df$local_height)
    } else {
      NULL
    }
    if (!is.null(legacy_exp)) {
      finite <- is.finite(legacy_exp)
      contrast <- rep(NA_real_, length(legacy_exp))
      if (any(finite)) {
        bounds <- stats::quantile(legacy_exp[finite], probs = c(0.5, 0.9), na.rm = TRUE, names = FALSE)
        clipped <- pmin(pmax(legacy_exp[finite], bounds[1]), bounds[2])
        contrast[finite] <- if (isTRUE(all.equal(bounds[1], bounds[2]))) {
          0.5
        } else {
          (clipped - bounds[1]) / diff(bounds)
        }
      }
      df$local_height_contrast <- contrast
    }
  }
  if (!"local_height_norm_contrast" %in% names(df)) {
    legacy_name <- if ("local_height_norm_exp10" %in% names(df)) {
      "local_height_norm_exp10"
    } else if ("local_height_log_norm" %in% names(df)) {
      "local_height_log_norm"
    } else {
      NA_character_
    }
    if (!is.na(legacy_name)) {
      df$local_height_norm_contrast <- pmin(pmax((as.numeric(df[[legacy_name]]) - 1) / 9, 0), 1)
    } else if ("local_height_norm" %in% names(df)) {
      df$local_height_norm_contrast <- pmin(pmax((10^as.numeric(df$local_height_norm) - 1) / 9, 0), 1)
    }
  }

  if (height_column %in% names(df)) {
    df$.height_for_col <- as.numeric(df[[height_column]])
  } else {
    df$.height_for_col <- NA_real_
  }

  if (height_column == "local_height_norm_contrast" && "local_height_norm_contrast_col" %in% names(df)) {
    full_col <- df$local_height_norm_contrast_col
  } else if (height_column == "local_height_contrast" && "local_height_contrast_col" %in% names(df)) {
    full_col <- df$local_height_contrast_col
  } else {
    full_col <- fallback_col(df$.height_for_col)
  }

  normal_cols <- c("norm.x", "norm.y", "norm.z")
  have_normals <- all(normal_cols %in% names(df))

  view <- NULL
  if (have_normals) {
    view <- CV3D::view_eye_face_on(
      df,
      projection = "3D",
      col = grDevices::adjustcolor(full_col, alpha.f = 0.35),
      rgl_size = 3,
      axes = TRUE
    )
    set_cv3d_rgl_window_size(scale = 3)
  } else {
    message("Surface normals unavailable; using the legacy unconstrained rgl view.")
    rgl::open3d(useNULL = FALSE)
    set_cv3d_rgl_window_size(scale = 3)
    rgl::plot3d(
      df[, c("x", "y", "z")],
      aspect = "iso",
      col = full_col,
      size = 3,
      alpha = 0.35
    )
  }

  if (nrow(thr) > 0) {
    if (have_normals) {
      # The reference surface is centred for display by view_eye_face_on().
      # Keep thresholded points in their original position relative to that
      # surface rather than centring this subset independently.
      thr_plot <- sweep(
        as.matrix(thr[, c("x", "y", "z")]),
        2,
        view$cloud_centre,
        "-"
      )
      rgl::points3d(
        thr_plot[, 1], thr_plot[, 2], thr_plot[, 3],
        col = "red",
        size = 8
      )
    } else {
      rgl::points3d(
        thr$x, thr$y, thr$z,
        col = "red",
        size = 8
      )
    }
  }

  Sys.sleep(0.5)
  message("Saving PNG snapshot to: ", out_png)
  rgl::rgl.snapshot(filename = out_png, fmt = "png")
  if (!file.exists(out_png)) stop("rgl snapshot did not create the expected PNG: ", out_png, call. = FALSE)

  write_status(
    "success",
    if (open_rgl) "Thresholded local-height 3D plot created. Interactive rgl window is open; close it to finish."
    else "Thresholded local-height 3D plot created successfully.",
    list(
      output_plot_png = out_png,
      input_local_heights = input_csv,
      input_local_height_thresholded = thresholded_csv,
      input_mode = task$input_mode,
      height_column = height_column,
      local_height_threshold = task$local_height_threshold,
      source_point_count = nrow(df),
      thresholded_point_count = nrow(thr),
      open_rgl_window = open_rgl
    )
  )

  if (open_rgl) {
    message("Interactive rgl window requested. Close the rgl window to finish this task.")
    repeat {
      Sys.sleep(0.2)
      cur <- tryCatch(rgl::rgl.cur(), error = function(e) 0)
      if (is.null(cur) || identical(cur, 0L) || identical(cur, 0)) break
    }
  } else {
    try(rgl::close3d(), silent = TRUE)
  }
}

tryCatch(
  main(),
  error = function(e) {
    msg <- conditionMessage(e)
    message("CV3D 03B thresholded local-height 3D plot failed: ", msg)
    write_status("failed", msg)
    quit(status = 1, save = "no")
  }
)
