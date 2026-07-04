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

  if (height_column %in% names(df)) {
    df$.height_for_col <- as.numeric(df[[height_column]])
  } else {
    df$.height_for_col <- NA_real_
  }

  if (height_column == "local_height_log_norm" && "local_height_log_norm_col" %in% names(df)) {
    full_col <- df$local_height_log_norm_col
  } else if (height_column == "local_height_log" && "local_height_log_col" %in% names(df)) {
    full_col <- df$local_height_log_col
  } else {
    full_col <- fallback_col(df$.height_for_col)
  }

  message("Opening rgl device...")
  rgl::open3d(useNULL = FALSE)

  
  set_cv3d_rgl_window_size(scale = 3)
rgl::plot3d(
    df %>% dplyr::select(x, y, z),
    aspect = "iso",
    col = full_col,
    size = 3,
    alpha = 0.35
  )

  if (nrow(thr) > 0) {
    rgl::points3d(
      thr %>% dplyr::select(x, y, z),
      aspect = "iso",
      col = "red",
      size = 8
    )
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
