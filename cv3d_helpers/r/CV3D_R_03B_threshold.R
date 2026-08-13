#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript CV3D_R_step03B_local_height_thresholding.R <task_json>", call. = FALSE)
}

task_json <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)

safe_require <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) stop("Required R package is not installed: ", pkg, call. = FALSE)
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
      script_version = "CV3D_R_step03B_local_height_thresholding_0.3.5"
    ),
    extra
  )
  dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(payload, status_file, pretty = TRUE, auto_unbox = TRUE, null = "null")
}

main <- function() {
  input_csv <- normalizePath(task$input_local_heights_abs, winslash = "/", mustWork = TRUE)
  output_plot <- task$output_threshold_preview_plot_abs
  height_column <- task$height_column
  preview_only <- isTRUE(task$preview_only)
  threshold <- suppressWarnings(as.numeric(task$local_height_threshold))
  min_threshold <- suppressWarnings(as.numeric(task$min_threshold))
  max_threshold <- suppressWarnings(as.numeric(task$max_threshold))

  # In preview-only mode there is intentionally no thresholded-output CSV yet.
  # The final 03B run receives output_local_height_thresholded_abs and writes it.
  output_csv <- NULL
  if (!preview_only) {
    output_csv <- task$output_local_height_thresholded_abs
    if (is.null(output_csv) || is.na(output_csv) || !nzchar(output_csv)) {
      stop("Final 03B run is missing output_local_height_thresholded_abs.", call. = FALSE)
    }
    dir.create(dirname(output_csv), recursive = TRUE, showWarnings = FALSE)
  }

  if (is.null(output_plot) || is.na(output_plot) || !nzchar(output_plot)) {
    stop("03B task is missing output_threshold_preview_plot_abs.", call. = FALSE)
  }
  dir.create(dirname(output_plot), recursive = TRUE, showWarnings = FALSE)

  if (!is.finite(min_threshold)) min_threshold <- 0
  if (!is.finite(max_threshold)) max_threshold <- 1
  if (!preview_only && !is.finite(threshold)) stop("local_height_threshold is not finite.", call. = FALSE)
  if (preview_only) threshold <- NA_real_
  if (min_threshold > max_threshold) {
    stop("min_threshold must be smaller than or equal to max_threshold.", call. = FALSE)
  }

  message("Reading local-height table: ", input_csv)
  df <- suppressMessages(readr::read_csv(input_csv, show_col_types = FALSE))

  # Convert legacy exponentiated columns to the current 0--1 contrast scales
  # when thresholding older datasets.
  if (identical(height_column, "local_height_contrast") && !height_column %in% names(df)) {
    legacy_name <- if ("local_height_exp10" %in% names(df)) "local_height_exp10" else if ("local_height_log" %in% names(df)) "local_height_log" else NA_character_
    legacy_exp <- if (!is.na(legacy_name)) as.numeric(df[[legacy_name]]) else if ("local_height" %in% names(df)) 10^as.numeric(df$local_height) else NULL
    if (!is.null(legacy_exp)) {
      finite <- is.finite(legacy_exp)
      contrast <- rep(NA_real_, length(legacy_exp))
      if (any(finite)) {
        bounds <- stats::quantile(legacy_exp[finite], probs = c(0.5, 0.9), na.rm = TRUE, names = FALSE)
        clipped <- pmin(pmax(legacy_exp[finite], bounds[1]), bounds[2])
        contrast[finite] <- if (isTRUE(all.equal(bounds[1], bounds[2]))) 0.5 else (clipped - bounds[1]) / diff(bounds)
      }
      df$local_height_contrast <- contrast
    }
  }
  if (identical(height_column, "local_height_norm_contrast") && !height_column %in% names(df)) {
    legacy_name <- if ("local_height_norm_exp10" %in% names(df)) "local_height_norm_exp10" else if ("local_height_log_norm" %in% names(df)) "local_height_log_norm" else NA_character_
    if (!is.na(legacy_name)) {
      df$local_height_norm_contrast <- pmin(pmax((as.numeric(df[[legacy_name]]) - 1) / 9, 0), 1)
    } else if ("local_height_norm" %in% names(df)) {
      df$local_height_norm_contrast <- pmin(pmax((10^as.numeric(df$local_height_norm) - 1) / 9, 0), 1)
    }
  }

  required_cols <- c("x", "y", "z", height_column)
  missing_cols <- setdiff(required_cols, names(df))
  if (length(missing_cols) > 0) {
    stop("Input table is missing required columns: ", paste(missing_cols, collapse = ", "), call. = FALSE)
  }

  df <- df %>%
    dplyr::mutate(
      x = as.numeric(x),
      y = as.numeric(y),
      z = as.numeric(z),
      .threshold_height = as.numeric(.data[[height_column]]),
      .source_index = dplyr::row_number()
    )

  input_point_count <- nrow(df)
  finite_height_count <- sum(is.finite(df$.threshold_height))
  if (finite_height_count == 0) stop("No finite values found in height column: ", height_column, call. = FALSE)

  if (preview_only) {
    thresholded <- df[0, , drop = FALSE]
    thresholded_point_count <- NA_integer_
    message("Preview-only mode: no final thresholded point cloud will be written.")
  } else {
    thresholded <- df %>%
      dplyr::filter(is.finite(.threshold_height), .threshold_height >= threshold)

    thresholded_point_count <- nrow(thresholded)

    output <- thresholded %>%
      dplyr::transmute(
        x = x,
        y = y,
        z = z,
        source_index = .source_index,
        height_value = .threshold_height
      )

    readr::write_csv(output, output_csv)

    message("Thresholded point count: ", thresholded_point_count, " / ", input_point_count)
    message("Writing thresholded local-height point cloud: ", output_csv)
  }

  # Inspection plot: one eye panel coloured with a continuous viridis scale.
  # The selected preview minimum and maximum define the colour scale directly;
  # values outside the range are clipped to the corresponding end colour.
  png(output_plot, width = 1200, height = 900, res = 150)
  old_par <- par(no.readonly = TRUE)

  finite_height <- is.finite(df$.threshold_height)
  palette_n <- 256

  pal <- grDevices::colorRampPalette(
    c("#440154", "#482878", "#3E4989", "#31688E", "#26828E",
      "#1F9E89", "#35B779", "#6DCD59", "#B4DE2C", "#FDE725")
  )(palette_n)

  colour_range <- c(min_threshold, max_threshold)
  if (!all(is.finite(colour_range))) {
    colour_range <- range(df$.threshold_height[finite_height], na.rm = TRUE)
  }

  if (!all(is.finite(colour_range)) || diff(colour_range) == 0) {
    color_idx <- rep(round(palette_n / 2), nrow(df))
  } else {
    scaled_height <- (df$.threshold_height - colour_range[1]) / diff(colour_range)
    scaled_height[!is.finite(scaled_height)] <- 0.5
    scaled_height <- pmin(pmax(scaled_height, 0), 1)
    color_idx <- pmax(1, pmin(palette_n, round(scaled_height * (palette_n - 1)) + 1))
  }
  point_cols <- pal[color_idx]

  add_continuous_viridis_legend <- function(colour_range, pal, height_column) {
    usr <- par("usr")
    x_span <- usr[2] - usr[1]
    y_span <- usr[4] - usr[3]

    x_left <- usr[2] - 0.080 * x_span
    x_right <- usr[2] - 0.045 * x_span
    y_bottom <- usr[3] + 0.12 * y_span
    y_top <- usr[4] - 0.12 * y_span

    if (!all(is.finite(colour_range)) || diff(colour_range) == 0) {
      rect(x_left, y_bottom, x_right, y_top, col = pal[round(length(pal) / 2)], border = "black")
      text(x_right + 0.018 * x_span, (y_bottom + y_top) / 2,
           labels = signif(colour_range[1], 4), adj = c(0, 0.5), cex = 0.7)
    } else {
      n <- length(pal)
      y0 <- seq(y_bottom, y_top, length.out = n + 1)
      for (i in seq_len(n)) {
        rect(x_left, y0[i], x_right, y0[i + 1], col = pal[i], border = NA)
      }
      rect(x_left, y_bottom, x_right, y_top, border = "black")

      tick_values <- pretty(colour_range, n = 5)
      tick_values <- tick_values[tick_values >= colour_range[1] & tick_values <= colour_range[2]]
      tick_values <- sort(unique(c(colour_range[1], tick_values, colour_range[2])))
      tick_y <- y_bottom + (tick_values - colour_range[1]) / diff(colour_range) * (y_top - y_bottom)
      segments(x_right, tick_y, x_right + 0.012 * x_span, tick_y)
      text(x_right + 0.018 * x_span, tick_y, labels = signif(tick_values, 4), adj = c(0, 0.5), cex = 0.7)
    }

    text(
      x_left,
      y_top + 0.055 * y_span,
      labels = height_column,
      adj = c(0, 0),
      cex = 0.75
    )
  }

  plot(
    df$x,
    df$y,
    pch = 16,
    cex = 0.25,
    col = point_cols,
    asp = 1,
    main = paste("Local-height values:", height_column),
    xlab = "x",
    ylab = "y"
  )
  add_continuous_viridis_legend(colour_range, pal, height_column)

  if (!preview_only && nrow(thresholded) > 0) {
    points(thresholded$x, thresholded$y, pch = 16, cex = 0.4, col = "red")
    legend("bottomright", legend = "thresholded", col = "red", pch = 16, cex = 0.75, bg = "white")
  }

  try(par(old_par), silent = TRUE)
  dev.off()

  warnings <- list()
  if (!preview_only && thresholded_point_count == 0) warnings <- c(warnings, "No points passed the selected threshold.")

  if (preview_only) {
    write_status(
      "success_preview",
      "03B viridis local-height preview created successfully.",
      list(
        summary = list(
          input_mode = task$input_mode,
          input_local_heights = task$input_local_heights,
          height_column = height_column,
          min_threshold = min_threshold,
          max_threshold = max_threshold,
          input_point_count = input_point_count,
          finite_height_count = finite_height_count,
          output_threshold_preview_plot = task$output_threshold_preview_plot
        ),
        warnings = warnings
      )
    )
  } else {
    write_status(
      "success",
      "03B local-height thresholding completed successfully.",
      list(
        summary = list(
          input_mode = task$input_mode,
          input_local_heights = task$input_local_heights,
          height_column = height_column,
          min_threshold = min_threshold,
          max_threshold = max_threshold,
          local_height_threshold = threshold,
          input_point_count = input_point_count,
          finite_height_count = finite_height_count,
          thresholded_point_count = thresholded_point_count,
          output_local_height_thresholded = task$output_local_height_thresholded,
          output_threshold_preview_plot = task$output_threshold_preview_plot
        ),
        warnings = warnings
      )
    )
  }
}

tryCatch(
  main(),
  error = function(e) {
    msg <- conditionMessage(e)
    tb <- paste(utils::capture.output(traceback()), collapse = "\n")
    message("CV3D 03B local-height thresholding failed: ", msg)
    if (nzchar(tb)) message(tb)
    write_status("failed", msg, list(traceback = tb))
    quit(status = 1, save = "no")
  }
)
