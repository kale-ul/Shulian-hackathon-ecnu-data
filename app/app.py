# -*- coding: utf-8 -*-
"""Compatibility entry point for older shortcuts.

The maintained Web console now lives in ``app/console.py``. Keep this file
working so `streamlit run app/app.py` resolves to the same product shell.
"""
from app.console import main


if __name__ == "__main__":
    main()
