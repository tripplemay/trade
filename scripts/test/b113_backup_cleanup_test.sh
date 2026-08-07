#!/usr/bin/env bash
# B113 F001 (OPS1) — workbench-backup cleanup_stage 回归测试。
#
# 从真实脚本提取 cleanup_stage 函数（不改产品逻辑拷贝），验证：
#   1. 正常删除本 run 暂存文件（精确名）；
#   2. 通配位被「不可删对象」（目录）占位时不报错退出（事故形态：他主文件权限失败）；
#   3. 不误删目录/他主对象；
#   4. 空通配（无可清文件）也返回 0。
#
# 用法：bash scripts/test/b113_backup_cleanup_test.sh（退出码 0 = 全过）

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/workbench/deploy/backup/workbench-backup.sh"

# 提取真实函数定义（cleanup_stage() { ... } 到收尾 }）。
FUNC_TEXT="$(sed -n '/^cleanup_stage()/,/^}/p' "${SCRIPT}")"
if [[ -z "${FUNC_TEXT}" ]]; then
  echo "FAIL: cleanup_stage not found in ${SCRIPT}" >&2
  exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

failures=0
check() { # check <描述> <退出码>
  if [[ "$2" -eq 0 ]]; then
    echo "PASS: $1"
  else
    echo "FAIL: $1" >&2
    failures=$((failures + 1))
  fi
}

# --- 用例 1：正常清理删除本 run 暂存文件（精确名）且返回 0 ---
(
  set -e
  eval "${FUNC_TEXT}"
  STAGE_FILE="${WORKDIR}/stage_a.db"
  STAGE_GZ="${WORKDIR}/stage_a.db.gz"
  touch "${STAGE_FILE}" "${STAGE_GZ}"
  cleanup_stage
  [[ ! -e "${STAGE_FILE}" && ! -e "${STAGE_GZ}" ]]
)
check "清理删除本 run 暂存文件且返回 0" "$?"

# --- 用例 2+4：空通配（无可清文件）也返回 0 ---
(
  set -e
  eval "${FUNC_TEXT}"
  STAGE_FILE="${WORKDIR}/nope_a.db"
  STAGE_GZ="${WORKDIR}/nope_a.db.gz"
  cleanup_stage
)
check "空通配返回 0" "$?"

# --- 用例 3：通配位被不可删对象占位（目录模拟他主文件）时不报错、不误删 ---
# /tmp 真实事故的替代形态：rm -f 对目录恒失败（=他主文件在 sticky /tmp 的形态）。
(
  set -e
  eval "${FUNC_TEXT}"
  cd /tmp
  STAGE_FILE="/tmp/wb-b113test-$$.db"
  STAGE_GZ="${STAGE_FILE}.gz"
  touch "${STAGE_FILE}" "${STAGE_GZ}"
  mkdir -p /tmp/wb-b113test-foreign.db
  cleanup_stage
  result=$?
  [[ ! -e "${STAGE_FILE}" && -d /tmp/wb-b113test-foreign.db ]]
  within=$?
  rmdir /tmp/wb-b113test-foreign.db
  [[ $result -eq 0 && $within -eq 0 ]]
)
check "通配位被不可删对象占位时清理返回 0 且不误删" "$?"

if [[ "${failures}" -gt 0 ]]; then
  echo "FAILED: ${failures} 个用例未过" >&2
  exit 1
fi
echo "全部用例通过"
