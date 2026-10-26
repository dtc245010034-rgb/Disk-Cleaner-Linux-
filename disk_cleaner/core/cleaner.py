from __future__ import annotations

from . import logging_, safety
from .models import Category, CleanResult, Item


def run_cleanup(selection: list[tuple[Category, list[Item]]], dry_run: bool,
                root_runner=None, log_path=None) -> dict[str, CleanResult]:
    results: dict[str, CleanResult] = {}
    pending: list[tuple[Category, list[Item]]] = []
    for cat, items in selection:
        if not items:
            continue
        if cat.needs_root:
            if dry_run:
                results[cat.id] = CleanResult(freed_bytes=sum(i.size_bytes for i in items),
                                              skipped=["dry-run"])
            else:
                pending.append((cat, items))
            continue
        try:
            results[cat.id] = cat.clean(items, dry_run)
        except safety.SafetyError as exc:
            results[cat.id] = CleanResult(errors=[f"Bị chặn bởi safety: {exc}"])
        except Exception as exc:
            results[cat.id] = CleanResult(errors=[f"{type(exc).__name__}: {exc}"])
    if pending:
        results.update(_run_root(pending, root_runner))
    for cid, res in results.items():
        logging_.record(cid, res, dry_run, log_path)
    return results


def _run_root(pending, runner) -> dict[str, CleanResult]:
    out: dict[str, CleanResult] = {}
    if runner is None:
        for cat, _ in pending:
            out[cat.id] = CleanResult(skipped=["Không có công cụ cấp quyền root"])
        return out
    flat: list[list[str]] = []
    spans = []
    for cat, items in pending:
        ops = cat.root_ops(items)
        spans.append((cat, items, len(flat), len(flat) + len(ops)))
        flat.extend(ops)
    answers = runner.run(flat) if flat else []
    for cat, items, a, b in spans:
        chunk = answers[a:b]
        if any(x.get("cancelled") for x in chunk):
            out[cat.id] = CleanResult(skipped=["Đã huỷ xác thực quyền root"])
            continue
        errors = [x.get("error", "lỗi không rõ") for x in chunk if not x.get("ok")]
        if len(chunk) < b - a:
            errors.append("Thiếu kết quả từ root helper")
        freed = 0 if errors else sum(i.size_bytes for i in items)
        out[cat.id] = CleanResult(freed_bytes=freed, errors=errors)
    return out
