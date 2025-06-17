import os
import matplotlib.pyplot as plt
import pandas as pd


def generate_visual_charts(data_frames: dict, output_dir: str) -> dict:
    """
    Generate market-gap-specific charts for each DataFrame.
    - If DataFrame has a 'Tier' column, create a pie chart of tier distribution.
    - If DataFrame has a 'Status' column, create a bar chart of status counts.
    - If DataFrame has 'Obsolescence' or 'Gap' numeric columns, create bar charts for them.
    - Otherwise, default to the first numeric column's value-count bar chart.

    Saves each chart as a PNG in output_dir and returns a mapping of
    chart keys to their file paths.

    Args:
      data_frames: dict mapping filenames to pandas DataFrames
      output_dir: directory path where charts will be saved

    Returns:
      charts: dict mapping chart keys to local image paths
    """
    charts = {}
    os.makedirs(output_dir, exist_ok=True)

    for name, df in data_frames.items():
        base = os.path.splitext(name)[0]
        # 1. Tier pie chart
        if 'Tier' in df.columns:
            counts = df['Tier'].value_counts()
            fig, ax = plt.subplots()
            counts.plot.pie(ax=ax, autopct='%1.1f%%')
            ax.set_ylabel('')
            ax.set_title(f"{base} Tier Distribution")
            path = os.path.join(output_dir, f"{base}_tier_pie.png")
            fig.savefig(path)
            plt.close(fig)
            charts[f"{base}_tier"] = path

        # 2. Status bar chart
        if 'Status' in df.columns:
            counts = df['Status'].value_counts()
            fig, ax = plt.subplots()
            counts.plot(kind='bar', ax=ax)
            ax.set_xlabel('Status')
            ax.set_ylabel('Count')
            ax.set_title(f"{base} Status Counts")
            path = os.path.join(output_dir, f"{base}_status_bar.png")
            fig.savefig(path)
            plt.close(fig)
            charts[f"{base}_status"] = path

        # 3. Obsolescence or Gap columns
        for col in df.columns:
            if 'Obsolescence' in col or 'Gap' in col:
                if pd.api.types.is_numeric_dtype(df[col]):
                    fig, ax = plt.subplots()
                    df[col].plot(kind='bar', ax=ax)
                    ax.set_xlabel(col)
                    ax.set_ylabel('Value')
                    ax.set_title(f"{base} {col}")
                    path = os.path.join(output_dir, f"{base}_{col}_bar.png")
                    fig.savefig(path)
                    plt.close(fig)
                    charts[f"{base}_{col}"] = path

        # 4. Default numeric column
        if not any(key.startswith(base) for key in charts):
            numeric_cols = df.select_dtypes(include='number').columns
            if len(numeric_cols) > 0:
                col = numeric_cols[0]
                counts = df[col].value_counts()
                fig, ax = plt.subplots()
                counts.plot(kind='bar', ax=ax)
                ax.set_xlabel(col)
                ax.set_ylabel('Count')
                ax.set_title(f"{base} {col} Distribution")
                path = os.path.join(output_dir, f"{base}_{col}_dist.png")
                fig.savefig(path)
                plt.close(fig)
                charts[f"{base}_{col}"] = path

    return charts
