"""
Book Price Tracker - Data Visualization Module
Creates charts and graphs for the Flask UI
"""

import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
import io
import base64
from pathlib import Path
import seaborn as sns

# Set style for better looking charts
try:
    plt.style.use("seaborn-v0_8")
except OSError:
    try:
        plt.style.use("seaborn")
    except OSError:
        plt.style.use("default")

try:
    sns.set_palette("husl")
except:
    pass  # Fallback if seaborn is not available


def create_price_comparison_chart(df: pd.DataFrame, isbn: str = None) -> str:
    """
    Create a price comparison chart for different sources

    Args:
        df: DataFrame with price data
        isbn: Optional specific ISBN to filter by

    Returns:
        Base64 encoded image string
    """
    if df.empty:
        return create_no_data_chart("No price data available")

    # Filter by ISBN if specified
    if isbn:
        filtered_df = df[df["isbn"] == isbn]
        if filtered_df.empty:
            return create_no_data_chart(f"No data for ISBN {isbn}")
    else:
        filtered_df = df

    # Filter out unsuccessful records and NaN prices
    filtered_df = filtered_df[
        (filtered_df["success"] == True) & 
        (filtered_df["price"].notna()) & 
        (filtered_df["price"] > 0)
    ]
    
    if filtered_df.empty:
        return create_no_data_chart("No valid price data available")

    # Get latest price for each source
    latest_prices = filtered_df.groupby("source")["price"].last().reset_index()

    if latest_prices.empty or latest_prices["price"].isna().all():
        return create_no_data_chart("No valid prices found")

    # Create the chart
    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.bar(latest_prices["source"], latest_prices["price"], color=["#3498db", "#e74c3c", "#2ecc71", "#f39c12"])

    # Customize the chart
    ax.set_title(f"Price Comparison{f' for ISBN {isbn}' if isbn else ''}", fontsize=16, fontweight="bold")
    ax.set_xlabel("Source", fontsize=12)
    ax.set_ylabel("Price ($)", fontsize=12)
    ax.grid(axis="y", alpha=0.3)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        if pd.notna(height) and height > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + max(height * 0.01, 0.5),  # Dynamic offset based on height
                f"${height:.2f}",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

    # Rotate x-axis labels if needed
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    return fig_to_base64(fig)

    # Rotate x-axis labels if needed
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    return fig_to_base64(fig)


def create_price_trend_chart(df: pd.DataFrame, isbn: str = None) -> str:
    """
    Create a price trend chart over time

    Args:
        df: DataFrame with price data
        isbn: Optional specific ISBN to filter by

    Returns:
        Base64 encoded image string
    """
    if df.empty:
        return create_no_data_chart("No price data available")

    # Filter by ISBN if specified
    if isbn:
        filtered_df = df[df["isbn"] == isbn]
        if filtered_df.empty:
            return create_no_data_chart(f"No data for ISBN {isbn}")
    else:
        filtered_df = df

    # Filter out unsuccessful records and NaN prices
    filtered_df = filtered_df.copy()
    filtered_df = filtered_df[
        (filtered_df["success"] == True) & 
        (filtered_df["price"].notna()) & 
        (filtered_df["price"] > 0)
    ]
    
    if filtered_df.empty:
        return create_no_data_chart("No valid price data available for trends")

    # Convert timestamp to datetime
    filtered_df["timestamp"] = pd.to_datetime(filtered_df["timestamp"])

    # Create the chart
    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot line for each source
    sources = filtered_df["source"].unique()
    colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]

    for i, source in enumerate(sources):
        source_data = filtered_df[filtered_df["source"] == source].sort_values("timestamp")
        if not source_data.empty and len(source_data) > 0:
            ax.plot(
                source_data["timestamp"],
                source_data["price"],
                marker="o",
                label=source,
                color=colors[i % len(colors)],
                linewidth=2,
                markersize=6,
            )

    # Customize the chart
    ax.set_title(f"Price Trends Over Time{f' for ISBN {isbn}' if isbn else ''}", fontsize=16, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Price ($)", fontsize=12)
    ax.grid(True, alpha=0.3)
    
    # Only show legend if we have data to plot
    if sources.size > 0:
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

    # Format dates on x-axis
    plt.xticks(rotation=45)
    plt.tight_layout()

    return fig_to_base64(fig)


def create_source_summary_chart(df: pd.DataFrame) -> str:
    """
    Create a summary chart showing successful data by source

    Args:
        df: DataFrame with price data

    Returns:
        Base64 encoded image string
    """
    if df.empty:
        return create_no_data_chart("No data available")

    # Count successful records by source only
    successful_df = df[df["success"] == True]
    
    if successful_df.empty:
        return create_no_data_chart("No successful records available")
    
    source_counts = successful_df["source"].value_counts()

    if source_counts.empty:
        return create_no_data_chart("No valid source data available")

    # Create pie chart
    fig, ax = plt.subplots(figsize=(8, 8))

    colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]
    wedges, texts, autotexts = ax.pie(
        source_counts.values, 
        labels=source_counts.index, 
        autopct="%1.1f%%", 
        colors=colors[:len(source_counts)], 
        startangle=90
    )

    # Customize the chart
    ax.set_title("Successful Price Records by Source", fontsize=16, fontweight="bold")

    # Make percentage text bold
    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontweight("bold")

    plt.tight_layout()

    return fig_to_base64(fig)


def create_no_data_chart(message: str) -> str:
    """
    Create a placeholder chart when no data is available

    Args:
        message: Message to display

    Returns:
        Base64 encoded image string
    """
    fig, ax = plt.subplots(figsize=(8, 6))

    ax.text(
        0.5,
        0.5,
        message,
        ha="center",
        va="center",
        fontsize=16,
        transform=ax.transAxes,
        bbox=dict(boxstyle="round", facecolor="lightgray"),
    )

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    return fig_to_base64(fig)


def fig_to_base64(fig) -> str:
    """
    Convert matplotlib figure to base64 string

    Args:
        fig: Matplotlib figure

    Returns:
        Base64 encoded image string
    """
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
    img_buffer.seek(0)

    img_string = base64.b64encode(img_buffer.getvalue()).decode("utf-8")
    plt.close(fig)  # Close figure to free memory

    return img_string


def generate_dashboard_charts(df: pd.DataFrame) -> dict:
    """
    Generate all charts for the dashboard

    Args:
        df: DataFrame with price data

    Returns:
        Dictionary with chart names and base64 encoded images
    """
    charts = {}

    try:
        charts["price_comparison"] = create_price_comparison_chart(df)
        charts["price_trends"] = create_price_trend_chart(df)
        charts["source_summary"] = create_source_summary_chart(df)
    except Exception as e:
        # If any chart fails, create error chart
        error_chart = create_no_data_chart(f"Error generating charts: {str(e)}")
        charts["price_comparison"] = error_chart
        charts["price_trends"] = error_chart
        charts["source_summary"] = error_chart

    return charts


if __name__ == "__main__":
    # Test the visualization with sample data
    print("Testing data visualization module...")

    try:
        # Load sample data
        from app import load_prices_data

        df = load_prices_data()
        print(f"Loaded {len(df)} records for testing")

        if not df.empty:
            charts = generate_dashboard_charts(df)
            print(f"Generated {len(charts)} charts successfully")

            # Save a sample chart to file for testing
            if "price_comparison" in charts:
                chart_data = charts["price_comparison"]
                print(f"Price comparison chart generated (length: {len(chart_data)} characters)")
        else:
            print("No data available for testing charts")

        print("Visualization module test complete!")
    except ImportError as e:
        print(f"Could not import app module for testing: {e}")
    except Exception as e:
        print(f"Error during testing: {e}")
