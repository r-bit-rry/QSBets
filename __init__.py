"""
QSBets - Quantitative Stock Betting System
"""
import os
import sys

# Make sure the package directory is in path so modules can be imported
package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.append(package_dir)
