// 规则 4.1 — 选择结构: if 无 else（依赖 1.1, 3.1，扩展 1.2）
// <语句>   -> <if语句>
// <if语句> -> if <表达式> <语句块> <else部分>
// <else部分> -> 空
// 演示：不带 else 的 if 语句（来自 PDF 示例 program_4_10）

fn program_4_10(a:i32) -> i32 {
    if a>0 {
        return 1;
    }
    return 0;
}
#
