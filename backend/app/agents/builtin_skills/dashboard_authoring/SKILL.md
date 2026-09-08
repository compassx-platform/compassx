# Dashboard & Widget Authoring Skill Guide

## Overview
This skill provides comprehensive instructions for designing, building, and publishing interactive, high-performance dashboards on CompassX.

---

## 1. Dashboard Structure & Information Architecture

Dashboards in CompassX are structured in ordered layers:
$$\textbf{Dashboard} \longrightarrow \textbf{Pages (1 or more)} \longrightarrow \textbf{SQL Datasets} \longrightarrow \textbf{Visual Widgets}$$

### Page Architecture Guidelines:
* **Single Page (Focused Views / Default)**: If the dashboard addresses a focused domain topic, operational summary, or standard KPI view, present a clean single-page dashboard. Do not artificially split related metrics across multiple pages.
* **Multi-Page (Distinct Business Perspectives)**: If the scope spans distinct business perspectives, personas, or analytical depths (e.g., Executive Overview vs. Detailed Diagnostics vs. Financial Impact), structure dedicated, purposeful pages.

### Step-by-Step Workflow:
1. **Create Dashboard**: Call `create_dashboard` with a descriptive name (creates initial page).
2. **Setup Pages (if multi-page warranted)**: Call `update_dashboard(dashboard_id="...", pages=["Overview", "Diagnostics", ...])`.
3. **Register SQL Datasets**: Call `add_dataset` for each visual component. Always validate SQL first with `run_query`.
4. **Bind Widgets to Datasets**: Call `add_widget` with `widget_type: "chart"` and specify `chart_config` (`chartType`, `datasetId`, `xField`, `yFields`).
5. **Publish**: Call `publish_dashboard` to finalize and register in the Unified Catalog.

---

## 2. All 19 Supported Chart Types & Configurations

Every visual widget MUST have:
* `widget_type: "chart"` (Never use chart names as widget_type).
* `chart_config.chartType`: One of the 19 valid types listed below.
* `chart_config.datasetId`: UUID of the dataset providing the data.

---

### A. Metric KPI Cards & Single Stats (`chartType: "counter"`)
Displays a single primary KPI metric value with optional comparison and trend sparkline.
* **Required**: `datasetId`, `yFields` (1 measure column name)
* **Optional**: `showSparkline`, `comparisonField`, `numberFormat`, `conditionalFormatting`
* **JSON Example**:
```json
{
  "widget_type": "chart",
  "title": "Day Plant Availability (%)",
  "chart_config": {
    "chartType": "counter",
    "datasetId": "<dataset_id>",
    "yFields": ["mpa_pct"],
    "numberFormat": { "type": "percent", "decimals": 2 },
    "conditionalFormatting": [
      { "min": 98.0, "color": "#22c55e" },
      { "max": 95.0, "color": "#ef4444" }
    ]
  },
  "grid_item": { "x": 0, "y": 0, "w": 3, "h": 4 }
}
```

---

### B. Bar / Column Charts (`chartType: "bar"`)
Vertical or horizontal bars comparing discrete categories across one or more numeric metrics.
* **Required**: `datasetId`, `xField` (category dimension), `yFields` (array of measure columns)
* **Optional**: `layout` (`"group"` | `"stack"` | `"100stack"`), `colorField`, `showValueLabels`, `showGridlines`, `facetField`
* **JSON Example**:
```json
{
  "widget_type": "chart",
  "title": "Capacity by Site (AC vs DC MW)",
  "chart_config": {
    "chartType": "bar",
    "datasetId": "<dataset_id>",
    "xField": "site",
    "yFields": ["ac_capacity_mw", "dc_capacity_mwp"],
    "layout": "group",
    "showValueLabels": true,
    "showGridlines": true
  },
  "grid_item": { "x": 0, "y": 4, "w": 6, "h": 8 }
}
```

---

### C. Time-Series Line Charts (`chartType: "line"`)
Continuous multi-line or single-line trend charts across dates or timestamps.
* **Required**: `datasetId`, `xField` (date/timestamp), `yFields` (array of measure columns)
* **Optional**: `colorField`, `lineThickness` (1-5), `showGridlines`, `annotations`
* **JSON Example**:
```json
{
  "widget_type": "chart",
  "title": "Daily Actual vs Budget Generation (MWh)",
  "chart_config": {
    "chartType": "line",
    "datasetId": "<dataset_id>",
    "xField": "report_date",
    "yFields": ["me_mwh", "be_mwh"],
    "showGridlines": true,
    "annotations": [
      { "axis": "y", "value": 500.0, "label": "P50 Target Line", "color": "#ef4444" }
    ]
  },
  "grid_item": { "x": 0, "y": 0, "w": 7, "h": 8 }
}
```

---

### D. Interactive Data Tables (`chartType: "table"`)
Interactive tabular grid showing all or selected dataset columns with sorting and search.
* **Required**: `datasetId`
* **Optional**: `pageSize` (default 10 or 25), `showSearch` (true/false), `wrapText` (true/false)
* **JSON Example**:
```json
{
  "widget_type": "chart",
  "title": "Equipment MTTR & Reliability Master Table",
  "chart_config": {
    "chartType": "table",
    "datasetId": "<dataset_id>",
    "pageSize": 25,
    "showSearch": true
  },
  "grid_item": { "x": 0, "y": 8, "w": 12, "h": 9 }
}
```

---

### E. Pie / Donut Breakdown Charts (`chartType: "pie"`)
Circular slice breakdown showing proportional contributions to a total.
* **Required**: `datasetId`, `xField` (slice category dimension), `yFields` (1 measure column)
* **Optional**: `showValueLabels` (true/false)
* **JSON Example**:
```json
{
  "widget_type": "chart",
  "title": "Revenue Loss by Equipment Type",
  "chart_config": {
    "chartType": "pie",
    "datasetId": "<dataset_id>",
    "xField": "equipment_type",
    "yFields": ["revenue_loss_mn"],
    "showValueLabels": true
  },
  "grid_item": { "x": 7, "y": 0, "w": 5, "h": 8 }
}
```

---

### F. Dual-Axis Combo Charts (`chartType: "combo"`)
Combines bars on primary left Y-axis with lines on secondary right Y2-axis for measures on different scales.
* **Required**: `datasetId`, `xField`, `yFields` (left axis bars), `y2Fields` (right axis lines)
* **Optional**: `showGridlines`, `showValueLabels`
* **JSON Example**:
```json
{
  "widget_type": "chart",
  "title": "Daily Generation (MWh) vs Plant Availability (%)",
  "chart_config": {
    "chartType": "combo",
    "datasetId": "<dataset_id>",
    "xField": "report_date",
    "yFields": ["actual_energy_mwh"],
    "y2Fields": ["plant_availability_pct"],
    "showGridlines": true
  },
  "grid_item": { "x": 0, "y": 0, "w": 12, "h": 8 }
}
```

---

### G. Waterfall Variance Charts (`chartType: "waterfall"`)
Sequential step breakdown showing positive and negative variances from baseline to total.
* **Required**: `datasetId`, `xField` (variance category name), `yFields` (delta variance value)
* **Optional**: `showValueLabels`
* **JSON Example**:
```json
{
  "widget_type": "chart",
  "title": "Generation Loss Waterfall (MWh)",
  "chart_config": {
    "chartType": "waterfall",
    "datasetId": "<dataset_id>",
    "xField": "loss_component",
    "yFields": ["loss_mwh"]
  },
  "grid_item": { "x": 0, "y": 0, "w": 6, "h": 8 }
}
```

---

### H. Multi-Dimensional Pivot Matrix (`chartType: "pivot"`)
Aggregated matrix grouping rows and columns across hierarchical dimensions.
* **Required**: `datasetId`, `xField` (column grouping), `yFields` (aggregated values)
* **Optional**: `facetField` (row grouping)
* **JSON Example**:
```json
{
  "widget_type": "chart",
  "title": "Module Cleaning Monthly Status Matrix",
  "chart_config": {
    "chartType": "pivot",
    "datasetId": "<dataset_id>",
    "xField": "status",
    "yFields": ["cleaned_modules_count"],
    "facetField": "site"
  },
  "grid_item": { "x": 0, "y": 8, "w": 12, "h": 8 }
}
```

---

### I. Area Charts (`chartType: "area"`)
Filled area chart for cumulative or volume trends over time.
* **Required**: `datasetId`, `xField` (date/time), `yFields` (measure columns)
* **Optional**: `layout` (`"group"` | `"stack"` | `"100stack"`), `showGridlines`

---

### J. Scatter & Bubble Charts (`chartType: "scatter"` / `chartType: "bubble"`)
Correlates two continuous numeric variables (plus optional marker size).
* **Required**: `datasetId`, `xField` (X-axis numeric metric), `yFields` (Y-axis numeric metric)
* **Optional for Bubble**: `sizeField` (bubble radius measure), `colorField` (category)

---

### K. Heatmaps (`chartType: "heatmap"`)
2D matrix where cell color intensity indicates value magnitude.
* **Required**: `datasetId`, `xField` (X dimension), `yFields` (Y dimension & intensity measure)

---

### L. Histograms & Box Plots (`chartType: "histogram"` / `chartType: "box"`)
Distribution analysis for statistical variance and quartiles.
* **Required**: `datasetId`, `yFields` (distribution measure column)
* **Optional for Box**: `xField` (category grouping)

---

### M. Funnel & Sankey Diagrams (`chartType: "funnel"` / `chartType: "sankey"`)
Conversion funnels or directional flow allocations between nodes.
* **Required for Funnel**: `datasetId`, `xField` (stage name), `yFields` (stage count)

---

## 3. Layout Best Practices (12-Column Grid)

* **Top KPI Row**: 3 or 4 metric counter cards side-by-side (`w: 3` each, `h: 4`, `y: 0`).
* **Main Visualizations**: 2 medium charts side-by-side (`w: 6` each, `h: 8`, `y: 4`), or 1 wide time-series chart (`w: 7` or `w: 12`, `h: 8`).
* **Breakdown Tables**: Place wide data tables at the bottom spanning the full width (`w: 12`, `h: 8` or `h: 9`, `y: 12`).
