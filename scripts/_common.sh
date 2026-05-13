#!/bin/bash

resolve_python_bin() {
  if [ -n "${PYTHON_BIN:-}" ] && [ -x "$PYTHON_BIN" ]; then
    echo "$PYTHON_BIN"
    return 0
  fi

  if [ -n "${ROOT:-}" ] && [ -x "$ROOT/.venv/bin/python" ]; then
    echo "$ROOT/.venv/bin/python"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  return 1
}


resolve_cplex_cmd() {
  if [ -n "${CPLEX_CMD:-}" ] && [ -x "$CPLEX_CMD" ]; then
    echo "$CPLEX_CMD"
    return 0
  fi

  if [ -n "${CPLEX_BIN:-}" ] && [ -x "$CPLEX_BIN/cplex" ]; then
    echo "$CPLEX_BIN/cplex"
    return 0
  fi

  if [ -n "${CPLEX_STUDIO_DIR:-}" ]; then
    for candidate in \
      "$CPLEX_STUDIO_DIR/cplex/bin/arm64_osx/cplex" \
      "$CPLEX_STUDIO_DIR/cplex/bin/x86-64_osx/cplex" \
      "$CPLEX_STUDIO_DIR/cplex/bin/x86-64_linux/cplex"
    do
      if [ -x "$candidate" ]; then
        echo "$candidate"
        return 0
      fi
    done
  fi

  for candidate in \
    "/Users/admin/Applications/CPLEX_Studio2212/cplex/bin/arm64_osx/cplex" \
    "/Applications/CPLEX_Studio2212/cplex/bin/arm64_osx/cplex" \
    "/Applications/CPLEX_Studio2212/cplex/bin/x86-64_osx/cplex" \
    "/Applications/CPLEX_Studio2211/cplex/bin/arm64_osx/cplex" \
    "/Applications/CPLEX_Studio2211/cplex/bin/x86-64_osx/cplex" \
    "/home/hind.bahir/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex" \
    "/opt/ibm/ILOG/CPLEX_Studio2212/cplex/bin/x86-64_linux/cplex" \
    "/opt/ibm/ILOG/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex"
  do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  if command -v cplex >/dev/null 2>&1; then
    command -v cplex
    return 0
  fi

  return 1
}


require_screen() {
  if ! command -v screen >/dev/null 2>&1; then
    echo "GNU screen is required but was not found on PATH."
    return 1
  fi
}
