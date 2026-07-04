#!/usr/bin/env Rscript

# Usage:
#   Rscript CV3D_R_step03A2b_plot_local_heights.R <task_json>

suppressPackageStartupMessages({
  library(jsonlite)
  library(readr)
  library(dplyr)
  library(rgl)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript CV3D_R_step03A2b_plot_local_heights.R <task_json>", call. = FALSE)
}

task_json <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

read_task <- function(path) jsonlite::fromJSON(path, simplifyVector = TRUE)

write_status <- function(path, status, message, extra = list()) {
  payload <- c(
    list(
      status = status,
      message = message,
      task_json = task_json,
      script_version = "CV3D_R_step03A2b_plot_local_heights_0.1.1"
    ),
    extra
  )
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(payload, path, pretty = TRUE, auto_unbox = TRUE, null = "null")
}


set_cv3d_rgl_window_size <- function(scale = 3) {
  width <- 600 * scale
  height <- 450 * scale
  try(rgl::par3d(windowRect = c(40, 40, 40 + width, 40 + height)), silent = TRUE)
}


task <- read_task(task_json)

input_csv <- normalizePath(task$input_local_heights_normalized_abs, winslash = "/", mustWork = TRUE)
out_png <- task$output_plot_png_abs
status_file <- task$status_file_abs
open_rgl <- isTRUE(task$open_rgl_window)

dir.create(dirname(out_png), recursive = TRUE, showWarnings = FALSE)
dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)

message("Reading normalized local-height CSV: ", input_csv)
local_heights <- suppressMessages(readr::read_csv(input_csv, show_col_types = FALSE))

required_cols <- c("x", "y", "z", "local_height_col", "local_height_log_col", "local_height_log_norm_col")
missing_cols <- setdiff(required_cols, names(local_heights))
if (length(missing_cols) > 0) {
  stop(
    "The normalized local-height CSV is missing required columns: ",
    paste(missing_cols, collapse = ", "),
    call. = FALSE
  )
}

if (nrow(local_heights) == 0) {
  stop("The normalized local-height CSV is empty.", call. = FALSE)
}

message("Opening rgl device...")
rgl::open3d(useNULL = FALSE)

  set_cv3d_rgl_window_size(scale = 3)
on.exit(try(rgl::par3d(skipRedraw = FALSE), silent = TRUE), add = TRUE)

mean_x <- mean(local_heights$x, na.rm = TRUE)

message("Rendering 3D local-height views...")
rgl::plot3d(
  local_heights %>%
    dplyr::select(x, y, z) %>%
    dplyr::mutate(x = x - (mean_x * 2)),
  aspect = "iso",
  col = local_heights$local_height_col,
  size = 5
)
rgl::points3d(
  local_heights %>% dplyr::select(x, y, z),
  aspect = "iso",
  col = local_heights$local_height_log_col,
  size = 5
)
rgl::points3d(
  local_heights %>%
    dplyr::select(x, y, z) %>%
    dplyr::mutate(x = x + (mean_x * 2)),
  aspect = "iso",
  col = local_heights$local_height_log_norm_col,
  size = 5
)

# Give the device a moment to render before snapshotting.
Sys.sleep(0.5)
message("Saving PNG snapshot to: ", out_png)
rgl::rgl.snapshot(filename = out_png, fmt = "png")

write_status(
  status_file,
  "success",
  if (open_rgl) {
    "3D plot created. Interactive rgl window is open; close it to let the runner finish."
  } else {
    "3D plot created successfully."
  },
  list(
    output_plot_png = out_png,
    input_local_heights_normalized = input_csv,
    point_count = nrow(local_heights),
    open_rgl_window = open_rgl
  )
)

if (open_rgl) {
  message("Interactive rgl window requested. Close the rgl window to finish this task.")
  repeat {
    Sys.sleep(0.2)
    cur <- tryCatch(rgl::rgl.cur(), error = function(e) 0)
    if (is.null(cur) || identical(cur, 0L) || identical(cur, 0)) {
      break
    }
  }
} else {
  try(rgl::close3d(), silent = TRUE)
}
