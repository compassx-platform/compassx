"""Starter notebook content generator for newly created workspaces."""
from __future__ import annotations

from typing import Any


def build_getting_started_notebook(
    catalog_name: str,
    schema_name: str = "default",
    volume_name: str = "sample_data",
) -> dict[str, Any]:
    """Generate the JSON structure of the getting-started notebook.

    Includes working code references for:
    - Writing and reading files to/from CompassX Volumes (pandas & fsspec)
    - Authoring, locally testing, and promoting AI Agent Tools (@cx.tool)
    - Querying data using DuckDB
    """
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# CompassX Platform Reference & Getting Started\n",
                "\n",
                f"Welcome to your workspace! This notebook provides practical code references for core CompassX platform capabilities:\n",
                f"- **Volumes**: Writing and reading files using `cx://` URLs with pandas and `fsspec`\n",
                f"- **AI Agent Tools**: Defining tools with `@cx.tool`, testing locally, and promoting them to the Unified Catalog\n",
                f"- **Data Queries**: Querying tables and data using DuckDB\n",
                "\n",
                f"**Current Catalog Context**: `{catalog_name}`  \n",
                f"**Current Schema Context**: `{schema_name}`  \n",
                f"**Default Volume**: `{volume_name}`\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1. Volumes: Writing Files\n",
                "\n",
                "CompassX Volumes provide cloud-native, securable storage accessible via the `cx://` protocol.\n",
                "URL format: `cx://<catalog>.<schema>.<volume>/<file_path>`\n",
                "\n",
                "You can write tabular data directly using **pandas** or arbitrary text/binary files using **fsspec**.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import pandas as pd\n",
                "import fsspec\n",
                "\n",
                f'CATALOG = "{catalog_name}"\n',
                f'SCHEMA = "{schema_name}"\n',
                f'VOLUME = "{volume_name}"\n',
                "\n",
                "# Sample tabular dataset\n",
                "data = {\n",
                '    "device_id": [101, 102, 103, 104],\n',
                '    "sensor_name": ["Solar Inverter A", "Solar Inverter B", "Battery Unit 1", "Grid Gateway"],\n',
                '    "efficiency_rate": [0.94, 0.98, 0.89, 0.96],\n',
                '    "status": ["active", "active", "maintenance", "active"],\n',
                "}\n",
                "df = pd.DataFrame(data)\n",
                "\n",
                "# ── Option A: Save DataFrame as CSV to Volume ──────────────────────\n",
                'csv_url = f"cx://{CATALOG}.{SCHEMA}.{VOLUME}/devices.csv"\n',
                "df.to_csv(csv_url, index=False)\n",
                'print(f"Successfully saved DataFrame to: {csv_url}")\n',
                "\n",
                "# ── Option B: Write raw text or binary data using fsspec ───────────\n",
                'txt_url = f"cx://{CATALOG}.{SCHEMA}.{VOLUME}/readme.txt"\n',
                'with fsspec.open(txt_url, "w") as f:\n',
                '    f.write("Welcome to CompassX Volumes!\\nFiles written here are securely stored and catalog-governed.\\n")\n',
                'print(f"Successfully wrote text file to: {txt_url}")\n',
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 2. Volumes: Reading Files\n",
                "\n",
                "Files stored in Volumes can be read back using `pandas.read_csv`, `pandas.read_parquet`, or `fsspec.open`.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ── Option A: Read CSV directly into a pandas DataFrame ────────────\n",
                "df_read = pd.read_csv(csv_url)\n",
                'print("DataFrame read from volume:")\n',
                "display(df_read)\n",
                "\n",
                "# ── Option B: Read raw text file using fsspec ──────────────────────\n",
                'with fsspec.open(txt_url, "r") as f:\n',
                '    print("\\nRaw text read from volume:")\n',
                "    print(f.read())\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 3. AI Agent Tools: Authoring & Promotion\n",
                "\n",
                "CompassX enables you to write Python functions, decorate them with `@cx.tool`, test them locally in your notebook, and **promote** them to the Unified Catalog so AI Agents can autonomously discover and invoke them.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import compassx_tools as cx\n",
                "\n",
                "# Define a tool with @cx.tool\n",
                "@cx.tool(\n",
                '    name="calculate_solar_power",\n',
                '    description="Calculate expected solar power output in Watts and Kilowatts given panel surface area and solar irradiance."\n',
                ")\n",
                "def calculate_solar_power(area_sqm: float, irradiance_wm2: float = 1000.0, efficiency: float = 0.20) -> dict:\n",
                '    """Calculate expected solar power output.\n',
                "    \n",
                "    Parameters:\n",
                "        area_sqm: Total panel surface area in square meters.\n",
                "        irradiance_wm2: Solar irradiance in W/m^2 (standard test condition is 1000 W/m^2).\n",
                "        efficiency: Panel conversion efficiency rate (e.g. 0.20 for 20%).\n",
                '    """\n',
                "    watts = round(area_sqm * irradiance_wm2 * efficiency, 2)\n",
                "    return {\n",
                '        "surface_area_sqm": area_sqm,\n',
                '        "irradiance_wm2": irradiance_wm2,\n',
                '        "efficiency_rate": efficiency,\n',
                '        "power_output_watts": watts,\n',
                '        "power_output_kw": round(watts / 1000.0, 3),\n',
                "    }\n",
                "\n",
                "# Test the tool locally in the notebook before promoting\n",
                "test_output = calculate_solar_power(area_sqm=30.0, irradiance_wm2=950.0)\n",
                'print("Local tool execution result:", test_output)\n',
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Promote the tool into your workspace catalog and schema\n",
                "# Once promoted, AI agents running workflows in this workspace can call this tool\n",
                "promoted_tool = cx.tools.promote(\n",
                "    calculate_solar_power,\n",
                "    catalog=CATALOG,\n",
                "    schema=SCHEMA,\n",
                ")\n",
                'print(f"Tool promoted successfully: {promoted_tool.full_name} (Version {promoted_tool.version})")\n',
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 4. Querying Data with DuckDB\n",
                "\n",
                "You can also run ad-hoc SQL queries or join datasets using DuckDB directly inside your compute kernel.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import duckdb\n",
                "\n",
                "# Query pandas DataFrames directly with SQL\n",
                'con = duckdb.connect()\n',
                'query_result = con.execute("""\n',
                "    SELECT \n",
                "        sensor_name, \n",
                "        efficiency_rate * 100.0 AS efficiency_pct, \n",
                "        status \n",
                "    FROM df \n",
                "    WHERE status = 'active'\n",
                '""").fetchdf()\n',
                "\n",
                "display(query_result)\n",
            ],
        },
    ]

    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11",
            },
        },
        "cells": cells,
    }
