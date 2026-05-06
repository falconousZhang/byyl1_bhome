"""MIPS assembly code generator from quadruple IR.

Calling convention (simplified, leaf-function friendly):
  $a0-$a3  : first 4 incoming parameters
  $v0      : return value
  $t0-$t1  : scratch registers for computation
  $sp      : stack pointer (fixed inside a function; no nested calls)
  0($sp)   : saved $ra

Stack frame layout (per function, words from $sp):
  +0    : $ra save slot
  +4    : param_0
  +8    : param_1
  ...
  +...  : local variables
  +...  : temporaries
  +...  : array/tuple data cells
"""


def _is_imm(v: str) -> bool:
    return v != '_' and v.lstrip('-').isdigit()


def _is_label(v: str) -> bool:
    return v.startswith('L')


def _needs_slot(v: str) -> bool:
    return v != '_' and not _is_imm(v) and not _is_label(v)


# ── Per-function code generator ───────────────────────────────────────────────

class FuncGen:
    def __init__(self, name: str, quads: list[dict]):
        self.name       = name
        self.quads      = quads
        self.lines: list[str]      = []
        self.var_off: dict[str, int] = {}   # name -> byte offset from $sp
        self.arrays:  dict[str, int] = {}   # array_temp -> element count
        self.tuples:  dict[str, int] = {}   # tuple_temp -> element count
        self.params:  list[str]      = []
        self.frame   = 0                    # total frame size in bytes

    # ── phase 1: collect variable slots ──────────────────────────────────────

    def _collect(self):
        order: list[str] = []
        seen:  set[str]  = set()

        def add(v: str):
            if _needs_slot(v) and v not in seen:
                seen.add(v); order.append(v)

        for q in self.quads:
            op, a1, a2, r = q['op'], q['arg1'], q['arg2'], q['result']
            if op in ('func_begin', 'func_end'):
                pass  # skip: function name must not become a stack slot
            elif op == 'param':
                self.params.append(a1); add(a1)
            elif op == 'alloc[]':
                n = int(a1); self.arrays[r] = n
                add(r)
                for i in range(n): add(f'__a_{r}_{i}')
            elif op == 'alloc()':
                n = int(a1); self.tuples[r] = n
                add(r)
                for i in range(n): add(f'__u_{r}_{i}')
            else:
                for v in (a1, a2, r): add(v)

        # slot 0 reserved for $ra; variables start at slot 1
        self.frame = 4 * (len(order) + 1)
        self.var_off = {'__ra': 0}
        for i, name in enumerate(order):
            self.var_off[name] = 4 * (i + 1)

    # ── emit helpers ──────────────────────────────────────────────────────────

    def _asm(self, s: str):
        self.lines.append(s)

    def _load(self, v: str, reg: str):
        """Load value/variable v into reg."""
        if v == '_':
            self._asm(f'    li      {reg}, 0')
        elif _is_imm(v):
            self._asm(f'    li      {reg}, {v}')
        else:
            off = self.var_off.get(v)
            if off is not None:
                self._asm(f'    lw      {reg}, {off}($sp)')
            else:
                self._asm(f'    # [warn] unknown var: {v}')

    def _store(self, reg: str, name: str):
        """Store reg into variable name's stack slot."""
        if not _needs_slot(name): return
        off = self.var_off.get(name)
        if off is not None:
            self._asm(f'    sw      {reg}, {off}($sp)')

    def _arr_addr(self, arr: str, reg: str):
        """Load base address of array's data cells into reg."""
        slot = f'__a_{arr}_0'
        off  = self.var_off.get(slot, 0)
        self._asm(f'    addiu   {reg}, $sp, {off}')

    def _tup_addr(self, tup: str, reg: str):
        slot = f'__u_{tup}_0'
        off  = self.var_off.get(slot, 0)
        self._asm(f'    addiu   {reg}, $sp, {off}')

    def _idx_addr(self, base_reg: str, idx: str):
        """Offset base_reg by idx*4, leaving result in base_reg."""
        if _is_imm(idx):
            byte_off = int(idx) * 4
            if byte_off:
                self._asm(f'    addiu   {base_reg}, {base_reg}, {byte_off}')
        else:
            self._load(idx, '$t1')
            self._asm(f'    sll     $t1, $t1, 2')
            self._asm(f'    addu    {base_reg}, {base_reg}, $t1')

    # ── phase 2: generate ─────────────────────────────────────────────────────

    def generate(self) -> list[str]:
        self._collect()
        epi = f'__{self.name}_ret'

        # Function label + prologue
        self._asm(f'{self.name}:')
        self._asm(f'    addiu   $sp, $sp, -{self.frame}')
        self._asm(f'    sw      $ra, 0($sp)')

        # Copy $a0-$a3 to parameter slots
        for i, pname in enumerate(self.params[:4]):
            self._asm(f'    sw      $a{i}, {self.var_off[pname]}($sp)    # {pname}')

        # Translate body quads
        for q in self.quads:
            self._quad(q, epi)

        # Epilogue (handles void-return or fall-through)
        self._asm(f'{epi}:')
        self._asm(f'    lw      $ra, 0($sp)')
        self._asm(f'    addiu   $sp, $sp, {self.frame}')
        self._asm(f'    jr      $ra')
        return self.lines

    # ── quad → MIPS ───────────────────────────────────────────────────────────

    def _quad(self, q: dict, epi: str):
        op, a1, a2, r = q['op'], q['arg1'], q['arg2'], q['result']

        if op in ('func_begin', 'func_end', 'param'):
            return

        # ── control flow ──────────────────────────────────────────────────────
        if op == 'label':
            self._asm(f'{r}:')
            return

        if op == 'goto':
            self._asm(f'    j       {r}')
            return

        if op == 'if_false':
            self._load(a1, '$t0')
            self._asm(f'    beq     $t0, $zero, {r}')
            return

        if op == 'return':
            if a1 != '_':
                self._load(a1, '$v0')
            self._asm(f'    j       {epi}')
            return

        # ── assignment ────────────────────────────────────────────────────────
        if op == ':=':
            self._load(a1, '$t0')
            self._store('$t0', r)
            return

        # ── arithmetic ────────────────────────────────────────────────────────
        if op in ('+', '-', '*', '/'):
            self._load(a1, '$t0'); self._load(a2, '$t1')
            if   op == '+': self._asm(f'    addu    $t0, $t0, $t1')
            elif op == '-': self._asm(f'    subu    $t0, $t0, $t1')
            elif op == '*': self._asm(f'    mul     $t0, $t0, $t1')
            elif op == '/':
                self._asm(f'    div     $t0, $t1')
                self._asm(f'    mflo    $t0')
            self._store('$t0', r)
            return

        if op == 'neg':
            self._load(a1, '$t0')
            self._asm(f'    subu    $t0, $zero, $t0')
            self._store('$t0', r)
            return

        # ── comparisons ───────────────────────────────────────────────────────
        if op in ('<', '>', '<=', '>=', '==', '!='):
            self._load(a1, '$t0'); self._load(a2, '$t1')
            if   op == '<':  self._asm(f'    slt     $t0, $t0, $t1')
            elif op == '>':  self._asm(f'    slt     $t0, $t1, $t0')
            elif op == '<=':
                self._asm(f'    slt     $t0, $t1, $t0')   # t0 = (b < a)
                self._asm(f'    xori    $t0, $t0, 1')      # NOT → (a <= b)
            elif op == '>=':
                self._asm(f'    slt     $t0, $t0, $t1')   # t0 = (a < b)
                self._asm(f'    xori    $t0, $t0, 1')      # NOT → (a >= b)
            elif op == '==':
                self._asm(f'    xor     $t0, $t0, $t1')
                self._asm(f'    sltiu   $t0, $t0, 1')      # 1 iff xor == 0
            elif op == '!=':
                self._asm(f'    xor     $t0, $t0, $t1')
                self._asm(f'    sltu    $t0, $zero, $t0')  # 1 iff xor != 0
            self._store('$t0', r)
            return

        # ── references ────────────────────────────────────────────────────────
        if op in ('&', '&mut'):
            off = self.var_off.get(a1, 0)
            self._asm(f'    addiu   $t0, $sp, {off}')
            self._store('$t0', r)
            return

        if op == 'deref':
            self._load(a1, '$t0')
            self._asm(f'    lw      $t0, 0($t0)')
            self._store('$t0', r)
            return

        if op == 'deref_write':     # *a1 = a2
            self._load(a1, '$t0')   # t0 = address
            self._load(a2, '$t1')   # t1 = value
            self._asm(f'    sw      $t1, 0($t0)')
            return

        # ── arrays ────────────────────────────────────────────────────────────
        if op == 'alloc[]':
            self._arr_addr(r, '$t0')
            self._store('$t0', r)
            return

        if op == '[]:=':            # a1[a2] = r(val)
            if a1 in self.arrays:
                self._arr_addr(a1, '$t0')
            else:
                self._load(a1, '$t0')
            self._idx_addr('$t0', a2)
            self._load(r, '$t1')
            self._asm(f'    sw      $t1, 0($t0)')
            return

        if op == '[]':              # r = a1[a2]
            if a1 in self.arrays:
                self._arr_addr(a1, '$t0')
            else:
                self._load(a1, '$t0')
            self._idx_addr('$t0', a2)
            self._asm(f'    lw      $t0, 0($t0)')
            self._store('$t0', r)
            return

        if op == 'arr_len':
            n = self.arrays.get(a1, 0)
            self._asm(f'    li      $t0, {n}')
            self._store('$t0', r)
            return

        # ── tuples ────────────────────────────────────────────────────────────
        if op == 'alloc()':
            self._tup_addr(r, '$t0')
            self._store('$t0', r)
            return

        if op == '.:=':             # a1.a2 = r(val)
            if a1 in self.tuples:
                self._tup_addr(a1, '$t0')
            else:
                self._load(a1, '$t0')
            self._idx_addr('$t0', a2)
            self._load(r, '$t1')
            self._asm(f'    sw      $t1, 0($t0)')
            return

        if op == '.':               # r = a1.a2
            if a1 in self.tuples:
                self._tup_addr(a1, '$t0')
            else:
                self._load(a1, '$t0')
            self._idx_addr('$t0', a2)
            self._asm(f'    lw      $t0, 0($t0)')
            self._store('$t0', r)
            return

        # ── range (value unused in practice) ─────────────────────────────────
        if op == 'range':
            return

        # ── fallback ─────────────────────────────────────────────────────────
        self._asm(f'    # (unhandled) {op}  {a1}  {a2}  {r}')


# ── Top-level splitter ────────────────────────────────────────────────────────

class MIPSGen:
    def __init__(self, quads: list[dict]):
        self.quads = quads

    def _split(self) -> list[tuple[str, list[dict]]]:
        funcs, i = [], 0
        while i < len(self.quads):
            q = self.quads[i]
            if q['op'] == 'func_begin':
                fname = q['arg1']
                j = i + 1
                while j < len(self.quads) and self.quads[j]['op'] != 'func_end':
                    j += 1
                funcs.append((fname, self.quads[i: j + 1]))
                i = j + 1
            else:
                i += 1
        return funcs

    def generate(self) -> str:
        lines = [
            '# MIPS assembly generated by byyl1 compiler',
            '.text',
            '.globl main',
            '',
        ]
        for fname, fquads in self._split():
            fg = FuncGen(fname, fquads)
            lines.extend(fg.generate())
            lines.append('')
        return '\n'.join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_mips(quads: list[dict]) -> str:
    return MIPSGen(quads).generate()
