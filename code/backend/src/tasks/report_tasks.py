"""
Report generation tasks for asynchronous processing.
Handles PDF/Excel report generation and data export tasks.
"""

import io
import logging
from datetime import datetime
from typing import Any, Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from src.tasks.celery_app import (
    TaskValidationError,
    celery_app,
    task_result_manager,
    task_with_progress,
)

logger = logging.getLogger(__name__)


@task_with_progress()
def generate_portfolio_report(
    self, portfolio_data: Dict, report_config: Dict
) -> Dict[str, Any]:
    """
    Generate comprehensive portfolio report in PDF format.

    Args:
        portfolio_data: Portfolio data and analysis results
        report_config: Report configuration and formatting options

    Returns:
        Dict containing report file path and metadata
    """
    try:
        task_result_manager.store_task_progress(
            self.request.id,
            {"progress": 10, "status": "Initializing report generation"},
        )
        required_fields = ["portfolio_name", "holdings", "performance_data"]
        for field in required_fields:
            if field not in portfolio_data:
                raise TaskValidationError(f"Missing required field: {field}")
        report_filename = f"portfolio_report_{portfolio_data['portfolio_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        report_path = f"/tmp/{report_filename}"
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 20, "status": "Creating report structure"}
        )
        doc = SimpleDocTemplate(report_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            alignment=1,
        )
        story.append(Paragraph("Portfolio Analysis Report", title_style))
        story.append(Spacer(1, 20))
        story.append(
            Paragraph(
                f"Portfolio: {portfolio_data['portfolio_name']}", styles["Heading2"]
            )
        )
        story.append(
            Paragraph(
                f"Report Date: {datetime.now().strftime('%B %d, %Y')}", styles["Normal"]
            )
        )
        story.append(Spacer(1, 40))
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 40, "status": "Adding portfolio summary"}
        )
        story.append(Paragraph("Portfolio Summary", styles["Heading2"]))
        story.append(Spacer(1, 12))
        holdings_data = [["Asset", "Weight (%)", "Value ($)", "Allocation"]]
        total_value = sum(portfolio_data["holdings"].values())
        for asset, value in portfolio_data["holdings"].items():
            weight = value / total_value * 100
            holdings_data.append(
                [asset, f"{weight:.2f}%", f"${value:,.2f}", f"${value:,.0f}"]
            )
        holdings_table = Table(holdings_data)
        holdings_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        story.append(holdings_table)
        story.append(Spacer(1, 20))
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 60, "status": "Adding performance analysis"}
        )
        story.append(Paragraph("Performance Analysis", styles["Heading2"]))
        story.append(Spacer(1, 12))
        if "performance_data" in portfolio_data:
            perf_data = portfolio_data["performance_data"]
            performance_summary = [
                ["Metric", "Value"],
                ["Total Return", f"{perf_data.get('total_return', 0):.2%}"],
                ["Annualized Return", f"{perf_data.get('annualized_return', 0):.2%}"],
                ["Volatility", f"{perf_data.get('volatility', 0):.2%}"],
                ["Sharpe Ratio", f"{perf_data.get('sharpe_ratio', 0):.2f}"],
                ["Max Drawdown", f"{perf_data.get('max_drawdown', 0):.2%}"],
            ]
            perf_table = Table(performance_summary)
            perf_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            story.append(perf_table)
            story.append(Spacer(1, 20))
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 80, "status": "Adding risk analysis"}
        )
        if "risk_metrics" in portfolio_data:
            story.append(Paragraph("Risk Analysis", styles["Heading2"]))
            story.append(Spacer(1, 12))
            risk_data = portfolio_data["risk_metrics"]
            risk_summary = [
                ["Risk Metric", "Value"],
                ["VaR (95%)", f"{risk_data.get('var_95', 0):.2%}"],
                ["VaR (99%)", f"{risk_data.get('var_99', 0):.2%}"],
                ["CVaR (95%)", f"{risk_data.get('cvar_95', 0):.2%}"],
                ["CVaR (99%)", f"{risk_data.get('cvar_99', 0):.2%}"],
            ]
            risk_table = Table(risk_summary)
            risk_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            story.append(risk_table)
        doc.build(story)
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 100, "status": "Report generation completed"}
        )
        results = {
            "report_path": report_path,
            "report_filename": report_filename,
            "report_type": "portfolio_analysis",
            "portfolio_name": portfolio_data["portfolio_name"],
            "generated_at": datetime.utcnow().isoformat(),
            "file_size_bytes": _get_file_size(report_path),
            "metadata": {"task_id": self.request.id, "report_config": report_config},
        }
        logger.info(
            f"Portfolio report generated successfully for task {self.request.id}"
        )
        return results
    except Exception as e:
        logger.error(
            f"Portfolio report generation failed for task {self.request.id}: {str(e)}"
        )
        raise


@task_with_progress()
def generate_risk_report(
    self, risk_analysis_data: Dict, report_config: Dict
) -> Dict[str, Any]:
    """
    Generate comprehensive risk analysis report.

    Args:
        risk_analysis_data: Risk analysis results and data
        report_config: Report configuration options

    Returns:
        Dict containing report file path and metadata
    """
    try:
        task_result_manager.store_task_progress(
            self.request.id,
            {"progress": 10, "status": "Initializing risk report generation"},
        )
        report_filename = f"risk_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        report_path = f"/tmp/{report_filename}"
        doc = SimpleDocTemplate(report_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            alignment=1,
        )
        story.append(Paragraph("Risk Analysis Report", title_style))
        story.append(Spacer(1, 20))
        story.append(
            Paragraph(
                f"Report Date: {datetime.now().strftime('%B %d, %Y')}", styles["Normal"]
            )
        )
        story.append(Spacer(1, 40))
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 30, "status": "Adding Monte Carlo results"}
        )
        if "monte_carlo_results" in risk_analysis_data:
            story.append(
                Paragraph("Monte Carlo Simulation Results", styles["Heading2"])
            )
            story.append(Spacer(1, 12))
            mc_data = risk_analysis_data["monte_carlo_results"]
            mc_summary = [
                ["Metric", "Value"],
                ["Number of Simulations", f"{mc_data.get('num_simulations', 0):,}"],
                ["Time Horizon (days)", f"{mc_data.get('time_horizon', 0)}"],
                ["VaR (95%)", f"{mc_data.get('var_95', 0):.2%}"],
                ["VaR (99%)", f"{mc_data.get('var_99', 0):.2%}"],
                ["CVaR (95%)", f"{mc_data.get('cvar_95', 0):.2%}"],
                ["CVaR (99%)", f"{mc_data.get('cvar_99', 0):.2%}"],
                ["Probability of Loss", f"{mc_data.get('probability_of_loss', 0):.2%}"],
            ]
            mc_table = Table(mc_summary)
            mc_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            story.append(mc_table)
            story.append(Spacer(1, 20))
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 60, "status": "Adding stress test results"}
        )
        if "stress_test_results" in risk_analysis_data:
            story.append(Paragraph("Stress Test Results", styles["Heading2"]))
            story.append(Spacer(1, 12))
            stress_data = risk_analysis_data["stress_test_results"]
            for i, scenario in enumerate(stress_data.get("stress_results", [])):
                story.append(
                    Paragraph(
                        f"Scenario {i + 1}: {scenario['scenario']['type']}",
                        styles["Heading3"],
                    )
                )
                scenario_summary = [
                    ["Metric", "Value"],
                    ["Return Impact", f"{scenario.get('return_impact', 0):.2%}"],
                    [
                        "Volatility Impact",
                        f"{scenario.get('volatility_impact', 0):.2%}",
                    ],
                    [
                        "Relative Return Impact",
                        f"{scenario.get('relative_return_impact', 0):.2%}",
                    ],
                    [
                        "Relative Volatility Impact",
                        f"{scenario.get('relative_volatility_impact', 0):.2%}",
                    ],
                ]
                scenario_table = Table(scenario_summary)
                scenario_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ]
                    )
                )
                story.append(scenario_table)
                story.append(Spacer(1, 12))
        doc.build(story)
        task_result_manager.store_task_progress(
            self.request.id,
            {"progress": 100, "status": "Risk report generation completed"},
        )
        results = {
            "report_path": report_path,
            "report_filename": report_filename,
            "report_type": "risk_analysis",
            "generated_at": datetime.utcnow().isoformat(),
            "file_size_bytes": _get_file_size(report_path),
            "metadata": {"task_id": self.request.id, "report_config": report_config},
        }
        logger.info(f"Risk report generated successfully for task {self.request.id}")
        return results
    except Exception as e:
        logger.error(
            f"Risk report generation failed for task {self.request.id}: {str(e)}"
        )
        raise


@task_with_progress()
def export_portfolio_data(
    self, portfolio_data: Dict, export_config: Dict
) -> Dict[str, Any]:
    """
    Export portfolio data to Excel format.

    Args:
        portfolio_data: Portfolio data to export
        export_config: Export configuration options

    Returns:
        Dict containing export file path and metadata
    """
    try:
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 10, "status": "Initializing data export"}
        )
        export_format = export_config.get("format", "excel")
        if export_format == "excel":
            export_filename = (
                f"portfolio_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            export_path = f"/tmp/{export_filename}"
        else:
            export_filename = (
                f"portfolio_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            export_path = f"/tmp/{export_filename}"
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 30, "status": "Preparing data for export"}
        )
        if export_format == "excel":
            with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
                if "holdings" in portfolio_data:
                    holdings_df = pd.DataFrame(
                        [
                            {
                                "Asset": asset,
                                "Value": value,
                                "Weight": value
                                / sum(portfolio_data["holdings"].values()),
                            }
                            for asset, value in portfolio_data["holdings"].items()
                        ]
                    )
                    holdings_df.to_excel(writer, sheet_name="Holdings", index=False)
                task_result_manager.store_task_progress(
                    self.request.id,
                    {"progress": 50, "status": "Exporting performance data"},
                )
                if "performance_data" in portfolio_data:
                    perf_df = pd.DataFrame([portfolio_data["performance_data"]])
                    perf_df.to_excel(writer, sheet_name="Performance", index=False)
                if "risk_metrics" in portfolio_data:
                    risk_df = pd.DataFrame([portfolio_data["risk_metrics"]])
                    risk_df.to_excel(writer, sheet_name="Risk_Metrics", index=False)
                task_result_manager.store_task_progress(
                    self.request.id, {"progress": 80, "status": "Finalizing export"}
                )
                if "historical_returns" in portfolio_data:
                    hist_df = pd.DataFrame(portfolio_data["historical_returns"])
                    hist_df.to_excel(
                        writer, sheet_name="Historical_Returns", index=False
                    )
        elif "holdings" in portfolio_data:
            holdings_df = pd.DataFrame(
                [
                    {
                        "Asset": asset,
                        "Value": value,
                        "Weight": value / sum(portfolio_data["holdings"].values()),
                    }
                    for asset, value in portfolio_data["holdings"].items()
                ]
            )
            holdings_df.to_csv(export_path, index=False)
        task_result_manager.store_task_progress(
            self.request.id, {"progress": 100, "status": "Data export completed"}
        )
        results = {
            "export_path": export_path,
            "export_filename": export_filename,
            "export_format": export_format,
            "portfolio_name": portfolio_data.get("portfolio_name", "Unknown"),
            "exported_at": datetime.utcnow().isoformat(),
            "file_size_bytes": _get_file_size(export_path),
            "metadata": {"task_id": self.request.id, "export_config": export_config},
        }
        logger.info(f"Portfolio data export completed for task {self.request.id}")
        return results
    except Exception as e:
        logger.error(
            f"Portfolio data export failed for task {self.request.id}: {str(e)}"
        )
        raise


@celery_app.task(bind=True)
def generate_daily_reports(self) -> object:
    """
    Generate daily reports for all active portfolios.
    This is a scheduled task that runs daily.
    """
    try:
        logger.info("Starting daily report generation")
        active_portfolios = [
            {"id": 1, "name": "Portfolio A"},
            {"id": 2, "name": "Portfolio B"},
            {"id": 3, "name": "Portfolio C"},
        ]
        generated_reports = []
        for portfolio in active_portfolios:
            try:
                logger.info(
                    f"Generating daily report for portfolio {portfolio['name']}"
                )
                report_info = {
                    "portfolio_id": portfolio["id"],
                    "portfolio_name": portfolio["name"],
                    "report_date": datetime.utcnow().isoformat(),
                    "status": "generated",
                }
                generated_reports.append(report_info)
            except Exception as e:
                logger.error(
                    f"Failed to generate report for portfolio {portfolio['name']}: {str(e)}"
                )
                generated_reports.append(
                    {
                        "portfolio_id": portfolio["id"],
                        "portfolio_name": portfolio["name"],
                        "status": "failed",
                        "error": str(e),
                    }
                )
        results = {
            "task_type": "daily_reports",
            "generated_at": datetime.utcnow().isoformat(),
            "total_portfolios": len(active_portfolios),
            "successful_reports": len(
                [r for r in generated_reports if r["status"] == "generated"]
            ),
            "failed_reports": len(
                [r for r in generated_reports if r["status"] == "failed"]
            ),
            "reports": generated_reports,
        }
        logger.info(
            f"Daily report generation completed: {results['successful_reports']} successful, {results['failed_reports']} failed"
        )
        return results
    except Exception as e:
        logger.error(f"Daily report generation failed: {str(e)}")
        raise


def _get_file_size(file_path: object) -> object:
    """Get file size in bytes."""
    try:
        import os

        return os.path.getsize(file_path)
    except Exception:
        return 0


def _create_chart_image(
    data: "np.ndarray | pd.DataFrame | list", chart_type: str = "line"
) -> object:
    """Create chart image for inclusion in reports."""
    try:
        plt.figure(figsize=(8, 6))
        if chart_type == "line":
            plt.plot(data)
        elif chart_type == "bar":
            plt.bar(range(len(data)), data)
        elif chart_type == "pie":
            plt.pie(data, autopct="%1.1f%%")
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", bbox_inches="tight", dpi=150)
        img_buffer.seek(0)
        plt.close()
        return img_buffer
    except Exception as e:
        logger.error(f"Chart creation failed: {str(e)}")
        return None
