#!/usr/bin/env python3
"""Invoke the shared JVM generator through the same Gradle task as CI.

No generated source is authored by this wrapper. Install/publish the updated
pub.tool.General generator first; see specs/GENERATED-SOURCES.md.
"""
from pathlib import Path
import os
import subprocess
import sys

repository = Path(__file__).resolve().parents[1]
command = ["bash", str(repository / "gradlew"), "--no-daemon", "generateModustroSchemaBindings"]
if len(sys.argv) > 1:
    raise SystemExit("This wrapper takes no arguments; Gradle always regenerates/checks its owned files.")
subprocess.run(command, cwd=repository, env=os.environ, check=True)
