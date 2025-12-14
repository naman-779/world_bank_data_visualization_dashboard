# World Bank Data Visualization Dashboard

An interactive dashboard that visualizes key global development indicators using data from the World Bank API. Built with Python, Dash, and Plotly.

## Prerequisites

-   Python 3.8+
-   pip

## Installation

1.  **Clone the repository** (if applicable) or download the source code.
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

    *If you don't use requirements.txt, the core packages are:*
    ```bash
    pip install dash plotly pandas wbgapi
    ```

## Usage

1.  **Run the application**:
    ```bash
    python app.py
    ```

2.  **Open the dashboard**:
    Navigate to `http://127.0.0.1:8050/` in your web browser.

## Data Source

The data is fetched from the World Bank API using the wbgapi library. It is also cached in a csv file for faster loading. (world_bank_data_v3.csv)