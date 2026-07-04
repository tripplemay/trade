"""B080 F003 — the re-validation kernel is parameter-FROZEN (spec §2 F003 / §3).

"Re-validation is not re-training": the frozen kernel must expose NO way to inject a
strategy parameter — it constructs ``CnAttackParameters`` only from module-level
FROZEN constants. This guard fails if a tunable knob ever appears on the public
entrypoint's signature (the exact "inject params → reject" acceptance).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from workbench_api.monitoring import reverify_kernel

# Any of these appearing as a public-entrypoint argument = a param-injection path.
_TUNABLE_NAMES = frozenset(
    {
        "params",
        "parameters",
        "factor_variant",
        "weighting_scheme",
        "top_n",
        "config",
        "exit_rule",
        "size_tilt_weight",
    }
)


def test_run_frozen_revalidation_exposes_no_tunable_param() -> None:
    sig = inspect.signature(reverify_kernel.run_frozen_revalidation)
    assert set(sig.parameters) & _TUNABLE_NAMES == set(), (
        f"frozen re-validation entrypoint leaked a tunable param: {set(sig.parameters)}"
    )
    # Only the data-root + optional end-date are accepted.
    assert set(sig.parameters) == {"data_root", "end"}


def test_frozen_params_built_only_from_module_constants() -> None:
    # _frozen_params must reference the FROZEN_* module constants and pass NO
    # caller-derived value into CnAttackParameters (AST check — no argument comes
    # from a function parameter, since _frozen_params takes none).
    src = inspect.getsource(reverify_kernel._frozen_params)
    tree = ast.parse(src)
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)
    assert fn.args.args == []  # takes no arguments → cannot be handed a tunable value
    # The only CnAttackParameters(...) call uses the imported FROZEN factor/weighting.
    calls = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "CnAttackParameters"
    ]
    assert len(calls) == 1
    kw = {k.arg for k in calls[0].keywords}
    assert kw == {"factor_variant", "weighting_scheme"}


def test_kernel_module_has_no_validated_true() -> None:
    # Belt-and-suspenders: the frozen kernel never sets an OOS card validated=True
    # (that only the manual un-watch batch may do — spec §3 invariant ②).
    src = Path(reverify_kernel.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "validated":
            assert not (isinstance(node.value, ast.Constant) and node.value.value is True)
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "validated":
                    assert not (
                        isinstance(node.value, ast.Constant) and node.value.value is True
                    )
