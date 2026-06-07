"""Athena tools — capabilities the orchestrator can delegate to."""
from athena.tools.apps_tool import AppTool, register_apps
from athena.tools.base import Tool, ToolRegistry
from athena.tools.report_tool import (
    PortfolioReportTool,
    build_portfolio_report,
    register_report,
)
from athena.tools.saoirse_tool import register_saoirse
from athena.tools.sionnach_tool import (
    SionnachFleetTool,
    SionnachScanTool,
    register_sionnach,
)


def default_registry() -> ToolRegistry:
    """A registry with every available built-in tool wired in."""
    reg = ToolRegistry()
    register_sionnach(reg)
    register_report(reg)
    register_apps(reg)
    register_saoirse(reg)
    return reg


__all__ = [
    "Tool",
    "ToolRegistry",
    "SionnachScanTool",
    "SionnachFleetTool",
    "register_sionnach",
    "PortfolioReportTool",
    "build_portfolio_report",
    "register_report",
    "AppTool",
    "register_apps",
    "register_saoirse",
    "default_registry",
]
