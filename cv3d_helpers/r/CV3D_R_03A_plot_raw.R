#!/usr/bin/env Rscript

# Usage:
#   Rscript CV3D_R_step03A_plot_raw_local_heights.R <task_json>

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript CV3D_R_step03A_plot_raw_local_heights.R <task_json>", call. = FALSE)
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
safe_require("rgl")

task <- jsonlite::fromJSON(task_json, simplifyVector = TRUE)
status_file <- task$status_file_abs

write_status <- function(status, message, extra = list()) {
  payload <- c(
    list(
      status = status,
      message = message,
      task_json = task_json,
      script_version = "CV3D_R_step03A_plot_raw_local_heights_0.1.2"
    ),
    extra
  )
  if (!is.null(status_file) && !is.na(status_file) && nzchar(status_file)) {
    dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)
    jsonlite::write_json(payload, status_file, pretty = TRUE, auto_unbox = TRUE, null = "null")
  }
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
  out_png <- task$output_plot_png_abs
  open_rgl <- isTRUE(task$open_rgl_window)

  dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)

  message("Reading raw local-height CSV: ", input_csv)
  local_heights <- suppressMessages(readr::read_csv(input_csv, show_col_types = FALSE))

  required_cols <- c("x", "y", "z", "local_height")
  missing_cols <- setdiff(required_cols, names(local_heights))
  if (length(missing_cols) > 0) {
    stop("The raw local-height CSV is missing required columns: ", paste(missing_cols, collapse = ", "), call. = FALSE)
  }
  if (nrow(local_heights) == 0) stop("The raw local-height CSV is empty.", call. = FALSE)

  local_heights <- local_heights %>%
    dplyr::mutate(
      x = as.numeric(x),
      y = as.numeric(y),
      z = as.numeric(z),
      local_height = as.numeric(local_height)
    )

  if (!any(stats::complete.cases(local_heights[, c("x", "y", "z")]))) {
    stop("No finite x/y/z coordinates available for plotting.", call. = FALSE)
  }

  if (!"local_height_col" %in% names(local_heights) || all(is.na(local_heights$local_height_col))) {
    message("Column local_height_col not found/usable; generating fallback colours from local_height.")
    local_heights$local_height_col <- fallback_col(local_heights$local_height)
  }

  if (!"local_height_log" %in% names(local_heights)) {
    message("Column local_height_log not found; generating display-only log10(abs(local_height)+eps).")
    local_heights$local_height_log <- log10(abs(local_heights$local_height) + .Machine$double.eps)
  } else {
    local_heights$local_height_log <- as.numeric(local_heights$local_height_log)
  }

  if (!"local_height_log_col" %in% names(local_heights) || all(is.na(local_heights$local_height_log_col))) {
    message("Column local_height_log_col not found/usable; generating fallback colours from local_height_log.")
    local_heights$local_height_log_col <- fallback_col(local_heights$local_height_log)
  }

  message("Opening rgl device...")
  rgl::open3d(useNULL = FALSE)

  
  set_cv3d_rgl_window_size(scale = 3)
mean_x <- mean(local_heights$x, na.rm = TRUE)
  if (!is.finite(mean_x)) mean_x <- 0

  message("Rendering raw/local-height-log 3D views...")
  rgl::plot3d(
    local_heights %>% dplyr::select(x, y, z) %>% dplyr::mutate(x = x - mean_x),
    aspect = "iso",
    col = local_heights$local_height_col,
    size = 5
  )
  rgl::points3d(
    local_heights %>% dplyr::select(x, y, z) %>% dplyr::mutate(x = x + mean_x),
    aspect = "iso",
    col = local_heights$local_height_log_col,
    size = 5
  )

  Sys.sleep(0.5)
  message("Saving PNG snapshot to: ", out_png)
  rgl::rgl.snapshot(filename = out_png, fmt = "png")

  if (!file.exists(out_png)) {
    stop("rgl snapshot did not create the expected PNG: ", out_png, call. = FALSE)
  }

  write_status(
    "success",
    if (open_rgl) "Raw local-height 3D plot created. Interactive rgl window is open; close it to finish."
    else "Raw local-height 3D plot created successfully.",
    list(
      output_plot_png = out_png,
      input_local_heights = input_csv,
      point_count = nrow(local_heights),
      open_rgl_window = open_rgl,
      plotted_panels = c("local_height", "local_height_log")
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
    message("CV3D raw local-height 3D plot failed: ", msg)
    write_status("failed", msg)
    quit(status = 1, save = "no")
  }
)
