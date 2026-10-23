import os
import py_compile
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
error_count = 0
checked_count = 0

print(f"Scanning directory: {base_dir}")
for root, dirs, files in os.walk(base_dir):
    rel_root = os.path.relpath(root, base_dir)
    if ".git" in root or ".venv" in root or "__pycache__" in root or "Guruh uchun bot" in rel_root.split(os.sep):
        continue
    for file in sorted(files):
        if file.endswith(".py") and file != "check_project.py":
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, base_dir)
            checked_count += 1
            try:
                py_compile.compile(full_path, doraise=True)
                print(f"  [OK] {rel_path}")
            except Exception as e:
                print(f"  [FAILED] {rel_path}: {e}")
                error_count += 1

print("\n" + "=" * 50)
print(f"Results: {checked_count} files checked, {error_count} errors found.")
if error_count == 0:
    print("ALL PYTHON FILES PASSED SYNTAX CHECK 100%!")
else:
    print("ERRORS DETECTED!")
    sys.exit(1)
