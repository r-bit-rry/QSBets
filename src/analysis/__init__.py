import os
import sys

# Make 'src' directory importable without src prefix
package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.append(package_dir)
