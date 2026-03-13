#!/usr/bin/env python3
""" [-GPL2.0 license-] """
import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, NoReturn, Optional, Tuple, Union
compiled = ""
builtins_emitted = False
no_runtime = False
no_main = False
def _bhumi_get_source_lines():
    try:
        with open(compiled, encoding="utf-8", errors="ignore") as f:
            return f.read().splitlines()
    except OSError:
        return []
def _visual_col(
    line: str, col: int, tabsize: int = 4
) -> int:
    if col <= 1:
        return 0
    visual = 0
    for ch in line[: col - 1]:
        if ch == "\t":
            visual += tabsize - (visual % tabsize)
        else:
            visual += 1
    return visual
def bhumi_report_error(
    line: int | None, col: int | None, msg: str, length: int = 1
) -> NoReturn:
    if "[Crawl-Checker]-[ERR]" in str(msg):
        print(str(msg))
    else:
        print("[BhumiCompiler] Error: " + str(msg))
    src_lines = _bhumi_get_source_lines()
    if line is not None and 1 <= line <= len(src_lines):
        raw_line = src_lines[line - 1]
        expanded = raw_line.expandtabs(4)
        prefix = f"{line}| "
        print(prefix + expanded)
        if col is not None and col > 0:
            col0 = _visual_col(raw_line, col)
        else:
            col0 = 0
        pointer = " " * len(prefix) + " " * col0 + "^"
        if length and length > 1:
            pointer += "~" * (length - 1)
        print(pointer)
    sys.exit(1)
def llvm_to_lang(llvm_t: str) -> str:
    for high, low in type_map.items():
        if low == llvm_t:
            return high
    if llvm_t.startswith("%struct.") and llvm_t.endswith("*"):
        return llvm_t[len("%struct.") : -1] + "*"
    if llvm_t.startswith("%struct.") and not llvm_t.endswith("*"):
        return llvm_t[len("%struct.") :]
    if llvm_t.startswith("%enum.") and llvm_t.endswith("*"):
        return llvm_t[len("%enum.") : -1] + "*"
    if llvm_t.startswith("%enum.") and not llvm_t.endswith("*"):
        return llvm_t[len("%enum.") :]
    if m := re.fullmatch(r"i(\d+)", llvm_t):
        bits = int(m.group(1))
        return "int" if bits == 64 else f"int{bits}"
    if llvm_t == "double":
        return "float"
    if llvm_t == "float":
        return "float32"
    if llvm_t.endswith("*"):
        base = llvm_t.rstrip("*")
        if base.startswith("%struct."):
            return base[len("%struct.") :] + "*"
        if base.startswith("%enum."):
            return base[len("%enum.") :] + "*"
        return "void*"
    return llvm_t
TYPE_TOKENS = {
    "IDENT",   "INT",    "INT8",   "INT16",  "INT32",  "INT64",
    "FLOAT",   "FLOAT32",
    "STRING",  "CHAR",   "BOOL",   "VOID",
    "UINT",    "UINT8",  "UINT16", "UINT32", "UINT64",
    "HASH",
}
CAST_TYPE_TOKENS = {
    "INT",     "INT8",   "INT16",  "INT32",  "INT64",
    "FLOAT",   "FLOAT32",
    "STRING",  "CHAR",   "BOOL",   "VOID",
    "UINT",    "UINT8",  "UINT16", "UINT32", "UINT64",
}
@dataclass
class Token:
    kind: str
    value: str
    line: int
    col: int
KEYWORDS = {
    "fn",        "if",        "else",      "while",     "return",    "import",
    "pub",       "priv",      "prot",      "extern",
    "int",       "int8",      "int16",     "int32",     "int64",
    "uint",      "uint8",     "uint16",    "uint32",    "uint64",
    "float",     "float32",
    "bool",      "char",      "string",    "void",
    "true",      "false",     "null",
    "struct",    "enum",      "match",
    "async",     "await",     "vasync",    "vawait",
    "continue",  "break",
    "nomd",      "pin",       "crumble",
    "nown",
    "take",      "except",
    "typeswitch","typecase", "fallback",
}
SINGLE_CHARS = {
    "(": "LPAREN",   ")": "RPAREN",
    "{": "LBRACE",   "}": "RBRACE",
    "[": "LBRACKET", "]": "RBRACKET",
    ",": "COMMA",    ";": "SEMI",     ".": "DOT",      ":": "COLON",
    "=": "EQUAL",
    "+": "PLUS",     "-": "MINUS",    "*": "STAR",     "/": "SLASH",
    "%": "PERCENT",
    "<": "LT",       ">": "GT",
    "!": "BANG",     "?": "QUESTION",
    "&": "AMP",      "|": "PIPE",     "^": "CARET",
    "#": "HASH",
}
MULTI_CHARS = {
    "==": "EQEQ",      "!=": "NEQ",
    "<=": "LE",        ">=": "GE",
    "<<=": "LSHIFTEQ", ">>=": "RSHIFTEQ",
    "<<": "LSHIFT",    ">>": "RSHIFT",
    "+=": "PLUSEQ",    "-=": "MINUSEQ",
    "*=": "STAREQ",    "/=": "SLASHEQ",
    "%=": "PERCENTEQ",
    "&=": "ANDEQ",     "|=": "OREQ",   "^=": "XOREQ",
    "&&": "AND",       "||": "OR",
    "->": "ARROW",
    "~": "TILDE",
}
class SymbolTable:
    def __init__(self):
        self.scopes: List[Dict[str, Tuple[str, str]]] = [{}]
    def push(self):
        self.scopes.append({})
    def pop(self):
        self.scopes.pop()
    def declare(self, name: str, llvm_type: str, ir_name: str):
        self.scopes[-1][name] = (llvm_type, ir_name)
    def lookup(self, name: str) -> Optional[Tuple[str, str]]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None
    def current(self) -> Dict[str, Tuple[str, str]]:
        return self.scopes[-1]
    def clear(self):
        self.scopes = [{}]
class TypeEnv:
    def __init__(self):
        self.scopes: List[Dict[str, str]] = [{}]
    def push(self):
        self.scopes.append({})
    def pop(self):
        self.scopes.pop()
    def declare(self, name: str, typ: str):
        self.scopes[-1][name] = typ
    def lookup(self, name: str) -> Optional[str]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None
def llvm_ty_of(typ: str) -> str:
    if typ == "#":
        bhumi_report_error(
            None,
            None,
            "Internal compiler error: encountered placeholder '#' in llvm_ty_of, missing monomorphisation",
        )
    _generic_m = re.fullmatch(r"([A-Za-z_]\w*)<(.+)>(\*?)", typ)
    if _generic_m:
        base_g, inner_g, ptr_g = _generic_m.group(1), _generic_m.group(2), _generic_m.group(3)
        mono_g = ensure_monomorph_for_enum(base_g, [inner_g]) if base_g in globals().get("original_enum_defs", {}) else base_g + "__mono__" + inner_g
        typ = mono_g + ptr_g
    if re.fullmatch(r"i\d+(\*)?", typ):
        return typ
    if typ == "void":
        return "void"
    if typ == "void*":
        return "i8*"
    if typ.endswith("*"):
        base = typ[:-1]
        if base == "void":
            return "i8*"
        if base.startswith("%"):
            return base + "*"
        if base in enum_variant_map and any(
            p is not None for _, p in enum_variant_map[base]
        ):
            return f"%enum.{base}*"
        if base in enum_variant_map:
            mapped = type_map.get(base)
            if mapped == "void":
                return "i8*"
            if mapped:
                return mapped + "*"
            return f"%struct.{base}*"
        if base in type_map:
            mapped = type_map[base]
            if mapped == "void":
                return "i8*"
            return mapped + "*"
        return llvm_ty_of(base) + "*"
    if typ in enum_variant_map:
        if any(p is not None for _, p in enum_variant_map[typ]):
            return f"%enum.{typ}*"
        return type_map.get(typ, type_map.get("int", "i64"))
    if typ in type_map:
        if type_map[typ] == "void":
            return "void"
        return type_map[typ]
    _fixed_arr_m = re.fullmatch(r"([A-Za-z_]\w*\**)\[(\d+)]", typ)
    if _fixed_arr_m:
        elem_base, count = _fixed_arr_m.group(1), _fixed_arr_m.group(2)
        elem_llvm = llvm_ty_of(elem_base)
        return f"[{count} x {elem_llvm}]*"
    _unsized_arr_m = re.fullmatch(r"([A-Za-z_]\w*\**)\[]", typ)
    if _unsized_arr_m:
        elem_base = _unsized_arr_m.group(1)
        elem_llvm = llvm_ty_of(elem_base)
        return f"{elem_llvm}*"
    if typ.startswith("%"):
        return typ
    return f"%struct.{typ}"
def zero_const_for_llvm(llvm_t: str) -> str:
    if "*" in llvm_t or llvm_t.strip().startswith("%"):
        return "null"
    return "0"
def demangle_mononame(mononame: str) -> str:
    return mono_map.get(mononame, mononame)
def ensure_monomorph_for_call(
    base_name: str, actual_types: List[str], expected_ret: Optional[str] = None
) -> str:
    mangled_parts = [mangle_type(a) for a in actual_types]
    if expected_ret is not None:
        mangled_parts.append(mangle_type(expected_ret))
    if mangled_parts:
        mononame = f"{base_name}__mono__" + "_".join(mangled_parts)
    else:
        mononame = base_name
    if mononame not in func_table:
        _candidate = _func_name_map.get(base_name)
        base_fn = _candidate if _candidate and (_candidate.type_params or _candidate.ret_type == "#") else None
        if base_fn is None:
            bhumi_report_error(
                None, None, f"Attempted to monomorph unknown function '{base_name}'"
            )
        new_ret = base_fn.ret_type
        if getattr(base_fn, "type_params", None) and new_ret in base_fn.type_params:
            idx = base_fn.type_params.index(new_ret)
            new_ret = actual_types[idx]
        if new_ret == "#" and expected_ret is not None:
            new_ret = expected_ret
        if new_ret == "#":
            bhumi_report_error(
                None,
                None,
                f"Cannot monomorph '{base_name}' without concrete return type",
            )
        if getattr(base_fn, "is_async", False):
            struct_ty = f"%async.{mononame}"
            func_table[f"{mononame}_init"] = f"{struct_ty}*"
            func_table[f"{mononame}_resume"] = "i1"
            func_table.setdefault(f"{base_name}_init", func_table[f"{mononame}_init"])
            func_table.setdefault(
                f"{base_name}_resume", func_table[f"{mononame}_resume"]
            )
    return mononame
def ensure_monomorph_for_enum(base_name: str, actual_types: List[str]) -> str:
    mangled_parts = [mangle_type(a) for a in actual_types]
    if mangled_parts:
        mononame = f"{base_name}__mono__" + "_".join(mangled_parts)
    else:
        mononame = base_name
    if mononame in enum_variant_map:
        return mononame
    template = globals().get("original_enum_defs", {}).get(base_name)
    if template is None:
        bhumi_report_error(None, None, f"Attempted to monomorph unknown enum '{base_name}'")
    if len(template.type_params) != len(actual_types):
        bhumi_report_error(None, None, f"Enum '{base_name}' expects {len(template.type_params)} type parameters, got {len(actual_types)}")
    subst: Dict[str, str] = {}
    for tp_name, actual in zip(template.type_params, actual_types):
        subst[tp_name] = actual
    def _subst_t(typ: Optional[str]) -> Optional[str]:
        if typ is None:
            return None
        if typ in subst:
            return subst[typ]
        for k, v in subst.items():
            if typ == k:
                return v
            if typ.startswith(k) and typ[len(k):] in ("*", "[]"):
                return v + typ[len(k):]
        t = typ
        for k, v in subst.items():
            t = re.sub(r'\b' + re.escape(k) + r'\b', v, t)
        return t
    new_variants: List[Tuple[str, Optional[str]]] = []
    for v in template.variants:
        payload = _subst_t(v.typ)
        new_variants.append((v.name, payload))
    unresolved = [
        (vname, payload)
        for vname, payload in new_variants
        if payload is not None and any(
            re.search(r'\b' + re.escape(tp) + r'\b', payload)
            for tp in template.type_params
        )
    ]
    if unresolved:
        bad = ", ".join(f"{vn}:{p}" for vn, p in unresolved)
        bhumi_report_error(
            None, None,
            f"Enum '{base_name}' monomorphisation with {actual_types} left unresolved "
            f"type parameters in variants: {bad}. "
            f"Make sure all type arguments are concrete types, not type-param names."
        )
    enum_variant_map[mononame] = new_variants
    if base_name in type_map:
        type_map[mononame] = type_map[base_name]
    for vname, payload in new_variants:
        gm = globals().get("variant_map_global")
        if gm is None:
            gm = {}
            globals()["variant_map_global"] = gm
        gm.setdefault(vname, []).append((mononame, payload))
    return mononame
def ensure_monomorph_call(
    call_expr: "Call", out: List[str], expected_ret: Optional[str] = None
) -> str:
    base_fn = _func_name_map.get(call_expr.name)
    if base_fn and base_fn.ret_type == "#":
        if expected_ret is None:
            bhumi_report_error(
                None,
                None,
                f"Cannot infer return type for '{call_expr.name}', no expected type provided",
            )
    if not base_fn:
        return call_expr.name
    has_type_params = bool(getattr(base_fn, "type_params", None))
    if not has_type_params and base_fn.ret_type != "#":
        return call_expr.name
    if has_type_params and not call_expr.args:
        bhumi_report_error(
            None,
            None,
            f"Generic function '{call_expr.name}' called with no arguments to infer type parameters",
        )
    arg_types = [infer_type(a) for a in (call_expr.args or [])]
    actuals: List[str] = []
    if has_type_params:
        for tp in base_fn.type_params:
            found = None
            for param_idx, (param_typ, _) in enumerate(base_fn.params):
                if param_typ == tp or tp in param_typ:
                    if param_idx < len(arg_types):
                        found = arg_types[param_idx]
                        break
            if found is None and base_fn.ret_type == tp and len(arg_types) > 0:
                found = arg_types[0]
            if found is None:
                bhumi_report_error(
                    None,
                    None,
                    f"Cannot infer type parameter '{tp}' for generic function '{call_expr.name}'",
                )
            actuals.append(found)
    mangled_parts = [mangle_type(a) for a in actuals]
    if base_fn.ret_type == "#" and expected_ret is not None:
        mangled_parts.append(mangle_type(expected_ret))
    if not mangled_parts and base_fn.ret_type != "#":
        return call_expr.name
    if mangled_parts:
        mononame = f"{call_expr.name}__mono__" + "_".join(mangled_parts)
    else:
        mononame = call_expr.name
    mono_map[mononame] = base_fn.name
    if mononame in func_table:
        return mononame
    subst_map: Dict[str, str] = {}
    if has_type_params:
        for (param_type, _), actual in zip(base_fn.params, arg_types):
            for tp in base_fn.type_params:
                if param_type == tp:
                    subst_map[tp] = actual
                elif param_type.startswith(tp) and param_type[len(tp) :] in ("*", "[]"):
                    subst_map[tp] = actual
    if base_fn.ret_type == "#" and expected_ret is not None:
        subst_map["#"] = expected_ret
    def _subst_type(t: Optional[str], subst: Dict[str, str]) -> Optional[str]:
        if t is None:
            return None
        for k, v in subst.items():
            if t == k:
                return v
            if t.startswith(k) and t[len(k) :] in ("*", "[]"):
                return v + t[len(k) :]
        return t
    def replace_in_expr(e: Expr):
        if e is None:
            return None
        if isinstance(e, Var):
            return Var(e.name)
        if isinstance(e, (IntLit, FloatLit, BoolLit, StrLit, CharLit, NullLit)):
            return e
        if isinstance(e, Call):
            return Call(e.name, [replace_in_expr(a) for a in (e.args or [])])
        if isinstance(e, UnaryOp):
            return UnaryOp(e.op, replace_in_expr(e.expr))
        if isinstance(e, BinOp):
            return BinOp(e.op, replace_in_expr(e.left), replace_in_expr(e.right))
        if isinstance(e, FieldAccess):
            return FieldAccess(replace_in_expr(e.base), e.field)
        if isinstance(e, Index):
            return Index(replace_in_expr(e.array), replace_in_expr(e.index))
        if isinstance(e, StructInit):
            return StructInit(
                e.name, [(fname, replace_in_expr(fexpr)) for fname, fexpr in e.fields]
            )
        if isinstance(e, AwaitExpr):
            return AwaitExpr(replace_in_expr(e.expr))
        if isinstance(e, VAwaitExpr):
            return VAwaitExpr(replace_in_expr(e.expr))
        if isinstance(e, UnaryDeref):
            return UnaryDeref(replace_in_expr(e.ptr))
        if isinstance(e, AddressOf):
            return AddressOf(replace_in_expr(e.expr))
        if isinstance(e, Cast):
            return Cast(_subst_type(e.typ, subst_map), replace_in_expr(e.expr))
        if isinstance(e, Ternary):
            return Ternary(
                replace_in_expr(e.cond),
                replace_in_expr(e.then_expr),
                replace_in_expr(e.else_expr),
            )
        if isinstance(e, TypeofExpr):
            if isinstance(e.expr, CallerType):
                concrete = subst_map.get("#")
                if concrete is not None:
                    return StrLit(concrete)
                return TypeofExpr(CallerType())
            return TypeofExpr(replace_in_expr(e.expr))
        return e
    def transform_stmt_list(stmt_list):
        out = []
        for st in stmt_list or []:
            r = replace_in_stmt(st)
            if r is None:
                continue
            if isinstance(r, list):
                out.extend(r)
            else:
                out.append(r)
        return out
    def replace_in_stmt(s: Stmt):
        if s is None:
            return None
        if isinstance(s, VarDecl):
            return VarDecl(
                s.access,
                _subst_type(s.typ, subst_map),
                s.name,
                replace_in_expr(s.expr) if s.expr else None,
                s.nomd,
            )
        if isinstance(s, Assign):
            name = s.name
            if isinstance(name, UnaryDeref):
                return Assign(
                    UnaryDeref(replace_in_expr(name.ptr)), replace_in_expr(s.expr)
                )
            else:
                return Assign(name, replace_in_expr(s.expr))
        if isinstance(s, IndexAssign):
            return IndexAssign(
                s.array, replace_in_expr(s.index), replace_in_expr(s.value)
            )
        if isinstance(s, ExprStmt):
            return ExprStmt(replace_in_expr(s.expr))
        if isinstance(s, IfStmt):
            cond0 = replace_in_expr(s.cond)
            then_body0 = transform_stmt_list(s.then_body)
            else_body0 = None
            if s.else_body:
                if isinstance(s.else_body, IfStmt):
                    else_body0 = replace_in_stmt(s.else_body)
                else:
                    else_body0 = transform_stmt_list(s.else_body)
            return IfStmt(cond0, then_body0, else_body0)
        if isinstance(s, WhileStmt):
            return WhileStmt(replace_in_expr(s.cond), transform_stmt_list(s.body))
        if isinstance(s, ReturnStmt):
            return ReturnStmt(replace_in_expr(s.expr) if s.expr else None)
        if isinstance(s, Match):
            new_expr0 = replace_in_expr(s.expr)
            new_cases = []
            for case in s.cases:
                new_body0 = transform_stmt_list(case.body)
                new_cases.append(MatchCase(
                    case.variant, case.binding, new_body0,
                    nested_pattern=case.nested_pattern
                ))
            return Match(new_expr0, new_cases)
        if isinstance(s, TypeSwitch):
            subj = s.subject
            actual = subst_map.get(subj)
            if actual is None:
                new_cases = []
                for case in s.cases:
                    new_body = transform_stmt_list(case.body)
                    new_cases.append(
                        TypeSwitchCase(_subst_type(case.typ, subst_map), new_body)
                    )
                new_fb = None
                if s.fallback:
                    new_fb = transform_stmt_list(s.fallback)
                return TypeSwitch(subj, new_cases, new_fb)
            processed_cases = []
            for case in s.cases:
                ct = _subst_type(case.typ, subst_map)
                processed_cases.append((ct, case.body))
            for ct, body in processed_cases:
                if ct == actual:
                    return transform_stmt_list(body)
            if actual == "int":
                for ct, body in processed_cases:
                    if isinstance(ct, str) and ct.startswith("int"):
                        return transform_stmt_list(body)
            for ct, body in processed_cases:
                if unify_types(ct, actual) is not None:
                    return transform_stmt_list(body)
            if s.fallback is not None:
                return transform_stmt_list(s.fallback)
            return []
        return s
    new_params = [(_subst_type(p[0], subst_map), p[1]) for p in base_fn.params]
    new_ret = _subst_type(base_fn.ret_type, subst_map)
    new_body = []
    if base_fn.body:
        for stmt in base_fn.body:
            r = replace_in_stmt(stmt)
            if r is None:
                continue
            if isinstance(r, list):
                new_body.extend(r)
            else:
                new_body.append(r)
    new_fn = Func(
        base_fn.access,
        mononame,
        [],
        new_params,
        new_ret,
        new_body,
        base_fn.is_extern,
        base_fn.is_async,
    )
    new_fn.take_params = set(getattr(base_fn, "take_params", None) or set())
    all_funcs.append(new_fn)
    _func_name_map[new_fn.name] = new_fn
    if new_ret == "#":
        bhumi_report_error(
            None,
            None,
            f"Cannot monomorph '{call_expr.name}' without concrete return type",
        )
    func_table[mononame] = llvm_ty_of(new_ret)
    generated_mono[mononame] = True
    def all_paths_return(stmts):
        if not stmts:
            return False
        i = 0
        while i < len(stmts):
            st = stmts[i]
            if isinstance(st, ReturnStmt):
                return True
            if isinstance(st, IfStmt):
                then_body = st.then_body or []
                else_body = []
                if st.else_body:
                    if isinstance(st.else_body, IfStmt):
                        else_body = [st.else_body]
                    else:
                        else_body = st.else_body
                then_ret = all_paths_return(then_body)
                else_ret = all_paths_return(else_body) if else_body else False
                if then_ret and else_ret:
                    return True
                i += 1
                continue
            i += 1
        return False
    if new_fn.ret_type is not None and new_fn.ret_type != "void":
        if not all_paths_return(new_fn.body or []):
            bhumi_report_error(
                getattr(new_fn, "lineno", None),
                getattr(new_fn, "col", None),
                f"Function '{demangle_mononame(mononame)}' may not return a value of type '{new_fn.ret_type}' on all control paths. "
                "Add a matching typecase, a fallback, or a return statement.",
            )
    try:
        llvm_lines = gen_func(new_fn)
    except Exception as e:
        generated_mono.pop(mononame, None)
        func_table.pop(mononame, None)
        try:
            all_funcs.remove(new_fn)
            _func_name_map.pop(new_fn.name, None)
        except ValueError:
            pass
        bhumi_report_error(
            None,
            None,
            f"Codegen error while monomorphising '{demangle_mononame(mononame)}': {e}",
        )
    out.insert(0, "\n".join(llvm_lines) + "\n")
    return mononame
def _subst_type(typ: Optional[str], subst: Dict[str, str]) -> Optional[str]:
    if typ is None:
        return None
    if typ in subst:
        return subst[typ]
    for param, concrete in subst.items():
        if typ == param:
            return concrete
        if typ.startswith(param) and typ[len(param) :] in ("*", "[]"):
            return concrete + typ[len(param) :]
    return typ
def mangle_type(typ: str) -> str:
    if typ is None:
        return "void"
    t = typ
    t = t.replace("%struct.", "struct_")
    t = t.replace("%enum.", "enum_")
    t = t.replace("*", "_ptr")
    t = t.replace("[", "_").replace("]", "")
    for ch in [" ", ",", ".", "<", ">", ":", "/", "\\", "%"]:
        t = t.replace(ch, "_")
    while "__" in t:
        t = t.replace("__", "_")
    return t.strip("_")
def llvm_int_bitsize(ty: str) -> Optional[int]:
    if m := re.fullmatch(r"i(\d+)", ty):
        return int(m.group(1))
    return None
def emit_cast_value(
    val: Optional[str], src_t: str, dst_t: str, out: List[str]
) -> Optional[str]:
    if val is None:
        return None
    src_llvm = llvm_ty_of(src_t)
    dst_llvm = llvm_ty_of(dst_t)
    if src_llvm == dst_llvm:
        return val
    if src_llvm.startswith("%enum.") and src_llvm.endswith("*"):
        enum_name = src_llvm[len("%enum."):-1]
        variants = enum_variant_map.get(enum_name, [])
        payload_types = [p for (_, p) in variants if p is not None]
        matching_payload = None
        for p in payload_types:
            if llvm_ty_of(p) == dst_llvm:
                matching_payload = p
                break
            p_llvm = llvm_ty_of(p)
            if p_llvm.endswith("*") and dst_llvm.endswith("*"):
                matching_payload = p
                break
        if matching_payload is not None:
            payload_llvm = llvm_ty_of(matching_payload)
            raw_ptr = new_tmp()
            out.append(
                f"  {raw_ptr} = getelementptr inbounds %enum.{enum_name}, "
                f"%enum.{enum_name}* {val}, i32 0, i32 1"
            )
            cast_ptr = new_tmp()
            out.append(
                f"  {cast_ptr} = bitcast [8 x i8]* {raw_ptr} to {payload_llvm}*"
            )
            loaded = new_tmp()
            out.append(f"  {loaded} = load {payload_llvm}, {payload_llvm}* {cast_ptr}")
            if payload_llvm != dst_llvm:
                final = new_tmp()
                out.append(f"  {final} = bitcast {payload_llvm} {loaded} to {dst_llvm}")
                return final
            return loaded
    if src_llvm.endswith("*") and dst_llvm.endswith("*"):
        tmp = new_tmp()
        out.append(f"  {tmp} = bitcast {src_llvm} {val} to {dst_llvm}")
        return tmp
    if src_llvm.endswith("*") and dst_llvm == "i1":
        tmp = new_tmp()
        out.append(f"  {tmp} = icmp ne {src_llvm} {val}, null")
        return tmp
    if (
        src_llvm.endswith("*")
        and dst_llvm.startswith("i")
        and not dst_llvm.endswith("*")
    ):
        tmp = new_tmp()
        out.append(f"  {tmp} = ptrtoint {src_llvm} {val} to {dst_llvm}")
        return tmp
    if (
        dst_llvm.endswith("*")
        and src_llvm.startswith("i")
        and not src_llvm.endswith("*")
    ):
        tmp = new_tmp()
        out.append(f"  {tmp} = inttoptr {src_llvm} {val} to {dst_llvm}")
        return tmp
    if (
        src_llvm.startswith("i")
        and not src_llvm.endswith("*")
        and dst_llvm.startswith("i")
        and not dst_llvm.endswith("*")
    ):
        src_bits = llvm_int_bitsize(src_llvm)
        dst_bits = llvm_int_bitsize(dst_llvm)
        tmp = new_tmp()
        if src_bits and dst_bits:
            if src_bits > dst_bits:
                out.append(f"  {tmp} = trunc {src_llvm} {val} to {dst_llvm}")
            else:
                if is_unsigned_int_type(src_t):
                    out.append(f"  {tmp} = zext {src_llvm} {val} to {dst_llvm}")
                else:
                    out.append(f"  {tmp} = sext {src_llvm} {val} to {dst_llvm}")
            return tmp
    if src_llvm.startswith("i") and not src_llvm.endswith("*") and dst_llvm == "double":
        tmp = new_tmp()
        out.append(f"  {tmp} = sitofp {src_llvm} {val} to double")
        return tmp
    if dst_llvm.startswith("i") and not dst_llvm.endswith("*") and src_llvm == "double":
        tmp = new_tmp()
        out.append(f"  {tmp} = fptosi double {val} to {dst_llvm}")
        return tmp
    if src_llvm == "double" and dst_llvm == "float":
        tmp = new_tmp()
        out.append(f"  {tmp} = fptrunc double {val} to float")
        return tmp
    if src_llvm == "float" and dst_llvm == "double":
        tmp = new_tmp()
        out.append(f"  {tmp} = fpext float {val} to double")
        return tmp
    if (
        src_llvm == "i1"
        and dst_llvm.startswith("i")
        and not dst_llvm.endswith("*")
        and dst_llvm != "i1"
    ):
        tmp = new_tmp()
        out.append(f"  {tmp} = zext i1 {val} to {dst_llvm}")
        return tmp
    if src_llvm.startswith("i") and not src_llvm.endswith("*") and dst_llvm == "i1":
        tmp = new_tmp()
        out.append(f"  {tmp} = icmp ne {src_llvm} {val}, 0")
        return tmp
    if src_llvm.endswith("*") and dst_llvm.endswith("*"):
        tmp = new_tmp()
        out.append(f"  {tmp} = bitcast {src_llvm} {val} to {dst_llvm}")
        return tmp
    return val
def is_unsigned_int_type(typ: str) -> bool:
    if typ is None:
        return False
    return typ.startswith("uint")
def int_type_info(typ: str) -> Tuple[int, bool]:
    if typ == "int":
        return 64, False
    if typ == "uint":
        return 64, True
    if m := re.fullmatch(r"(u?)int(\d+)", typ):
        unsigned = m.group(1) == "u"
        bits = int(m.group(2))
        return bits, unsigned
    llvm_name = type_map.get(typ)
    if llvm_name and llvm_name.startswith("i"):
        return int(llvm_name[1:]), False
    return 64, False
def extract_array_base_type(llvm_ty: str) -> str:
    match = re.match(r"\[\d+\s*x\s+(.+)]", llvm_ty)
    if not match:
        bhumi_report_error(None, None, f"Cannot extract element type from: {llvm_ty}")
    return match.group(1)
def lex(source: str) -> List[Token]:
    tokens: List[Token] = []
    i, line, col = 0, 1, 1
    while i < len(source):
        c = source[i]
        if c in " \t":
            i += 1
            col += 1
            continue
        if c == "\n":
            i += 1
            line += 1
            col = 1
            continue
        if c == "/" and i + 1 < len(source) and source[i + 1] == "/":
            while i < len(source) and source[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < len(source) and source[i + 1] == "*":
            i += 2
            while i < len(source) - 1:
                if source[i] == "*" and source[i + 1] == "/":
                    i += 2
                    break
                if source[i] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                i += 1
            else:
                bhumi_report_error(
                    line, None, f"Unclosed multiline comment starting at line {line}"
                )
            continue
        matched = False
        for mc, kind in MULTI_CHARS.items():
            if source.startswith(mc, i):
                tokens.append(Token(kind, mc, line, col))
                i += len(mc)
                col += len(mc)
                matched = True
                break
        if matched:
            continue
        if c.isalpha() or c in {"_", "@"}:
            start = i
            while i < len(source) and (source[i].isalnum() or source[i] in {"_", "@"}):
                i += 1
            val = source[start:i]
            kind = val if val in KEYWORDS else "IDENT"
            tokens.append(Token(kind.upper(), val, line, col))
            col += len(val)
            continue
        if c.isdigit():
            start = i
            if c == "0" and i + 1 < len(source) and source[i + 1] in {"x", "X"}:
                i += 2
                while i < len(source) and re.match(r"[0-9a-fA-F]", source[i]):
                    i += 1
                raw = source[start:i]
                tokens.append(Token("INT", raw, line, col))
                col += len(raw)
                continue
            while i < len(source) and source[i].isdigit():
                i += 1
            is_float = False
            if i < len(source) and source[i] == ".":
                i += 1
                while i < len(source) and source[i].isdigit():
                    i += 1
                is_float = True
            if i < len(source) and source[i] in {"e", "E"}:
                i += 1
                if i < len(source) and source[i] in {"+", "-"}:
                    i += 1
                while i < len(source) and source[i].isdigit():
                    i += 1
                is_float = True
            is_float32 = False
            if i < len(source) and source[i] in {"f", "F"}:
                is_float32 = True
                i += 1
                is_float = True
            raw = source[start:i]
            if is_float:
                if is_float32:
                    tokens.append(Token("FLOAT32", raw[:-1], line, col))
                else:
                    tokens.append(Token("FLOAT", raw, line, col))
            else:
                tokens.append(Token("INT", raw, line, col))
            col += len(raw)
            continue
        if c == '"':
            i += 1
            start_col = col
            val = ""
            while i < len(source) and source[i] != '"':
                if source[i] == "\\" and i + 1 < len(source):
                    nxt = source[i + 1]
                    if nxt == "n":
                        val += "\n"
                    elif nxt == "t":
                        val += "\t"
                    elif nxt == "\\":
                        val += "\\"
                    elif nxt == '"':
                        val += '"'
                    else:
                        val += nxt
                    i += 2
                    col += 2
                else:
                    val += source[i]
                    i += 1
                    col += 1
            if i >= len(source) or source[i] != '"':
                bhumi_report_error(line, start_col, f"Unclosed string literal")
            i += 1
            col += 1
            tokens.append(Token("STRING", val, line, start_col))
            continue
        if c == "'":
            i += 1
            start_col = col
            if i < len(source) and source[i] == "\\" and i + 1 < len(source):
                nxt = source[i + 1]
                if nxt == "n":
                    val = "\n"
                elif nxt == "t":
                    val = "\t"
                elif nxt == "\\":
                    val = "\\"
                elif nxt == "'":
                    val = "'"
                else:
                    val = nxt
                i += 2
                col += 2
            else:
                if i < len(source):
                    val = source[i]
                    i += 1
                    col += 1
                else:
                    bhumi_report_error(line, start_col, f"Unclosed character literal")
            if i >= len(source) or source[i] != "'":
                bhumi_report_error(line, start_col, f"Unclosed character literal")
            i += 1
            col += 1
            tokens.append(Token("CHAR", val, line, start_col))
            continue
        if c in SINGLE_CHARS:
            tokens.append(Token(SINGLE_CHARS[c], c, line, col))
            i += 1
            col += 1
            matched = True
            continue
        bhumi_report_error(line, col, f"Unrecognized character '{c}'")
    tokens.append(Token("EOF", "", line, col))
    return tokens
@dataclass
class Expr:
    pass
@dataclass
class Stmt:
    pass
@dataclass
class IntLit(Expr):
    value: int
@dataclass
class FloatLit(Expr):
    value: float
    bits: int = 64
@dataclass
class BoolLit(Expr):
    value: bool
@dataclass
class CharLit(Expr):
    value: str
@dataclass
class StrLit(Expr):
    value: str
@dataclass
class Var(Expr):
    name: str
@dataclass
class NullLit(Expr):
    pass
@dataclass
class CallerType(Expr):
    pass
@dataclass
class GlobalVar:
    typ: str
    name: str
    expr: Optional[Expr]
    nomd: bool = False
    pinned: bool = False
    is_extern: bool = False
@dataclass
class ForgetStmt(Stmt):
    varname: str
@dataclass
class UnaryDeref(Expr):
    ptr: Expr
@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr
@dataclass
class Call(Expr):
    name: str
    args: List[Expr]
@dataclass
class AddressOf(Expr):
    expr: Expr
@dataclass
class EnumVariant:
    name: str
    typ: Optional[str]
@dataclass
class EnumDef(Stmt):
    name: str
    type_params: List[str]
    variants: List[EnumVariant]
@dataclass
class CrumbleStmt(Stmt):
    name: str
    max_reads: Optional[int] = None
    max_writes: Optional[int] = None
@dataclass
class VarDecl(Stmt):
    access: str
    typ: str
    name: str
    expr: Optional[Expr]
    nomd: bool = False
@dataclass
class Assign(Stmt):
    name: Union[str, Expr]
    expr: Expr
@dataclass
class StructField:
    name: str
    typ: str
@dataclass
class UnaryOp(Expr):
    op: str
    expr: Expr
@dataclass
class IndexAssign(Stmt):
    array: str
    index: Expr
    value: Expr
@dataclass
class StructDef(Stmt):
    name: str
    fields: List[StructField]
@dataclass
class FieldAccess(Expr):
    base: Expr
    field: str
@dataclass
class MatchCase:
    variant: str
    binding: Optional[str]
    body: List[Stmt]
    nested_pattern: Optional["MatchCase"] = None
@dataclass
class Match(Stmt):
    expr: Expr
    cases: List[MatchCase]
@dataclass
class StructInit(Expr):
    name: str
    fields: List[Tuple[str, Expr]]
@dataclass
class ArrayInit(Expr):
    elements: List[Expr]
@dataclass
class TypeSwitchCase:
    typ: str
    body: List[Stmt]
@dataclass
class TypeSwitch(Stmt):
    subject: str
    cases: List[TypeSwitchCase]
    fallback: Optional[List[Stmt]] = None
@dataclass
class IfStmt(Stmt):
    cond: Expr
    then_body: List[Stmt]
    else_body: Optional[Union["IfStmt", List[Stmt]]]
@dataclass
class WhileStmt(Stmt):
    cond: Expr
    body: List[Stmt]
@dataclass
class ReturnStmt(Stmt):
    expr: Optional[Expr]
@dataclass
class ExprStmt(Stmt):
    expr: Expr
@dataclass
class Index(Expr):
    array: Expr
    index: Expr
@dataclass
class TypeofExpr(Expr):
    expr: Expr
@dataclass
class ContinueStmt(Stmt):
    pass
@dataclass
class BreakStmt(Stmt):
    pass
@dataclass
class Ternary(Expr):
    cond: Expr
    then_expr: Expr
    else_expr: Expr
@dataclass
class Cast(Expr):
    typ: str
    expr: Expr
@dataclass
class AwaitExpr(Expr):
    expr: Expr
@dataclass
class VAwaitExpr(Expr):
    expr: Expr
@dataclass
class Func:
    access: str
    name: str
    type_params: List[str]
    params: List[Tuple[str, str]]
    ret_type: str
    body: Optional[List[Stmt]] = None
    is_extern: bool = False
    is_async: bool = False
    is_vasync: bool = False
    vasync_except: List[str] = None
    _vasync_captured: Optional[set] = None
    is_variadic: bool = False
    is_nown: bool = False
    take_params: Optional[set] = None
    def __post_init__(self):
        if self.vasync_except is None:
            self.vasync_except = []
        else:
            self.vasync_except = list(self.vasync_except)
        if self.take_params is None:
            self.take_params = set()
@dataclass
class Program:
    funcs: List[Func]
    imports: List[str]
    structs: List[StructDef]
    enums: List[EnumDef]
    globals: List[GlobalVar]
string_constants: List[str] = []
struct_field_map: Dict[str, List[Tuple[str, str]]] = {}
generated_mono: Dict[str, bool] = {}
all_funcs: List[Func] = []
_func_name_map: Dict[str, "Func"] = {}
enum_variant_map: Dict[str, List[Tuple[str, Optional[str]]]] = {}
loop_stack: List[Dict[str, str]] = []
crumb_runtime: Dict[str, Dict[str, Any]] = {}
owned_vars: set = set()
scope_drop_stack: List[Dict[str, object]] = []
binding_enum_payload: Dict[str, tuple] = {}
binding_source_name: Dict[str, str] = {}
_entry_alloca_buf: List[str] = []
_extern_spill_names: set = set()
_ar_spilled_ssa_vals: set = set()
_ar_spill_val_to_name: Dict[str, str] = {}
_fn_body_remaining: List = []
_expr_type_cache: Dict[int, str] = {}
_parse_cache: Dict[str, Any] = {}
_NOWN_BUILTIN_FUNCS: frozenset = frozenset({
    "bhumi_argv",
})
_FREE_ARG_FUNS: frozenset = frozenset({
    "free_str",
    "Ufree_union",
    "bhumi_c_free",
})
mono_map: Dict[str, str] = {}
class Parser:
    def __init__(self, tokens: List[Token]):
        self.declared_vars: Dict[str, VarDecl] = {}
        self.tokens = tokens
        self.pos = 0
    def peek(self) -> Token:
        return self.tokens[self.pos]
    def bump(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t
    def expect(self, kind: str) -> Token:
        if self.peek().kind == kind:
            return self.bump()
        bhumi_report_error(
            self.peek().line,
            self.peek().col,
            f"Expected {kind}, got {self.peek().kind}",
        )
    def match(self, kind: str) -> bool:
        if self.peek().kind == kind:
            self.bump()
            return True
        return False
    def _lookahead_is_func(self) -> bool:
        _FUNC_MODS = {"NOWN", "PUB", "PRIV", "PROT", "ASYNC", "VASYNC", "EXTERN"}
        i = self.pos + 1
        while i < len(self.tokens):
            tk = self.tokens[i].kind
            if tk == "FN":
                return True
            if tk in _FUNC_MODS:
                i += 1
                continue
            if tk != "FN" and tk.lower() in KEYWORDS:
                i += 1
                continue
            return False
        return False
    def parse(self) -> Program:
        funcs = []
        imports = []
        structs = []
        enums = []
        globals = []
        while self.peek().kind != "EOF":
            if (
                self.peek().kind == "IDENT"
                and isinstance(self.peek().value, str)
                and self.peek().value.startswith("@")
            ):
                directive = self.bump().value
                if not self.match("SEMI"):
                    bhumi_report_error(
                        self.peek().line,
                        self.peek().col,
                        f"Expected ';' after directive {directive}",
                    )
                if directive == "@nrt":
                    global no_runtime
                    no_runtime = True
                    continue
                elif directive == "@nomain":
                    global no_main
                    no_main = True
                    continue
                else:
                    bhumi_report_error(
                        self.peek().line,
                        self.peek().col,
                        f"Unknown directive {directive}",
                    )
            if self.match("IMPORT"):
                while True:
                    if self.peek().kind == "STRING":
                        raw = self.bump().value
                    elif self.peek().kind == "IDENT":
                        raw = self.bump().value
                    else:
                        bhumi_report_error(
                            self.peek().line,
                            self.peek().col,
                            f"Expected import path, got {self.peek().kind}",
                        )
                    imports.append(raw)
                    if self.peek().kind == "SEMI":
                        self.bump()
                        break
                    elif self.peek().kind == "COMMA":
                        self.bump()
                        continue
                    else:
                        bhumi_report_error(
                            self.peek().line,
                            self.peek().col,
                            f"Expected ',' or ';' in import list, got {self.peek().kind}",
                        )
            elif (
                self.peek().kind == "EXTERN" and self._lookahead_is_func()
            ):
                funcs.append(self.parse_func())
            elif self.peek().kind in {"EXTERN", "NOMD", "PIN"}:
                is_extern = False
                nomd = False
                pinned = False
                seen_nomd = False
                while self.peek().kind in {"EXTERN", "NOMD", "PIN"}:
                    if self.match("EXTERN"):
                        is_extern = True
                        continue
                    if self.peek().kind == "PIN":
                        if seen_nomd:
                            bhumi_report_error(
                                self.peek().line,
                                self.peek().col,
                                "Invalid modifier order: 'pin' cannot follow 'nomd'. Use 'pin nomd' not 'nomd pin'.",
                            )
                        self.bump()
                        pinned = True
                        continue
                    if self.peek().kind == "NOMD":
                        self.bump()
                        nomd = True
                        seen_nomd = True
                        continue
                decl = self.parse_var_decl()
                if is_extern and decl.expr is not None:
                    bhumi_report_error(
                        None, None, "extern globals cannot have initializers"
                    )
                globals.append(
                    GlobalVar(
                        decl.typ,
                        decl.name,
                        decl.expr,
                        nomd=nomd,
                        pinned=pinned,
                        is_extern=is_extern,
                    )
                )
            elif self.peek().kind == "STRUCT":
                structs.append(self.parse_struct_def())
            elif self.peek().kind == "ENUM":
                enums.append(self.parse_enum_def())
            else:
                funcs.append(self.parse_func())
        self.program = Program(funcs, imports, structs, enums, globals)
        return self.program
    def _expect_gt(self):
        if self.peek().kind == "GT":
            return self.bump()
        if self.peek().kind == "RSHIFT":
            tok = self.tokens[self.pos]
            self.tokens[self.pos] = Token("GT", ">", tok.line, tok.col + 1)
            return Token("GT", ">", tok.line, tok.col)
        bhumi_report_error(
            self.peek().line,
            self.peek().col,
            f"Expected '>' to close generic type parameters, got {self.peek().kind}",
        )
    def parse_type(self) -> str:
        prefix_amp = False
        if self.peek().kind == "AMP":
            self.bump()
            prefix_amp = True
        if self.peek().kind not in TYPE_TOKENS and self.peek().kind != "IDENT":
            bhumi_report_error(
                self.peek().line, self.peek().col, f"Expected type, got {self.peek().kind}"
            )
        base = self.bump().value
        if self.match("LT"):
            params: List[str] = []
            while True:
                params.append(self.parse_type())
                if not self.match("COMMA"):
                    break
            self._expect_gt()
            base = f"{base}<" + ",".join(params) + ">"
        if prefix_amp or self.match("AMP"):
            base += "*"
        while self.match("STAR"):
            base += "*"
        if self.match("LBRACKET"):
            if self.peek().kind == "INT":
                size_tok = self.bump()
                self.expect("RBRACKET")
                base += f"[{size_tok.value}]"
            else:
                self.expect("RBRACKET")
                base += "[]"
        return base
    def parse_enum_def(self) -> EnumDef:
        self.expect("ENUM")
        ident_tok = self.expect("IDENT")
        name = ident_tok.value
        if "__mono__" in name:
            bhumi_report_error(
                ident_tok.line,
                ident_tok.col,
                "Names containing '__mono__' are reserved for compiler-generated functions.",
            )
        type_params: List[str] = []
        if self.match("LT"):
            while True:
                tp_tok = self.expect("IDENT")
                if "__mono__" in tp_tok.value:
                    bhumi_report_error(
                        tp_tok.line,
                        tp_tok.col,
                        "Type parameter names cannot contain '__mono__'.",
                    )
                type_params.append(tp_tok.value)
                if not self.match("COMMA"):
                    break
            self.expect("GT")
        self.expect("LBRACE")
        variants: List[EnumVariant] = []
        while self.peek().kind != "RBRACE":
            v_tok = self.expect("IDENT")
            variant_name = v_tok.value
            if "__mono__" in variant_name:
                bhumi_report_error(
                    v_tok.line,
                    v_tok.col,
                    "Enum variant names cannot contain '__mono__'.",
                )
            variant_type: Optional[str] = None
            if self.peek().kind == "LPAREN":
                self.bump()
                variant_type = self.parse_type()
                self.expect("RPAREN")
                self.expect("SEMI")
            else:
                self.expect("SEMI")
            variants.append(EnumVariant(variant_name, variant_type))
        self.expect("RBRACE")
        return EnumDef(name, type_params, variants)
    def parse_struct_def(self) -> StructDef:
        self.expect("STRUCT")
        ident_tok = self.expect("IDENT")
        name = ident_tok.value
        if "__mono__" in name:
            bhumi_report_error(
                ident_tok.line,
                ident_tok.col,
                "Names containing '__mono__' are reserved for compiler-generated functions.",
            )
        self.expect("LBRACE")
        fields = []
        while self.peek().kind != "RBRACE":
            prefix_amp = False
            if self.peek().kind == "AMP":
                self.bump()
                prefix_amp = True
            if self.peek().kind in TYPE_TOKENS or self.peek().kind == "IDENT":
                typ = self.parse_type()
                f_tok = self.expect("IDENT")
                fname = f_tok.value
                if prefix_amp or self.match("AMP"):
                    typ += "*"
                while self.match("STAR"):
                    typ += "*"
                if self.match("LBRACKET"):
                    size_tok = self.expect("INT")
                    self.expect("RBRACKET")
                    typ += f"[{size_tok.value}]"
                if "__mono__" in fname:
                    bhumi_report_error(
                        f_tok.line, f_tok.col, "Field names cannot contain '__mono__'."
                    )
            else:
                bhumi_report_error(
                    self.peek().line,
                    self.peek().col,
                    f"Expected type in struct field, got {self.peek().kind}",
                )
            self.expect("SEMI")
            fields.append(StructField(fname, typ))
        self.expect("RBRACE")
        return StructDef(name, fields)
    def parse_func(self) -> Func:
        access = "pub"
        is_extern = False
        is_async = False
        is_vasync = False
        is_nown = False
        while True:
            tk = self.peek().kind
            if tk == "EXTERN":
                is_extern = True
                self.bump()
                continue
            if tk in {"PUB", "PRIV", "PROT"}:
                access = self.bump().kind.lower()
                continue
            if tk == "NOWN":
                is_nown = True
                self.bump()
                continue
            if tk == "ASYNC":
                if no_runtime:
                    bhumi_report_error(
                        None,
                        None,
                        "Cannot use async and/or runtime features with @nrt (No Run Time);",
                    )
                else:
                    is_async = True
                    self.bump()
                    continue
            if tk == "VASYNC":
                is_vasync = True
                self.bump()
                continue
            if tk != "FN" and tk.lower() in KEYWORDS:
                self.bump()
                continue
            break
        self.expect("FN")
        type_params: List[str] = []
        if self.peek().kind == "LBRACKET":
            self.bump()
            while True:
                tp_tok = self.expect("IDENT")
                if "__mono__" in tp_tok.value:
                    bhumi_report_error(
                        tp_tok.line,
                        tp_tok.col,
                        "Type parameter names cannot contain '__mono__'.",
                    )
                type_params.append(tp_tok.value)
                if not self.match("COMMA"):
                    break
            self.expect("RBRACKET")
        ident_tok = self.expect("IDENT")
        name = ident_tok.value
        if "__mono__" in name:
            bhumi_report_error(
                ident_tok.line,
                ident_tok.col,
                "Names containing '__mono__' are reserved for compiler-generated functions.",
            )
        variadic = False
        self.expect("LPAREN")
        params: List[Tuple[str, str]] = []
        take_indices: set = set()
        if self.peek().kind != "RPAREN":
            while True:
                is_take = False
                if self.peek().kind == "TAKE":
                    is_take = True
                    self.bump()
                prefix_amp = False
                if self.peek().kind == "AMP":
                    self.bump()
                    prefix_amp = True
                if self.peek().kind in TYPE_TOKENS or self.peek().kind == "IDENT":
                    typ = self.parse_type()
                    if prefix_amp or self.match("AMP"):
                        typ += "*"
                    while self.match("STAR"):
                        typ += "*"
                    if self.match("LBRACKET"):
                        size_tok = self.expect("INT")
                        self.expect("RBRACKET")
                        typ += f"[{size_tok.value}]"
                    p_tok = self.expect("IDENT")
                    if "__mono__" in p_tok.value:
                        bhumi_report_error(
                            p_tok.line,
                            p_tok.col,
                            "Parameter names cannot contain '__mono__'.",
                        )
                    pname = p_tok.value
                    params.append((typ, pname))
                    if is_take:
                        take_indices.add(len(params) - 1)
                else:
                    bhumi_report_error(
                        self.peek().line,
                        self.peek().col,
                        f"Expected type, got {self.peek().kind}",
                    )
                if self.match("COMMA"):
                    if self.peek().kind == "RPAREN":
                        if not is_extern:
                            bhumi_report_error(
                                self.peek().line,
                                self.peek().col,
                                "Variadics are only allowed in external functions (use 'extern fn ...').",
                            )
                        variadic = True
                        break
                    continue
                break
        self.expect("RPAREN")
        vasync_except: List[str] = []
        if is_vasync and self.peek().kind == "EXCEPT":
            self.bump()
            self.expect("LPAREN")
            while True:
                if self.peek().kind != "IDENT":
                    bhumi_report_error(
                        self.peek().line,
                        self.peek().col,
                        "Expected identifier in except(...)",
                    )
                vasync_except.append(self.bump().value)
                if not self.match("COMMA"):
                    break
            self.expect("RPAREN")
        self.expect("LT")
        ret_type = self.parse_type()
        self.expect("GT")
        if is_extern:
            self.expect("SEMI")
            fn_ext = Func(
                access,
                name,
                type_params,
                params,
                ret_type,
                None,
                True,
                is_async,
                is_vasync,
                list(vasync_except),
                is_variadic=variadic,
            )
            fn_ext.is_nown = is_nown
            fn_ext.take_params = take_indices
            return fn_ext
        self.expect("LBRACE")
        body = self.parse_block()
        self.expect("RBRACE")
        fn_reg = Func(
            access,
            name,
            type_params,
            params,
            ret_type,
            body,
            False,
            is_async,
            is_vasync,
            list(vasync_except),
            is_variadic=variadic,
        )
        fn_reg.is_nown = is_nown
        fn_reg.take_params = take_indices
        return fn_reg
    def parse_block(self) -> List[Stmt]:
        stmts = []
        while self.peek().kind != "RBRACE":
            stmts.append(self.parse_stmt())
        return stmts
    def parse_stmt(self) -> Stmt:
        t = self.peek()
        if t.kind == "MATCH":
            return self.parse_match()
        if t.kind == "STAR":
            return self.parse_ptr_assign()
        if t.kind == "IDENT":
            next_kind = self.tokens[self.pos + 1].kind
            if next_kind in {
                "EQUAL",
                "PLUSEQ",
                "MINUSEQ",
                "STAREQ",
                "SLASHEQ",
                "PERCENTEQ",
                "ANDEQ",
                "OREQ",
                "XOREQ",
                "LSHIFTEQ",
                "RSHIFTEQ",
            }:
                return self.parse_compound_assign()
        if t.kind == "IDENT" and self.tokens[self.pos + 1].kind == "LBRACKET":
            return self.parse_index_assign()
        if (
            t.kind == "IDENT"
            and t.value == "forget"
            and self.tokens[self.pos + 1].kind == "LPAREN"
        ):
            return self.parse_forget()
        if (t.kind in CAST_TYPE_TOKENS or t.kind == "IDENT") and self.tokens[
            self.pos + 1
        ].kind == "LPAREN":
            return self.parse_expr_stmt()
        if (
            t.kind in {"PUB", "PRIV", "PROT", "NOMD"}
            or t.kind in TYPE_TOKENS
            or t.kind == "IDENT"
        ):
            return self.parse_var_decl()
        if t.kind == "IF":
            return self.parse_if()
        if t.kind == "WHILE":
            return self.parse_while()
        if t.kind == "TYPESWITCH":
            return self.parse_typeswitch()
        if self.match("CRUMBLE"):
            return self.parse_crumble()
        if t.kind == "CONTINUE":
            self.bump()
            self.expect("SEMI")
            return ContinueStmt()
        if t.kind == "BREAK":
            self.bump()
            self.expect("SEMI")
            return BreakStmt()
        if t.kind == "RETURN":
            return self.parse_return()
        return self.parse_expr_stmt()
    def parse_typeswitch(self) -> TypeSwitch:
        self.expect("TYPESWITCH")
        self.expect("LPAREN")
        if self.peek().kind not in ("IDENT", "HASH"):
            bhumi_report_error(
                self.peek().line,
                self.peek().col,
                "Expected type parameter identifier or '#' in typeswitch(.)",
            )
        subject = self.bump().value
        self.expect("RPAREN")
        self.expect("LBRACE")
        cases: List[TypeSwitchCase] = []
        fallback_body: Optional[List[Stmt]] = None
        while self.peek().kind != "RBRACE":
            if self.peek().kind == "TYPECASE":
                self.bump()
                self.expect("LPAREN")
                case_typ = self.parse_type()
                self.expect("RPAREN")
                self.expect("LBRACE")
                body = self.parse_block()
                self.expect("RBRACE")
                cases.append(TypeSwitchCase(case_typ, body))
                continue
            if self.peek().kind == "FALLBACK":
                self.bump()
                self.expect("LBRACE")
                fallback_body = self.parse_block()
                self.expect("RBRACE")
                continue
            bhumi_report_error(
                self.peek().line,
                self.peek().col,
                f"Unexpected token in typeswitch: {self.peek().kind}",
            )
        self.expect("RBRACE")
        return TypeSwitch(subject, cases, fallback_body)
    def parse_compound_assign(self) -> Assign:
        name = self.expect("IDENT").value
        op_token = self.bump()
        expr = self.parse_expr()
        self.expect("SEMI")
        if op_token.kind == "EQUAL":
            return Assign(name, expr)
        compound_map = {
            "PLUSEQ": "+",
            "MINUSEQ": "-",
            "STAREQ": "*",
            "SLASHEQ": "/",
            "PERCENTEQ": "%",
            "ANDEQ": "&",
            "OREQ": "|",
            "XOREQ": "^",
            "LSHIFTEQ": "<<",
            "RSHIFTEQ": ">>",
        }
        if op_token.kind not in compound_map:
            bhumi_report_error(
                getattr(op_token, "line", None),
                getattr(op_token, "col", None),
                f"Unknown compound assignment: {op_token.kind}",
            )
        op = compound_map[op_token.kind]
        lhs_var = Var(name)
        binop = BinOp(op, lhs_var, expr)
        return Assign(name, binop)
    def parse_crumble(self) -> CrumbleStmt:
        self.expect("LPAREN")
        var_name = self.expect("IDENT").value
        self.expect("RPAREN")
        max_r, max_w = None, None
        while self.match("BANG"):
            kw = self.expect("IDENT").value
            self.expect("EQUAL")
            val = int(self.expect("INT").value)
            if kw == "r":
                max_r = val
            elif kw == "w":
                max_w = val
            else:
                bhumi_report_error(None, None, f"Unknown crumb kind '!{kw}'")
        self.expect("SEMI")
        return CrumbleStmt(var_name, max_r, max_w)
    def parse_ptr_assign(self) -> Stmt:
        self.expect("STAR")
        ptr_expr = self.parse_primary()
        self.expect("EQUAL")
        val_expr = self.parse_expr()
        self.expect("SEMI")
        return Assign(UnaryDeref(ptr_expr), val_expr)
    def parse_forget(self) -> ForgetStmt:
        self.expect("IDENT")
        self.expect("LPAREN")
        varname = self.expect("IDENT").value
        self.expect("RPAREN")
        self.expect("SEMI")
        return ForgetStmt(varname)
    def parse_match(self) -> Match:
        self.expect("MATCH")
        self.expect("LPAREN")
        expr_to_match = self.parse_expr()
        self.expect("RPAREN")
        self.expect("LBRACE")
        cases: List[MatchCase] = []
        while self.peek().kind != "RBRACE":
            case = self._parse_match_case()
            self.expect("LBRACE")
            body_stmts: List[Stmt] = []
            while self.peek().kind != "RBRACE":
                body_stmts.append(self.parse_stmt())
            self.expect("RBRACE")
            case.body = body_stmts
            cases.append(case)
        self.expect("RBRACE")
        return Match(expr_to_match, cases)
    def _parse_match_case(self) -> "MatchCase":
        v_tok = self.expect("IDENT")
        variant_name = v_tok.value
        if "__mono__" in variant_name:
            bhumi_report_error(
                v_tok.line, v_tok.col,
                "Match variant names cannot contain '__mono__'.",
            )
        binding_name: Optional[str] = None
        nested_pattern: Optional[MatchCase] = None
        if self.match("LPAREN"):
            inner_tok = self.expect("IDENT")
            inner_name = inner_tok.value
            if "__mono__" in inner_name:
                bhumi_report_error(
                    inner_tok.line, inner_tok.col,
                    "Binding names cannot contain '__mono__'.",
                )
            if self.peek().kind == "LPAREN":
                self.bump()
                inner_case = self._parse_match_case_inner(inner_name)
                self.expect("RPAREN")
                nested_pattern = inner_case
                binding_name = None
            elif self.peek().kind == "RPAREN":
                binding_name = inner_name
                self.expect("RPAREN")
            else:
                bhumi_report_error(
                    inner_tok.line, inner_tok.col,
                    f"Expected ')' or nested pattern after '{inner_name}' in match arm",
                )
        return MatchCase(variant=variant_name, binding=binding_name, body=[], nested_pattern=nested_pattern)
    def _parse_match_case_inner(self, variant_name: str) -> "MatchCase":
        if "__mono__" in variant_name:
            bhumi_report_error(None, None, "Match variant names cannot contain '__mono__'.")
        binding_name: Optional[str] = None
        nested_pattern: Optional[MatchCase] = None
        inner_tok = self.expect("IDENT")
        inner_name = inner_tok.value
        if self.peek().kind == "LPAREN":
            self.bump()
            deeper = self._parse_match_case_inner(inner_name)
            self.expect("RPAREN")
            nested_pattern = deeper
        else:
            binding_name = inner_name
        return MatchCase(variant=variant_name, binding=binding_name, body=[], nested_pattern=nested_pattern)
    def parse_var_decl(self) -> VarDecl:
        access = "priv"
        nomd = False
        if self.peek().kind in {"PUB", "PRIV", "PROT"}:
            access = self.bump().kind.lower()
        if self.peek().kind == "NOMD":
            self.bump()
            nomd = True
        prefix_amp = False
        if self.peek().kind == "AMP":
            self.bump()
            prefix_amp = True
        if self.peek().kind in TYPE_TOKENS or self.peek().kind == "IDENT" or self.peek().kind == "AMP":
            typ = self.parse_type()
        else:
            bhumi_report_error(
                self.peek().line,
                self.peek().col,
                f"Expected type (one of {TYPE_TOKENS} or user-defined), got {self.peek().kind}",
            )
        ident_tok = self.expect("IDENT")
        name = ident_tok.value
        if "__mono__" in name:
            bhumi_report_error(
                ident_tok.line,
                ident_tok.col,
                "Names containing '__mono__' are reserved for compiler-generated symbols.",
            )
        expr = None
        if self.match("EQUAL"):
            expr = self.parse_expr()
        self.expect("SEMI")
        var_decl = VarDecl(access, typ, name, expr, nomd)
        self.declared_vars[name] = var_decl
        return var_decl
    def parse_index_assign(self) -> IndexAssign:
        arr_name = self.expect("IDENT").value
        self.expect("LBRACKET")
        index = self.parse_expr()
        self.expect("RBRACKET")
        self.expect("EQUAL")
        value = self.parse_expr()
        self.expect("SEMI")
        return IndexAssign(arr_name, index, value)
    def parse_if(self) -> IfStmt:
        self.expect("IF")
        self.expect("LPAREN")
        cond = self.parse_expr()
        self.expect("RPAREN")
        self.expect("LBRACE")
        then_body = self.parse_block()
        self.expect("RBRACE")
        else_body = None
        if self.match("ELSE"):
            if self.peek().kind == "IF":
                else_body = self.parse_if()
            else:
                self.expect("LBRACE")
                else_body = self.parse_block()
                self.expect("RBRACE")
        return IfStmt(cond, then_body, else_body)
    def parse_while(self) -> WhileStmt:
        self.expect("WHILE")
        self.expect("LPAREN")
        cond = self.parse_expr()
        self.expect("RPAREN")
        self.expect("LBRACE")
        body = self.parse_block()
        self.expect("RBRACE")
        return WhileStmt(cond, body)
    def parse_return(self) -> ReturnStmt:
        self.expect("RETURN")
        expr = None
        if self.peek().kind != "SEMI":
            expr = self.parse_expr()
        self.expect("SEMI")
        return ReturnStmt(expr)
    def parse_expr_stmt(self) -> ExprStmt:
        expr = self.parse_expr()
        self.expect("SEMI")
        return ExprStmt(expr)
    def parse_expr(self, min_prec: int = 0) -> Expr:
        left = self.parse_primary()
        while True:
            op_token = self.peek()
            if op_token.kind in {
                "PLUS", "MINUS", "STAR", "SLASH",
                "PERCENT", "EQEQ", "NEQ", "LT",
                "LE", "GT", "GE", "AMP",
                "PIPE", "CARET", "LSHIFT", "RSHIFT",
                "AND", "OR",
            }:
                op_prec = self.get_precedence(op_token.kind)
                if op_prec < min_prec:
                    break
                self.bump()
                right = self.parse_expr(op_prec + 1)
                left = BinOp(op_token.value, left, right)
                continue
            if op_token.kind == "QUESTION" and min_prec == 0:
                self.bump()
                then_expr = self.parse_expr()
                self.expect("COLON")
                else_expr = self.parse_expr()
                left = Ternary(left, then_expr, else_expr)
                continue
            break
        return left
    def get_precedence(self, op: str) -> int:
        return {
            "STAR": 9, "SLASH": 9, "PERCENT": 9, "PLUS": 8,
            "MINUS": 8, "LSHIFT": 7, "RSHIFT": 7, "LT": 6,
            "LE": 6, "GT": 6, "GE": 6, "EQEQ": 5,
            "NEQ": 5, "AMP": 4, "CARET": 3, "PIPE": 2,
            "AND": 1, "OR": 0,
        }.get(op, 0)
    def parse_primary(self) -> Expr:
        if self.peek().kind in {
            "RPAREN", "RBRACE",
            "RBRACKET", "COMMA",
            "SEMI", "COLON",
        }:
            t = self.peek()
            bhumi_report_error(
                t.line, t.col, f"Unexpected token while parsing expression: {t.kind}"
            )
        if self.peek().kind == "AWAIT":
            self.bump()
            inner = self.parse_primary()
            return AwaitExpr(inner)
        if self.peek().kind == "VAWAIT":
            self.bump()
            inner = self.parse_primary()
            return VAwaitExpr(inner)
        if self.peek().kind == "STAR":
            self.bump()
            inner = self.parse_primary()
            return UnaryDeref(inner)
        if self.peek().kind == "AMP":
            self.bump()
            inner = self.parse_primary()
            return AddressOf(inner)
        if self.peek().kind == "BANG":
            self.bump()
            inner = self.parse_primary()
            return UnaryOp("!", inner)
        if self.peek().kind == "MINUS":
            self.bump()
            inner = self.parse_primary()
            return UnaryOp("-", inner)
        if self.peek().kind == "TILDE":
            self.bump()
            inner = self.parse_primary()
            return UnaryOp("~", inner)
        def parse_atom() -> Expr:
            t = self.bump()
            if t.kind == "LBRACKET":
                elems: List[Expr] = []
                if self.peek().kind != "RBRACKET":
                    while True:
                        elems.append(self.parse_expr())
                        if not self.match("COMMA"):
                            break
                self.expect("RBRACKET")
                return ArrayInit(elems)
            if (
                t.kind == "IDENT"
                and t.value == "typeof"
                and self.peek().kind == "LPAREN"
            ):
                self.expect("LPAREN")
                arg_expr = self.parse_expr()
                self.expect("RPAREN")
                return TypeofExpr(arg_expr)
            if (
                t.kind in TYPE_TOKENS
                and t.kind != "IDENT"
                and self.peek().kind == "LPAREN"
            ):
                type_name = t.value
                self.expect("LPAREN")
                inner = self.parse_expr()
                self.expect("RPAREN")
                return Cast(type_name, inner)
            if t.kind == "INT" and re.match(r"^[0-9]", t.value):
                try:
                    return IntLit(int(t.value, 0))
                except Exception:
                    bhumi_report_error(
                        t.line, t.col, f"Invalid integer literal: {t.value}"
                    )
            if t.kind == "FLOAT":
                return FloatLit(float(t.value), bits=64)
            if t.kind == "FLOAT32":
                return FloatLit(float(t.value), bits=32)
            if t.kind == "STRING":
                return StrLit(t.value)
            if t.kind == "CHAR":
                return CharLit(t.value)
            if t.kind == "TRUE":
                return BoolLit(True)
            if t.kind == "FALSE":
                return BoolLit(False)
            if t.kind == "NULL":
                return NullLit()
            if t.kind == "LPAREN":
                expr = self.parse_expr()
                self.expect("RPAREN")
                return expr
            if t.kind == "IDENT" and t.value == "BhumiCompiler.get_args":
                return Call("BhumiCompiler.get_args", [])
            if t.kind == "IDENT":
                ident_name = t.value
                if self.peek().kind == "ARROW":
                    self.bump()
                    variant_tok = self.expect("IDENT")
                    variant_name = variant_tok.value
                    args = []
                    if self.match("LPAREN"):
                        if self.peek().kind != "RPAREN":
                            args.append(self.parse_expr())
                        self.expect("RPAREN")
                    return Call(f"{ident_name}->{variant_name}", args)
                base = Var(ident_name)
                if self.peek().kind == "LBRACE":
                    self.bump()
                    fields_list: List[Tuple[str, Expr]] = []
                    while self.peek().kind != "RBRACE":
                        fname = self.expect("IDENT").value
                        self.expect("COLON")
                        fexpr = self.parse_expr()
                        self.expect("SEMI")
                        fields_list.append((fname, fexpr))
                    self.expect("RBRACE")
                    return StructInit(t.value, fields_list)
                if self.peek().kind == "LPAREN":
                    self.bump()
                    args: List[Expr] = []
                    if self.peek().kind != "RPAREN":
                        while True:
                            args.append(self.parse_expr())
                            if not self.match("COMMA"):
                                break
                    self.expect("RPAREN")
                    return Call(t.value, args)
                if self.peek().kind == "LBRACKET":
                    self.bump()
                    index_expr = self.parse_expr()
                    self.expect("RBRACKET")
                    return Index(base, index_expr)
                return base
            if t.kind == "HASH":
                return CallerType()
            bhumi_report_error(t.line, t.col, f"Unexpected token: {t.kind}")
        expr: Expr = parse_atom()
        while self.peek().kind == "DOT":
            self.bump()
            field_name = self.expect("IDENT").value
            expr = FieldAccess(expr, field_name)
        return expr
tmp_id = 0
def new_tmp() -> str:
    global tmp_id
    tmp_id += 1
    return f"%t{tmp_id}"
label_id = 0
def new_label(base="L") -> str:
    global label_id
    label_id += 1
    return f"{base}{label_id}"
def unify_int_types(t1: Optional[str], t2: Optional[str]) -> Optional[str]:
    if t1 is None or t2 is None:
        return None
    try:
        b1, u1 = int_type_info(t1)
        b2, u2 = int_type_info(t2)
    except Exception:
        return None
    if b1 > b2:
        chosen_bits = b1
        chosen_unsigned = u1 or (u2 and b1 == b2)
    elif b2 > b1:
        chosen_bits = b2
        chosen_unsigned = u2 or (u1 and b1 == b2)
    else:
        chosen_bits = b1
        chosen_unsigned = u1 or u2
    if chosen_bits == 64:
        return "uint" if chosen_unsigned else "int"
    else:
        return f"uint{chosen_bits}" if chosen_unsigned else f"int{chosen_bits}"
def unify_types(t1: str, t2: str) -> Optional[str]:
    if t1 == t2:
        return t1
    if t1 in {"null", "void*"}:
        return t2 if t2.endswith("*") or t2 == "string" else None
    if t2 in {"null", "void*"}:
        return t1 if t1.endswith("*") or t1 == "string" else None
    if int_common := unify_int_types(t1, t2):
        return int_common
    if (t1, t2) in {("float", "int"), ("int", "float")}:
        return "float"
    if (t1, t2) in {
        ("float", "float32"),
        ("float32", "float"),
        ("float32", "int"),
        ("int", "float32"),
    }:
        return "float32"
    return None
type_map = {
    "int": "i64", "int8": "i8", "int16": "i16", "int32": "i32",
    "void": "void", "int64": "i64", "float": "double", "bool": "i1",
    "char": "i8", "string": "i8*", "void*": "i8*", "uint": "i64",
    "uint8": "i8", "uint16": "i16", "uint32": "i32", "uint64": "i64",
    "int1": "i1", "uint1": "i1", "float32": "float",
}
struct_llvm_defs: List[str] = []
symbol_table = SymbolTable()
func_table: Dict[str, str] = {}
def gen_expr(expr: Expr, out: List[str], expected: Optional[str] = None) -> str | None:
    if isinstance(expr, CallerType):
        bhumi_report_error(
            getattr(expr, "lineno", None),
            getattr(expr, "col", None),
            "Internal compiler error: unresolved caller-placeholder '#' reached codegen (missing monomorphisation)",
        )
    def format_float(val: float) -> str:
        return f"{val:.8e}"
    def _is_heap_string_temp(e: Expr) -> bool:
        if isinstance(e, BinOp) and e.op == "+" and infer_type(e) == "string":
            return True
        if isinstance(e, Call):
            if e.name in _NOWN_BUILTIN_FUNCS:
                return False
            callee_fn = _func_name_map.get(e.name)
            if callee_fn is not None and getattr(callee_fn, "is_nown", False):
                return False
            return infer_type(e) == "string"
        return False
    def _emit_free_if_temp(e: Expr, ssa_val: str) -> None:
        if not _is_heap_string_temp(e):
            return
        if ssa_val is None:
            return
        if ssa_val in _ar_spilled_ssa_vals:
            _spill_nm = _ar_spill_val_to_name.get(ssa_val)
            if _spill_nm is None:
                return
            _spill_res = symbol_table.lookup(_spill_nm)
            if _spill_res is None:
                return
            _spill_llvm, _ir_name = _spill_res
            _addr = f"@{_ir_name}" if _ir_name.startswith("@") else f"%{_ir_name}_addr"
            _ld = new_tmp()
            out.append(f"  {_ld} = load {_spill_llvm}, {_spill_llvm}* {_addr}")
            _cast = new_tmp()
            out.append(f"  {_cast} = bitcast {_spill_llvm} {_ld} to i8*")
            _isnull = new_tmp()
            out.append(f"  {_isnull} = icmp eq i8* {_cast}, null")
            _skiplbl = new_label("tmp_free_skip")
            _dolbl   = new_label("tmp_free_do")
            out.append(f"  br i1 {_isnull}, label %{_skiplbl}, label %{_dolbl}")
            out.append(f"{_dolbl}:")
            out.append(f"  call void @bhumi_safe_c_free(i8* {_cast})")
            out.append(f"  br label %{_skiplbl}")
            out.append(f"{_skiplbl}:")
            out.append(f"  store {_spill_llvm} null, {_spill_llvm}* {_addr}")
            owned_vars.discard(_spill_nm)
            for _sctx in scope_drop_stack:
                _sctx.get("body_decl_names", set()).discard(_spill_nm)
                _sctx.get("extra_ir_owned", [])
            return
        _ft = new_tmp()
        out.append(f"  {_ft} = icmp eq i8* {ssa_val}, null")
        _fskip = new_label("tmp_free_skip")
        _fdo   = new_label("tmp_free_do")
        out.append(f"  br i1 {_ft}, label %{_fskip}, label %{_fdo}")
        out.append(f"{_fdo}:")
        out.append(f"  call void @bhumi_safe_c_free(i8* {ssa_val})")
        out.append(f"  br label %{_fskip}")
        out.append(f"{_fskip}:")
        _spill_nm = _ar_spill_val_to_name.get(ssa_val)
        if _spill_nm is not None:
            _spill_res = symbol_table.lookup(_spill_nm)
            if _spill_res is not None:
                _spill_llvm, _ = _spill_res
                out.append(f"  store {_spill_llvm} {zero_const_for_llvm(_spill_llvm)}, {_spill_llvm}* %{_spill_nm}_addr")
            owned_vars.discard(_spill_nm)
            for _sctx in scope_drop_stack:
                _sctx.get("body_decl_names", set()).discard(_spill_nm)
    def _maybe_flush_deferred(e: Expr, ssa_name: str) -> None:
        if not isinstance(e, Var):
            return
        name = e.name
        cr = crumb_runtime.get(name)
        if not cr:
            return
        deferred = cr.get("_deferred_frees")
        if not deferred:
            return
        new_deferred = []
        for (vn, ssa_tmp, llvm_typ) in list(deferred):
            if ssa_tmp == ssa_name:
                cast_tmp = new_tmp()
                out.append(f"  {cast_tmp} = bitcast {llvm_typ} {ssa_tmp} to i8*")
                out.append(f"  call void @bhumi_free(i8* {cast_tmp})")
                _sym_df = symbol_table.lookup(vn)
                if _sym_df:
                    _ir_df = _sym_df[1]
                    _addr_df = f"@{_ir_df}" if _ir_df.startswith("@") else f"%{_ir_df}_addr"
                    out.append(f"  store {llvm_typ} null, {llvm_typ}* {_addr_df}")
                    _bep_df = binding_enum_payload.get(_ir_df)
                    if _bep_df is not None:
                        _bep_df_subj, _bep_df_en, _bep_df_vi, _bep_df_pty, _bep_df_slot = _bep_df
                        out.append(f"  store {_bep_df_pty} null, {_bep_df_pty}* {_bep_df_slot}")
                    for _ctx in scope_drop_stack:
                        _ctx.get("body_decl_names", set()).discard(vn)
                        _eiro = _ctx.get("extra_ir_owned", [])
                        _ctx["extra_ir_owned"] = [(_ir_nm, _ir_ty, _ir_src)
                            for _ir_nm, _ir_ty, _ir_src in _eiro
                            if _ir_nm != _ir_df
                        ]
                cr["owned"] = False
                if vn in owned_vars:
                    owned_vars.discard(vn)
            else:
                new_deferred.append((vn, ssa_tmp, llvm_typ))
        if new_deferred:
            cr["_deferred_frees"] = new_deferred
        else:
            cr.pop("_deferred_frees", None)
    global string_constants
    if isinstance(expr, Cast):
        dst_t = expr.typ
        dst_llvm = llvm_ty_of(dst_t)
        inner = expr.expr
        if isinstance(inner, IntLit):
            val = inner.value
            if dst_t == "string":
                return gen_expr(StrLit(str(val)), out)
            if dst_t == "float":
                return gen_expr(FloatLit(float(val)), out)
            if dst_t == "bool":
                return gen_expr(BoolLit(bool(val)), out)
            if dst_llvm.startswith("i"):
                bits = llvm_int_bitsize(dst_llvm)
                if bits:
                    masked = val & ((1 << bits) - 1)
                    tmp = new_tmp()
                    out.append(f"  {tmp} = add {dst_llvm} 0, {masked}")
                    return tmp
        if isinstance(inner, FloatLit):
            if dst_t == "string":
                return gen_expr(StrLit(f"{inner.value:.8e}"), out)
            if dst_t.startswith("int"):
                int_val = int(inner.value)
                tmp = new_tmp()
                dst_llvm = llvm_ty_of(dst_t)
                out.append(f"  {tmp} = add {dst_llvm} 0, {int_val}")
                return tmp
            if dst_t == "float":
                tmp = new_tmp()
                out.append(f"  {tmp} = fadd double 0.0, {inner.value:.8e}")
                return tmp
        if isinstance(inner, BoolLit):
            if dst_t == "string":
                return gen_expr(StrLit("true" if inner.value else "false"), out)
            if dst_t.startswith("int"):
                dst_llvm = llvm_ty_of(dst_t)
                tmp = new_tmp()
                out.append(f"  {tmp} = add {dst_llvm} 0, {1 if inner.value else 0}")
                return tmp
            if dst_t == "bool":
                tmp = new_tmp()
                out.append(f"  {tmp} = add i1 0, {1 if inner.value else 0}")
                return tmp
        if isinstance(inner, StrLit):
            if dst_t == "bool":
                bval = len(inner.value) != 0
                return gen_expr(BoolLit(bval), out)
            if dst_t.startswith("int"):
                try:
                    ival = int(inner.value, 0)
                    tmp = new_tmp()
                    dst_llvm = llvm_ty_of(dst_t)
                    out.append(f"  {tmp} = add {dst_llvm} 0, {ival}")
                    return tmp
                except Exception:
                    bhumi_report_error(
                        None, None, f"Cannot convert string '{inner.value}' to integer"
                    )
            if dst_t == "float":
                try:
                    fval = float(inner.value)
                    tmp = new_tmp()
                    fstr = f"{fval:.8e}"
                    out.append(f"  {tmp} = fadd double 0.0, {fstr}")
                    return tmp
                except Exception:
                    bhumi_report_error(
                        None, None, f"Cannot convert string '{inner.value}' to float"
                    )
        val = gen_expr(inner, out)
        src_t = infer_type(inner)
        src_llvm = llvm_ty_of(src_t)
        if src_t == dst_t:
            return val
        src_bits = llvm_int_bitsize(src_llvm)
        dst_bits = llvm_int_bitsize(dst_llvm)
        if src_bits and dst_bits:
            cast_tmp = new_tmp()
            if src_bits > dst_bits:
                out.append(f"  {cast_tmp} = trunc {src_llvm} {val} to {dst_llvm}")
            else:
                src_unsigned = is_unsigned_int_type(src_t)
                if src_unsigned:
                    out.append(f"  {cast_tmp} = zext {src_llvm} {val} to {dst_llvm}")
                else:
                    out.append(f"  {cast_tmp} = sext {src_llvm} {val} to {dst_llvm}")
            return cast_tmp
        if src_llvm.startswith("i") and dst_llvm == "double":
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = sitofp {src_llvm} {val} to double")
            return cast_tmp
        if src_llvm == "double" and dst_llvm.startswith("i"):
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = fptosi double {val} to {dst_llvm}")
            return cast_tmp
        if src_llvm == "double" and dst_llvm == "float":
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = fptrunc double {val} to float")
            return cast_tmp
        if src_llvm == "float" and dst_llvm == "double":
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = fpext float {val} to double")
            return cast_tmp
        if src_llvm.endswith("*") and dst_llvm.endswith("*"):
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = bitcast {src_llvm} {val} to {dst_llvm}")
            return cast_tmp
        if src_llvm == "i8*" and dst_llvm == "i1":
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = icmp ne i8* {val}, null")
            return cast_tmp
        if src_llvm == "i1" and dst_llvm.startswith("i") and dst_llvm != "i1":
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = zext i1 {val} to {dst_llvm}")
            return cast_tmp
        if src_llvm.startswith("i") and dst_llvm == "i1":
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = icmp ne {src_llvm} {val}, 0")
            return cast_tmp
        if (
            dst_llvm.endswith("*")
            and not src_llvm.endswith("*")
            and src_llvm.startswith("i")
        ):
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = inttoptr {src_llvm} {val} to {dst_llvm}")
            return cast_tmp
        if (
            src_llvm.endswith("*")
            and not dst_llvm.endswith("*")
            and dst_llvm.startswith("i")
        ):
            cast_tmp = new_tmp()
            out.append(f"  {cast_tmp} = ptrtoint {src_llvm} {val} to {dst_llvm}")
            return cast_tmp
        bhumi_report_error(None, None, f"Unsupported cast from {src_t} -> {dst_t}")
    if isinstance(expr, VAwaitExpr):
        bhumi_report_error(
            getattr(expr, "lineno", None),
            getattr(expr, "col", None),
            "vawait is not yet supported in codegen; use await instead",
        )
    if isinstance(expr, AwaitExpr):
        inner = expr.expr
        if isinstance(inner, Call):
            call_target = ensure_monomorph_call(inner, out)
            args_ir: List[str] = []
            concrete_fn = _func_name_map.get(call_target)
            if concrete_fn:
                for a, (param_typ, _) in zip(inner.args, concrete_fn.params):
                    tmpa = gen_expr(a, out)
                    ty_a = infer_type(a)
                    llvm_param_ty = llvm_ty_of(param_typ)
                    if tmpa is None:
                        args_ir.append(
                            f"{llvm_param_ty} {zero_const_for_llvm(llvm_param_ty)}"
                        )
                    else:
                        cast_tmp = emit_cast_value(tmpa, ty_a, param_typ, out)
                        args_ir.append(f"{llvm_param_ty} {cast_tmp}")
            else:
                for a in inner.args:
                    tmpa = gen_expr(a, out)
                    ty_a = infer_type(a)
                    llvm_ty = llvm_ty_of(ty_a)
                    if tmpa is None:
                        args_ir.append(f"{llvm_ty} {zero_const_for_llvm(llvm_ty)}")
                    else:
                        args_ir.append(f"{llvm_ty} {tmpa}")
            args_sig = ", ".join(args_ir)
            handle_tmp = new_tmp()
            struct_name = f"%async.{call_target}"
            if args_sig:
                out.append(
                    f"  {handle_tmp} = call {struct_name}* @{call_target}_init({args_sig})"
                )
            else:
                out.append(
                    f"  {handle_tmp} = call {struct_name}* @{call_target}_init()"
                )
            done_tmp = new_tmp()
            out.append(
                f"  {done_tmp} = call i1 @{call_target}_resume({struct_name}* {handle_tmp})"
            )
            cont_lbl = new_label("await_cont")
            suspend_lbl = new_label("await_suspend")
            out.append(f"  br i1 {done_tmp}, label %{cont_lbl}, label %{suspend_lbl}")
            out.append(f"{suspend_lbl}:")
            resume_ptr_tmp = new_tmp()
            out.append(
                f"  {resume_ptr_tmp} = bitcast i1 ({struct_name}*)* @{call_target}_resume to i8*"
            )
            handle_b_tmp = new_tmp()
            out.append(f"  {handle_b_tmp} = bitcast {struct_name}* {handle_tmp} to i8*")
            out.append(
                f"  call void @bhumi_register_async(i8* {resume_ptr_tmp}, i8* {handle_b_tmp})"
            )
            out.append(f"  call void @bhumi_block_until_complete(i8* {handle_b_tmp})")
            out.append(f"  br label %{cont_lbl}")
            out.append(f"{cont_lbl}:")
            base_fn = _func_name_map.get(call_target)
            ret_llvm = llvm_ty_of(base_fn.ret_type) if base_fn else "i64"
            res_ptr = new_tmp()
            out.append(
                f"  {res_ptr} = getelementptr inbounds {struct_name}, {struct_name}* {handle_tmp}, i32 0, i32 1"
            )
            await_ret = new_tmp()
            out.append(f"  {await_ret} = load {ret_llvm}, {ret_llvm}* {res_ptr}")
            _handle_free_tmp = new_tmp()
            out.append(f"  {_handle_free_tmp} = bitcast {struct_name}* {handle_tmp} to i8*")
            out.append(f"  call void @bhumi_free(i8* {_handle_free_tmp})")
            return await_ret
        else:
            out.append("  ; await of non-call expression is not supported here")
            return None
    if isinstance(expr, UnaryOp):
        val = gen_expr(expr.expr, out)
        ty = infer_type(expr.expr)
        llvm_ty = llvm_ty_of(ty)
        tmp = new_tmp()
        if expr.op == "-":
            if llvm_ty == "double" or ty == "float":
                out.append(f"  {tmp} = fsub double 0.0, {val}")
            else:
                out.append(f"  {tmp} = sub {llvm_ty} 0, {val}")
            _maybe_flush_deferred(expr.expr, val)
            return tmp
        elif expr.op == "+":
            return val
        elif expr.op == "!":
            if llvm_ty == "i1":
                out.append(f"  {tmp} = xor i1 {val}, 1")
                _maybe_flush_deferred(expr.expr, val)
                return tmp
            else:
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Unary '!' requires bool operand, found {ty}",
                )
        elif expr.op == "~":
            if llvm_ty.startswith("i"):
                if llvm_ty == "i1":
                    out.append(f"  {tmp} = xor i1 {val}, 1")
                else:
                    out.append(f"  {tmp} = xor {llvm_ty} {val}, -1")
                _maybe_flush_deferred(expr.expr, val)
                return tmp
            else:
                bhumi_report_error(
                    None, None, f"Unary '~' requires integer operand, found {ty}"
                )
        else:
            bhumi_report_error(None, None, f"Unsupported unary operator: {expr.op}")
    if isinstance(expr, UnaryDeref):
        ptr_val = gen_expr(expr.ptr, out)
        ptr_type = infer_type(expr.ptr)
        if not ptr_type.endswith("*"):
            bhumi_report_error(
                None, None, f"Dereferencing non-pointer type '{ptr_type}'"
            )
        pointee_lang = ptr_type[:-1]
        if pointee_lang == "void":
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                "Cannot generate code to dereference 'void*' without an explicit cast ...",
            )
        llvm_pointee = llvm_ty_of(pointee_lang)
        null_cmp = new_tmp()
        fail_lbl = new_label("null_fail")
        ok_lbl = new_label("null_ok")
        out.append(f"  {null_cmp} = icmp eq {llvm_pointee}* {ptr_val}, null")
        out.append(f"  br i1 {null_cmp}, label %{fail_lbl}, label %{ok_lbl}")
        out.append(f"{fail_lbl}:")
        out.append(f"  call void @bhumi_null_abort()")
        out.append(f"  unreachable")
        out.append(f"{ok_lbl}:")
        tmp = new_tmp()
        out.append(f"  {tmp} = load {llvm_pointee}, {llvm_pointee}* {ptr_val}")
        _maybe_flush_deferred(expr.ptr, tmp)
        return tmp
    if isinstance(expr, AddressOf):
        inner = expr.expr
        if isinstance(inner, UnaryDeref):
            return gen_expr(inner.ptr, out)
        if isinstance(inner, Var):
            res = symbol_table.lookup(inner.name)
            if res is None:
                bhumi_report_error(
                    getattr(inner, "lineno", None),
                    getattr(inner, "col", None),
                    f"Undefined variable: {inner.name}",
                )
            _, ir_name = res
            if ir_name.startswith("@"):
                return ir_name
            return f"%{ir_name}_addr"
        if isinstance(inner, FieldAccess):
            base = inner.base
            field = inner.field
            base_raw = infer_type(base)
            base_name = base_raw
            if base_name.endswith("*"):
                base_name = base_name[:-1]
            if base_name.startswith("%struct."):
                base_name = base_name[len("%struct.") :]
            if base_name not in struct_field_map:
                bhumi_report_error(
                    getattr(base, "lineno", None),
                    getattr(base, "col", None),
                    f"Struct type '{base_name}' not found",
                )
            fields = struct_field_map[base_name]
            field_dict = dict(fields)
            if field not in field_dict:
                bhumi_report_error(
                    getattr(inner, "lineno", None),
                    getattr(inner, "col", None),
                    f"Field '{field}' not in struct '{base_name}'",
                )
            index = list(field_dict.keys()).index(field)
            if isinstance(base, Var):
                res = symbol_table.lookup(base.name)
                if res is None:
                    bhumi_report_error(
                        getattr(base, "lineno", None),
                        getattr(base, "col", None),
                        f"Undefined variable: {base.name}",
                    )
                _, base_ir_name = res
                base_ty = infer_type(base)
                if base_ty.endswith("*"):
                    if base_ir_name.startswith("@"):
                        base_val = base_ir_name
                    elif base_ir_name.startswith("%"):
                        base_val = f"{base_ir_name}_addr"
                    else:
                        base_val = f"%{base_ir_name}_addr"
                    llvm_base_llvm_ty = llvm_ty_of(base_ty)
                    is_null = new_tmp()
                    fail_lbl = new_label("null_fail")
                    ok_lbl = new_label("null_ok")
                    out.append(
                        f"  {is_null} = icmp eq {llvm_base_llvm_ty} {base_val}, null"
                    )
                    out.append(f"  br i1 {is_null}, label %{fail_lbl}, label %{ok_lbl}")
                    out.append(f"{fail_lbl}:")
                    out.append(f"  call void @bhumi_null_abort()")
                    out.append(f"  unreachable")
                    out.append(f"{ok_lbl}:")
                    ptr = new_tmp()
                    out.append(
                        f"  {ptr} = getelementptr inbounds %struct.{base_name}, %struct.{base_name}* {base_val}, i32 0, i32 {index}"
                    )
                    return ptr
                else:
                    if base_ir_name.startswith("@"):
                        base_ptr_token = base_ir_name
                    else:
                        base_ptr_token = f"%{base_ir_name}_addr"
                    ptr = new_tmp()
                    out.append(
                        f"  {ptr} = getelementptr inbounds %struct.{base_name}, %struct.{base_name}* {base_ptr_token}, i32 0, i32 {index}"
                    )
                    return ptr
            else:
                base_val = gen_expr(base, out)
                base_ty = infer_type(base)
                if not base_ty.endswith("*"):
                    bhumi_report_error(
                        None,
                        None,
                        "Taking address of a field on an rvalue struct is not supported",
                    )
                if (
                    base_val.startswith("%")
                    and not base_val.endswith("_addr")
                    and not base_val.startswith("%struct.")
                ):
                    tmp_addr = new_tmp()
                    _entry_alloca_buf.append(f"  {tmp_addr} = alloca %struct.{base_name}")
                    out.append(
                        f"  store %struct.{base_name} {base_val}, %struct.{base_name}* {tmp_addr}"
                    )
                    base_val_ptr = tmp_addr
                else:
                    base_val_ptr = base_val
                llvm_base_llvm_ty = llvm_ty_of(base_ty)
                is_null = new_tmp()
                fail_lbl = new_label("null_fail")
                ok_lbl = new_label("null_ok")
                out.append(
                    f"  {is_null} = icmp eq {llvm_base_llvm_ty} {base_val_ptr}, null"
                )
                out.append(f"  br i1 {is_null}, label %{fail_lbl}, label %{ok_lbl}")
                out.append(f"{fail_lbl}:")
                out.append(f"  call void @bhumi_null_abort()")
                out.append(f"  unreachable")
                out.append(f"{ok_lbl}:")
                ptr = new_tmp()
                out.append(
                    f"  {ptr} = getelementptr inbounds %struct.{base_name}, %struct.{base_name}* {base_val_ptr}, i32 0, i32 {index}"
                )
                return ptr
        if isinstance(inner, Index):
            if not isinstance(inner.array, Var):
                bhumi_report_error(
                    getattr(inner, "lineno", None),
                    getattr(inner, "col", None),
                    f"Only direct variable array indexing is supported for address-of, got: {inner.array}",
                )
            var_name = inner.array.name
            idx_val = gen_expr(inner.index, out)
            arr_info = symbol_table.lookup(var_name)
            if not arr_info:
                bhumi_report_error(
                    getattr(inner.array, "lineno", None),
                    getattr(inner.array, "col", None),
                    f"Undefined array: {var_name}",
                )
            llvm_ty, name = arr_info
            idx_ty = infer_type(inner.index)
            idx_llvm = llvm_ty_of(idx_ty)
            if idx_llvm != "i32":
                idx_cast = new_tmp()
                if (
                    idx_llvm.startswith("i")
                    and idx_llvm[1:].isdigit()
                    and int(idx_llvm[1:]) > 32
                ):
                    out.append(f"  {idx_cast} = trunc {idx_llvm} {idx_val} to i32")
                else:
                    out.append(f"  {idx_cast} = sext {idx_llvm} {idx_val} to i32")
            else:
                idx_cast = idx_val
            if llvm_ty.startswith("["):
                if name.startswith("@"):
                    len_addr = f"@{var_name}_len"
                    arr_addr_token = name
                else:
                    len_addr = f"%{var_name}_len"
                    arr_addr_token = f"%{name}_addr"
                len_val = new_tmp()
                out.append(f"  {len_val} = load i32, i32* {len_addr}")
                ok = new_tmp()
                out.append(f"  {ok} = icmp ult i32 {idx_cast}, {len_val}")
                fail_lbl = new_label("oob_fail")
                ok_lbl = new_label("oob_ok")
                out.append(f"  br i1 {ok}, label %{ok_lbl}, label %{fail_lbl}")
                out.append(f"{fail_lbl}:")
                out.append(f"  call void @bhumi_oob_abort()")
                out.append(f"  unreachable")
                out.append(f"{ok_lbl}:")
                gep_tmp = new_tmp()
                out.append(
                    f"  {gep_tmp} = getelementptr inbounds {llvm_ty}, {llvm_ty}* {arr_addr_token}, i32 0, i32 {idx_cast}"
                )
                return gep_tmp
            elif llvm_ty.endswith("*"):
                if name.startswith("@"):
                    ptr_load = new_tmp()
                    out.append(f"  {ptr_load} = load {llvm_ty}, {llvm_ty}* {name}")
                else:
                    ptr_load = new_tmp()
                    out.append(
                        f"  {ptr_load} = load {llvm_ty}, {llvm_ty}* %{name}_addr"
                    )
                is_null_tmp = new_tmp()
                out.append(f"  {is_null_tmp} = icmp eq {llvm_ty} {ptr_load}, null")
                null_fail = new_label("null_ptr_fail")
                null_ok = new_label("null_ptr_ok")
                out.append(
                    f"  br i1 {is_null_tmp}, label %{null_fail}, label %{null_ok}"
                )
                out.append(f"{null_fail}:")
                out.append(f"  call void @bhumi_null_abort()")
                out.append(f"  unreachable")
                out.append(f"{null_ok}:")
                idx_i64 = new_tmp()
                if idx_llvm.startswith("i") and idx_llvm[1:].isdigit():
                    bits = int(idx_llvm[1:]) if idx_llvm[1:].isdigit() else 32
                    if bits < 64:
                        if is_unsigned_int_type(idx_ty):
                            out.append(
                                f"  {idx_i64} = zext {idx_llvm} {idx_val} to i64"
                            )
                        else:
                            out.append(
                                f"  {idx_i64} = sext {idx_llvm} {idx_val} to i64"
                            )
                    else:
                        out.append(f"  {idx_i64} = trunc {idx_llvm} {idx_val} to i64")
                else:
                    out.append(f"  {idx_i64} = zext i32 {idx_val} to i64")
                bit_tmp = new_tmp()
                out.append(f"  {bit_tmp} = bitcast {llvm_ty} {ptr_load} to i8*")
                size_i64 = new_tmp()
                out.append(f"  {size_i64} = call i64 @bhumi_alloc_size(i8* {bit_tmp})")
                ok64 = new_tmp()
                out.append(f"  {ok64} = icmp ult i64 {idx_i64}, {size_i64}")
                fail_lbl = new_label("oob_fail")
                ok_lbl = new_label("oob_ok")
                out.append(f"  br i1 {ok64}, label %{ok_lbl}, label %{fail_lbl}")
                out.append(f"{fail_lbl}:")
                out.append(f"  call void @bhumi_oob_abort()")
                out.append(f"  unreachable")
                out.append(f"{ok_lbl}:")
                gep_tmp = new_tmp()
                base_ty = extract_array_base_type(llvm_ty)
                out.append(
                    f"  {gep_tmp} = getelementptr inbounds {base_ty}, {base_ty}* {ptr_load}, i32 {idx_cast}"
                )
                return gep_tmp
            else:
                bhumi_report_error(
                    getattr(inner, "lineno", None),
                    getattr(inner, "col", None),
                    "Address-of index not supported for this array kind",
                )
        bhumi_report_error(
            getattr(expr, "lineno", None),
            getattr(expr, "col", None),
            "Address-of not supported for this expression form",
        )
    if isinstance(expr, IntLit):
        tmp = new_tmp()
        inferred = infer_type(expr)
        llvm_ty = type_map[inferred]
        out.append(f"  {tmp} = add {llvm_ty} 0, {expr.value}")
        return tmp
    if isinstance(expr, NullLit):
        tmp = new_tmp()
        out.append(f"  {tmp} = bitcast i8* null to i8*")
        return tmp
    if isinstance(expr, Call) and expr.name == "BhumiCompiler.get_args":
        tmp = new_tmp()
        out.append(f"  {tmp} = load i8**, i8*** @__argv_ptr")
        return tmp
    if isinstance(expr, TypeofExpr):
        raw = infer_type(expr.expr)
        def _pretty_mono(t: str) -> str:
            is_ptr = t.endswith("*")
            base = t[:-1] if is_ptr else t
            if base.startswith("%enum."):
                base = base[len("%enum."):]
            elif base.startswith("%struct."):
                base = base[len("%struct."):]
            if "__mono__" in base:
                enum_base, _, type_arg = base.partition("__mono__")
                type_arg = type_arg.replace("_ptr", "*")
                base = f"{enum_base}<{type_arg}>"
            return base
        if raw.startswith("%struct.") or raw.startswith("%enum.") or "__mono__" in raw or raw.endswith("*"):
            out_str = _pretty_mono(raw)
        else:
            out_str = raw
        label = f"@.str{len(string_constants)}"
        esc = out_str.replace('"', r"\"")
        byte_len = len(out_str.encode("utf-8")) + 1
        string_constants.append(
            f'{label} = private unnamed_addr constant [{byte_len} x i8] c"{esc}\\00"'
        )
        tmp = new_tmp()
        out.append(
            f"  {tmp} = getelementptr inbounds [{byte_len} x i8], "
            f"[{byte_len} x i8]* {label}, i32 0, i32 0"
        )
        return tmp
    if isinstance(expr, FloatLit):
        tmp = new_tmp()
        float_val = format_float(expr.value)
        out.append(f"  {tmp} = fadd double 0.0, {float_val}")
        return tmp
    if isinstance(expr, BoolLit):
        tmp = new_tmp()
        val = 1 if expr.value else 0
        out.append(f"  {tmp} = add i1 0, {val}")
        return tmp
    if isinstance(expr, Ternary):
        cond_val = gen_expr(expr.cond, out)
        then_lbl = new_label("tern_then")
        else_lbl = new_label("tern_else")
        end_lbl = new_label("tern_end")
        out.append(f"  br i1 {cond_val}, label %{then_lbl}, label %{else_lbl}")
        out.append(f"{then_lbl}:")
        then_val = gen_expr(expr.then_expr, out)
        then_tmp = new_tmp()
        then_ty = type_map[infer_type(expr.then_expr)]
        out.append(f"  {then_tmp} = add {then_ty} 0, {then_val}")
        out.append(f"  br label %{end_lbl}")
        out.append(f"{else_lbl}:")
        else_val = gen_expr(expr.else_expr, out)
        else_tmp = new_tmp()
        else_ty = type_map[infer_type(expr.else_expr)]
        out.append(f"  {else_tmp} = add {else_ty} 0, {else_val}")
        out.append(f"  br label %{end_lbl}")
        out.append(f"{end_lbl}:")
        phi_tmp = new_tmp()
        out.append(
            f"  {phi_tmp} = phi {then_ty} [{then_tmp}, %{then_lbl}], [{else_tmp}, %{else_lbl}]"
        )
        _maybe_flush_deferred(expr.then_expr, then_val)
        _maybe_flush_deferred(expr.else_expr, else_val)
        return phi_tmp
    if isinstance(expr, Index):
        if not isinstance(expr.array, Var):
            bhumi_report_error(
                getattr(expr.array, "lineno", None),
                getattr(expr.array, "col", None),
                f"Only direct variable array indexing is supported, got: {expr.array}",
            )
        var_name = expr.array.name
        idx = gen_expr(expr.index, out)
        arr_info = symbol_table.lookup(var_name)
        if not arr_info:
            bhumi_report_error(
                getattr(expr.array, "lineno", None),
                getattr(expr.array, "col", None),
                f"Undefined array: {var_name}",
            )
        llvm_ty, name = arr_info
        base_ty = extract_array_base_type(llvm_ty)
        tmp_ptr = new_tmp()
        tmp_val = new_tmp()
        idx_ty = infer_type(expr.index)
        idx_llvm = type_map[idx_ty]
        if idx_llvm != "i32":
            idx_cast = new_tmp()
            if idx_llvm.startswith("i") and int(idx_llvm[1:]) > 32:
                out.append(f"  {idx_cast} = trunc {idx_llvm} {idx} to i32")
            else:
                out.append(f"  {idx_cast} = sext {idx_llvm} {idx} to i32")
        else:
            idx_cast = idx
        if llvm_ty.startswith("["):
            if name.startswith("@"):
                len_addr = f"@{var_name}_len"
                arr_addr_token = name
            else:
                len_addr = f"%{var_name}_len"
                arr_addr_token = f"%{name}_addr"
            len_val = new_tmp()
            out.append(f"  {len_val} = load i32, i32* {len_addr}")
            ok = new_tmp()
            out.append(f"  {ok} = icmp ult i32 {idx_cast}, {len_val}")
            fail_lbl = new_label("oob_fail")
            ok_lbl = new_label("oob_ok")
            out.append(f"  br i1 {ok}, label %{ok_lbl}, label %{fail_lbl}")
            out.append(f"{fail_lbl}:")
            out.append(f"  call void @bhumi_oob_abort()")
            out.append(f"  unreachable")
            out.append(f"{ok_lbl}:")
            out.append(
                f"  {tmp_ptr} = getelementptr inbounds {llvm_ty}, {llvm_ty}* {arr_addr_token}, i32 0, i32 {idx_cast}"
            )
        elif llvm_ty.endswith("*"):
            if name.startswith("@"):
                ptr_load = new_tmp()
                out.append(f"  {ptr_load} = load {llvm_ty}, {llvm_ty}* {name}")
            else:
                ptr_load = new_tmp()
                out.append(f"  {ptr_load} = load {llvm_ty}, {llvm_ty}* %{name}_addr")
            is_null_tmp = new_tmp()
            out.append(f"  {is_null_tmp} = icmp eq {llvm_ty} {ptr_load}, null")
            null_fail = new_label("null_ptr_fail")
            null_ok = new_label("null_ptr_ok")
            out.append(f"  br i1 {is_null_tmp}, label %{null_fail}, label %{null_ok}")
            out.append(f"{null_fail}:")
            out.append(f"  call void @bhumi_null_abort()")
            out.append(f"  unreachable")
            out.append(f"{null_ok}:")
            bit_tmp = new_tmp()
            out.append(f"  {bit_tmp} = bitcast {llvm_ty} {ptr_load} to i8*")
            size_i64 = new_tmp()
            out.append(f"  {size_i64} = call i64 @bhumi_alloc_size(i8* {bit_tmp})")
            if idx_llvm != "i64":
                idx_i64 = new_tmp()
                if idx_llvm.startswith("i"):
                    bits = int(idx_llvm[1:]) if idx_llvm[1:].isdigit() else 32
                    if bits < 64:
                        if is_unsigned_int_type(idx_ty):
                            out.append(f"  {idx_i64} = zext {idx_llvm} {idx} to i64")
                        else:
                            out.append(f"  {idx_i64} = sext {idx_llvm} {idx} to i64")
                    else:
                        out.append(f"  {idx_i64} = trunc {idx_llvm} {idx} to i64")
                else:
                    out.append(f"  {idx_i64} = zext i32 {idx} to i64")
            else:
                idx_i64 = idx
            ok64 = new_tmp()
            out.append(f"  {ok64} = icmp ult i64 {idx_i64}, {size_i64}")
            fail_lbl = new_label("oob_fail")
            ok_lbl = new_label("oob_ok")
            out.append(f"  br i1 {ok64}, label %{ok_lbl}, label %{fail_lbl}")
            out.append(f"{fail_lbl}:")
            out.append(f"  call void @bhumi_oob_abort()")
            out.append(f"  unreachable")
            out.append(f"{ok_lbl}:")
            out.append(
                f"  {tmp_ptr} = getelementptr inbounds {base_ty}, {base_ty}* {ptr_load}, i32 {idx_cast}"
            )
        else:
            out.append(f"  call void @bhumi_oob_abort()")
            out.append(f"  unreachable")
        out.append(f"  {tmp_val} = load {base_ty}, {base_ty}* {tmp_ptr}")
        _maybe_flush_deferred(expr.index, idx)
        return tmp_val
    if isinstance(expr, StrLit):
        tmp = new_tmp()
        label = f"@.str{len(string_constants)}"
        raw = expr.value
        esc = ""
        for ch in raw:
            code = ord(ch)
            if ch == "\n":
                esc += r"\0A"
            elif ch == "\r":
                esc += r"\0D"
            elif ch == "\t":
                esc += r"\09"
            elif ch == "\\":
                esc += r"\\"
            elif ch == '"':
                esc += r"\22"
            elif 32 <= code <= 126:
                esc += ch
            else:
                esc += f"\\{code:02X}"
        byte_len = len(raw.encode("utf-8")) + 1
        string_constants.append(
            f'{label} = private unnamed_addr constant [{byte_len} x i8] c"{esc}\\00"'
        )
        out.append(
            f"  {tmp} = getelementptr inbounds [{byte_len} x i8], "
            f"[{byte_len} x i8]* {label}, i32 0, i32 0"
        )
        return tmp
    if isinstance(expr, Var):
        result = symbol_table.lookup(expr.name)
        if result is None:
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Undefined variable: {expr.name}",
            )
        typ, name = result
        tmp = new_tmp()
        if name.startswith("@"):
            out.append(f"  {tmp} = load {typ}, {typ}* {name}")
        elif name.startswith("%"):
            out.append(f"  {tmp} = load {typ}, {typ}* {name}_addr")
        else:
            out.append(f"  {tmp} = load {typ}, {typ}* %{name}_addr")
        vn = expr.name
        cr = crumb_runtime.get(vn)
        if cr is not None:
            cr["rc"] = int(cr.get("rc", 0) or 0) + 1
            cr["owned"] = bool(cr.get("owned", False)) or (vn in owned_vars)
            rmax = cr.get("rmax")
            wmax = cr.get("wmax")
            if rmax is not None and cr["rc"] == rmax and cr.get("owned"):
                cr.setdefault("_deferred_frees", []).append((vn, tmp, typ))
                cr["owned"] = False
                owned_vars.discard(vn)
                if wmax is None:
                    print(
                        f"[Bhumi] Warning: crumble '{vn}' autofreed after {rmax} read(s); "
                        f"no write limit (!w) was set, {cr.get('wc', 0)} write(s) consumed. "
                        f"Set crumble({vn})!w=<count>; to silence this.",
                        file=__import__("sys").stderr,
                    )
        return tmp
    if isinstance(expr, BinOp):
        lhs = gen_expr(expr.left, out)
        rhs = gen_expr(expr.right, out)
        ty = infer_type(expr.left)
        if ty == "string" and expr.op == "+":
            len_l = new_tmp()
            out.append(f"  {len_l} = call i64 @strlen(i8* {lhs})")
            len_r = new_tmp()
            out.append(f"  {len_r} = call i64 @strlen(i8* {rhs})")
            total = new_tmp()
            out.append(f"  {total} = add i64 {len_l}, {len_r}")
            alloc_size = new_tmp()
            out.append(f"  {alloc_size} = add i64 {total}, 1")
            raw = new_tmp()
            out.append(f"  {raw} = call i8* @malloc(i64 {alloc_size})")
            out.append(
                f"  call void @llvm.memcpy.p0i8.p0i8.i64("
                f"i8* {raw}, i8* {lhs}, i64 {len_l}, i1 false)"
            )
            dest_rhs = new_tmp()
            out.append(
                f"  {dest_rhs} = getelementptr inbounds i8, i8* {raw}, i64 {len_l}"
            )
            out.append(
                f"  call void @llvm.memcpy.p0i8.p0i8.i64("
                f"i8* {dest_rhs}, i8* {rhs}, i64 {len_r}, i1 false)"
            )
            term_ptr = new_tmp()
            out.append(
                f"  {term_ptr} = getelementptr inbounds i8, i8* {raw}, i64 {total}"
            )
            out.append(f"  store i8 0, i8* {term_ptr}")
            _maybe_flush_deferred(expr.left, lhs)
            _maybe_flush_deferred(expr.right, rhs)
            _emit_free_if_temp(expr.left, lhs)
            _emit_free_if_temp(expr.right, rhs)
            return raw
        lt = infer_type(expr.left)
        rt = infer_type(expr.right)
        def _ptr_arith_offset(offset_val: str, offset_type: str) -> str:
            off_llvm = llvm_ty_of(offset_type)
            if off_llvm == "i64":
                return offset_val
            cast_t = new_tmp()
            sign = "z" if is_unsigned_int_type(offset_type) else "s"
            out.append(f"  {cast_t} = {sign}ext {off_llvm} {offset_val} to i64")
            return cast_t
        if lt.endswith("*") and not rt.endswith("*") and expr.op in {"+", "-"}:
            llvm_ptr_ty = llvm_ty_of(lt)
            base_ty = llvm_ptr_ty[:-1]
            offset = _ptr_arith_offset(rhs, rt)
            if expr.op == "-":
                neg_t = new_tmp()
                out.append(f"  {neg_t} = sub i64 0, {offset}")
                offset = neg_t
            tmp = new_tmp()
            out.append(f"  {tmp} = getelementptr inbounds {base_ty}, {llvm_ptr_ty} {lhs}, i64 {offset}")
            _maybe_flush_deferred(expr.left, lhs)
            _maybe_flush_deferred(expr.right, rhs)
            return tmp
        if rt.endswith("*") and not lt.endswith("*") and expr.op == "+":
            llvm_ptr_ty = llvm_ty_of(rt)
            base_ty = llvm_ptr_ty[:-1]
            offset = _ptr_arith_offset(lhs, lt)
            tmp = new_tmp()
            out.append(f"  {tmp} = getelementptr inbounds {base_ty}, {llvm_ptr_ty} {rhs}, i64 {offset}")
            _maybe_flush_deferred(expr.left, lhs)
            _maybe_flush_deferred(expr.right, rhs)
            return tmp
        if lt.endswith("*") and rt.endswith("*") and lt == rt and expr.op == "-":
            lhs_int = new_tmp()
            rhs_int = new_tmp()
            llvm_ptr_ty = llvm_ty_of(lt)
            out.append(f"  {lhs_int} = ptrtoint {llvm_ptr_ty} {lhs} to i64")
            out.append(f"  {rhs_int} = ptrtoint {llvm_ptr_ty} {rhs} to i64")
            diff_bytes = new_tmp()
            out.append(f"  {diff_bytes} = sub i64 {lhs_int}, {rhs_int}")
            base_ty = llvm_ptr_ty[:-1]
            null_t = new_tmp()
            size_t = new_tmp()
            out.append(f"  {null_t} = getelementptr inbounds {base_ty}, {llvm_ptr_ty} null, i32 1")
            out.append(f"  {size_t} = ptrtoint {llvm_ptr_ty} {null_t} to i64")
            tmp = new_tmp()
            out.append(f"  {tmp} = sdiv i64 {diff_bytes}, {size_t}")
            _maybe_flush_deferred(expr.left, lhs)
            _maybe_flush_deferred(expr.right, rhs)
            return tmp
        common_t = unify_types(lt, rt)
        if common_t is None:
            bhumi_report_error(
                None,
                None,
                f"Cannot unify operand types for '{expr.op}': left={lt}, right={rt}",
            )
        llvm_ty = llvm_ty_of(common_t)
        tmp = new_tmp()
        if expr.op == "%":
            if llvm_ty in ("double", "float"):
                op = "frem"
            else:
                op = "urem" if is_unsigned_int_type(common_t) else "srem"
            out.append(f"  {tmp} = {op} {llvm_ty} {lhs}, {rhs}")
            _maybe_flush_deferred(expr.left, lhs)
            _maybe_flush_deferred(expr.right, rhs)
            return tmp
        if expr.op in {"&&", "||"}:
            out.append(
                f"  {tmp} = {'and' if expr.op == '&&' else 'or'} {llvm_ty} {lhs}, {rhs}"
            )
            _maybe_flush_deferred(expr.left, lhs)
            _maybe_flush_deferred(expr.right, rhs)
            return tmp
        if llvm_ty in ("double", "float"):
            op_map = {
                "+": "fadd",
                "-": "fsub",
                "*": "fmul",
                "/": "fdiv",
                "==": "fcmp oeq",
                "!=": "fcmp one",
                "<": "fcmp olt",
                "<=": "fcmp ole",
                ">": "fcmp ogt",
                ">=": "fcmp oge",
            }
            op = op_map.get(expr.op)
            if not op:
                bhumi_report_error(
                    None,
                    None,
                    f"Unsupported float operator '{expr.op}' for type {common_t}",
                )
            out.append(f"  {tmp} = {op} {llvm_ty} {lhs}, {rhs}")
            _maybe_flush_deferred(expr.left, lhs)
            _maybe_flush_deferred(expr.right, rhs)
            return tmp
        if llvm_ty.startswith("i"):
            unsigned = is_unsigned_int_type(common_t)
            if expr.op in {"+", "-", "*"}:
                op = {"+": "add", "-": "sub", "*": "mul"}[expr.op]
            elif expr.op == "/":
                op = "udiv" if unsigned else "sdiv"
            elif expr.op == "%":
                op = "urem" if unsigned else "srem"
            elif expr.op in {"==", "!="}:
                op = "icmp " + ("eq" if expr.op == "==" else "ne")
            elif expr.op in {"<", "<=", ">", ">="}:
                op = {
                    "<": "icmp ult" if unsigned else "icmp slt",
                    "<=": "icmp ule" if unsigned else "icmp sle",
                    ">": "icmp ugt" if unsigned else "icmp sgt",
                    ">=": "icmp uge" if unsigned else "icmp sge",
                }[expr.op]
            elif expr.op in {"&", "|", "^", "<<"}:
                op = {"&": "and", "|": "or", "^": "xor", "<<": "shl"}[expr.op]
            elif expr.op == ">>":
                op = "lshr" if unsigned else "ashr"
            else:
                bhumi_report_error(
                    None,
                    None,
                    f"Unsupported integer operator '{expr.op}' for type {common_t}",
                )
            out.append(f"  {tmp} = {op} {llvm_ty} {lhs}, {rhs}")
            _maybe_flush_deferred(expr.left, lhs)
            _maybe_flush_deferred(expr.right, rhs)
            return tmp
        bhumi_report_error(
            None,
            None,
            f"Unsupported binary operator '{expr.op}' for operand types: left={lt}, right={rt}, common={common_t}",
        )
    if isinstance(expr, Call):
        qualified_enum = None
        variant_name = expr.name
        if "->" in expr.name:
            qualified_enum, variant_name = expr.name.split("->", 1)
        args_ir: List[str] = []
        arg_types: List[str] = []
        arg_vals: List[str] = []
        _variant_arg_expected: List[Optional[str]] = [None] * len(expr.args)
        if "->" in expr.name and expected is not None:
            _gm_inner = re.fullmatch(r"[A-Za-z_]\w*<(.+)>", expected.rstrip("*"))
            if _gm_inner:
                _inner_types = [p.strip() for p in _gm_inner.group(1).split(",")]
                for _i in range(min(len(_variant_arg_expected), len(_inner_types))):
                    _variant_arg_expected[_i] = _inner_types[_i]
        for _i, arg in enumerate(expr.args):
            a = gen_expr(arg, out, expected=_variant_arg_expected[_i])
            ty2 = infer_type(arg)
            arg_types.append(ty2)
            arg_vals.append(a)
        def _is_enum_variant_name(name):
            bare = name.split("->")[-1] if "->" in name else name
            for _ev_variants in enum_variant_map.values():
                for _ev_vname, _ in _ev_variants:
                    if _ev_vname == bare:
                        return True
            return False
        if _is_enum_variant_name(expr.name):
            for _ot_arg, _ot_ty in zip(expr.args, arg_types):
                if (
                    isinstance(_ot_arg, Var)
                    and _ot_arg.name in owned_vars
                    and _ot_ty is not None
                    and (_ot_ty == "string" or _ot_ty.endswith("*"))
                ):
                    owned_vars.discard(_ot_arg.name)
        if scope_drop_stack and not _is_enum_variant_name(expr.name):
            for _spill_i, (_spill_arg, _spill_val, _spill_ty) in enumerate(
                zip(expr.args, arg_vals, arg_types)
            ):
                if not isinstance(_spill_arg, Call):
                    continue
                _spill_nown = (
                    _spill_arg.name in _NOWN_BUILTIN_FUNCS
                    or getattr(
                        _func_name_map.get(_spill_arg.name), "is_nown", False
                    )
                )
                if _spill_nown:
                    continue
                if _spill_ty is None or not (
                    _spill_ty == "string" or _spill_ty.endswith("*")
                ):
                    continue
                _spill_llvm_ty = llvm_ty_of(_spill_ty)
                _spill_id = new_tmp()[1:]
                _spill_name = f"__ar_anon_{_spill_id}"
                _entry_alloca_buf.append(
                    f"  %{_spill_name}_addr = alloca {_spill_llvm_ty}"
                )
                _entry_alloca_buf.append(
                    f"  store {_spill_llvm_ty} null, {_spill_llvm_ty}* %{_spill_name}_addr"
                )
                out.append(
                    f"  store {_spill_llvm_ty} {_spill_val}, {_spill_llvm_ty}* %{_spill_name}_addr"
                )
                symbol_table.declare(_spill_name, _spill_llvm_ty, _spill_name)
                owned_vars.add(_spill_name)
                scope_drop_stack[-1]["body_decl_names"].add(_spill_name)
                _ar_spilled_ssa_vals.add(_spill_val)
                _ar_spill_val_to_name[_spill_val] = _spill_name
                _spill_callee_fn = _func_name_map.get(_spill_arg.name)
                if _spill_callee_fn is not None and getattr(_spill_callee_fn, "is_extern", False):
                    _extern_spill_names.add(_spill_name)
        candidates = []
        for ename, variants in enum_variant_map.items():
            if "__mono__" in ename:
                continue
            for idx, (vname, payload) in enumerate(variants):
                if vname == variant_name and (
                        qualified_enum is None or ename == qualified_enum
                ):
                    candidates.append((ename, idx, payload))
        gm = globals().get("variant_map_global")
        if gm and expr.name in gm:
            existing_enames = {c[0] for c in candidates}
            for ename, payload in gm[expr.name]:
                if ename in existing_enames:
                    continue
                if "__mono__" in ename:
                    continue
                if qualified_enum is not None and ename != qualified_enum:
                    continue
                for idx, (vname2, payload2) in enumerate(enum_variant_map.get(ename, [])):
                    if vname2 == expr.name:
                        candidates.append((ename, idx, payload2))
                        break
        found_enum = None
        found_variant_idx = None
        found_variant_payload = None
        if candidates:
            if len(candidates) == 1:
                found_enum, found_variant_idx, found_variant_payload = candidates[0]
            else:
                use_site_line = getattr(expr, "lineno", None)
                use_site_col = getattr(expr, "col", None)
                msg_lines = []
                msg_lines.append(f"ambiguous enum variant '{variant_name}'")
                msg_lines.append("")
                msg_lines.append(f"The name `{variant_name}` matches multiple enum variants in scope:")
                for ename, idx, payload in candidates:
                    payload_desc = "no payload" if payload is None else f"payload={payload}"
                    msg_lines.append(f"  - {ename}->{variant_name}  ({payload_desc})")
                msg_lines.append("")
                msg_lines.append("To fix, qualify the variant with its enum name:")
                msg_lines.append(f"  - To choose a variant:  {candidates[0][0]}->{variant_name}(...)")
                bhumi_report_error(use_site_line, use_site_col, "\n".join(msg_lines))
        if found_enum is not None:
            template = globals().get("original_enum_defs", {}).get(found_enum)
            if template and template.type_params:
                actuals: List[str] = []
                def _normalize_expected(exp_str):
                    if exp_str is None:
                        return None
                    s = exp_str.strip()
                    s = s.rstrip("*")
                    if s.startswith("%enum."):
                        s = s[len("%enum."):]
                    elif s.startswith("%struct."):
                        s = s[len("%struct."):]
                    return s
                def _actuals_from_expected(exp_str, base_enum, tparams):
                    if exp_str is None:
                        return None
                    bare = _normalize_expected(exp_str)
                    if bare is None:
                        return None
                    generic_m = re.fullmatch(re.escape(base_enum) + r"<(.+)>", bare)
                    if generic_m:
                        raw = generic_m.group(1)
                        parts = [p.strip() for p in raw.split(",")]
                        if len(parts) == len(tparams):
                            return parts
                    mono_prefix = base_enum + "__mono__"
                    if bare.startswith(mono_prefix) and bare in enum_variant_map:
                        concrete_variants = enum_variant_map[bare]
                        orig_variants = template.variants
                        result: List[Optional[str]] = [None] * len(tparams)
                        for orig_v, concrete_pair in zip(orig_variants, concrete_variants):
                            conc_payload = concrete_pair[1]
                            orig_payload_type = orig_v.typ
                            if orig_payload_type is not None and conc_payload is not None:
                                for i, tp in enumerate(tparams):
                                    if orig_payload_type == tp:
                                        result[i] = conc_payload
                        if all(r is not None for r in result):
                            return result
                    return None
                if found_variant_payload is not None and isinstance(found_variant_payload, str):
                    if len(template.type_params) == 1:
                        if not arg_types:
                            bhumi_report_error(None, None, f"Cannot infer type parameter for enum {found_enum}; no args provided")
                        actuals = [arg_types[0]]
                    else:
                        actuals_from_exp = _actuals_from_expected(expected, found_enum, template.type_params)
                        if actuals_from_exp is not None:
                            actuals = actuals_from_exp
                        else:
                            for tp in template.type_params:
                                if found_variant_payload == tp:
                                    if not arg_types:
                                        bhumi_report_error(None, None, f"Cannot infer type parameter '{tp}' for enum {found_enum}; no args provided")
                                    actuals.append(arg_types[0])
                                else:
                                    actuals.append(tp)
                else:
                    actuals_from_exp = _actuals_from_expected(expected, found_enum, template.type_params)
                    if actuals_from_exp is not None:
                        actuals = actuals_from_exp
                if actuals and all(isinstance(a, str) and not re.fullmatch(r"[A-Z]\w*", a) for a in actuals):
                    mononame = ensure_monomorph_for_enum(found_enum, actuals)
                    variants = enum_variant_map.get(mononame)
                    if variants:
                        _, payload = variants[found_variant_idx]
                        found_enum = mononame
                        found_variant_payload = payload
                elif actuals and expected is not None:
                    actuals_from_exp = _actuals_from_expected(expected, found_enum, template.type_params)
                    if actuals_from_exp is not None:
                        mononame = ensure_monomorph_for_enum(found_enum, actuals_from_exp)
                        variants = enum_variant_map.get(mononame)
                        if variants:
                            _, payload = variants[found_variant_idx]
                            found_enum = mononame
                            found_variant_payload = payload
                if (
                    found_variant_payload is not None
                    and isinstance(found_variant_payload, str)
                    and re.fullmatch(r"[A-Z]\w*", found_variant_payload)
                    and found_variant_payload in template.type_params
                ):
                    _partial = {found_variant_payload: arg_types[0]} if arg_types else {}
                    _actuals_exp = _actuals_from_expected(expected, found_enum, template.type_params)
                    _final_actuals = []
                    for _tp in template.type_params:
                        if _tp in _partial:
                            _final_actuals.append(_partial[_tp])
                        elif _actuals_exp is not None:
                            _idx = template.type_params.index(_tp)
                            _final_actuals.append(_actuals_exp[_idx])
                        else:
                            _final_actuals = []
                            break
                    if _final_actuals and all(
                        isinstance(a, str) and not re.fullmatch(r"[A-Z]\w*", a)
                        for a in _final_actuals
                    ):
                        mononame = ensure_monomorph_for_enum(found_enum, _final_actuals)
                        variants = enum_variant_map.get(mononame)
                        if variants:
                            _, payload = variants[found_variant_idx]
                            found_enum = mononame
                            found_variant_payload = payload
        if found_enum is not None:
            llvm_enum_ty = type_map.get(found_enum, type_map.get("int", "i64"))
            if found_variant_payload is None:
                if llvm_enum_ty.startswith("i"):
                    if len(expr.args) != 0:
                        bhumi_report_error(
                            None,
                            None,
                            f"Enum variant {expr.name} for {found_enum} takes no arguments",
                        )
                    tmp = new_tmp()
                    out.append(f"  {tmp} = add {llvm_enum_ty} 0, {found_variant_idx}")
                    return tmp
                else:
                    szptr = new_tmp()
                    out.append(
                        f"  {szptr} = getelementptr inbounds %enum.{found_enum}, %enum.{found_enum}* null, i32 1"
                    )
                    sz64 = new_tmp()
                    out.append(
                        f"  {sz64} = ptrtoint %enum.{found_enum}* {szptr} to i64"
                    )
                    raw = new_tmp()
                    out.append(f"  {raw} = call i8* @malloc(i64 {sz64})")
                    struct_ptr = new_tmp()
                    out.append(
                        f"  {struct_ptr} = bitcast i8* {raw} to %enum.{found_enum}*"
                    )
                    tag_ptr = new_tmp()
                    out.append(
                        f"  {tag_ptr} = getelementptr inbounds %enum.{found_enum}, %enum.{found_enum}* {struct_ptr}, i32 0, i32 0"
                    )
                    out.append(f"  store i32 {found_variant_idx}, i32* {tag_ptr}")
                    return struct_ptr
            if found_variant_payload is not None:
                if len(expr.args) != 1:
                    bhumi_report_error(
                        None,
                        None,
                        f"Enum constructor '{expr.name}' requires exactly one argument",
                    )
                payload_val = arg_vals[0]
                payload_ty = found_variant_payload
                if (
                    isinstance(payload_ty, str)
                    and re.fullmatch(r"[A-Z]\w*", payload_ty)
                    and payload_ty not in type_map
                    and payload_ty not in enum_variant_map
                ):
                    inferred = infer_type(expr.args[0])
                    if inferred and inferred != payload_ty:
                        payload_ty = inferred
                llvm_payload_ty = llvm_ty_of(payload_ty)
                szptr = new_tmp()
                out.append(
                    f"  {szptr} = getelementptr inbounds %enum.{found_enum}, %enum.{found_enum}* null, i32 1"
                )
                sz64 = new_tmp()
                out.append(f"  {sz64} = ptrtoint %enum.{found_enum}* {szptr} to i64")
                raw = new_tmp()
                out.append(f"  {raw} = call i8* @malloc(i64 {sz64})")
                struct_ptr = new_tmp()
                out.append(f"  {struct_ptr} = bitcast i8* {raw} to %enum.{found_enum}*")
                tag_ptr = new_tmp()
                out.append(
                    f"  {tag_ptr} = getelementptr inbounds %enum.{found_enum}, %enum.{found_enum}* {struct_ptr}, i32 0, i32 0"
                )
                out.append(f"  store i32 {found_variant_idx}, i32* {tag_ptr}")
                payload_ptr_raw = new_tmp()
                out.append(
                    f"  {payload_ptr_raw} = getelementptr inbounds %enum.{found_enum}, %enum.{found_enum}* {struct_ptr}, i32 0, i32 1"
                )
                payload_ptr = new_tmp()
                out.append(
                    f"  {payload_ptr} = bitcast [8 x i8]* {payload_ptr_raw} to {llvm_payload_ty}*"
                )
                out.append(
                    f"  store {llvm_payload_ty} {payload_val}, {llvm_payload_ty}* {payload_ptr}"
                )
                if llvm_payload_ty == "i8*" and not isinstance(expr.args[0], StrLit):
                    out.append(f"  call void @bhumi_ctbl_insert(i8* {payload_val})")
                return struct_ptr
            bhumi_report_error(
                None,
                None,
                f"Enum variant '{expr.name}' mismatches enum '{found_enum}' payload specification",
            )
        if expr.name == "!" and len(expr.args) == 1:
            arg = gen_expr(expr.args[0], out)
            arg_ty = infer_type(expr.args[0])
            if arg_ty != "bool":
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Unary ! requires bool, got {arg_ty}",
                )
            tmp = new_tmp()
            out.append(f"  {tmp} = xor i1 {arg}, true")
            return tmp
        call_target = ensure_monomorph_call(expr, out, expected_ret=expected)
        concrete_fn = _func_name_map.get(call_target)
        if concrete_fn and concrete_fn.is_async:
            bhumi_report_error(
                None, None, f"async function '{expr.name}' must be awaited"
            )
        def _promote_variadic_and_emit(a_val, a_ty, out):
            if a_ty in ("float", "float32"):
                target_bhumi_ty = "double"
                llvm_ty = llvm_ty_of(target_bhumi_ty)
                if a_val is None:
                    return llvm_ty, zero_const_for_llvm(llvm_ty)
                promoted = emit_cast_value(a_val, a_ty, target_bhumi_ty, out)
                return llvm_ty, promoted
            small_int_names = {
                "i8",
                "i16",
                "int8",
                "int16",
                "u8",
                "u16",
                "uint8",
                "uint16",
                "char",
                "signed char",
                "unsigned char",
                "short",
                "short int",
                "unsigned short",
                "i32",
                "int32",
            }
            if a_ty in small_int_names:
                target_bhumi_ty = "int"
                llvm_ty = llvm_ty_of(target_bhumi_ty)
                if a_val is None:
                    return llvm_ty, zero_const_for_llvm(llvm_ty)
                promoted = emit_cast_value(a_val, a_ty, target_bhumi_ty, out)
                return llvm_ty, promoted
            llvm_ty = llvm_ty_of(a_ty)
            if a_val is None:
                return llvm_ty, zero_const_for_llvm(llvm_ty)
            return llvm_ty, a_val
        args_ir = []
        if concrete_fn:
            for (param_typ, _), a_val, a_ty in zip(
                concrete_fn.params, arg_vals, arg_types
            ):
                llvm_param_ty = llvm_ty_of(param_typ)
                if a_val is None:
                    args_ir.append(
                        f"{llvm_param_ty} {zero_const_for_llvm(llvm_param_ty)}"
                    )
                else:
                    cast_tmp = emit_cast_value(a_val, a_ty, param_typ, out)
                    args_ir.append(f"{llvm_param_ty} {cast_tmp}")
            if getattr(concrete_fn, "is_variadic", False):
                fixed_count = len(concrete_fn.params)
                for idx in range(fixed_count, len(arg_vals)):
                    a_val = arg_vals[idx]
                    a_ty = arg_types[idx]
                    llvm_ty, ssa_or_const = _promote_variadic_and_emit(a_val, a_ty, out)
                    args_ir.append(f"{llvm_ty} {ssa_or_const}")
        else:
            for a_val, a_ty in zip(arg_vals, arg_types):
                if a_ty == "#":
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Cannot determine argument LLVM type for call '{expr.name}': argument type is '#'.",
                    )
                llvm_ty = llvm_ty_of(a_ty)
                if a_val is None:
                    args_ir.append(f"{llvm_ty} {zero_const_for_llvm(llvm_ty)}")
                else:
                    args_ir.append(f"{llvm_ty} {a_val}")
        ret_ty = func_table.get(call_target, None)
        if ret_ty is None:
            if expected is not None:
                call_target = ensure_monomorph_call(expr, out, expected_ret=expected)
                ret_ty = func_table.get(call_target, None)
        if ret_ty is None:
            bhumi_report_error(
                None,
                None,
                f"Call to undefined function or unresolved monomorph '{expr.name}'",
            )
        if ret_ty == "void":
            if call_target == "free" and len(arg_vals) == 1:
                ptr_val = arg_vals[0]
                ptr_ty  = arg_types[0] if arg_types else "void*"
                ptr_llvm = llvm_ty_of(ptr_ty) if ptr_ty else "i8*"
                if ptr_llvm == "i8*":
                    ptr_i8 = ptr_val
                else:
                    ptr_i8 = new_tmp()
                    out.append(f"  {ptr_i8} = bitcast {ptr_llvm} {ptr_val} to i8*")
                out.append(f"  call void @bhumi_ffi_free(i8* {ptr_i8})")
                if expr.args and isinstance(expr.args[0], Var):
                    _fvn = expr.args[0].name
                    _fsym = symbol_table.lookup(_fvn)
                    if _fsym is not None:
                        _fty, _fname = _fsym
                        _faddr = f"@{_fname}" if _fname.startswith("@") else f"%{_fname}_addr"
                        out.append(f"  store {_fty} {zero_const_for_llvm(_fty)}, {_fty}* {_faddr}")
                        _bep = binding_enum_payload.get(_fname)
                        if _bep is not None:
                            _bep_enum_ptr, _bep_enum_nm, _bep_vidx, _bep_pty, _bep_slot = _bep
                            out.append(f"  store {_bep_pty} {zero_const_for_llvm(_bep_pty)}, {_bep_pty}* {_bep_slot}")
                        if _fvn in crumb_runtime:
                            crumb_runtime[_fvn]["owned"] = False
                        owned_vars.discard(_fvn)
                        for _ctx in scope_drop_stack:
                            _eirowned = _ctx.get("extra_ir_owned", [])
                            _ctx["extra_ir_owned"] = [(_ir_nm, _ir_ty, _ir_src)
                                for _ir_nm, _ir_ty, _ir_src in _eirowned
                                if _ir_nm != _fname
                            ]
                if expr.args and isinstance(expr.args[0], Var):
                    _cancel_vn = expr.args[0].name
                    _cancel_cr = crumb_runtime.get(_cancel_vn)
                    if _cancel_cr:
                        _cancel_cr.pop("_deferred_frees", None)
                return ""
            if call_target in _FREE_ARG_FUNS and len(arg_vals) >= 1:
                if expr.args and isinstance(expr.args[0], Var):
                    _ffvn = expr.args[0].name
                    _ffsym = symbol_table.lookup(_ffvn)
                    if _ffsym is not None:
                        _ffty, _ffname = _ffsym
                        _ffaddr = _ffname if _ffname.startswith("@") else f"%{_ffname}_addr"
                        out.append(f"  call void @{call_target}({', '.join(args_ir)})")
                        out.append(f"  store {_ffty} {zero_const_for_llvm(_ffty)}, {_ffty}* {_ffaddr}")
                        _bep2 = binding_enum_payload.get(_ffname)
                        if _bep2 is not None:
                            _, _, _, _bep2_pty, _bep2_slot = _bep2
                            out.append(f"  store {_bep2_pty} {zero_const_for_llvm(_bep2_pty)}, {_bep2_pty}* {_bep2_slot}")
                        if _ffvn in crumb_runtime:
                            crumb_runtime[_ffvn]["owned"] = False
                        owned_vars.discard(_ffvn)
                        for _ctx in scope_drop_stack:
                            _ctx.get("body_decl_names", set()).discard(_ffvn)
                            _ctx["extra_ir_owned"] = [
                                (_ir_nm, _ir_ty, _ir_src)
                                for _ir_nm, _ir_ty, _ir_src in _ctx.get("extra_ir_owned", [])
                                if _ir_nm != _ffname
                            ]
                        return ""
            out.append(f"  call void @{call_target}({', '.join(args_ir)})")
            for arg_expr, arg_val in zip(expr.args, arg_vals):
                _maybe_flush_deferred(arg_expr, arg_val)
                try:
                    if (
                        arg_val is not None
                        and infer_type(arg_expr) == "string"
                        and isinstance(arg_expr, BinOp)
                        and arg_expr.op == "+"
                    ):
                        cast_tmp = new_tmp()
                        out.append(f"  {cast_tmp} = bitcast i8* {arg_val} to i8*")
                        out.append(f"  call void @free(i8* {cast_tmp})")
                except Exception:
                    pass
            return ""
        else:
            tmp2 = new_tmp()
            out.append(f"  {tmp2} = call {ret_ty} @{call_target}({', '.join(args_ir)})")
            _is_extern_call = (
                concrete_fn is not None and getattr(concrete_fn, "is_extern", False)
            ) or (
                concrete_fn is None
                and call_target not in (
                    "llvm.memcpy.p0i8.p0i8.i64", "puts", "strlen",
                    "exit", "time", "srand", "rand", "usleep", "signal",
                    "malloc", "free", "bhumi_malloc", "bhumi_free",
                    "bhumi_safe_c_free", "bhumi_c_free", "bhumi_ffi_free",
                    "bhumi_tbl_insert", "bhumi_tbl_remove", "bhumi_tbl_contains",
                    "bhumi_ctbl_insert", "bhumi_ctbl_remove", "bhumi_ctbl_contains",
                )
                and not call_target.startswith("bhumi_")
                and not call_target.startswith("llvm.")
            )
            if ret_ty == "i8*" and _is_extern_call:
                _null_chk = new_tmp()
                _ins_skip = new_label("ctbl_ins_skip")
                _ins_do   = new_label("ctbl_ins_do")
                out.append(f"  {_null_chk} = icmp eq i8* {tmp2}, null")
                out.append(f"  br i1 {_null_chk}, label %{_ins_skip}, label %{_ins_do}")
                out.append(f"{_ins_do}:")
                out.append(f"  call void @bhumi_ctbl_insert(i8* {tmp2})")
                out.append(f"  br label %{_ins_skip}")
                out.append(f"{_ins_skip}:")
            for arg_expr, arg_val in zip(expr.args, arg_vals):
                _maybe_flush_deferred(arg_expr, arg_val)
                if infer_type(arg_expr) == "string":
                    _emit_free_if_temp(arg_expr, arg_val)
            return tmp2
    if isinstance(expr, FieldAccess):
        if isinstance(expr.base, Var) and expr.base.name in enum_variant_map:
            base_name = expr.base.name
            llvm_enum_ty = type_map.get(base_name, type_map.get("int", "i64"))
            if llvm_enum_ty.startswith("i"):
                variants = enum_variant_map[base_name]
                for idx, (vname, payload) in enumerate(variants):
                    if vname == expr.field:
                        tmp = new_tmp()
                        out.append(f"  {tmp} = add {llvm_enum_ty} 0, {idx}")
                        return tmp
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Enum '{base_name}' has no variant '{expr.field}'",
                )
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Cannot access variant {expr.field} on enum type {base_name} (tagged enums require constructors like Some(...))",
            )
        field_base = expr.base
        base_raw = infer_type(field_base)
        base_name = base_raw
        if base_name.endswith("*"):
            base_name = base_name[:-1]
        if base_name.startswith("%struct."):
            base_name = base_name[len("%struct.") :]
        if base_name in enum_variant_map and type_map.get(base_name, "").startswith(
            "i"
        ):
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                "Field access on an enum value is not supported; use match or constructors",
            )
        if base_name not in struct_field_map:
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Struct type '{base_name}' not found",
            )
        fields = struct_field_map[base_name]
        field_dict = dict(fields)
        if expr.field not in field_dict:
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Struct '{base_name}' has no field '{expr.field}'",
            )
        index = list(field_dict.keys()).index(expr.field)
        field_typ = field_dict[expr.field]
        field_llvm = llvm_ty_of(field_typ)
        if isinstance(field_base, Var):
            res = symbol_table.lookup(field_base.name)
            if res is None:
                bhumi_report_error(
                    getattr(field_base, "lineno", None),
                    getattr(field_base, "col", None),
                    f"Undefined variable: {field_base.name}",
                )
            llvm_var_ty, name = res
            if llvm_var_ty.endswith("*"):
                if name.startswith("@"):
                    ptr_load = new_tmp()
                    out.append(
                        f"  {ptr_load} = load {llvm_var_ty}, {llvm_var_ty}* {name}"
                    )
                else:
                    ptr_load = new_tmp()
                    if name.startswith("%"):
                        out.append(
                            f"  {ptr_load} = load {llvm_var_ty}, {llvm_var_ty}* {name}_addr"
                        )
                    else:
                        out.append(
                            f"  {ptr_load} = load {llvm_var_ty}, {llvm_var_ty}* %{name}_addr"
                        )
                is_null_tmp = new_tmp()
                out.append(f"  {is_null_tmp} = icmp eq {llvm_var_ty} {ptr_load}, null")
                null_fail = new_label("null_ptr_fail")
                null_ok = new_label("null_ptr_ok")
                out.append(
                    f"  br i1 {is_null_tmp}, label %{null_fail}, label %{null_ok}"
                )
                out.append(f"{null_fail}:")
                out.append(f"  call void @bhumi_null_abort()")
                out.append(f"  unreachable")
                out.append(f"{null_ok}:")
                base_ptr = ptr_load
            else:
                if name.startswith("@"):
                    base_ptr = name
                else:
                    if name.startswith("%"):
                        base_ptr = f"{name}_addr"
                    else:
                        base_ptr = f"%{name}_addr"
        else:
            base_val = gen_expr(field_base, out)
            base_ty = infer_type(field_base)
            if not base_ty.endswith("*"):
                if (
                    base_val.startswith("%")
                    and not base_val.endswith("_addr")
                    and not base_val.startswith("%struct.")
                ):
                    tmp_addr = new_tmp()
                    _entry_alloca_buf.append(f"  {tmp_addr} = alloca %struct.{base_name}")
                    out.append(
                        f"  store %struct.{base_name} {base_val}, %struct.{base_name}* {tmp_addr}"
                    )
                    base_ptr = tmp_addr
                else:
                    bhumi_report_error(
                        None,
                        None,
                        "Taking address of a field on an rvalue struct is not supported",
                    )
            else:
                base_ptr = base_val
        ptr = new_tmp()
        out.append(
            f"  {ptr} = getelementptr inbounds %struct.{base_name}, %struct.{base_name}* {base_ptr}, i32 0, i32 {index}"
        )
        tmp = new_tmp()
        out.append(f"  {tmp} = load {field_llvm}, {field_llvm}* {ptr}")
        _maybe_flush_deferred(field_base, base_ptr)
        return tmp
    if isinstance(expr, StructInit):
        struct_name = expr.name
        struct_ty = f"%struct.{struct_name}"
        size_tmp = new_tmp()
        out.append(
            f"  {size_tmp} = ptrtoint {struct_ty}* getelementptr ({struct_ty}, {struct_ty}* null, i32 1) to i64"
        )
        malloc_tmp = new_tmp()
        out.append(f"  {malloc_tmp} = call i8* @malloc(i64 {size_tmp})")
        tmp_ptr = new_tmp()
        out.append(f"  {tmp_ptr} = bitcast i8* {malloc_tmp} to {struct_ty}*")
        field_dict = dict(struct_field_map[struct_name])
        for field_name, field_expr in expr.fields:
            if field_name not in field_dict:
                bhumi_report_error(
                    None, None, f"Field '{field_name}' not in struct '{struct_name}'"
                )
            field_type = field_dict[field_name]
            field_llvm = llvm_ty_of(field_type)
            field_val = gen_expr(field_expr, out)
            index = list(field_dict.keys()).index(field_name)
            ptr = new_tmp()
            out.append(
                f"  {ptr} = getelementptr inbounds {struct_ty}, {struct_ty}* {tmp_ptr}, i32 0, i32 {index}"
            )
            out.append(f"  store {field_llvm} {field_val}, {field_llvm}* {ptr}")
        return tmp_ptr
    if isinstance(expr, ArrayInit):
        count = len(expr.elements)
        if count == 0:
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                "Empty array literal must have explicit type",
            )
        elem_t = infer_type(expr.elements[0])
        elem_llvm = llvm_ty_of(elem_t)
        arr_llvm_ty = f"[{count} x {elem_llvm}]"
        tmp_ptr = new_tmp()
        out.append(f"  {tmp_ptr} = alloca {arr_llvm_ty}")
        for i, el in enumerate(expr.elements):
            val = gen_expr(el, out)
            gep = new_tmp()
            out.append(
                f"  {gep} = getelementptr inbounds {arr_llvm_ty}, {arr_llvm_ty}* {tmp_ptr}, i32 0, i32 {i}"
            )
            out.append(f"  store {elem_llvm} {val}, {elem_llvm}* {gep}")
        return tmp_ptr
    bhumi_report_error(
        getattr(expr, "lineno", None),
        getattr(expr, "col", None),
        f"Unhandled expr: {expr}",
    )
def infer_type(expr: Expr) -> str:
    cached = _expr_type_cache.get(id(expr))
    if cached is not None:
        return cached
    if isinstance(expr, CallerType):
        return "#"
    if isinstance(expr, UnaryDeref):
        if isinstance(expr.ptr, NullLit):
            bhumi_report_error(
                getattr(expr.ptr, "lineno", None),
                getattr(expr.ptr, "col", None),
                "[BhumiCompiler-ERR]: dereference of literal null pointer",
            )
        ptr_type = infer_type(expr.ptr)
        if ptr_type == "null" or ptr_type == "void*":
            bhumi_report_error(
                getattr(expr.ptr, "lineno", None),
                getattr(expr.ptr, "col", None),
                "[BhumiCompiler-ERR]: dereference of an expression known to be null",
            )
        if not ptr_type.endswith("*"):
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Dereferencing non-pointer type '{ptr_type}'",
            )
        pointee = ptr_type[:-1]
        if pointee == "void":
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                "Cannot dereference 'void*' without an explicit cast to a concrete pointer type",
            )
        return pointee
    if isinstance(expr, UnaryOp):
        return infer_type(expr.expr)
    if isinstance(expr, IntLit):
        return "int"
    if isinstance(expr, FloatLit):
        return "float32" if getattr(expr, "bits", 64) == 32 else "float"
    if isinstance(expr, BoolLit):
        return "bool"
    if isinstance(expr, CharLit):
        return "char"
    if isinstance(expr, StrLit):
        return "string"
    if isinstance(expr, NullLit):
        return "null"
    if isinstance(expr, Cast):
        return expr.typ
    if isinstance(expr, AwaitExpr):
        inner = expr.expr
        if isinstance(inner, Call):
            base_fn = _func_name_map.get(inner.name)
            if base_fn is None:
                bhumi_report_error(
                    getattr(inner, "lineno", None),
                    getattr(inner, "col", None),
                    f"Await of unknown function '{inner.name}'",
                )
            return base_fn.ret_type
        else:
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                "Await supports only direct Call(...) expressions in type checking",
            )
    if isinstance(expr, Var):
        result = symbol_table.lookup(expr.name)
        if result is None:
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Undefined variable: {expr.name}",
            )
        llvm_ty, _ = result
        if llvm_ty.startswith("[") and " x " in llvm_ty and llvm_ty.endswith("]"):
            inside = llvm_ty[1:-1]
            elem_llvm = inside.split(" x ")[1]
            for high, low in type_map.items():
                if low == elem_llvm:
                    return high
            return elem_llvm
        for high, low in type_map.items():
            if low == llvm_ty:
                return high
        if llvm_ty.startswith("%struct.") and llvm_ty.endswith("*"):
            return llvm_ty[len("%struct.") : -1] + "*"
        return llvm_ty
    if isinstance(expr, TypeofExpr):
        return "string"
    if isinstance(expr, FieldAccess):
        if isinstance(expr.base, Var) and expr.base.name in enum_variant_map:
            return "int"
        base_raw = infer_type(expr.base)
        base_name = base_raw
        if base_name.endswith("*"):
            base_name = base_name[:-1]
        if base_name.startswith("%struct."):
            base_name = base_name[len("%struct.") :]
        if base_name in enum_variant_map:
            return "int"
        if base_name not in struct_field_map:
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Struct type '{base_name}' not found",
            )
        fields = struct_field_map[base_name]
        field_dict = dict(fields)
        if expr.field not in field_dict:
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Field '{expr.field}' not in struct '{base_name}'",
            )
        return field_dict[expr.field]
    if isinstance(expr, StructInit):
        return expr.name + "*"
    if isinstance(expr, ArrayInit):
        elem_type = None
        for e in expr.elements:
            t = infer_type(e)
            if elem_type is None:
                elem_type = t
                continue
            common_int = unify_int_types(elem_type, t)
            if common_int is not None:
                elem_type = common_int
                continue
            if t != elem_type:
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Array literal element types do not match: {elem_type} vs {t}",
                )
        return f"{elem_type}[{len(expr.elements)}]"
    if isinstance(expr, Call) and expr.name == "!" and len(expr.args) == 1:
        arg_t = infer_type(expr.args[0])
        if arg_t != "bool":
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Unary ! requires bool, got {arg_t}",
            )
        return "bool"
    if isinstance(expr, BinOp):
        left_type = infer_type(expr.left)
        right_type = infer_type(expr.right)
        if left_type.endswith("*") and not right_type.endswith("*") and expr.op in {"+", "-"}:
            if expr.op in {"==", "!=", "<", "<=", ">", ">="}:
                return "bool"
            return left_type
        if right_type.endswith("*") and not left_type.endswith("*") and expr.op == "+":
            return right_type
        if (left_type.endswith("*") and right_type.endswith("*")
                and left_type == right_type and expr.op == "-"):
            return "int"
        common = unify_int_types(left_type, right_type)
        if not common:
            if left_type != right_type:
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Type mismatch in binary op '{expr.op}': {left_type} vs {right_type}",
                )
            common = left_type
        if expr.op in {"==", "!=", "<", "<=", ">", ">="}:
            return "bool"
        return common
    if isinstance(expr, AddressOf):
        inner_ty = infer_type(expr.expr)
        return inner_ty + "*"
    if isinstance(expr, Call):
        _infer_qualified_enum = None
        _infer_variant_name = expr.name
        if "->" in expr.name:
            _infer_qualified_enum, _infer_variant_name = expr.name.split("->", 1)
        _infer_matches = []
        for ename, variants in enum_variant_map.items():
            if "__mono__" in ename:
                continue
            if _infer_qualified_enum is not None and ename != _infer_qualified_enum:
                continue
            for vname, payload in variants:
                if vname == _infer_variant_name:
                    _orig_edef = globals().get("original_enum_defs", {}).get(ename)
                    _tparams = getattr(_orig_edef, "type_params", []) if _orig_edef else []
                    _infer_matches.append((ename, payload, bool(_tparams)))
                    break
        if _infer_matches:
            _concrete_matches = [(e, p, g) for e, p, g in _infer_matches if not g]
            _chosen = _concrete_matches[0] if _concrete_matches else _infer_matches[0]
            ename, payload, has_tparams = _chosen
            _orig_edef = globals().get("original_enum_defs", {}).get(ename)
            _tparams = getattr(_orig_edef, "type_params", []) if _orig_edef else []
            if _tparams and payload is not None and payload in _tparams and expr.args:
                if len(_tparams) == 1:
                    _actual_t = infer_type(expr.args[0])
                    _mono = ensure_monomorph_for_enum(ename, [_actual_t])
                    return _mono + "*"
                else:
                    _orig_edef2 = globals().get("original_enum_defs", {}).get(ename)
                    _tparams2 = getattr(_orig_edef2, "type_params", []) if _orig_edef2 else []
                    if _orig_edef2 and _tparams2 and expr.args:
                        _arg_types2 = [infer_type(a) for a in expr.args]
                        _actuals2: List[Optional[str]] = [None] * len(_tparams2)
                        for _vi, _vv in enumerate(_orig_edef2.variants):
                            if _vv.name == _infer_variant_name and _vv.typ is not None:
                                for _pi, _tp2 in enumerate(_tparams2):
                                    if _vv.typ == _tp2 and len(_arg_types2) > 0:
                                        _actuals2[_pi] = _arg_types2[0]
                        if all(a is not None for a in _actuals2):
                            _mono2 = ensure_monomorph_for_enum(ename, _actuals2)
                            return _mono2 + "*"
                    return ename + "*"
            if type_map.get(ename, "").startswith("i") and payload is None:
                return ename
            return ename + "*"
        for fn in all_funcs:
            if fn.name == expr.name and fn.ret_type == "#":
                arg_types_for_mono = [infer_type(a) for a in (expr.args or [])]
                for ft_name, ft_ret in func_table.items():
                    if not ft_name.startswith(expr.name + "__mono__"):
                        continue
                    for k, v in type_map.items():
                        if v == ft_ret:
                            return k
                    if ft_ret.startswith("%struct."):
                        return ft_ret[8:]
                    if ft_ret.startswith("%enum."):
                        return ft_ret[6:].rstrip("*")
                    return ft_ret
                return "#"
        if expr.name in func_table:
            ret_llvm_ty = func_table[expr.name]
            for k, v in type_map.items():
                if v == ret_llvm_ty:
                    return k
            if ret_llvm_ty.startswith("%struct."):
                return ret_llvm_ty[8:]
            return ret_llvm_ty
        for fn in all_funcs:
            if fn.name == expr.name and fn.type_params:
                if not expr.args:
                    bhumi_report_error(
                        None,
                        None,
                        f"Generic function '{expr.name}' called with no arguments",
                    )
                arg_types = [infer_type(a) for a in expr.args]
                actuals: List[str] = []
                for tp in fn.type_params:
                    found = None
                    for param_idx, (param_typ, _) in enumerate(fn.params):
                        if param_typ == tp or tp in param_typ:
                            if param_idx < len(arg_types):
                                found = arg_types[param_idx]
                                break
                    if found is None:
                        if fn.ret_type == tp and len(arg_types) > 0:
                            found = arg_types[0]
                    if found is None:
                        bhumi_report_error(
                            None,
                            None,
                            f"Cannot infer type parameter '{tp}' for generic function '{expr.name}'",
                        )
                    actuals.append(found)
                mononame = ensure_monomorph_for_call(expr.name, actuals)
                new_ret = fn.ret_type
                if new_ret in fn.type_params:
                    idx = fn.type_params.index(new_ret)
                    return actuals[idx]
                return new_ret
    if isinstance(expr, Index):
        if not isinstance(expr.array, Var):
            bhumi_report_error(
                None,
                None,
                f"Only direct variable array indexing is supported, got: {expr.array}",
            )
        arr_name = expr.array.name
        arr_info = symbol_table.lookup(arr_name)
        if not arr_info:
            bhumi_report_error(None, None, f"Undefined array: {arr_name}")
        llvm_ty, _ = arr_info
        if not (llvm_ty.startswith("[") and " x " in llvm_ty and llvm_ty.endswith("]")):
            bhumi_report_error(
                None, None, f"Attempting to index non-array type '{llvm_ty}'"
            )
        inside = llvm_ty[1:-1]
        elem_llvm = inside.split(" x ")[1]
        for high, low in type_map.items():
            if low == elem_llvm:
                return high
        return elem_llvm
    if isinstance(expr, Ternary):
        then_t = infer_type(expr.then_expr)
        else_t = infer_type(expr.else_expr)
        if then_t != else_t:
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Ternary branches must match: {then_t} vs {else_t}",
            )
        return then_t
    if hasattr(expr, "__dict__"):
        possible = expr.__dict__.get("name", "")
        if isinstance(possible, str) and possible.endswith("*"):
            return possible
    bhumi_report_error(
        getattr(expr, "lineno", None),
        getattr(expr, "col", None),
        f"Cannot infer type for expression: {expr}",
    )
def emit_deep_free(llvm_ty: str, ptr_tmp: str, out: List[str], safe_envelope: bool = False) -> None:
    enum_name = None
    if llvm_ty.startswith("%enum.") and llvm_ty.endswith("*"):
        enum_name = llvm_ty[len("%enum."):-1]
    elif llvm_ty.startswith("%struct.") and llvm_ty.endswith("*"):
        bare = llvm_ty[len("%struct."):-1]
        if bare in enum_variant_map:
            enum_name = bare
    if enum_name is not None and enum_name in enum_variant_map:
        variants = enum_variant_map[enum_name]
        ptr_variants = [
            (vname, vp) for vname, vp in variants
            if vp is not None and llvm_ty_of(vp).endswith("*")
        ]
        if ptr_variants:
            tag_tmp = new_tmp()
            tag_ptr_tmp = new_tmp()
            out.append(
                f"  {tag_ptr_tmp} = getelementptr inbounds %enum.{enum_name}, "
                f"%enum.{enum_name}* {ptr_tmp}, i32 0, i32 0"
            )
            out.append(f"  {tag_tmp} = load i32, i32* {tag_ptr_tmp}")
            after_payload_lbl = new_label("dp_after_payload")
            for idx, (vname, vp) in enumerate(variants):
                if vp is None:
                    continue
                vp_llvm = llvm_ty_of(vp)
                if not vp_llvm.endswith("*"):
                    continue
                is_variant_tmp = new_tmp()
                out.append(f"  {is_variant_tmp} = icmp eq i32 {tag_tmp}, {idx}")
                do_payload_lbl = new_label(f"dp_pay_{vname}")
                skip_payload_lbl = new_label(f"dp_nopay_{vname}")
                out.append(
                    f"  br i1 {is_variant_tmp}, label %{do_payload_lbl}, "
                    f"label %{skip_payload_lbl}"
                )
                out.append(f"{do_payload_lbl}:")
                raw_slot_tmp = new_tmp()
                cast_slot_tmp = new_tmp()
                loaded_pay_tmp = new_tmp()
                out.append(
                    f"  {raw_slot_tmp} = getelementptr inbounds %enum.{enum_name}, "
                    f"%enum.{enum_name}* {ptr_tmp}, i32 0, i32 1"
                )
                out.append(
                    f"  {cast_slot_tmp} = bitcast [8 x i8]* {raw_slot_tmp} to {vp_llvm}*"
                )
                out.append(
                    f"  {loaded_pay_tmp} = load {vp_llvm}, {vp_llvm}* {cast_slot_tmp}"
                )
                null_pay_tmp = new_tmp()
                pay_cast_tmp = new_tmp()
                out.append(f"  {pay_cast_tmp} = bitcast {vp_llvm} {loaded_pay_tmp} to i8*")
                out.append(f"  {null_pay_tmp} = icmp eq i8* {pay_cast_tmp}, null")
                skip_null_lbl = new_label(f"dp_null_{vname}")
                do_free_lbl = new_label(f"dp_free_{vname}")
                out.append(
                    f"  br i1 {null_pay_tmp}, label %{skip_null_lbl}, "
                    f"label %{do_free_lbl}"
                )
                out.append(f"{do_free_lbl}:")
                if (
                    vp_llvm.startswith("%enum.") or
                    (vp_llvm.startswith("%struct.") and
                     vp_llvm[len("%struct."):-1] in enum_variant_map)
                ):
                    emit_deep_free(vp_llvm, loaded_pay_tmp, out)
                else:
                    out.append(f"  call void @bhumi_safe_c_free(i8* {pay_cast_tmp})")
                out.append(f"  br label %{skip_null_lbl}")
                out.append(f"{skip_null_lbl}:")
                out.append(f"  br label %{skip_payload_lbl}")
                out.append(f"{skip_payload_lbl}:")
            out.append(f"  br label %{after_payload_lbl}")
            out.append(f"{after_payload_lbl}:")
    env_cast = new_tmp()
    out.append(f"  {env_cast} = bitcast {llvm_ty} {ptr_tmp} to i8*")
    if enum_name is None:
        out.append(f"  call void @bhumi_safe_c_free(i8* {env_cast})")
    else:
        out.append(f"  call void @bhumi_free(i8* {env_cast})")
def _last_is_terminator(out: List[str]) -> bool:
    for line in reversed(out):
        stripped = line.strip()
        if not stripped or stripped.endswith(":"):
            continue
        return (
            stripped.startswith("ret ")
            or stripped == "ret void"
            or stripped.startswith("br ")
            or stripped == "unreachable"
        )
    return False
def _emit_scope_drops(ctx: dict, out: List[str], force: bool = False) -> None:
    import sys as _sys
    if not force and _last_is_terminator(out):
        ctx["extra_ir_owned"] = []
        ctx["match_envelopes"] = []
        return
    body_decl_names = ctx.get("body_decl_names", set())
    pre_owned = ctx.get("pre_owned_snapshot", set())
    candidates = set(body_decl_names)
    for _vn in list(owned_vars):
        if _vn not in pre_owned:
            candidates.add(_vn)
    _xir_names = {_n for _n, _t, _s in ctx.get("extra_ir_owned", [])}
    for nm in candidates:
        cr = crumb_runtime.get(nm)
        owned_here = (nm in owned_vars) or (cr is not None and cr.get("owned"))
        if not owned_here:
            continue
        result = symbol_table.lookup(nm)
        if result is None:
            continue
        llvm_ty, llvm_name = result
        if not llvm_ty.endswith("*"):
            continue
        if llvm_name in _xir_names:
            continue
        if cr is not None:
            _rmax_v = cr.get("rmax")
            _wmax_v = cr.get("wmax")
            _rc_v = cr.get("rc", 0)
            _wc_v = cr.get("wc", 0)
            if _rmax_v is None and _wmax_v is None:
                print(
                    f"[Bhumi] Warning: crumble '{nm}' dropped at scope exit; "
                    f"no read (!r) or write (!w) limit was set, "
                    f"{_rc_v} read(s) and {_wc_v} write(s) consumed. "
                    f"Set crumble({nm})!r=<N>!w=<M>; to silence this.",
                    file=_sys.stderr,
                )
            elif _rmax_v is None:
                print(
                    f"[Bhumi] Warning: crumble '{nm}' dropped at scope exit; "
                    f"no read limit (!r) was set, {_rc_v} read(s) consumed. "
                    f"Set crumble({nm})!r=<count>; to silence this.",
                    file=_sys.stderr,
                )
            elif _wmax_v is None:
                print(
                    f"[Bhumi] Warning: crumble '{nm}' dropped at scope exit; "
                    f"no write limit (!w) was set, {_wc_v} write(s) consumed. "
                    f"Set crumble({nm})!w=<count>; to silence this.",
                    file=_sys.stderr,
                )
        addr_token = llvm_name if llvm_name.startswith("@") else f"%{llvm_name}_addr"
        ptr_tmp = new_tmp()
        out.append(f"  {ptr_tmp} = load {llvm_ty}, {llvm_ty}* {addr_token}")
        cast_tmp = new_tmp()
        out.append(f"  {cast_tmp} = bitcast {llvm_ty} {ptr_tmp} to i8*")
        drop_skip_lbl = new_label("drop_skip")
        drop_free_lbl = new_label("drop_free")
        drop_null_tmp = new_tmp()
        out.append(f"  {drop_null_tmp} = icmp eq i8* {cast_tmp}, null")
        out.append(f"  br i1 {drop_null_tmp}, label %{drop_skip_lbl}, label %{drop_free_lbl}")
        out.append(f"{drop_free_lbl}:")
        emit_deep_free(llvm_ty, ptr_tmp, out, safe_envelope=(nm in _extern_spill_names))
        out.append(f"  store {llvm_ty} null, {llvm_ty}* {addr_token}")
        out.append(f"  br label %{drop_skip_lbl}")
        out.append(f"{drop_skip_lbl}:")
        if nm in crumb_runtime:
            crumb_runtime[nm]["owned"] = False
        owned_vars.discard(nm)
    for _ir_nm, _ir_ty, _ir_src in ctx.get("extra_ir_owned", []):
        _ir_addr = f"%{_ir_nm}_addr"
        _ir_ptr = new_tmp()
        _ir_cast = new_tmp()
        _ir_null = new_tmp()
        _ir_skip = new_label("xir_skip")
        _ir_free = new_label("xir_free")
        out.append(f"  {_ir_ptr} = load {_ir_ty}, {_ir_ty}* {_ir_addr}")
        out.append(f"  {_ir_cast} = bitcast {_ir_ty} {_ir_ptr} to i8*")
        out.append(f"  {_ir_null} = icmp eq i8* {_ir_cast}, null")
        out.append(f"  br i1 {_ir_null}, label %{_ir_skip}, label %{_ir_free}")
        out.append(f"{_ir_free}:")
        emit_deep_free(_ir_ty, _ir_ptr, out)
        out.append(f"  store {_ir_ty} null, {_ir_ty}* {_ir_addr}")
        out.append(f"  br label %{_ir_skip}")
        out.append(f"{_ir_skip}:")
        owned_vars.discard(_ir_src)
    ctx["extra_ir_owned"] = []
    for _me_ty, _me_ir, _me_vn in ctx.get("match_envelopes", []):
        _me_addr = _me_ir if _me_ir.startswith("@") else f"%{_me_ir}_addr"
        _me_ptr = new_tmp()
        _me_cast = new_tmp()
        _me_null = new_tmp()
        _me_skip = new_label("me_skip")
        _me_free = new_label("me_free")
        out.append(f"  {_me_ptr} = load {_me_ty}, {_me_ty}* {_me_addr}")
        out.append(f"  {_me_cast} = bitcast {_me_ty} {_me_ptr} to i8*")
        out.append(f"  {_me_null} = icmp eq i8* {_me_cast}, null")
        out.append(f"  br i1 {_me_null}, label %{_me_skip}, label %{_me_free}")
        out.append(f"{_me_free}:")
        emit_deep_free(_me_ty, _me_ptr, out)
        out.append(f"  store {_me_ty} null, {_me_ty}* {_me_addr}")
        out.append(f"  br label %{_me_skip}")
        out.append(f"{_me_skip}:")
    ctx["match_envelopes"] = []
def _make_scope_ctx() -> dict:
    return {
        "body_decl_names": set(),
        "pre_owned_snapshot": set(owned_vars),
    }
def _name_used_in_stmts(name: str, stmts) -> bool:
    def _walk(node) -> bool:
        if node is None:
            return False
        if isinstance(node, Var) and node.name == name:
            return True
        for attr_val in getattr(node, "__dict__", {}).values():
            if isinstance(attr_val, list):
                for item in attr_val:
                    if hasattr(item, "__dict__") and _walk(item):
                        return True
            elif hasattr(attr_val, "__dict__"):
                if _walk(attr_val):
                    return True
        return False
    for s in stmts:
        if _walk(s):
            return True
    return False
def gen_stmt(stmt: Stmt, out: List[str], ret_ty: str):
    if isinstance(stmt, VarDecl):
        def _pick_ir_name(name):
            existing = None
            try:
                existing = symbol_table.lookup(name)
            except Exception:
                existing = None
            if existing is not None and name not in symbol_table.scopes[-1]:
                suf = new_tmp()[1:]
                return f"{name}_{suf}"
            return name
        ir_name = _pick_ir_name(stmt.name)
        llvm_ty = None
        if "[" in stmt.typ:
            base, rest = stmt.typ.split("[", 1)
            count = rest[:-1]
            elem_llvm = llvm_ty_of(base)
            llvm_ty = f"[{count} x {elem_llvm}]"
            if stmt.name not in symbol_table.scopes[-1]:
                out.append(f"  %{ir_name}_addr = alloca {llvm_ty}")
                out.append(
                    f"  store {llvm_ty} zeroinitializer, {llvm_ty}* %{ir_name}_addr"
                )
                out.append(f"  %{ir_name}_len  = alloca i32")
                out.append(f"  store i32 {count}, i32* %{ir_name}_len")
                symbol_table.declare(stmt.name, llvm_ty, ir_name)
            if stmt.expr:
                val = gen_expr(stmt.expr, out, expected=stmt.typ)
                src_cast = new_tmp()
                dst_cast = new_tmp()
                out.append(f"  {src_cast} = bitcast {llvm_ty}* {val} to i8*")
                out.append(f"  {dst_cast} = bitcast {llvm_ty}* %{ir_name}_addr to i8*")
                size_tmp = new_tmp()
                out.append(
                    f"  {size_tmp} = ptrtoint {llvm_ty}* getelementptr ({llvm_ty}, {llvm_ty}* null, i32 1) to i64"
                )
                out.append(
                    f"  call void @llvm.memcpy.p0i8.p0i8.i64(i8* {dst_cast}, i8* {src_cast}, i64 {size_tmp}, i1 false)"
                )
            return
        llvm_ty = llvm_ty_of(stmt.typ)
        _check_no_bare_generic(
            stmt.typ,
            f"Variable declaration '{stmt.name}'",
            getattr(stmt, "lineno", None), getattr(stmt, "col", None)
        )
        if stmt.name not in symbol_table.scopes[-1]:
            out.append(f"  %{ir_name}_addr = alloca {llvm_ty}")
            if llvm_ty.endswith("*"):
                out.append(f"  store {llvm_ty} null, {llvm_ty}* %{ir_name}_addr")
            elif llvm_ty == "double" or llvm_ty == "float":
                out.append(f"  store {llvm_ty} 0.0, {llvm_ty}* %{ir_name}_addr")
            elif llvm_ty.startswith("i"):
                out.append(f"  store {llvm_ty} 0, {llvm_ty}* %{ir_name}_addr")
            else:
                out.append(
                    f"  store {llvm_ty} zeroinitializer, {llvm_ty}* %{ir_name}_addr"
                )
            symbol_table.declare(stmt.name, llvm_ty, ir_name)
        if stmt.expr:
            val = gen_expr(stmt.expr, out, expected=stmt.typ)
            if isinstance(stmt.expr, Call):
                call_target = ensure_monomorph_call(
                    stmt.expr, out, expected_ret=stmt.typ
                )
                src_llvm = func_table.get(call_target) or llvm_ty_of(
                    infer_type(stmt.expr)
                )
            else:
                src_llvm = llvm_ty_of(infer_type(stmt.expr))
            if llvm_ty.endswith("*") and src_llvm.endswith("*"):
                if src_llvm != llvm_ty:
                    cast_tmp = new_tmp()
                    out.append(f"  {cast_tmp} = bitcast {src_llvm} {val} to {llvm_ty}")
                    val = cast_tmp
                out.append(f"  store {llvm_ty} {val}, {llvm_ty}* %{ir_name}_addr")
                if isinstance(stmt.expr, Call):
                    ret_t = infer_type(stmt.expr)
                    _nown_callee = (
                        stmt.expr.name in _NOWN_BUILTIN_FUNCS
                        or getattr(_func_name_map.get(stmt.expr.name), "is_nown", False)
                    )
                    if ret_t is not None and (ret_t.endswith("*") or ret_t == "string") and not _nown_callee:
                        owned_vars.add(stmt.name)
                        if stmt.name in crumb_runtime:
                            crumb_runtime[stmt.name]["owned"] = True
                elif isinstance(stmt.expr, StructInit):
                    owned_vars.add(stmt.name)
                    if stmt.name in crumb_runtime:
                        crumb_runtime[stmt.name]["owned"] = True
                elif isinstance(stmt.expr, Var):
                    _src_vn = stmt.expr.name
                    if _src_vn in owned_vars:
                        owned_vars.discard(_src_vn)
                        owned_vars.add(stmt.name)
                        if stmt.name in crumb_runtime:
                            crumb_runtime[stmt.name]["owned"] = True
                        if _src_vn in crumb_runtime:
                            crumb_runtime[_src_vn]["owned"] = False
                return
            if src_llvm.endswith("*") and not llvm_ty.endswith("*"):
                bhumi_report_error(
                    None, None, f"Type error: cannot assign pointer {src_llvm} into non-pointer {llvm_ty}"
                )
            if src_llvm != llvm_ty:
                cast_tmp = new_tmp()
                bits_src = llvm_int_bitsize(src_llvm)
                bits_dst = llvm_int_bitsize(llvm_ty)
                if bits_src and bits_dst:
                    if bits_src > bits_dst:
                        out.append(
                            f"  {cast_tmp} = trunc {src_llvm} {val} to {llvm_ty}"
                        )
                    else:
                        out.append(f"  {cast_tmp} = sext {src_llvm} {val} to {llvm_ty}")
                    val = cast_tmp
            out.append(f"  store {llvm_ty} {val}, {llvm_ty}* %{ir_name}_addr")
            if isinstance(stmt.expr, Call):
                ret_t = infer_type(stmt.expr)
                _nown_callee2 = (
                    stmt.expr.name in _NOWN_BUILTIN_FUNCS
                    or getattr(_func_name_map.get(stmt.expr.name), "is_nown", False)
                )
                if ret_t is not None and (ret_t.endswith("*") or ret_t == "string") and not _nown_callee2:
                    owned_vars.add(stmt.name)
                    if stmt.name in crumb_runtime:
                        crumb_runtime[stmt.name]["owned"] = True
        return
    elif isinstance(stmt, Assign):
        if isinstance(stmt.name, UnaryDeref):
            ptr_val = gen_expr(stmt.name.ptr, out)
            ptr_type = infer_type(stmt.name.ptr)
            val_expected = None
            if isinstance(ptr_type, str) and ptr_type.endswith("*"):
                val_expected = ptr_type[:-1]
            val = gen_expr(stmt.expr, out, expected=val_expected)
            val_ty = infer_type(stmt.expr)
            llvm_ty = llvm_ty_of(val_ty)
            out.append(f"  store {llvm_ty} {val}, {llvm_ty}* {ptr_val}")
        else:
            llvm_ty, ir_name = symbol_table.lookup(stmt.name)
            if ir_name.startswith("@"):
                addr_token = ir_name
            else:
                addr_token = f"%{ir_name}_addr"
            expected_lang = None
            if llvm_ty is not None:
                for high, low in type_map.items():
                    if low == llvm_ty:
                        expected_lang = high
                        break
                if (
                    expected_lang is None
                    and isinstance(llvm_ty, str)
                    and llvm_ty.startswith("%struct.")
                ):
                    expected_lang = llvm_ty[len("%struct.") :]
            val = gen_expr(stmt.expr, out, expected=expected_lang)
            vn = stmt.name
            cr = crumb_runtime.get(vn)
            handled_write_exhaustion_new_alloc = False
            if cr is not None:
                cr["wc"] = (cr.get("wc", 0) or 0) + 1
                _wmax = cr.get("wmax")
                _rmax = cr.get("rmax")
                if (
                    _wmax is not None
                    and cr["wc"] == _wmax
                    and cr.get("owned")
                ):
                    old_tmp = new_tmp()
                    out.append(f"  {old_tmp} = load {llvm_ty}, {llvm_ty}* {addr_token}")
                    cast_tmp = new_tmp()
                    out.append(f"  {cast_tmp} = bitcast {llvm_ty} {old_tmp} to i8*")
                    out.append(f"  call void @bhumi_free(i8* {cast_tmp})")
                    out.append(f"  store {llvm_ty} null, {llvm_ty}* {addr_token}")
                    _sym_crw_pre = symbol_table.lookup(vn)
                    if _sym_crw_pre:
                        _ir_crw_pre = _sym_crw_pre[1]
                        _bep_crw = binding_enum_payload.get(_ir_crw_pre)
                        if _bep_crw is not None:
                            _bcrw_subj, _bcrw_en, _bcrw_vi, _bcrw_pty, _bcrw_slot = _bep_crw
                            out.append(f"  store {_bcrw_pty} null, {_bcrw_pty}* {_bcrw_slot}")
                    cr["owned"] = False
                    owned_vars.discard(vn)
                    for _ctx in scope_drop_stack:
                        _ctx.get("body_decl_names", set()).discard(vn)
                        _sym_crw = symbol_table.lookup(vn)
                        if _sym_crw:
                            _ir_crw = _sym_crw[1]
                            _eiro_crw = _ctx.get("extra_ir_owned", [])
                            _ctx["extra_ir_owned"] = [
                                (_n, _t, _s) for _n, _t, _s in _eiro_crw if _n != _ir_crw
                            ]
                    if _rmax is None:
                        print(
                            f"[Bhumi] Warning: crumble '{vn}' autofreed after {_wmax} write(s); "
                            f"no read limit (!r) was set, {cr.get('rc', 0)} read(s) consumed. "
                            f"Set crumble({vn})!r=<count>; to silence this.",
                            file=__import__("sys").stderr,
                        )
                elif (
                    _wmax is not None
                    and cr["wc"] == _wmax
                    and not cr.get("owned")
                    and isinstance(stmt.expr, Call)
                ):
                    cast_tmp2 = new_tmp()
                    out.append(f"  {cast_tmp2} = bitcast {llvm_ty} {val} to i8*")
                    out.append(f"  call void @bhumi_free(i8* {cast_tmp2})")
                    out.append(f"  store {llvm_ty} null, {llvm_ty}* {addr_token}")
                    _sym_crw2_pre = symbol_table.lookup(vn)
                    if _sym_crw2_pre:
                        _ir_crw2_pre = _sym_crw2_pre[1]
                        _bep_crw2 = binding_enum_payload.get(_ir_crw2_pre)
                        if _bep_crw2 is not None:
                            _bcrw2_subj, _bcrw2_en, _bcrw2_vi, _bcrw2_pty, _bcrw2_slot = _bep_crw2
                            out.append(f"  store {_bcrw2_pty} null, {_bcrw2_pty}* {_bcrw2_slot}")
                    cr["owned"] = False
                    owned_vars.discard(vn)
                    for _ctx in scope_drop_stack:
                        _ctx.get("body_decl_names", set()).discard(vn)
                        _sym_crw2 = symbol_table.lookup(vn)
                        if _sym_crw2:
                            _ir_crw2 = _sym_crw2[1]
                            _eiro_crw2 = _ctx.get("extra_ir_owned", [])
                            _ctx["extra_ir_owned"] = [
                                (_n, _t, _s) for _n, _t, _s in _eiro_crw2 if _n != _ir_crw2
                            ]
                    handled_write_exhaustion_new_alloc = True
                    if _rmax is None:
                        print(
                            f"[Bhumi] Warning: crumble '{vn}' autofreed (new-alloc path) after {_wmax} write(s); "
                            f"no read limit (!r) was set, {cr.get('rc', 0)} read(s) consumed. "
                            f"Set crumble({vn})!r=<count>; to silence this.",
                            file=__import__("sys").stderr,
                        )
            curfn = globals().get("__bhumi_current_codegen_fn", None)
            if curfn is not None and getattr(curfn, "is_vasync", False):
                cap = getattr(curfn, "_vasync_captured", set()) or set()
                exc = set(getattr(curfn, "vasync_except", []) or [])
                target_name = (
                    stmt.name
                    if isinstance(stmt.name, str)
                    else getattr(stmt.name, "name", None)
                )
                if (
                    isinstance(target_name, str)
                    and target_name in cap
                    and target_name not in exc
                ):
                    out.append("  call void @bhumi_vvolatile_abort()")
                    out.append("  unreachable")
                    return
            if handled_write_exhaustion_new_alloc:
                return
            _reassign_allocs_new = (
                (
                    isinstance(stmt.expr, BinOp)
                    and stmt.expr.op == "+"
                    and infer_type(stmt.expr) == "string"
                )
                or (
                    isinstance(stmt.expr, Call)
                    and infer_type(stmt.expr) is not None
                    and (
                        infer_type(stmt.expr) == "string"
                        or infer_type(stmt.expr).endswith("*")
                    )
                )
            )
            _rhs_takes_lhs = False
            if isinstance(stmt.expr, Call):
                _callee_name = stmt.expr.name
                _callee_def = _func_name_map.get(_callee_name)
                if _callee_def is None:
                    _base_nm = _callee_name.split("__mono__")[0]
                    _callee_def = _func_name_map.get(_base_nm)
                if _callee_def is not None:
                    _tp = getattr(_callee_def, "take_params", None) or set()
                    for _ti in _tp:
                        if _ti < len(stmt.expr.args):
                            _ta = stmt.expr.args[_ti]
                            if isinstance(_ta, Var) and _ta.name == vn:
                                _rhs_takes_lhs = True
                                break
            if (
                cr is None
                and vn in owned_vars
                and llvm_ty.endswith("*")
                and _reassign_allocs_new
                and not _rhs_takes_lhs
            ):
                _old_ptr = new_tmp()
                out.append(f"  {_old_ptr} = load {llvm_ty}, {llvm_ty}* {addr_token}")
                _old_cast = new_tmp()
                out.append(f"  {_old_cast} = bitcast {llvm_ty} {_old_ptr} to i8*")
                _old_null_chk = new_tmp()
                _drop_old_skip = new_label("drop_old_skip")
                _drop_old_free = new_label("drop_old_free")
                out.append(f"  {_old_null_chk} = icmp eq i8* {_old_cast}, null")
                out.append(
                    f"  br i1 {_old_null_chk}, label %{_drop_old_skip}, label %{_drop_old_free}"
                )
                out.append(f"{_drop_old_free}:")
                out.append(f"  call void @bhumi_safe_c_free(i8* {_old_cast})")
                out.append(f"  br label %{_drop_old_skip}")
                out.append(f"{_drop_old_skip}:")
            out.append(f"  store {llvm_ty} {val}, {llvm_ty}* {addr_token}")
            if isinstance(stmt.expr, Call):
                ret_t = infer_type(stmt.expr)
                _nown_assign = (
                    stmt.expr.name in _NOWN_BUILTIN_FUNCS
                    or getattr(_func_name_map.get(stmt.expr.name), "is_nown", False)
                )
                if ret_t is not None and (ret_t.endswith("*") or ret_t == "string") and not _nown_assign:
                    owned_vars.add(vn)
                    if vn in crumb_runtime:
                        crumb_runtime[vn]["owned"] = True
            elif isinstance(stmt.expr, BinOp) and stmt.expr.op == "+" and infer_type(stmt.expr) == "string":
                owned_vars.add(vn)
                if vn in crumb_runtime:
                    crumb_runtime[vn]["owned"] = True
            elif isinstance(stmt.expr, Var) and llvm_ty.endswith("*"):
                _src_vn2 = stmt.expr.name
                if _src_vn2 in owned_vars:
                    owned_vars.discard(_src_vn2)
                    owned_vars.add(vn)
                    if vn in crumb_runtime:
                        crumb_runtime[vn]["owned"] = True
                    if _src_vn2 in crumb_runtime:
                        crumb_runtime[_src_vn2]["owned"] = False
    elif isinstance(stmt, ContinueStmt):
        if not loop_stack:
            bhumi_report_error(None, None, "`continue` used outside of a loop")
        head_lbl = loop_stack[-1]["continue"]
        out.append(f"  br label %{head_lbl}")
        out.append("  unreachable")
    elif isinstance(stmt, CrumbleStmt):
        name = stmt.name
        rmax = stmt.max_reads
        wmax = stmt.max_writes
        crumb_runtime[name] = {
            "rmax": rmax,
            "wmax": wmax,
            "rc": 0,
            "wc": 0,
            "owned": (name in owned_vars),
        }
        return
    elif isinstance(stmt, BreakStmt):
        if not loop_stack:
            bhumi_report_error(None, None, "`break` used outside of a loop")
        break_lbl = loop_stack[-1]["break"]
        out.append(f"  br label %{break_lbl}")
        out.append("  unreachable")
    elif isinstance(stmt, IndexAssign):
        idx = gen_expr(stmt.index, out)
        val = gen_expr(stmt.value, out)
        llvm_ty, name = symbol_table.lookup(stmt.array)
        base_ty = extract_array_base_type(llvm_ty)
        idx_ty = infer_type(stmt.index)
        idx_llvm = type_map[idx_ty]
        if idx_llvm != "i32":
            idx_cast = new_tmp()
            if idx_llvm.startswith("i") and int(idx_llvm[1:]) > 32:
                out.append(f"  {idx_cast} = trunc {idx_llvm} {idx} to i32")
            else:
                out.append(f"  {idx_cast} = sext {idx_llvm} {idx} to i32")
        else:
            idx_cast = idx
        if name.startswith("@"):
            len_addr = f"@{stmt.array}_len"
            arr_addr_token = name
        else:
            len_addr = f"%{stmt.array}_len"
            arr_addr_token = f"%{name}_addr"
        len_val = new_tmp()
        out.append(f"  {len_val} = load i32, i32* {len_addr}")
        ok = new_tmp()
        out.append(f"  {ok} = icmp ult i32 {idx_cast}, {len_val}")
        fail_lbl = new_label("oob_fail")
        ok_lbl = new_label("oob_ok")
        out.append(f"  br i1 {ok}, label %{ok_lbl}, label %{fail_lbl}")
        out.append(f"{fail_lbl}:")
        out.append(f"  call void @bhumi_oob_abort()")
        out.append(f"  unreachable")
        out.append(f"{ok_lbl}:")
        ptr_tmp = new_tmp()
        out.append(
            f"  {ptr_tmp} = getelementptr inbounds {llvm_ty}, {llvm_ty}* {arr_addr_token}, i32 0, i32 {idx_cast}"
        )
        out.append(f"  store {base_ty} {val}, {base_ty}* {ptr_tmp}")
    elif isinstance(stmt, IfStmt):
        cond = gen_expr(stmt.cond, out, expected="bool")
        then_lbl = new_label("then")
        else_lbl = new_label("else") if stmt.else_body else None
        end_lbl = new_label("endif")
        out.append(f"  br i1 {cond}, label %{then_lbl}, label %{else_lbl or end_lbl}")
        out.append(f"{then_lbl}:")
        symbol_table.push()
        _then_ctx = _make_scope_ctx()
        scope_drop_stack.append(_then_ctx)
        for s in stmt.then_body:
            gen_stmt(s, out, ret_ty)
        _emit_scope_drops(_then_ctx, out)
        scope_drop_stack.pop()
        symbol_table.pop()
        last = out[-1].strip() if out else ""
        if not (
            last.startswith("ret") or last == "unreachable" or last.startswith("br ")
        ):
            out.append(f"  br label %{end_lbl}")
        if stmt.else_body:
            out.append(f"{else_lbl}:")
            symbol_table.push()
            _else_ctx = _make_scope_ctx()
            scope_drop_stack.append(_else_ctx)
            if isinstance(stmt.else_body, list):
                for s in stmt.else_body:
                    gen_stmt(s, out, ret_ty)
            elif isinstance(stmt.else_body, IfStmt):
                gen_stmt(stmt.else_body, out, ret_ty)
            _emit_scope_drops(_else_ctx, out)
            scope_drop_stack.pop()
            symbol_table.pop()
            last = out[-1].strip() if out else ""
            if not (
                last.startswith("ret")
                or last == "unreachable"
                or last.startswith("br ")
            ):
                out.append(f"  br label %{end_lbl}")
        out.append(f"{end_lbl}:")
    elif isinstance(stmt, WhileStmt):
        head_lbl = new_label("while_head")
        body_lbl = new_label("while_body")
        end_lbl = new_label("while_end")
        loop_stack.append({"continue": head_lbl, "break": end_lbl})
        out.append(f"  br label %{head_lbl}")
        out.append(f"{head_lbl}:")
        cond = gen_expr(stmt.cond, out, expected="bool")
        out.append(f"  br i1 {cond}, label %{body_lbl}, label %{end_lbl}")
        out.append(f"{body_lbl}:")
        symbol_table.push()
        _while_ctx = _make_scope_ctx()
        scope_drop_stack.append(_while_ctx)
        for s in stmt.body:
            gen_stmt(s, out, ret_ty)
        _emit_scope_drops(_while_ctx, out)
        scope_drop_stack.pop()
        symbol_table.pop()
        last = out[-1].strip() if out else ""
        if not (
            last.startswith("ret") or last == "unreachable" or last.startswith("br ")
        ):
            out.append(f"  br label %{head_lbl}")
        out.append(f"{end_lbl}:")
        loop_stack.pop()
    elif isinstance(stmt, TypeSwitch):
        bhumi_report_error(
            getattr(stmt, "lineno", None),
            getattr(stmt, "col", None),
            "Internal compiler error: typeswitch remained in codegen (should be resolved at monomorphization)",
        )
    elif isinstance(stmt, ReturnStmt):
        val = None
        if stmt.expr:
            dst_lang = llvm_to_lang(ret_ty)
            val = gen_expr(stmt.expr, out, expected=dst_lang)
        _returned_var: Optional[str] = None
        if stmt.expr is not None and isinstance(stmt.expr, Var):
            _returned_var = stmt.expr.name
        if scope_drop_stack:
            import sys as _sys
            for ctx in reversed(scope_drop_stack):
                body_decl_names = ctx.get("body_decl_names", set())
                pre_owned = ctx.get("pre_owned_snapshot", set())
                candidates = set(body_decl_names)
                for _vn2 in list(owned_vars):
                    if _vn2 not in pre_owned:
                        candidates.add(_vn2)
                for nm in candidates:
                    if nm == _returned_var:
                        continue
                    cr = crumb_runtime.get(nm)
                    owned_here = (nm in owned_vars) or (
                        cr is not None and cr.get("owned")
                    )
                    if not owned_here:
                        continue
                    result = symbol_table.lookup(nm)
                    if result is None:
                        continue
                    llvm_ty, llvm_name = result
                    if not llvm_ty.endswith("*"):
                        continue
                    if cr is not None:
                        _rmax_v = cr.get("rmax")
                        _wmax_v = cr.get("wmax")
                        _rc_v = cr.get("rc", 0)
                        _wc_v = cr.get("wc", 0)
                        if _rmax_v is None and _wmax_v is None:
                            print(
                                f"[Bhumi] Warning: crumble '{nm}' dropped at scope exit (early return); "
                                f"no read (!r) or write (!w) limit was set, "
                                f"{_rc_v} read(s) and {_wc_v} write(s) consumed. "
                                f"Set crumble({nm})!r=<N>!w=<M>; to silence this.",
                                file=_sys.stderr,
                            )
                        elif _rmax_v is None:
                            print(
                                f"[Bhumi] Warning: crumble '{nm}' dropped at scope exit (early return); "
                                f"no read limit (!r) was set, {_rc_v} read(s) consumed. "
                                f"Set crumble({nm})!r=<count>; to silence this.",
                                file=_sys.stderr,
                            )
                        elif _wmax_v is None:
                            print(
                                f"[Bhumi] Warning: crumble '{nm}' dropped at scope exit (early return); "
                                f"no write limit (!w) was set, {_wc_v} write(s) consumed. "
                                f"Set crumble({nm})!w=<count>; to silence this.",
                                file=_sys.stderr,
                            )
                    addr_token = llvm_name if llvm_name.startswith("@") else f"%{llvm_name}_addr"
                    ptr_tmp = new_tmp()
                    out.append(
                        f"  {ptr_tmp} = load {llvm_ty}, {llvm_ty}* {addr_token}"
                    )
                    cast_tmp = new_tmp()
                    out.append(f"  {cast_tmp} = bitcast {llvm_ty} {ptr_tmp} to i8*")
                    ret_ar_skip = new_label("ret_ar_skip")
                    ret_ar_free = new_label("ret_ar_free")
                    ret_ar_null = new_tmp()
                    out.append(f"  {ret_ar_null} = icmp eq i8* {cast_tmp}, null")
                    out.append(f"  br i1 {ret_ar_null}, label %{ret_ar_skip}, label %{ret_ar_free}")
                    out.append(f"{ret_ar_free}:")
                    emit_deep_free(llvm_ty, ptr_tmp, out)
                    out.append(f"  store {llvm_ty} null, {llvm_ty}* {addr_token}")
                    out.append(f"  br label %{ret_ar_skip}")
                    out.append(f"{ret_ar_skip}:")
                for _me_ty, _me_ir, _me_vn in ctx.get("match_envelopes", []):
                    _me_addr = _me_ir if _me_ir.startswith("@") else f"%{_me_ir}_addr"
                    _me_ptr = new_tmp()
                    _me_cast = new_tmp()
                    _me_null = new_tmp()
                    _me_skip = new_label("ret_me_skip")
                    _me_free = new_label("ret_me_free")
                    out.append(f"  {_me_ptr} = load {_me_ty}, {_me_ty}* {_me_addr}")
                    out.append(f"  {_me_cast} = bitcast {_me_ty} {_me_ptr} to i8*")
                    out.append(f"  {_me_null} = icmp eq i8* {_me_cast}, null")
                    out.append(f"  br i1 {_me_null}, label %{_me_skip}, label %{_me_free}")
                    out.append(f"{_me_free}:")
                    emit_deep_free(_me_ty, _me_ptr, out)
                    out.append(f"  store {_me_ty} null, {_me_ty}* {_me_addr}")
                    out.append(f"  br label %{_me_skip}")
                    out.append(f"{_me_skip}:")
                ctx["match_envelopes"] = []
                ctx["extra_ir_owned"] = []
        if val:
            src_lang = infer_type(stmt.expr)
            dst_lang = llvm_to_lang(ret_ty)
            src_llvm_check = llvm_ty_of(src_lang) if src_lang else ret_ty
            if (
                src_llvm_check != ret_ty
                and src_llvm_check.endswith("*")
                and ret_ty.endswith("*")
                and src_llvm_check.startswith("%struct.")
                and (ret_ty.startswith("%enum.") or ret_ty.startswith("%struct."))
            ):
                if src_llvm_check != ret_ty:
                    bt = new_tmp()
                    out.append(f"  {bt} = bitcast {src_llvm_check} {val} to {ret_ty}")
                    val = bt
                out.append(f"  ret {ret_ty} {val}")
            else:
                cast_tmp = emit_cast_value(val, src_lang, dst_lang, out)
                if cast_tmp is None:
                    cast_tmp = val
                out.append(f"  ret {ret_ty} {cast_tmp}")
        else:
            out.append(f"  ret void")
    elif isinstance(stmt, ExprStmt):
        gen_expr(stmt.expr, out)
    elif isinstance(stmt, ForgetStmt):
        llvm_ty, llvm_name = symbol_table.lookup(stmt.varname)
        if not llvm_ty.endswith("*"):
            bhumi_report_error(
                getattr(stmt, "lineno", None),
                getattr(stmt, "col", None),
                f"Cannot forget non-pointer type '{llvm_ty}'",
            )
        addr_token = llvm_name if llvm_name.startswith("@") else f"%{llvm_name}_addr"
        ptr_tmp = new_tmp()
        out.append(f"  {ptr_tmp} = load {llvm_ty}, {llvm_ty}* {addr_token}")
        cast_tmp = new_tmp()
        out.append(f"  {cast_tmp} = bitcast {llvm_ty} {ptr_tmp} to i8*")
        skip_lbl     = new_label("forget_skip")
        try_free_lbl = new_label("forget_try")
        null_tmp = new_tmp()
        out.append(f"  {null_tmp} = icmp eq i8* {cast_tmp}, null")
        out.append(f"  br i1 {null_tmp}, label %{skip_lbl}, label %{try_free_lbl}")
        out.append(f"{try_free_lbl}:")
        emit_deep_free(llvm_ty, ptr_tmp, out, safe_envelope=True)
        null_store_lbl = new_label("forget_null_store")
        out.append(f"  br label %{null_store_lbl}")
        out.append(f"{null_store_lbl}:")
        out.append(f"  store {llvm_ty} null, {llvm_ty}* {addr_token}")
        _fgt_bep = binding_enum_payload.get(llvm_name)
        if _fgt_bep is not None:
            _fgt_ep, _fgt_en, _fgt_vi, _fgt_pty, _fgt_slot = _fgt_bep
            out.append(f"  store {_fgt_pty} null, {_fgt_pty}* {_fgt_slot}")
        out.append(f"  br label %{skip_lbl}")
        out.append(f"{skip_lbl}:")
        if stmt.varname in crumb_runtime:
            crumb_runtime[stmt.varname]["owned"] = False
        owned_vars.discard(stmt.varname)
        for _ctx in scope_drop_stack:
            _eirowned = _ctx.get("extra_ir_owned", [])
            _ctx["extra_ir_owned"] = [(_ir_nm, _ir_ty, _ir_src)
                for _ir_nm, _ir_ty, _ir_src in _eirowned
                if _ir_nm != llvm_name
            ]
    elif isinstance(stmt, Match):
        raw_ty = infer_type(stmt.expr)
        if isinstance(stmt.expr, Var):
            _sym = symbol_table.lookup(stmt.expr.name)
            if _sym is not None:
                _sym_llvm_ty = _sym[0]
                _sym_base = _sym_llvm_ty.rstrip("*")
                if _sym_base.startswith("%enum."):
                    raw_ty = _sym_base[len("%enum."):] + "*"
                elif _sym_base.startswith("%struct."):
                    _candidate = _sym_base[len("%struct."):]
                    if _candidate in enum_variant_map:
                        raw_ty = _candidate + "*"
        enum_name = None
        base = raw_ty
        while base.endswith("*"):
            base = base[:-1]
        if base.startswith("%enum."):
            enum_name = base[len("%enum.") :]
        elif base.startswith("%struct."):
            nm = base[len("%struct.") :]
            if nm in enum_variant_map:
                enum_name = nm
        elif base in enum_variant_map:
            enum_name = base
        if enum_name is not None:
            _orig_edef = globals().get("original_enum_defs", {}).get(enum_name)
            if _orig_edef and getattr(_orig_edef, "type_params", []):
                for _ename, _variants in enum_variant_map.items():
                    if "__mono__" not in _ename:
                        continue
                    if not _ename.startswith(enum_name + "__mono__"):
                        continue
                    _tparams = set(getattr(_orig_edef, "type_params", []))
                    if all(
                        p is None or p not in _tparams
                        for _, p in _variants
                    ):
                        enum_name = _ename
                        break
        if enum_name is None:
            if isinstance(stmt.expr, Var):
                _sym2 = symbol_table.lookup(stmt.expr.name)
                if _sym2 is not None:
                    _llvm2 = _sym2[0].rstrip("*")
                    if _llvm2.startswith("%enum."):
                        enum_name = _llvm2[len("%enum."):]
        if enum_name is None:
            raw_llvm = type_map.get(raw_ty, raw_ty)
            candidates = [
                high
                for high, low in type_map.items()
                if low == raw_llvm and high in enum_variant_map
            ]
            if len(candidates) == 1:
                enum_name = candidates[0]
            elif candidates:
                case_variant_names = {case.variant for case in stmt.cases}
                chosen = None
                for cand in candidates:
                    cand_variants = {v[0] for v in enum_variant_map[cand]}
                    if case_variant_names.issubset(cand_variants):
                        chosen = cand
                        break
                enum_name = chosen if chosen is not None else candidates[0]
        if enum_name is None:
            bhumi_report_error(
                getattr(stmt, "lineno", None),
                getattr(stmt, "col", None),
                f"Match expression is not an enum type: {raw_ty}",
            )
        llvm_enum_ty = type_map.get(enum_name, None)
        has_payloads = any(p is not None for (_, p) in enum_variant_map[enum_name])
        if llvm_enum_ty and llvm_enum_ty.startswith("i") and not has_payloads:
            val = gen_expr(stmt.expr, out, expected=enum_name)
            end_lbl = new_label("match_end")
            variant_labels = {
                vname: new_label(f"case_{vname}")
                for vname, _ in enum_variant_map[enum_name]
            }
            out.append(f"  switch {llvm_enum_ty} {val}, label %{end_lbl} [")
            for idx, (vname, _) in enumerate(enum_variant_map[enum_name]):
                out.append(f"	{llvm_enum_ty} {idx}, label %{variant_labels[vname]}")
            out.append("  ]")
            for case in stmt.cases:
                lbl = variant_labels.get(case.variant)
                if not lbl:
                    bhumi_report_error(
                        getattr(case, "lineno", None),
                        getattr(case, "col", None),
                        f"Unknown variant {case.variant} for enum {enum_name}",
                    )
                out.append(f"{lbl}:")
                symbol_table.push()
                _sw_arm_ctx = _make_scope_ctx()
                scope_drop_stack.append(_sw_arm_ctx)
                for s in case.body:
                    gen_stmt(s, out, ret_ty)
                _emit_scope_drops(_sw_arm_ctx, out)
                scope_drop_stack.pop()
                symbol_table.pop()
                last = out[-1].strip() if out else ""
                if not (
                    last.startswith("ret")
                    or last == "unreachable"
                    or last.startswith("br ")
                ):
                    out.append(f"  br label %{end_lbl}")
            out.append(f"{end_lbl}:")
            return
        enum_ptr = gen_expr(stmt.expr, out, expected=enum_name)
        tag_ptr = new_tmp()
        out.append(
            f"  {tag_ptr} = getelementptr inbounds %enum.{enum_name}, %enum.{enum_name}* {enum_ptr}, i32 0, i32 0"
        )
        loaded_tag = new_tmp()
        out.append(f"  {loaded_tag} = load i32, i32* {tag_ptr}")
        end_lbl = new_label("match_end")
        variant_labels = {
            vname: new_label(f"case_{vname}")
            for vname, _ in enum_variant_map[enum_name]
        }
        out.append(f"  switch i32 {loaded_tag}, label %{end_lbl} [")
        for idx, (vname, _) in enumerate(enum_variant_map[enum_name]):
            out.append(f"	i32 {idx}, label %{variant_labels[vname]}")
        out.append("  ]")
        def gen_nested_match_case(case, outer_enum_name, outer_enum_ptr, outer_payload_val, outer_payload_type, arm_end_lbl, out, ret_ty, outer_enum_ptr_owned=False):
            if case.nested_pattern is None:
                if outer_payload_val is not None and case.binding is not None:
                    llvm_payload_ty = llvm_ty_of(outer_payload_type)
                    binding_ir = f"{case.binding}_{new_tmp().lstrip('%')}"
                    _entry_alloca_buf.append(f"  %{binding_ir}_addr = alloca {llvm_payload_ty}")
                    if llvm_payload_ty.endswith("*"):
                        _entry_alloca_buf.append(f"  store {llvm_payload_ty} null, {llvm_payload_ty}* %{binding_ir}_addr")
                    out.append(
                        f"  store {llvm_payload_ty} {outer_payload_val}, {llvm_payload_ty}* %{binding_ir}_addr"
                    )
                    symbol_table.declare(case.binding, llvm_payload_ty, binding_ir)
                    _nested_payload_is_bhumi_obj = (
                        llvm_payload_ty.endswith("*")
                        and (
                            llvm_payload_ty.startswith("%enum.")
                            or llvm_payload_ty.startswith("%struct.")
                        )
                    )
                    if _nested_payload_is_bhumi_obj and outer_enum_ptr_owned:
                        owned_vars.add(case.binding)
                        if scope_drop_stack:
                            scope_drop_stack[-1].setdefault(
                                "extra_ir_owned", []
                            ).append((binding_ir, llvm_payload_ty, case.binding))
                for s in case.body:
                    gen_stmt(s, out, ret_ty)
                last = out[-1].strip() if out else ""
                if not (last.startswith("ret") or last == "unreachable" or last.startswith("br ")):
                    out.append(f"  br label %{arm_end_lbl}")
            else:
                inner_case = case.nested_pattern
                inner_enum_name = outer_payload_type
                if inner_enum_name.endswith("*"):
                    inner_enum_name = inner_enum_name[:-1]
                if inner_enum_name.startswith("%enum."):
                    inner_enum_name = inner_enum_name[len("%enum."):]
                elif inner_enum_name.startswith("%struct."):
                    inner_enum_name = inner_enum_name[len("%struct."):]
                if inner_enum_name not in enum_variant_map:
                    bhumi_report_error(
                        None, None,
                        f"Nested match: type '{inner_enum_name}' is not a known enum. "
                        f"Only enum types can be nested in match patterns."
                    )
                inner_enum_ptr = outer_payload_val
                inner_tag_ptr = new_tmp()
                out.append(
                    f"  {inner_tag_ptr} = getelementptr inbounds %enum.{inner_enum_name}, "
                    f"%enum.{inner_enum_name}* {inner_enum_ptr}, i32 0, i32 0"
                )
                inner_tag = new_tmp()
                out.append(f"  {inner_tag} = load i32, i32* {inner_tag_ptr}")
                inner_end_lbl = new_label("nested_match_end")
                inner_labels = {
                    vname: new_label(f"nested_case_{vname}")
                    for vname, _ in enum_variant_map[inner_enum_name]
                }
                inner_variant_info = next(
                    (v for v in enum_variant_map[inner_enum_name] if v[0] == inner_case.variant), None
                )
                if inner_variant_info is None:
                    bhumi_report_error(
                        None, None,
                        f"Nested match: unknown variant '{inner_case.variant}' "
                        f"for inner enum '{inner_enum_name}'"
                    )
                out.append(f"  switch i32 {inner_tag}, label %{inner_end_lbl} [")
                for idx2, (vname2, _) in enumerate(enum_variant_map[inner_enum_name]):
                    lbl2 = inner_labels[vname2]
                    out.append(f"	i32 {idx2}, label %{lbl2}")
                out.append("  ]")
                for vname2, vpayload2 in enum_variant_map[inner_enum_name]:
                    lbl2 = inner_labels[vname2]
                    out.append(f"{lbl2}:")
                    if vname2 != inner_case.variant:
                        out.append(f"  br label %{inner_end_lbl}")
                        continue
                    next_payload_val = None
                    next_payload_type = None
                    if vpayload2 is not None:
                        inner_payload_raw = new_tmp()
                        out.append(
                            f"  {inner_payload_raw} = getelementptr inbounds "
                            f"%enum.{inner_enum_name}, %enum.{inner_enum_name}* "
                            f"{inner_enum_ptr}, i32 0, i32 1"
                        )
                        inner_llvm_payload_ty = llvm_ty_of(vpayload2)
                        inner_payload_cast = new_tmp()
                        out.append(
                            f"  {inner_payload_cast} = bitcast [8 x i8]* {inner_payload_raw} "
                            f"to {inner_llvm_payload_ty}*"
                        )
                        inner_loaded = new_tmp()
                        out.append(
                            f"  {inner_loaded} = load {inner_llvm_payload_ty}, "
                            f"{inner_llvm_payload_ty}* {inner_payload_cast}"
                        )
                        next_payload_val = inner_loaded
                        next_payload_type = vpayload2
                    gen_nested_match_case(
                        inner_case, inner_enum_name, inner_enum_ptr,
                        next_payload_val, next_payload_type,
                        arm_end_lbl, out, ret_ty
                    )
                out.append(f"{inner_end_lbl}:")
                last = out[-1].strip() if out else ""
                if not (last.startswith("ret") or last == "unreachable" or last.startswith("br ")):
                    out.append(f"  br label %{arm_end_lbl}")
        for case in stmt.cases:
            lbl = variant_labels.get(case.variant)
            if not lbl:
                bhumi_report_error(
                    getattr(case, "lineno", None),
                    getattr(case, "col", None),
                    f"Unknown variant {case.variant} for enum {enum_name}",
                )
            out.append(f"{lbl}:")
            symbol_table.push()
            _arm_ctx = _make_scope_ctx()
            scope_drop_stack.append(_arm_ctx)
            variant_info = next(
                (v for v in enum_variant_map[enum_name] if v[0] == case.variant), None
            )
            if variant_info is None:
                bhumi_report_error(
                    getattr(case, "lineno", None),
                    getattr(case, "col", None),
                    f"Unknown variant {case.variant} for enum {enum_name}",
                )
            payload_type = variant_info[1]
            if (
                payload_type is not None
                and isinstance(payload_type, str)
                and re.fullmatch(r"[A-Z]\w*", payload_type)
                and payload_type not in type_map
                and payload_type not in enum_variant_map
            ):
                _orig_edef = globals().get("original_enum_defs", {}).get(
                    enum_name.split("__mono__")[0] if "__mono__" in enum_name else enum_name
                )
                _tparams = set(getattr(_orig_edef, "type_params", [])) if _orig_edef else set()
                _tp_idx = list(_tparams).index(payload_type) if payload_type in _tparams else None
                _resolved = None
                if _tp_idx is not None and "__mono__" in enum_name:
                    _suffix = enum_name.split("__mono__", 1)[1]
                    _parts = _suffix.split("_")
                    if _tp_idx < len(_parts):
                        _resolved = _parts[_tp_idx]
                if _resolved is None:
                    if isinstance(stmt.expr, Var):
                        _sym3 = symbol_table.lookup(stmt.expr.name)
                        if _sym3 is not None:
                            _sym_llvm = _sym3[0].rstrip("*")
                            if _sym_llvm.startswith("%enum."):
                                _mono = _sym_llvm[len("%enum."):]
                                _concrete_variants = enum_variant_map.get(_mono)
                                if _concrete_variants:
                                    for _vn, _vp in _concrete_variants:
                                        if _vn == case.variant and _vp is not None:
                                            _resolved = _vp
                                            break
                if _resolved and not re.fullmatch(r"[A-Z]\w*", _resolved):
                    payload_type = _resolved
            loaded_payload = None
            if payload_type is not None:
                payload_ptr_raw = new_tmp()
                out.append(
                    f"  {payload_ptr_raw} = getelementptr inbounds %enum.{enum_name}, %enum.{enum_name}* {enum_ptr}, i32 0, i32 1"
                )
                llvm_payload_ty = llvm_ty_of(payload_type)
                payload_ptr_cast = new_tmp()
                out.append(
                    f"  {payload_ptr_cast} = bitcast [8 x i8]* {payload_ptr_raw} to {llvm_payload_ty}*"
                )
                loaded_payload = new_tmp()
                out.append(
                    f"  {loaded_payload} = load {llvm_payload_ty}, {llvm_payload_ty}* {payload_ptr_cast}"
                )
                if case.nested_pattern is None and case.binding is not None:
                    binding_ir = f"{case.binding}_{new_tmp().lstrip('%')}"
                    _entry_alloca_buf.append(f"  %{binding_ir}_addr = alloca {llvm_payload_ty}")
                    if llvm_payload_ty.endswith("*"):
                        _entry_alloca_buf.append(f"  store {llvm_payload_ty} null, {llvm_payload_ty}* %{binding_ir}_addr")
                    out.append(
                        f"  store {llvm_payload_ty} {loaded_payload}, {llvm_payload_ty}* %{binding_ir}_addr"
                    )
                    _match_subj_owned = False
                    if isinstance(stmt.expr, Var):
                        _match_subj_owned = stmt.expr.name in owned_vars
                    if llvm_payload_ty.endswith("*"):
                        _null_subj_name = stmt.expr.name if isinstance(stmt.expr, Var) else None
                        _subj_live_after = (
                            _null_subj_name is not None
                            and _name_used_in_stmts(_null_subj_name, _fn_body_remaining)
                        )
                    else:
                        _subj_live_after = False
                    if llvm_payload_ty.endswith("*") and _match_subj_owned and not _subj_live_after:
                        out.append(
                            f"  store {llvm_payload_ty} null, {llvm_payload_ty}* {payload_ptr_cast}"
                        )
                    symbol_table.declare(case.binding, llvm_payload_ty, binding_ir)
                    if llvm_payload_ty.endswith("*"):
                        _v_idx = next(
                            (i for i, (vn, _) in enumerate(enum_variant_map.get(enum_name, []))
                             if vn == case.variant), None
                        )
                        _subj_var_name = stmt.expr.name if isinstance(stmt.expr, Var) else None
                        binding_enum_payload[binding_ir] = (
                            _subj_var_name, enum_name, _v_idx, llvm_payload_ty, payload_ptr_cast
                        )
                        binding_source_name[binding_ir] = case.binding
                    _payload_is_bhumi_obj = (
                        llvm_payload_ty.endswith("*")
                        and (
                            llvm_payload_ty.startswith("%enum.")
                            or llvm_payload_ty.startswith("%struct.")
                        )
                    )
                    if _payload_is_bhumi_obj and _match_subj_owned and not _subj_live_after:
                        owned_vars.add(case.binding)
                        if scope_drop_stack:
                            scope_drop_stack[-1].setdefault(
                                "extra_ir_owned", []
                            ).append((binding_ir, llvm_payload_ty, case.binding))
                    elif llvm_payload_ty == "i8*" and _match_subj_owned and not _subj_live_after:
                        owned_vars.add(case.binding)
                        if scope_drop_stack:
                            scope_drop_stack[-1].setdefault(
                                "extra_ir_owned", []
                            ).append((binding_ir, llvm_payload_ty, case.binding))
            if case.nested_pattern is not None:
                _subj_owned_nested = isinstance(stmt.expr, Var) and stmt.expr.name in owned_vars
                gen_nested_match_case(
                    case, enum_name, enum_ptr,
                    loaded_payload, payload_type,
                    end_lbl, out, ret_ty,
                    outer_enum_ptr_owned=_subj_owned_nested
                )
                _emit_scope_drops(_arm_ctx, out)
            else:
                for s in case.body:
                    gen_stmt(s, out, ret_ty)
                _emit_scope_drops(_arm_ctx, out)
                last = out[-1].strip() if out else ""
                if not (
                    last.startswith("ret")
                    or last == "unreachable"
                    or last.startswith("br ")
                ):
                    out.append(f"  br label %{end_lbl}")
            scope_drop_stack.pop()
            symbol_table.pop()
        out.append(f"{end_lbl}:")
        if isinstance(stmt.expr, Var) and stmt.expr.name in owned_vars:
            _subj_sym = symbol_table.lookup(stmt.expr.name)
            if _subj_sym is not None:
                _subj_llvm_ty, _subj_ir = _subj_sym
                if _subj_llvm_ty.endswith("*") and (
                    _subj_llvm_ty.startswith("%enum.")
                    or (_subj_llvm_ty.startswith("%struct.")
                        and _subj_llvm_ty[len("%struct."):-1] in enum_variant_map)
                ):
                    if scope_drop_stack:
                        scope_drop_stack[-1].setdefault("match_envelopes", []).append(
                            (_subj_llvm_ty, _subj_ir, stmt.expr.name)
                        )
                    else:
                        _env_ptr = new_tmp()
                        _env_addr = f"@{_subj_ir}" if _subj_ir.startswith("@") else f"%{_subj_ir}_addr"
                        out.append(f"  {_env_ptr} = load {_subj_llvm_ty}, {_subj_llvm_ty}* {_env_addr}")
                        _env_null_tmp = new_tmp()
                        _env_cast = new_tmp()
                        out.append(f"  {_env_cast} = bitcast {_subj_llvm_ty} {_env_ptr} to i8*")
                        _env_done_lbl = new_label("match_env_done")
                        _env_free_lbl = new_label("match_env_free")
                        out.append(f"  {_env_null_tmp} = icmp eq i8* {_env_cast}, null")
                        out.append(f"  br i1 {_env_null_tmp}, label %{_env_done_lbl}, label %{_env_free_lbl}")
                        out.append(f"{_env_free_lbl}:")
                        emit_deep_free(_subj_llvm_ty, _env_ptr, out)
                        out.append(f"  store {_subj_llvm_ty} null, {_subj_llvm_ty}* {_env_addr}")
                        out.append(f"  br label %{_env_done_lbl}")
                        out.append(f"{_env_done_lbl}:")
                    owned_vars.discard(stmt.expr.name)
def _check_no_bare_generic(typ: str, context: str, lineno=None, col=None):
    orig = globals().get("original_enum_defs", {})
    base = typ.rstrip("*")
    if base.startswith("%enum."):
        base = base[len("%enum."):]
    elif base.startswith("%struct."):
        base = base[len("%struct."):]
    edef = orig.get(base)
    if edef is None:
        return
    tparams = getattr(edef, "type_params", [])
    if not tparams:
        return
    if "__mono__" not in base and "<" not in typ:
        needed = ", ".join(tparams)
        bhumi_report_error(
            lineno, col,
            f"{context}: '{base}' is a generic enum requiring type arguments "
            f"<{needed}>, but was used without them. "
            f"Did you mean '{base}<{needed}>'?"
        )
def gen_func(fn: Func) -> List[str]:
    _saved_outer_alloca_buf = list(_entry_alloca_buf)
    _saved_outer_scope_drop = list(scope_drop_stack)
    _saved_outer_crumb = dict(crumb_runtime)
    _saved_outer_owned = set(owned_vars)
    _saved_outer_spilled_ssa = set(_ar_spilled_ssa_vals)
    _saved_outer_spill_name = dict(_ar_spill_val_to_name)
    _saved_outer_extern_spills = set(_extern_spill_names)
    crumb_runtime.clear()
    owned_vars.clear()
    binding_enum_payload.clear()
    binding_source_name.clear()
    _entry_alloca_buf.clear()
    _extern_spill_names.clear()
    _ar_spilled_ssa_vals.clear()
    _ar_spill_val_to_name.clear()
    scope_drop_stack.clear()
    def _restore_outer():
        _entry_alloca_buf.extend(_saved_outer_alloca_buf)
        scope_drop_stack.extend(_saved_outer_scope_drop)
        crumb_runtime.update(_saved_outer_crumb)
        owned_vars.update(_saved_outer_owned)
        _ar_spilled_ssa_vals.update(_saved_outer_spilled_ssa)
        _ar_spill_val_to_name.update(_saved_outer_spill_name)
        _extern_spill_names.update(_saved_outer_extern_spills)
    if fn.type_params:
        _restore_outer()
        return []
    if fn.ret_type == "#":
        _restore_outer()
        return []
    if fn.is_extern and fn.ret_type == "#":
        bhumi_report_error(
            getattr(fn, "lineno", None),
            getattr(fn, "col", None),
            "extern functions cannot use '#' as a return type",
        )
    if fn.is_extern:
        param_sig = ", ".join(f"{llvm_ty_of(t)} %{n}" for t, n in fn.params)
        ret_ty = llvm_ty_of(fn.ret_type)
        generated_mono[fn.name] = True
        _restore_outer()
        return [f"declare {ret_ty} @{fn.name}({param_sig})"]
    if fn.is_async:
        if fn.body is None or len(fn.body) == 0:
            bhumi_report_error(
                getattr(fn, "lineno", None),
                getattr(fn, "col", None),
                f"Async function '{fn.name}' has an empty body, cannot generate async state machine.",
            )
        generated_mono[fn.name] = True
        func_table[fn.name] = llvm_ty_of(fn.ret_type)
        symbol_table.push()
        codegen_adapter = type("CodegenAdapter", (), {})()
        setattr(codegen_adapter, "gen_expr", gen_expr)
        def _adapter_gen_stmt(stmt, outlist, ret_ty_inner):
            return gen_stmt(stmt, outlist, ret_ty_inner)
        setattr(codegen_adapter, "_gen_stmt", _adapter_gen_stmt)
        asm = AsyncStateMachine(fn, codegen_adapter)
        lines = asm.generate()
        struct_ty = f"%async.{fn.name}"
        func_table[f"{fn.name}_init"] = f"{struct_ty}*"
        func_table[f"{fn.name}_resume"] = "i1"
        symbol_table.pop()
        _restore_outer()
        return lines
    symbol_table.push()
    generated_mono[fn.name] = True
    globals()["__bhumi_current_codegen_fn"] = fn
    if fn.name == "main":
        ret_ty = "i32"
        out = [f"define i32 @main(i32 %argc, i8** %argv) {{", "entry:"]
        out.append("  store i8** %argv, i8*** @__argv_ptr")
    else:
        _check_no_bare_generic(
            fn.ret_type,
            f"Return type of function '{fn.name}'",
            getattr(fn, "lineno", None), getattr(fn, "col", None)
        )
        for _pty, _pname in fn.params:
            _check_no_bare_generic(
                _pty,
                f"Parameter '{_pname}' of function '{fn.name}'",
                getattr(fn, "lineno", None), getattr(fn, "col", None)
            )
        ret_ty = llvm_ty_of(fn.ret_type)
        param_sig = ", ".join(f"{llvm_ty_of(t)} %{n}" for t, n in fn.params)
        out = [f"define {ret_ty} @{fn.name}({param_sig}) {{", "entry:"]
    for typ, name in fn.params:
        llvm_ty = llvm_ty_of(typ)
        _fixed_arr = re.fullmatch(r"([A-Za-z_]\w*\**)\[(\d+)]", typ)
        _unsized_arr = re.fullmatch(r"([A-Za-z_]\w*\**)\[]", typ)
        if _fixed_arr:
            count = _fixed_arr.group(2)
            out.append(f"  %{name}_addr = alloca {llvm_ty}")
            out.append(f"  store {llvm_ty} %{name}, {llvm_ty}* %{name}_addr")
            out.append(f"  %{name}_len = alloca i32")
            out.append(f"  store i32 {count}, i32* %{name}_len")
            inner_ty = llvm_ty[:-1]
            symbol_table.declare(name, inner_ty, name)
        elif _unsized_arr:
            out.append(f"  %{name}_addr = alloca {llvm_ty}")
            out.append(f"  store {llvm_ty} %{name}, {llvm_ty}* %{name}_addr")
            out.append(f"  %{name}_len = alloca i32")
            out.append(f"  store i32 -1, i32* %{name}_len")
            symbol_table.declare(name, llvm_ty, name)
        else:
            out.append(f"  %{name}_addr = alloca {llvm_ty}")
            out.append(f"  store {llvm_ty} %{name}, {llvm_ty}* %{name}_addr")
            symbol_table.declare(name, llvm_ty, name)
    decls = []
    def walk(node):
        if node is None:
            return
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if type(node).__name__ == "VarDecl":
            decls.append(node)
            return
        for attr in getattr(node, "__dict__", {}):
            val = getattr(node, attr)
            if isinstance(val, list):
                for v in val:
                    walk(v)
            elif hasattr(val, "__dict__"):
                walk(val)
    for s in fn.body or []:
        walk(s)
    seen = set()
    for stmt in decls:
        if stmt.name in seen:
            continue
        seen.add(stmt.name)
        if "[" in stmt.typ:
            base, rest = stmt.typ.split("[", 1)
            count = rest[:-1]
            elem_llvm = llvm_ty_of(base)
            llvm_ty = f"[{count} x {elem_llvm}]"
            if not symbol_table.lookup(stmt.name):
                out.append(f"  %{stmt.name}_addr = alloca {llvm_ty}")
                out.append(
                    f"  store {llvm_ty} zeroinitializer, {llvm_ty}* %{stmt.name}_addr"
                )
                out.append(f"  %{stmt.name}_len  = alloca i32")
                out.append(f"  store i32 {count}, i32* %{stmt.name}_len")
                symbol_table.declare(stmt.name, llvm_ty, stmt.name)
        else:
            llvm_ty = llvm_ty_of(stmt.typ)
            if not symbol_table.lookup(stmt.name):
                out.append(f"  %{stmt.name}_addr = alloca {llvm_ty}")
                if llvm_ty.endswith("*"):
                    out.append(f"  store {llvm_ty} null, {llvm_ty}* %{stmt.name}_addr")
                elif llvm_ty == "double" or llvm_ty == "float":
                    out.append(f"  store {llvm_ty} 0.0, {llvm_ty}* %{stmt.name}_addr")
                elif llvm_ty.startswith("i"):
                    out.append(f"  store {llvm_ty} 0, {llvm_ty}* %{stmt.name}_addr")
                else:
                    out.append(
                        f"  store {llvm_ty} zeroinitializer, {llvm_ty}* %{stmt.name}_addr"
                    )
                symbol_table.declare(stmt.name, llvm_ty, stmt.name)
    entry_insert_pos = len(out)
    has_return = False
    _fn_scope_ctx = _make_scope_ctx()
    scope_drop_stack.append(_fn_scope_ctx)
    _body_list = list(fn.body or [])
    for _stmt_idx, stmt in enumerate(_body_list):
        global _fn_body_remaining
        _fn_body_remaining = _body_list[_stmt_idx + 1:]
        if isinstance(stmt, ReturnStmt):
            gen_stmt(stmt, out, ret_ty)
            has_return = True
            break
        else:
            gen_stmt(stmt, out, ret_ty)
    _fn_body_remaining = []
    if not has_return:
        _emit_scope_drops(_fn_scope_ctx, out, force=True)
    if scope_drop_stack:
        scope_drop_stack.pop()
    if _entry_alloca_buf:
        for i, line in enumerate(_entry_alloca_buf):
            out.insert(entry_insert_pos + i, line)
        _entry_alloca_buf.clear()
    scope_drop_stack.extend(_saved_outer_scope_drop)
    crumb_runtime.update(_saved_outer_crumb)
    owned_vars.update(_saved_outer_owned)
    _entry_alloca_buf.extend(_saved_outer_alloca_buf)
    _ar_spilled_ssa_vals.update(_saved_outer_spilled_ssa)
    _ar_spill_val_to_name.update(_saved_outer_spill_name)
    _extern_spill_names.update(_saved_outer_extern_spills)
    if not has_return:
        if ret_ty == "void":
            out.append("  ret void")
        elif ret_ty == "double":
            out.append(f"  ret {ret_ty} 0.0")
        elif ret_ty == "i8*":
            out.append("  ret i8* null")
        elif ret_ty.startswith("i"):
            out.append(f"  ret {ret_ty} 0")
        else:
            out.append(f"  ret {ret_ty} null")
    out.append("}")
    globals()["__bhumi_current_codegen_fn"] = None
    symbol_table.pop()
    return out
def annotate_types(prog: Program) -> None:
    global _expr_type_cache
    _expr_type_cache.clear()
    ann_env = TypeEnv()
    for g in prog.globals:
        ann_env.declare(g.name, g.typ)
    def _cache(expr: Expr, typ: str) -> str:
        _expr_type_cache[id(expr)] = typ
        return typ
    def _ann_expr(expr: Expr, expected: Optional[str] = None) -> Optional[str]:
        if expr is None:
            return None
        existing = _expr_type_cache.get(id(expr))
        if existing is not None:
            return existing
        if isinstance(expr, IntLit):
            return _cache(expr, "int")
        if isinstance(expr, FloatLit):
            t = "float32" if getattr(expr, "bits", 64) == 32 else "float"
            return _cache(expr, t)
        if isinstance(expr, BoolLit):
            return _cache(expr, "bool")
        if isinstance(expr, CharLit):
            return _cache(expr, "char")
        if isinstance(expr, StrLit):
            return _cache(expr, "string")
        if isinstance(expr, NullLit):
            return _cache(expr, "null")
        if isinstance(expr, CallerType):
            t = expected if expected is not None else "#"
            return _cache(expr, t)
        if isinstance(expr, Cast):
            _ann_expr(expr.expr)
            return _cache(expr, expr.typ)
        if isinstance(expr, TypeofExpr):
            _ann_expr(expr.expr)
            return _cache(expr, "string")
        if isinstance(expr, Var):
            t = ann_env.lookup(expr.name)
            if t is None:
                return None
            return _cache(expr, t)
        if isinstance(expr, AddressOf):
            inner_t = _ann_expr(expr.expr)
            if inner_t is None:
                return None
            return _cache(expr, inner_t + "*")
        if isinstance(expr, UnaryDeref):
            ptr_t = _ann_expr(expr.ptr)
            if ptr_t is None or not ptr_t.endswith("*"):
                return None
            return _cache(expr, ptr_t[:-1])
        if isinstance(expr, UnaryOp):
            inner_t = _ann_expr(expr.expr)
            if inner_t is None:
                return None
            if expr.op == "!":
                return _cache(expr, "bool")
            return _cache(expr, inner_t)
        if isinstance(expr, BinOp):
            left_t  = _ann_expr(expr.left)
            right_t = _ann_expr(expr.right)
            if left_t is None or right_t is None:
                return None
            if expr.op in {"==", "!=", "<", "<=", ">", ">=", "&&", "||"}:
                return _cache(expr, "bool")
            common = unify_int_types(left_t, right_t) or (left_t if left_t == right_t else None)
            if common is None:
                return None
            return _cache(expr, common)
        if isinstance(expr, Ternary):
            _ann_expr(expr.cond, "bool")
            then_t = _ann_expr(expr.then_expr, expected)
            _ann_expr(expr.else_expr, expected)
            if then_t is not None:
                return _cache(expr, then_t)
            return None
        if isinstance(expr, AwaitExpr):
            inner = expr.expr
            if isinstance(inner, Call):
                base_fn = _func_name_map.get(inner.name)
                if base_fn is not None:
                    _ann_expr(inner)
                    return _cache(expr, base_fn.ret_type)
            return None
        if isinstance(expr, VAwaitExpr):
            _ann_expr(expr.expr)
            return None
        if isinstance(expr, FieldAccess):
            base_t = _ann_expr(expr.base)
            if base_t is None:
                return None
            base_name = base_t.rstrip("*")
            if base_name.startswith("%struct."):
                base_name = base_name[len("%struct."):]
            if base_name in struct_field_map:
                field_dict = dict(struct_field_map[base_name])
                ft = field_dict.get(expr.field)
                if ft is not None:
                    return _cache(expr, ft)
            return None
        if isinstance(expr, Index):
            _ann_expr(expr.index)
            if not isinstance(expr.array, Var):
                return None
            arr_info = ann_env.lookup(expr.array.name)
            if arr_info is None:
                return None
            if "[" in arr_info:
                base = arr_info.split("[", 1)[0]
                _cache(expr.array, arr_info)
                return _cache(expr, base)
            return None
        if isinstance(expr, StructInit):
            for _, fexpr in expr.fields:
                _ann_expr(fexpr)
            return _cache(expr, expr.name + "*")
        if isinstance(expr, ArrayInit):
            elem_t = None
            for el in expr.elements:
                t = _ann_expr(el)
                if elem_t is None:
                    elem_t = t
            if elem_t is None:
                return None
            return _cache(expr, f"{elem_t}[{len(expr.elements)}]")
        if isinstance(expr, Call):
            variant_name = expr.name
            qualified_enum = None
            if "->" in expr.name:
                qualified_enum, variant_name = expr.name.split("->", 1)
            matches = []
            for ename, variants in enum_variant_map.items():
                if "__mono__" in ename:
                    continue
                if qualified_enum is not None and ename != qualified_enum:
                    continue
                for vname, payload in variants:
                    if vname == variant_name:
                        orig = globals().get("original_enum_defs", {}).get(ename)
                        tparams = getattr(orig, "type_params", []) if orig else []
                        matches.append((ename, payload, bool(tparams)))
                        break
            if matches:
                concrete = [(e, p, g) for e, p, g in matches if not g]
                chosen_enum, chosen_payload, has_tparams = (concrete[0] if concrete else matches[0])
                orig_edef = globals().get("original_enum_defs", {}).get(chosen_enum)
                tparams = getattr(orig_edef, "type_params", []) if orig_edef else []
                payload_expected: Optional[str] = None
                if has_tparams and chosen_payload is not None and chosen_payload in tparams:
                    if expected is not None:
                        exp_bare = expected.rstrip("*")
                        gm_exp = re.fullmatch(re.escape(chosen_enum) + r"<(.+)>", exp_bare)
                        if gm_exp:
                            parts = [p.strip() for p in gm_exp.group(1).split(",")]
                            if len(tparams) == 1 and len(parts) == 1:
                                payload_expected = parts[0]
                            elif len(parts) == len(tparams):
                                idx = tparams.index(chosen_payload)
                                payload_expected = parts[idx]
                        if payload_expected is None:
                            mono_prefix = chosen_enum + "__mono__"
                            if exp_bare.startswith(mono_prefix):
                                mono_suffix = exp_bare[len(mono_prefix):]
                                parts = mono_suffix.split("_")
                                for k, v in type_map.items():
                                    if mangle_type(k) == mono_suffix or k == mono_suffix:
                                        payload_expected = k
                                        break
                                if payload_expected is None and len(parts) >= 1:
                                    payload_expected = parts[0]
                else:
                    payload_expected = chosen_payload
                arg_types = [_ann_expr(a, expected=payload_expected) for a in (expr.args or [])]
                if has_tparams and chosen_payload is not None and chosen_payload in tparams:
                    actual_payload = (arg_types[0] if arg_types else None) or payload_expected
                    if actual_payload is not None:
                        if len(tparams) == 1:
                            try:
                                mono = ensure_monomorph_for_enum(chosen_enum, [actual_payload])
                                return _cache(expr, mono + "*")
                            except Exception:
                                pass
                        else:
                            if expected is not None:
                                exp_bare = expected.rstrip("*")
                                gm = re.fullmatch(re.escape(chosen_enum) + r"<(.+)>", exp_bare)
                                if gm:
                                    parts = [p.strip() for p in gm.group(1).split(",")]
                                    if len(parts) == len(tparams):
                                        try:
                                            mono = ensure_monomorph_for_enum(chosen_enum, parts)
                                            return _cache(expr, mono + "*")
                                        except Exception:
                                            pass
                    return _cache(expr, chosen_enum + "*")
                if type_map.get(chosen_enum, "").startswith("i") and chosen_payload is None:
                    return _cache(expr, chosen_enum)
                return _cache(expr, chosen_enum + "*")
            base_fn = _func_name_map.get(expr.name)
            arg_expected: List[Optional[str]] = []
            if base_fn is not None and base_fn.params:
                for (ptype, _) in base_fn.params:
                    arg_expected.append(None if ptype in (getattr(base_fn, "type_params", []) or []) else ptype)
            while len(arg_expected) < len(expr.args or []):
                arg_expected.append(None)
            arg_types = [_ann_expr(a, expected=arg_expected[i])
                         for i, a in enumerate(expr.args or [])]
            if base_fn is not None and base_fn.ret_type == "#":
                if expected is not None:
                    return _cache(expr, expected)
                for ft_name in func_table:
                    if ft_name.startswith(expr.name + "__mono__"):
                        ret_llvm = func_table[ft_name]
                        for k, v in type_map.items():
                            if v == ret_llvm:
                                return _cache(expr, k)
                return None
            if base_fn is not None and getattr(base_fn, "type_params", None):
                concrete_arg_types = [t for t in arg_types if t is not None]
                if concrete_arg_types:
                    try:
                        mononame = ensure_monomorph_call(expr, [], expected_ret=expected)
                        ret_llvm = func_table.get(mononame)
                        if ret_llvm is not None:
                            for k, v in type_map.items():
                                if v == ret_llvm:
                                    return _cache(expr, k)
                            if ret_llvm.startswith("%struct."):
                                return _cache(expr, ret_llvm[8:] + "*")
                            if ret_llvm.startswith("%enum."):
                                return _cache(expr, ret_llvm[6:].rstrip("*") + "*")
                    except Exception:
                        pass
                return None
            if expr.name in func_table:
                ret_llvm = func_table[expr.name]
                for k, v in type_map.items():
                    if v == ret_llvm:
                        return _cache(expr, k)
                if ret_llvm.startswith("%struct."):
                    return _cache(expr, ret_llvm[8:] + "*")
                if ret_llvm.startswith("%enum."):
                    return _cache(expr, ret_llvm[6:].rstrip("*") + "*")
                return _cache(expr, ret_llvm)
            if base_fn is not None:
                ret = base_fn.ret_type
                if ret and ret != "#":
                    return _cache(expr, ret)
            return None
        return None
    def _ann_stmt(stmt: Stmt, ret_type: str):
        if stmt is None:
            return
        if isinstance(stmt, VarDecl):
            ann_env.declare(stmt.name, stmt.typ)
            if stmt.expr:
                _ann_expr(stmt.expr, expected=stmt.typ)
            return
        if isinstance(stmt, Assign):
            if isinstance(stmt.name, str):
                var_t = ann_env.lookup(stmt.name)
                _ann_expr(stmt.expr, expected=var_t)
            elif isinstance(stmt.name, UnaryDeref):
                _ann_expr(stmt.name.ptr)
                _ann_expr(stmt.expr)
            return
        if isinstance(stmt, IndexAssign):
            _ann_expr(stmt.index)
            _ann_expr(stmt.value)
            return
        if isinstance(stmt, ExprStmt):
            _ann_expr(stmt.expr)
            return
        if isinstance(stmt, ReturnStmt):
            if stmt.expr:
                _ann_expr(stmt.expr, expected=ret_type)
            return
        if isinstance(stmt, IfStmt):
            _ann_expr(stmt.cond, "bool")
            ann_env.push()
            for s in (stmt.then_body or []):
                _ann_stmt(s, ret_type)
            ann_env.pop()
            if stmt.else_body:
                ann_env.push()
                if isinstance(stmt.else_body, list):
                    for s in stmt.else_body:
                        _ann_stmt(s, ret_type)
                else:
                    _ann_stmt(stmt.else_body, ret_type)
                ann_env.pop()
            return
        if isinstance(stmt, WhileStmt):
            _ann_expr(stmt.cond, "bool")
            ann_env.push()
            for s in (stmt.body or []):
                _ann_stmt(s, ret_type)
            ann_env.pop()
            return
        if isinstance(stmt, Match):
            _ann_expr(stmt.expr)
            for case in stmt.cases:
                ann_env.push()
                matched_type = _expr_type_cache.get(id(stmt.expr))
                if matched_type and case.binding:
                    bare = matched_type.rstrip("*")
                    variants = enum_variant_map.get(bare, [])
                    for vname, payload in variants:
                        if vname == case.variant and payload:
                            ann_env.declare(case.binding, payload)
                            break
                for s in (case.body or []):
                    _ann_stmt(s, ret_type)
                ann_env.pop()
            return
        if isinstance(stmt, (ContinueStmt, BreakStmt, CrumbleStmt, ForgetStmt)):
            return
        for attr in getattr(stmt, "__dict__", {}):
            val = getattr(stmt, attr)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, Stmt):
                        _ann_stmt(item, ret_type)
                    elif isinstance(item, Expr):
                        _ann_expr(item)
    for fn in prog.funcs:
        if fn.is_extern:
            continue
        if fn.type_params or fn.ret_type == "#":
            continue
        ann_env.push()
        for (param_typ, param_name) in (fn.params or []):
            ann_env.declare(param_name, param_typ)
        for stmt in (fn.body or []):
            _ann_stmt(stmt, fn.ret_type)
        ann_env.pop()
def compile_program(prog: Program) -> str:
    global all_funcs, func_table, builtins_emitted, _func_name_map
    all_funcs = prog.funcs[:]
    _func_name_map = {f.name: f for f in all_funcs}
    string_constants.clear()
    func_table.clear()
    for fn in prog.funcs:
        if fn.type_params:
            continue
        if fn.ret_type == "#":
            continue
        llvm_ret_ty = llvm_ty_of(fn.ret_type)
        func_table[fn.name] = llvm_ret_ty
    func_table["exit"] = "void"
    func_table["malloc"] = "i8*"
    func_table["free"] = "void"
    func_table["bhumi_c_free"] = "void"
    func_table["bhumi_safe_c_free"] = "void"
    func_table["bhumi_ffi_free"] = "void"
    func_table["bhumi_tbl_insert"] = "void"
    func_table["bhumi_tbl_remove"] = "void"
    func_table["bhumi_tbl_contains"] = "i1"
    func_table["bhumi_ctbl_insert"] = "void"
    func_table["bhumi_ctbl_remove"] = "void"
    func_table["bhumi_ctbl_contains"] = "i1"
    func_table["puts"] = "i32"
    func_table["strlen"] = "i64"
    func_table["bhumi_argc"] = "i64"
    func_table["bhumi_argv"] = "i8*"
    has_user_main = False
    for fn in prog.funcs:
        if fn.name == "main":
            has_user_main = True
            fn.name = "user_main"
            llvm_ret_ty = llvm_ty_of(fn.ret_type)
            func_table.pop("main", None)
            func_table["user_main"] = llvm_ret_ty
            func_table["main"] = func_table["user_main"]
            break
    lines: List[str] = [
        "; ModuleID = 'bhumi'",
        f'source_filename = "{compiled}"',
        "@__argv_ptr = global i8** null",
        "declare i8* @malloc(i64)",
        "declare void @free(i8*)",
        "declare i64 @strlen(i8*)",
        "declare i32 @puts(i8*)",
        "declare void @exit(i32)",
        "declare i64 @time(i64*)",
        "declare void @srand(i32)",
        "declare i32 @rand()",
        "declare i32 @usleep(i32)",
        "declare i64 @malloc_usable_size(i8*)",
        "declare i8* @signal(i32, i8*)",
        "",
    ]
    runtime_block = """
@.oob_msg = private unnamed_addr constant [52 x i8] c"[BhumiCompiler-RT-CHCK]: Index out of bounds error.\\00"
@.null_msg = private unnamed_addr constant [45 x i8] c"[BhumiCompiler-RT-CHCK]: Null pointer deref.\\00"
@.heap_msg = private unnamed_addr constant [67 x i8] c"[BhumiCompiler-RT-HEAP]: Invalid free or heap corruption detected.\\00"
@.segv_msg = private unnamed_addr constant [71 x i8] c"[BhumiCompiler-RT-CHCK]: Segmentation fault / memory violation caught.\\00"
@.ffi_free_msg = private unnamed_addr constant [55 x i8] c"[BhumiCompiler-RT-HEAP]: free() on bhumi-owned pointer\\00"
@.forget_c_msg = private unnamed_addr constant [55 x i8] c"[BhumiCompiler-RT-HEAP]: forget() on non-bhumi pointer\\00"
@.alloc_magic = global i64 0
define void @bhumi_signal_handler(i32 %sig) {
entry:
  %tmp = call i32 @puts(i8* getelementptr inbounds ([71 x i8], [71 x i8]* @.segv_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
}
define void @bhumi_oob_abort() {
entry:
  %tmp_puts = call i32 @puts(i8* getelementptr inbounds ([52 x i8], [52 x i8]* @.oob_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
}
define void @bhumi_null_abort() {
entry:
  %tmp_puts1 = call i32 @puts(i8* getelementptr inbounds ([45 x i8], [45 x i8]* @.null_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
}
define void @bhumi_init_runtime() {
entry:
  %t = call i64 @time(i64* null)
  %t32 = trunc i64 %t to i32
  call void @srand(i32 %t32)
  %r = call i32 @rand()
  %r64 = zext i32 %r to i64
  %xor_magic = xor i64 %r64, 16045690984833335023
  store i64 %xor_magic, i64* @.alloc_magic
  %handler = bitcast void (i32)* @bhumi_signal_handler to i8*
  %_prev_segv = call i8* @signal(i32 11, i8* %handler)
  %_prev_abrt = call i8* @signal(i32 6, i8* %handler)
  ret void
}
@.bhumi_tbl_ptr = global i8** null
@.bhumi_tbl_cap = global i64 0
@.bhumi_tbl_cnt = global i64 0
define void @bhumi_tbl_raw_insert(i8** %slots, i64 %cap, i8* %ptr) {
entry:
  %mask = sub i64 %cap, 1
  %pint = ptrtoint i8* %ptr to i64
  %hash = and i64 %pint, %mask
  br label %probe
probe:
  %slot = phi i64 [ %hash, %entry ], [ %next_wrap, %occupied ]
  %ep = getelementptr i8*, i8** %slots, i64 %slot
  %cur = load i8*, i8** %ep
  %is_empty = icmp eq i8* %cur, null
  br i1 %is_empty, label %do_store, label %occupied
occupied:
  %next = add i64 %slot, 1
  %next_wrap = and i64 %next, %mask
  br label %probe
do_store:
  store i8* %ptr, i8** %ep
  ret void
}
define void @bhumi_tbl_grow(i64 %newcap) {
entry:
  %nbytes = mul i64 %newcap, 8
  %raw = call i8* @malloc(i64 %nbytes)
  %new_slots = bitcast i8* %raw to i8**
  br label %zero_loop
zero_loop:
  %zi = phi i64 [ 0, %entry ], [ %zi_next, %zero_loop ]
  %zep = getelementptr i8*, i8** %new_slots, i64 %zi
  store i8* null, i8** %zep
  %zi_next = add i64 %zi, 1
  %zi_done = icmp eq i64 %zi_next, %newcap
  br i1 %zi_done, label %rehash, label %zero_loop
rehash:
  %old_slots = load i8**, i8*** @.bhumi_tbl_ptr
  %old_cap   = load i64, i64* @.bhumi_tbl_cap
  %old_null  = icmp eq i8** %old_slots, null
  br i1 %old_null, label %rehash_done, label %rehash_loop
rehash_loop:
  %ri = phi i64 [ 0, %rehash ], [ %ri_next, %rehash_cont ]
  %rep = getelementptr i8*, i8** %old_slots, i64 %ri
  %rval = load i8*, i8** %rep
  %r_empty = icmp eq i8* %rval, null
  br i1 %r_empty, label %rehash_cont, label %do_reinsert
do_reinsert:
  call void @bhumi_tbl_raw_insert(i8** %new_slots, i64 %newcap, i8* %rval)
  br label %rehash_cont
rehash_cont:
  %ri_next = add i64 %ri, 1
  %ri_done = icmp eq i64 %ri_next, %old_cap
  br i1 %ri_done, label %free_old, label %rehash_loop
free_old:
  %old_raw = bitcast i8** %old_slots to i8*
  call void @free(i8* %old_raw)
  br label %rehash_done
rehash_done:
  store i8** %new_slots, i8*** @.bhumi_tbl_ptr
  store i64 %newcap,     i64*  @.bhumi_tbl_cap
  ret void
}
define void @bhumi_tbl_ensure_init() {
entry:
  %cap = load i64, i64* @.bhumi_tbl_cap
  %need_init = icmp eq i64 %cap, 0
  br i1 %need_init, label %do_init, label %done
do_init:
  call void @bhumi_tbl_grow(i64 64)
  br label %done
done:
  ret void
}
define void @bhumi_tbl_insert(i8* %ptr) {
entry:
  call void @bhumi_tbl_ensure_init()
  %cnt = load i64, i64* @.bhumi_tbl_cnt
  %cap = load i64, i64* @.bhumi_tbl_cap
  %cnt4 = mul i64 %cnt, 4
  %cap3 = mul i64 %cap, 3
  %overload = icmp uge i64 %cnt4, %cap3
  br i1 %overload, label %do_grow, label %do_insert
do_grow:
  %newcap = mul i64 %cap, 2
  call void @bhumi_tbl_grow(i64 %newcap)
  br label %do_insert
do_insert:
  %slots = load i8**, i8*** @.bhumi_tbl_ptr
  %cap2  = load i64, i64* @.bhumi_tbl_cap
  call void @bhumi_tbl_raw_insert(i8** %slots, i64 %cap2, i8* %ptr)
  %cnt2 = load i64, i64* @.bhumi_tbl_cnt
  %cnt3 = add i64 %cnt2, 1
  store i64 %cnt3, i64* @.bhumi_tbl_cnt
  ret void
}
define void @bhumi_tbl_remove(i8* %ptr) {
entry:
  %cap = load i64, i64* @.bhumi_tbl_cap
  %is_empty_tbl = icmp eq i64 %cap, 0
  br i1 %is_empty_tbl, label %not_found, label %do_remove
do_remove:
  %mask = sub i64 %cap, 1
  %slots = load i8**, i8*** @.bhumi_tbl_ptr
  %pint = ptrtoint i8* %ptr to i64
  %hash = and i64 %pint, %mask
  br label %find_loop
find_loop:
  %fi = phi i64 [ %hash, %do_remove ], [ %fwrap, %find_cont ]
  %fep = getelementptr i8*, i8** %slots, i64 %fi
  %fcur = load i8*, i8** %fep
  %is_null = icmp eq i8* %fcur, null
  br i1 %is_null, label %not_found, label %check_match
check_match:
  %match = icmp eq i8* %fcur, %ptr
  br i1 %match, label %found, label %find_cont
find_cont:
  %fnext = add i64 %fi, 1
  %fwrap = and i64 %fnext, %mask
  br label %find_loop
found:
  store i8* null, i8** %fep
  %shift_start = add i64 %fi, 1
  %shift_wrap = and i64 %shift_start, %mask
  br label %shift_loop
shift_loop:
  %si = phi i64 [ %shift_wrap, %found ], [ %snext_wrap, %shift_cont ]
  %sep = getelementptr i8*, i8** %slots, i64 %si
  %scur = load i8*, i8** %sep
  %s_empty = icmp eq i8* %scur, null
  br i1 %s_empty, label %shift_done, label %do_shift
do_shift:
  %prev_si = sub i64 %si, 1
  %prev_si_wrap = and i64 %prev_si, %mask
  %prev_ep = getelementptr i8*, i8** %slots, i64 %prev_si_wrap
  %prev_val = load i8*, i8** %prev_ep
  %prev_empty = icmp eq i8* %prev_val, null
  br i1 %prev_empty, label %can_shift, label %no_shift
can_shift:
  store i8* %scur, i8** %prev_ep
  store i8* null, i8** %sep
  br label %shift_cont
no_shift:
  br label %shift_cont
shift_cont:
  %snext = add i64 %si, 1
  %snext_wrap = and i64 %snext, %mask
  br label %shift_loop
shift_done:
  %cnt_r = load i64, i64* @.bhumi_tbl_cnt
  %cnt_r1 = sub i64 %cnt_r, 1
  store i64 %cnt_r1, i64* @.bhumi_tbl_cnt
  ret void
not_found:
  ret void
}
define i1 @bhumi_tbl_contains(i8* %ptr) {
entry:
  %is_null = icmp eq i8* %ptr, null
  br i1 %is_null, label %ret_false, label %check_init
check_init:
  %cap = load i64, i64* @.bhumi_tbl_cap
  %no_cap = icmp eq i64 %cap, 0
  br i1 %no_cap, label %ret_false, label %do_probe
do_probe:
  %mask = sub i64 %cap, 1
  %slots = load i8**, i8*** @.bhumi_tbl_ptr
  %pint = ptrtoint i8* %ptr to i64
  %hash = and i64 %pint, %mask
  br label %probe
probe:
  %slot = phi i64 [ %hash, %do_probe ], [ %next_wrap, %cont ]
  %ep = getelementptr i8*, i8** %slots, i64 %slot
  %cur = load i8*, i8** %ep
  %is_empty = icmp eq i8* %cur, null
  br i1 %is_empty, label %ret_false, label %check_match
check_match:
  %match = icmp eq i8* %cur, %ptr
  br i1 %match, label %ret_true, label %cont
cont:
  %next = add i64 %slot, 1
  %next_wrap = and i64 %next, %mask
  br label %probe
ret_true:
  ret i1 1
ret_false:
  ret i1 0
}
define i8* @bhumi_malloc(i64 %usize) {
entry:
  %hdr_sz = add i64 %usize, 24
  %ovf = icmp ult i64 %hdr_sz, %usize
  br i1 %ovf, label %oom, label %try_malloc
oom:
  %tmp_puts_oom = call i32 @puts(i8* getelementptr inbounds ([67 x i8], [67 x i8]* @.heap_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
try_malloc:
  %raw = call i8* @malloc(i64 %hdr_sz)
  %isnull = icmp eq i8* %raw, null
  br i1 %isnull, label %oom_malloc, label %ok_alloc
oom_malloc:
  %tmp_puts_oom2 = call i32 @puts(i8* getelementptr inbounds ([67 x i8], [67 x i8]* @.heap_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
ok_alloc:
  %hdr_ptr = bitcast i8* %raw to i64*
  %global_magic = load i64, i64* @.alloc_magic
  store i64 %global_magic, i64* %hdr_ptr
  %size_slot = getelementptr i8, i8* %raw, i64 8
  %size_slot_i64 = bitcast i8* %size_slot to i64*
  store i64 %usize, i64* %size_slot_i64
  %user_ptr = getelementptr i8, i8* %raw, i64 16
  %footer_ptr = getelementptr i8, i8* %user_ptr, i64 %usize
  %footer_ptr_i64 = bitcast i8* %footer_ptr to i64*
  store i64 %global_magic, i64* %footer_ptr_i64
  call void @bhumi_tbl_insert(i8* %user_ptr)
  ret i8* %user_ptr
}
define void @bhumi_free(i8* %userptr) nounwind {
entry:
  %is_null = icmp eq i8* %userptr, null
  br i1 %is_null, label %ret_void, label %check_tbl
check_tbl:
  %is_bhumi = call i1 @bhumi_tbl_contains(i8* %userptr)
  br i1 %is_bhumi, label %free_ok, label %free_fail
free_fail:
  %tmp_puts2 = call i32 @puts(i8* getelementptr inbounds ([67 x i8], [67 x i8]* @.heap_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
free_ok:
  call void @bhumi_tbl_remove(i8* %userptr)
  %raw_hdr = getelementptr i8, i8* %userptr, i64 -16
  %hdr_i64 = bitcast i8* %raw_hdr to i64*
  %size_slot = getelementptr i8, i8* %raw_hdr, i64 8
  %size_i64 = bitcast i8* %size_slot to i64*
  store i64 0, i64* %hdr_i64
  store i64 0, i64* %size_i64
  call void @free(i8* %raw_hdr)
  ret void
ret_void:
  ret void
}
@.vvolatile_msg = private unnamed_addr constant [69 x i8] c"[BhumiCompiler-RT-CHCK]: Volatile write attempted in vasync (panic).\\00"
define void @bhumi_c_free(i8* %userptr) nounwind {
entry:
  %is_null = icmp eq i8* %userptr, null
  br i1 %is_null, label %done, label %check_tbl
check_tbl:
  %is_bhumi = call i1 @bhumi_tbl_contains(i8* %userptr)
  br i1 %is_bhumi, label %is_bhumi_lbl, label %is_c_alloc
is_bhumi_lbl:
  call void @bhumi_free(i8* %userptr)
  br label %done
is_c_alloc:
  call void @free(i8* %userptr)
  br label %done
done:
  ret void
}
@.bhumi_ctbl_ptr = global i8** null
@.bhumi_ctbl_cap = global i64 0
@.bhumi_ctbl_cnt = global i64 0
define void @bhumi_ctbl_raw_insert(i8** %slots, i64 %cap, i8* %ptr) {
entry:
  %mask = sub i64 %cap, 1
  %pint = ptrtoint i8* %ptr to i64
  %hash = and i64 %pint, %mask
  br label %probe
probe:
  %slot = phi i64 [ %hash, %entry ], [ %next_wrap, %occupied ]
  %ep = getelementptr i8*, i8** %slots, i64 %slot
  %cur = load i8*, i8** %ep
  %is_empty = icmp eq i8* %cur, null
  br i1 %is_empty, label %do_store, label %occupied
occupied:
  %next = add i64 %slot, 1
  %next_wrap = and i64 %next, %mask
  br label %probe
do_store:
  store i8* %ptr, i8** %ep
  ret void
}
define void @bhumi_ctbl_grow(i64 %newcap) {
entry:
  %nbytes = mul i64 %newcap, 8
  %raw = call i8* @malloc(i64 %nbytes)
  %new_slots = bitcast i8* %raw to i8**
  br label %zero_loop
zero_loop:
  %zi = phi i64 [ 0, %entry ], [ %zi_next, %zero_loop ]
  %zep = getelementptr i8*, i8** %new_slots, i64 %zi
  store i8* null, i8** %zep
  %zi_next = add i64 %zi, 1
  %zi_done = icmp eq i64 %zi_next, %newcap
  br i1 %zi_done, label %rehash, label %zero_loop
rehash:
  %old_slots = load i8**, i8*** @.bhumi_ctbl_ptr
  %old_cap   = load i64, i64* @.bhumi_ctbl_cap
  %old_null  = icmp eq i8** %old_slots, null
  br i1 %old_null, label %rehash_done, label %rehash_loop
rehash_loop:
  %ri = phi i64 [ 0, %rehash ], [ %ri_next, %rehash_cont ]
  %rep = getelementptr i8*, i8** %old_slots, i64 %ri
  %rval = load i8*, i8** %rep
  %r_empty = icmp eq i8* %rval, null
  br i1 %r_empty, label %rehash_cont, label %do_reinsert
do_reinsert:
  call void @bhumi_ctbl_raw_insert(i8** %new_slots, i64 %newcap, i8* %rval)
  br label %rehash_cont
rehash_cont:
  %ri_next = add i64 %ri, 1
  %ri_done = icmp eq i64 %ri_next, %old_cap
  br i1 %ri_done, label %free_old, label %rehash_loop
free_old:
  %old_raw = bitcast i8** %old_slots to i8*
  call void @free(i8* %old_raw)
  br label %rehash_done
rehash_done:
  store i8** %new_slots, i8*** @.bhumi_ctbl_ptr
  store i64 %newcap,     i64*  @.bhumi_ctbl_cap
  ret void
}
define void @bhumi_ctbl_ensure_init() {
entry:
  %cap = load i64, i64* @.bhumi_ctbl_cap
  %need_init = icmp eq i64 %cap, 0
  br i1 %need_init, label %do_init, label %done
do_init:
  call void @bhumi_ctbl_grow(i64 64)
  br label %done
done:
  ret void
}
define void @bhumi_ctbl_insert(i8* %ptr) {
entry:
  %is_null = icmp eq i8* %ptr, null
  br i1 %is_null, label %done, label %do_insert
do_insert:
  call void @bhumi_ctbl_ensure_init()
  %cnt = load i64, i64* @.bhumi_ctbl_cnt
  %cap = load i64, i64* @.bhumi_ctbl_cap
  %cnt4 = mul i64 %cnt, 4
  %cap3 = mul i64 %cap, 3
  %overload = icmp uge i64 %cnt4, %cap3
  br i1 %overload, label %do_grow, label %insert_now
do_grow:
  %newcap = mul i64 %cap, 2
  call void @bhumi_ctbl_grow(i64 %newcap)
  br label %insert_now
insert_now:
  %slots = load i8**, i8*** @.bhumi_ctbl_ptr
  %cap2  = load i64, i64* @.bhumi_ctbl_cap
  call void @bhumi_ctbl_raw_insert(i8** %slots, i64 %cap2, i8* %ptr)
  %cnt2 = load i64, i64* @.bhumi_ctbl_cnt
  %cnt3 = add i64 %cnt2, 1
  store i64 %cnt3, i64* @.bhumi_ctbl_cnt
  br label %done
done:
  ret void
}
define i1 @bhumi_ctbl_contains(i8* %ptr) {
entry:
  %is_null = icmp eq i8* %ptr, null
  br i1 %is_null, label %ret_false, label %check_init
check_init:
  %cap = load i64, i64* @.bhumi_ctbl_cap
  %no_cap = icmp eq i64 %cap, 0
  br i1 %no_cap, label %ret_false, label %do_probe
do_probe:
  %mask = sub i64 %cap, 1
  %slots = load i8**, i8*** @.bhumi_ctbl_ptr
  %pint = ptrtoint i8* %ptr to i64
  %hash = and i64 %pint, %mask
  br label %probe
probe:
  %slot = phi i64 [ %hash, %do_probe ], [ %next_wrap, %cont ]
  %ep = getelementptr i8*, i8** %slots, i64 %slot
  %cur = load i8*, i8** %ep
  %is_empty = icmp eq i8* %cur, null
  br i1 %is_empty, label %ret_false, label %check_match
check_match:
  %match = icmp eq i8* %cur, %ptr
  br i1 %match, label %ret_true, label %cont
cont:
  %next = add i64 %slot, 1
  %next_wrap = and i64 %next, %mask
  br label %probe
ret_true:
  ret i1 1
ret_false:
  ret i1 0
}
define void @bhumi_ctbl_remove(i8* %ptr) {
entry:
  %cap = load i64, i64* @.bhumi_ctbl_cap
  %is_empty_tbl = icmp eq i64 %cap, 0
  br i1 %is_empty_tbl, label %not_found, label %do_remove
do_remove:
  %mask = sub i64 %cap, 1
  %slots = load i8**, i8*** @.bhumi_ctbl_ptr
  %pint = ptrtoint i8* %ptr to i64
  %hash = and i64 %pint, %mask
  br label %find_loop
find_loop:
  %fi = phi i64 [ %hash, %do_remove ], [ %fwrap, %find_cont ]
  %fep = getelementptr i8*, i8** %slots, i64 %fi
  %fcur = load i8*, i8** %fep
  %is_null = icmp eq i8* %fcur, null
  br i1 %is_null, label %not_found, label %check_match
check_match:
  %match = icmp eq i8* %fcur, %ptr
  br i1 %match, label %found, label %find_cont
find_cont:
  %fnext = add i64 %fi, 1
  %fwrap = and i64 %fnext, %mask
  br label %find_loop
found:
  store i8* null, i8** %fep
  %cnt_r = load i64, i64* @.bhumi_ctbl_cnt
  %cnt_r1 = sub i64 %cnt_r, 1
  store i64 %cnt_r1, i64* @.bhumi_ctbl_cnt
  ret void
not_found:
  ret void
}
define void @bhumi_safe_c_free(i8* %userptr) nounwind {
entry:
  %is_null = icmp eq i8* %userptr, null
  br i1 %is_null, label %done, label %check_bhumi
check_bhumi:
  %is_bhumi = call i1 @bhumi_tbl_contains(i8* %userptr)
  br i1 %is_bhumi, label %do_bhumi_free, label %check_ctbl
do_bhumi_free:
  call void @bhumi_free(i8* %userptr)
  br label %done
check_ctbl:
  %is_c = call i1 @bhumi_ctbl_contains(i8* %userptr)
  br i1 %is_c, label %do_c_free, label %done
do_c_free:
  call void @bhumi_ctbl_remove(i8* %userptr)
  call void @free(i8* %userptr)
  br label %done
done:
  ret void
}
define void @bhumi_ffi_free(i8* %userptr) nounwind {
entry:
  %is_null = icmp eq i8* %userptr, null
  br i1 %is_null, label %ffi_done, label %ffi_check_tbl
ffi_check_tbl:
  %is_bhumi = call i1 @bhumi_tbl_contains(i8* %userptr)
  br i1 %is_bhumi, label %ffi_bhumi_err, label %ffi_do_free
ffi_bhumi_err:
  %tmp_ffi = call i32 @puts(i8* getelementptr inbounds ([78 x i8], [78 x i8]* @.ffi_free_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
ffi_do_free:
  call void @free(i8* %userptr)
  br label %ffi_done
ffi_done:
  ret void
}
define void @bhumi_vvolatile_abort() {
entry:
  %tmp_puts_vv = call i32 @puts(i8* getelementptr inbounds ([69 x i8], [69 x i8]* @.vvolatile_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
}
define i64 @bhumi_alloc_size(i8* %userptr) nounwind willreturn {
entry:
  %is_null = icmp eq i8* %userptr, null
  br i1 %is_null, label %ret_zero, label %check_tbl
check_tbl:
  %is_bhumi = call i1 @bhumi_tbl_contains(i8* %userptr)
  br i1 %is_bhumi, label %read_hdr, label %ret_zero
read_hdr:
  %raw_hdr = getelementptr i8, i8* %userptr, i64 -16
  %size_slot = getelementptr i8, i8* %raw_hdr, i64 8
  %size_i64 = bitcast i8* %size_slot to i64*
  %sz = load i64, i64* %size_i64
  ret i64 %sz
ret_zero:
  ret i64 0
}
%bhumi_node = type { i8*, i8*, %bhumi_node* }
@bhumi_buckets = global [1024 x %bhumi_node*] zeroinitializer
define void @bhumi_register_async(i8* %resume, i8* %handle) {
entry:
  %szptr = getelementptr %bhumi_node, %bhumi_node* null, i32 1
  %sz = ptrtoint %bhumi_node* %szptr to i64
  %raw = call i8* @malloc(i64 %sz)
  %node = bitcast i8* %raw to %bhumi_node*
  %rptr = getelementptr %bhumi_node, %bhumi_node* %node, i32 0, i32 0
  %hptr = getelementptr %bhumi_node, %bhumi_node* %node, i32 0, i32 1
  %nptr = getelementptr %bhumi_node, %bhumi_node* %node, i32 0, i32 2
  store i8* %resume, i8** %rptr
  store i8* %handle, i8** %hptr
  %h_addr = ptrtoint i8* %handle to i64
  %bucket_idx64 = and i64 %h_addr, 1023
  %bucket_idx = trunc i64 %bucket_idx64 to i32
  %slot = getelementptr [1024 x %bhumi_node*], [1024 x %bhumi_node*]* @bhumi_buckets, i32 0, i32 %bucket_idx
  br label %insert_loop
insert_loop:
  %old_head = load atomic %bhumi_node*, %bhumi_node** %slot seq_cst, align 8
  store %bhumi_node* %old_head, %bhumi_node** %nptr
  %pair = cmpxchg %bhumi_node** %slot, %bhumi_node* %old_head, %bhumi_node* %node seq_cst seq_cst
  %succ = extractvalue { %bhumi_node*, i1 } %pair, 1
  br i1 %succ, label %insert_done, label %insert_loop
insert_done:
  ret void
}
define void @bhumi_remove_and_free_node(%bhumi_node* %target, %bhumi_node** %slot) {
entry:
  br label %try_head
try_head:
  %head = load atomic %bhumi_node*, %bhumi_node** %slot seq_cst, align 8
  %is_head = icmp eq %bhumi_node* %head, %target
  br i1 %is_head, label %remove_head, label %scan_pred
remove_head:
  %t_nptr = getelementptr %bhumi_node, %bhumi_node* %target, i32 0, i32 2
  %t_next = load atomic %bhumi_node*, %bhumi_node** %t_nptr seq_cst, align 8
  %pair = cmpxchg %bhumi_node** %slot, %bhumi_node* %target, %bhumi_node* %t_next seq_cst seq_cst
  %succ = extractvalue { %bhumi_node*, i1 } %pair, 1
  br i1 %succ, label %freed, label %try_head
scan_pred:
  %pred0 = load atomic %bhumi_node*, %bhumi_node** %slot seq_cst, align 8
  br label %scan_loop
scan_loop:
  %pred = phi %bhumi_node* [ %pred0, %scan_pred ], [ %pred_next, %advance_pred ]
  %pred_is_null = icmp eq %bhumi_node* %pred, null
  br i1 %pred_is_null, label %notfound, label %check_pred_next
check_pred_next:
  %pred_nptr = getelementptr %bhumi_node, %bhumi_node* %pred, i32 0, i32 2
  %pred_next = load atomic %bhumi_node*, %bhumi_node** %pred_nptr seq_cst, align 8
  %cmp_pred = icmp eq %bhumi_node* %pred_next, %target
  br i1 %cmp_pred, label %try_remove_mid, label %advance_pred
try_remove_mid:
  %target_nptr = getelementptr %bhumi_node, %bhumi_node* %target, i32 0, i32 2
  %target_next = load atomic %bhumi_node*, %bhumi_node** %target_nptr seq_cst, align 8
  %pair2 = cmpxchg %bhumi_node** %pred_nptr, %bhumi_node* %target, %bhumi_node* %target_next seq_cst seq_cst
  %succ2 = extractvalue { %bhumi_node*, i1 } %pair2, 1
  br i1 %succ2, label %freed, label %scan_pred
advance_pred:
  br label %scan_loop
notfound:
  ret void
freed:
  %rawptr = bitcast %bhumi_node* %target to i8*
  call void @free(i8* %rawptr)
  ret void
}
define void @bhumi_block_until_complete(i8* %handle) {
entry:
  %h_addr = ptrtoint i8* %handle to i64
  %bucket_idx64 = and i64 %h_addr, 1023
  %bucket_idx = trunc i64 %bucket_idx64 to i32
  %slot = getelementptr [1024 x %bhumi_node*], [1024 x %bhumi_node*]* @bhumi_buckets, i32 0, i32 %bucket_idx
  br label %scan
scan:
  %head = load atomic %bhumi_node*, %bhumi_node** %slot seq_cst, align 8
  br label %scan_loop
scan_loop:
  %cur = phi %bhumi_node* [ %head, %scan ], [ %next, %advance ]
  %isnull = icmp eq %bhumi_node* %cur, null
  br i1 %isnull, label %sleep, label %checknode
checknode:
  %hptr = getelementptr %bhumi_node, %bhumi_node* %cur, i32 0, i32 1
  %hval = load atomic i8*, i8** %hptr seq_cst, align 8
  %cmp = icmp eq i8* %hval, %handle
  br i1 %cmp, label %invoke, label %advance
invoke:
  %rptr = getelementptr %bhumi_node, %bhumi_node* %cur, i32 0, i32 0
  %rval = load atomic i8*, i8** %rptr seq_cst, align 8
  %resume_fn = bitcast i8* %rval to i1 (i8*)*
  %res = call i1 %resume_fn(i8* %handle)
  br i1 %res, label %remove_node, label %scan
remove_node:
  call void @bhumi_remove_and_free_node(%bhumi_node* %cur, %bhumi_node** %slot)
  br label %done
advance:
  %nptr2 = getelementptr %bhumi_node, %bhumi_node* %cur, i32 0, i32 2
  %next = load atomic %bhumi_node*, %bhumi_node** %nptr2 seq_cst, align 8
  br label %scan_loop
sleep:
  %tmp_usleep = call i32 @usleep(i32 1000)
  br label %scan
done:
  ret void
}
"""
    runtime_block_noop = """
@.alloc_magic = global i64 0
define void @bhumi_signal_handler(i32 %sig) {
entry:
  ret void
}
define void @bhumi_oob_abort() {
entry:
  ret void
}
define void @bhumi_null_abort() {
entry:
  ret void
}
define void @bhumi_init_runtime() {
entry:
  ret void
}
define void @bhumi_vvolatile_abort() {
entry:
  ret void
}
define i8* @bhumi_malloc(i64 %usize) {
entry:
  %p = call i8* @malloc(i64 %usize)
  ret i8* %p
}
define void @bhumi_free(i8* %userptr) {
entry:
  call void @free(i8* %userptr)
  ret void
}
define void @bhumi_c_free(i8* %userptr) {
entry:
  %is_null = icmp eq i8* %userptr, null
  br i1 %is_null, label %done, label %do_free
do_free:
  call void @free(i8* %userptr)
  br label %done
done:
  ret void
}
define void @bhumi_ffi_free(i8* %userptr) nounwind {
entry:
  %is_null = icmp eq i8* %userptr, null
  br i1 %is_null, label %done, label %do_free
do_free:
  call void @free(i8* %userptr)
  br label %done
done:
  ret void
}
define void @bhumi_tbl_insert(i8* %ptr) {
entry:
  ret void
}
define void @bhumi_tbl_remove(i8* %ptr) {
entry:
  ret void
}
define i1 @bhumi_tbl_contains(i8* %ptr) {
entry:
  ret i1 0
}
define void @bhumi_ctbl_insert(i8* %ptr) {
entry:
  ret void
}
define void @bhumi_ctbl_remove(i8* %ptr) {
entry:
  ret void
}
define i1 @bhumi_ctbl_contains(i8* %ptr) {
entry:
  ret i1 0
}
define void @bhumi_safe_c_free(i8* %userptr) nounwind {
entry:
  ret void
}
define i64 @bhumi_alloc_size(i8* %userptr) {
entry:
  ret i64 0
}
%bhumi_node = type { i8*, i8*, %bhumi_node* }
@bhumi_buckets = global [1024 x %bhumi_node*] zeroinitializer
define void @bhumi_register_async(i8* %resume, i8* %handle) {
entry:
  ret void
}
define void @bhumi_remove_and_free_node(%bhumi_node* %target, %bhumi_node** %slot) {
entry:
  ret void
}
define void @bhumi_block_until_complete(i8* %handle) {
entry:
  ret void
}
"""
    struct_llvm_defs: List[str] = []
    for sdef in prog.structs:
        field_tys: List[str] = []
        struct_field_map[sdef.name] = [(f.name, f.typ) for f in sdef.fields]
        for fld in sdef.fields:
            if fld.typ in type_map:
                field_tys.append(type_map[fld.typ])
            else:
                field_tys.append(f"%struct.{fld.typ}")
        llvm_line = f"%struct.{sdef.name} = type {{ {', '.join(field_tys)} }}"
        struct_llvm_defs.append(llvm_line)
    if struct_llvm_defs:
        lines.extend(struct_llvm_defs)
        lines.append("")
    for ename, variants in enum_variant_map.items():
        if any(payload is not None for (_, payload) in variants):
            llvm_line = f"%enum.{ename} = type {{ i32, [8 x i8] }}"
            lines.append(llvm_line)
    if any(any(p is not None for (_, p) in v) for v in enum_variant_map.values()):
        lines.append("")
    for g in prog.globals:
        is_array = False
        arr_count = None
        if "[" in g.typ and g.typ.endswith("]"):
            is_array = True
            base, arr_count = g.typ.split("[")
            arr_count = arr_count[:-1]
            base_llvm = llvm_ty_of(base)
            llvm_ty = f"[{arr_count} x {base_llvm}]"
        else:
            llvm_ty = type_map.get(g.typ, f"%struct.{g.typ}")
        initializer = "zeroinitializer"
        if isinstance(g.expr, IntLit):
            initializer = str(g.expr.value)
        elif isinstance(g.expr, FloatLit):
            initializer = f"{g.expr.value:.8e}"
        elif isinstance(g.expr, BoolLit):
            initializer = "1" if g.expr.value else "0"
        elif isinstance(g.expr, CharLit):
            initializer = str(ord(g.expr.value))
        elif isinstance(g.expr, StrLit):
            label = f"@.str{len(string_constants)}"
            esc = ""
            for ch in g.expr.value:
                if ch == "\n":
                    esc += r"\0A"
                elif ch == "\t":
                    esc += r"\09"
                elif ch == "\\":
                    esc += r"\\"
                elif ch == '"':
                    esc += r"\""
                else:
                    esc += ch
            length = len(g.expr.value) + 1
            string_constants.append(
                f'{label} = private unnamed_addr constant [{length} x i8] c"{esc}\\00"'
            )
            initializer = f"getelementptr inbounds ([{length} x i8], [{length} x i8]* {label}, i32 0, i32 0)"
            llvm_ty = "i8*"
        if getattr(g, "is_extern", False):
            lines.append(f"@{g.name} = external global {llvm_ty}")
            if is_array:
                lines.append(f"@{g.name}_len = external global i32")
                symbol_table.declare(f"{g.name}_len", "i32", f"@{g.name}_len")
            symbol_table.declare(g.name, llvm_ty, f"@{g.name}")
            continue
        lines.append(f"@{g.name} = global {llvm_ty} {initializer}")
        symbol_table.declare(g.name, llvm_ty, f"@{g.name}")
        if is_array:
            lines.append(f"@{g.name}_len = global i32 {arr_count}")
            symbol_table.declare(f"{g.name}_len", "i32", f"@{g.name}_len")
    existing_globals = set()
    existing_funcs = set()
    for line in lines:
        m_g = re.match(r"\s*@(\w+)\s*=", line)
        if m_g:
            existing_globals.add(m_g.group(1))
        m_f = re.match(r"\s*define\s+[^(]+\s+@(\w+)\s*\(", line)
        if m_f:
            existing_funcs.add(m_f.group(1))
    if not builtins_emitted and "bhumi_argc_global" not in existing_globals:
        lines.append("@bhumi_argc_global = global i64 0")
        lines.append("@bhumi_argv_global = global i8** null")
        lines.append("")
        lines.append("define i64 @bhumi_argc() {")
        lines.append("entry:")
        lines.append("  %t0 = load i64, i64* @bhumi_argc_global")
        lines.append("  ret i64 %t0")
        lines.append("}")
        lines.append("")
        string_constants.append(
            '@.str_null = private unnamed_addr constant [5 x i8] c"null\\00"'
        )
        lines.append("define i8* @bhumi_argv(i64 %idx) {")
        lines.append("entry:")
        lines.append("  %argvp = load i8**, i8*** @bhumi_argv_global")
        lines.append("  %isnull = icmp eq i8** %argvp, null")
        lines.append("  br i1 %isnull, label %null_case, label %check_bounds")
        lines.append("null_case:")
        lines.append(
            "  %src = getelementptr inbounds [5 x i8], [5 x i8]* @.str_null, i32 0, i32 0"
        )
        lines.append("  ret i8* %src")
        lines.append("check_bounds:")
        lines.append("  %argc = load i64, i64* @bhumi_argc_global")
        lines.append("  %neg = icmp slt i64 %idx, 0")
        lines.append("  %uge = icmp uge i64 %idx, %argc")
        lines.append("  %oob = or i1 %neg, %uge")
        lines.append("  br i1 %oob, label %null_case2, label %in_bounds")
        lines.append("null_case2:")
        lines.append(
            "  %src2 = getelementptr inbounds [5 x i8], [5 x i8]* @.str_null, i32 0, i32 0"
        )
        lines.append("  ret i8* %src2")
        lines.append("in_bounds:")
        lines.append("  %gep = getelementptr inbounds i8*, i8** %argvp, i64 %idx")
        lines.append("  %val = load i8*, i8** %gep")
        lines.append("  ret i8* %val")
        lines.append("}")
        lines.append("")
        builtins_emitted = True
    async_defs: List[str] = []
    for fn in prog.funcs:
        if getattr(fn, "is_async", False):
            async_defs.extend(gen_func(fn))
    if async_defs:
        lines.extend(async_defs)
        lines.append("")
    for fn in prog.funcs:
        if not getattr(fn, "is_async", False):
            lines += gen_func(fn)
    if string_constants:
        lines.extend(string_constants)
        lines.append("")
        string_constants.clear()
    if has_user_main and not no_main:
        lines.append("define i32 @main(i32 %argc, i8** %argv) {")
        lines.append("entry:")
        lines.append("  %argc64 = sext i32 %argc to i64")
        lines.append("  store i64 %argc64, i64* @bhumi_argc_global")
        lines.append("  store i8** %argv, i8*** @bhumi_argv_global")
        if not no_runtime:
            lines.append("  call void @bhumi_init_runtime()")
        user_ret = func_table.get("user_main", "i64")
        if user_ret == "void":
            lines.append("  call void @user_main()")
            lines.append("  ret i32 0")
        elif user_ret == "i64":
            lines.append("  %ret64 = call i64 @user_main()")
            lines.append("  %ret32 = trunc i64 %ret64 to i32")
            lines.append("  ret i32 %ret32")
        elif (
            isinstance(user_ret, str)
            and user_ret.startswith("i")
            and user_ret[1:].isdigit()
        ):
            bits = int(user_ret[1:])
            lines.append(f"  %rettmp = call {user_ret} @user_main()")
            if bits > 32:
                lines.append(f"  %ret32 = trunc {user_ret} %rettmp to i32")
            elif bits < 32:
                lines.append(f"  %ret32 = sext {user_ret} %rettmp to i32")
            else:
                lines.append(f"  %ret32 = add i32 %rettmp, 0")
            lines.append("  ret i32 %ret32")
        elif user_ret == "double":
            lines.append("  %retf = call double @user_main()")
            lines.append("  %ret32 = fptosi double %retf to i32")
            lines.append("  ret i32 %ret32")
        else:
            lines.append("  %ret64 = call i64 @user_main()")
            lines.append("  %ret32 = trunc i64 %ret64 to i32")
            lines.append("  ret i32 %ret32")
        lines.append("}")
    module_text = "\n".join(lines)
    def _replace_call_malloc(m):
        s = m.group(0)
        return s.replace("@malloc(", "@bhumi_malloc(")
    def _replace_call_free(m):
        s = m.group(0)
        return s.replace("@free(", "@bhumi_free(")
    module_text = re.sub(r"\bcall\b[^\n]*@malloc\(", _replace_call_malloc, module_text)
    module_text = re.sub(r"\bcall\b[^\n]*@free\(", _replace_call_free, module_text)
    if not no_runtime:
        module_text = module_text + "\n" + runtime_block
    else:
        module_text = module_text + "\n" + runtime_block_noop
    return module_text
def check_types(prog: Program):
    env = TypeEnv()
    crumb_map: Dict[str, Tuple[Optional[int], Optional[int], int, int]] = {}
    funcs = {f.name: f for f in prog.funcs}
    variant_map: Dict[str, List[Tuple[str, Optional[str]]]] = {}
    alias_creations: List[Tuple[str, str, Optional[int], Optional[int], int]] = []
    alias_targets: Dict[str, set] = {}
    alias_set: set = set()
    alias_creation_counter = 0
    nown_vars: set = set()
    crumb_order: Dict[str, int] = {}
    write_revoked: set = set()
    def _inc_read(name: str, node_desc: Optional[str] = None):
        if name not in crumb_map:
            return
        rmax, wmax, rc, wc = crumb_map[name]
        rc += 1
        crumb_map[name] = (rmax, wmax, rc, wc)
    def _inc_write(name: str, node_desc: Optional[str] = None):
        if name not in crumb_map:
            return
        rmax, wmax, rc, wc = crumb_map[name]
        wc += 1
        crumb_map[name] = (rmax, wmax, rc, wc)
    struct_defs: Dict[str, StructDef] = {s.name: s for s in prog.structs}
    enum_defs: Dict[str, EnumDef] = {e.name: e for e in prog.enums}
    global original_enum_defs
    try:
        original_enum_defs
    except NameError:
        original_enum_defs = {}
    for ename, edef in enum_defs.items():
        original_enum_defs[ename] = edef
    for sdef in prog.structs:
        struct_field_map[sdef.name] = [(fld.name, fld.typ) for fld in sdef.fields]
    for struct_name in struct_defs:
        env.declare(struct_name, struct_name)
    for ename, edef in enum_defs.items():
        variants = []
        has_payload = False
        for v in edef.variants:
            variants.append((v.name, v.typ))
            if getattr(v, "typ", None) is not None:
                has_payload = True
        enum_variant_map[ename] = variants
        env.declare(ename, ename)
        if not has_payload:
            type_map[ename] = type_map.get("int", "i64")
    for ename, edef in enum_defs.items():
        for v in edef.variants:
            variant_map.setdefault(v.name, []).append((ename, v.typ))
    def eval_const_int(e):
        if e is None:
            return None
        if isinstance(e, IntLit):
            try:
                return int(e.value)
            except Exception:
                return None
        if isinstance(e, UnaryOp):
            if e.op in ("-", "+"):
                v = eval_const_int(e.expr)
                if v is None:
                    return None
                return -v if e.op == "-" else v
            return None
        if isinstance(e, BinOp):
            left = eval_const_int(e.left)
            right = eval_const_int(e.right)
            if left is None or right is None:
                return None
            try:
                if e.op == "+":
                    return left + right
                if e.op == "-":
                    return left - right
                if e.op == "*":
                    return left * right
                if e.op == "/":
                    if right == 0:
                        return None
                    return left // right
                if e.op == "%":
                    if right == 0:
                        return None
                    return left % right
                if e.op == "<<":
                    return left << right
                if e.op == ">>":
                    return left >> right
            except Exception:
                return None
        return None
    def check_expr(expr: Expr, expected: Optional[str] = None) -> str:
        if isinstance(expr, CallerType):
            if expected is not None:
                return expected
            return "#"
        if isinstance(expr, AwaitExpr):
            return check_expr(expr.expr)
        if isinstance(expr, UnaryOp):
            inner_t = check_expr(expr.expr)
            if expr.op in {"-", "+"}:
                if inner_t == "float" or inner_t.startswith("int") or inner_t == "int":
                    return inner_t
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Unary '{expr.op}' requires integer or float operand, got '{inner_t}'",
                )
            if expr.op == "!":
                if inner_t != "bool":
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Unary '!' requires bool operand, got '{inner_t}'",
                    )
                return "bool"
            if expr.op == "~":
                if inner_t.startswith("int") or inner_t == "int":
                    return inner_t
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Unary '~' requires integer operand, got '{inner_t}'",
                )
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Unsupported unary operator: {expr.op}",
            )
        if isinstance(expr, IntLit):
            return "int"
        if isinstance(expr, FloatLit):
            return "float32" if getattr(expr, "bits", 64) == 32 else "float"
        if isinstance(expr, BoolLit):
            return "bool"
        if isinstance(expr, CharLit):
            return "char"
        if isinstance(expr, StrLit):
            return "string"
        if isinstance(expr, NullLit):
            return "null"
        if isinstance(expr, Cast):
            inner_type = check_expr(expr.expr)
            if (
                expr.typ.startswith("int") or expr.typ.startswith("uint")
            ) and inner_type == "int":
                return expr.typ
            if inner_type in {"null", "void*"} and (
                expr.typ.endswith("*") or expr.typ == "string"
            ):
                return expr.typ
            if inner_type == "float" and expr.typ == "float32":
                return "float32"
            if inner_type == "float32" and expr.typ == "float":
                return "float"
            common = unify_types(inner_type, expr.typ)
            if inner_type != expr.typ and (not common or common != expr.typ):
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Cannot cast {inner_type} to {expr.typ}",
                )
            return expr.typ
        if isinstance(expr, AddressOf):
            if isinstance(expr.expr, Var):
                typ = env.lookup(expr.expr.name)
                if not typ:
                    bhumi_report_error(
                        getattr(expr.expr, "lineno", None),
                        getattr(expr.expr, "col", None),
                        f"Use of undeclared variable '{expr.expr.name}'",
                    )
                return typ + "*"
            inner_t = check_expr(expr.expr)
            return inner_t + "*"
        if isinstance(expr, UnaryDeref):
            ptr_t = check_expr(expr.ptr)
            if not ptr_t.endswith("*"):
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Cannot dereference non-pointer type '{ptr_t}'",
                )
            return ptr_t[:-1]
        if isinstance(expr, Var):
            typ = env.lookup(expr.name)
            if not typ:
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Use of undeclared variable '{expr.name}'",
                )
            if typ == "undefined":
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Use of variable '{expr.name}' after deref (use-after-free)",
                )
            _inc_read(expr.name, node_desc=f"Var@{getattr(expr, 'lineno', '?')}")
            return typ
        if isinstance(expr, TypeofExpr):
            check_expr(expr.expr)
            return "string"
        if isinstance(expr, Ternary):
            cond_type = check_expr(expr.cond)
            if cond_type != "bool":
                bhumi_report_error(
                    getattr(expr.cond, "lineno", None),
                    getattr(expr.cond, "col", None),
                    "Ternary condition must be bool",
                )
            then_t = check_expr(expr.then_expr)
            else_t = check_expr(expr.else_expr)
            if then_t != else_t:
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Ternary branches must match: {then_t} vs {else_t}",
                )
            return then_t
        if isinstance(expr, BinOp):
            left = check_expr(expr.left)
            right = check_expr(expr.right)
            if expr.op in {"/", "%"}:
                cval = eval_const_int(expr.right)
                if cval is not None and cval == 0:
                    bhumi_report_error(
                        getattr(expr.right, "lineno", None),
                        getattr(expr.right, "col", None),
                        f"[BhumiCompiler-ERR]: division or modulo by constant 0 ('{expr.op}')",
                    )
            if expr.op == "+" and left == "string" and right == "string":
                return "string"
            if expr.op in {"&&", "||"}:
                if left != "bool" or right != "bool":
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Logical '{expr.op}' requires both operands to be bool, got {left} and {right}",
                    )
                return "bool"
            if expr.op == "%":
                if left == "int" and right == "int":
                    return "int"
                elif left == "float" and right == "float":
                    return "float"
                else:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Modulo '%' requires int or float, got {left} and {right}",
                    )
            if left.endswith("*") and not right.endswith("*") and expr.op in {"+", "-"}:
                return left
            if right.endswith("*") and not left.endswith("*") and expr.op == "+":
                return right
            if left.endswith("*") and right.endswith("*") and left == right and expr.op == "-":
                return "int"
            common = unify_types(left, right)
            if not common:
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Type mismatch: {left} {expr.op} {right}",
                )
            if expr.op in {"==", "!=", "<", ">", "<=", ">="}:
                return "bool"
            return common
        if isinstance(expr, Call):
            qualified_enum = None
            variant_name = expr.name
            if "->" in expr.name:
                qualified_enum, variant_name = expr.name.split("->", 1)
            _arg_expected: List[Optional[str]] = [None] * len(expr.args)
            if "->" in expr.name and expected is not None:
                _gm_ae = re.fullmatch(r"[A-Za-z_]\w*<(.+)>", expected.rstrip("*"))
                if _gm_ae:
                    _inner_types = [p.strip() for p in _gm_ae.group(1).split(",")]
                    for _i in range(min(len(_arg_expected), len(_inner_types))):
                        _arg_expected[_i] = _inner_types[_i]
            else:
                _fn_lookup = next(
                    (f for f in prog.funcs if f.name == expr.name), None
                )
                if _fn_lookup is not None and getattr(_fn_lookup, "params", None):
                    for _i, (_ptype, _) in enumerate(_fn_lookup.params):
                        if _i < len(_arg_expected):
                            _arg_expected[_i] = _ptype if _ptype != "#" else None
            arg_types = [
                check_expr(a, expected=_arg_expected[i] if i < len(_arg_expected) else None)
                for i, a in enumerate(expr.args)
            ]
            if expr.name in ("free", "bhumi_free"):
                if len(expr.args) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"'free' expects one argument",
                    )
                a0 = expr.args[0]
                if isinstance(a0, Var):
                    vname = a0.name
                    v_typ = env.lookup(vname)
                    if v_typ is None:
                        bhumi_report_error(
                            getattr(a0, "lineno", None),
                            getattr(a0, "col", None),
                            f"free() of undeclared variable '{vname}'",
                        )
                    global_decl = next(
                        (g for g in prog.globals if g.name == vname), None
                    )
                    is_extern_global = bool(
                        global_decl and getattr(global_decl, "is_extern", False)
                    )
                    if not (
                        v_typ.endswith("*")
                        or v_typ == "void*"
                        or v_typ == "string"
                        or is_extern_global
                    ):
                        bhumi_report_error(
                            getattr(a0, "lineno", None),
                            getattr(a0, "col", None),
                            f"free() argument must be a pointer or string (or extern global). got '{v_typ}', this looks like a stack/local variable",
                        )
                    if v_typ == "undefined":
                        bhumi_report_error(
                            getattr(a0, "lineno", None),
                            getattr(a0, "col", None),
                            f"[BhumiCompiler-ERR]: double free detected on variable '{vname}'",
                        )
                    if not is_extern_global and vname not in nown_vars:
                        bhumi_report_error(
                            getattr(a0, "lineno", None),
                            getattr(a0, "col", None),
                            f"'free({vname})' is not allowed: \n'{vname}' does not trace back to a 'nown' (non owning) function.\n"
                            f"Only values returned by 'nown' functions may be manually released with free() or forget().",
                        )
                    env.declare(vname, "undefined")
                return "void"
            if expr.name == "!" and len(arg_types) == 1:
                if arg_types[0] != "bool":
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Unary '!' requires bool operand, got '{arg_types[0]}'",
                    )
                return "bool"
            if expr.name == "~" and len(arg_types) == 1:
                if arg_types[0].startswith("int") or arg_types[0] == "int":
                    return arg_types[0]
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Unary '~' requires integer operand, got '{arg_types[0]}'",
                )
            if expr.name == "not" and len(arg_types) == 1:
                if arg_types[0] != "bool":
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"'not' requires bool operand, got '{arg_types[0]}'",
                    )
                return "bool"
            if expr.name == "exit":
                if len(arg_types) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "exit() takes exactly one int argument",
                    )
                arg_ty = arg_types[0]
                if not arg_ty.startswith("int"):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "exit() expects an integer argument",
                    )
                return "void"
            if expr.name == "malloc":
                if len(arg_types) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "malloc() takes exactly one int argument",
                    )
                arg_ty = arg_types[0]
                if not arg_ty.startswith("int"):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "malloc() expects an integer argument",
                    )
                return "int*"
            if expr.name == "free":
                if len(arg_types) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "free() takes exactly one pointer (or string) argument",
                    )
                arg_ty = arg_types[0]
                if not (
                    arg_ty.endswith("*") or arg_ty == "void*" or arg_ty == "string"
                ):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "free() expects a pointer or string argument",
                    )
                return "void"
            if expr.name == "puts":
                if len(arg_types) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "puts() takes exactly one string argument",
                    )
                arg_ty = arg_types[0]
                if arg_ty != "string" and not arg_ty.endswith("*"):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "puts() expects a string (or pointer) argument",
                    )
                return "void"
            if expr.name == "strlen":
                if len(arg_types) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "strlen() takes exactly one string argument",
                    )
                arg_ty = arg_types[0]
                if arg_ty != "string" and not arg_ty.endswith("*"):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "strlen() expects a string (or pointer) argument",
                    )
                return "int"
            if expr.name == "bhumi_argc":
                if len(arg_types) != 0:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "bhumi_argc() takes no arguments",
                    )
                return "int"
            if expr.name == "bhumi_argv":
                if len(arg_types) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "bhumi_argv() takes exactly one int argument",
                    )
                if not arg_types[0].startswith("int"):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "bhumi_argv() expects an int index",
                    )
                return "string"
            if expr.name == "time":
                if len(arg_types) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "time() takes exactly one pointer argument (or null)",
                    )
                a = arg_types[0]
                if a != "int" and not a.endswith("*"):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "time() expects a pointer or null",
                    )
                return "int"
            if expr.name == "srand":
                if len(arg_types) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "srand() takes exactly one int argument",
                    )
                if not arg_types[0].startswith("int"):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "srand() expects an integer",
                    )
                return "void"
            if expr.name == "rand":
                if len(arg_types) != 0:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "rand() takes no arguments",
                    )
                return "int"
            if expr.name == "usleep":
                if len(arg_types) != 1:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "usleep() takes exactly one int argument",
                    )
                if not arg_types[0].startswith("int"):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "usleep() expects an integer argument",
                    )
                return "int"
            candidates = variant_map.get(variant_name, []).copy()
            gm = globals().get("variant_map_global", {})
            candidates.extend(gm.get(variant_name, []))
            if candidates:
                chosen = None
                if qualified_enum is not None:
                    candidates = [
                        (ename, payload)
                        for (ename, payload) in candidates
                        if ename == qualified_enum
                        or ename.startswith(qualified_enum + "__mono__")
                    ]
                    if not candidates:
                        _all_variants = variant_map.get(variant_name, [])
                        _all_variants_g = list(gm.get(variant_name, []))
                        _all_enums = {
                            (e.split("__mono__")[0] if "__mono__" in e else e)
                            for e, _ in (_all_variants + _all_variants_g)
                        }
                        def _pretty_enum_name_err(raw: str) -> str:
                            base = raw.partition("__mono__")[0] if "__mono__" in raw else raw
                            orig = globals().get("original_enum_defs", {}).get(base)
                            if orig is None:
                                return base
                            tps = getattr(orig, "type_params", [])
                            return base + "<" + ", ".join(tps) + ">" if tps else base
                        _others = ", ".join(
                            sorted({_pretty_enum_name_err(e) for e in _all_enums if e != qualified_enum})
                        )
                        _exists_msg = f" '{variant_name}' exists in: {_others}" if _others else ""
                        bhumi_report_error(
                            getattr(expr, "lineno", None),
                            getattr(expr, "col", None),
                            f"Enum '{qualified_enum}' has no variant '{variant_name}'.{_exists_msg}",
                        )
                mono_bases = {
                    ename.split("__mono__")[0]
                    for (ename, _) in candidates
                    if "__mono__" in ename
                }
                if mono_bases:
                    candidates = [
                        (ename, payload)
                        for (ename, payload) in candidates
                        if "__mono__" in ename or ename not in mono_bases
                    ]
                _orig_defs = globals().get("original_enum_defs", {})
                concrete_candidates = [
                    (ename, payload) for (ename, payload) in candidates
                    if not (
                        payload is not None
                        and payload in getattr(
                            _orig_defs.get(ename.partition("__mono__")[0] if "__mono__" in ename else ename),
                            "type_params", []
                        )
                        and "__mono__" not in ename
                    )
                ]
                if concrete_candidates:
                    candidates = concrete_candidates
                if len(candidates) > 1 and expected is not None:
                    exp_bare = expected.rstrip("*")
                    preferred = [
                        (ename, payload)
                        for (ename, payload) in candidates
                        if ename == exp_bare or exp_bare.startswith(ename)
                    ]
                    if len(preferred) == 1:
                        candidates = preferred
                if len(candidates) > 1 and arg_types:
                    payload_matched = [
                        (ename, payload)
                        for (ename, payload) in candidates
                        if payload is not None
                        and (
                            unify_types(payload, arg_types[0]) is not None
                            or unify_types(arg_types[0], payload) is not None
                        )
                    ]
                    if len(payload_matched) == 1:
                        candidates = payload_matched
                if len(candidates) > 1:
                    def _pretty_enum_name(raw: str) -> str:
                        base = raw.partition("__mono__")[0] if "__mono__" in raw else raw
                        orig = globals().get("original_enum_defs", {}).get(base)
                        if orig is None:
                            return base
                        type_params = getattr(orig, "type_params", [])
                        return base + "<" + ", ".join(type_params) + ">" if type_params else base
                    msg_lines = []
                    msg_lines.append(f"ambiguous enum variant '{variant_name}'")
                    msg_lines.append("")
                    msg_lines.append(f"The name `{variant_name}` matches multiple enum variants in scope:")
                    seen_bases: set = set()
                    for ename, payload in candidates:
                        pretty = _pretty_enum_name(ename)
                        base_key = ename.partition("__mono__")[0] if "__mono__" in ename else ename
                        if base_key in seen_bases:
                            continue
                        seen_bases.add(base_key)
                        payload_desc = "no payload" if payload is None else f"payload={payload}"
                        msg_lines.append(f"  - {pretty}->{variant_name}  ({payload_desc})")
                    msg_lines.append("")
                    msg_lines.append("To fix, qualify the variant with its enum name:")
                    best = _pretty_enum_name(candidates[0][0])
                    msg_lines.append(f"  - To choose a variant:  {best}->{variant_name}(...)")
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        "\n".join(msg_lines),
                    )
                chosen = candidates[0]
                enum_name, payload = chosen
                _mono_base = enum_name.split("__mono__")[0] if "__mono__" in enum_name else enum_name
                _orig_edef = globals().get("original_enum_defs", {}).get(_mono_base)
                _type_params = getattr(_orig_edef, "type_params", []) if _orig_edef else []
                if (
                    "__mono__" in enum_name
                    and payload is not None
                    and arg_types
                    and unify_types(payload, arg_types[0]) is None
                    and unify_types(arg_types[0], payload) is None
                    and _orig_edef is not None
                ):
                    _base_variant_payload = next(
                        (v.typ for v in _orig_edef.variants if v.name == variant_name), None
                    )
                    if _base_variant_payload in _type_params:
                        _actuals_retry = None
                        if expected is not None:
                            _exp_bare = expected.rstrip("*")
                            _gm_retry = re.fullmatch(re.escape(_mono_base) + r"<(.+)>", _exp_bare)
                            if _gm_retry:
                                _parts = [p.strip() for p in _gm_retry.group(1).split(",")]
                                if len(_parts) == len(_type_params):
                                    _actuals_retry = _parts
                            if _actuals_retry is None:
                                _mono_prefix = _mono_base + "__mono__"
                                if _exp_bare.startswith(_mono_prefix) and _exp_bare in enum_variant_map:
                                    _cvlist = enum_variant_map[_exp_bare]
                                    _res = [None] * len(_type_params)
                                    for _ov, (_, _cp) in zip(_orig_edef.variants, _cvlist):
                                        if _ov.typ is not None and _cp is not None:
                                            for _i, _tp in enumerate(_type_params):
                                                if _ov.typ == _tp:
                                                    _res[_i] = _cp
                                    if all(r is not None for r in _res):
                                        _actuals_retry = _res
                        if _actuals_retry is None:
                            _param_idx = _type_params.index(_base_variant_payload)
                            _actuals_retry = list(_type_params)
                            _actuals_retry[_param_idx] = arg_types[0]
                        if _actuals_retry is not None and all(
                            t not in _type_params for t in _actuals_retry
                        ):
                            _retry_mono = ensure_monomorph_for_enum(_mono_base, _actuals_retry)
                            _retry_variants = enum_variant_map.get(_retry_mono, [])
                            _retry_payload = next(
                                (p for n, p in _retry_variants if n == variant_name), None
                            )
                            enum_name = _retry_mono
                            payload = _retry_payload
                            _type_params = []
                if payload is None:
                    if len(arg_types) != 0:
                        bhumi_report_error(
                            getattr(expr, "lineno", None),
                            getattr(expr, "col", None),
                            f"Enum variant '{expr.name}' takes no arguments",
                        )
                    return enum_name
                else:
                    if len(arg_types) != 1:
                        bhumi_report_error(
                            getattr(expr, "lineno", None),
                            getattr(expr, "col", None),
                            f"Enum variant '{expr.name}' requires one payload of type '{payload}'",
                        )
                    if _type_params and payload in _type_params:
                        actual_arg_t = arg_types[0]
                        if len(_type_params) == 1:
                            mono_name = ensure_monomorph_for_enum(enum_name, [actual_arg_t])
                            return mono_name
                        else:
                            actuals_ce = None
                            if expected is not None:
                                exp_bare = expected.rstrip("*")
                                gm_ce = re.fullmatch(re.escape(enum_name) + r"<(.+)>", exp_bare)
                                if gm_ce:
                                    parts_ce = [p.strip() for p in gm_ce.group(1).split(",")]
                                    if len(parts_ce) == len(_type_params):
                                        actuals_ce = parts_ce
                                if actuals_ce is None:
                                    mono_prefix_ce = enum_name + "__mono__"
                                    if exp_bare.startswith(mono_prefix_ce) and exp_bare in enum_variant_map:
                                        concrete_vlist = enum_variant_map[exp_bare]
                                        orig_vlist = _orig_edef.variants
                                        res_ce: List[Optional[str]] = [None] * len(_type_params)
                                        for orig_v, conc_pair in zip(orig_vlist, concrete_vlist):
                                            conc_p = conc_pair[1]
                                            if orig_v.typ is not None and conc_p is not None:
                                                for i, tp in enumerate(_type_params):
                                                    if orig_v.typ == tp:
                                                        res_ce[i] = conc_p
                                        if all(r is not None for r in res_ce):
                                            actuals_ce = res_ce
                            if actuals_ce is not None:
                                mono_name = ensure_monomorph_for_enum(enum_name, actuals_ce)
                                return mono_name
                            return enum_name
                    if (
                        unify_types(payload, arg_types[0]) is None
                        and unify_types(arg_types[0], payload) is None
                    ):
                        bhumi_report_error(
                            getattr(expr, "lineno", None),
                            getattr(expr, "col", None),
                            f"Enum variant '{expr.name}' payload type mismatch: expected {payload}, got {arg_types[0]}",
                        )
                    return enum_name
            fn = funcs.get(expr.name)
            if fn is None:
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Call to undeclared function '{expr.name}'",
                )
            type_subst: Dict[str, str] = {}
            if getattr(fn, "type_params", None):
                for (param_type, _), actual in zip(fn.params, arg_types):
                    for tp in fn.type_params:
                        if param_type == tp:
                            type_subst[tp] = actual
                        elif param_type.startswith(tp) and param_type[len(tp) :] in (
                            "*",
                            "[]",
                        ):
                            type_subst[tp] = actual
                if fn.type_params and not any(
                    tp in type_subst for tp in fn.type_params
                ):
                    if arg_types:
                        type_subst[fn.type_params[0]] = arg_types[0]
            if fn.is_extern and getattr(fn, "is_variadic", False):
                if len(arg_types) < len(fn.params):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Too few arguments in call to '{expr.name}'; expected at least {len(fn.params)}",
                    )
            else:
                if len(arg_types) != len(fn.params):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Arity mismatch in call to '{expr.name}'",
                    )
            for actual_type, (expected_type, _) in zip(arg_types, fn.params):
                expected_concrete = _subst_type(expected_type, type_subst)
                if isinstance(actual_type, str) and re.fullmatch(
                    r"[A-Z]\w*", actual_type
                ):
                    if expected_concrete is not None and not re.fullmatch(
                        r"[A-Z]\w*", expected_concrete
                    ):
                        env.declare(actual_type, expected_concrete)
                        actual_type = expected_concrete
                common = unify_int_types(actual_type, expected_concrete)
                if (
                    expected_concrete != "void"
                    and actual_type != expected_concrete
                    and (not common or common != expected_concrete)
                ):
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Argument type mismatch in call to '{expr.name}': expected {expected_concrete}, got {actual_type}",
                    )
            ret = fn.ret_type
            if getattr(fn, "type_params", None) and isinstance(ret, str):
                ret = _subst_type(ret, type_subst)
            if ret == "#":
                if expected is not None:
                    return expected
                else:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Call to '{expr.name}' returns '#', but call context does not provide required expected type",
                    )
            return ret
        if isinstance(expr, Index):
            if not isinstance(expr.array, Var):
                bhumi_report_error(
                    getattr(expr.array, "lineno", None),
                    getattr(expr.array, "col", None),
                    f"Only direct variable array indexing is supported, got: {expr.array}",
                )
            arr_name = expr.array.name
            _inc_read(arr_name, node_desc=f"Index@{getattr(expr, 'lineno', '?')}")
            var_typ = env.lookup(arr_name)
            if not var_typ:
                bhumi_report_error(
                    getattr(expr.array, "lineno", None),
                    getattr(expr.array, "col", None),
                    f"Indexing undeclared variable '{arr_name}'",
                )
            if "[" not in var_typ or not var_typ.endswith("]"):
                bhumi_report_error(
                    getattr(expr.array, "lineno", None),
                    getattr(expr.array, "col", None),
                    f"Attempting to index non-array type '{var_typ}'",
                )
            base_type = var_typ.split("[", 1)[0]
            if "<" in base_type:
                base_type = base_type.split("<", 1)[0]
            idx_type = check_expr(expr.index)
            if idx_type != "int":
                bhumi_report_error(
                    getattr(expr.index, "lineno", None),
                    getattr(expr.index, "col", None),
                    f"Array index must be 'int', got '{idx_type}'",
                )
            try:
                inside = var_typ.split("[", 1)[1][:-1]
                array_len = int(inside) if inside.isdigit() else None
            except Exception:
                array_len = None
            if array_len is not None:
                cval = eval_const_int(expr.index)
                if cval is not None:
                    if cval < 0 or cval >= array_len:
                        bhumi_report_error(
                            getattr(expr.index, "lineno", None),
                            getattr(expr.index, "col", None),
                            f"Array index constant {cval} out of bounds for array of length {array_len}",
                        )
            return base_type
        if isinstance(expr, FieldAccess):
            base_type = check_expr(expr.base).rstrip("*")
            if "<" in base_type:
                base_type = base_type.split("<", 1)[0]
            if base_type in struct_defs:
                fields = struct_field_map[base_type]
                for (fname, ftyp) in fields:
                    if fname == expr.field:
                        return ftyp
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Struct '{base_type}' has no field '{expr.field}'",
                )
            if base_type in enum_defs:
                vars = enum_variant_map[base_type]
                for (vname, vtyp) in vars:
                    if vname == expr.field:
                        if vtyp is not None:
                            bhumi_report_error(
                                getattr(expr, "lineno", None),
                                getattr(expr, "col", None),
                                f"Enum variant '{expr.field}' carries payload; use constructor call",
                            )
                        return base_type
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Enum '{base_type}' has no variant '{expr.field}'",
                )
            bhumi_report_error(
                getattr(expr, "lineno", None),
                getattr(expr, "col", None),
                f"Attempting field access on non-struct/enum type '{base_type}'",
            )
        if isinstance(expr, StructInit):
            if expr.name not in struct_defs:
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Unknown struct type '{expr.name}' in initializer",
                )
            expected_fields = struct_field_map[expr.name][:]
            seen_fields = set()
            for (fname, fexpr) in expr.fields:
                match_list = [ft for (fn, ft) in expected_fields if fn == fname]
                if not match_list:
                    bhumi_report_error(
                        getattr(fexpr, "lineno", None),
                        getattr(fexpr, "col", None),
                        f"Struct '{expr.name}' has no field '{fname}'",
                    )
                declared_type = match_list[0]
                actual_type = check_expr(fexpr, expected=declared_type)
                if actual_type != declared_type:
                    bhumi_report_error(
                        getattr(fexpr, "lineno", None),
                        getattr(fexpr, "col", None),
                        f"Struct '{expr.name}' field '{fname}': expected '{declared_type}', got '{actual_type}'",
                    )
                seen_fields.add(fname)
            all_field_names = {fn for (fn, _) in expected_fields}
            if seen_fields != all_field_names:
                missing = all_field_names - seen_fields
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    f"Struct '{expr.name}' initializer missing fields {missing}",
                )
            return expr.name + "*"
        if isinstance(expr, ArrayInit):
            if len(expr.elements) == 0:
                bhumi_report_error(
                    getattr(expr, "lineno", None),
                    getattr(expr, "col", None),
                    "Cannot infer type for empty array literal; give it a type",
                )
            first_t = infer_type(expr.elements[0])
            for el in expr.elements[1:]:
                el_t = infer_type(el)
                if unify_types(first_t, el_t) is None:
                    bhumi_report_error(
                        getattr(expr, "lineno", None),
                        getattr(expr, "col", None),
                        f"Array literal element types do not match: {first_t} vs {el_t}",
                    )
            return f"{first_t}[{len(expr.elements)}]"
        bhumi_report_error(
            getattr(expr, "lineno", None),
            getattr(expr, "col", None),
            f"Unsupported expression: {expr}",
        )
    def check_stmt(stmt: Stmt, expected_ret: str, func: Optional[Func] = None):
        nonlocal alias_creation_counter
        nonlocal nown_vars
        if isinstance(stmt, VarDecl):
            if env.lookup(stmt.name):
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Variable '{stmt.name}' already declared",
                )
            raw_typ = stmt.typ
            base_type = raw_typ.rstrip("*")
            if "[" in base_type and base_type.endswith("]"):
                base_type = base_type.split("[", 1)[0]
            if "<" in base_type:
                base_type = base_type.split("<", 1)[0]
            if (
                    base_type not in type_map
                    and base_type not in struct_defs
                    and base_type not in enum_defs
            ):
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Unknown type '{raw_typ}'",
                )
            env.declare(stmt.name, raw_typ)
            if stmt.expr is not None:
                _is_nown_init = False
                if isinstance(stmt.expr, Call):
                    _callee = _func_name_map.get(stmt.expr.name)
                    if _callee is not None and getattr(_callee, "is_nown", False):
                        _is_nown_init = True
                elif isinstance(stmt.expr, Var) and stmt.expr.name in nown_vars:
                    _is_nown_init = True
                if _is_nown_init:
                    nown_vars.add(stmt.name)
            if stmt.expr:
                expr_type = check_expr(stmt.expr, expected=raw_typ)
                _inc_write(
                    stmt.name, node_desc=f"VarInit@{getattr(stmt, 'lineno', '?')}"
                )
                if isinstance(stmt.expr, AddressOf) and (
                    raw_typ.endswith("*") or raw_typ == "string"
                ):
                    inner = stmt.expr.expr
                    if isinstance(inner, Var):
                        original_name = inner.name
                        alias_name = stmt.name
                        alias_creations.append(
                            (
                                alias_name,
                                original_name,
                                getattr(stmt, "lineno", None),
                                getattr(stmt, "col", None),
                                alias_creation_counter,
                            )
                        )
                        alias_creation_counter += 1
                        alias_targets.setdefault(original_name, set()).add(alias_name)
                        alias_set.add(alias_name)
                if expr_type == "float" and raw_typ == "float32":
                    stmt.expr = Cast("float32", stmt.expr)
                    expr_type = "float32"
                elif expr_type == "float32" and raw_typ == "float":
                    stmt.expr = Cast("float", stmt.expr)
                    expr_type = "float"
                common = unify_types(expr_type, raw_typ)
                def _generic_matches_mono(generic_typ: str, mono_typ: str) -> bool:
                    m = re.fullmatch(r"([A-Za-z_]\w*)<(.+)>", generic_typ)
                    if m and mono_typ.startswith(m.group(1) + "__mono__"):
                        return True
                    return False
                if expr_type != raw_typ and (not common or common != raw_typ):
                    if not (_generic_matches_mono(raw_typ, expr_type) or _generic_matches_mono(expr_type, raw_typ)):
                        bhumi_report_error(
                            getattr(stmt, "lineno", None),
                            getattr(stmt, "col", None),
                            f"Type mismatch in variable init '{stmt.name}': expected {raw_typ}, got {expr_type}",
                        )
            return
        if isinstance(stmt, ContinueStmt) or isinstance(stmt, BreakStmt):
            return
        if isinstance(stmt, Assign):
            if isinstance(stmt.name, UnaryDeref):
                def _find_var_in_expr(node, _depth=0, _max_depth=10):
                    if node is None or _depth > _max_depth:
                        return None
                    if isinstance(node, Var):
                        return node.name
                    maybe_name = getattr(node, "name", None)
                    if isinstance(maybe_name, str):
                        return maybe_name
                    child_attrs = (
                        "expr",
                        "value",
                        "arg",
                        "target",
                        "ptr",
                        "base",
                        "operand",
                        "inner",
                        "v",
                        "var",
                        "lhs",
                        "rhs",
                        "obj",
                    )
                    for attr in child_attrs:
                        if hasattr(node, attr):
                            child = getattr(node, attr)
                            if isinstance(child, (list, tuple)) and child:
                                for c in child:
                                    vn = _find_var_in_expr(c, _depth + 1, _max_depth)
                                    if vn:
                                        return vn
                                continue
                            vn = _find_var_in_expr(child, _depth + 1, _max_depth)
                            if vn:
                                return vn
                    for k, v in getattr(node, "__dict__", {}).items():
                        if k.startswith("_"):
                            continue
                        if isinstance(v, (list, tuple)):
                            for c in v:
                                vn = _find_var_in_expr(c, _depth + 1, _max_depth)
                                if vn:
                                    return vn
                        else:
                            vn = _find_var_in_expr(v, _depth + 1, _max_depth)
                            if vn:
                                return vn
                    return None
                base_var = _find_var_in_expr(stmt.name.ptr)
                ptr_type = check_expr(stmt.name.ptr)
                if not ptr_type.endswith("*"):
                    bhumi_report_error(
                        getattr(stmt, "lineno", None),
                        None,
                        f"Dereferencing non-pointer type '{ptr_type}'",
                    )
                pointee = ptr_type[:-1]
                expr_type = check_expr(stmt.expr, expected=pointee)
                if expr_type != pointee:
                    bhumi_report_error(
                        getattr(stmt, "lineno", None),
                        getattr(stmt, "col", None),
                        f"Type mismatch: attempted to store '{expr_type}' into '{ptr_type}'",
                    )
                if base_var is not None and base_var in crumb_map:
                    if base_var in write_revoked:
                        bhumi_report_error(
                            getattr(stmt, "lineno", None),
                            getattr(stmt, "col", None),
                            f"[Crawl-Checker]-[ERR]: write through alias '{base_var}' is not allowed"
                            f" — its write permission was revoked by a newer mutable alias."
                            f" Only the most recently granted mutable alias may write.",
                        )
                    rmax, wmax, rc, wc = crumb_map[base_var]
                    if rc > 0:
                        crumb_map[base_var] = (rmax, wmax, rc - 1, wc)
                    _inc_write(
                        base_var,
                        node_desc=f"UnaryDerefWrite@{getattr(stmt, 'lineno', None)}",
                    )
                return
            var_type = env.lookup(stmt.name)
            if isinstance(stmt.expr, AddressOf) and (
                var_type is not None and var_type.endswith("*")
            ):
                inner = stmt.expr.expr
                if isinstance(inner, Var):
                    original_name = inner.name
                    alias_name = (
                        stmt.name
                        if isinstance(stmt.name, str)
                        else getattr(stmt.name, "name", None)
                    )
                    alias_creations.append(
                        (
                            alias_name,
                            original_name,
                            getattr(stmt, "lineno", None),
                            getattr(stmt, "col", None),
                            alias_creation_counter,
                        )
                    )
                    alias_creation_counter += 1
                    alias_targets.setdefault(original_name, set()).add(alias_name)
                    alias_set.add(alias_name)
            if not var_type:
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Assign to undeclared variable '{stmt.name}'",
                )
            global_decl = next((g for g in prog.globals if g.name == stmt.name), None)
            if global_decl and global_decl.nomd:
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Cannot assign to 'nomd' global variable '{stmt.name}'",
                )
            if (
                isinstance(stmt.expr, BinOp)
                and isinstance(stmt.expr.left, Var)
                and stmt.expr.left.name == stmt.name
            ):
                right_type = check_expr(stmt.expr.right)
                left_type = var_type
                if (
                    stmt.expr.op == "+"
                    and left_type == "string"
                    and right_type == "string"
                ):
                    expr_type = "string"
                else:
                    common = unify_int_types(left_type, right_type)
                    if not common:
                        if left_type != right_type:
                            bhumi_report_error(
                                getattr(stmt, "lineno", None),
                                getattr(stmt, "col", None),
                                f"Type mismatch in compound assignment '{stmt.expr.op}': {left_type} vs {right_type}",
                            )
                        common = left_type
                    expr_type = common
                _inc_read(
                    stmt.name,
                    node_desc=f"CompoundAssignRead@{getattr(stmt, 'lineno', '?')}",
                )
            else:
                expr_type = check_expr(stmt.expr, expected=var_type)
            if expr_type == "float" and var_type == "float32":
                stmt.expr = Cast("float32", stmt.expr)
                expr_type = "float32"
            elif expr_type == "float32" and var_type == "float":
                stmt.expr = Cast("float", stmt.expr)
                expr_type = "float"
            if expr_type != var_type:
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Assign type mismatch: {var_type} = {expr_type}",
                )
            if func is not None and getattr(func, "is_vasync", False):
                cap = getattr(func, "_vasync_captured", set()) or set()
                exc = set(getattr(func, "vasync_except", []) or [])
                target_name = (
                    stmt.name
                    if isinstance(stmt.name, str)
                    else getattr(stmt.name, "name", None)
                )
                if (
                    isinstance(target_name, str)
                    and target_name in cap
                    and target_name not in exc
                ):
                    bhumi_report_error(
                        getattr(stmt, "lineno", None),
                        getattr(stmt, "col", None),
                        f'Variable "{target_name}" was accessed in a context where its value is volatile/unsure.',
                    )
            _inc_write(
                stmt.name, node_desc=f"AssignWrite@{getattr(stmt, 'lineno', '?')}"
            )
            if isinstance(stmt.name, str):
                if isinstance(stmt.expr, Call):
                    _a_callee = _func_name_map.get(stmt.expr.name)
                    if _a_callee is not None and getattr(_a_callee, "is_nown", False):
                        nown_vars.add(stmt.name)
                elif isinstance(stmt.expr, Var) and stmt.expr.name in nown_vars:
                    nown_vars.add(stmt.name)
            if isinstance(stmt.expr, Var) and var_type.endswith("*"):
                src_name = stmt.expr.name
                if src_name != stmt.name:
                    src_typ = env.lookup(src_name)
                    if src_typ and src_typ.endswith("*") and src_name in alias_set:
                        env.declare(src_name, "undefined")
                        if src_name in crumb_runtime:
                            crumb_runtime[src_name]["owned"] = False
                        if src_name in owned_vars:
                            owned_vars.discard(src_name)
            return
        if isinstance(stmt, ForgetStmt):
            ptr_typ = env.lookup(stmt.varname)
            if ptr_typ is None:
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Cannot forget undeclared variable '{stmt.varname}'",
                )
            if not (ptr_typ.endswith("*") or ptr_typ == "string"):
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Cannot forget non-pointer variable '{stmt.varname}' of type '{ptr_typ}'",
                )
            if ptr_typ == "undefined":
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Compile-time error: double free / forget on variable '{stmt.varname}'",
                )
            if stmt.varname not in nown_vars:
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"'forget({stmt.varname})' is not allowed: \n'{stmt.varname}' does not trace back to a 'nown' (non owning) function.\n"
                    f"Only values returned by 'nown' functions may be manually released with forget() or free().",
                )
            env.declare(stmt.varname, "undefined")
            return
        if isinstance(stmt, CrumbleStmt):
            if env.lookup(stmt.name) is None:
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Cannot crumble undeclared variable '{stmt.name}'",
                )
            if stmt.name in crumb_map:
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Variable '{stmt.name}' already crumbled",
                )
            crumb_map[stmt.name] = (stmt.max_reads, stmt.max_writes, 0, 0)
            crumb_order[stmt.name] = getattr(stmt, "lineno", -1)
            new_allows_write = (stmt.max_writes is None) or (stmt.max_writes > 0)
            if new_allows_write:
                for original, aliases in alias_targets.items():
                    if stmt.name not in aliases:
                        continue
                    for other in list(aliases):
                        if other == stmt.name or other not in crumb_map:
                            continue
                        rmax_o, wmax_o, rc_o, wc_o = crumb_map[other]
                        other_allows_write = (wmax_o is None) or (wmax_o > 0)
                        if other_allows_write:
                            crumb_map[other] = (rmax_o, wc_o, rc_o, wc_o)
                            write_revoked.add(other)
            return
        if isinstance(stmt, IndexAssign):
            arr_name = stmt.array
            var_type = env.lookup(arr_name)
            if not var_type:
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Index-assign to undeclared variable '{arr_name}'",
                )
            if "[" not in var_type or not var_type.endswith("]"):
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Index-assign to non-array variable '{var_type}'",
                )
            base_type = var_type.split("[", 1)[0]
            if "<" in base_type:
                base_type = base_type.split("<", 1)[0]
            _inc_write(
                arr_name, node_desc=f"IndexAssign@{getattr(stmt, 'lineno', '?')}"
            )
            idx_type = check_expr(stmt.index)
            if idx_type != "int":
                bhumi_report_error(
                    getattr(stmt.index, "lineno", None),
                    getattr(stmt.index, "col", None),
                    f"Array index must be 'int', got '{idx_type}'",
                )
            try:
                inside = var_type.split("[", 1)[1][:-1]
                array_len = int(inside) if inside.isdigit() else None
            except Exception:
                array_len = None
            if array_len is not None:
                cval = eval_const_int(stmt.index)
                if cval is not None:
                    if cval < 0 or cval >= array_len:
                        bhumi_report_error(
                            getattr(stmt.index, "lineno", None),
                            getattr(stmt.index, "col", None),
                            f"Array index constant {cval} out of bounds for array of length {array_len}",
                        )
            val_type = check_expr(stmt.value, expected=base_type)
            if val_type != base_type:
                bhumi_report_error(
                    getattr(stmt.value, "lineno", None),
                    getattr(stmt.value, "col", None),
                    f"Index-assign type mismatch: array of {base_type}, got {val_type}",
                )
            return
        if isinstance(stmt, IfStmt):
            cond_type = check_expr(stmt.cond)
            if cond_type != "bool":
                bhumi_report_error(
                    getattr(stmt.cond, "lineno", None),
                    getattr(stmt.cond, "col", None),
                    f"If condition must be bool, got {cond_type}",
                )
            env.push()
            for s in stmt.then_body:
                check_stmt(s, expected_ret, func)
            env.pop()
            if stmt.else_body:
                env.push()
                if isinstance(stmt.else_body, list):
                    for s in stmt.else_body:
                        check_stmt(s, expected_ret, func)
                else:
                    check_stmt(stmt.else_body, expected_ret, func)
                env.pop()
            return
        if isinstance(stmt, WhileStmt):
            cond_type = check_expr(stmt.cond)
            if cond_type != "bool":
                bhumi_report_error(
                    getattr(stmt.cond, "lineno", None),
                    getattr(stmt.cond, "col", None),
                    f"While condition must be bool, got {cond_type}",
                )
            env.push()
            for s in stmt.body:
                check_stmt(s, expected_ret, func)
            env.pop()
            return
        if isinstance(stmt, TypeSwitch):
            if stmt.subject == "#":
                if func is None or func.ret_type != "#":
                    bhumi_report_error(
                        getattr(stmt, "lineno", None),
                        getattr(stmt, "col", None),
                        "typeswitch subject '#' is only allowed in functions whose declared return type is the caller-placeholder '<#>'.\n "
                        "Either change the function to return '<#>' (e.g. `fn foo() <#> { ... }`) or switch on a type parameter instead (e.g. `typeswitch(T)`).",
                    )
            else:
                if func is not None and stmt.subject not in (func.type_params or []):
                    bhumi_report_error(
                        getattr(stmt, "lineno", None),
                        getattr(stmt, "col", None),
                        f"typeswitch subject '{stmt.subject}' is not a type parameter",
                    )
            for case in stmt.cases:
                base_type = case.typ.rstrip("*")
                if "[" in base_type and base_type.endswith("]"):
                    base_type = base_type.split("[", 1)[0]
                if "<" in base_type:
                    base_type = base_type.split("<", 1)[0]
                if (
                    base_type not in type_map
                    and base_type not in struct_defs
                    and base_type not in enum_defs
                    and base_type not in (func.type_params if func else [])
                ):
                    bhumi_report_error(
                        getattr(stmt, "lineno", None),
                        getattr(stmt, "col", None),
                        f"Unknown type in typeswitch case: {case.typ}",
                    )
                env.push()
                case_expected = case.typ if stmt.subject == "#" else expected_ret
                for s in case.body:
                    check_stmt(s, case_expected, func)
                env.pop()
            if stmt.fallback:
                env.push()
                for s in stmt.fallback:
                    check_stmt(s, expected_ret, func)
                env.pop()
            return
        if isinstance(stmt, ReturnStmt):
            if stmt.expr:
                actual = check_expr(stmt.expr, expected=expected_ret)
                if actual == "float" and expected_ret == "float32":
                    stmt.expr = Cast("float32", stmt.expr)
                    actual = "float32"
                elif actual == "float32" and expected_ret == "float":
                    stmt.expr = Cast("float", stmt.expr)
                    actual = "float"
                if func is not None and (
                    getattr(func, "type_params", None) or func.ret_type == "#"
                ):
                    return
                common = unify_types(actual, expected_ret)
                def _is_mono_of(actual_t, expected_t):
                    if actual_t is None or expected_t is None:
                        return False
                    base_m = re.match(r"^([A-Za-z_]\w*)__mono__", actual_t)
                    if not base_m:
                        return False
                    base = base_m.group(1)
                    gm = re.fullmatch(re.escape(base) + r"<.+>", expected_t)
                    return gm is not None
                if actual != expected_ret and (not common or common != expected_ret):
                    if not _is_mono_of(actual, expected_ret) and not _is_mono_of(actual.rstrip("*"), expected_ret.rstrip("*")):
                        bhumi_report_error(
                            getattr(stmt, "lineno", None),
                            getattr(stmt, "col", None),
                            f"Return type mismatch: expected {expected_ret}, got {actual}",
                        )
            else:
                if not (
                    func is not None
                    and (getattr(func, "type_params", None) or func.ret_type == "#")
                ):
                    if expected_ret != "void":
                        bhumi_report_error(
                            getattr(stmt, "lineno", None),
                            getattr(stmt, "col", None),
                            f"Return without value in function returning {expected_ret}",
                        )
            return
        if isinstance(stmt, ExprStmt):
            check_expr(stmt.expr)
            return
        if isinstance(stmt, Match):
            enum_typ = check_expr(stmt.expr)
            enum_base = enum_typ.rstrip("*")
            if "[" in enum_base and enum_base.endswith("]"):
                enum_base = enum_base.split("[", 1)[0]
            if "<" in enum_base:
                enum_base = enum_base.split("<", 1)[0]
            def _resolve_match_enum(raw_typ):
                bare = raw_typ.rstrip("*")
                if bare in enum_defs:
                    return enum_defs[bare], None, bare
                gm2 = re.match(r"^([A-Za-z_]\w*)<", bare)
                if gm2:
                    base2 = gm2.group(1)
                    if base2 in enum_defs:
                        params_m = re.fullmatch(re.escape(base2) + r"<(.+)>", bare)
                        if params_m:
                            param_list = [p.strip() for p in params_m.group(1).split(",")]
                            try:
                                mono2 = ensure_monomorph_for_enum(base2, param_list)
                                conc_variants = enum_variant_map.get(mono2)
                                return enum_defs[base2], conc_variants, mono2
                            except Exception:
                                pass
                        return enum_defs[base2], None, base2
                mono_m2 = re.match(r"^([A-Za-z_]\w*)__mono__", bare)
                if mono_m2:
                    base3 = mono_m2.group(1)
                    if base3 in enum_defs:
                        conc_variants = enum_variant_map.get(bare)
                        return enum_defs[base3], conc_variants, bare
                return None, None, bare
            resolved_edef, conc_variant_list, resolved_name = _resolve_match_enum(enum_typ)
            if resolved_edef is None:
                bhumi_report_error(
                    getattr(stmt.expr, "lineno", None),
                    getattr(stmt.expr, "col", None),
                    f"Cannot match on non-enum type '{enum_typ}'",
                )
            enum_def = resolved_edef
            defined_variants = {v.name for v in enum_def.variants}
            if conc_variant_list is not None:
                concrete_payload = {vname: payload for vname, payload in conc_variant_list}
            else:
                concrete_payload = {v.name: v.typ for v in enum_def.variants}
            seen_variants = set()
            for case in stmt.cases:
                if case.variant not in defined_variants:
                    bhumi_report_error(
                        getattr(case, "lineno", None),
                        getattr(case, "col", None),
                        f"Enum '{enum_typ}' has no variant '{case.variant}'",
                    )
                payload_type = concrete_payload.get(case.variant)
                if payload_type is None and case.binding is not None:
                    bhumi_report_error(
                        getattr(case, "lineno", None),
                        getattr(case, "col", None),
                        f"Variant '{case.variant}' carries no payload; remove binding",
                    )
                if payload_type is not None and case.binding is None:
                    bhumi_report_error(
                        getattr(case, "lineno", None),
                        getattr(case, "col", None),
                        f"Variant '{case.variant}' requires binding of type '{payload_type}'",
                    )
                env.push()
                if case.binding is not None:
                    env.declare(case.binding, payload_type)
                for s in case.body:
                    check_stmt(s, expected_ret, func)
                env.pop()
                seen_variants.add(case.variant)
            if seen_variants != defined_variants:
                missing = defined_variants - seen_variants
                bhumi_report_error(
                    getattr(stmt, "lineno", None),
                    getattr(stmt, "col", None),
                    f"Non-exhaustive match on '{enum_typ}', missing {missing}",
                )
            return
        bhumi_report_error(
            getattr(stmt, "lineno", None),
            getattr(stmt, "col", None),
            f"Unsupported statement: {stmt}",
        )
    for g in prog.globals:
        env.declare(g.name, g.typ)
        if g.nomd:
            crumb_map[g.name] = (None, 0, 0, 0)
    def _collect_used_names(node, out: set):
        if node is None:
            return
        if isinstance(node, Var):
            out.add(node.name)
            return
        if isinstance(node, Assign):
            if isinstance(node.name, str):
                out.add(node.name)
            _collect_used_names(node.expr, out)
            return
        if isinstance(node, IndexAssign):
            if isinstance(node.array, str):
                out.add(node.array)
            _collect_used_names(node.index, out)
            _collect_used_names(node.value, out)
            return
        if isinstance(node, list):
            for n in node:
                _collect_used_names(n, out)
            return
        for attr in getattr(node, "__dict__", {}):
            val = getattr(node, attr)
            if isinstance(val, list):
                for item in val:
                    _collect_used_names(item, out)
            elif hasattr(val, "__dict__"):
                _collect_used_names(val, out)
    def _collect_local_decls(node, out: set):
        if node is None:
            return
        if isinstance(node, VarDecl):
            out.add(node.name)
            return
        if isinstance(node, list):
            for n in node:
                _collect_local_decls(n, out)
            return
        for attr in getattr(node, "__dict__", {}):
            val = getattr(node, attr)
            if isinstance(val, list):
                for item in val:
                    _collect_local_decls(item, out)
            elif hasattr(val, "__dict__"):
                _collect_local_decls(val, out)
    for func in prog.funcs:
        used = set()
        for s in func.body or []:
            _collect_used_names(s, used)
        local_names = {pname for (_, pname) in func.params}
        local_decls = set()
        for s in func.body or []:
            _collect_local_decls(s, local_decls)
        local_names |= local_decls
        captured = used - local_names
        func._vasync_captured = captured
        if getattr(func, "vasync_except", None) is None:
            func.vasync_except = []
        env.push()
        for (param_typ, param_name) in func.params:
            env.declare(param_name, param_typ)
        _pre_func_crumb_keys = set(crumb_map.keys())
        alias_creations.clear()
        alias_targets.clear()
        alias_set.clear()
        crumb_order.clear()
        nown_vars.clear()
        write_revoked.clear()
        reachable = True
        for i, s in enumerate((func.body or [])):
            if not reachable:
                print(
                    f"[BhumiCompiler-WARN-Reachability]: unreachable code in function '{func.name}' at statement index {i}"
                )
                check_stmt(s, func.ret_type, func)
                continue
            check_stmt(s, func.ret_type, func)
            if isinstance(s, ReturnStmt):
                reachable = False
            elif (
                isinstance(s, ExprStmt)
                and isinstance(s.expr, Call)
                and s.expr.name
                in (
                    "exit",
                    "bhumi_oob_abort",
                    "bhumi_null_abort",
                    "bhumi_vvolatile_abort",
                )
            ):
                reachable = False
        env.pop()
        _func_crumb_keys = set(crumb_map.keys()) - _pre_func_crumb_keys
        for (alias_name, original_name, lineno, col, idx) in alias_creations:
            if alias_name is None:
                bhumi_report_error(
                    lineno,
                    col,
                    f"Internal alias error: alias name is None (original='{original_name}')",
                )
            if alias_name not in crumb_map:
                bhumi_report_error(
                    lineno,
                    col,
                    f"Alias '{alias_name}' must have a corresponding crumble({alias_name}) statement to declare mutability (e.g. crumble({alias_name})!r=<read_count>!w=<write_count>;)",
                )
        over_errors = []
        for name in _func_crumb_keys:
            rmax, wmax, rc, wc = crumb_map[name]
            over_r = (rc - rmax) if (rmax is not None and rc > rmax) else 0
            over_w = (wc - wmax) if (wmax is not None and wc > wmax) else 0
            if over_r or over_w:
                over_errors.append((name, rmax, wmax, rc, wc, over_r, over_w))
        if over_errors:
            msgs = []
            for (name, rmax, wmax, rc, wc, orr, ow) in over_errors:
                msgs.append(
                    f"'Var \"{name}\"': reads {rc} (limit {rmax}, over {orr}), writes {wc} (limit {wmax}, over {ow})"
                )
            bhumi_report_error(
                None,
                None,
                "[Crawl-Checker]-[ERR]: Crumble limits exceeded: " + "; ".join(msgs),
            )
        for name in _func_crumb_keys:
            rmax, wmax, rc, wc = crumb_map[name]
            if rmax is not None and rc < rmax:
                print(
                    f"[Crawl-Checker]-[WARN]: unused read crumbs on '{name}': {rmax - rc} left. [This is not an error but a security warning!]"
                )
            if wmax is not None and wc < wmax:
                print(
                    f"[Crawl-Checker]-[WARN]: unused write crumbs on '{name}': {wmax - wc} left. [This is not an error but a security warning!]"
                )
            del crumb_map[name]
class AsyncStateMachine:
    def __init__(self, func: Func, codegen):
        self.func = func
        self.codegen = codegen
        self.states: List[List[str]] = []
        self.current_state = 0
        self.allocas: List[Tuple[str, str]] = []
        self.local_decls: List[Tuple[str, str]] = []
        self.promoted: set = set()
    def _expr_uses_name(self, e: Expr, name: str) -> bool:
        if e is None:
            return False
        if getattr(e, "name", None) == name and type(e).__name__ == "Var":
            return True
        if isinstance(e, Call):
            return any(self._expr_uses_name(a, name) for a in e.args)
        if isinstance(e, BinOp):
            return self._expr_uses_name(e.left, name) or self._expr_uses_name(
                e.right, name
            )
        if isinstance(e, UnaryOp):
            return self._expr_uses_name(e.expr, name)
        if hasattr(e, "__dict__"):
            for v in e.__dict__.values():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, Expr) and self._expr_uses_name(item, name):
                            return True
                elif isinstance(v, Expr):
                    if self._expr_uses_name(v, name):
                        return True
        return False
    def _stmt_uses_name(self, st: Stmt, name: str) -> bool:
        if st is None:
            return False
        if isinstance(st, ExprStmt):
            return self._expr_uses_name(st.expr, name)
        if isinstance(st, VarDecl):
            if getattr(st, "expr", None):
                return self._expr_uses_name(st.expr, name)
            return False
        if isinstance(st, Assign):
            if not isinstance(st.name, str) and hasattr(st.name, "__dict__"):
                try:
                    if self._expr_uses_name(st.name, name):
                        return True
                except Exception:
                    pass
            return self._expr_uses_name(st.expr, name)
        if isinstance(st, IfStmt):
            if self._expr_uses_name(st.cond, name):
                return True
            for s in st.then_body:
                if self._stmt_uses_name(s, name):
                    return True
            if st.else_body:
                if isinstance(st.else_body, list):
                    for s in st.else_body:
                        if self._stmt_uses_name(s, name):
                            return True
                else:
                    if self._stmt_uses_name(st.else_body, name):
                        return True
            return False
        if isinstance(st, WhileStmt):
            if self._expr_uses_name(st.cond, name):
                return True
            for s in st.body:
                if self._stmt_uses_name(s, name):
                    return True
            return False
        if isinstance(st, ReturnStmt):
            if getattr(st, "expr", None):
                return self._expr_uses_name(st.expr, name)
            return False
        if hasattr(st, "__dict__"):
            for v in st.__dict__.values():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, Stmt) and self._stmt_uses_name(item, name):
                            return True
                        if isinstance(item, Expr) and self._expr_uses_name(item, name):
                            return True
                elif isinstance(v, Expr):
                    if self._expr_uses_name(v, name):
                        return True
                elif isinstance(v, Stmt):
                    if self._stmt_uses_name(v, name):
                        return True
        return False
    def _contains_await(self, stmt: Stmt) -> bool:
        if isinstance(stmt, ExprStmt):
            return self._expr_contains_await(stmt.expr)
        if isinstance(stmt, VarDecl):
            return stmt.expr is not None and self._expr_contains_await(stmt.expr)
        if isinstance(stmt, Assign):
            return self._expr_contains_await(stmt.expr)
        if isinstance(stmt, ReturnStmt):
            return stmt.expr is not None and self._expr_contains_await(stmt.expr)
        if hasattr(stmt, "__dict__"):
            for v in stmt.__dict__.values():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, Stmt) and self._contains_await(item):
                            return True
                        if isinstance(item, Expr) and self._expr_contains_await(item):
                            return True
                elif isinstance(v, Expr):
                    if self._expr_contains_await(v):
                        return True
                elif isinstance(v, Stmt):
                    if self._contains_await(v):
                        return True
        return False
    def _expr_contains_await(self, e: Expr) -> bool:
        if e is None:
            return False
        if isinstance(e, AwaitExpr):
            return True
        if isinstance(e, BinOp):
            return self._expr_contains_await(e.left) or self._expr_contains_await(
                e.right
            )
        if isinstance(e, UnaryOp):
            return self._expr_contains_await(e.expr)
        if isinstance(e, Call):
            return any(self._expr_contains_await(a) for a in e.args)
        if hasattr(e, "__dict__"):
            for v in e.__dict__.values():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, Expr) and self._expr_contains_await(item):
                            return True
                elif isinstance(v, Expr):
                    if self._expr_contains_await(v):
                        return True
        return False
    def _compute_promoted_locals(self):
        await_positions = [
            i for i, st in enumerate(self.func.body) if self._contains_await(st)
        ]
        decl_positions = {}
        for i, st in enumerate(self.func.body):
            if isinstance(st, VarDecl):
                decl_positions[st.name] = i
        promoted = set()
        for name, decl_i in decl_positions.items():
            for ai in await_positions:
                if decl_i < ai:
                    for later in self.func.body[ai + 1 :]:
                        if self._stmt_uses_name(later, name):
                            promoted.add(name)
                            break
                    if name in promoted:
                        break
        self.promoted = promoted
    def _split_at_await(
        self, stmt: Stmt
    ) -> Tuple[List[str], Optional[AwaitExpr], List[str]]:
        if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, AwaitExpr):
            return ([], stmt.expr, [])
        if isinstance(stmt, VarDecl) and isinstance(stmt.expr, AwaitExpr):
            llvm_ty = llvm_ty_of(stmt.typ)
            after_lines = [
                f"  store {llvm_ty} %await_ret, {llvm_ty}* %{stmt.name}_addr"
            ]
            return ([], stmt.expr, after_lines)
        if isinstance(stmt, Assign) and isinstance(stmt.expr, AwaitExpr):
            return ([], stmt.expr, [])
        if isinstance(stmt, ReturnStmt) and isinstance(stmt.expr, AwaitExpr):
            return ([], stmt.expr, [])
        return ([], None, [])
    def _build_states(self):
        self.states = []
        self.allocas = list(self.allocas)
        self.current_state = 0
        self.local_decls = list(self.local_decls)
        accum: List[str] = []
        for st in self.func.body:
            if self._contains_await(st):
                before, await_expr, after = self._split_at_await(st)
                for bstmt in before:
                    accum.append(bstmt)
                if isinstance(st, VarDecl) and isinstance(st.expr, AwaitExpr):
                    llvm_ty = llvm_ty_of(st.typ)
                    if not symbol_table.lookup(st.name):
                        symbol_table.declare(st.name, llvm_ty, st.name)
                    if not any(nm == st.name for nm, _ in self.allocas):
                        self.allocas.append((st.name, llvm_ty))
                        self.local_decls.append((st.typ, st.name))
                self.states.append(list(accum))
                accum = []
                self.current_state += 1
                if isinstance(await_expr.expr, Call):
                    cal = await_expr.expr
                    call_target = ensure_monomorph_call(cal, accum)
                    concrete_fn = next(
                        (f for f in all_funcs if f.name == call_target), None
                    )
                    arg_tokens: List[str] = []
                    if concrete_fn:
                        for a, (param_typ, _) in zip(cal.args, concrete_fn.params):
                            arg_tmp = (
                                self.codegen.gen_expr(a, [])
                                if hasattr(self.codegen, "gen_expr")
                                else None
                            )
                            if arg_tmp is None:
                                arg_tokens.append(f"{llvm_ty_of(param_typ)} 0")
                            else:
                                arg_tokens.append(f"{llvm_ty_of(param_typ)} {arg_tmp}")
                    else:
                        for a in cal.args:
                            arg_tmp = (
                                self.codegen.gen_expr(a, [])
                                if hasattr(self.codegen, "gen_expr")
                                else None
                            )
                            if arg_tmp is None:
                                arg_tokens.append("i64 0")
                            else:
                                arg_tokens.append(f"i64 {arg_tmp}")
                    args_ir = ", ".join(arg_tokens)
                    struct_name = f"%async.{call_target}"
                    accum.append(
                        f"  %await_handle = call {struct_name}* @{call_target}_init({args_ir})"
                    )
                    accum.append(
                        f"  %await_done = call i1 @{call_target}_resume({struct_name}* %await_handle)"
                    )
                    suspend_lbl = new_label("await_suspend")
                    cont_lbl = new_label("await_cont")
                    accum.append(
                        f"  %cmp{self.current_state} = icmp eq i1 %await_done, 0"
                    )
                    accum.append(
                        f"  br i1 %cmp{self.current_state}, label %{suspend_lbl}, label %{cont_lbl}"
                    )
                    accum.append(f"{suspend_lbl}:")
                    accum.append(f"  store i32 {self.current_state}, i32* %stptr")
                    accum.append(f"  ret i1 0")
                    accum.append(f"{cont_lbl}:")
                    ret_llvm = (
                        llvm_ty_of(concrete_fn.ret_type) if concrete_fn else "i64"
                    )
                    accum.append(
                        f"  %res_ptr = getelementptr inbounds {struct_name}, {struct_name}* %await_handle, i32 0, i32 1"
                    )
                    accum.append(
                        f"  %await_ret = load {ret_llvm}, {ret_llvm}* %res_ptr"
                    )
                else:
                    accum.append("  ret i1 0")
                if after:
                    accum.extend(after)
            else:
                if isinstance(st, ReturnStmt):
                    if st.expr is not None:
                        tmp = self.codegen.gen_expr(st.expr, accum)
                        ret_ty = llvm_ty_of(self.func.ret_type)
                        accum.append(
                            f"  %ret_ptr = getelementptr inbounds %async.{self.func.name}, %async.{self.func.name}* %sm, i32 0, i32 1"
                        )
                        accum.append(f"  store {ret_ty} {tmp}, {ret_ty}* %ret_ptr")
                    accum.append("  ret i1 1")
                else:
                    self.codegen._gen_stmt(st, accum, llvm_ty_of(self.func.ret_type))
        if accum:
            self.states.append(list(accum))
    def generate(self) -> List[str]:
        name = self.func.name
        st_ty = f"%async.{name}"
        lines: List[str] = []
        param_types = [llvm_ty_of(t) for t, n in self.func.params]
        ret_ty = llvm_ty_of(self.func.ret_type)
        self._compute_promoted_locals()
        all_local_decls: List[VarDecl] = []
        for st in self.func.body:
            if isinstance(st, VarDecl):
                all_local_decls.append(st)
        self.non_promoted_locals: List[Tuple[str, str]] = []
        for st in all_local_decls:
            llvm_ty = llvm_ty_of(st.typ)
            if st.name in self.promoted:
                continue
            if not symbol_table.lookup(st.name):
                symbol_table.declare(st.name, llvm_ty, st.name)
            self.non_promoted_locals.append((st.typ, st.name))
        self._compute_promoted_locals()
        for pname in self.promoted:
            decl_typ = None
            for st in self.func.body:
                if isinstance(st, VarDecl) and st.name == pname:
                    decl_typ = st.typ
                    break
            if decl_typ is None:
                continue
            llvm_ty = llvm_ty_of(decl_typ)
            if not any(nm == pname for nm, _ in self.allocas):
                self.allocas.append((pname, llvm_ty))
                self.local_decls.append((decl_typ, pname))
            try:
                if not symbol_table.lookup(pname):
                    symbol_table.declare(pname, llvm_ty, pname)
            except Exception:
                pass
        local_types = [llvm_ty_of(t) for (t, n) in getattr(self, "local_decls", [])]
        fields = ["i32", ret_ty] + param_types + local_types
        lines.append(f"{st_ty} = type {{ {', '.join(fields)} }}")
        params = ", ".join(f"{llvm_ty_of(t)} %{n}" for t, n in self.func.params)
        lines.append(f"define {st_ty}* @{name}_init({params}) {{")
        lines.append("entry:")
        lines.append(f"  %szptr = getelementptr inbounds {st_ty}, {st_ty}* null, i32 1")
        lines.append(f"  %sz = ptrtoint {st_ty}* %szptr to i64")
        lines.append(f"  %raw = call i8* @malloc(i64 %sz)")
        lines.append(f"  %s = bitcast i8* %raw to {st_ty}*")
        lines.append(
            f"  %st0 = getelementptr inbounds {st_ty}, {st_ty}* %s, i32 0, i32 0"
        )
        lines.append(f"  store i32 0, i32* %st0")
        for i, (typ, namep) in enumerate(self.func.params):
            idx = 2 + i
            lines.append(
                f"  %p{i}_ptr = getelementptr inbounds {st_ty}, {st_ty}* %s, i32 0, i32 {idx}"
            )
            lines.append(
                f"  store {llvm_ty_of(typ)} %{namep}, {llvm_ty_of(typ)}* %p{i}_ptr"
            )
        for idx, (nm, ty) in enumerate(self.allocas):
            field_index = 2 + len(self.func.params) + idx
            lines.append(
                f"  %{nm}_init_addr = getelementptr inbounds {st_ty}, {st_ty}* %s, i32 0, i32 {field_index}"
            )
            if ty.endswith("*"):
                lines.append(f"  store {ty} null, {ty}* %{nm}_init_addr")
            elif ty == "double" or ty == "float":
                lines.append(f"  store {ty} 0.0, {ty}* %{nm}_init_addr")
            elif ty.startswith("i"):
                lines.append(f"  store {ty} 0, {ty}* %{nm}_init_addr")
            else:
                lines.append(f"  store {ty} zeroinitializer, {ty}* %{nm}_init_addr")
        lines.append(f"  ret {st_ty}* %s")
        lines.append("}")
        lines.append(f"define i1 @{name}_resume({st_ty}* %sm) {{")
        lines.append("entry:")
        for typ, namep in getattr(self, "non_promoted_locals", []):
            llvm_ty = llvm_ty_of(typ)
            lines.append(f"  %{namep}_addr = alloca {llvm_ty}")
            if llvm_ty.endswith("*"):
                lines.append(f"  store {llvm_ty} null, {llvm_ty}* %{namep}_addr")
            elif llvm_ty == "double" or llvm_ty == "float":
                lines.append(f"  store {llvm_ty} 0.0, {llvm_ty}* %{namep}_addr")
            elif llvm_ty.startswith("i"):
                lines.append(f"  store {llvm_ty} 0, {llvm_ty}* %{namep}_addr")
            else:
                lines.append(
                    f"  store {llvm_ty} zeroinitializer, {llvm_ty}* %{namep}_addr"
                )
            decl_node = next(
                (
                    s
                    for s in self.func.body
                    if isinstance(s, VarDecl) and s.name == namep
                ),
                None,
            )
            if decl_node is not None and getattr(decl_node, "expr", None) is not None:
                val = self.codegen.gen_expr(decl_node.expr, lines)
                if val is not None:
                    lines.append(f"  store {llvm_ty} {val}, {llvm_ty}* %{namep}_addr")
        for idx, (nm, ty) in enumerate(self.allocas):
            field_index = 2 + len(self.func.params) + idx
            lines.append(
                f"  %{nm}_addr = getelementptr inbounds {st_ty}, {st_ty}* %sm, i32 0, i32 {field_index}"
            )
        lines.append(
            f"  %stptr = getelementptr inbounds {st_ty}, {st_ty}* %sm, i32 0, i32 0"
        )
        lines.append(f"  %st = load i32, i32* %stptr")
        self._build_states()
        if self.states:
            lines.append(f"  switch i32 %st, label %state0 [")
            for i in range(len(self.states)):
                lines.append(f"	i32 {i}, label %state{i}")
            lines.append("  ]")
        for i, st in enumerate(self.states):
            lines.append(f"state{i}:")
            for l in st:
                lines.append(l)
            last = st[-1].strip() if st else ""
            if not (
                last.startswith("ret")
                or last == "unreachable"
                or last.startswith("br ")
            ):
                if i + 1 < len(self.states):
                    lines.append(f"  br label %state{i+1}")
                else:
                    if ret_ty != "void":
                        lines.append(
                            f"  %ret_ptr = getelementptr inbounds {st_ty}, {st_ty}* %sm, i32 0, i32 1"
                        )
                        if ret_ty == "double":
                            lines.append(f"  store {ret_ty} 0.0, {ret_ty}* %ret_ptr")
                        elif ret_ty.startswith("i"):
                            lines.append(f"  store {ret_ty} 0, {ret_ty}* %ret_ptr")
                        else:
                            lines.append(f"  store {ret_ty} null, {ret_ty}* %ret_ptr")
                    lines.append("  ret i1 1")
        if not self.states:
            lines.append("state0:")
            if ret_ty != "void":
                lines.append(
                    f"  %ret_ptr = getelementptr inbounds {st_ty}, {st_ty}* %sm, i32 0, i32 1"
                )
                if ret_ty == "double":
                    lines.append(f"  store {ret_ty} 0.0, {ret_ty}* %ret_ptr")
                elif ret_ty.startswith("i"):
                    lines.append(f"  store {ret_ty} 0, {ret_ty}* %ret_ptr")
                else:
                    lines.append(f"  store {ret_ty} null, {ret_ty}* %ret_ptr")
            lines.append("  ret i1 1")
        lines.append("}")
        return lines
def main():
    global all_funcs, func_table, builtins_emitted
    all_funcs = []
    func_table = {}
    builtins_emitted = False
    enum_variant_map.clear()
    symbol_table.clear()
    struct_field_map.clear()
    string_constants.clear()
    generated_mono.clear()
    parser = argparse.ArgumentParser(description="Bhumi Compiler")
    parser.add_argument("input", help="Input source file (.bhumi or .sbhumi)")
    parser.add_argument(
        "-o", "--output", required=True, help="Output LLVM IR file (.ll)"
    )
    args = parser.parse_args()
    global compiled
    compiled = args.input
    _expr_type_cache.clear()
    _parse_cache.clear()
    with open(args.input, encoding="utf-8", errors="ignore") as f:
        src = f.read()
    tokens = lex(src)
    parser_obj = Parser(tokens)
    main_prog = parser_obj.parse()
    seen_imports = set()
    seen_func_signatures = set()
    all_funcs = []
    all_structs = []
    all_enums = []
    all_globals = []
    def load_imports_recursively(prog, all_funcs, all_structs, all_enums, all_globals):
        for imp in prog.imports:
            candidates = []
            if imp.endswith(".bu"):
                candidates.append(imp + "hmi")
            elif imp.endswith(".sbhu"):
                candidates.append(imp + "hmi")
            elif imp.endswith(".bhumi") or imp.endswith(".sbhumi"):
                candidates.append(imp)
            else:
                candidates += [imp + ".bhumi", imp + ".sbhumi"]
            resolved_path = None
            for path in candidates:
                if os.path.isfile(path):
                    resolved_path = os.path.abspath(path)
                    break
            if not resolved_path and os.path.isdir(imp):
                for base in ("index", "main"):
                    for ext in (".bhumi", ".sbhumi"):
                        candidate = os.path.join(imp, base + ext)
                        if os.path.isfile(candidate):
                            resolved_path = os.path.abspath(candidate)
                            break
                    if resolved_path:
                        break
            if not resolved_path:
                bhumi_report_error(
                    None, None, f"Import '{imp}' not found. Tried: {candidates} + ..."
                )
            if resolved_path in seen_imports:
                continue
            seen_imports.add(resolved_path)
            if resolved_path in _parse_cache:
                sub_prog = _parse_cache[resolved_path]
            else:
                with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
                    imported_src = f.read()
                global compiled
                previous_compiled = compiled
                compiled = resolved_path
                try:
                    imported_tokens = lex(imported_src)
                    imported_parser = Parser(imported_tokens)
                    sub_prog = imported_parser.parse()
                    _parse_cache[resolved_path] = sub_prog
                finally:
                    compiled = previous_compiled
            load_imports_recursively(
                sub_prog, all_funcs, all_structs, all_enums, all_globals
            )
            all_structs.extend(sub_prog.structs)
            all_enums.extend(sub_prog.enums)
            all_globals.extend(sub_prog.globals)
            for func in sub_prog.funcs:
                sig = (func.name, len(func.params), func.is_extern)
                if sig not in seen_func_signatures:
                    all_funcs.append(func)
                    seen_func_signatures.add(sig)
    load_imports_recursively(main_prog, all_funcs, all_structs, all_enums, all_globals)
    all_funcs.extend(main_prog.funcs)
    all_structs.extend(main_prog.structs)
    all_enums.extend(main_prog.enums)
    all_globals.extend(main_prog.globals)
    final_prog = Program(
        funcs=all_funcs,
        imports=main_prog.imports,
        structs=all_structs,
        enums=all_enums,
        globals=all_globals,
    )
    seen_names = {}
    for idx, fn in enumerate(final_prog.funcs):
        if fn.name in seen_names:
            prev_idx = seen_names[fn.name]
            bhumi_report_error(
                None,
                None,
                f"Duplicate function definition: '{fn.name}', remove or rename the duplicate.",
            )
        seen_names[fn.name] = idx
    seen_enum_names = {}
    for idx, en in enumerate(final_prog.enums):
        if en.name in seen_enum_names:
            bhumi_report_error(
                None,
                None,
                f"Duplicate enum definition: '{en.name}', remove or rename the duplicate.",
            )
        seen_enum_names[en.name] = idx
    seen_struct_names = {}
    for idx, st in enumerate(final_prog.structs):
        if st.name in seen_struct_names:
            bhumi_report_error(
                None,
                None,
                f"Duplicate struct definition: '{st.name}', remove or rename the duplicate.",
            )
        seen_struct_names[st.name] = idx
    has_main = any(fn.name == "main" for fn in final_prog.funcs)
    if not has_main and not no_main:
        bhumi_report_error(
            None,
            None,
            "No startpoint: no main function found. Add a 'fn main(...) <...>' function, or use @nomain; to suppress emission of the wrapper startpoint.",
        )
    for fn in final_prog.funcs:
        if getattr(fn, "is_async", False) and (fn.body is None or len(fn.body) == 0):
            bhumi_report_error(
                None,
                None,
                f"Async function '{fn.name}' has an empty body; async functions must contain at least one statement or be removed.",
            )
    check_types(final_prog)
    func_table.clear()
    for _fn in final_prog.funcs:
        if _fn.type_params or _fn.ret_type == "#":
            continue
        func_table[_fn.name] = llvm_ty_of(_fn.ret_type)
    func_table.update({
        "exit": "void", "malloc": "i8*", "free": "void",
        "bhumi_c_free": "void",
        "bhumi_tbl_insert": "void", "bhumi_tbl_remove": "void",
        "bhumi_tbl_contains": "i1",
        "puts": "i32", "strlen": "i64",
        "bhumi_argc": "i64", "bhumi_argv": "i8*",
    })
    annotate_types(final_prog)
    llvm = compile_program(final_prog)
    with open(args.output, "w", encoding="utf-8", errors="ignore") as f:
        f.write(llvm)
if __name__ == "__main__":
    main()
